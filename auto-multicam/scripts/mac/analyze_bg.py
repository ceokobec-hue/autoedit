#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_bg.py — 맨 보드 이미지들에서 «잉크량 곡선»과 «판서/지움 구간»을 뽑는다.
(board_bg.py 가 만든 bgs.npy 를 쓴다. 영상을 다시 훑지 않는다)

잉크를 재는 법 — «주변보다 어두운 점»만 센다
  화면 전체 밝기와 견주면 보드 가장자리 그늘·조명 반사까지 잉크로 세어 버린다(첫 시도 실패 원인).
  글씨는 «얇고 주변보다 어둡다». 그래서 25픽셀 창 평균(=그 자리의 바탕색)보다
  일정 이상 어두운 점만 남긴다. 넓은 그늘은 창 평균도 같이 어두워지므로 저절로 사라진다.
"""
import argparse, json, os
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (판서 감지).\n'
        '   이 도구의 부품은 ~/.autoedit/venv 라는 \u00ab작은 방\u00bb 안에 있습니다.\n'
        '   그 방의 파이썬으로 부르세요:\n'
        '     {} {} {}'.format(_v, _o.path.abspath(__file__), ' '.join(_s.argv[1:])) +
        '\n   방이 아직 없다면 설치.md 2단계를 보세요 (python3 doctor.py 로 확인).')


def boxblur(img, r):
    """적분영상으로 만든 상자 흐림 — 그 픽셀 «주변의 바탕색»을 구한다."""
    H, Wd = img.shape
    pad = np.pad(img.astype(np.float64), r + 1, mode='edge')
    ii = pad.cumsum(0).cumsum(1)
    y0, y1 = np.arange(H), np.arange(H) + 2 * r + 1
    x0, x1 = np.arange(Wd), np.arange(Wd) + 2 * r + 1
    S = (ii[np.ix_(y1, x1)] - ii[np.ix_(y0, x1)] - ii[np.ix_(y1, x0)] + ii[np.ix_(y0, x0)])
    return S / ((2 * r + 1) ** 2)


def inkmap(b, r=25, thr=7.0):
    return np.clip(boxblur(b, r) - b.astype(np.float64) - thr, 0, None)


def main():
    ap = argparse.ArgumentParser(description='칠판 프레임을 훑어 «판서 중인 구간»을 찾는다')
    ap.add_argument('--dir', required=True, help='board_bg.py 가 뽑아 둔 프레임 폴더')
    ap.add_argument('--dur', type=float, required=True, help='영상 길이(초)')
    a = ap.parse_args()

    d = json.load(open(os.path.join(a.dir, 'board_bg.json')))
    bgs = np.load(os.path.join(a.dir, 'bgs.npy'))
    t = np.array(d['t']); step = d['step']
    n = len(bgs)

    print('잉크 지도 만드는 중… (%d장)' % n)
    maps = np.stack([inkmap(b) for b in bgs])
    ink = maps.reshape(n, -1).mean(axis=1)

    # 판서 속도 = 앞뒤 24초 기울기
    L = max(1, int(24 / step / 2))
    rate = np.zeros(n)
    rate[L:n - L] = ink[2 * L:] - ink[:n - 2 * L]

    noise = np.median(np.abs(rate - np.median(rate))) * 1.4826
    thr_w = max(noise * 2.2, ink.max() * 0.012)
    thr_e = -max(noise * 3.5, ink.max() * 0.030)
    print('  잉크 %.3f ~ %.3f · 잡음 %.4f · 판서임계 %+.4f · 지움임계 %+.4f'
          % (ink.min(), ink.max(), noise, thr_w, thr_e))

    def runs(mask, min_len, merge):
        idx = np.flatnonzero(mask)
        if not len(idx):
            return []
        out, s, p = [], idx[0], idx[0]
        for i in idx[1:]:
            if (i - p) * step > merge:
                out.append((s, p)); s = i
            p = i
        out.append((s, p))
        return [(x, y) for x, y in out if (y - x) * step >= min_len]

    segs = []
    for x, y in runs(rate > thr_w, 8, 16):
        i0, i1 = max(0, x - L), min(n - 1, y + L)
        gain = float(ink[i1] - ink[i0])
        segs.append({'kind': '판서', 'i0': i0, 'i1': i1, 'gain': gain})
    for x, y in runs(rate < thr_e, 6, 12):
        i0, i1 = max(0, x - L), min(n - 1, y + L)
        segs.append({'kind': '지움', 'i0': i0, 'i1': i1, 'gain': float(ink[i1] - ink[i0])})

    segs.sort(key=lambda s: s['i0'])
    print('\n| 구간 | 시각 | 길이 | 종류 | 잉크변화 |')
    keep = []
    for s in segs:
        s0, s1 = float(t[s['i0']]), float(t[s['i1']])
        ok = (s['gain'] >= ink.max() * 0.02) if s['kind'] == '판서' else (s['gain'] <= -ink.max() * 0.05)
        print('| %s | %02d:%02d~%02d:%02d | %4.0f초 | %s | %+.3f | %s' %
              ('✅' if ok else '❌', max(s0, 0) // 60, max(s0, 0) % 60, s1 // 60, s1 % 60,
               s1 - s0, s['kind'], s['gain'], '' if ok else '(변화 미미 — 버림)'))
        if ok:
            keep.append({'kind': s['kind'], 'start': round(max(s0, 0), 2), 'end': round(min(s1, a.dur), 2),
                         'gain': round(s['gain'], 4), 'i0': int(s['i0']), 'i1': int(s['i1'])})

    json.dump({'step': step, 't': d['t'], 'ink': [round(float(v), 4) for v in ink],
               'segs': keep, 'ink_max': float(ink.max())},
              open(os.path.join(a.dir, 'board_segs.json'), 'w'), ensure_ascii=False, indent=1)
    tot = sum(s['end'] - s['start'] for s in keep)
    print('\n채택 %d구간 · %.0f초 (전체의 %.0f%%)' % (len(keep), tot, tot / a.dur * 100))

    print('\n1분 단위 잉크 곡선')
    for j in range(0, n, int(60 / step)):
        bar = '█' * int((ink[j] - ink.min()) / (ink.max() - ink.min() + 1e-9) * 46)
        print('  %02d:%02d %6.3f %s' % (max(t[j], 0) // 60, max(t[j], 0) % 60, ink[j], bar))


if __name__ == '__main__':
    main()
