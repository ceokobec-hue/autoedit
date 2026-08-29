#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""작업 설정 한 곳 — 스크립트마다 경로를 박아 두지 않는다.

같은 폴더의 job.json 을 읽는다. 없으면 환경변수, 그것도 없으면 에러.

job.json 예:
{
 "video":   "/절대경로/편집끝난_영상.mp4",
 "srt":     "/절대경로/자막-한국어.srt",
 "workdir": "/절대경로/작업폴더",
 "width": 2560, "height": 1440,
 "sub_band":  [1190, 1345],          # 이미 구워진 자막 띠 (실측)
 "pip":       [1795, 0, 2560, 435],  # 화면공유 샷의 얼굴 창 (measure_pip.py 로 잰다)
 "bug_zone":  [0, 0, 600, 210],      # 채널 버그·소제목 자리
 "out":       "완성본.mp4"           # 최종 렌더 파일명 (없으면 작업폴더의 완성본.mp4)
}

⛔ 개인 절대경로를 스크립트에 박지 않는다. 경로는 전부 이 파일이나 환경변수로 받는다.
"""
import os, json, sys

_HERE = os.path.dirname(os.path.abspath(__file__))

def load(start=None):
    for d in (start or os.getcwd(), _HERE):
        p = os.path.join(d, 'job.json')
        if os.path.exists(p):
            return json.load(open(p, encoding='utf-8'))
    env = {k: os.environ.get('AI_'+k.upper()) for k in ('video','srt','workdir')}
    if all(env.values()):
        return env
    sys.exit('❌ job.json 이 없습니다. 작업 폴더에 만들어 주세요.\n'
             '   → 옆에 있는 예시를 복사해서 고치면 됩니다:\n'
             '     cp %s ./job.json' % os.path.join(_HERE, 'job.example.json'))

J = load()
VIDEO   = J['video']
SRT     = J['srt']
WORKDIR = J.get('workdir', os.getcwd())
W, H    = J.get('width', 2560), J.get('height', 1440)
SUB     = tuple(J.get('sub_band', [1190, 1345]))
PIP     = tuple(J.get('pip', [1795, 0, 2560, 435]))
BUGZONE = tuple(J.get('bug_zone', [0, 0, 600, 210]))
OUT     = J.get('out', '완성본.mp4')   # 최종 렌더 파일명 — ⛔개인 경로를 코드에 박지 않는다
# ── ffmpeg·크롬 경로는 저장소 뿌리의 도우미 한 곳에서만 정한다 ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
import platform_tools
FF      = J.get('ffmpeg', ff_path.FFMPEG)
# ⛔ 크롬 위치를 코드에 박지 않는다 — OS 마다 자리가 다르다.
#    job.json 의 "chrome" ▸ 환경변수 CHROME ▸ OS 별 표준 자리 순서로 찾는다.
CHROME  = J.get('chrome') or platform_tools.find_chrome()
FONT    = J.get('font', os.path.join(os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts')),'Pretendard-Bold.otf'))

def chdir():
    os.makedirs(WORKDIR, exist_ok=True); os.chdir(WORKDIR)

def save_atomic(obj, path):
    """⛔ open(path,'w') 를 dump 안에서 바로 쓰면 실패 시 «원본이 이미 비워진» 채로 남는다."""
    txt = json.dumps(obj, indent=1, ensure_ascii=False)
    tmp = path + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(txt)
    os.replace(tmp, path)
