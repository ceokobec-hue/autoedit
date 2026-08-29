#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시험용 «20초짜리 영상 + 자막»을 만든다. 카메라도 촬영본도 필요 없다.

왜 필요한가: 「내 환경이 제대로 됐나」를 «결과물»로 확인하는 게 제일 확실하다.
  doctor.py 의 ✅ 는 부품이 있다는 뜻이지, 끝까지 돈다는 뜻이 아니다.

사용: python3 examples/make_sample.py        (저장소 폴더에서)
      → examples/sample.mp4 · examples/sample.srt · examples/sample2.mp4

★ make_sample.sh 와 하는 일이 같다. 윈도우에는 bash 가 없어서 파이썬으로도 두었다.
⛔ 중간에 하나가 실패해도 «어디서 멈췄는지» 말없이 사라지지 않게 한 단계씩 알린다.
"""
import os
import subprocess
import sys

# ── ffmpeg 경로·인코더는 저장소 뿌리의 도우미 한 곳에서만 정한다 ──
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import ff_path
import platform_tools

W, H, SEC = 2560, 1440, 20   # 20초 — OTS 카드는 8초 이상 간격이 필요해 10초로는 두 장이 안 들어간다

SRT = """1
00:00:00,000 --> 00:00:02,500
안녕하세요, 시험용 자막입니다.

2
00:00:02,500 --> 00:00:05,000
여기에 첫 번째 인서트가 붙습니다.

3
00:00:05,000 --> 00:00:07,500
자막은 인서트가 «어느 말에» 붙는지 고르는 재료입니다.

4
00:00:07,500 --> 00:00:10,000
여기서 두 번째 단원이 시작됩니다.

5
00:00:10,000 --> 00:00:12,500
두 번째 인서트는 여기입니다.

6
00:00:12,500 --> 00:00:15,000
카드가 배경에 묻히는지 코드가 재서 정합니다.

7
00:00:15,000 --> 00:00:17,500
검수 시트에서 번호로 지적하면 됩니다.

8
00:00:17,500 --> 00:00:20,000
끝까지 나오면 성공입니다.
"""


def make(src_filter, out_name):
    """lavfi 로 그림 하나 + 소리 하나를 만들어 mp4 로 굽는다."""
    cmd = [ff_path.FFMPEG, '-v', 'error', '-y',
           '-f', 'lavfi', '-i', '%s=size=%dx%d:rate=30:duration=%d' % (src_filter, W, H, SEC),
           '-f', 'lavfi', '-i', 'sine=frequency=440:duration=%d' % SEC] \
        + platform_tools.venc('4M') \
        + ['-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
           os.path.join(HERE, out_name)]
    return subprocess.run(cmd).returncode == 0


def main():
    ff_path.require()                      # 없으면 «한국어 한 줄»로 죽는다
    print('ffmpeg:', ff_path.FFMPEG)
    print('인코더:', platform_tools.encoder_note())
    print()

    # ── ① 시험용 영상 — 색이 계속 바뀌는 배경 + 초 세는 숫자 ────────────
    #    배경이 변해야 «카드가 배경에 묻히나»를 재는 기능을 시험할 수 있다.
    print('① 영상 만드는 중… (%dx%d · %d초)' % (W, H, SEC))
    if make('testsrc2', 'sample.mp4'):
        print('  ✅ examples/sample.mp4')
    else:
        sys.exit('  ⛔ 영상 만들기 실패 — 위에 나온 ffmpeg 메시지를 보세요.')

    # ── ② 두 번째 카메라 흉내 — 오토멀티캠 시험용 (같은 소리 · 다른 그림) ──
    print('② 두 번째 카메라 영상 만드는 중…')
    if make('smptebars', 'sample2.mp4'):
        print('  ✅ examples/sample2.mp4')
    else:
        print('  ⚠️ 두 번째 영상은 실패 — 오토인서트 시험에는 없어도 됩니다')

    # ── ③ 자막 — 인서트가 «어느 말에» 붙는지 고르는 재료 ────────────────
    with open(os.path.join(HERE, 'sample.srt'), 'w', encoding='utf-8') as f:
        f.write(SRT)
    print('  ✅ examples/sample.srt (8줄)')

    print()
    print('다음: examples/README.md 의 「2. 첫 결과물」 로 가세요.')


if __name__ == '__main__':
    main()
