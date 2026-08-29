#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""detect_opencv.py — 맥이 아닌 곳(윈도우·리눅스)에서 «사람·얼굴·글자»를 찾는다.

맥에는 애플 Vision 이 들어 있어 `speaker_box.swift` 한 줄이면 끝난다.
윈도우에는 그게 없다. 그래서 OpenCV 로 «같은 모양의 답»을 만든다.

★ 이 파일의 목표는 «Vision 을 이기는 것»이 아니라 «Vision 과 똑같은 칸의 답을 내는 것»이다.
  나가는 JSON 이 speaker_box.swift 와 한 칸이라도 다르면
  이걸 받아 쓰는 세 스크립트가 «에러 없이» 엉뚱한 자리에 카드를 붙인다.
  스키마는 detector.py 맨 위 설명을 보라.

세 가지를 각각 어떻게 하는지 — 정직하게

  ① 얼굴  : YuNet (models/face_detection_yunet_*.onnx). Vision 과 거의 같다. 실측 중심점 차이 2px.
  ② 사람  : ⚠️ 진짜 검출이 아니다. «얼굴에서 몸을 어림잡는다». 아래 estimate_person() 주석 참고.
  ③ 글자  : ⚠️ 글자를 «읽지» 않는다. 글자처럼 생긴 «덩어리»를 찾을 뿐이다. text_boxes() 주석 참고.

⛔ 좌표계
  Vision 은 [0,1] 정규화 + 원점이 «왼쪽 아래»라서 speaker_box.swift 가 뒤집어 내보낸다.
  OpenCV 는 처음부터 «픽셀 + 왼쪽 위»다. 그래서 여기서는 뒤집지 않는다.
  뒤집으면 카드가 위아래 반대 자리에 붙는다 — 에러는 안 난다.
"""
import math
import os
import sys

# ── 저장소 뿌리 찾기 (ff_path.py 가 있는 곳). models/ 폴더가 거기 있다 ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
MODEL_DIR = os.environ.get('AUTOEDIT_MODELS') or os.path.join(_R, 'models')

# YuNet 모델 두 개를 넣어 둔 이유 — 넣지 않으면 OpenCV 5 에서 조용히 실패한다
#   2023mar : 입력 크기가 «고정»된 원본. OpenCV 4.x 용.
#   2026may : 같은 모델을 «크기 자유»로 다시 내보낸 것. OpenCV 5.x 의 새 엔진이 이걸 요구한다.
# (근거: opencv_zoo/models/face_detection_yunet/README.md)
MODEL_V4 = 'face_detection_yunet_2023mar.onnx'
MODEL_V5 = 'face_detection_yunet_2026may.onnx'

MIN_CV = (4, 7, 0)          # FaceDetectorYN 자체는 4.5.4 부터지만 2023mar 모델은 4.7 부터다

# ── 얼굴에서 몸을 어림잡는 비율 (estimate_person 참고) ──
# ⛔ 이 숫자는 «YuNet 얼굴 상자» 기준이다. Vision 얼굴 상자로 재서 여기에 넣으면 안 된다.
#    같은 얼굴을 Vision 은 550px 폭, YuNet 은 430px 폭으로 잡는다(YuNet 이 22% 좁다).
#    처음에 Vision 기준 3.7 을 그대로 넣었더니 사람 상자가 200~580px 좁게 나왔다 — 에러는 없었다.
BODY_W_PER_FACE_W = 4.6     # 몸통+팔 가로폭 ÷ YuNet 얼굴 가로폭 (실측 중앙값 4.65, 범위 4.07~4.97)
HEAD_TOP_PER_FACE_H = 0.16  # 얼굴 상자 위 «정수리» 몫 ÷ YuNet 얼굴 세로 (실측 중앙값 0.16)

_det = None                 # YuNet 은 한 번만 만든다(매번 만들면 프레임당 0.1초가 더 든다)
_det_size = None


# ────────────────────────────────────────────────────────────────
# 부품 준비
# ────────────────────────────────────────────────────────────────
def _die(msg):
    """⛔ 스택트레이스 대신 «한국어 한 줄 + 어떻게 고치는지»로 죽는다 (ff_path.require 와 같은 규칙)."""
    sys.exit(msg)


def load_cv2():
    """OpenCV 를 «필요한 순간에만» 불러온다.

    ⛔ 파일 맨 위에서 import 하면 맥 사용자도 opencv 를 깔아야 한다.
       맥은 Swift 통로로 가므로 opencv 가 «없어도» 지금처럼 다 돌아야 한다 — 그래서 지연 import 다.
    """
    try:
        import cv2
    except ModuleNotFoundError:
        _die('⛔ opencv-python 이 없습니다 (얼굴·사람 찾기).\n'
             '   맥에서는 애플 Vision(swift)을 쓰지만, 이 컴퓨터에는 그 통로가 없어 OpenCV 가 필요합니다.\n\n'
             '   설치:\n'
             '     pip install opencv-python\n'
             '   («작은 방» 파이썬을 쓰신다면)\n'
             '     python -m pip install opencv-python\n\n'
             '   지금 상태 확인:  python3 doctor.py')
    try:
        ver = tuple(int(x) for x in cv2.__version__.split('.')[:3])
    except ValueError:
        ver = (0, 0, 0)
    if ver < MIN_CV:
        _die('⛔ opencv-python 이 너무 낮습니다 — 지금 %s, 필요 %s 이상.\n'
             '   얼굴 찾기(FaceDetectorYN)가 그 아래 버전에는 아예 없습니다.\n\n'
             '   올리기:\n'
             '     pip install --upgrade opencv-python'
             % (cv2.__version__, '.'.join(str(v) for v in MIN_CV)))
    if not hasattr(cv2, 'FaceDetectorYN'):
        _die('⛔ 이 opencv 에는 얼굴 찾기(FaceDetectorYN)가 없습니다 — %s.\n'
             '   opencv-python-headless 대신 opencv-python 을 쓰셨는지 확인하세요.\n'
             '     pip install --upgrade --force-reinstall opencv-python' % cv2.__version__)
    return cv2


def model_path(cv2):
    """이 opencv 버전에 맞는 YuNet 모델 파일 경로. 없으면 한국어로 죽는다."""
    env = os.environ.get('AUTOEDIT_YUNET_MODEL')
    if env:
        if not os.path.exists(env):
            _die('⛔ AUTOEDIT_YUNET_MODEL 로 지정하신 파일이 없습니다:\n  %s' % env)
        return env
    major = int(cv2.__version__.split('.')[0])
    order = [MODEL_V5, MODEL_V4] if major >= 5 else [MODEL_V4, MODEL_V5]
    for name in order:
        p = os.path.join(MODEL_DIR, name)
        if os.path.exists(p):
            return p
    _die('⛔ 얼굴 찾기 모델 파일이 없습니다.\n'
         '   찾은 곳: %s\n'
         '   있어야 할 파일: %s\n\n'
         '   저장소를 통째로 내려받으셨다면 원래 들어 있습니다.\n'
         '   일부만 복사하셨다면 models/ 폴더도 같이 가져오세요.\n'
         '   다른 곳에 두셨다면:  set AUTOEDIT_YUNET_MODEL=<onnx 파일 경로>'
         % (MODEL_DIR, ' 또는 '.join(order)))


def detector(cv2, w, h):
    """YuNet 을 한 번만 만들고 크기만 바꿔 쓴다."""
    global _det, _det_size
    if _det is None:
        p = model_path(cv2)
        try:
            _det = cv2.FaceDetectorYN.create(p, '', (320, 320), 0.6, 0.3, 5000)
        except Exception as e:
            _die('⛔ 얼굴 찾기 모델을 열지 못했습니다:\n  %s\n  %s\n\n'
                 '   파일이 깨졌을 수 있습니다. 저장소를 다시 내려받아 보세요.\n'
                 '   (git-lfs 없이 받으면 132바이트짜리 «가짜 파일»이 됩니다 — 크기를 확인해 보세요)'
                 % (p, str(e)[:200]))
    if _det_size != (w, h):
        _det.setInputSize((w, h))
        _det_size = (w, h)
    return _det


def imread_any(cv2, path):
    """한글·공백이 든 경로에서도 이미지를 연다.

    ⛔ 윈도우에서 cv2.imread('C:/영상/프레임.png') 는 «에러 없이 None» 을 돌려준다.
       (OpenCV 가 경로를 ANSI 로 넘겨서 한글이 깨진다)
       그래서 파이썬이 파일을 읽고, OpenCV 에는 «바이트»만 넘긴다.
    """
    import numpy as np
    try:
        buf = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


# ────────────────────────────────────────────────────────────────
# 숫자 모양 맞추기 — speaker_box.swift 와 똑같이
# ────────────────────────────────────────────────────────────────
def r1(v):
    """소수 첫째 자리까지. swift 의 (x*10).rounded()/10 과 같게 «반올림은 0에서 멀어지는 쪽»."""
    return math.copysign(math.floor(abs(float(v)) * 10 + 0.5), v) / 10


def whole(v):
    """딱 떨어지는 값은 «정수»로 만든다.

    ⚠️ swift 쪽 JSON 은 260.0 을 «260» 으로 적는다(Swift 의 JSON 만드는 방식이 그렇다).
       파이썬은 그냥 두면 «260.0» 으로 적는다. 계산 결과는 같지만 두 파일을 나란히 비교하면
       «전부 다르다»고 나와서, 진짜 다른 곳을 찾을 수 없게 된다. 그래서 모양을 맞춘다.
    """
    return int(v) if float(v) == int(v) else v


def box(x, y, w, h, conf):
    """speaker_box.swift 의 struct Box 와 «같은 칸·같은 자리수».

    ⛔ text 칸은 일부러 넣지 않는다. swift 도 값이 없으면 그 칸을 아예 안 내보낸다
       (Swift Codable 이 nil 을 encodeIfPresent 로 건너뛴다). 여기서 null 을 넣으면 모양이 달라진다.
    """
    return {'x': whole(r1(x)), 'y': whole(r1(y)), 'w': whole(r1(w)), 'h': whole(r1(h)),
            'conf': whole(round(float(conf), 3))}


# ────────────────────────────────────────────────────────────────
# ① 얼굴 — YuNet
# ────────────────────────────────────────────────────────────────
def faces_of(cv2, img):
    H, W = img.shape[:2]
    d = detector(cv2, W, H)
    ok, res = d.detect(img)
    out = []
    if res is None:
        return out
    for f in res:
        x, y, w, h = (float(v) for v in f[:4])
        # ⚠️ YuNet 은 화면 밖으로 삐져나온 상자를 그대로 돌려준다. Vision 은 화면 안으로 잘라 준다.
        #    맞춰 두지 않으면 «음수 x» 가 그대로 흘러가 자리 계산이 틀어진다.
        x0, y0 = max(0.0, x), max(0.0, y)
        x1, y1 = min(float(W), x + w), min(float(H), y + h)
        if x1 <= x0 or y1 <= y0:
            continue
        out.append(box(x0, y0, x1 - x0, y1 - y0, f[-1]))
    out.sort(key=lambda b: -b['conf'])
    return out


# ────────────────────────────────────────────────────────────────
# ② 사람 — ⚠️ 검출이 아니라 «어림»이다
# ────────────────────────────────────────────────────────────────
def estimate_person(f, W, H):
    """얼굴 상자 하나에서 «사람 상자»를 어림잡는다.

    왜 진짜 사람 검출을 안 했나 — 세 가지를 재 보고 내린 판단이다.
      · HOG(cv2.HOGDescriptor) : 서 있는 «전신 보행자»용이다. 강의·브이로그처럼 상반신만 잡히는
        화면에서는 아예 0개가 나온다. 느리기까지 하다. → 못 쓴다.
      · YOLO 같은 사람 검출 모델 : 잘 되지만 파일이 7MB 넘는다. 이 저장소는 «받으면 바로 도는 것»이
        원칙이라 무거운 모델을 하나 더 넣기 어렵다.
      · 얼굴에서 어림잡기 : 이걸 골랐다. 아래 쓰임새를 보면 «얼굴만 알아도 되는» 일이었다.

    이 값을 쓰는 곳이 실제로 무엇을 보는가 (그래서 어림으로 충분한가)
      · place_captions.py : 사람 «가운데 x» → 자막을 왼쪽에 둘지 오른쪽에 둘지
      · ots_place.py      : 사람 «왼쪽 끝·오른쪽 끝» → 카드 놓을 빈 폭
      · pipeline_v2/place.py : 사람 안 씀(얼굴만)
    세로 위치는 아무도 안 본다. 그래서 «가로»만 맞으면 된다.

    비율의 근거
      · 가로 4.6배 — 어깨너비는 머리너비의 2.2~2.5배(인체 계측)이고, Vision 의 사람 상자는
        거기에 팔까지 넣어 더 넓다. ★그리고 YuNet 얼굴 상자가 Vision 것보다 좁아 배수가 커진다.
        같은 프레임 8장에서 «Vision 사람폭 ÷ YuNet 얼굴폭» = 4.07~4.97(중앙값 4.65)였다.
      · 위로 0.16배 — 얼굴 상자는 «정수리»를 안 넣는다. 같은 방식 실측 중앙값 0.16.
      · 아래는 «화면 바닥까지». 실측 10프레임 전부 Vision 의 사람 상자 아랫변이 화면 바닥이었다
        (사람은 화면 밖으로 이어진다). 재는 법은 models/README.md 에 적어 뒀다.

    ⚠️ 남는 차이 — 정직하게
      Vision 의 사람 상자는 팔을 뻗은 쪽으로 «치우친다» — 중심이 얼굴 중심에서 −0.20~+0.50
      얼굴폭만큼 옮겨간다(실측 8장). 부호가 왔다갔다 하니 «그 사람이 그때 팔을 어디 뒀나»이지
      사람 몸의 성질이 아니다. 한 영상에 맞춰 보정하면 다른 영상에서 더 틀린다.
      그래서 여기서는 «얼굴 중심 = 사람 중심»으로 둔다.
      ⚠️ 그 결과 화자가 화면 한가운데 서 있으면 자막을 왼쪽에 둘지 오른쪽에 둘지가 Vision 과
         갈릴 수 있다. 판정선(화면 정중앙)에 걸친 경우라 어느 쪽도 «틀린» 답은 아니다.
    """
    fcx = f['x'] + f['w'] / 2
    w = f['w'] * BODY_W_PER_FACE_W
    x0 = max(0.0, fcx - w / 2)
    x1 = min(float(W), fcx + w / 2)
    y0 = max(0.0, f['y'] - f['h'] * HEAD_TOP_PER_FACE_H)
    return box(x0, y0, x1 - x0, float(H) - y0, f['conf'])


# ────────────────────────────────────────────────────────────────
# ③ 글자 — ⚠️ 읽지 않는다. «글자처럼 생긴 줄»을 찾을 뿐이다
# ────────────────────────────────────────────────────────────────
TEXT_PAD = 0.10        # 찾은 상자를 위아래로 10% 부풀린다(아래 «안전한 쪽» 설명)
TEXT_MIN_W_RATIO = 0.035  # 화면 폭의 3.5% 보다 좁은 «줄»은 버린다 (아래 근거)


def text_boxes(cv2, img):
    """화면에 «구워진 글자»가 있을 만한 줄을 찾는다.

    ⛔ OCR 이 아니다. 글자를 읽지 못하므로 결과에 text 칸이 없다.
       Vision 은 «이게 한국어 글자인가»를 알지만, 여기서는 «글자처럼 생겼나»만 본다.

    이 값을 쓰는 곳
      · 아래쪽(화면 58% 밑) 글자 → 이미 구워진 자막 띠 → 인서트가 침범하면 안 되는 «금지선»
      · 위쪽 글자 → 슬라이드·판서 영역 → 카드가 가리면 안 되는 곳

    어떻게 찾나 (한 줄 설명)
      ① 밝기의 «가장자리»를 뽑는다(모폴로지 그라디언트) → 글자 획만 하얗게 남는다
      ② 하얀 덩어리를 낱낱이 센다 → 글자 한 자 한 자가 덩어리가 된다
      ③ «같은 높이 + 같은 밑줄 + 옆으로 나란히» 인 덩어리들만 한 줄로 묶는다

    ★ ③번이 핵심이다. 얼굴·옷·배경도 ①②를 통과하지만, 그것들은 «밑줄이 맞지» 않는다.
      이 조건을 빼면 사람 얼굴 위에 «글자 있음»이 마구 잡힌다(실측: 한 프레임에 39개 → 11개로 줄었다).

    ⚠️ Vision 보다 부정확하다 — 실측으로 확인된 것
      · 작고 흐린 글자(화면 구석 채널 이름 등)를 놓친다.
      · 사람 옷·머리카락 무늬를 글자로 오인하는 일이 남아 있다.
      · 다만 오인은 «금지선이 더 위로 올라가는» 쪽이라 인서트가 자막을 덮는 사고로는 잘 안 간다.
        (금지선이 실제보다 아래로 내려가는 쪽이 위험한데, 그건 «놓쳤을 때»고
         그때는 부르는 쪽이 「자막을 못 찾았다」고 경고를 띄운다.)
    """
    import numpy as np
    import statistics as st
    H, W = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    grad = cv2.morphologyEx(g, cv2.MORPH_GRADIENT,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(bw, 8)

    hmin, hmax = H * 0.010, H * 0.16
    comps = []
    for i in range(1, n):
        x, y, w, h, a = (int(v) for v in stats[i])
        if h < hmin or h > hmax:      continue   # 너무 작은 티끌·너무 큰 물체
        if w > h * 2.2 or w < h * 0.10: continue # 가로로 긴 것 = 밑줄·판 테두리, 세로로 긴 것 = 기둥
        fill = a / float(w * h)
        if fill < 0.06 or fill > 0.95: continue  # 속이 텅 비었거나 꽉 찬 네모 = 글자가 아니다
        comps.append((x, y, w, h))
    comps.sort(key=lambda c: (c[1], c[0]))

    used = [False] * len(comps)
    lines = []
    for i, c in enumerate(comps):
        if used[i]:
            continue
        used[i] = True
        members = [c]
        gx0, gy0, gx1, gy1 = c[0], c[1], c[0] + c[2], c[1] + c[3]
        grew = True
        while grew:                      # 옆으로 붙는 덩어리가 없어질 때까지 키운다
            grew = False
            gh = gy1 - gy0
            for j, d in enumerate(comps):
                if used[j]:
                    continue
                dy0, dy1 = d[1], d[1] + d[3]
                if min(gy1, dy1) - max(gy0, dy0) < 0.55 * min(gh, d[3]):
                    continue             # 세로로 안 겹치면 다른 줄이다
                if not (0.5 <= d[3] / float(gh) <= 2.0):
                    continue             # 글자 키가 너무 다르면 다른 것이다
                if max(gx0 - (d[0] + d[2]), d[0] - gx1) > 1.0 * gh:
                    continue             # 한 글자 높이보다 멀면 다른 낱말이다
                used[j] = True
                members.append(d)
                gx0 = min(gx0, d[0]); gy0 = min(gy0, d[1])
                gx1 = max(gx1, d[0] + d[2]); gy1 = max(gy1, d[1] + d[3])
                grew = True
        if len(members) < 3:
            continue
        hs = [m[3] for m in members]
        bots = [m[1] + m[3] for m in members]
        mh = st.median(hs)
        if max(hs) / float(min(hs)) > 2.2:   continue  # 키가 들쭉날쭉 = 무늬
        if st.pstdev(hs) / mh > 0.35:        continue
        if st.pstdev(bots) > 0.30 * mh:      continue  # ★ 밑줄이 안 맞으면 글자가 아니다
        w, h = gx1 - gx0, gy1 - gy0
        if h > 1.8 * mh:  continue           # 한 줄인데 글자 키의 두 배 = 세로로 뭉친 무늬
        if w < 2.0 * h:   continue           # 너무 짧은 것은 버린다(두 글자 이하 라벨은 놓친다)
        # ★ 손톱만 한 «줄»은 버린다. 배경(창밖 간판·주차된 차)이 글자처럼 잡히는 게 여기서 걸린다.
        #   실측: 진짜 글자 중 제일 좁은 것이 화면폭의 4.2%, 헛것 둘은 1.8%·3.2% 였다.
        #   ⚠️ 헛것 하나가 금지선을 1181px → 853px 로 끌어올렸다. 안전한 쪽이긴 해도
        #      인서트를 얹을 자리를 328px 이나 잡아먹는다.
        if w < W * TEXT_MIN_W_RATIO:
            continue
        # 획만 잡아서 Vision 보다 상자가 작다 → 위아래로 조금 부풀려 «안전한 쪽»에 둔다
        pad = h * TEXT_PAD
        y0 = max(0.0, gy0 - pad)
        y1 = min(float(H), gy1 + pad)
        lines.append(box(gx0, y0, w, y1 - y0, 0.5))
    lines.sort(key=lambda b: (b['y'], b['x']))
    return lines


# ────────────────────────────────────────────────────────────────
# 한 장 분석 — speaker_box.swift 의 analyze() 와 같은 자리
# ────────────────────────────────────────────────────────────────
def analyze(path, want_text=True):
    cv2 = load_cv2()
    img = imread_any(cv2, path)
    if img is None:
        # ★ 문구까지 swift 와 같게 맞춘다. 부르는 쪽이 이 글자를 보고 판단할 수 있어야 한다.
        return {'image': path, 'width': 0, 'height': 0,
                'persons': [], 'faces': [], 'texts': [], 'error': '이미지를 열 수 없음'}
    H, W = img.shape[:2]
    try:
        faces = faces_of(cv2, img)
        persons = [estimate_person(f, W, H) for f in faces]
        texts = text_boxes(cv2, img) if want_text else []
    except Exception as e:
        return {'image': path, 'width': W, 'height': H,
                'persons': [], 'faces': [], 'texts': [], 'error': str(e)}
    persons.sort(key=lambda b: -b['conf'])
    return {'image': path, 'width': W, 'height': H,
            'persons': persons, 'faces': faces, 'texts': texts}


def analyze_all(paths, want_text=True):
    return [analyze(p, want_text) for p in paths]
