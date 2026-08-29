#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자리 판정 «후» 정리 — ① 같은 시간대 겹침 해소 ② #1 오프닝 타이틀 되살리기.
   ⛔ 시각을 민 뒤에는 반드시 다시 겹침 검사를 해야 한다(이번에 놓쳐서 4건 발생)."""
import os, json, subprocess, math
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (겹침 계산).\n'
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
W,H=job.W,job.H; CELL=40; GW,GH=W//CELL,H//CELL
SUB=job.SUB; PIP=job.PIP
SIZE={'sticker':(560,150),'bento':(720,380),'rail':(700,400),
      'daepan':(940,240),'terminal':(800,300)}
CARDS=json.load(open('cards.json',encoding='utf-8')); C={c['no']:c for c in CARDS}
P=json.load(open('placement.json'))

def gray(t):
    r=subprocess.run([FF,'-v','error','-ss','%.2f'%t,'-i',V,'-frames:v','1',
                      '-vf','format=gray','-f','rawvideo','-'],capture_output=True)
    return np.frombuffer(r.stdout,dtype=np.uint8)[:W*H].reshape(H,W).astype(np.float32)
def busy(g):
    b=g[:GH*CELL,:GW*CELL].reshape(GH,CELL,GW,CELL).transpose(0,2,1,3).reshape(GH,GW,-1)
    return b.std(axis=2)
def rects(ok):
    R=[];hgt=np.zeros(ok.shape[1],dtype=int)
    for r in range(ok.shape[0]):
        hgt=np.where(ok[r],hgt+1,0); st=[]
        for c in range(ok.shape[1]+1):
            h=hgt[c] if c<ok.shape[1] else 0; s=c
            while st and st[-1][1]>=h:
                p,hh=st.pop()
                if hh>0: R.append((p,r-hh+1,c-1,r,hh,c-p))
                s=p
            st.append((s,h))
    return R
def place(kind,t,avoid=None):
    g=gray(t); bz=busy(g); scr=g[30:130,250:900].mean()>145
    ok = bz < (9.0 if kind=='daepan' else 22.0)
    ok[:1,:]=False; ok[-1:,:]=False; ok[:,:1]=False; ok[:,-1:]=False
    ok[:210//CELL+1,:600//CELL+1]=False                      # 채널 버그 자리
    ok[SUB[0]//CELL:min(GH-1,SUB[1]//CELL)+1,:]=False          # 기존 자막
    if scr: ok[PIP[1]//CELL:PIP[3]//CELL+1, PIP[0]//CELL:]=False
    if avoid:                                                  # ★ 다른 카드가 쓰는 자리
        x0,y0,x1,y1=avoid
        ok[max(0,y0//CELL):min(GH,y1//CELL+1), max(0,x0//CELL):min(GW,x1//CELL+1)]=False
    nw,nh=SIZE[kind]; cw,ch=math.ceil(nw/CELL),math.ceil(nh/CELL)
    best=None
    for c0,r0,c1,r1,hh,ww in rects(ok):
        if ww<cw or hh<ch: continue
        s=ww*hh
        if best is None or s>best[0]: best=(s,c0,r0)
    if not best: return None
    _,c0,r0=best
    return {'t':round(t,2),'screen':bool(scr),'x':int(c0)*CELL,'y':int(r0)*CELL,
            'w':int(nw),'h':int(nh),'shift':0,'kind':kind}

log=[]
# ── ① #1 오프닝 타이틀: 10초로 밀린 데다 #3 과 같은 자리였다 → 판 있는 카드로 바꿔 0초대에 되돌린다
p3=P['3']; av=(p3['x'],p3['y'],p3['x']+p3['w'],p3['y']+p3['h'])
for t in (0.5,2.0,3.5,5.0):
    got=place('bento',t,avoid=av)
    if got:
        P['1']=got; log.append('#1 무판대판 10.0초 → 벤토 %.1f초 (오프닝 타이틀 제자리로, #3 자리 회피)'%t); break
else:
    log.append('#1 되돌리기 실패 — 그대로 둠')

# ── ② 겹침 해소: 앞 카드를 짧게 잘라 0.3초 띄운다(최소 2.5초 보장)
DUR={c['no']:c['dur'] for c in CARDS}
for _ in range(4):
    seg=sorted([( (P.get(str(n)) or {}).get('t', C[n]['at']), n) for n in C])
    changed=False
    for (t0,n0),(t1,n1) in zip(seg,seg[1:]):
        end=t0+DUR[n0]
        if t1 < end-0.01:
            new=max(2.5, round(t1-t0-0.3,2))
            if new < DUR[n0]:
                log.append('#%d %.1f초 → %.1f초 (#%d 와 겹쳐 앞을 잘랐음)'%(n0,DUR[n0],new,n1))
                DUR[n0]=new; changed=True
    if not changed: break

def save(obj, path):
    txt=json.dumps(obj,indent=1,ensure_ascii=False)   # 먼저 «문자열로» 만들어 본다
    tmp=path+'.tmp'
    open(tmp,'w',encoding='utf-8').write(txt)
    os.replace(tmp,path)                              # 다 됐을 때만 갈아끼운다
save(P,'placement.json')
save({str(k):float(v) for k,v in DUR.items()},'durations.json')
# 최종 검사
seg=sorted([((P.get(str(n)) or {}).get('t',C[n]['at']), (P.get(str(n)) or {}).get('t',C[n]['at'])+DUR[n], n) for n in C])
ov=[(a[2],b[2]) for a,b in zip(seg,seg[1:]) if b[0]<a[1]-0.01]
same=[]
for i,(a0,a1,an) in enumerate(seg):
    for b0,b1,bn in seg[i+1:]:
        if b0>=a1: break
        pa,pb=P.get(str(an)),P.get(str(bn))
        if pa and pb and not (pa['x']+pa['w']<=pb['x'] or pb['x']+pb['w']<=pa['x']
                              or pa['y']+pa['h']<=pb['y'] or pb['y']+pb['h']<=pa['y']):
            same.append((an,bn))
print('\n'.join(log) or '조정 없음')
print('\n시간 겹침:', ov or '없음 ✅')
print('같은 시간·같은 자리 충돌:', same or '없음 ✅')
