# 오토인서트 — 맥(Apple Silicon) 실행 경로

윈도우판(`../*.ps1`)과 **같은 공정·같은 규약**을 macOS에서 돌린다.
PowerShell 스크립트는 맥에서 못 돈다(그중 `srt_tools.ps1` 의 글자 폭 측정은
윈도우 전용 WPF `GlyphTypeface` 라 pwsh 를 깔아도 안 된다). 그래서 이식했다.

**전제**: 컷편집과 **본문 자막까지 이미 끝낸** mp4 + SRT 로 시작한다.
그래서 맥판은 본문 자막을 굽지 않는다 — **장식층(인물 옆 자막·예능형 자막)과 인서트컷** 전담.

---

## 한 번만 하는 준비

전부 [설치.md](../../../설치.md) 에 있다. 이미 하셨으면 건너뛴다.

```bash
brew install ffmpeg-full                      # ⛔ 기본 ffmpeg 엔 libass 가 없다 → 자막을 한 글자도 못 굽는다
brew install --cask google-chrome             # 카드·인서트 PNG 를 굽는다
npm i -g hyperframes                          # 인서트 «제작» 단계에만 필요. 안 깔아도 나머지는 돈다
python3 -m venv ~/.autoedit/venv && ~/.autoedit/venv/bin/pip install fonttools numpy
bash auto-insert/scripts/mac/get_fonts.sh     # ~/.autoedit/fonts
```

검증은 한 줄로: `python3 doctor.py` — **전부 ✅ 면 준비 끝.**

## 매번 하는 준비 (터미널 열 때마다)

```bash
cd ~/Downloads/autoedit                       # ★ 모든 명령은 저장소 폴더 안에서
PY=~/.autoedit/venv/bin/python                # 파이썬은 «작은 방» 것 (설치.md 2단계)
S=auto-insert/scripts/mac
```

> ⚠️ **결과물은 «지금 서 있는 폴더»에 만들어집니다.** 회차별 작업 폴더를 만들고
> 거기서 돌리려면 `cd ~/작업/1회차` 로 옮긴 뒤 스크립트를 **저장소 경로로** 부르세요:
> `$PY ~/Downloads/autoedit/$S/build_inserts.py ...`

---

# 갈래 ① 인물 옆 자막 + 인서트컷 합성

## 공정

```
① srt_tools.py      SRT 읽기·블록 스캔·앵커 탐색·큐 병합·규격 대조
② place_captions.py 큐마다 프레임 1장 → 화자 위치 → 자막 자리 + 인서트 하단 금지선
③ (인서트 제작)      assets/insert-engine.html 데이터 배열 → hyperframes render
④ plan_check.py     ★게이트. 겹침·삽입점 충돌·보호구간·자산 실재·길이 초과
⑤ make_ass_deco.py  인물 옆 자막 + 예능형 자막 → .ass
⑥ compose_mac.py    1 인서트 덮어쓰기 → 2 자막 굽기 → 3 범퍼 삽입
```

## 파일이 어떻게 이어지나

| 단계 | 먹는 것 | 내놓는 것 |
|---|---|---|
| ① `srt_tools.py sync` | `자막.srt` + `편집원본.mp4` | (화면에 표만 — 0.5초 넘으면 여기서 멈춘다) |
| ② `place_captions.py` | `--video` `--srt` | `작업폴더/placement.json` |
| ③ 인서트 제작 | `plan.json` 의 컷 목록 | `인서트mp4들/INS-01.mp4` … |
| ④ `plan_check.py` | `plan.json` | 통과/실패 판정만 |
| ⑤ `make_ass_deco.py` | `placement.json` + `variety.json` + `plan.json` | `deco.ass` |
| ⑥ `compose_mac.py` | `plan.json`(안에 `ass`·`inserts` 경로) | `완성본.mp4` |

`plan.json` · `variety.json` 에 무엇을 적는지는 [`파일형식.md`](../../../파일형식.md).

## 명령

```bash
$PY $S/srt_tools.py sync 자막.srt 편집원본.mp4        # 0.5초 넘으면 여기서 멈춘다
$PY $S/srt_tools.py fontcheck ~/.autoedit/fonts/NanumSquareNeo-ExtraBold.otf --srt 자막.srt

$PY $S/place_captions.py --video 편집원본.mp4 --srt 자막.srt --out 작업폴더
$PY $S/plan_check.py --plan plan.json --protect 440:455

$PY $S/make_ass_deco.py --placement 작업폴더/placement.json \
     --font ~/.autoedit/fonts/NanumSquareNeo-ExtraBold.otf \
     --variety variety.json --plan plan.json --out deco.ass

$PY $S/compose_mac.py --plan plan.json --stages 1,2,3
```

부분 재실행은 `--stages 2` 처럼 층만 다시 돈다(v1 재사용).

---

# 갈래 ② 방송형 오버레이 (배경이 계속 바뀌는 영상)

규격·함정은 [`../../references/broadcast-overlay.md`](../../references/broadcast-overlay.md). 여기선 **명령과 파일 계보**만.

## 파일이 어떻게 이어지나 ★ 이 표를 먼저 본다

```
cards.json      ─ots_place.py→  ots_measure.json
                                      │
                                      ↓ (--from-measure 가 자동 계산)
cards.json  +  place.json  ─build_inserts.py→  inserts.json  +  shots/<id>.png
                                      │
chapters.json ─broadcast_overlay.py→ overlay.ass
                                      │
                                      ↓
                 review_sheet.py  🙋  →  render_final.py  →  완성본.mp4
```

| 스크립트 | 먹는 것 | 내놓는 것 |
|---|---|---|
| `ots_place.py` | `영상.mp4` `cards.json` | **`ots_measure.json`** (지금 폴더에) |
| `build_inserts.py` | `--cards cards.json` `--from-measure ots_measure.json` | **`inserts.json`** · `shots/<id>.png` · `place.json` |
| `broadcast_overlay.py` | `--chapters chapters.json` `--end <초>` | **`overlay.ass`** |
| `review_sheet.py` | `--video` `--inserts inserts.json` `--chapters` | **`.png` 격자 시트** 🙋 (⛔`.html` 아님) |
| `render_final.py` | `--video` `--inserts inserts.json` `--ass overlay.ass` | 완성본 mp4 |

> `--ass` 를 안 주면 지금 폴더의 `overlay.ass` 를 찾습니다.
> **그 파일이 없으면 채널 버그·소제목 없이 굽고 한 줄로 알려 줍니다** — 조용히 빠지지 않습니다.

## 명령

```bash
DUR=$(/opt/homebrew/opt/ffmpeg-full/bin/ffprobe -v error \
      -show_entries format=duration -of csv=p=0 영상.mp4)

$PY $S/ots_place.py 영상.mp4 cards.json                              # → ots_measure.json
$PY $S/build_inserts.py --cards cards.json --from-measure ots_measure.json --out inserts.json
$PY $S/broadcast_overlay.py --chapters chapters.json --end $DUR --out overlay.ass

$PY $S/review_sheet.py --video 영상.mp4 --inserts inserts.json --chapters chapters.json --out 검수시트.png
open 검수시트.png                                                    # 🙋 번호로 지적한다

$PY $S/render_final.py --video 영상.mp4 --inserts inserts.json --ass overlay.ass --out 완성본.mp4 --bitrate 24M
```

**자동 배치가 마음에 안 들면** `place.json` 을 직접 고친 뒤 `--from-measure` 없이 다시 돌린다.

```bash
$PY $S/build_inserts.py --cards cards.json --place place.json --out inserts.json
```

`render_final.py` 에 `--ss/--t` 를 주면 **짧게 시험 렌더**해서 필터 그래프를 먼저 검증할 수 있다(60초 = 17초).
전체를 굽기 전에 이걸 한 번 하면, 몇 분짜리 렌더를 헛돌리는 일이 없다.

⚠️ 스크립트 상단의 좌표 상수(`GUARD`, `TOPSAFE`)는 **영상마다 확인할 것.**
`GUARD`(구워진 자막 윗변)는 **글자 y 히스토그램으로 실측**한다 — 단순 min 은 슬라이드를 자막으로 오인한다.

---

## 맥에서 바뀐 것 (윈도우판과의 차이)

| | 윈도우 | 맥 |
|---|---|---|
| 글자 폭 측정 | WPF `GlyphTypeface` | **fontTools** `hmtx/cmap` — 실측 결과 동일(Pretendard 0.8643 vs 문서 0.864) |
| 인코더 | `h264_nvenc` | **`h264_videotoolbox`** |
| 화자 위치 | 없던 기능 | **Apple Vision** `VNDetectHumanRectangles` + `VNDetectFaceRectangles` |
| 조각 파일 | 남겨 둠 | **이어 붙인 즉시 삭제** (긴 영상은 중간 파일이 디스크를 금방 채운다) |
| 받아쓰기 | faster-whisper | `whisper-cli` — ⚠️ **`brew install whisper-cpp` 로 따로 받는다.** ffmpeg-full 에 안 딸려 온다 |

## 참고 실측 (M1 8GB 랩톱 기준 · QHD)

여러분 맥에서는 다르게 나옵니다. **「대략 이 정도 걸리는구나」** 감을 잡는 용도입니다.

| 작업 | 시간 |
|---|---|
| 인서트 47컷 · 약 250초 · 1080p high 렌더 | 약 **6분 30초** |
| 같은 공식 | 대략 `8초 + 영상초 × 1.5` |
| 자막 굽기 (12초 클립, videotoolbox) | 2초 |
| Vision 화자 판정 | 프레임 1장당 1초 미만 |

---

## 자막 폰트 (20종을 검사해 10종을 남긴 결과)

`bash auto-insert/scripts/mac/get_fonts.sh [폴더]` 로 받는다. 기본 `~/.autoedit/fonts`.
**자동 8종 + 수동 2종**(배민 도현·G마켓 산스 — 공식 페이지가 동의 절차라 직접 받는다).
카드 렌더용 **woff2 4종**과 **라이선스 전문**도 같이 받는다.

전부 **무료 · 영상에 구워 쓰는 것 허용**. 다만 **폰트 파일 자체를 재배포하는 조건은 제각각**이라
저장소에 넣지 않았다 → [THIRD-PARTY-NOTICES.md](../../../THIRD-PARTY-NOTICES.md)

| 용도 | 1순위 | 2순위 | 비고 |
|---|---|---|---|
| 본문 · 인물 옆 자막 | **Pretendard**(0.864em) | NanumSquare Neo Eb(0.948) | Pretendard 가 제일 좁아 한 줄에 많이 들어간다 |
| 예능형 강조 | **Jalnan 2**(잘난체2) | BM DoHyeon OTF | 둘 다 결손 0 |
| 초굵은 강조·썸네일 | Gasoek One | Bagel Fat One | 기호(①○★→) 없음 → 짧은 말만 |

### ⛔ 쓰면 안 되는 것 — 「」가 없다

인서트 엔진은 `「」` 를 많이 쓴다. 아래는 **□로 뜨거나 빈칸**이 된다.

| 폰트 | 빠진 글자 |
|---|---|
| **Black Han Sans**(검은고딕) | 「」『』· — … 화살표 · 원문자 · ★ |
| **Jua**(주아) | 「」『』· — … 화살표 · 원문자 |
| **Sunflower**(해바라기) | 「」『』· — … 기호 전부 |
| **구글판 Do Hyeon** | 「」『』· — …  ★**배민 원본 `.otf` 는 정상** — 같은 이름 다른 파일 |
| **Noto Sans KR 가변** | 글자는 있으나 **Thin 으로 렌더된다** → 자막 불가 |
| S-Core Dream | `—`(em dash) 하나 |

새 폰트를 받으면 반드시:
```bash
$PY $S/srt_tools.py fontcheck 폰트.otf --srt 이번회차.srt
```
`ASS Fontname` 은 **파일명이 아니라 패밀리 이름**이다. fontcheck 가 찍어 주는 이름을 그대로 써야 libass 가 찾는다.

---

## 함정 (실제로 당한 것)

1. **`ffmpeg -filters` 로 확인할 때 «전체 경로»를 쓸 것.** homebrew 기본 `ffmpeg` 에는
   libass·freetype 이 없고, `ffmpeg-full` 은 keg-only 라 PATH 에 안 올라온다.
   `-buildconf` 에 `--enable-libass` 가 있어도 grep 패턴이 틀리면 0 이 나온다 — `grep -w` 로 볼 것.
2. **Vision `regionOfInterest` 를 쓰지 말 것.** ROI 를 주면 결과 좌표가 **ROI 기준**으로 돌아온다.
   실측: 아래 45% ROI 로 찾은 자막이 y=112(화면 위)로 나왔고 전체 스캔은 y=642 였다.
   **에러가 없고 숫자도 그럴싸했다.** 전체 스캔과 대조해야만 잡힌다.
3. **인서트 구간엔 인물 옆 자막을 달지 않는다.** 인서트가 화면을 통째로 덮으므로 '옆'이 없고,
   인서트 자체 글자를 가린다(실측: 인서트의 큰 글씨가 반쯤 가려짐). `--plan` 을 주면 자동으로 숨는다.
4. **못 찾은 큐를 지어내지 않는다.** `place_captions.py` 는 직전 판정을 물려받고 `carried=true` 로 표시한다.
   걸어 다니는 B롤·클로즈업에서는 검출률이 떨어진다(실측 50%). 강의처럼 화자가 고정된 화면이 대상이다.
5. **길이가 맞아도 내용은 틀릴 수 있다.** 단계마다 콘택트시트를 뽑아 **눈으로** 본다.
6. **Chrome 헤드리스에서 알파를 얻으려면 카드 주변에 여백**을 둬야 한다. 창에 딱 맞으면 `rgb24` 로 나와
   드롭섀도우가 잘린다(`ffprobe ... pix_fmt` 로 `rgba` 확인).
7. **`~/Desktop` 밑 파일 복사가 멈춘다**(iCloud 가 파일을 아직 안 내려받은 상태). 폰트는 CDN 에서 받는다.
8. **카드 CSS 를 `<link>` 로 걸면 «에러 없이 민무늬 카드»가 나온다.** HTML 은 `build/` 에 있고
   CSS 정본은 `assets/broadcast/` 에 있어 경로가 안 맞는다 → 내용을 통째로 HTML 안에 넣는다.
