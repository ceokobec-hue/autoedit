#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""화면 구조 실측 — «같은 샷 안»에서 3초간 6프레임. 정지한 앱 화면 vs 살아 움직이는 얼굴 PIP 분리."""
import subprocess, json, os
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (레이아웃 실측).\n'
        '   이 도구의 부품은 ~/.autoedit/venv 라는 \u00ab작은 방\u00bb 안에 있습니다.\n'
        '   그 방의 파이썬으로 부르세요:\n'
        '     {} {} {}'.format(_v, _o.path.abspath(__file__), ' '.join(_s.argv[1:])) +
        '\n   방이 아직 없다면 설치.md 2단계를 보세요 (python3 doctor.py 로 확인).')
import sys, os as _os
sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import job
job.chdir()
FF=job.FF
V=job.VIDEO
W,H=job.W,job.H

def clip_gray(t, n=6, step=0.5):
    """t 부터 n장, step 초 간격"""
    r=subprocess.run([FF,'-v','error','-ss',str(t),'-i',V,'-frames:v',str(n),
        '-vf','fps=%g,format=gray'%(1/step),'-f','rawvideo','-'],capture_output=True)
    a=np.frombuffer(r.stdout,dtype=np.uint8)
    k=len(a)//(W*H)
    return a[:k*W*H].reshape(k,H,W).astype(np.float32)

def pip_box(t):
    G=clip_gray(t)
    if len(G)<3: return None
    mov=G.std(axis=0)                     # 픽셀별 시간 변화량
    m = mov > 6.0
    # 열/행 프로파일 — 30% 이상 픽셀이 움직이는 구간
    cp=m.mean(axis=0); rp=m.mean(axis=1)
    cs=np.where(cp>0.15)[0]; rs=np.where(rp>0.15)[0]
    if not len(cs) or not len(rs): return None
    return [int(cs[0]),int(rs[0]),int(cs[-1]),int(rs[-1])], float(m.mean())

for t in (420, 455, 560, 640, 780, 810, 880):
    b=pip_box(t)
    print('t=%4ds  PIP box = %s'%(t, b))

# 자막 띠 — 한 샷 안에서 «하단이 켜졌다 꺼지는» 행
G=clip_gray(455, n=10, step=0.4)
low=G[:,1100:1440,:]
srow=low.std(axis=0).mean(axis=1)
cand=np.where(srow>8)[0]
print('자막 변화 행 y =', (1100+cand[0], 1100+cand[-1]) if len(cand) else '미검출')
# 자막 판 밝기(회색 판) — 실제 프레임에서 가로로 균일한 밝은 띠
f=G[0]
for y in range(1150,1400,25):
    row=f[y,:]
    print('  y=%4d  평균 %5.1f  표준편차 %5.1f'%(y,row.mean(),row.std()))
