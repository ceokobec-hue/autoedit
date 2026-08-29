#!/bin/sh
# 시험용 «10초짜리 영상 + 자막»을 만든다. 카메라도 촬영본도 필요 없다.
#
# 왜 필요한가: 「내 환경이 제대로 됐나」를 «결과물»로 확인하는 게 제일 확실하다.
#   doctor.py 의 ✅ 는 부품이 있다는 뜻이지, 끝까지 돈다는 뜻이 아니다.
#
# 사용: bash examples/make_sample.sh          (저장소 폴더에서)
#       → examples/sample.mp4 · examples/sample.srt · examples/sample2.mp4
#
# ⛔ set -e 를 쓰지 않는다 — 어디서 멈췄는지 말없이 사라지지 않게.

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
FF=$(python3 "$ROOT/ff_path.py" 2>/dev/null | sed -n 's/^ffmpeg *: *\(.*\) [✅⛔].*/\1/p')
[ -z "$FF" ] && FF=${FFMPEG:-/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg}

if [ ! -x "$FF" ]; then
  echo "⛔ ffmpeg 을 못 찾았습니다: $FF"
  echo "   설치.md 1단계를 하셨나요?   brew install ffmpeg-full"
  echo "   확인:  python3 doctor.py"
  exit 1
fi
echo "ffmpeg: $FF"

W=2560; H=1440; SEC=20   # 20초 — OTS 카드는 8초 이상 간격이 필요해 10초로는 두 장이 안 들어간다

# ── ① 시험용 영상 — 색이 계속 바뀌는 배경 + 초 세는 숫자 ────────────
#    배경이 변해야 «카드가 배경에 묻히나»를 재는 기능을 시험할 수 있다.
echo "① 영상 만드는 중… (${W}x${H} · ${SEC}초)"
"$FF" -v error -y \
  -f lavfi -i "testsrc2=size=${W}x${H}:rate=30:duration=${SEC}" \
  -f lavfi -i "sine=frequency=440:duration=${SEC}" \
  -c:v h264_videotoolbox -b:v 4M -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart \
  "$HERE/sample.mp4" \
  && echo "  ✅ examples/sample.mp4" \
  || { echo "  ⛔ 영상 만들기 실패"; exit 1; }

# ── ② 두 번째 카메라 흉내 — 오토멀티캠 시험용 (같은 소리 · 다른 그림) ──
echo "② 두 번째 카메라 영상 만드는 중…"
"$FF" -v error -y \
  -f lavfi -i "smptebars=size=${W}x${H}:rate=30:duration=${SEC}" \
  -f lavfi -i "sine=frequency=440:duration=${SEC}" \
  -c:v h264_videotoolbox -b:v 4M -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart \
  "$HERE/sample2.mp4" \
  && echo "  ✅ examples/sample2.mp4" \
  || echo "  ⚠️ 두 번째 영상은 실패 — 오토인서트 시험에는 없어도 됩니다"

# ── ③ 자막 — 인서트가 «어느 말에 붙는지» 고르는 재료 ────────────────
cat > "$HERE/sample.srt" <<'SRT'
1
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
SRT
echo "  ✅ examples/sample.srt (8줄)"

echo
echo "다음: examples/README.md 의 「2. 첫 결과물」 로 가세요."
