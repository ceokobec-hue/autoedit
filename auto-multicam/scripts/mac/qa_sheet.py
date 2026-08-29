#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qa_sheet.py — 완성본의 «전환 지점 전/후» 프레임을 번호 붙여 뽑는다.

전체를 다 볼 수는 없다. 그러나 «잘못될 수 있는 곳»은 정해져 있다 — 카메라가 바뀌는 순간이다.
경계 앞뒤 0.25초를 뽑아 나란히 놓으면 «의도한 카메라로 갔는지»가 한눈에 보인다.
"""
import argparse, json, os, subprocess

import sys
# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF = ff_path.FFMPEG
FONTS = os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts'))
F = os.path.join(FONTS,'Pretendard-Bold.otf')
COL = {1: '0xD8402A', 2: '0x1D6FB8'}


def sh(args):
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode()[-800:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True); ap.add_argument('--plan', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--tmp', required=True)
    a = ap.parse_args()

    tl = json.load(open(a.plan))
    os.makedirs(a.tmp, exist_ok=True)
    for f in os.listdir(a.tmp):
        os.remove(os.path.join(a.tmp, f))

    shots, k = [], 0
    for i in range(1, len(tl)):
        t = tl[i]['start']
        for dt, s in ((-0.25, tl[i - 1]), (+0.25, tl[i])):
            z = '%d%%' % s['zoom'] if s['zoom'] > 100 else ''
            # ★ drawtext 안의 콜론은 필터 문법과 충돌한다 — 시각은 m/s 표기로 쓴다
            txt = '%02d%s CAM%d %s %02dm%02ds' % (i, '전' if dt < 0 else '후', s['cam'], z,
                                                  int(t) // 60, int(t) % 60)
            p = os.path.join(a.tmp, 'q%03d.png' % k); k += 1
            sh([FF, '-y', '-v', 'error', '-ss', '%.3f' % max(t + dt, 0), '-i', a.video,
                '-frames:v', '1', '-vf',
                # ★ expansion=none 없으면 '135%' 의 % 를 변수로 읽어 «Stray %» 로 죽는다
                "scale=480:-1,drawtext=fontfile='%s':text='%s':expansion=none:x=8:y=8:fontsize=24:"
                "fontcolor=white:box=1:boxcolor=%s@0.94:boxborderw=8" % (F, txt, COL[s['cam']]), p])
            shots.append(p)

    cols = 4
    rows = (len(shots) + cols - 1) // cols
    sh([FF, '-y', '-v', 'error', '-i', os.path.join(a.tmp, 'q%03d.png'),
        '-filter_complex', 'tile=%dx%d:margin=6:padding=4:color=0x1a1a1a' % (cols, rows),
        '-frames:v', '1', a.out])
    for p in shots:
        os.remove(p)
    print('전환 %d곳 · 프레임 %d장 → %s' % (len(tl) - 1, len(shots), a.out))


if __name__ == '__main__':
    main()
