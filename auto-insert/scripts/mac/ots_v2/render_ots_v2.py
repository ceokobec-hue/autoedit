#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""최종 렌더 — 원본 위에 OTS 카드를 «한 패스»로 굽는다.

   한 패스인 이유: 세대가 쌓이면 화질이 깎이고 QHD 중간본이 디스크를 먹는다.
   ⛔자막은 이미 원본에 구워져 있으므로 건드리지 않는다.

사용: python3 render_ots_v2.py [--video 원본.mp4] [--out 완성본.mp4] [--bitrate 24M]
      plan_final.json · check_cards.json 은 approve.py 가, fin/*.png 는 cards_v2.py 가 만든다."""
import json, os, subprocess, sys, argparse, time
# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
from platform_tools import venc      # 인코더는 OS 마다 다르다 (맥·윈도우·리눅스)
FF=ff_path.FFMPEG
FP=ff_path.FFPROBE
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cards_v2 import SIZE                      # 종류별 (본체폭, 본체높이, 여백)

ap=argparse.ArgumentParser(description='OTS 카드를 원본 위에 한 패스로 굽는다')
ap.add_argument('--video', default=os.environ.get('OTS_VIDEO','source.mp4'),
                help='자막이 구워진 원본 영상 (기본: $OTS_VIDEO 또는 source.mp4)')
ap.add_argument('--plan',  default='plan_final.json', help='approve.py 가 만든 배치')
ap.add_argument('--cards', default='check_cards.json', help='approve.py 가 만든 카드 목록')
ap.add_argument('--pngdir', default='fin', help='cards_v2.py 가 구운 카드 PNG 폴더')
ap.add_argument('--out', default='완성본.mp4')
ap.add_argument('--bitrate', default='24M')
ap.add_argument('--ss', type=float); ap.add_argument('--t', type=float)
a=ap.parse_args()
V = a.video

def need(path, who):
    if not os.path.exists(path): sys.exit('⛔ %s 이(가) 없습니다.\n   → %s'%(path,who))
need(a.plan,  'python3 approve.py --cards cards.json --plan plan_out.json  을 먼저 돌리세요')
need(a.cards, 'python3 approve.py --cards cards.json --plan plan_out.json  을 먼저 돌리세요')
need(V,       '영상 경로를 --video 로 알려 주세요 (또는 $OTS_VIDEO)')

P = json.load(open(a.plan, encoding='utf-8'))
C = {c['id']:c for c in json.load(open(a.cards, encoding='utf-8'))}
if not P: sys.exit('⛔ %s 에 카드가 한 장도 없습니다.'%a.plan)
items=[]
for r in P:
    if r['id'] not in C:
        sys.exit('⛔ %s 에 %s 카드가 없습니다 — approve.py 를 다시 돌리세요.'%(a.cards, r['id']))
    c=C[r['id']]
    # 합성 좌표 = 카드 «본체» 좌표 − 여백(그림자·돌출용 투명 테두리)
    # ⛔ 종류별 여백을 여기 다시 적으면 cards_v2 와 어긋난다 → SIZE 에서 그대로 가져온다
    pad = r.get('pad', round(SIZE[r['kind']][2] * r.get('scale',1.0)))
    items.append({'png':os.path.join(a.pngdir,'%s.png'%r['id']), 'x':r['x']-pad, 'y':r['y']-pad,
                  's':c['at'], 'e':c['at']+c.get('dur',6), 'id':r['id']})
items.sort(key=lambda i:i['s'])

gone=[it['png'] for it in items if not os.path.exists(it['png'])]
if gone:
    sys.exit('⛔ 카드 PNG 가 없습니다:\n  '+'\n  '.join(gone)+
             '\n→ python3 cards_v2.py %s %s  를 먼저 돌리세요'%(a.cards, a.pngdir))

cmd=[FF,'-y','-hide_banner']
if a.ss is not None: cmd+=['-ss',str(a.ss)]
if a.t  is not None: cmd+=['-t',str(a.t)]
cmd+=['-i',V]
for it in items: cmd+=['-i',it['png']]

off=a.ss or 0.0
fc=[]; cur='0:v'
for k,it in enumerate(items,1):
    nxt='v%d'%k
    fc.append("[%s][%d:v]overlay=%d:%d:enable='between(t,%.2f,%.2f)'[%s]"
              %(cur,k,it['x'],it['y'],it['s']-off,it['e']-off,nxt))
    cur=nxt
# ⛔ '0:a:0' 는 소리가 없는 영상에서 «옵션 값이 틀렸다»며 죽는다 → '?' = 없으면 그냥 건너뛴다
cmd+=(['-filter_complex',';'.join(fc),'-map','[%s]'%cur,'-map','0:a:0?']
      + venc(a.bitrate) +                       # ← 이 컴퓨터에 맞는 인코더 (platform_tools.py)
      ['-pix_fmt','yuv420p',
      '-g','60','-r','30','-video_track_timescale','30000',
      '-c:a','aac','-b:a','192k','-movflags','+faststart',a.out])

print('카드 %d장 · 비트레이트 %s'%(len(items),a.bitrate), flush=True)
t0=time.time()
r=subprocess.run(cmd,capture_output=True,text=True)
if r.returncode:
    print('⛔ 실패:\n'+r.stderr[-2500:]); sys.exit(1)
el=time.time()-t0

def dur(p):
    return float(subprocess.run([FP,'-v','error','-show_entries','format=duration',
        '-of','csv=p=0',p],capture_output=True,text=True).stdout.strip())
d0,d1 = dur(V), dur(a.out)
print('✅ 완료  %.0f초 걸림 (%.1f분)'%(el,el/60))
print('   길이  원본 %.3f → 완성 %.3f  (오차 %+.3f초)'%(d0,d1,d1-d0))
print('   용량  %.2f GB'%(os.path.getsize(a.out)/1e9))
print('   경로  %s'%a.out)
