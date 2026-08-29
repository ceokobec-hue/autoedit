# models — 얼굴 찾기 모델

여기 있는 `.onnx` 파일 2개는 **YuNet**이라는 얼굴 찾기 모델입니다.
윈도우·리눅스에서 「인물 옆 자막」·「OTS 카드 자리 찾기」를 쓸 때 필요합니다.

| 파일 | 크기 | 무엇 |
|---|---|---|
| `face_detection_yunet_2023mar.onnx` | 232KB | 입력 크기가 **고정**된 원본 — OpenCV **4.x** 용 |
| `face_detection_yunet_2026may.onnx` | 230KB | 같은 모델을 **크기 자유**로 다시 내보낸 것 — OpenCV **5.x** 용 |
| `YuNet-LICENSE.txt` | 1KB | MIT 라이선스 전문 |

> **맥에서는 이 폴더가 필요 없습니다.** 맥은 애플이 운영체제에 넣어 준 Vision 을 씁니다
> (`auto-insert/scripts/mac/speaker_box.swift`). 이 폴더는 그게 없는 컴퓨터를 위한 것입니다.

---

## ⚠️ 파일을 지우지 마세요 — 지우면 «에러 없이» 얼굴을 못 찾습니다

「하나면 되겠지」 하고 하나를 지우면, 버전이 안 맞는 쪽만 남았을 때
**아무 말도 없이 얼굴 0개**가 나옵니다. 그러면 자막이 엉뚱한 자리에 붙습니다.

`detect_opencv.py` 가 `cv2.__version__` 을 보고 알아서 고릅니다. 그냥 두세요.

**왜 두 개가 필요합니까?**
OpenCV 5 부터 ONNX 를 읽는 엔진이 바뀌었고, 새 엔진은 「입력 크기가 자유로운」 모델을 요구합니다.
2023mar 은 크기가 고정돼 있어 그 엔진에서 문제가 생길 수 있습니다.
근거는 만든 쪽 문서 「Notes」입니다 —
<https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet>

---

## 파일이 깨졌는지 확인하기

내려받다 만 파일은 **132바이트짜리 «주소만 적힌 쪽지»** 인 경우가 있습니다
(GitHub 이 큰 파일을 따로 보관하는 방식 때문입니다). 크기부터 보세요.

```bash
# 맥·리눅스
ls -l models/*.onnx        # 각각 23만 바이트쯤이면 정상. 132바이트면 «쪽지»입니다
shasum -a 256 models/*.onnx
```

```powershell
# 윈도우
dir models\*.onnx
certutil -hashfile models\face_detection_yunet_2023mar.onnx SHA256
```

정상 값:

```
8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4  face_detection_yunet_2023mar.onnx
ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0  face_detection_yunet_2026may.onnx
```

다른 곳에 두고 쓰시려면 환경변수로 알려 주세요.

```bash
export AUTOEDIT_YUNET_MODEL=/어디/face_detection_yunet_2023mar.onnx   # 파일 하나를 콕 집기
export AUTOEDIT_MODELS=/어디/models                                   # 폴더째 옮겼을 때
```

---

## 라이선스

**MIT** · Copyright (c) 2020 Shiqi Yu — 전문은 `YuNet-LICENSE.txt`.
MIT 는 「저작권 표시와 라이선스 전문을 같이 넣으면」 자유롭게 쓰고 나눠 줄 수 있습니다.
그래서 이 저장소는 전문을 옆에 두고 파일을 동봉했습니다.
근거와 출처는 저장소 뿌리의 `THIRD-PARTY-NOTICES.md` 를 보세요.
