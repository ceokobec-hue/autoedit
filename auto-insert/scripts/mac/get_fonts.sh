#!/bin/sh
# 폰트 조달 — 전부 무료·상업이용 가능. 공식 페이지로 라이선스를 확인한 것만 받는다.
#
# ⛔ 폰트 파일은 저장소에 넣지 않는다. 대부분 「파일 재배포 금지」다(영상에 구워 쓰는 건 허용).
# ⛔ libass 는 woff2 를 못 읽는다 → «자막용»은 OTF/TTF 로 받는다.
#    «카드·인서트 HTML»은 크롬이 굽기 때문에 woff2 가 필요하다 → 둘 다 받는다.
# ⛔ fonts.googleapis.com/css 로 받으면 서브셋(24~44KB)이 온다. 아래 CDN 경로로 전체 파일을 받는다.
# ⚠️ 같은 패밀리의 여러 굵기를 한 폴더에 두면 게이트가 「가장 굵은 것」을 집는다 → 자막용 굵기는 하나씩만.
#
# 사용: bash auto-insert/scripts/mac/get_fonts.sh          (기본 ~/.autoedit/fonts)
#       bash auto-insert/scripts/mac/get_fonts.sh <폴더>   (다른 곳에 받고 싶을 때)
#
# ⛔ set -e 를 쓰지 않는다 — URL 하나가 죽었을 때 «말없이 멈추는» 것이 제일 나쁘다.
#    하나가 실패해도 나머지를 마저 받고, 맨 끝에 「받은 것 / 못 받은 것」을 보여준다.

# ⛔ 자기 위치는 «cd 하기 전에» 알아 둔다 — 나중에 하면 $0 의 상대경로가 깨진다
SELF=$(cd "$(dirname "$0")" && pwd)

D="${1:-${AUTOEDIT_FONTS:-$HOME/.autoedit/fonts}}"
mkdir -p "$D" || { echo "⛔ 폴더를 만들지 못했습니다: $D"; exit 1; }
cd "$D" || exit 1
D=$(pwd)                       # 상대경로로 받았어도 절대경로로 굳힌다 (바로가기용)
GF=https://cdn.jsdelivr.net/gh/google/fonts@main/ofl
PW=https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/static/woff2

OK_LIST=""
NG_LIST=""
ok()  { OK_LIST="$OK_LIST  ✅ $1
"; }
ng()  { NG_LIST="$NG_LIST  ⛔ $1  ($2)
"; }

# get <저장할이름> <URL> — 성공/실패를 그때그때 말한다
get() {
  name="$1"; url="$2"
  if curl -fL --retry 2 --connect-timeout 20 -o "$name.part" "$url" 2>/dev/null && [ -s "$name.part" ]; then
    mv -f "$name.part" "$name"; echo "  ✅ $name"; ok "$name"
  else
    rm -f "$name.part"; echo "  ⛔ $name — 못 받았습니다 (건너뜁니다)"; ng "$name" "$url"
  fi
}

# getzip <저장할이름> <URL> <zip 안의 경로> — 압축 안에서 한 파일만 꺼낸다
getzip() {
  name="$1"; url="$2"; inner="$3"; tmp="$(mktemp -t autoedit_font).zip"
  if curl -fL --retry 2 --connect-timeout 20 -o "$tmp" "$url" 2>/dev/null && [ -s "$tmp" ]; then
    if unzip -j -o "$tmp" "$inner" -d . >/dev/null 2>&1; then
      base=$(basename "$inner")
      [ "$base" != "$name" ] && mv -f "$base" "$name"
      echo "  ✅ $name"; ok "$name"
    else
      echo "  ⛔ $name — 압축 안에 $inner 가 없습니다 (건너뜁니다)"; ng "$name" "zip 구조가 바뀜"
    fi
  else
    echo "  ⛔ $name — 못 받았습니다 (건너뜁니다)"; ng "$name" "$url"
  fi
  rm -f "$tmp"
}

echo "받는 곳: $D"
echo
echo "── ① 자막용 OTF/TTF · SIL OFL (수정·재배포까지 자유) ──"
get Pretendard-Bold.otf https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/public/static/Pretendard-Bold.otf
get GothicA1-Black.ttf  $GF/gothica1/GothicA1-Black.ttf
get GasoekOne.ttf       $GF/gasoekone/GasoekOne-Regular.ttf
get BagelFatOne.ttf     $GF/bagelfatone/BagelFatOne-Regular.ttf

echo
echo "── ② 자막용 · 국내 기업 무료 글꼴 (영상 사용 O · 파일 재배포 X) ──"
getzip NanumSquareNeo-ExtraBold.otf \
  https://hangeul.naver.com/hangeul_static/webfont/zips/nanum-square-neo.zip \
  "nanum-square-neo/OTF/NanumSquareNeoOTF-Eb.otf"
getzip Jalnan2.otf \
  https://framerusercontent.com/assets/uK4mTd9JFejCoAXNZyXHV6glsI.zip "Jalnan2/Jalnan2.otf"
getzip JalnanGothic.otf \
  https://framerusercontent.com/assets/nDlVcfwW7fVXLTZeKX4WdTVY1Yk.zip "JalnanGothic/JalnanGothic.otf"
getzip SCDream7.otf \
  https://s-core.co.kr/wp-content/uploads/2020/03/S-Core_Dream_OTF.zip "SCDream7.otf"

echo
echo "── ③ 카드·인서트 HTML 용 웹폰트 woff2 (크롬이 굽는다) ──"
for w in Regular Medium Bold Black; do
  get "Pretendard-$w.woff2" "$PW/Pretendard-$w.woff2"
done

echo
echo "── ④ 라이선스 전문 (OFL 은 폰트를 옮길 때 함께 가야 한다) ──"
mkdir -p licenses && cd licenses || exit 1
get OFL-Pretendard.txt  https://raw.githubusercontent.com/orioncactus/pretendard/main/LICENSE
get OFL-GothicA1.txt    $GF/gothica1/OFL.txt
get OFL-GasoekOne.txt   $GF/gasoekone/OFL.txt
get OFL-BagelFatOne.txt $GF/bagelfatone/OFL.txt
cd "$D" || exit 1

# ── ⑤ HTML/CSS 가 보는 자리와 이어 준다 ────────────────────────────
# card.css · insert-engine.html 은 «자기 옆의 fonts/» 를 본다. 폰트 창고는 여기 한 곳뿐이므로
# 저장소의 assets/fonts 를 이 폴더로 이어 둔다(바로가기). ⛔저장소에는 커밋되지 않는다.
ASSETS="$SELF/../../assets"
if [ -d "$ASSETS" ]; then
  if [ -d "$ASSETS/fonts" ] && [ ! -L "$ASSETS/fonts" ]; then
    echo
    echo "⚠️ $ASSETS/fonts 가 «진짜 폴더»입니다 — 바로가기를 만들지 않았습니다."
    echo "   woff2 4종을 그 폴더에도 복사해 두세요."
  else
    ln -sfn "$D" "$ASSETS/fonts" 2>/dev/null \
      && echo && echo "🔗 $ASSETS/fonts → $D  (HTML 카드가 폰트를 찾는 길)"
  fi
fi

echo
echo "════════ 결과 ════════"
printf '%s' "$OK_LIST"
if [ -n "$NG_LIST" ]; then
  echo
  echo "못 받은 것 — 아래 주소가 바뀌었을 수 있습니다:"
  printf '%s' "$NG_LIST"
  echo "  → 이 파일들이 없어도 나머지는 씁니다. 다만 카드 렌더에 woff2 4종은 «반드시» 필요합니다."
fi
echo
echo "확인: python3 doctor.py    (저장소 폴더에서)"
echo "     ~/.autoedit/venv/bin/python auto-insert/scripts/mac/srt_tools.py fontcheck <폰트파일> --srt <자막.srt>"
echo "     ↑ 자막에 쓸 글자가 그 폰트에 다 있는지 봅니다"

# ── 수동 조달 2종 (자동 다운로드 불가 — 공식 페이지가 SPA/동의 절차) ──
#  배민 도현   https://www.woowahan.com/fonts       → BMDOHYEON_otf.otf
#  G마켓 산스  https://company.gmarket.co.kr        → GmarketSansTTFBold.ttf
#  ※ 이미 맥에 설치해 둔 글꼴이 있다면 그대로 복사해 써도 됩니다:
#     cp ~/Library/Fonts/BMDOHYEON_otf.otf      "$D/BMDoHyeon.otf"
#     cp ~/Library/Fonts/GmarketSansTTFBold.ttf "$D/GmarketSansBold.ttf"
