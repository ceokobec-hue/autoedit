#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OS 마다 «달라지는 것»을 한 곳에서 고른다 — ①영상 인코더 ②크롬.

ff_path.py 와 같은 생각이다. 같은 고르기 로직이 스크립트마다 흩어져 있으면
그중 하나가 틀렸을 때 「어떤 스크립트는 되고 어떤 스크립트는 안 되는」 상태가 된다.

────────────────────────────────────────────────────────
① 인코더  venc('24M')  →  ['-c:v', ..., 화질 옵션...]
────────────────────────────────────────────────────────
맥      h264_videotoolbox   (맥에 내장된 하드웨어 인코더)
윈도우  h264_nvenc          (NVIDIA 그래픽카드가 «실제로 굽는지» 시험해 보고)
        libx264             (안 되면 — 느리지만 어디서나 돈다)
리눅스  같은 방식

⛔ 인코더마다 «옵션 문법이 다르다». 이름만 갈아끼우면 조용히 망가진다.
   · videotoolbox·nvenc  → 목표 비트레이트(-b:v)로 굽는다. -preset 은 videotoolbox 에 없다(넣으면 에러).
   · libx264             → 비트레이트가 아니라 «화질 눈금»(-crf)이 정석이고 -preset 이 필요하다.
   그래서 이 파일은 «인코더 이름 + 그 인코더에 맞는 화질 옵션»을 **한 덩어리로** 돌려준다.

⚠️ libx264 에서 여러분이 준 비트레이트는 «상한선»(-maxrate)이 된다. 버려지지 않는다.
   화질은 -crf 가 정하고, 비트레이트는 「이보다 두껍게는 쓰지 마라」는 뜻으로 쓰인다.
   눈금을 바꾸고 싶으면  export AUTOEDIT_CRF=18   (숫자가 «작을수록» 고화질·큰 파일)

★ 강제 지정:  export AUTOEDIT_ENCODER=libx264   ← 지정하면 언제나 이게 이긴다

────────────────────────────────────────────────────────
② 크롬  find_chrome() / require_chrome()
────────────────────────────────────────────────────────
카드·인서트 PNG 는 전부 크롬이 굽는다. 찾는 순서는
  ① 환경변수 CHROME  ② OS 별 표준 설치 자리  ③ PATH
"""
import os
import shutil
import subprocess
import sys

# ff_path 는 이 파일 «옆»에 있다 (저장소 뿌리)
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import ff_path

IS_MAC = sys.platform == 'darwin'
IS_WIN = os.name == 'nt'


# ══════════════════════════════════════════════════════════════
#  ① 인코더
# ══════════════════════════════════════════════════════════════

_ENCODER = None          # 한 번 정하면 이 프로세스가 끝날 때까지 다시 재지 않는다


def _nvenc_works():
    """NVIDIA 인코더가 «실제로 굽는지» 손바닥만 한 영상으로 시험해 본다.

    ⛔ `ffmpeg -encoders` 목록에 h264_nvenc 가 «있다»는 것만으로는 안 된다.
       그 목록은 ffmpeg 을 만들 때 박히는 «고정 목록»이라, NVIDIA 카드가 없는 컴퓨터에서도
       그대로 나온다. 실제 판정은 굽는 순간에야 난다 — 그때 나면 렌더가 통째로 날아간다.
       그래서 여기서 0.2초짜리를 미리 구워 보고 «안 되면 조용히 libx264 로» 내려간다.
       (한 번에 1초 안쪽. 이 프로세스에서 다시는 안 한다.)
    """
    ff = ff_path.FFMPEG
    if not os.path.exists(ff):
        return False
    try:
        r = subprocess.run(
            [ff, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=128x128:r=25:d=0.2',
             '-c:v', 'h264_nvenc', '-pix_fmt', 'yuv420p', '-f', 'null', '-'],
            capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        # 시험 자체가 안 되면(ffmpeg 이 없다·너무 오래 걸린다) «없는 것으로» 친다.
        return False


def encoder():
    """이 컴퓨터에서 쓸 영상 인코더 이름."""
    global _ENCODER
    if _ENCODER:
        return _ENCODER
    forced = (os.environ.get('AUTOEDIT_ENCODER') or '').strip()
    if forced:
        _ENCODER = forced
    elif IS_MAC:
        # 맥은 시험하지 않는다 — videotoolbox 는 맥에 «내장»이라 없을 수가 없고,
        # 괜히 시험하면 지금 잘 도는 것에 새 실패 지점만 하나 늘어난다.
        _ENCODER = 'h264_videotoolbox'
    else:
        _ENCODER = 'h264_nvenc' if _nvenc_works() else 'libx264'
    return _ENCODER


def _bps(bitrate):
    """'24M' → 24000000 · '192k' → 192000 · '8000000' → 8000000 · 못 읽으면 None."""
    s = str(bitrate).strip()
    mul = 1
    if s[-1:] in ('M', 'm'):
        mul, s = 1000000, s[:-1]
    elif s[-1:] in ('K', 'k'):
        mul, s = 1000, s[:-1]
    try:
        return int(float(s) * mul)
    except ValueError:
        return None


def venc(bitrate):
    """«-c:v 부터 화질을 정하는 옵션까지»를 한 덩어리로 돌려준다.

    나머지 옵션(-pix_fmt · -g · -r · -profile:v …)은 부르는 쪽이 지금 쓰던 그대로 이어 붙인다.
    ⚠️ 조각을 구워 concat -c copy 로 잇는 곳(compose_mac·render_multicam)은
       «모든 조각이 같은 설정»이어야 한다. 이 함수는 항상 같은 답을 주므로 그 조건이 지켜진다.
    """
    e = encoder()
    if e == 'libx264':
        opts = ['-preset', os.environ.get('AUTOEDIT_X264_PRESET', 'medium'),
                '-crf', os.environ.get('AUTOEDIT_CRF', '20')]
        n = _bps(bitrate)
        if n:                       # 받은 비트레이트는 버리지 않고 «상한선»으로 쓴다
            opts += ['-maxrate', str(n), '-bufsize', str(n * 2)]
        return ['-c:v', e] + opts
    # videotoolbox · nvenc · 그 밖에 사용자가 강제 지정한 것 — 목표 비트레이트로 간다
    return ['-c:v', e, '-b:v', bitrate]


def encoder_note():
    """doctor.py 가 사람에게 보여 줄 한 줄."""
    e = encoder()
    if os.environ.get('AUTOEDIT_ENCODER'):
        return '%s  (AUTOEDIT_ENCODER 로 직접 지정하셨습니다)' % e
    return {
        'h264_videotoolbox': 'h264_videotoolbox  (맥 내장 하드웨어 인코더)',
        'h264_nvenc':        'h264_nvenc  (NVIDIA 그래픽카드 — 실제로 구워 보고 확인했습니다)',
        'libx264':           'libx264  (그래픽카드 가속 없이 굽습니다 — 느리지만 정확합니다)',
    }.get(e, e)


# ══════════════════════════════════════════════════════════════
#  ② 크롬
# ══════════════════════════════════════════════════════════════

def _chrome_candidates():
    """찾아볼 자리를 «순서대로». 맨 앞이 그 OS 의 표준 설치 자리다."""
    if IS_MAC:
        return ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
                '/Applications/Chromium.app/Contents/MacOS/Chromium']
    if IS_WIN:
        pf   = os.environ.get('ProgramFiles', r'C:\Program Files')
        pf86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
        la   = os.environ.get('LOCALAPPDATA', '')
        c = [os.path.join(pf,   r'Google\Chrome\Application\chrome.exe'),
             os.path.join(pf86, r'Google\Chrome\Application\chrome.exe')]
        if la:
            c.append(os.path.join(la, r'Google\Chrome\Application\chrome.exe'))
        # ⚠️ 크롬이 없으면 «엣지»로 굽는다. 엣지는 크롬과 «같은 엔진(크로미움)»이라
        #    --headless --screenshot 이 글자 하나 안 바꾸고 그대로 통한다.
        #    윈도우에는 엣지가 항상 깔려 있어서, 크롬을 못 받는 사람도 일단 굴러간다.
        #    (⛔ 다만 이 저장소는 아직 윈도우에서 실제로 돌려 확인하지 못했다.)
        c += [os.path.join(pf86, r'Microsoft\Edge\Application\msedge.exe'),
              os.path.join(pf,   r'Microsoft\Edge\Application\msedge.exe')]
        return c
    return ['/opt/google/chrome/chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/google-chrome',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium']


def find_chrome():
    """크롬 실행파일 경로. 못 찾으면 «기대 경로»를 돌려준다(에러 메시지에 쓰려고)."""
    env = os.environ.get('CHROME')
    if env:
        return env
    cands = _chrome_candidates()
    for p in cands:
        if os.path.exists(p):
            return p
    for name in ('chrome', 'google-chrome', 'google-chrome-stable',
                 'chromium', 'chromium-browser', 'msedge'):
        p = shutil.which(name)
        if p:
            return p
    return cands[0]


def fonts_cmd():
    """폰트를 받는 명령 — OS 마다 다르다.

    ⛔ 윈도우에는 bash 가 없다. 에러 메시지가 `bash ...get_fonts.sh` 를 알려 주면
       그대로 쳤을 때 «command not found» 만 나온다 — 막힌 사람을 한 번 더 막는 셈이다.
    """
    if IS_MAC:
        return 'bash auto-insert/scripts/mac/get_fonts.sh'
    return ('python' if IS_WIN else 'python3') + ' auto-insert/scripts/mac/get_fonts.py'


def chrome_install_hint():
    """없을 때 «어떻게 받나»를 OS 에 맞게 한 줄로."""
    if IS_MAC:
        return 'brew install --cask google-chrome   (무료)'
    if IS_WIN:
        return ('https://www.google.com/chrome/ 에서 받으세요 (무료).\n'
                '     윈도우에 이미 있는 Microsoft Edge 도 같은 엔진이라 대신 쓸 수 있습니다.')
    return '배포판 패키지 관리자로 google-chrome 또는 chromium 을 받으세요.'


def require_chrome():
    """없으면 «한국어 한 줄»로 죽는다. ⛔스택트레이스는 비개발자에게 아무 정보도 주지 않는다."""
    p = find_chrome()
    if not os.path.exists(p):
        sys.exit('⛔ 크롬을 못 찾았습니다: %s\n'
                 '   카드·인서트 PNG 는 크롬이 굽습니다.\n'
                 '   → %s\n'
                 '     다른 곳에 있으면  CHROME 환경변수로 알려 주세요.' % (p, chrome_install_hint()))
    return p


# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print('OS      :', 'macOS' if IS_MAC else ('Windows' if IS_WIN else sys.platform))
    print('인코더  :', encoder_note())
    print('  옵션  :', ' '.join(venc('24M')))
    ch = find_chrome()
    print('크롬    :', ch, '✅' if os.path.exists(ch) else '⛔ 없음')
