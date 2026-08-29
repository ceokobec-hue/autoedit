#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""번호 격자 ↔ 실제 좌표 변환. 대판 «글자 블록»을 칸에 앉힌다.

  규약: 번호 = 글자 블록의 «왼쪽-아래 모서리»가 그 칸의 «왼쪽-아래»에 온다.
  자동 보정 2가지 (하면 반드시 보고한다):
    · 오른쪽으로 넘치면 화면 안으로 당긴다
    · 글자 아랫변이 안전선(y1139)보다 내려가면 올린다
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ink import bbox

W, H      = 2560, 1440
COLS,ROWS = 4, 6
CW, CH    = W//COLS, H//ROWS      # 640 × 240
MARGIN    = 50                    # 화면 좌우 최소 여백
SAFE_BOT  = 1139                  # 글자 아랫변 안전선 (구워진 자막 1152 − 13)

def cell_anchor(n):
    """번호 → (칸의 왼쪽 x, 칸의 아랫변 y)"""
    if not (1 <= n <= COLS*ROWS):
        raise ValueError('번호는 1~%d' % (COLS*ROWS))
    r, c = divmod(n-1, COLS)
    return c*CW, (r+1)*CH

def place(png, n, scale=1.0):
    """대판 PNG를 n번 칸에 앉힐 «합성 좌표»를 낸다.
       return (ox, oy, memo, inkw, inkh)"""
    b = bbox(png)
    if b is None: raise RuntimeError('글자를 못 찾음: %s' % png)
    il, it, ir, ib = b
    inkw, inkh = ir-il+1, ib-it+1
    tx, tyb = cell_anchor(n)
    tx, tyb = tx*scale, tyb*scale
    memo = []
    lo, hi = MARGIN*scale, W*scale - MARGIN*scale - inkw
    if tx > hi: tx = hi; memo.append('오른쪽 넘침 → 안으로 당김')
    if tx < lo: tx = lo; memo.append('왼쪽 여백 확보')
    if tyb > SAFE_BOT*scale:
        tyb = SAFE_BOT*scale; memo.append('자막 침범 → 위로 올림')
    if tyb - inkh < 0:
        tyb = inkh; memo.append('위로 넘침 → 내림')
    return round(tx-il), round(tyb-ib), ' · '.join(memo), inkw, inkh

def which_cell(x_ink_left, y_ink_bottom):
    """실제 좌표 → 제일 가까운 번호 (지금 어디 있는지 알려줄 때)"""
    c = min(COLS-1, max(0, int(x_ink_left)//CW))
    r = min(ROWS-1, max(0, (int(y_ink_bottom)-1)//CH))
    return r*COLS + c + 1

if __name__=='__main__':
    import glob
    print('%-4s %-9s %-8s %s'%('칸','글자폭','합성좌표','보정'))
    for p in sorted(glob.glob('fin/D*.png'))[:1]:
        for n in (1,2,3,5,9,13,14,17,18,21):
            ox,oy,memo,w,h = place(p,n)
            print('%-4d %-9d %-8s %s'%(n,w,'%d,%d'%(ox,oy),memo or '—'))
