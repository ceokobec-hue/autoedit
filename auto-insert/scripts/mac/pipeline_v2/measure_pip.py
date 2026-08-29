#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""화면공유 샷의 «얼굴 창(PIP)» 자리를 영상에서 직접 재서 알려 준다.

  결과의 x 범위·아랫변 y 를 job.json 의 "pip" 에 넣으면 인서트가 얼굴을 안 덮는다.
  사용: python3 measure_pip.py [--n 8] [--start 초] [--end 초]"""
import subprocess, os, argparse
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (얼굴 창 실측).\n'
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

def vdur(path):
    fp=os.path.join(os.path.dirname(FF),'ffprobe')   # ⛔ 문자열 치환은 경로까지 바꿔 버린다
    r=subprocess.run([fp,'-v','error','-show_entries','format=duration','-of','csv=p=0',path],
                     capture_output=True,text=True)
    try: return float(r.stdout.strip())
    except ValueError: return 0.0

_ap=argparse.ArgumentParser(description='얼굴 창(PIP) 자리를 실측한다')
_ap.add_argument('--n', type=int, default=8, help='표본 시각 개수 (기본 8)')
_ap.add_argument('--start', type=float, help='표본을 뽑을 시작 초 (기본: 영상 10%% 지점)')
_ap.add_argument('--end',   type=float, help='표본을 뽑을 끝 초 (기본: 영상 90%% 지점)')
_a=_ap.parse_args()
def clip(t,n=8,step=0.4):
    r=subprocess.run([FF,'-v','error','-ss',str(t),'-i',V,'-frames:v',str(n),
        '-vf','fps=%g,format=gray'%(1/step),'-f','rawvideo','-'],capture_output=True)
    a=np.frombuffer(r.stdout,dtype=np.uint8); k=len(a)//(W*H)
    return a[:k*W*H].reshape(k,H,W).astype(np.float32)
# ⛔ 표본 시각을 박아 두면 «다른 영상에선 엉뚱한 곳»을 잰다 → 영상 길이에서 고르게 뽑는다
_D  = vdur(V)
if _D <= 0: raise SystemExit('⛔ 영상 길이를 못 읽었습니다: %s'%V)
_a0 = _a.start if _a.start is not None else _D*0.10
_a1 = _a.end   if _a.end   is not None else _D*0.90
if _a1 <= _a0: raise SystemExit('⛔ --start 가 --end 보다 뒤에 있습니다.')
TIMES = [_a0] if _a.n<=1 else [_a0 + (_a1-_a0)*k/(_a.n-1) for k in range(_a.n)]
print('영상 %.1f초 · 표본 %d곳: %s'%(_D, len(TIMES), ' '.join('%.0f'%t for t in TIMES)))

res=[]
for t in TIMES:
    G=clip(t)
    if len(G)<4: continue
    mov=G.std(axis=0)
    # ① 열: 상단 400행에서 움직이는 비율이 높은 열 = PIP 열
    cp=(mov[:400,:]>6).mean(axis=0)
    cs=np.where(cp>0.5)[0]
    if not len(cs): continue
    x0,x1=int(cs[0]),int(cs[-1])
    # ② 행: 그 열 안에서만 본다
    rp=(mov[:800,x0:x1+1]>6).mean(axis=1)
    rs=np.where(rp>0.5)[0]
    y1=int(rs[-1]) if len(rs) else -1
    res.append((x0,y1,x1))
    print('t=%6.1f   PIP  x %d ~ %d   아랫변 y = %d'%(t,x0,x1,y1))
if not res:
    raise SystemExit('⛔ 얼굴 창을 못 찾았습니다 — 화면공유 구간을 --start/--end 로 지정해 보세요.')
A=np.array(res)
print('\n▶ 중앙값 PIP = x %d ~ %d · 아랫변 y %d'%(np.median(A[:,0]),np.median(A[:,2]),np.median(A[:,1])))
print('  → job.json 의 "pip": [%d, 0, %d, %d]'%(np.median(A[:,0]),np.median(A[:,2]),np.median(A[:,1])))
