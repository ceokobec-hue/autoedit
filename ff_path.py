#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ffmpeg / ffprobe 를 «한 곳에서» 찾는다.

같은 찾기 로직이 스크립트마다 흩어져 있으면 그중 하나가 틀렸을 때
「어떤 스크립트는 되고 어떤 스크립트는 안 되는」 상태가 된다 — 실제로 그랬다.

찾는 순서
  ① 환경변수  FFMPEG / FFPROBE  (직접 지정한 경로가 언제나 이긴다)
  ② 환경변수  FFMPEG_BIN        (bin 폴더만 지정하는 옛 방식)
  ③ ffmpeg-full 설치 자리        애플실리콘 → /opt/homebrew/opt/...  ·  인텔 → /usr/local/opt/...
  ④ PATH 의 ffmpeg               ⚠️ 기본 ffmpeg 일 수 있다(자막 필터가 없다)

⛔ ffmpeg-full 은 keg-only 라 PATH 에 «영원히» 안 올라온다.
   그래서 `which ffmpeg` 가 아니라 설치 자리를 직접 봐야 한다.
"""
import os, shutil, sys

KEG_DIRS = ('/opt/homebrew/opt/ffmpeg-full/bin',   # 애플실리콘
            '/usr/local/opt/ffmpeg-full/bin')      # 인텔 맥


def find(name):
    """name 은 'ffmpeg' 또는 'ffprobe'. 못 찾으면 «기대 경로»를 돌려준다(에러 메시지에 쓰려고)."""
    env = os.environ.get(name.upper())
    if env:
        return env
    binroot = os.environ.get('FFMPEG_BIN')
    if binroot:
        p = os.path.join(binroot, name)
        if os.path.exists(p):
            return p
    for d in KEG_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return shutil.which(name) or os.path.join(KEG_DIRS[0], name)


FFMPEG = find('ffmpeg')
FFPROBE = find('ffprobe')
BIN = os.path.dirname(FFMPEG)


def require(*paths):
    """없으면 «한국어 한 줄»로 죽는다. ⛔스택트레이스는 비개발자에게 아무 정보도 주지 않는다."""
    missing = [p for p in (paths or (FFMPEG,)) if not os.path.exists(p)]
    if missing:
        sys.exit('⛔ ffmpeg 을 못 찾았습니다:\n  ' + '\n  '.join(missing) +
                 '\n\n설치.md 1단계를 하셨나요?\n'
                 '  brew install ffmpeg-full\n'
                 '지금 상태 확인:  python3 doctor.py\n'
                 '다른 곳에 두셨다면:  export FFMPEG=<ffmpeg 경로>  export FFPROBE=<ffprobe 경로>')
    return paths[0] if paths else FFMPEG


if __name__ == '__main__':
    print('ffmpeg :', FFMPEG, '✅' if os.path.exists(FFMPEG) else '⛔ 없음')
    print('ffprobe:', FFPROBE, '✅' if os.path.exists(FFPROBE) else '⛔ 없음')
