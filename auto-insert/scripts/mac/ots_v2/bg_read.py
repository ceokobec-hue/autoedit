#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""배경 가독성 판독기 — 카드가 놓일 자리의 밝기·복잡도를 재서
   「흰 글씨가 읽히나 / 검은 글씨가 읽히나 / 판 없이 가도 되나」를 판정한다.
   ⛔외부 파이썬 패키지 안 씀(ffmpeg만). 윈도우 머신에서도 그대로 돈다."""
import subprocess, math, os

import sys
# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF = os.environ.get('FFFULL', ff_path.FFMPEG)
GW, GH = 24, 18          # 판독 격자 — 잔텍스처는 뭉개고 «큰 얼룩»만 본다

def _lin(v):
    """sRGB 8bit → 상대휘도(WCAG)"""
    c = v/255.0
    return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4

def _cr(l1, l2):
    a, b = max(l1,l2), min(l1,l2)
    return (a+0.05)/(b+0.05)

def sample(frame, x, y, w, h, gw=GW, gh=GH):
    """그 자리의 밝기 격자를 읽어온다 → 0~255 값 gw*gh개"""
    r = subprocess.run(
        [FF,'-v','error','-i',frame,
         '-vf','crop=%d:%d:%d:%d,scale=%d:%d:flags=area,format=gray'%(w,h,x,y,gw,gh),
         '-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'],
        capture_output=True)
    if r.returncode or len(r.stdout) < gw*gh:
        raise RuntimeError('격자 읽기 실패: %s' % r.stderr[:200].decode('utf8','replace'))
    return list(r.stdout[:gw*gh])

def read(frame, x, y, w, h):
    """한 자리를 판독해 숫자와 판정을 돌려준다"""
    g = sample(frame, x, y, w, h)
    n = len(g)
    mean = sum(g)/n
    std  = math.sqrt(sum((v-mean)**2 for v in g)/n)
    s = sorted(g)
    p10, p50, p90 = s[int(n*0.10)], s[int(n*0.50)], s[int(n*0.90)]

    # 최악의 칸 기준으로 대비를 잰다 — 평균만 보면 밝은 얼룩에 글씨가 묻힌다
    cr_white = _cr(1.0, _lin(p90))      # 흰 글씨 vs 그 자리에서 «제일 밝은» 쪽
    cr_black = _cr(_lin(p10), 0.0)      # 검은 글씨 vs 그 자리에서 «제일 어두운» 쪽
    return dict(mean=round(mean,1), std=round(std,1), p10=p10, p50=p50, p90=p90,
                cr_white=round(cr_white,2), cr_black=round(cr_black,2))

if __name__=='__main__':
    import sys, json, glob
    frames = sorted(glob.glob(sys.argv[1])) if len(sys.argv)>1 else []
    # 좌/우 후보 자리(카드 780x590 기준) + 하단 대판자막 자리
    SPOTS = {'좌':(90,300,780,590), '우':(1690,300,780,590),
             '중앙대판':(380,420,1800,420)}
    print('%-14s %-9s %6s %6s %7s %7s' % ('프레임','자리','평균','편차','흰대비','검은대비'))
    agg={k:[] for k in SPOTS}
    for f in frames:
        for k,(x,y,w,h) in SPOTS.items():
            try: r = read(f,x,y,w,h)
            except Exception as e: print('  ⛔',f,k,e); continue
            agg[k].append(r)
            print('%-14s %-9s %6.1f %6.1f %7.2f %7.2f' %
                  (os.path.basename(f), k, r['mean'], r['std'], r['cr_white'], r['cr_black']))
    print()
    for k,rs in agg.items():
        if not rs: continue
        m=lambda key: sum(r[key] for r in rs)/len(rs)
        print('■ %s  n=%d  평균밝기 %.1f · 편차 %.1f · 흰대비 %.2f · 검은대비 %.2f' %
              (k,len(rs),m('mean'),m('std'),m('cr_white'),m('cr_black')))
