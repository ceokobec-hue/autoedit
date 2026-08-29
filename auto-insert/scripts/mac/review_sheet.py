#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검수 시트 — 전체 렌더 없이 필요한 프레임만 구워 번호를 붙인다.

사용:
  python3 review_sheet.py --video 편집본.mp4 --inserts inserts.json \
          [--chapters chapters.json] [--channel "내 채널"]

chapters.json = [{"at": 23.2, "title": "소제목"}, ...]   (없으면 소제목 없이 그린다)
폰트 폴더는 환경변수 AUTOEDIT_FONTS (기본 ~/.autoedit/fonts) — get_fonts.sh 가 받아 두는 곳.
"""
import argparse, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from srt_tools import CaptionFont, get_text_width

# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF    = ff_path.FFMPEG
FONTS = os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts'))
F     = os.path.join(FONTS, 'Pretendard-Bold.otf')
PAD=80; GUARD,TOPSAFE=1176,210

V=None; CHAPTERS=[]; CHANNEL='내 채널'
_FONT_CACHE=[None]
def _font():
    if _FONT_CACHE[0] is None:
        if not os.path.exists(F):
            sys.exit(f"\u26d4 폰트가 없습니다: {F}\n   → bash get_fonts.sh  로 먼저 받아 주세요.")
        _FONT_CACHE[0]=CaptionFont(F)
    return _FONT_CACHE[0]
def chap(t):
    s=''
    for a,x in CHAPTERS:
        if t>=a: s=x
    return s
def bug(sub):
    """★판 폭을 글자 폭으로 실측해서 정한다 — 고정폭이면 긴 소제목이 삐져나온다(실측)."""
    fnt=_font()
    w_title=get_text_width(CHANNEL,fnt,42)
    w_sub  =get_text_width(sub,fnt,30)
    plate  =int(max(w_title+24, w_sub) + 64)     # 좌측 여백 20+바9+간격15 = 44, 우측 20
    line   =int(max(w_title+24, w_sub) + 8)
    return [f"drawbox=x=64:y=46:w={plate}:h=126:color=black@0.42:t=fill",
      "drawbox=x=84:y=64:w=9:h=48:color=0xE8442E@1:t=fill",
      f"drawtext=fontfile={F}:text='{CHANNEL}':expansion=none:x=108:y=62:fontsize=42:fontcolor=white",
      f"drawbox=x=84:y=124:w={line}:h=2:color=white@0.35:t=fill",
      f"drawtext=fontfile={F}:text='{sub}':expansion=none:x=84:y=134:fontsize=30:fontcolor=0xE8C9A0"]

def tag(n,txt,color='0xE8442E'):
    # ★번호표는 우상단 — 좌상단은 채널 버그 자리라 가리면 검수가 안 된다
    return (f"drawtext=fontfile={F}:text='{n:02d}  {txt}':expansion=none:x=w-tw-40:y=24:"
            f"fontsize=46:fontcolor=white:box=1:boxcolor={color}@0.92:boxborderw=16")
def one(a):
    i,m=a; n=i+1; out='sheet/%02d.png'%n
    W=1240
    if m['render']=='full':
        vf=f"[1:v]{tag(n,m['id']+'  풀프레임')},scale={W}:-1[v]"
        subprocess.run([FF,'-v','error','-ss',str(m['at']),'-i',V,'-i',m['png'],
            '-filter_complex',vf,'-map','[v]','-frames:v','1','-y',out],check=True)
    else:
        x = 2560-56-m['w'] if '우' in m['corner'] else 56
        y = TOPSAFE if '상' in m['corner'] else GUARD-m['h']
        vf=';'.join([f"[0:v]{','.join(bug(chap(m['at'])))}[b]",
                     f"[b][1:v]overlay={x-PAD}:{y-PAD}[o]",
                     f"[o]{tag(n,m['id']+'  '+m['corner']+'  %dx%d'%(m['w'],m['h']))},scale={W}:-1[v]"])
        subprocess.run([FF,'-v','error','-ss',str(m['at']+2),'-i',V,'-i',m['png'],
            '-filter_complex',vf,'-map','[v]','-frames:v','1','-y',out],check=True)
    return out
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--video',    required=True, help='검수할 영상')
    ap.add_argument('--inserts',  default='inserts.json', help='인서트 계획 JSON')
    ap.add_argument('--chapters', help='소제목 JSON (없으면 소제목 없이)')
    ap.add_argument('--channel',  default='내 채널')
    ap.add_argument('--cta',      help='CTA 이미지 PNG (있으면 마지막 장으로 붙인다)')
    ap.add_argument('--out',      default='review_sheet.png',
                    help='나갈 «한 장짜리 검수 그림». ⛔HTML 이 아니라 PNG/JPG 다')
    a=ap.parse_args()
    # ⛔ .html 을 주면 ffmpeg 이 «형식을 모르겠다»는 낯선 에러를 뱉는다 → 먼저 잡아 준다
    if os.path.splitext(a.out)[1].lower() not in ('.png','.jpg','.jpeg','.webp'):
        sys.exit('⛔ --out 은 그림 파일이어야 합니다 (지금: %s).\n'
                 '   이 시트는 «프레임을 격자로 붙인 한 장짜리 그림»입니다.\n'
                 '   예:  --out 검수시트.png' % a.out)
    for _p,_who in ((a.video,'--video 로 검수할 영상을 주세요'),
                    (a.inserts,'build_inserts.py 를 먼저 돌리세요')):
        if not os.path.exists(_p): sys.exit('⛔ %s 이(가) 없습니다.\n   → %s'%(_p,_who))
    V=a.video; CHANNEL=a.channel
    if a.chapters:
        CHAPTERS=[(float(c['at']),c['title']) for c in json.load(open(a.chapters,encoding='utf-8'))]
        CHAPTERS.sort()
    M=json.load(open(a.inserts,encoding='utf-8'))
    os.makedirs('sheet',exist_ok=True)
    for f in os.listdir('sheet'): os.remove('sheet/'+f)
    with ThreadPoolExecutor(max_workers=4) as ex: list(ex.map(one,list(enumerate(M))))
    if a.cta and os.path.exists(a.cta):
        n_cta=len(M)+1
        subprocess.run([FF,'-v','error','-i',a.cta,'-vf',
            f"{tag(n_cta,'CTA','0x6b4a8a')},scale=1240:-1",'-frames:v','1','-y','sheet/%02d.png'%n_cta],check=True)
    n=len(os.listdir('sheet'))
    if not n: sys.exit('⛔ 붙일 프레임이 없습니다 — inserts.json 이 비어 있나요?')
    print('프레임 %d장'%n)
    # ⛔ tile 은 «칸 수»가 입력보다 많으면 빈 칸에서 실패한다 → 장수에 맞춰 격자를 줄인다
    cols=min(4,n); rows=max(1,(n+cols-1)//cols)
    subprocess.run([FF,'-v','error','-pattern_type','glob','-i','sheet/*.png','-filter_complex',
        f'tile={cols}x{rows}:margin=10:padding=6:color=0x0E0E0E','-frames:v','1','-y',a.out],check=True)
    print('→ '+a.out)
