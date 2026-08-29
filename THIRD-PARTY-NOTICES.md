# 이 도구가 쓰는 남의 것

이 저장소에 **실제로 들어 있는 남의 것은 딱 하나**입니다 — `models/` 폴더의 **YuNet 얼굴 찾기 모델**
(232KB 짜리 `.onnx` 파일 2개, MIT). 아래 「저장소에 동봉한 것」에 따로 적어 두었습니다.
그 밖의 것은 **전부 여러분이 각자 받으시는 것**입니다. 저작권은 각 권리자에게 있습니다.

이 문서가 있는 이유는 하나입니다 — `get_fonts.sh` 가 「전부 무료·상업이용 가능」이라고
말하고 있으니, **그 말의 근거를 어디서 확인할 수 있는지**도 함께 드려야 하기 때문입니다.

---

## 자막·카드 폰트 (`get_fonts.sh` 가 받는 것)

| 폰트 | 만든 곳 | 라이선스 | 공식 페이지 |
|---|---|---|---|
| Pretendard | 길형진(orioncactus) | SIL OFL 1.1 | <https://github.com/orioncactus/pretendard> |
| Gothic A1 | Hanyang I&C | SIL OFL 1.1 | <https://fonts.google.com/specimen/Gothic+A1> |
| Gasoek One | Google Fonts | SIL OFL 1.1 | <https://fonts.google.com> |
| Bagel Fat One | Google Fonts | SIL OFL 1.1 | <https://fonts.google.com> |
| 나눔스퀘어 네오 | 네이버 | 네이버 나눔글꼴 라이선스 | <https://hangeul.naver.com/font> |
| 여기어때 잘난체 2 · 잘난체 고딕 | 여기어때컴퍼니 | 자체 라이선스 | <https://gccompany.co.kr/font> |
| 에스코어 드림 | 에스코어 | 자체 라이선스 | <https://s-core.co.kr/company/font/> |

**자동으로 못 받는 2종** — 공식 페이지가 동의 절차를 거치게 돼 있어 직접 받으셔야 합니다.

| 폰트 | 만든 곳 | 공식 페이지 |
|---|---|---|
| 배민 도현 | 우아한형제들 | <https://www.woowahan.com/fonts> |
| G마켓 산스 | 지마켓 | <https://company.gmarket.co.kr> |

### 세 줄 요약

1. **영상에 구워 쓰는 것**은 위 전부 **무료·상업 이용 가능**합니다
   (2026-08-29 각 공식 페이지에서 확인).
2. **폰트 파일 자체를 남에게 넘기실 거면** 조건이 갈립니다.
   SIL OFL 넷은 자유롭게 재배포할 수 있습니다(단독 판매만 금지).
   국내 기업 글꼴들은 대개 **저작권 표시와 라이선스 전문을 함께 넣는 조건**이고,
   **수정본 재배포와 폰트 자체의 판매는 금지**입니다. 위 공식 페이지를 먼저 읽으세요.
3. 그래서 `get_fonts.sh` 는 폰트와 함께 **각 라이선스 전문을 `licenses/` 폴더에 받아 둡니다.**
   폴더째 옮기시면 조건이 같이 따라갑니다.

> ⚠️ **여기 적힌 내용은 법률 자문이 아닙니다.** 회사 일로 쓰시거나 재배포하실 거면
> 그때는 반드시 위 공식 페이지의 원문을 직접 확인하세요. 조건은 바뀔 수 있습니다.

---

## 소프트웨어

| 무엇 | 라이선스 | 이 도구가 어떻게 씁니까 |
|---|---|---|
| **ffmpeg-full** | GPL-3.0-or-later | 별도 프로그램으로 **실행만** 합니다(코드로 링크하지 않습니다). 그래서 **여러분이 만든 영상에는 GPL이 붙지 않습니다** |
| **whisper.cpp** (`whisper-cli`) | MIT | 받아쓰기. 별도 프로그램으로 실행 |
| **GSAP** 3.14.2 | GreenSock Standard License (**OSI 승인 오픈소스가 아님**) | 인서트 엔진 HTML 이 CDN 으로 불러옵니다. 파일을 동봉하지 않습니다 |
| **HyperFrames** | Apache-2.0 | 인서트컷 렌더. `npm i -g hyperframes` 로 각자 설치 |
| **fontTools** | MIT | 글자 폭 실측. `pip install fonttools` |
| **numpy** | BSD-3-Clause | 파형·밝기 계산. `pip install numpy` |
| **opencv-python** | Apache-2.0 | **윈도우·리눅스에서만** 얼굴·사람·글자 찾기. **선택 사항**이라 저장소에 없고 `pip install opencv-python` 로 각자 설치합니다. 맥은 안 깔아도 됩니다(애플 Vision 을 씁니다) |
| **Google Chrome** | Google 서비스 약관 | 카드 HTML 을 PNG 로 굽습니다. 화면 없이(헤드리스) 실행만 합니다 |

### GSAP 만 따로 한 번 더

`auto-insert/assets/index-template.html` 과 `insert-engine.html` 이 GSAP 을 씁니다.
**이 저장소는 GSAP 파일을 동봉하지 않고 CDN 주소만 적어 두므로 문제가 없습니다.**

주의하실 건 **여러분이 다시 나눠 주실 때**입니다.
이 저장소의 코드는 MIT 라 마음대로 나눠 주셔도 되지만,
`insert-engine.html` 옆에 **`gsap.min.js` 파일을 같이 넣어 배포**하시면
그건 MIT 가 아닌 남의 라이선스를 재배포하는 것이 됩니다.
그러실 거면 <https://gsap.com/standard-license> 를 먼저 읽으세요.

---

## 저장소에 동봉한 것 — YuNet 얼굴 찾기 모델

| 무엇 | 만든 곳 | 라이선스 | 공식 페이지 |
|---|---|---|---|
| **YuNet** (`face_detection_yunet_*.onnx`) | Shiqi Yu 외 | **MIT** | <https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet> |

`models/` 폴더에 **파일 자체가 들어 있습니다.** 라이선스 전문은 같은 폴더 `models/YuNet-LICENSE.txt` 입니다.

**왜 폰트와 다르게 동봉했나요?**
폰트는 8종의 재배포 조건이 제각각이라 한 저장소에서 다 지키기 어려워 `get_fonts.sh` 로 각자 받게 했습니다.
YuNet 은 **MIT** 라 조건이 하나뿐입니다 — 「저작권 표시와 라이선스 전문을 같이 넣을 것」.
그래서 전문을 같이 넣고 동봉했습니다. 이렇게 하면 **윈도우에서 받자마자 바로 돕니다**
(인터넷으로 뭘 더 받지 않습니다 — 이 저장소의 약속입니다).

**왜 파일이 2개인가요?** 같은 모델의 «내보내기 방식»이 둘이고, OpenCV 버전에 따라 되는 쪽이 다릅니다.

| 파일 | 언제 쓰나 |
|---|---|
| `face_detection_yunet_2023mar.onnx` | 입력 크기가 **고정**된 원본. OpenCV **4.x** 용 |
| `face_detection_yunet_2026may.onnx` | 같은 모델을 **크기 자유**로 다시 내보낸 것. OpenCV **5.x** 의 새 엔진이 이 형태를 요구합니다 |

`detect_opencv.py` 가 `cv2.__version__` 을 보고 알아서 고릅니다. 지우지 마세요 —
버전이 안 맞는 쪽만 남으면 **에러 메시지 없이 얼굴을 0개**로 잡을 수 있습니다.
근거: <https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet> 의 README 「Notes」.

---

## 확인 방법

직접 확인해 보고 싶으시면:

```bash
npm view gsap@3.14.2 license          # → Standard 'no charge' license
npm view hyperframes license          # → Apache-2.0
npm view pretendard@1.3.9 license     # → OFL-1.1
brew info ffmpeg-full                 # → GPL-3.0-or-later
brew info whisper-cpp                 # → MIT

# 이 저장소에 폰트 파일이 정말 하나도 없는지
git ls-files | grep -E '\.(ttf|otf|woff2)$'    # → 아무것도 안 나와야 정상

# 동봉한 바이너리가 YuNet 모델 2개뿐인지 (그 밖의 «정체 모를 파일»이 없는지)
git ls-files | grep -E '\.(onnx|bin|dll|so|dylib|exe)$'
#   → models/face_detection_yunet_2023mar.onnx
#     models/face_detection_yunet_2026may.onnx   이 둘만 나와야 정상

pip show opencv-python | grep -i license      # → Apache 2.0
```
