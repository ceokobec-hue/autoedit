# examples — 5분 안에 «첫 결과물» 내기

여기 있는 파일로 **한 바퀴를 끝까지 돌려 보는 것**이 목적입니다.
자기 영상을 넣기 전에 여기서 먼저 돌려 보세요. 어디가 막히는지 미리 알 수 있습니다.

> **왜 이게 필요한가요?**
> `python3 doctor.py` 의 ✅ 는 「부품이 있다」는 뜻이지 「끝까지 돈다」는 뜻이 아닙니다.
> 진짜 확인은 **결과물 파일 하나가 나오는 것**입니다.

---

## 0. 준비 — 두 줄

모든 명령은 **저장소 폴더 안에서** 칩니다.

```bash
cd ~/Downloads/autoedit          # ← clone 받은 곳으로
PY=~/.autoedit/venv/bin/python   # ← 이 도구 전용 «작은 방»의 파이썬
```

> **왜 `python3` 가 아닌가요?** 부품(numpy·fontTools)을 `~/.autoedit/venv` 라는 작은 방 안에
> 넣어 뒀습니다. 방 밖의 `python3` 로는 그 부품이 **안 보입니다**. 방의 파이썬을 불러야 합니다.
> 설치가 아직이면 `설치.md` 를 먼저 보세요.

---

## 1. 시험용 영상 만들기 (30초)

카메라도, 찍어 둔 영상도 필요 없습니다. ffmpeg 이 만들어 줍니다.

```bash
bash examples/make_sample.sh
```

나오는 것:

| 파일 | 무엇 |
|---|---|
| `examples/sample.mp4` | 20초 · 2560×1440 · 색이 계속 바뀌는 배경 |
| `examples/sample2.mp4` | 「두 번째 카메라」 흉내 — 소리는 같고 그림만 다름 |
| `examples/sample.srt` | 자막 8줄 |

> 배경이 **계속 바뀌는** 영상인 이유: 「카드가 배경에 묻히나」를 재는 기능을 시험하려면
> 배경이 변해야 합니다. 색이 고른 화면으로는 그 기능이 일하는지 알 수 없습니다.

---

## 2. 첫 결과물 — 인서트컷이 얹힌 영상 (3분)

```bash
mkdir -p examples/out && cd examples/out
S=../../auto-insert/scripts/mac

# ① 카드를 PNG 로 굽는다 (Chrome 이 그립니다)
$PY $S/build_inserts.py --cards ../cards.json --place ../place.json --out inserts.json

# ② 채널 이름 + 단원 소제목을 자막(ASS)으로 만든다
$PY $S/broadcast_overlay.py --chapters ../chapters.json --end 20 --out overlay.ass --channel "내 채널"

# ③ 원본 위에 한 번에 굽는다
$PY $S/render_final.py --video ../sample.mp4 --inserts inserts.json --ass overlay.ass \
                       --out 완성본.mp4 --bitrate 8M

open 완성본.mp4        # ← 여기서 카드가 보이면 성공입니다
cd ../..
```

**보여야 하는 것** — 왼쪽 위에 「내 채널 / 첫 번째 단원」, 2.5초쯤에 코너 카드,
12초쯤에 화면을 가득 채우는 풀프레임 카드.

<details>
<summary>안 보이면?</summary>

- **카드가 통째로 안 보임** → `shots/` 안에 PNG 가 생겼는지 보세요. 없으면 Chrome 문제입니다
  (`python3 doctor.py` 의 「크롬」 줄).
- **글꼴이 이상함** → `bash auto-insert/scripts/mac/get_fonts.sh` 를 돌리세요.
  카드는 **woff2 4종**이 있어야 제 글꼴로 나옵니다.
- **왼쪽 위 글자만 안 나옴** → 기본 ffmpeg 을 보고 있는 겁니다. `python3 doctor.py` 로 확인하세요.
</details>

---

## 3. OTS 카드 — 자리·가독성을 코드가 정하는 쪽 (2분)

2번은 「내가 정한 자리」에 놓습니다. 이쪽은 **코드가 배경을 재서 자리와 글자색을 스스로 고릅니다.**

```bash
mkdir -p examples/ots && cd examples/ots
S=../../auto-insert/scripts/mac/ots_v2
cp ../ots_cards.json cards.json

$PY $S/plan_cards.py ../sample.mp4 cards.json                       # 자리·톤 재기 → plan_out.json
$PY $S/approve.py --cards cards.json --plan plan_out.json --end 20  # 확정 → 세 파일
$PY $S/cards_v2.py check_cards.json fin                             # 카드 PNG
$PY $S/build_sheet.py --video ../sample.mp4 --srt ../sample.srt     # 🙋 검수 시트
open 검수시트.html
cd ../..
```

`plan_cards.py` 가 찍는 표에서 `흰대비`·`검대비` 는 **명도 대비값**입니다 — 클수록 잘 읽힙니다.
값이 낮으면 코드가 「스크림(그늘)을 깔자」고 스스로 판정합니다.

**검수 시트가 이 도구의 핵심**입니다. 카드를 실제 화면에 얹은 그림 옆에
그 순간의 대사를 붙여 놓아서, **번호로 지적**하면 됩니다.

이대로 좋으면 최종 렌더:

```bash
cd examples/ots && $PY ../../auto-insert/scripts/mac/ots_v2/render_ots_v2.py \
    --video ../sample.mp4 --out 완성본.mp4 --bitrate 6M && cd ../..
```

---

## 4. 카메라 두 대 — 소리로 싱크 맞추기 (1분)

```bash
mkdir -p examples/mc && cd examples/mc
FF=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg     # 인텔 맥이면 /usr/local/opt/...

# 소리만 뽑는다 — sync_probe 는 «영상»이 아니라 «16bit 모노 wav» 를 먹습니다
$FF -v error -i ../sample.mp4  -vn -ac 1 -ar 16000 -c:a pcm_s16le -y A.wav
$FF -v error -i ../sample2.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le -y B.wav

$PY ../../auto-multicam/scripts/mac/sync_probe.py A.wav B.wav --probes 5,10,15 --win 4 --out sync.json
cd ../..
```

`밀림 0.000초` 가 나오면 정상입니다 — 두 샘플은 **같은 소리**를 넣어 만들었기 때문입니다.
실제 촬영본이라면 여기 나온 `intercept` 값을 `render_multicam.py --offset` 에 넣습니다.

전체 흐름은 `auto-multicam/사용법.md` 를 보세요.

---

## 이 폴더의 파일

| 파일 | 무엇 | 커밋되나 |
|---|---|---|
| `make_sample.sh` | 시험용 영상·자막을 만드는 스크립트 | ✅ |
| `cards.json` | 인서트컷 원고 2장 (코너 1 + 풀프레임 1) | ✅ |
| `place.json` | 그 카드를 «어디에·언제» 놓을지 | ✅ |
| `chapters.json` | 단원 2개 (0초·10초) | ✅ |
| `ots_cards.json` | OTS 카드 원고 2장 (스티커 + 무판대판) | ✅ |
| `job.example.json` | `pipeline_v2` 용 설정 예시 | ✅ |
| `sample.mp4` · `sample2.mp4` · `sample.srt` | 1번이 만들어 냅니다 | ⛔ (`.gitignore`) |
| `out/` · `ots/` · `mc/` | 2~4번의 산출물 | ⛔ |

칸 하나하나의 뜻은 [`파일형식.md`](../파일형식.md) 에 표로 있습니다.

## 다 돌려 본 뒤 — 내 영상으로

1. `cards.json` · `ots_cards.json` 의 글자를 **내 회차 내용으로** 바꿉니다.
2. `at`(언제) · `dur`(몇 초) 를 내 영상에 맞춥니다.
3. `--video` · `--srt` 를 내 파일로 바꿉니다.

`examples/` 는 그대로 두세요. 다음에 뭔가 안 될 때 **「원래는 되는가」를 확인하는 기준**이 됩니다.
