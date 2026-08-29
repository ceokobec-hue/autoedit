#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_multicam.py — 승인된 결정표대로 «전환 + 확대»가 구워진 한 편을 만든다.

방식: 조각내서 굽고 → 이어 붙인다
  구간마다 해당 카메라에서 잘라 «똑같은 규격»으로 인코딩한 뒤 concat 으로 잇는다.
  두 영상을 동시에 펼쳐 겹치는 방식보다 훨씬 빠르다(한 번에 한 줄기만 푼다).
  ⚠️ concat -c copy 는 조각들의 규격이 완전히 같아야 한다. 그래서 인코더 설정을 한 곳에 묶었다.

프레임 단위로 자른다
  경계를 «초»로 다루면 조각마다 반올림 오차가 쌓여 뒤로 갈수록 소리와 어긋난다.
  그래서 모든 경계를 프레임 번호로 바꾸고 `-frames:v` 로 «정확히 몇 장»을 지정한다.

소리는 자르지 않는다
  기준 카메라(CAM1)의 소리를 통째로 다시 씌운다. 한 번도 안 자르므로 튈 곳이 없고,
  원본 AAC 를 그대로 복사하므로 음질 손실도 없다.
"""
import argparse, json, os, subprocess, sys

# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
import vgeom
FFMPEG = ff_path.FFMPEG
FFPROBE = ff_path.FFPROBE
NUM, DEN = 30000, 1001                      # 29.97fps — 기준 카메라(--camA)에 맞춘다


def sh(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('ffmpeg 실패\n%s\n%s' % (' '.join(args[:16]), r.stderr[-1200:]))
    return r


def dur(p):
    return float(subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration',
                                 '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.strip())


def venc(bitrate):
    """모든 조각이 이 설정으로 구워져야 concat -c copy 가 된다. 한 글자도 달라지면 안 된다."""
    return ['-c:v', 'h264_videotoolbox', '-b:v', bitrate, '-pix_fmt', 'yuv420p',
            '-g', '60', '-r', '%d/%d' % (NUM, DEN), '-video_track_timescale', str(NUM),
            '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-an']


def zoom_vf(zoom, anchor, anchors, W, H):
    # ⛔ 해상도를 박아 두면 1080p 아닌 원본에서 크롭이 화면 밖으로 나간다 → 영상에서 읽은 W·H 를 쓴다
    return vgeom.crop_vf(zoom, anchors[anchor], W, H, flags='lanczos')


def build_timeline(cands, decisions, dur_s, main=1):
    """승인된 구간으로 «전 구간을 덮는» 타임라인을 만든다. 나머지는 전부 CAM1 100%."""
    keep = []
    for c in cands['items']:
        d = decisions.get(c['no'])
        if d is None:
            continue
        keep.append({**c, 'zoom': d})
    keep.sort(key=lambda c: c['start'])

    # 겹침 해소 — 앞 구간의 끝을 자른다
    for i in range(len(keep) - 1):
        if keep[i]['end'] > keep[i + 1]['start']:
            keep[i]['end'] = keep[i + 1]['start']
    keep = [k for k in keep if k['end'] - k['start'] >= 2.0]

    tl, cur = [], 0.0
    for k in keep:
        if k['start'] - cur > 0.5:
            tl.append({'cam': main, 'zoom': 100, 'anchor': 'face', 'start': cur, 'end': k['start'], 'no': 0})
        tl.append({'cam': k['cam'], 'zoom': k['zoom'], 'anchor': k['anchor'],
                   'start': k['start'], 'end': k['end'], 'no': k['no'], 'kind': k['kind']})
        cur = k['end']
    if dur_s - cur > 0.5:
        tl.append({'cam': main, 'zoom': 100, 'anchor': 'face', 'start': cur, 'end': dur_s, 'no': 0})

    # ── 깜빡임 방지 — 3초 미만 조각은 앞 구간에 흡수한다 ──────────
    # 「확대 → 원래크기 2.8초 → 다른 카메라」처럼 3초 안에 두 번 바뀌면 실수처럼 보인다.
    # 방송에서 한 화면을 최소 3초 유지하는 이유. 앞 구간을 늘려 덮는다.
    MIN = 3.0
    out, absorbed = [], []
    for s in tl:
        if s['end'] - s['start'] < MIN and out:
            absorbed.append((s['start'], s['end']))
            out[-1]['end'] = s['end']
        elif s['end'] - s['start'] < MIN and not out:
            absorbed.append((s['start'], s['end']))
            s2 = dict(s); s2['_pending'] = True; out.append(s2)
        else:
            if out and out[-1].get('_pending'):
                s = dict(s); s['start'] = out[-1]['start']; out.pop()
            out.append(s)
    if absorbed:
        print('⚠️ 3초 미만 조각 %d개를 앞 구간에 흡수 (깜빡임 방지):' % len(absorbed))
        for a0, a1 in absorbed:
            print('   · %02d:%02d~%02d:%02d (%.1f초)'
                  % (int(a0) // 60, int(a0) % 60, int(a1) // 60, int(a1) % 60, a1 - a0))
    return out


def main():
    ap = argparse.ArgumentParser(description='검토표에서 정한 대로 두 카메라를 이어 붙여 굽는다')
    ap.add_argument('--cands', required=True,
                    help='전환 후보 JSON (make_plan.py 산출). 검토표에서 살린 것만 쓰인다')
    ap.add_argument('--camA', required=True, help='카메라 1 영상 — ⛔소리는 항상 이쪽 것을 쓴다')
    ap.add_argument('--camB', required=True, help='카메라 2 영상')
    ap.add_argument('--offset', type=float, required=True,
                    help='두 카메라 시작 차이(초). sync_probe.py 가 알려 준다')
    ap.add_argument('--decide', default='',
                    help='검토표에서 복사한 결정. 예 "1:135 6:135 10:120" — 없으면 전부 살린다')
    ap.add_argument('--work', required=True, help='중간 조각이 쌓일 폴더 (용량을 많이 먹는다)')
    ap.add_argument('--out', required=True, help='완성 영상 파일명')
    ap.add_argument('--bitrate', default='14M', help='영상 비트레이트 (기본 14M)')
    ap.add_argument('--flip', default='', help='좌우반전할 카메라 (예 "1"). 미러 모드로 찍힌 카메라 교정')
    ap.add_argument('--main', type=int, default=1, choices=(1, 2),
                    help='빈 구간을 채울 메인 카메라. 소리는 --camA 것을 쓴다(별개)')
    ap.add_argument('--dry', action='store_true',
                    help='굽지 않고 «무엇을 할지»만 보여준다')
    a = ap.parse_args()

    C = json.load(open(a.cands)); anchors = C['anchors']; total = C['dur']
    VW, VH = vgeom.video_size(a.camA)
    print('영상 %dx%d' % (VW, VH))

    # ★ 두 카메라가 «둘 다 존재하는» 구간까지만 만든다.
    #   먼저 시작한 카메라는 그만큼 먼저 끝난다 — 그 뒤를 요구하면 마지막 조각이 몇 프레임 모자란다.
    usable = min(dur(a.camA), dur(a.camB) - a.offset)
    if usable < total - 0.02:
        print('ℹ️ 두 카메라가 겹치는 구간까지만 만든다: %.3f초 → %.3f초 (%.0f프레임 줄어듦)'
              % (total, usable, (total - usable) * NUM / DEN))
        total = round(usable, 3)
        C['dur'] = total

    if a.decide.strip():
        dec = {}
        for tok in a.decide.replace(',', ' ').split():
            parts = tok.split(':')
            no = int(parts[0])
            z = int(parts[-1]) if parts[-1].isdigit() else 100
            dec[no] = z
    else:
        dec = {c['no']: c['zoom'] for c in C['items'] if c['keep']}

    flip = set(c for c in a.flip if c.isdigit())
    if flip:
        print('좌우반전 적용: CAM' + ', CAM'.join(sorted(flip)))
    tl = build_timeline(C, dec, total, a.main)
    # 공통 구간까지로 줄었으면 타임라인 끝도 같이 잘라 준다
    tl = [x for x in tl if x['start'] < total - 0.05]
    tl[-1]['end'] = total

    # ── 정합성 검사 ─────────────────────────────────────────
    errs = []
    for i, s in enumerate(tl):
        if s['end'] - s['start'] < 1.0:
            errs.append('#%d 구간이 1초 미만 (%.2f초)' % (i, s['end'] - s['start']))
        if i and abs(s['start'] - tl[i - 1]['end']) > 0.001:
            errs.append('#%d 앞 구간과 이가 안 맞음' % i)
        if s['zoom'] > 100 and not zoom_vf(s['zoom'], s['anchor'], anchors, VW, VH):
            errs.append('#%d 확대 틀 계산 실패' % i)
    if abs(tl[-1]['end'] - total) > 0.05:
        errs.append('전체 길이 불일치 %.3f vs %.3f' % (tl[-1]['end'], total))
    if errs:
        print('⛔ 정합성 검사 실패:'); [print('  · ' + e) for e in errs]; sys.exit(1)

    sw = sum(1 for i in range(1, len(tl)) if tl[i]['cam'] != tl[i - 1]['cam'])
    c2 = sum(s['end'] - s['start'] for s in tl if s['cam'] == 2)
    print('구간 %d개 · 카메라 전환 %d회 · CAM2 %.0f초(%.0f%%) · 확대구간 %d개'
          % (len(tl), sw, c2, c2 / total * 100, sum(1 for s in tl if s['zoom'] > 100)))
    print('\n| # | 시각 | 길이 | CAM | 확대 |')
    for i, s in enumerate(tl, 1):
        print('| %2d | %02d:%02d~%02d:%02d | %5.1f초 | %d | %s |'
              % (i, int(s['start']) // 60, int(s['start']) % 60, int(s['end']) // 60,
                 int(s['end']) % 60, s['end'] - s['start'], s['cam'],
                 '%d%%' % s['zoom'] if s['zoom'] > 100 else '—'))
    json.dump(tl, open(os.path.join(a.work, 'switch_plan.json'), 'w'), ensure_ascii=False, indent=1)
    if a.dry:
        print('\n(dry — 렌더하지 않음)'); return

    # ── 조각 굽기 ───────────────────────────────────────────
    seg = os.path.join(a.work, 'seg'); os.makedirs(seg, exist_ok=True)
    for f in os.listdir(seg):
        os.remove(os.path.join(seg, f))

    E = venc(a.bitrate)
    files = []
    fend_prev = 0
    for i, s in enumerate(tl, 1):
        f0 = fend_prev
        f1 = round(s['end'] * NUM / DEN)
        nfr = f1 - f0
        if nfr <= 0:
            continue
        t0 = f0 * DEN / NUM
        src = a.camA if s['cam'] == 1 else a.camB
        ss = t0 + (0.0 if s['cam'] == 1 else a.offset)

        vf = []
        # ★ 미러 모드로 저장된 카메라 교정 — «자르기보다 먼저» 뒤집어야 확대 좌표가 맞는다.
        #   셀피(미러) 방향으로 찍는 카메라는 좌우가 뒤집힌 채 저장된다(칠판 글씨가 거울글씨).
        #   덤: 뒤집으면 두 카메라의 인물 위치가 같은 쪽이 되어 «축 넘기»도 해소된다.
        if str(s['cam']) in flip:
            vf.append('hflip')
        if s['cam'] == 2:
            vf.append('fps=%d/%d' % (NUM, DEN))          # 30.00 → 29.97 로 맞춘다
        z = zoom_vf(s['zoom'], s['anchor'], anchors, VW, VH)
        if z:
            vf.append(z)
        p = os.path.join(seg, 's%03d.mp4' % i)
        cmd = [FFMPEG, '-y', '-loglevel', 'error', '-ss', '%.5f' % ss, '-i', src, '-map', '0:v:0']
        if vf:
            cmd += ['-vf', ','.join(vf)]
        cmd += ['-frames:v', str(nfr)] + E + [p]
        sh(cmd)
        files.append(p)
        fend_prev = f1
        print('  조각 %2d/%d  CAM%d %s %d장  %s' % (i, len(tl), s['cam'],
              '%3d%%' % s['zoom'] if s['zoom'] > 100 else '   —', nfr, os.path.basename(p)))

    # ── 이어 붙이기 ─────────────────────────────────────────
    lf = os.path.join(a.work, 'concat.txt')
    # ★ concat 목록의 경로는 «목록 파일 기준»으로 풀린다 — 반드시 절대경로로 쓴다
    open(lf, 'w', encoding='utf-8').write(
        '\n'.join("file '%s'" % os.path.abspath(f) for f in files) + '\n')
    vonly = os.path.join(a.work, '_v.mp4')
    print('\n이어 붙이는 중…')
    sh([FFMPEG, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lf, '-c', 'copy', vonly])
    for f in files:
        os.remove(f)                                     # 디스크가 빠듯하다 — 즉시 버린다

    print('소리 씌우는 중… (원본 AAC 그대로 복사)')
    sh([FFMPEG, '-y', '-loglevel', 'error', '-i', vonly, '-i', a.camA,
        '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'copy',
        '-movflags', '+faststart', '-shortest', a.out])
    os.remove(vonly)

    d = dur(a.out)
    print('\n완성: %s' % a.out)
    print('  길이 %.3f초 (목표 %.3f · 차이 %+.3f초)  크기 %.2fGB'
          % (d, total, d - total, os.path.getsize(a.out) / 1e9))
    if abs(d - total) > 0.1:
        print('  ⚠️ 길이가 어긋난다 — 확인 필요')


if __name__ == '__main__':
    main()
