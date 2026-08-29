#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""폰트 조달 — 전부 무료·상업이용 가능. 공식 페이지로 라이선스를 확인한 것만 받는다.

⛔ 폰트 파일은 저장소에 넣지 않는다. 대부분 「파일 재배포 금지」다(영상에 구워 쓰는 건 허용).
⛔ libass 는 woff2 를 못 읽는다 → «자막용»은 OTF/TTF 로 받는다.
   «카드·인서트 HTML»은 크롬이 굽기 때문에 woff2 가 필요하다 → 둘 다 받는다.
⛔ fonts.googleapis.com/css 로 받으면 서브셋(24~44KB)이 온다. 아래 CDN 경로로 전체 파일을 받는다.
⚠️ 같은 패밀리의 여러 굵기를 한 폴더에 두면 게이트가 「가장 굵은 것」을 집는다 → 자막용 굵기는 하나씩만.

사용: python3 auto-insert/scripts/mac/get_fonts.py          (기본 ~/.autoedit/fonts)
      python3 auto-insert/scripts/mac/get_fonts.py <폴더>   (다른 곳에 받고 싶을 때)

★ get_fonts.sh 와 하는 일이 같다. 윈도우에는 bash·curl·unzip 이 없어서 파이썬으로도 두었다.
  파이썬 표준 부품(urllib·zipfile)만 쓴다 — 따로 받을 것이 없다.

⛔ 하나가 실패해도 «말없이 멈추지» 않는다 — 나머지를 마저 받고,
   맨 끝에 「받은 것 / 못 받은 것 + 직접 받을 주소」를 보여준다.
"""
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

GF = 'https://cdn.jsdelivr.net/gh/google/fonts@main/ofl'
PW = 'https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/woff2'

# ⚠️ 어떤 CDN 은 파이썬 기본 이름표(Python-urllib)를 막는다 → 브라우저처럼 이름을 대 준다
UA = {'User-Agent': 'Mozilla/5.0 (autoedit get_fonts)'}

OK_LIST = []       # [(이름,)]
NG_LIST = []       # [(이름, 왜)]


def fetch(url, timeout=30, tries=3):
    """내려받은 «내용»을 돌려준다. 실패하면 예외."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if not data:
                raise IOError('내용이 비어 있습니다')
            return data
        except Exception as e:      # 네트워크는 한 번에 안 될 때가 있다 → 두 번 더 해 본다
            last = e
    raise last


def get(name, url):
    """파일 하나를 받아 그 이름으로 저장한다."""
    try:
        data = fetch(url)
    except Exception as e:
        print('  ⛔ %s — 못 받았습니다 (건너뜁니다)' % name)
        NG_LIST.append((name, url, str(e)))
        return
    # ⛔ 곧바로 name 으로 쓰면 중간에 끊겼을 때 «반쪽짜리 폰트»가 남는다 → 다 받은 뒤 이름을 바꾼다
    tmp = name + '.part'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, name)
    print('  ✅ %s' % name)
    OK_LIST.append(name)


def getzip(name, url, inner):
    """압축을 받아 그 안에서 파일 «하나»만 꺼낸다."""
    try:
        data = fetch(url, timeout=90)
    except Exception as e:
        print('  ⛔ %s — 못 받았습니다 (건너뜁니다)' % name)
        NG_LIST.append((name, url, str(e)))
        return
    tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    tmp.write(data); tmp.close()
    try:
        with zipfile.ZipFile(tmp.name) as z:
            member = inner if inner in z.namelist() else None
            if member is None:
                # ⚠️ 배포처가 압축 안 폴더 이름을 바꾸는 일이 잦다 → 파일 이름만 같아도 받아 준다
                want = os.path.basename(inner)
                for m in z.namelist():
                    if os.path.basename(m) == want:
                        member = m
                        break
            if member is None:
                print('  ⛔ %s — 압축 안에 %s 가 없습니다 (건너뜁니다)' % (name, inner))
                NG_LIST.append((name, url, 'zip 구조가 바뀜'))
                return
            with open(name, 'wb') as f:
                f.write(z.read(member))
        print('  ✅ %s' % name)
        OK_LIST.append(name)
    except zipfile.BadZipFile:
        print('  ⛔ %s — 받은 것이 압축 파일이 아닙니다 (건너뜁니다)' % name)
        NG_LIST.append((name, url, '압축 파일이 아님'))
    finally:
        os.unlink(tmp.name)


def link_assets(self_dir, dest):
    """카드 HTML 이 «자기 옆의 fonts/» 를 보므로, 저장소의 assets/fonts 를 폰트 창고로 이어 준다.

    ⛔ 저장소에는 커밋되지 않는다(.gitignore).
    ⚠️ 윈도우는 «바로가기(심볼릭 링크)» 를 만들려면 관리자 권한이나 개발자 모드가 필요하다.
       안 되면 woff2 4종만 그 폴더로 «복사»한다 — 카드가 제 글꼴로 나오는 데 필요한 건 그것뿐이다.
    """
    assets = os.path.normpath(os.path.join(self_dir, '..', '..', 'assets'))
    if not os.path.isdir(assets):
        return
    target = os.path.join(assets, 'fonts')
    if os.path.isdir(target) and not os.path.islink(target):
        print()
        print('⚠️ %s 가 «진짜 폴더»입니다 — 바로가기를 만들지 않았습니다.' % target)
        print('   woff2 4종을 그 폴더에도 복사해 두세요.')
        return
    try:
        if os.path.islink(target) or os.path.exists(target):
            os.unlink(target)
        os.symlink(dest, target, target_is_directory=True)
        print()
        print('🔗 %s → %s  (HTML 카드가 폰트를 찾는 길)' % (target, dest))
    except OSError:
        os.makedirs(target, exist_ok=True)
        n = 0
        for w in ('Regular', 'Medium', 'Bold', 'Black'):
            f = 'Pretendard-%s.woff2' % w
            src = os.path.join(dest, f)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(target, f))
                n += 1
        print()
        print('📄 바로가기를 만들 수 없어 woff2 %d개를 복사했습니다 → %s' % (n, target))
        print('   (윈도우에서 바로가기는 개발자 모드나 관리자 권한이 필요합니다. 복사로도 똑같이 됩니다.)')


def main():
    self_dir = os.path.dirname(os.path.abspath(__file__))   # ⛔ 폴더를 옮기기 «전에» 알아 둔다

    dest = (sys.argv[1] if len(sys.argv) > 1
            else os.environ.get('AUTOEDIT_FONTS')
            or os.path.expanduser('~/.autoedit/fonts'))
    dest = os.path.abspath(os.path.expanduser(dest))
    try:
        os.makedirs(dest, exist_ok=True)
    except OSError as e:
        sys.exit('⛔ 폴더를 만들지 못했습니다: %s\n   %s' % (dest, e))
    os.chdir(dest)

    print('받는 곳: %s' % dest)
    print()
    print('── ① 자막용 OTF/TTF · SIL OFL (수정·재배포까지 자유) ──')
    get('Pretendard-Bold.otf',
        'https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/public/static/Pretendard-Bold.otf')
    get('GothicA1-Black.ttf', GF + '/gothica1/GothicA1-Black.ttf')
    get('GasoekOne.ttf',      GF + '/gasoekone/GasoekOne-Regular.ttf')
    get('BagelFatOne.ttf',    GF + '/bagelfatone/BagelFatOne-Regular.ttf')

    print()
    print('── ② 자막용 · 국내 기업 무료 글꼴 (영상 사용 O · 파일 재배포 X) ──')
    getzip('NanumSquareNeo-ExtraBold.otf',
           'https://hangeul.naver.com/hangeul_static/webfont/zips/nanum-square-neo.zip',
           'nanum-square-neo/OTF/NanumSquareNeoOTF-Eb.otf')
    getzip('Jalnan2.otf',
           'https://framerusercontent.com/assets/uK4mTd9JFejCoAXNZyXHV6glsI.zip',
           'Jalnan2/Jalnan2.otf')
    getzip('JalnanGothic.otf',
           'https://framerusercontent.com/assets/nDlVcfwW7fVXLTZeKX4WdTVY1Yk.zip',
           'JalnanGothic/JalnanGothic.otf')
    getzip('SCDream7.otf',
           'https://s-core.co.kr/wp-content/uploads/2020/03/S-Core_Dream_OTF.zip',
           'SCDream7.otf')

    print()
    print('── ③ 카드·인서트 HTML 용 웹폰트 woff2 (크롬이 굽는다) ──')
    for w in ('Regular', 'Medium', 'Bold', 'Black'):
        get('Pretendard-%s.woff2' % w, '%s/Pretendard-%s.woff2' % (PW, w))

    print()
    print('── ④ 라이선스 전문 (OFL 은 폰트를 옮길 때 함께 가야 한다) ──')
    lic = os.path.join(dest, 'licenses')
    os.makedirs(lic, exist_ok=True)
    os.chdir(lic)
    get('OFL-Pretendard.txt',
        'https://raw.githubusercontent.com/orioncactus/pretendard/main/LICENSE')
    get('OFL-GothicA1.txt',    GF + '/gothica1/OFL.txt')
    get('OFL-GasoekOne.txt',   GF + '/gasoekone/OFL.txt')
    get('OFL-BagelFatOne.txt', GF + '/bagelfatone/OFL.txt')
    os.chdir(dest)

    # ── ⑤ HTML/CSS 가 보는 자리와 이어 준다 ────────────────────────────
    link_assets(self_dir, dest)

    print()
    print('════════ 결과 ════════')
    for name in OK_LIST:
        print('  ✅ %s' % name)
    if NG_LIST:
        print()
        print('못 받은 것 — 아래 주소가 바뀌었을 수 있습니다.')
        print('브라우저로 그 주소를 열어 직접 받으신 뒤, 위 「받는 곳」 폴더에')
        print('«괄호 안의 이름 그대로» 넣어 주시면 똑같이 됩니다:')
        for name, url, why in NG_LIST:
            print('  ⛔ (%s)\n       %s\n       사유: %s' % (name, url, why))
        print('  → 이 파일들이 없어도 나머지는 씁니다. 다만 카드 렌더에 woff2 4종은 «반드시» 필요합니다.')

    py = 'python' if os.name == 'nt' else 'python3'
    print()
    print('확인: %s doctor.py    (저장소 폴더에서)' % py)
    print('     ~/.autoedit/venv/bin/python auto-insert/scripts/mac/srt_tools.py fontcheck <폰트파일> --srt <자막.srt>')
    print('     ↑ 자막에 쓸 글자가 그 폰트에 다 있는지 봅니다')
    print()
    print('── 수동 조달 2종 (자동 다운로드 불가 — 공식 페이지가 동의 절차를 거칩니다) ──')
    print('  배민 도현   https://www.woowahan.com/fonts       → BMDOHYEON_otf.otf')
    print('  G마켓 산스  https://company.gmarket.co.kr        → GmarketSansTTFBold.ttf')
    print('  ※ 이미 컴퓨터에 설치해 둔 글꼴이 있다면 그대로 복사해 써도 됩니다.')


if __name__ == '__main__':
    main()
