#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대판 위치 지정용 «번호 격자» — 16:9(2560×1440) 4열 × 6행 = 24칸.

  규약: 번호 = 대판 «글자 블록의 왼쪽-아래 모서리»가 놓일 칸의 «왼쪽-아래».
        · 오른쪽으로 넘치면 화면 안으로 자동으로 당긴다
        · 자막 안전선(y=1139) 아래면 자동으로 올린다
        두 경우 모두 «조정했음»을 보고한다.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cards_v2 import shot, SIZE

# 격자 번호를 그릴 때 쓰는 폰트. get_fonts.sh 가 받아 두는 곳을 본다.
FONTS    = os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts'))
FONTFILE = os.environ.get('OTS_GRID_FONT', os.path.join(FONTS,'Pretendard-Black.woff2'))

W,H = 2560,1440
COLS,ROWS = 4,6
CW,CH = W//COLS, H//ROWS            # 640 × 240
DW = SIZE['daepan'][0]              # 대판 글자 블록 폭 1700
SAFE_BOT = 1139                     # 글자 아랫변 안전선 (자막 1152 − 13)
SUB_TOP, SUB_BOT = 1152, 1262
EYE_LO, EYE_HI = 380, 700

def resolve(n):
    """번호 → 실제 좌표. (x, y_ink_bottom, 조정메모)"""
    r, c = divmod(n-1, COLS)
    x, yb = c*CW, (r+1)*CH
    memo=[]
    if x + DW > W:
        x = W - DW; memo.append('오른쪽 넘침 → 안으로 당김')
    if yb > SAFE_BOT:
        yb = SAFE_BOT; memo.append('자막 침범 → 위로 올림')
    return x, yb, ' · '.join(memo)

cells=''
for n in range(1, COLS*ROWS+1):
    r, c = divmod(n-1, COLS)
    x, y = c*CW, r*CH
    # 보정 여부는 «그 카드의 글자 폭»에 달렸다 → 칸을 미리 색칠하지 않는다.
    # 대신 자막에 걸리는 5·6행만 옅게 표시한다.
    cls = ' low' if (r+1)*CH > SAFE_BOT else ''
    cells += ('<div class="c%s" style="left:%dpx;top:%dpx">%d</div>' % (cls, x, y, n))

HTML = f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:'Pretendard';src:url('file://{FONTFILE}') format('woff2');font-weight:900}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;background:transparent;font-family:'Pretendard',sans-serif}}
.g{{position:relative;width:{W}px;height:{H}px}}
.c{{position:absolute;width:{CW}px;height:{CH}px;border:3px solid rgba(120,255,190,.72);
 color:#fff;font-size:66px;font-weight:900;line-height:1;padding:12px 0 0 18px;
 text-shadow:0 3px 10px rgba(0,0,0,.92),0 0 3px rgba(0,0,0,.92)}}
.c.low{{border-color:rgba(255,208,70,.6);color:#FFE9A8;background:rgba(255,208,70,.07)}}
.sub{{position:absolute;left:0;right:0;top:{SUB_TOP}px;height:{SUB_BOT-SUB_TOP}px;
 background:repeating-linear-gradient(45deg,rgba(232,68,46,.32) 0 22px,rgba(232,68,46,.14) 22px 44px);
 border-top:5px solid #E8442E;border-bottom:5px solid #E8442E}}
.safe{{position:absolute;left:0;right:0;top:{SAFE_BOT}px;height:0;border-top:5px dashed #6BE3A8}}
.lbl{{position:absolute;font-size:32px;font-weight:900;padding:7px 16px;border-radius:8px}}
.l1{{right:22px;top:{SUB_TOP+26}px;background:#E8442E;color:#fff}}
.l2{{right:22px;top:{SAFE_BOT-58}px;background:#6BE3A8;color:#0e2a1c}}
.l3{{right:22px;top:{EYE_LO+16}px;background:#FFD046;color:#16130E}}
.eye{{position:absolute;left:0;right:0;top:{EYE_LO}px;height:{EYE_HI-EYE_LO}px;
 background:rgba(255,208,70,.12);border-top:4px dashed rgba(255,208,70,.8);
 border-bottom:4px dashed rgba(255,208,70,.8)}}
</style></head><body><div class="g">
<div class="eye"></div><div class="lbl l3">눈 띠 — 글자가 여기 오면 안 됨</div>
{cells}
<div class="safe"></div><div class="lbl l2">글자 아랫변 안전선 y1139</div>
<div class="sub"></div><div class="lbl l1">구워진 본 자막 y1152~1262</div>
</div></body></html>'''

if __name__=='__main__':
    import argparse
    _ap=argparse.ArgumentParser(description='대판 위치 지정용 번호 격자 PNG 를 만든다')
    _ap.add_argument('--out', default='grid.png', help='나갈 PNG (기본: 지금 폴더의 grid.png)')
    _a=_ap.parse_args()
    _html = os.path.splitext(_a.out)[0] + '.html'
    open(_html,'w',encoding='utf-8').write(HTML)
    print('✅' if shot(_html,_a.out,W,H) else '❌', _a.out)
    print('\n번호 → 실제 좌표 (글자 블록 왼쪽 x · 아랫변 y)')
    for n in range(1,25):
        x,yb,memo = resolve(n)
        print('  %2d  x=%-5d 아랫변 y=%-5d %s'%(n,x,yb,memo or ''))
