#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""영상에서 «16kHz 모노 wav» 를 뽑는다.

왜 따로 있나
  싱크 재기(sync_probe.py)와 받아쓰기(whisper) 둘 다 «영상»이 아니라 이 모양의 wav 를 먹는다.
  전에는 문서에 ffmpeg 경로를 통째로 적어 뒀는데(`/opt/homebrew/opt/...`),
  ⛔그 경로는 인텔 맥·윈도우·다른 데 받은 사람에게 전부 틀린다.
  ff_path.py 가 알아서 찾게 하면 어느 컴퓨터에서든 같은 한 줄로 끝난다.

사용: python3 examples/make_wav.py <영상> [나갈파일.wav]
      나갈 파일을 안 적으면 영상 옆에 같은 이름 .wav 로 만든다.
      ★ 예제 폴더에 있지만 «아무 영상»에나 쓸 수 있다.

뽑는 모양 (이 셋이 규약이다 — 하나라도 다르면 도구들이 안 먹는다)
  -vn          그림 버리기
  -ac 1        한 채널(모노)
  -ar 16000    초당 16000번 표본
  -c:a pcm_s16le   압축 안 한 16비트 소리
"""
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import ff_path


def main():
    if len(sys.argv) < 2:
        sys.exit('사용: python3 examples/make_wav.py <영상> [나갈파일.wav]\n'
                 '  예: python3 examples/make_wav.py examples/sample.mp4 examples/mc/A.wav')
    src = sys.argv[1]
    if not os.path.exists(src):
        sys.exit('⛔ 영상이 없습니다: %s' % src)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + '.wav'

    ff_path.require()                       # 없으면 «한국어 한 줄»로 죽는다
    d = os.path.dirname(os.path.abspath(out))
    if d:
        os.makedirs(d, exist_ok=True)

    # ⛔ -y 는 «나갈 파일»에만 걸린다. 원본은 건드리지 않는다.
    r = subprocess.run([ff_path.FFMPEG, '-v', 'error', '-y', '-i', src,
                        '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', out],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit('⛔ 소리를 못 뽑았습니다:\n' + (r.stderr or '')[-1200:])
    print('✅ %s  (%.1f MB · 16kHz 모노)' % (out, os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    main()
