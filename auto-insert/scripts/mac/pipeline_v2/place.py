#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""컷마다 «그 시각의 실제 프레임»을 재서 카드 자리를 정한다.
   금지: 얼굴(+25% 여유) · 기존 자막 띠 · 화면에 글자/내용이 있는 칸.
   자리가 없으면 시각을 +15초까지 민다. 그래도 없으면 기록해서 보고한다."""
import subprocess, json, os, sys, math
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (자리 찾기).\n'
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
CELL=40; GW,GH=W//CELL,H//CELL          # 64 x 36
SUB=job.SUB                          # 기존 자막 띠(여유 포함)
PIP=job.PIP                    # 화면공유 샷의 얼굴 창(실측 y=421 + 여유)
FRAMES='_frames'; os.makedirs(FRAMES,exist_ok=True)

# 카드 종류별 최소 크기 (px) — 렌더 실측 전 설계값
SIZE={'sticker':(560,150),'bento':(720,380),'rail':(700,400),
      'daepan':(940,240),'terminal':(800,300)}

def grab(t):
    p='%s/f_%08.2f.jpg'%(FRAMES,t)
    if not os.path.exists(p):
        subprocess.run([FF,'-v','error','-ss','%.2f'%t,'-i',V,'-frames:v','1','-q:v','3','-y',p],check=True)
    return p

def gray(t):
    r=subprocess.run([FF,'-v','error','-ss','%.2f'%t,'-i',V,'-frames:v','1',
                      '-vf','format=gray','-f','rawvideo','-'],capture_output=True)
    return np.frombuffer(r.stdout,dtype=np.uint8)[:W*H].reshape(H,W).astype(np.float32)

def busy_grid(g):
    """칸마다 «내용이 있나» — 표준편차가 크면 글자/그림이 있는 것"""
    b=g[:GH*CELL,:GW*CELL].reshape(GH,CELL,GW,CELL).transpose(0,2,1,3).reshape(GH,GW,-1)
    return b.std(axis=2)

def is_screen(g):
    """화면공유 샷인가 — 좌상단이 밝고 평평한 UI 인가"""
    return g[30:130,250:900].mean()>145

def faces(paths):
    """★ 얼굴 검출기는 새로 만들지 않는다. 윗폴더의 detector.py 가 «통로»를 고른다.
       맥 = speaker_box.swift(애플 Vision) · 윈도우 = OpenCV(YuNet). 나가는 모양은 같다.
       출력: [{image,width,height,faces:[{x,y,w,h,conf}],persons:[...],texts:[...]}]
       ⚠️ 예전 --no-text 와 같은 뜻으로 want_text=False 를 준다 — 여기서는 얼굴만 쓴다."""
    _mac = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    if _mac not in sys.path:
        sys.path.insert(0, _mac)
    import detector
    out = {}
    try:
        for d in detector.detect(paths, want_text=False):
            out[d['image']] = [{'box':[int(f['x']), int(f['y']),
                                       int(f['x']+f['w']), int(f['y']+f['h'])],
                                'conf': f['conf']} for f in d.get('faces', [])]
    except Exception:
        pass
    return out

def largest_rects(ok):
    """빈 칸(True) 안에서 가능한 «최대 직사각형»들을 모아 준다 (히스토그램 방식)"""
    GHh,GWw=ok.shape; res=[]
    height=np.zeros(GWw,dtype=int)
    for r in range(GHh):
        height=np.where(ok[r],height+1,0)
        stack=[]
        for c in range(GWw+1):
            h=height[c] if c<GWw else 0
            start=c
            while stack and stack[-1][1]>=h:
                s,hh=stack.pop()
                if hh>0: res.append((s,r-hh+1,c-1,r,hh,c-s))   # c0,r0,c1,r1,h,w
                start=s
            stack.append((start,h))
    return res

CARDS=json.load(open('cards.json',encoding='utf-8'))
NEED=[c for c in CARDS if c['kind']!='full']
print('자리 판정 대상 %d컷 (풀프레임 %d컷은 자리 불필요)'%(len(NEED),len(CARDS)-len(NEED)))

# 1) 프레임 뽑기 — 컷당 시작 지점 1장 (+ 밀 때 추가)
plan={}; report=[]
SHIFTS=[0,2.5,5,7.5,10,12.5,15]
paths_needed=[]
for c in NEED:
    for s in SHIFTS: paths_needed.append((c['no'], round(c['at']+s,2)))
# 얼굴은 실제로 쓰는 것만 나중에 호출(전량은 비쌈)

def evaluate(c, t):
    if t+c['dur'] > 1323.0: return None
    g=gray(t); scr=is_screen(g); bz=busy_grid(g)
    # ★ 기준을 카드 종류로 나눈다.
    #   판 있는 카드(스티커·벤토·세로레일·터미널)는 «글자/그림»만 피하면 된다 → 22
    #   무판대판은 글자 없이 바탕에 바로 얹으므로 «정말 깨끗한 곳»이어야 한다 → 9
    THR = 9.0 if c['kind']=='daepan' else 22.0
    ok = bz < THR
    # 금지 구역 지우기
    fcx=None
    # ★ 화면 가장자리 40px 은 쓰지 않는다 — 카드가 화면에 붙으면 잘린 것처럼 보인다
    ok[:1,:]=False; ok[-1:,:]=False; ok[:,:1]=False; ok[:,-1:]=False
    # ★ 좌상단은 채널 버그(상시) + 단원 소제목 자리다 — 카드가 그 위에 얹히면 안 된다
    ok[:210//CELL+1, :600//CELL+1]=False
    r0,r1=SUB[0]//CELL, min(GH-1,SUB[1]//CELL)
    ok[r0:r1+1,:]=False
    if scr:
        ok[PIP[1]//CELL:PIP[3]//CELL+1, PIP[0]//CELL:]=False
    else:
        fp=grab(t); fs=faces([os.path.abspath(fp)]).get(os.path.abspath(fp),[])
        for f in fs:
            x0,y0,x1,y1=f['box']; m=int((x1-x0)*0.25)
            ok[max(0,(y0-m)//CELL):min(GH,(y1+m)//CELL+1),
               max(0,(x0-m)//CELL):min(GW,(x1+m)//CELL+1)]=False
        if not fs:   # 얼굴 못 찾으면 «사람이 있는 쪽»을 모르니 가운데 세로 띠를 피한다
            ok[:, int(GW*0.30):int(GW*0.78)]=False
        if fs:
            b=max(fs,key=lambda f:(f['box'][2]-f['box'][0]))['box']
            fcx=(b[0]+b[2])/2/W
    need_w,need_h=SIZE[c['kind']]
    cw,ch=math.ceil(need_w/CELL), math.ceil(need_h/CELL)
    best=None
    for c0,rr0,c1,rr1,hh,ww in largest_rects(ok):
        if ww<cw or hh<ch: continue
        # 점수: 실습 구간은 «오른쪽·위» 우대(화면공유 때 그쪽이 잘 빈다), 그 외는 넓고 가장자리 우대
        cx=(c0+c1)/2/GW; cy=(rr0+rr1)/2/GH
        score = ww*hh
        if c['zone']=='B':
            score += (cx*260) + ((1-cy)*140)          # 우측 상단 = 얼굴 창 아래의 세로 칸
        elif fcx is not None:
            score += abs(cx-fcx)*300                  # 실사 샷은 «얼굴 반대편»
        else:
            score += abs(cx-0.5)*180
        if best is None or score>best[0]: best=(score,c0,rr0,c1,rr1)
    if not best: return None
    _,c0,rr0,c1,rr1=best
    # 칸을 픽셀로, 필요한 크기만큼만 잘라 쓴다(왼쪽-위 정렬, 실습이면 오른쪽 정렬)
    X0,Y0,X1,Y1=c0*CELL,rr0*CELL,(c1+1)*CELL,(rr1+1)*CELL
    x = X1-need_w if c['zone']=='B' else X0
    y = Y0
    return {'t':round(t,2),'screen':bool(scr),'x':int(x),'y':int(y),
            'w':need_w,'h':need_h,'slot':[int(X0),int(Y0),int(X1),int(Y1)]}

# ★ 배경이 안 받치면 «판 있는 카드»로 강등한다 — 이 공정에서는 스크림(그라데이션)을 쓰지 않는다
DEMOTE={'daepan':'bento','rail':'sticker','bento':'sticker','terminal':'sticker','sticker':None}
for i,c in enumerate(NEED,1):
    got=None; used=c['kind']
    for s in SHIFTS:
        got=evaluate(c, c['at']+s)
        if got: got['shift']=s; break
    if not got:                                  # 원래 종류로는 자리가 없다 → 강등 재시도
        d=DEMOTE.get(c['kind'])
        while d and not got:
            c2=dict(c); c2['kind']=d
            for s in SHIFTS:
                got=evaluate(c2, c['at']+s)
                if got: got['shift']=s; used=d; break
            d=DEMOTE.get(d)
    if got:
        got['kind']=used
        plan[c['no']]=got
        if used!=c['kind']:      report.append((c['no'],'%s → %s 강등 (배경이 안 받침)'%(c['kind'],used)))
        elif got['shift']>0:     report.append((c['no'],'시각 +%.1f초'%got['shift']))
    else:
        report.append((c['no'],'⛔ 자리 없음 — 풀프레임 승격 검토'))
    if i%12==0: print('  ...%d/%d'%(i,len(NEED)), flush=True)

json.dump(plan, open('placement.json','w'), indent=1)
print('\n자리 확정 %d / %d'%(len(plan),len(NEED)))
print('조정·실패 %d건:'%len(report))
for no,w in report: print('   #%d  %s'%(no,w))
