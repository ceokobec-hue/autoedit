#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""환경 점검 — 돌리기 전에 «무엇이 없는지»를 먼저 알려준다.

    python3 doctor.py

⛔ 이 도구에서 제일 무서운 고장은 «에러 없이 자막만 안 나오는» 것이다.
   Homebrew 기본 ffmpeg 에는 글자를 그리는 부품(libass·freetype)이 없기 때문이다.
   그래서 여기서 필터 개수를 직접 센다.
"""
import os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ff_path

OK, WARN, BAD = '✅', '⚠️ ', '⛔'
problems = []
VENV_PY = os.path.expanduser('~/.autoedit/venv/bin/python')


def say(mark, title, detail=''):
    print(f'{mark} {title}' + (f'\n     {detail}' if detail else ''))


def find_ffmpeg():
    # ⛔ 찾기 로직을 여기 또 적으면 스크립트와 어긋난다 → ff_path.py 하나만 본다
    ff = ff_path.FFMPEG
    return ff if os.path.exists(ff) else None


def main():
    print('\n=== autoedit 환경 점검 ===\n')

    # 1. 파이썬
    v = sys.version_info
    if v >= (3, 9):
        say(OK, f'파이썬 {v.major}.{v.minor}.{v.micro}')
    else:
        say(BAD, f'파이썬이 너무 낮습니다 ({v.major}.{v.minor})', '3.9 이상이 필요합니다.')
        problems.append('python')

    # 2. ffmpeg — 있는지 + 글자를 그릴 수 있는지
    ff = find_ffmpeg()
    if not ff:
        say(BAD, 'ffmpeg 을 못 찾았습니다', 'brew install ffmpeg-full')
        problems.append('ffmpeg')
    else:
        try:
            out = subprocess.run([ff, '-hide_banner', '-filters'],
                                 capture_output=True, text=True, timeout=60).stdout
            names = set()
            for line in out.splitlines():
                p = line.split()
                if len(p) > 1 and p[1] in ('subtitles', 'ass', 'drawtext'):
                    names.add(p[1])
            if len(names) == 3:
                say(OK, f'ffmpeg — 자막 필터 3/3', ff)
            else:
                say(BAD, f'ffmpeg 에 자막 필터가 {len(names)}/3 개뿐입니다',
                    f'{ff}\n     → brew install ffmpeg-full 로 받으신 뒤 다시 점검하세요.\n'
                    '     이대로 쓰면 «에러 없이 자막만 안 나오는» 사고가 납니다.')
                problems.append('libass')
        except Exception as e:
            say(BAD, 'ffmpeg 을 실행할 수 없습니다', f'{ff}\n     {e}')
            problems.append('ffmpeg')

    # 3. ffprobe
    # ⛔ 경로 전체에 replace 를 걸면 '/opt/.../ffmpeg-full/bin/ffmpeg' 의 앞쪽이 먼저 걸려
    #    'ffprobe-full' 이 된다. 파일 이름만 바꾼다.
    fp = ff_path.FFPROBE
    if fp and os.path.exists(fp):
        say(OK, 'ffprobe', fp)
    else:
        say(WARN, 'ffprobe 를 못 찾았습니다', '길이 측정 단계에서 멈출 수 있습니다.')

    # 4. 작은 방(venv) — 부품이 여기 들어 있다
    if os.path.exists(VENV_PY):
        say(OK, '작은 방(venv)', VENV_PY)
    else:
        say(BAD, '작은 방(venv)이 없습니다', '설치.md 2단계:\n'
            '     python3 -m venv ~/.autoedit/venv\n'
            '     ~/.autoedit/venv/bin/pip install fonttools numpy')
        problems.append('venv')

    # 5. 파이썬 패키지 — fonttools(글자 폭 실측) · numpy(파형·밝기 계산)
    # ⛔ venv 는 «격리»라 python3 로는 절대 안 보인다. 「venv 에만 있음」을 ✅ 로 찍으면
    #    doctor 가 초록불인데 스크립트는 ModuleNotFoundError 로 죽는다 → ⚠️ 로 내리고 부르는 법을 알린다.
    venv_only = []
    for mod, pkg, why in (('fontTools', 'fonttools', '글자 폭 실측'),
                          ('numpy', 'numpy', '오토멀티캠 싱크·판서 감지')):
        here = subprocess.run([sys.executable, '-c', 'import ' + mod],
                              capture_output=True).returncode == 0
        invenv = (os.path.exists(VENV_PY) and
                  subprocess.run([VENV_PY, '-c', 'import ' + mod],
                                 capture_output=True).returncode == 0)
        if here:
            say(OK, f'{pkg} — 지금 파이썬에서 바로 보입니다  ({why})')
        elif invenv:
            say(WARN, f'{pkg} — 작은 방(venv)에만 있습니다  ({why})',
                '이 부품을 쓰는 스크립트는 «방 안의 파이썬»으로 불러야 합니다:\n'
                f'     {VENV_PY} <스크립트.py> ...\n'
                '     (짧게 쓰려면:  alias 오토=' + VENV_PY + ' )')
            venv_only.append(pkg)
        else:
            say(BAD, f'{pkg} 가 없습니다  ({why})',
                '~/.autoedit/venv/bin/pip install fonttools numpy')
            problems.append(pkg)

    # 6. 크롬 — 카드·인서트 PNG 는 전부 크롬이 굽는다
    chrome = os.environ.get('CHROME',
                            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    if os.path.exists(chrome):
        say(OK, '크롬 — 카드·인서트 PNG 제작 가능')
    else:
        say(BAD, '크롬이 없습니다  (카드·인서트 PNG 제작에 필요)',
            f'찾은 곳: {chrome}\n'
            '     → brew install --cask google-chrome   (무료)\n'
            '     다른 곳에 있으면  export CHROME=<크롬 실행파일 경로>')
        problems.append('chrome')

    # 7. 폰트 — 자막용(OTF/TTF)과 카드용(woff2)은 «다른 파일»이다
    fonts = os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts'))
    want_sub = ['Pretendard-Bold.otf', 'NanumSquareNeo-ExtraBold.otf']
    want_card = ['Pretendard-Regular.woff2', 'Pretendard-Medium.woff2',
                 'Pretendard-Bold.woff2', 'Pretendard-Black.woff2']
    if not os.path.isdir(fonts):
        say(BAD, f'폰트 폴더가 없습니다: {fonts}',
            'bash auto-insert/scripts/mac/get_fonts.sh')
        problems.append('fonts')
    else:
        have = set(os.listdir(fonts))
        n_sub = len([h for h in have if h.lower().endswith(('.otf', '.ttf'))])
        miss_sub = [w for w in want_sub if w not in have]
        if miss_sub:
            say(WARN, f'자막용 폰트 {n_sub}개 — 없는 것: {", ".join(miss_sub)}', fonts)
        else:
            say(OK, f'자막용 폰트 {n_sub}개 (OTF/TTF)', fonts)

        # ⛔ 이게 없으면 카드가 «에러 하나 없이» 다른 글꼴로 구워진다 — 제일 무서운 고장이다
        miss_card = [w for w in want_card if w not in have]
        if miss_card:
            say(BAD, f'카드용 웹폰트(woff2) {4 - len(miss_card)}/4',
                f'없는 것: {", ".join(miss_card)}\n'
                '     → bash auto-insert/scripts/mac/get_fonts.sh\n'
                '     이대로 카드를 구우면 «에러 없이 다른 글꼴»로 나갑니다.')
            problems.append('woff2')
        else:
            say(OK, '카드용 웹폰트 4/4 (woff2)')

    # 8. swift — 인물 옆 자막(얼굴 인식)에만 필요
    if shutil.which('swift'):
        say(OK, 'swift — 인물 옆 자막 사용 가능')
    else:
        say(WARN, 'swift 가 없습니다 (선택)',
            '「인물 옆 자막」·OTS 자리 판정만 못 씁니다. Xcode Command Line Tools:\n'
            '     xcode-select --install')

    # 9. hyperframes — 인서트 제작 단계에만 필요
    if shutil.which('hyperframes'):
        say(OK, 'hyperframes — 인서트 제작 사용 가능')
    else:
        say(WARN, 'hyperframes 가 없습니다 (선택)',
            '인서트컷 «제작» 단계만 못 씁니다. npm i -g hyperframes')

    print()
    if problems:
        print(f'{BAD} 필수 항목 {len(problems)}개가 빠졌습니다. 설치.md 를 보세요.\n')
        return 1
    if venv_only:
        print(f'{WARN}부품({", ".join(venv_only)})이 «작은 방» 안에만 있습니다.')
        print(f'     스크립트를 부를 때 python3 대신 {VENV_PY} 를 쓰세요.\n')
    print(f'{OK} 준비 끝입니다.  →  examples/README.md 로 «첫 결과물»부터 내 보세요.\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
