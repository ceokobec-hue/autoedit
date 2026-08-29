#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_probe.py — 두 카메라의 소리를 대조해 «밀림(offset)»과 «드리프트(speed)»를 잰다.

왜 두 단계인가
  0단계 거친측정 : 소리 «세기 곡선»(엔벨로프)으로 파일 전체를 훑는다.
                   마이크가 서로 달라도(핀마이크 vs 내장) 세기 흐름은 같으므로 안 놓친다.
  1단계 정밀측정 : 거친 값 주변 ±0.5초만 «원본 파형»으로 다시 본다. 0.1ms 해상도.

여러 지점에서 재는 이유
  카메라 두 대의 시계는 미세하게 다르게 간다(드리프트). 한 점만 재면 끝에서 어긋난다.
  세 점 이상의 (시각, 밀림)을 직선으로 맞춰 «기울기»를 얻으면 속도까지 보정할 수 있다.

사용: python3 sync_probe.py A.wav B.wav [--probes 120,780,1440] [--win 20]
출력: 표 + JSON

⛔ 입력은 «영상»이 아니라 «16bit 모노 wav» 다. 영상에서 먼저 뽑는다:
     ffmpeg -i A.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le A.wav
     ffmpeg -i B.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le B.wav
   (-ac 1 = 모노 한 줄로 · -ar 16000 = 1초를 16000칸으로 · pcm_s16le = 압축 없는 16bit)
"""
import argparse, json, os, sys, wave
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (소리 싱크).\n'
        '   이 도구의 부품은 ~/.autoedit/venv 라는 \u00ab작은 방\u00bb 안에 있습니다.\n'
        '   그 방의 파이썬으로 부르세요:\n'
        '     {} {} {}'.format(_v, _o.path.abspath(__file__), ' '.join(_s.argv[1:])) +
        '\n   방이 아직 없다면 설치.md 2단계를 보세요 (python3 doctor.py 로 확인).')


WAV_HOWTO = ('   영상에서 이렇게 뽑습니다:\n'
             '     ffmpeg -i <영상.mp4> -vn -ac 1 -ar 16000 -c:a pcm_s16le <소리.wav>\n'
             '     (-ac 1 = 모노 · -ar 16000 = 1초를 16000칸으로 · pcm_s16le = 압축 없는 16bit)')

def load_wav(path):
    if not os.path.exists(path):
        raise SystemExit('⛔ %s 이(가) 없습니다.\n%s' % (path, WAV_HOWTO))
    try:
        w = wave.open(path, 'rb')
    except Exception:
        raise SystemExit('⛔ %s 은(는) wav 파일이 아닙니다 (영상 파일을 주셨나요?).\n%s'
                         % (path, WAV_HOWTO))
    with w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise SystemExit('⛔ 16bit 모노 wav 가 아닙니다: %s\n%s' % (path, WAV_HOWTO))
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float32)
    x -= x.mean()
    return x, sr


def envelope(x, sr, hop):
    """소리 세기 곡선. 절댓값을 hop 칸씩 묶어 최댓값을 취한다."""
    n = len(x) // hop
    e = np.abs(x[:n * hop]).reshape(n, hop).max(axis=1)
    e = np.log1p(e)                      # 큰 소리에 끌려가지 않게 로그로 눌러준다
    e -= e.mean()
    return e, sr / hop


def ncc_search(template, signal):
    """template 을 signal 위로 밀어보며 가장 잘 포개지는 위치를 찾는다 (정규화 상관).

    반환: (최적 밀림 index, 그때의 상관계수 -1~1, 2등과의 격차)
    """
    nt, ns = len(template), len(signal)
    if ns < nt:
        raise ValueError('검색 구간이 조각보다 짧다')
    N = 1 << int(np.ceil(np.log2(ns + nt)))
    corr = np.fft.irfft(np.fft.rfft(signal, N) * np.conj(np.fft.rfft(template, N)), N)
    corr = corr[:ns - nt + 1]

    # signal 의 구간별 에너지(sliding)를 누적합으로 구해 정규화 → 진짜 상관계수가 된다
    cs = np.concatenate(([0.0], np.cumsum(signal.astype(np.float64) ** 2)))
    loc = np.sqrt(np.maximum(cs[nt:nt + len(corr)] - cs[:len(corr)], 1e-12))
    ncc = corr / (loc * np.sqrt(np.sum(template.astype(np.float64) ** 2)) + 1e-12)

    k = int(np.argmax(ncc))
    # 2등 격차 — 봉우리가 하나뿐인지(믿을 만한지) 보는 지표
    mask = np.ones(len(ncc), bool)
    mask[max(0, k - int(0.25 * len(template))):k + int(0.25 * len(template))] = False
    runner = float(ncc[mask].max()) if mask.any() else 0.0
    return k, float(ncc[k]), float(ncc[k]) - runner


def parabolic(y, k):
    """봉우리 세 점으로 포물선을 그려 «칸 사이»의 참 꼭짓점을 찾는다 (서브샘플 정밀도)."""
    if k <= 0 or k >= len(y) - 1:
        return 0.0
    a, b, c = y[k - 1], y[k], y[k + 1]
    d = a - 2 * b + c
    return 0.0 if d == 0 else float(np.clip(0.5 * (a - c) / d, -0.5, 0.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a'); ap.add_argument('b')
    ap.add_argument('--probes', default='',
                    help='측정할 시각을 쉼표로 직접 지정. 예: --probes 120,780,1440')
    ap.add_argument('--win', type=float, default=20.0,
                    help='한 지점당 비교할 길이(초). ⛔영상이 짧으면 이걸 줄여야 한다 (기본 20)')
    ap.add_argument('--out', default='')
    args = ap.parse_args()

    A, sr = load_wav(args.a)
    B, srb = load_wav(args.b)
    if sr != srb:
        raise SystemExit('⛔ 표본율이 다르다')
    durA, durB = len(A) / sr, len(B) / sr
    print('A(기준) %.2f초 · B %.2f초 · %dHz' % (durA, durB, sr))

    # ── 0단계 · 거친 측정 (세기 곡선) ──────────────────────────────
    HOP = 80                                   # 8000Hz / 80 = 100Hz (10ms 칸)
    ea, fps_e = envelope(A, sr, HOP)
    eb, _ = envelope(B, sr, HOP)
    # A 가운데 4분을 떼어 B 전체 위로 민다
    tlen = int(min(240 * fps_e, len(ea) * 0.5))
    tstart = (len(ea) - tlen) // 2
    tmpl = ea[tstart:tstart + tlen]
    k, score, margin = ncc_search(tmpl, eb)
    coarse = (k - tstart) / fps_e              # B 가 A 보다 이만큼 늦게 시작 (양수 = B 를 당겨야 함)
    print('\n[0단계 거친측정] 밀림 %+.3f초 · 일치도 %.3f · 2등격차 %.3f' % (coarse, score, margin))
    if score < 0.15:
        print('⚠️ 일치도가 낮다 — 두 파일이 같은 소리를 담고 있는지 의심스럽다')

    # ── 1단계 · 정밀 측정 (원본 파형, 여러 지점) ───────────────────
    if args.probes:
        probes = [float(x) for x in args.probes.split(',')]
    else:
        usable = min(durA, durB - coarse) - args.win - 5
        probes = [round(usable * f, 1) for f in (0.08, 0.30, 0.50, 0.70, 0.92)]

    W = int(args.win * sr)
    PAD = int(0.6 * sr)                        # 거친값 주변 ±0.6초만 본다
    rows = []
    for t in probes:
        ia = int(t * sr)
        if ia + W > len(A):
            continue
        tmpl = A[ia:ia + W]
        ib = int((t + coarse) * sr) - PAD
        ib0 = max(0, ib)
        seg = B[ib0:ib0 + W + 2 * PAD]
        if len(seg) < W + 10:
            continue
        k, score, margin = ncc_search(tmpl, seg)

        # 서브샘플 보정을 위해 봉우리 주변 상관값을 다시 계산
        nt = W
        cs = np.concatenate(([0.0], np.cumsum(seg.astype(np.float64) ** 2)))
        N = 1 << int(np.ceil(np.log2(len(seg) + nt)))
        c = np.fft.irfft(np.fft.rfft(seg, N) * np.conj(np.fft.rfft(tmpl, N)), N)[:len(seg) - nt + 1]
        loc = np.sqrt(np.maximum(cs[nt:nt + len(c)] - cs[:len(c)], 1e-12))
        ncc = c / (loc * np.sqrt(np.sum(tmpl.astype(np.float64) ** 2)) + 1e-12)
        frac = parabolic(ncc, k)

        off = (ib0 + k + frac) / sr - t        # 이 시각에서 B 를 얼마나 밀어야 A 와 맞나
        rows.append({'t': t, 'offset': off, 'score': score, 'margin': margin})

    if len(rows) < 2:
        # ⛔ 「측정 지점이 부족하다」 한 줄만 던지면 «그래서 어쩌라는》 건지 알 수 없다.
        #    기본 창(20초)이 영상보다 길면 지점이 하나도 안 잡힌다 → 얼마로 줄이면 되는지 계산해 준다.
        dur = min(len(A), len(B)) / float(sr)
        suggest = max(2.0, round(dur / 5.0))
        raise SystemExit(
            '⛔ 측정 지점이 %d곳뿐이라 드리프트(시계 차이)를 계산할 수 없습니다. 최소 2곳이 필요합니다.\n'
            '   지금 영상이 %.0f초인데 «한 지점당 창»이 %.0f초라 지점이 안 잡힙니다.\n'
            '   → 창을 줄여 다시 돌리세요:   --win %g\n'
            '   → 지점을 직접 찍어 줄 수도 있습니다:  --probes %s\n'
            '   (짧은 클립으로 시험만 하는 거라면 이대로도 «시작 밀림»은 위 0단계 값이 답입니다.)'
            % (len(rows), dur, args.win, suggest,
               ','.join('%g' % (dur * k / 4.0) for k in (1, 2, 3))))

    print('\n[1단계 정밀측정]')
    print('| 지점 | 밀림 | 일치도 | 2등격차 |')
    print('|---|---|---|---|')
    for r in rows:
        print('| %5.1f초 (%02d:%02d) | %+.4f초 | %.3f | %.3f |'
              % (r['t'], int(r['t']) // 60, int(r['t']) % 60, r['offset'], r['score'], r['margin']))

    good = [r for r in rows if r['score'] >= 0.10 and r['margin'] >= 0.02]
    if len(good) < 2:
        print('⚠️ 믿을 만한 지점이 2개 미만 — 세기곡선 값(%+.3f초)만 쓴다' % coarse)
        good = rows

    ts = np.array([r['t'] for r in good]); ofs = np.array([r['offset'] for r in good])
    slope, intercept = np.polyfit(ts, ofs, 1)
    resid = ofs - (slope * ts + intercept)
    speed = 1.0 + slope                        # B 를 이 배율로 재생해야 A 와 같은 속도가 된다
    spread = float(ofs.max() - ofs.min())

    print('\n[판정]')
    print('  시작 밀림      %+.4f초' % intercept)
    print('  드리프트 기울기 %+.6f초/초  →  속도비 %.6f (%.4f%%)' % (slope, speed, (speed - 1) * 100))
    print('  전 구간 벌어짐  %.3f초 (%.1f프레임 @29.97)' % (spread, spread * 29.97))
    print('  직선에서 벗어난 정도 최대 %.4f초 (%.2f프레임)' % (np.abs(resid).max(), np.abs(resid).max() * 29.97))

    if np.abs(resid).max() > 0.033:
        print('  ⚠️ 직선으로 안 맞는다 — 카메라가 중간에 프레임을 흘렸을 수 있다. 구간별 보정 필요')
    if spread < 0.033:
        print('  ✅ 드리프트 없음 — 단순 밀림 보정만으로 충분')
    else:
        print('  ✅ 드리프트 감지 — 속도 보정을 적용한다')

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.a)), '..', '01_sync', 'sync.json')
    # ⛔ --out 을 «지금 폴더의 파일명»으로 주면 dirname 이 '' 이라 makedirs 가 죽는다
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump({'coarse': coarse, 'probes': rows, 'intercept': intercept,
               'slope': slope, 'speed': speed, 'spread': spread,
               'resid_max': float(np.abs(resid).max()), 'durA': durA, 'durB': durB},
              open(out, 'w'), ensure_ascii=False, indent=2)
    print('\n저장: %s' % os.path.normpath(out))


if __name__ == '__main__':
    main()
