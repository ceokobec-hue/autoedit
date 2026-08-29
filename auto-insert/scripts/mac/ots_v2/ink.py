#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PNG에서 «글자 잉크»의 실제 사각 범위를 잰다.
   대판은 판이 없어서 «상자»가 아니라 «글자»가 어디 있는지가 전부다.
   그늘(스크림)은 검정이라 밝기로 걸러진다. ⛔외부 패키지 없음(ffmpeg만).

   ⛔투영(scale=iw:1)으로 재면 가는 획이 평균에 묻혀 «폭이 실제보다 좁게» 나온다.
     안전 판정에서 과소측정은 위험하다 → 행 단위로 직접 훑는다(bytes.find = C 속도)."""
import subprocess, os
import sys
# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF  = os.environ.get('FFFULL', ff_path.FFMPEG)
THR = 88          # 이 밝기 위면 «글자». 레드(#E8442E)의 luma ≈ 114 라 잡힌다

def _gray(png):
    r = subprocess.run([FF,'-v','error','-i',png,
        '-vf',"format=gray,lut=y='if(gt(val,%d),255,0)'"%THR,
        '-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'], capture_output=True)
    p = subprocess.run([os.path.join(os.path.dirname(FF),'ffprobe'),'-v','error',
        '-select_streams','v:0','-show_entries','stream=width,height','-of','csv=p=0:s=x',png],
        capture_output=True, text=True)
    w,h = (int(v) for v in p.stdout.strip().split('x')[:2])
    return r.stdout, w, h

def bbox(png):
    """글자만의 (left, top, right, bottom). 없으면 None"""
    buf,w,h = _gray(png)
    if len(buf) < w*h: return None
    L,T,R,B = w, -1, -1, -1
    for y in range(h):
        row = buf[y*w:(y+1)*w]
        i = row.find(255)
        if i < 0: continue
        j = row.rfind(255)
        if T < 0: T = y
        B = y
        if i < L: L = i
        if j > R: R = j
    return None if B < 0 else (L,T,R,B)

if __name__=='__main__':
    import sys
    for p in sys.argv[1:]:
        b = bbox(p)
        print('%-12s %s' % (os.path.basename(p),
              '없음' if not b else 'x %d~%d (폭 %d) · y %d~%d (높이 %d)'
              % (b[0],b[2],b[2]-b[0]+1,b[1],b[3],b[3]-b[1]+1)))
