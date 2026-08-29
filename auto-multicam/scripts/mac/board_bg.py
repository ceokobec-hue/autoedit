#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
board_bg.py — «강사를 지운 맨 보드»를 시각마다 만들어 판서를 정확히 잰다.

핵심 아이디어
  같은 자리를 찍은 여러 장을 픽셀마다 «중앙값»으로 합치면 지나가는 사람은 사라지고
  움직이지 않는 것(=보드와 글씨)만 남는다. 관광지에서 사람 없는 사진 만드는 그 원리.
  → 시각 t 의 맨 보드 = t 앞뒤 ±W초 프레임들의 픽셀별 중앙값

이렇게 하면
  · 강사가 보드 앞에 서 있어도 «잉크량»이 부풀지 않는다 (앞의 실패 원인)
  · 두 시점의 맨 보드를 빼면 «그 사이에 무엇을 썼는지»가 그림으로 나온다 (검토표 근거)

사용: python3 board_bg.py 영상 --crop 1120:1000:60:40 --offset 2.4249 --outdir 03_detect
"""
import argparse, json, os, subprocess
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

import sys
# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FFMPEG = ff_path.FFMPEG
FPS = 1.0
W, H = 280, 250
BGW = 20          # 맨 보드를 만들 때 앞뒤로 보는 초
STEP = 4          # 맨 보드를 몇 초마다 만들지


def grab(video, crop):
    cmd = [FFMPEG, '-v', 'error', '-i', video, '-map', '0:v:0',
           '-vf', 'crop=%s,fps=%g,scale=%d:%d,format=gray' % (crop, FPS, W, H),
           '-f', 'rawvideo', '-']
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise SystemExit('⛔ ffmpeg 실패:\n' + p.stderr.decode()[-1500:])
    b = np.frombuffer(p.stdout, dtype=np.uint8)
    n = len(b) // (W * H)
    return b[:n * W * H].reshape(n, H, W)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('--crop', required=True)
    ap.add_argument('--offset', type=float, default=0.0)
    ap.add_argument('--outdir', required=True)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    print('프레임 읽는 중…')
    F = grab(a.video, a.crop)
    n = len(F)
    print('  %d장 (%.0f초)' % (n, n / FPS))

    # ── 시각마다 «맨 보드» 만들기 ────────────────────────────
    ks = list(range(0, n, STEP))
    bgs = np.empty((len(ks), H, W), np.uint8)
    for j, k in enumerate(ks):
        lo, hi = max(0, k - BGW), min(n, k + BGW + 1)
        bgs[j] = np.median(F[lo:hi], axis=0).astype(np.uint8)
    tk = np.array(ks) / FPS - a.offset          # 기준(CAM1) 시각
    print('  맨 보드 %d장 (%d초 간격)' % (len(ks), STEP))

    # ── 잉크량 = 흰 바탕 대비 어두운 정도 ────────────────────
    B = bgs.reshape(len(ks), -1).astype(np.float32)
    base = np.percentile(B, 92, axis=1, keepdims=True)   # 그 시각 보드의 «흰 바탕»
    ink = np.clip(base - B, 12, None) - 12               # 12계조 이하 차이는 잡티로 본다
    ink = ink.mean(axis=1)

    np.save(os.path.join(a.outdir, 'bgs.npy'), bgs)
    json.dump({'step': STEP, 'fps': FPS, 'offset': a.offset, 'crop': a.crop,
               'W': W, 'H': H, 't': [round(float(v), 2) for v in tk],
               'ink': [round(float(v), 4) for v in ink]},
              open(os.path.join(a.outdir, 'board_bg.json'), 'w'))

    print('\n  시각      잉크')
    for j in range(0, len(ks), max(1, int(60 / STEP))):
        print('  %02d:%02d   %.3f' % (max(tk[j], 0) // 60, max(tk[j], 0) % 60, ink[j]))
    print('\n저장: %s' % a.outdir)


if __name__ == '__main__':
    main()
