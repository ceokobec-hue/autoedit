#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""최종 렌더 — 인서트컷 + 채널 버그(상시) + 단원 소제목을 한 번에 얹는다.

사용: python3 render_overlays.py [--out 완성본.mp4] [--test]
  --out 을 안 주면 job.json 의 "out" 키, 그것도 없으면 작업폴더의 완성본.mp4 로 나간다.
  --test 는 가운데 60초만 굽는 «맛보기»다 (전체 렌더 전에 자리·색을 확인한다)."""
import os, json, subprocess, sys, time, argparse
import sys, os as _os
sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import job
job.chdir()
FF=job.FF
V=job.VIDEO
CARDS=json.load(open('cards.json',encoding='utf-8'))
PLACE=json.load(open('placement.json'))
BUG=json.load(open('bug.json',encoding='utf-8'))
DUR=json.load(open('durations.json'))          # 겹침 정리로 짧아진 길이 반영
FADE=0.25

_ap = argparse.ArgumentParser(description='인서트컷·버그·소제목을 한 패스로 굽는다')
_ap.add_argument('--out', help='출력 파일 (기본: job.json 의 "out", 없으면 작업폴더의 완성본.mp4)')
_ap.add_argument('--test', action='store_true', help='가운데 60초만 굽는 맛보기')
_ap.add_argument('--ss', type=float, help='맛보기 시작 시각(초). 기본은 영상 한가운데')
_a = _ap.parse_args()

TEST = _a.test
# ⛔ 맛보기 시작을 특정 회차 시각으로 박아 두면 남의 영상에선 엉뚱한 데를 굽는다 → 한가운데
_END = max((c['at']+c['dur'] for c in CARDS), default=120.0)
SS, T = ((_a.ss if _a.ss is not None else max(0.0, _END/2 - 30)), 60.0) if TEST else (None, None)

inputs=['-i',V]; parts=[]; idx=1
def add(png, dur=None):
    '''⛔ 정지 PNG 를 그냥 넣으면 fade 가 t=0 에서 멈춰 «알파 0 = 안 보임» 이 된다.
       -loop 1 -t 로 진짜 시간축을 줘야 페이드가 산다.'''
    global idx
    if dur: inputs.extend(['-loop','1','-framerate','30','-t','%.2f'%(dur+0.2),'-i',png])
    else:   inputs.extend(['-i',png])
    i=idx; idx+=1; return i

def win(t0,dur):
    a,b=t0,t0+dur
    if TEST: a-=SS; b-=SS
    return a,b

layers=[]
for c in CARDS:
    p=PLACE.get(str(c['no']))
    t = p['t'] if p else c['at']
    if TEST and not (SS-6 <= t <= SS+T): continue
    x,y = (p['x'],p['y']) if p else (0,0)
    d=DUR.get(str(c['no']), c['dur'])
    layers.append((add('png/c%02d.png'%c['no'], d), x, y, t, d))
# 버그 = 상시
bx,by = BUG['bug_pos']
bug_i = add('png/bug.png')
ch_layers=[]
for ch in BUG['chapters']:
    if TEST and not (SS-6 <= ch['t'] <= SS+T): continue
    ch_layers.append((add('png/ch%02d.png'%ch['i'], ch['dur']), BUG['ch_pos'][0], BUG['ch_pos'][1], ch['t'], ch['dur']))

fc=[]; cur='0:v'
for i,(src,x,y,t,dur) in enumerate(layers):
    a,b=win(t,dur)
    fc.append(f"[{src}:v]format=rgba,fade=t=in:st=0:d={FADE}:alpha=1,"
              f"fade=t=out:st={dur-FADE:.2f}:d={FADE}:alpha=1,setpts=PTS+{a:.2f}/TB[l{i}];")
    fc.append(f"[{cur}][l{i}]overlay={x}:{y}:enable='between(t,{a:.2f},{b:.2f})'[v{i}];")
    cur=f'v{i}'
n=len(layers)
fc.append(f"[{cur}][{bug_i}:v]overlay={bx}:{by}[vb];")
cur='vb'
for j,(src,x,y,t,dur) in enumerate(ch_layers):
    a,b=win(t,dur)
    fc.append(f"[{src}:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,"
              f"fade=t=out:st={dur-0.3:.2f}:d=0.3:alpha=1,setpts=PTS+{a:.2f}/TB[m{j}];")
    fc.append(f"[{cur}][m{j}]overlay={x}:{y}:enable='between(t,{a:.2f},{b:.2f})'[w{j}];")
    cur=f'w{j}'
fc.append(f"[{cur}]null[out]")
open('filter.txt','w').write('\n'.join(fc))

# ⛔ 개인 경로·회차 이름을 박지 않는다 → --out ▸ job.json 의 "out" ▸ 작업폴더의 완성본.mp4
out = '_test.mp4' if TEST else (_a.out or job.OUT)
cmd=[FF,'-y']
if TEST: cmd += ['-ss',str(SS),'-t',str(T)]
# ⛔ '0:a' 는 소리가 없는 영상에서 죽는다 → '?' = 없으면 그냥 건너뛴다
cmd += inputs + ['-filter_complex','\n'.join(fc),'-map','[out]','-map','0:a?',
      '-c:v','h264_videotoolbox','-b:v','22M','-profile:v','high',
      '-c:a','copy','-movflags','+faststart', out]
# ⛔ 프리플라이트 — 입력 PNG 가 하나라도 없으면 여기서 멈춘다
missing=[a for a in inputs if a.endswith('.png') and not os.path.exists(a)]
if missing:
    print('❌ 없는 입력 %d개:'%len(missing), missing[:6]); sys.exit(1)
print('프리플라이트 OK — 입력 PNG %d개 전부 있음'%sum(1 for a in inputs if a.endswith('.png')))
print('레이어 %d장(카드 %d + 버그1 + 소제목 %d) · 출력 %s'%(len(layers)+1+len(ch_layers),len(layers),len(ch_layers),out))
t0=time.time()
r=subprocess.run(cmd,capture_output=True,text=True)
el=time.time()-t0
if r.returncode!=0:
    print('❌ 실패\n', r.stderr[-2500:]); sys.exit(1)
sz=os.path.getsize(out)/1073741824
print('✅ %.1f초 걸림 · %.2fGB'%(el,sz))
if TEST: print('   → 전체 %.0f초(%.1f분) 예상'%(el*_END/T, el*_END/T/60))
