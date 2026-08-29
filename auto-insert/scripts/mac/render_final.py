#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""최종 렌더 — 원본 위에 ①채널버그·소제목(ASS) ②인서트컷 ③CTA 를 한 패스로 굽는다.

한 패스로 하는 이유: 세대가 쌓이면 화질이 깎이고, QHD 중간본이 디스크를 먹는다.
사용: python3 render_final.py --video 원본.mp4 --inserts inserts.json [--ass overlay.ass] [--out 완성본.mp4]
      inserts.json 은 build_inserts.py 가 만든다."""
import json, os, subprocess, sys, argparse
# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF=ff_path.FFMPEG

PAD=80; GUARD,TOPSAFE=1176,210; W,H=2560,1440
FONTS = os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts'))

ap=argparse.ArgumentParser()
ap.add_argument('--video',required=True,help='원본 영상')
ap.add_argument('--inserts',default='inserts.json',help='인서트 계획 JSON (build_inserts.py 산출)')
ap.add_argument('--ass','--overlay',dest='ass',default='overlay.ass',
                help='채널버그·소제목 ASS (broadcast_overlay.py 산출). 없으면 자막 없이 굽는다')
ap.add_argument('--out',default='완성본.mp4')
ap.add_argument('--ss',type=float); ap.add_argument('--t',type=float)
ap.add_argument('--bitrate',default='24M')
ap.add_argument('--cta',help='CTA 이미지 PNG (선택)')
ap.add_argument('--cta-at',type=float,default=0.0,help='CTA 시작 초')
ap.add_argument('--cta-dur',type=float,default=3.0,help='CTA 길이 초')
a=ap.parse_args()

V=a.video
for _p, _who in ((V,'--video 로 원본 영상을 주세요'),
                 (a.inserts,'python3 build_inserts.py --cards <카드.json> --place <자리.json> 를 먼저 돌리세요')):
    if not os.path.exists(_p): sys.exit('⛔ %s 이(가) 없습니다.\n   → %s'%(_p,_who))
M=json.load(open(a.inserts,encoding='utf-8'))
_gone=[m['png'] for m in M if not os.path.exists(m['png'])]
if _gone:
    sys.exit('⛔ 인서트 PNG 가 없습니다:\n  '+'\n  '.join(_gone)+
             '\n→ build_inserts.py 를 «이 폴더에서» 다시 돌리세요.')
items=[]
for m in M:
    st=m['at']; en=st+m['dur']
    if m['render']=='full':
        items.append({'png':m['png'],'x':0,'y':0,'s':st,'e':en,'id':m['id']})
    else:
        x = W-56-m['w'] if '우' in m['corner'] else 56
        y = TOPSAFE if '상' in m['corner'] else GUARD-m['h']
        items.append({'png':m['png'],'x':x-PAD,'y':y-PAD,'s':st,'e':en,'id':m['id']})
if a.cta:
    items.append({'png':a.cta,'x':0,'y':0,'s':a.cta_at,'e':a.cta_at+a.cta_dur,'id':'CTA'})
items.sort(key=lambda i:i['s'])

cmd=[FF,'-y','-hide_banner']
if a.ss is not None: cmd+=['-ss',str(a.ss)]
if a.t  is not None: cmd+=['-t',str(a.t)]
cmd+=['-i',V]
for it in items: cmd+=['-i',it['png']]

off = a.ss or 0.0
# ⛔ ASS 파일이 없는데 subtitles 필터를 걸면 ffmpeg 이 통째로 실패한다 → 있을 때만 건다
if os.path.exists(a.ass):
    fc=[f"[0:v]subtitles={a.ass}:fontsdir={FONTS}[v0]"]
    cur='v0'
else:
    print('⚠️ %s 이 없어 채널버그·소제목 없이 굽습니다 (broadcast_overlay.py 로 만들 수 있습니다)'%a.ass)
    fc=[]; cur='0:v'
for k,it in enumerate(items,1):
    nxt='v%d'%k
    s=it['s']-off; e=it['e']-off
    fc.append(f"[{cur}][{k}:v]overlay={it['x']}:{it['y']}:enable='between(t,{s:.2f},{e:.2f})'[{nxt}]")
    cur=nxt
if not fc: fc=[f"[{cur}]null[vout]"]; cur='vout'
# ⛔ '0:a:0' 는 소리가 없는 영상에서 죽는다 → '?' = 없으면 그냥 건너뛴다
cmd+=['-filter_complex',';'.join(fc),'-map','[%s]'%cur,'-map','0:a:0?',
      '-c:v','h264_videotoolbox','-b:v',a.bitrate,'-pix_fmt','yuv420p',
      '-g','60','-r','30','-video_track_timescale','30000',
      '-c:a','aac','-b:a','192k','-movflags','+faststart',a.out]
print('인서트 %d개%s · 출력 %s'%(len(items)-(1 if a.cta else 0),' (+CTA)' if a.cta else '',a.out))
r=subprocess.run(cmd,capture_output=True,text=True)
if r.returncode:
    print('⛔ 실패:\n'+r.stderr[-2500:]); sys.exit(1)
sz=os.path.getsize(a.out)/1e9
d=subprocess.run([ff_path.FFPROBE,'-v','error','-show_entries',
    'format=duration','-of','csv=p=0',a.out],capture_output=True,text=True).stdout.strip()
print('✅ 완료  %s초  %.2f GB'%(d,sz))
