#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""detector.py — 프레임에서 «사람·얼굴·글자»를 찾는 통로를 «한 곳에서» 고른다.

왜 필요한가
  얼굴 찾기를 부르는 곳이 세 군데 있고, 셋 다 `swift speaker_box.swift` 를 직접 불렀다.
  swift 는 맥에만 있다. 윈도우에서는 세 곳이 전부 같은 자리에서 멈춘다.
  통로 고르기를 여기 한 곳에 모아 두면 «어디는 되고 어디는 안 되는» 상태가 안 생긴다
  (ff_path.py 가 ffmpeg 경로에 대해 하는 일과 같다).

고르는 순서
  ① 환경변수 AUTOEDIT_DETECTOR = swift | opencv   (직접 지정한 것이 언제나 이긴다)
  ② 맥 + swift 있음 + speaker_box.swift 있음      → swift  (★맥 기본값. 지금까지와 완전히 같다)
  ③ 그 밖                                          → opencv (윈도우·리눅스)

⛔ 맥에서는 지금까지 하던 대로 애플 Vision(swift)을 쓴다.
   OpenCV 가 더 좋아서 바꾼 게 아니라, 윈도우에 Vision 이 «없어서» 옆길을 낸 것이다.
   Vision 이 더 정확하다 — 특히 글자 읽기는 비교가 안 된다.

⚠️ ②에서 「맥인가」를 왜 같이 보나
   윈도우에도 Swift 를 깔 수 있다. 그런데 Vision 프레임워크는 애플 것이라 없다.
   `swift 가 있다`만 보고 골랐다가는 윈도우에서 «import Vision 실패»로 죽는다.

─────────────────────────────────────────────────────────────────
나가는 JSON (두 통로가 «완전히 같아야» 한다 — 이 파일이 지키는 약속)

  [ { "image":  "넘긴 파일 경로 그대로",
      "width":  2560, "height": 1440,          ← 정수(픽셀)
      "persons":[ {"x":284.2,"y":98.9,"w":2056.8,"h":1347.4,"conf":0.657}, ... ],
      "faces":  [ {...같은 칸...} ],
      "texts":  [ {...같은 칸..., "text":"읽은 글자"} ],
      "error":  "…"                            ← 실패했을 때만 있는 칸
  }, ... ]

  · 좌표는 «픽셀», 원점은 «화면 왼쪽 위». 정규화 아님.
    (Vision 원본은 0~1 정규화 + 왼쪽 «아래»가 원점이라 speaker_box.swift 가 뒤집어 준다.
     OpenCV 는 처음부터 왼쪽 위 픽셀이라 뒤집지 않는다. 여기를 틀리면 카드가 위아래 반대로 붙는다.)
  · x·y·w·h 는 소수 첫째 자리, conf 는 소수 셋째 자리.
  · persons·faces 는 conf 큰 순으로 정렬돼 있다.
  · text 칸은 «읽은 글자가 있을 때만» 나온다. OpenCV 통로에는 글자 읽기가 없어 늘 없다.

혼자 돌려 보기
  python3 detector.py 프레임.png                  ← 지금 통로로
  AUTOEDIT_DETECTOR=opencv python3 detector.py 프레임.png
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SWIFT = os.path.join(HERE, 'speaker_box.swift')

_notified = False           # 안내는 한 번만 (프레임마다 찍으면 로그가 안 읽힌다)


def which():
    """지금 쓸 통로 이름 — 'swift' 또는 'opencv'."""
    env = (os.environ.get('AUTOEDIT_DETECTOR') or '').strip().lower()
    if env in ('swift', 'vision'):
        return 'swift'
    if env in ('opencv', 'cv2'):
        return 'opencv'
    if env:
        sys.exit('⛔ AUTOEDIT_DETECTOR 값이 «%s» 입니다. swift 또는 opencv 만 됩니다.\n'
                 '   맥 기본값(애플 Vision)으로 돌리시려면 이 값을 지우세요.' % env)
    if sys.platform == 'darwin' and shutil.which('swift') and os.path.exists(SWIFT):
        return 'swift'
    return 'opencv'


def _notice(kind, want_text):
    """어떤 통로로 도는지 «부르는 쪽 화면»에 한 번 알린다.

    ★ 이 안내가 왜 필요한가 — 결과가 조금 다른데 이유를 모르면 사람이 «내가 뭘 잘못했나» 를 찾는다.
      OpenCV 통로는 글자를 «읽지» 못하므로 그 사실을 먼저 말해 준다.

    ⛔ 반드시 stderr 로 낸다. stdout 으로 내면
       `python3 detector.py f.png > boxes.json` 했을 때 안내문이 JSON 안에 섞여 파일이 깨진다.
    """
    global _notified
    if _notified:
        return
    _notified = True
    if kind == 'swift':
        return                      # ★ 맥 기본 통로는 지금까지처럼 «아무 말도 안 한다»
    w = sys.stderr.write
    if (os.environ.get('AUTOEDIT_DETECTOR') or '').strip():
        # 사람이 일부러 골라 놓은 경우 — «없어서» 라고 하면 거짓말이 된다
        w('※ 얼굴·사람 찾기: OpenCV(YuNet) 통로 — AUTOEDIT_DETECTOR 로 직접 지정하셨습니다.\n')
    else:
        w('※ 얼굴·사람 찾기: OpenCV(YuNet) 통로로 돕니다 — 이 컴퓨터에 애플 Vision 이 없습니다.\n')
    if want_text:
        w('  ⚠️ 이 통로는 화면의 글자를 «읽지» 못합니다. 글자처럼 생긴 «줄»을 어림잡을 뿐이라\n')
        w('     구워진 자막 위치가 맥보다 부정확합니다. 결과를 꼭 눈으로 확인하세요.\n')
        w('     (어림잡기를 끄려면:  AUTOEDIT_TEXT_DETECT=off)\n')
    sys.stderr.flush()


def _run_swift(paths, want_text, chunk):
    """지금까지 하던 것 그대로 — 인자로 여러 장을 한 번에 넘긴다. 너무 길면 나눠 부른다."""
    args = ['swift', SWIFT] + ([] if want_text else ['--no-text'])
    out = []
    for i in range(0, len(paths), chunk):
        r = subprocess.run(args + paths[i:i + chunk], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('speaker_box.swift 실패:\n' + r.stderr[:800])
        out.extend(json.loads(r.stdout))
    return out


def detect(paths, want_text=True, chunk=40):
    """프레임 여러 장 → 결과 리스트. 통로가 무엇이든 «같은 모양»으로 돌려준다.

    paths     : 프레임 이미지 경로들
    want_text : 화면 글자도 찾을지 (speaker_box.swift 의 --no-text 와 반대)
    chunk     : swift 통로에서 한 번에 넘길 장수 (인자 줄이 너무 길면 셸이 거부한다)
    """
    paths = list(paths)
    if not paths:
        return []
    kind = which()
    if kind == 'swift':
        _notice(kind, want_text)
        return _run_swift(paths, want_text, chunk)
    # 글자 어림잡기를 끄고 싶을 때 (부정확해서 차라리 «못 찾았다»로 두고 싶을 때)
    if (os.environ.get('AUTOEDIT_TEXT_DETECT') or '').strip().lower() in ('off', '0', 'no'):
        want_text = False
    _notice(kind, want_text)
    # ⛔ 여기서만 부른다 — 맥은 opencv 를 안 깔아도 지금처럼 다 돌아야 한다(선택 의존성).
    #    ⚠️ 부르는 쪽이 이 폴더를 sys.path 에 안 넣었을 수 있으니 여기서 직접 넣는다.
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import detect_opencv
    return detect_opencv.analyze_all(paths, want_text)


# ── 혼자 돌려 보기 (speaker_box.swift 와 같은 사용법) ──────────────
if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--no-text']
    want = '--no-text' not in sys.argv[1:]
    if not args:
        sys.exit('사용: python3 detector.py [--no-text] 프레임1.png 프레임2.png ...\n'
                 '  지금 통로: %s   (바꾸려면 AUTOEDIT_DETECTOR=swift|opencv)' % which())
    print(json.dumps(detect(args, want_text=want), ensure_ascii=False, indent=2, sort_keys=True))
