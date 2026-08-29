#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OTS 카드 스팬별 배치 판정 — 스팬 안 여러 프레임 전부에서 비어 있는 쪽만 채택."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
S=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, S)
from srt_tools import tc
# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF=ff_path.FFMPEG
SWIFT=os.path.join(S,'speaker_box.swift')

def grab(video, times, outdir):
    os.makedirs(outdir, exist_ok=True)
    def one(a):
        i,t=a; p=os.path.join(outdir,'f%05d.png'%i)
        subprocess.run([FF,'-v','error','-ss','%.3f'%t,'-i',video,'-frames:v','1','-y',p],check=True)
        return p
    with ThreadPoolExecutor(max_workers=4) as ex: return list(ex.map(one,list(enumerate(times))))

def vision(frames, chunk=30):
    out=[]
    for i in range(0,len(frames),chunk):
        r=subprocess.run(['swift',SWIFT]+frames[i:i+chunk],capture_output=True,text=True)
        if r.returncode: raise RuntimeError(r.stderr[:600])
        out+=json.loads(r.stdout)
    return out

def label_of(c):
    """화면에 찍을 이름. ⛔'label' 만 찾으면 스키마에 없는 칸이라 KeyError 로 죽는다."""
    import re as _re
    for k in ('label','head','keyword','kicker','h1'):
        v = c.get(k)
        if v: return _re.sub(r'<[^>]+>', ' ', str(v)).strip()
    return c['id']

if __name__=='__main__':
    # ⛔ sys.argv[1] 을 그냥 집으면 «IndexError» 만 나온다 — 비개발자에겐 아무 정보도 없는 벽이다
    if len(sys.argv) < 3:
        raise SystemExit(
            '사용: python3 ots_place.py <영상.mp4> <카드계획.json>\n'
            '  나가는 것: ots_measure.json (카드마다 사람·글자를 피해 어디가 비었는지)\n'
            '  카드계획.json 형식은 ots_v2/README.md 「카드 계획 JSON 스키마」 참고\n'
            '  다음 단계: python3 build_inserts.py --cards <카드계획.json> --from-measure ots_measure.json')
    V=sys.argv[1]
    for p in (V, sys.argv[2]):
        if not os.path.exists(p): raise SystemExit('⛔ %s 이(가) 없습니다.'%p)
    CARDS=json.load(open(sys.argv[2],encoding='utf-8'))
    if not CARDS: raise SystemExit('⛔ %s 에 카드가 한 장도 없습니다.'%sys.argv[2])
    # ⛔ 여기서 통과시키면 사용자는 다음 단계(build_inserts)에서 스택트레이스를 맞는다.
    #    「관대한 앞단 + 엄격한 뒷단」이 제일 나쁘다 → 첫 단계에서 알려준다.
    _ots=[c for c in CARDS if c.get('kind') in ('sticker','bento','rail','daepan','terminal')]
    if _ots:
        raise SystemExit(
            '⛔ %s 은(는) «OTS 카드» 형식입니다 — 이 스크립트는 «방송형 인서트»용입니다.\n'
            '   섞여 있는 카드: %s\n\n'
            '   OTS 카드는 이쪽으로 가세요:\n'
            '     python3 auto-insert/scripts/mac/ots_v2/plan_cards.py <영상.mp4> %s\n\n'
            '   두 형식의 차이는 파일형식.md 를 보세요.'
            % (sys.argv[2], ', '.join(c.get('id','?') for c in _ots), sys.argv[2]))
    SAMPLES=5
    times, index = [], []
    for c in CARDS:
        if 'at' not in c:
            raise SystemExit('⛔ %s 카드에 «언제 띄울지»(at)가 없습니다 — 카드 JSON 에 "at": 초 를 넣어 주세요.'%c.get('id','?'))
        for k in range(SAMPLES):
            _d = c.get('dur', 5.0)
            times.append(c['at'] + _d*k/(SAMPLES-1) if SAMPLES>1 else c['at']); index.append(c['id'])
    frames=grab(V, times, '_ots_frames')
    vis=vision(frames)
    W=vis[0]['width']; H=vis[0]['height']
    print('영상 %dx%d · 표본 %d장\n' % (W,H,len(vis)))

    # 하단 자막 띠 윗변 — 아래 58% 밑에 있는 글자만
    bands=[]
    for r in vis:
        ys=[t['y'] for t in r['texts'] if t['y']>=H*0.58]
        if ys: bands.append(min(ys))
    guard = min(bands) if bands else None
    print('구워진 자막 윗변: %s  (표본 %d/%d)' % ('%.0fpx'%guard if guard else '못 찾음', len(bands), len(vis)))

    res=[]
    for c in CARDS:
        rs=[v for v,i in zip(vis,index) if i==c['id']]
        # 스팬 전체에서 사람 박스의 최대 확장
        boxes=[p for r in rs for p in r['persons'] if p['conf']>=0.45 and p['h']>H*0.25 and p['w']<W*0.92]
        if boxes:
            L=min(b['x'] for b in boxes); R=max(b['x']+b['w'] for b in boxes)
        else:
            L=R=None
        # 슬라이드/판서 = 화면 위 58% 안의 글자 뭉치
        stx=[t for r in rs for t in r['texts'] if t['y']<H*0.58]
        sL=min([t['x'] for t in stx],default=None); sR=max([t['x']+t['w'] for t in stx],default=None)
        left_free  = (L if L is not None else W) - 0
        right_free = W - (R if R is not None else 0)
        res.append({'id':c['id'],'at':c['at'],'dur':c.get('dur',5.0),'label':label_of(c),
                    'person_L':None if L is None else round(L),'person_R':None if R is None else round(R),
                    'left_free':round(left_free),'right_free':round(right_free),
                    'slide_L':None if sL is None else round(sL),'slide_R':None if sR is None else round(sR),
                    'n_person':len(boxes),'n_text':len(stx)})
        print('%-4s %s %-14s │ 사람 %s~%s │ 좌여백 %4d 우여백 %4d │ 상단글자 %s' % (
            c['id'], tc(c['at']), label_of(c)[:14],
            '%4s'%(L and round(L)), '%4s'%(R and round(R)),
            left_free, right_free,
            ('%d개 x%s~%s'%(len(stx),round(sL),round(sR))) if stx else '없음'))
    json.dump({'W':W,'H':H,'guard':guard,'cards':res}, open('ots_measure.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
