# autoedit — 강의 영상 편집 자동화 도구

**맥(Apple Silicon) 전용입니다. 윈도우에서는 돌지 않습니다.**

혼자 강의 영상을 만드는 사람이 **편집에 쓰는 시간을 줄이자**고 만든 도구입니다.
제 채널([유튜브 「모두의 AI교육」](https://www.youtube.com/@workai_lab)) 영상들을 실제로 이걸로 만들었고, 그대로 공개합니다.

> **English:** Lecture-video editing automation for macOS (Apple Silicon) — dual-camera
> audio sync, whiteboard-writing detection, speaker-aware subtitle placement, and
> broadcast-style overlays. Built for **Korean-language** lecture videos: the typography,
> line-breaking, and font pipeline are Korean-specific. Docs are in Korean.

---

## 먼저, 안전에 관한 약속 3가지

이런 걸 처음 받아보시는 분들이 제일 먼저 걱정하시는 것부터 말씀드립니다.

1. **이 저장소는 아무것도 자동으로 실행하지 않습니다.** 설치 스크립트도, 백그라운드 프로그램도 없습니다.
   여러분이 직접 명령을 쳤을 때만 그 파일 하나가 돕니다.
2. **인터넷으로 아무것도 보내지 않습니다.** 계정도, 로그인도, 서버도 없습니다.
   딱 하나 예외가 `get_fonts.sh` 인데, 이건 **공개된 무료 폰트를 내려받기만** 합니다.
3. **여러분 컴퓨터의 파일을 뒤지지 않습니다.** 여러분이 명령에 직접 적어 준 영상·자막 파일만 읽고,
   결과는 지금 있는 폴더에만 만듭니다.

의심스러우면 파일을 열어 보세요. 전부 사람이 읽을 수 있는 파이썬 스크립트입니다.

---

## 5분 안에 첫 결과물

받아서 → 준비하고 → **여러분 맥에서 실제로 도는 걸 눈으로 확인**하는 데까지의 최단 경로입니다.

```bash
git clone https://github.com/ceokobec-hue/autoedit.git && cd autoedit
brew install ffmpeg-full && python3 -m venv ~/.autoedit/venv && ~/.autoedit/venv/bin/pip install fonttools numpy
bash auto-insert/scripts/mac/get_fonts.sh
python3 doctor.py                              # 전부 ✅ 면 준비 끝
bash examples/make_sample.sh                   # 시험용 영상 + 자막 만들기 → examples/
```

마지막 줄이 만든 샘플로 도구를 한 번 돌려 봅니다.

```bash
~/.autoedit/venv/bin/python auto-insert/scripts/mac/srt_tools.py sync examples/sample.srt examples/sample.mp4
```

**★ 모든 명령은 이 `autoedit` 폴더 안에서** 칩니다. 자세한 건 **[설치.md](설치.md)**,
샘플로 한 바퀴 도는 법은 `examples/README.md` 를 보세요.

---

## 뭘 하는 물건인가요

영상 편집에는 **"판단해야 하는 일"** 과 **"손만 바쁜 일"** 이 섞여 있습니다.
이 도구는 뒤쪽 — 손만 바쁜 일 — 만 가져갑니다. 판단은 그대로 사람이 합니다.

### 1. 오토멀티캠 (`auto-multicam/`) — 카메라 두 대를 하나로

카메라 두 대로 찍으면 늘 하는 일이 있습니다. 소리를 보면서 두 영상의 시작점을 맞추고,
칠판에 글씨 쓸 때 다른 카메라로 바꾸고, 중요한 대목에서 확대하고.

- 소리 파형을 대조해 **두 영상의 밀림(offset)을 자동으로 찾습니다**
- 강사를 지운 「맨 보드」를 만들어 **판서 중인 구간을 찾아냅니다**
- 자막 문장 단위로 **카메라 전환 후보**를 뽑습니다
- 🙋 **후보를 검토표(HTML) 한 장으로 내밀고, 사람이 체크해 승인합니다** ← 판정은 사람
- 승인된 것만 실제로 렌더합니다

> **컷 편집(불필요한 부분 삭제)은 하지 않습니다.** 이 도구가 만드는 건
> "이제 컷 편집을 시작할 수 있는 한 편"입니다.

### 2. 오토인서트 (`auto-insert/`) — 자막·인서트컷 얹기

컷 편집이 끝난 영상에 화면 장식을 얹는 단계입니다.

- **인물 옆 자막** — 맥 내장 얼굴 인식으로 화자 위치를 찾아 **빈 쪽에** 자막을 겁니다
- **인서트컷** — 설명 카드를 HTML로 만들어 화면에 덮습니다
- **OTS 카드 5종** — 자리의 밝기를 격자로 읽어 **흰 글씨가 읽히는 쪽**을 고릅니다
- **방송형 오버레이** — 채널 버그(로고 판)와 단원 소제목을 상시로 답니다
- 🙋 **검수 시트**를 먼저 뽑습니다. 전체를 렌더하기 전에 번호로 지적할 수 있습니다

---

## ⚠️ 미리 알고 계셔야 할 것

| | |
|---|---|
| **맥(Apple Silicon) 기준입니다** | M1 이상. 인텔 맥은 ffmpeg 경로만 바꾸면(`FFMPEG=` 환경변수) 대체로 됩니다 |
| **`brew install ffmpeg-full` 이 필수** | 그냥 `ffmpeg` 로는 **자막을 한 글자도 못 굽습니다.** 자세한 건 설치.md |
| **파이썬 3.9 이상** | 맥에 이미 깔려 있습니다. `python3 --version` 으로 확인 |
| **Google Chrome 이 필요합니다** | 카드·인서트컷 그림을 굽는 데 씁니다. 무료 — `brew install --cask google-chrome` |
| **폰트는 직접 받으셔야 합니다** | 8종의 라이선스가 제각각이라 한 저장소에 묶지 않았습니다. `get_fonts.sh` 가 받아 줍니다 → [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) |
| **자막(SRT)은 미리 있어야 합니다** | 없으면 `brew install whisper-cpp` 로 만듭니다. 설치.md 부록 참고 |
| **윈도우용 `.ps1` 은 참고용** | `auto-insert/scripts/*.ps1` 은 원래 윈도우판입니다. 맥에서는 안 돕니다 |
| **컷 편집 도구는 안 들어 있습니다** | 컷 편집 쪽은 윈도우 GPU 에서만 돌아서 뺐습니다 |
| **글자·카드 내용은 전부 예시입니다** | 어느 파일에도 실제 영상 내용이 들어 있지 않습니다. 예시를 지우고 본인 것으로 채워 쓰시면 됩니다 |
| **범퍼 영상 자산은 없습니다** | 만드는 방법(`references/bumper-set.md`)만 넣었습니다. 범퍼는 각자 시리즈 것을 만들어 쓰는 자산이라서요 |
| **인서트 제작 단계는 외부 도구가 필요** | HyperFrames(`npm i -g hyperframes`). 안 깔아도 나머지 단계는 전부 돕니다 |

---

## 폴더 구조

```
autoedit/
├── 설치.md                  ← 여기부터
├── 파일형식.md               입력 JSON 7종의 «어디에 뭘 적나» 표
├── doctor.py                 환경 점검 (제일 먼저 돌려 보세요)
├── examples/                 시험용 샘플 영상·자막·JSON — 먼저 여기서 한 바퀴
├── auto-multicam/            카메라 두 대 → 한 편
│   ├── SKILL.md              공정 설명 · 실행 명령 · 함정
│   └── scripts/mac/          파이썬 9개
├── auto-insert/              자막 · 인서트컷 · 오버레이
│   ├── SKILL.md
│   ├── references/           규격 문서 6종 (읽을 만합니다)
│   ├── assets/               인서트 엔진 HTML (예시 데이터)
│   └── scripts/mac/          파이썬 10개 + ots_v2/ 9개 + pipeline_v2/ 11개
└── .claude/skills/           AI 코딩 도구(Claude Code)가 이 폴더를 열었을 때 읽는 링크
```

`SKILL.md` 는 원래 AI 에이전트(Claude Code)에게 읽히려고 쓴 문서인데,
**사람이 읽어도 그대로 설명서**입니다. 실제로 터졌던 함정들이 표로 정리돼 있습니다.

### Claude Code 를 쓰신다면

이 저장소는 **AI 에이전트가 몰아 주면 제일 잘 도는 물건**입니다.
`CLAUDE.md` 와 `.claude/skills/` 가 이미 들어 있어서, 이 폴더를 열고
「**두 대로 찍었어, 붙여 줘**」라고 말하면 에이전트가 순서를 알아서 잡습니다.
승인 게이트(검토표·검수 시트)는 그대로 남으니 **판정은 여전히 사람이** 합니다.

---

## 안 되거나, 이상하거나, 궁금하면

[Issues](https://github.com/ceokobec-hue/autoedit/issues) 에 편하게 남겨 주세요.
개발자가 아니셔도 됩니다. **`python3 doctor.py` 결과를 그대로 붙여 주시면** 제일 빠릅니다.

보안 문제일 수 있는 것은 공개 이슈 말고 [SECURITY.md](SECURITY.md) 를 보세요.

---

## 만든 사람

**김지백** · 유튜브 [「모두의 AI교육」](https://www.youtube.com/@workai_lab)

제 강의 영상을 만들면서 필요해서 하나씩 붙인 도구들입니다.
「사람이 판단할 자리」와 「기계가 손만 놀릴 자리」를 나눠 보려던 실험이기도 합니다.
그래서 이 도구는 **끝까지 자동으로 가지 않습니다** — 중간에 반드시 사람이 보고 승인하는 자리가 있습니다.

만드는 과정과 왜 이렇게 나눴는지는 채널에서 이야기했습니다.

---

## 라이선스

**이 저장소의 코드**는 MIT 입니다. 마음대로 쓰시고, 고치시고, 나눠 주셔도 됩니다.
다만 **책임은 못 집니다.** 중요한 원본은 반드시 백업해 두고 쓰세요.

### 이 도구가 부르는 남의 것 (전부 이 저장소에 들어 있지 않고, 각자 받습니다)

| 무엇 | 라이선스 | 알아둘 것 |
|---|---|---|
| **GSAP** (인서트 엔진 애니메이션) | GreenSock Standard License | **MIT가 아닙니다.** 쓰는 건 무료·상업이용 가능하지만, **GSAP 파일을 여러분 제품에 넣어 재배포**하실 거면 <https://gsap.com/standard-license> 를 먼저 읽으세요 |
| **HyperFrames** (인서트 렌더) | Apache-2.0 | `npm i -g hyperframes` |
| **ffmpeg-full** | GPL-3.0-or-later | 별도 프로그램으로 부르기만 합니다. **여러분이 만든 영상에는 GPL이 붙지 않습니다** |
| **whisper.cpp** (받아쓰기) | MIT | `brew install whisper-cpp` |
| **자막·카드 폰트 8종** | 제각각 | [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) 참조 |
