#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""영상 크기와 «확대 자리» 계산을 한 곳에서 한다.

왜 필요한가
  확대(크롭) 계산이 1920×1080 을 코드에 박아 두고 있었다. 1280×720 원본을 넣으면
  자르려는 사각형이 화면 밖으로 나가고, ffmpeg 은 «스트림에 패킷이 하나도 안 왔다»는
  낯선 말을 하며 빈 파일을 만든다 — 검토표가 아예 안 만들어진다.

그래서 두 가지를 바꿨다
  ① 크기는 «영상에서 읽는다»(ffprobe).
  ② 확대 중심점(anchor)은 «비율(0~1)»로 적는다. 그래야 어떤 해상도에서도 같은 자리를 가리킨다.

옛 계획 파일 호환
  anchor 값이 1보다 크면 «1920×1080 기준 절대좌표»로 보고 비율로 바꿔 준다.
"""
import os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ff_path

LEGACY_W, LEGACY_H = 1920.0, 1080.0


def video_size(path, default=(1920, 1080)):
    """영상의 가로·세로를 읽는다. 못 읽으면 default."""
    r = subprocess.run([ff_path.FFPROBE, '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height', '-of', 'csv=p=0:s=x', path],
                       capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split('x')[:2]
        return int(float(w)), int(float(h))
    except Exception:
        return default


def as_ratio(anchor):
    """(x, y) 를 «비율»로 만든다. 1보다 크면 옛 1920×1080 절대좌표로 본다."""
    x, y = float(anchor[0]), float(anchor[1])
    if x > 1.0 or y > 1.0:
        return x / LEGACY_W, y / LEGACY_H
    return x, y


def crop_vf(zoom, anchor, W, H, flags=None):
    """확대용 ffmpeg 필터 문자열. zoom<=100 이면 None(자를 것이 없다).

    zoom=135 → 화면의 1/1.35 만 남기고 다시 원래 크기로 늘린다 = 1.35배 확대.
    """
    if zoom <= 100:
        return None
    cw = int(W / (zoom / 100.0)) // 2 * 2          # ⛔홀수면 h264 인코더가 싫어한다
    ch = int(H / (zoom / 100.0)) // 2 * 2
    rx, ry = as_ratio(anchor)
    cx, cy = rx * W, ry * H
    x = int(min(max(cx - cw / 2.0, 0), W - cw))    # 화면 밖으로 나가지 않게 당긴다
    y = int(min(max(cy - ch / 2.0, 0), H - ch))
    tail = ':flags=' + flags if flags else ''
    return 'crop=%d:%d:%d:%d,scale=%d:%d%s' % (cw, ch, x, y, W, H, tail)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('사용: python3 vgeom.py <영상.mp4>   — 크기와 확대 계산을 확인한다')
    W, H = video_size(sys.argv[1])
    print('영상 %dx%d' % (W, H))
    for z in (100, 120, 135):
        print('  zoom %3d%% · board(0.385,0.361) → %s' % (z, crop_vf(z, (0.385, 0.361), W, H)))
