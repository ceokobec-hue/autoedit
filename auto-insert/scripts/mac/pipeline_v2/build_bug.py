#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""채널 버그(상시) + 단원 소제목 9개. 판 폭은 Pretendard 실측 폭으로 정한다."""
import os, json, subprocess, html
import sys, os as _os
sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import job
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    from fontTools.ttLib import TTFont
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 fonttools 가 없습니다 (글자 폭 실측).\n'
        '   이 도구의 부품은 ~/.autoedit/venv 라는 \u00ab작은 방\u00bb 안에 있습니다.\n'
        '   그 방의 파이썬으로 부르세요:\n'
        '     {} {} {}'.format(_v, _o.path.abspath(__file__), ' '.join(_s.argv[1:])) +
        '\n   방이 아직 없다면 설치.md 2단계를 보세요 (python3 doctor.py 로 확인).')
job.chdir()
FF=job.FF
CHROME=job.CHROME
FP=job.FONT
FONT='file://'+FP
os.makedirs('png',exist_ok=True); os.makedirs('html',exist_ok=True)

f=TTFont(FP); upm=f['head'].unitsPerEm; hmtx=f['hmtx']
cmap=f.getBestCmap()
def text_w(s, size):
    """실측 글자 폭 (px)"""
    tot=0
    for ch in s:
        g=cmap.get(ord(ch))
        tot += hmtx[g][0] if g and g in hmtx.metrics else int(upm*0.5)
    return tot/upm*size

BUG='내 채널'
BUG_FS=42; PAD_X=22; BAR=9; GAP=14
bug_w = int(64 + BAR + GAP + text_w(BUG,BUG_FS) + PAD_X*2)   # 실측
bug_h = 76

CH=[(0.0,   '오프닝 — 무엇부터 자동화할까'),
    (31.8,  '잠깐, 세 가지만 떠올려 보세요'),
    (94.3,  '반복은 어디에나 있다'),
    (190.6, '문제를 다섯 가지로 나눈다'),
    (365.3, '여기에 자동화가 붙는다'),
    (413.1, '실습 — 카페 세 곳의 엑셀'),
    (695.9, '두 번째 단원'),
    (1001.0,'무엇부터 자동화할까 — 우선순위'),
    (1138.0,'사람의 몫, 그리고 다음 강')]
CH_FS=34; CH_DUR=6.0

blocks=[]; sizes=[]
# ① 버그
bw = int(BAR+GAP+text_w(BUG,BUG_FS)+PAD_X*2); bh=bug_h
blocks.append(('bug', bw, bh, f'''<div class="slot" style="width:{bw}px;height:{bh}px">
 <div class="bug"><i></i><span>{html.escape(BUG)}</span></div></div>'''))
# ② 소제목
for i,(t,txt) in enumerate(CH,1):
    w=int(text_w(txt,CH_FS)+PAD_X*2); h=62
    blocks.append(('ch%02d'%i, w, h, f'''<div class="slot" style="width:{w}px;height:{h}px">
     <div class="ch">{html.escape(txt)}</div></div>'''))

CSS=f'''@font-face{{font-family:PD;src:url("{FONT}")}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:transparent}}
body{{font-family:PD,sans-serif;-webkit-font-smoothing:antialiased;width:1400px}}
.slot{{overflow:hidden}}
.bug{{height:100%;background:rgba(0,0,0,.42);border-radius:12px;display:flex;align-items:center;
  padding:0 {PAD_X}px;gap:{GAP}px}}
.bug i{{width:{BAR}px;height:48px;background:#E8442E;border-radius:2px;display:block}}
.bug span{{color:#fff;font-size:{BUG_FS}px;letter-spacing:-.02em}}
.ch{{height:100%;background:rgba(0,0,0,.36);border-radius:10px;color:#F4F1EA;
  font-size:{CH_FS}px;display:flex;align-items:center;padding:0 {PAD_X}px;letter-spacing:-.02em}}
'''
body=''.join(b for *_,b in blocks)
hp='html/_bug.html'
open(hp,'w',encoding='utf-8').write('<!doctype html><meta charset="utf-8"><style>'+CSS+'</style><body>'+body)
total=sum(h for _,_,h,_ in blocks)
subprocess.run([CHROME,'--headless','--disable-gpu','--hide-scrollbars',
  '--window-size=1400,%d'%total,'--default-background-color=00000000',
  '--screenshot='+os.path.abspath('png/_bugbatch.png'),'--virtual-time-budget=3000',
  'file://'+os.path.abspath(hp)],capture_output=True)
y=0; meta={}
for name,w,h,_ in blocks:
    subprocess.run([FF,'-v','error','-i','png/_bugbatch.png','-vf','crop=%d:%d:0:%d'%(w,h,y),
                    '-y','png/%s.png'%name],check=True)
    meta[name]={'w':w,'h':h}; y+=h
os.remove('png/_bugbatch.png')
meta['chapters']=[{'i':i,'t':t,'title':x,'dur':CH_DUR} for i,(t,x) in enumerate(CH,1)]
meta['bug_pos']=[64,46]; meta['ch_pos']=[64,46+bh+18]
json.dump(meta,open('bug.json','w'),ensure_ascii=False,indent=1)
print('버그 %dx%d (실측 폭) · 소제목 %d개'%(bw,bh,len(CH)))
for i,(t,x) in enumerate(CH,1):
    print('  %d. %5.1fs  %-30s 판 폭 %dpx'%(i,t,x,meta['ch%02d'%i]['w']))
