#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카드 72장 — «한 장에 몰아 굽고 잘라내기». Chrome 은 2~3번만 띄운다."""
import os, json, subprocess, html
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (PNG 검사).\n'
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
CHROME=job.CHROME
FONT='file://'+os.path.join(os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts')),'Pretendard-Bold.otf')
W,H=job.W,job.H
os.makedirs('png',exist_ok=True)
CARDS=json.load(open('cards.json',encoding='utf-8'))
PLACE=json.load(open('placement.json'))
SIZE={'sticker':(560,150),'bento':(720,380),'rail':(700,400),
      'daepan':(940,240),'terminal':(800,300),'full':(W,H)}
def kind_of(c): return PLACE[str(c['no'])]['kind'] if str(c['no']) in PLACE else 'full'

# ── 무판대판 배경 밝기 일괄 측정 ────────────────────────
BG={}
for c in CARDS:
    if kind_of(c)!='daepan': continue
    p=PLACE[str(c['no'])]; w,h=SIZE['daepan']
    r=subprocess.run([FF,'-v','error','-ss','%.2f'%p['t'],'-i',V,'-frames:v','1',
        '-vf','crop=%d:%d:%d:%d,format=gray'%(w,h,p['x'],p['y']),'-f','rawvideo','-'],capture_output=True)
    a=np.frombuffer(r.stdout,dtype=np.uint8)
    BG[c['no']]=(float(a.mean()),float(a.std())) if a.size>10 else (128.0,99.0)

BASE=f'''@font-face{{font-family:PD;src:url("{FONT}")}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:transparent}}
body{{font-family:PD,-apple-system,sans-serif;-webkit-font-smoothing:antialiased;
 word-break:keep-all}}
.slot{{position:relative;overflow:hidden}}
.kick{{letter-spacing:.10em;color:#E8442E}}
.key{{letter-spacing:-.03em;line-height:1.24}}
.sub{{line-height:1.5;opacity:.92}}
.box{{height:100%;display:flex;flex-direction:column;justify-content:center}}
.st .box{{align-items:center;justify-content:center}}
.st .in{{background:#E8442E;color:#fff;border-radius:20px;padding:26px 38px;
   box-shadow:0 12px 34px rgba(0,0,0,.34)}}
.st .key{{font-size:54px}}
.be .box,.ra .box{{background:#F4F1EA;color:#16130E;border-radius:20px;padding:34px 36px;
   border:2px solid rgba(22,19,14,.22);
   box-shadow:0 14px 38px rgba(0,0,0,.34),0 0 0 1px rgba(255,255,255,.5)}}
.ra .box{{border-left:14px solid #E8442E;padding-left:30px}}
.be .kick,.ra .kick{{font-size:26px;margin-bottom:12px}}
.be .key{{font-size:50px}} .ra .key{{font-size:54px}}
.be .sub,.ra .sub{{font-size:24px;margin-top:14px;color:#5f584d}}
.te .box{{background:#12100d;border:2px solid #3a352c;border-radius:14px;padding:28px 32px;
   box-shadow:0 12px 34px rgba(0,0,0,.42);font-family:ui-monospace,Menlo,monospace}}
.te .kick{{font-size:24px;margin-bottom:12px}} .te .key{{font-size:44px;color:#d8f5e0}}
.te .sub{{font-size:24px;margin-top:14px;color:#8fdca0}}
.dp .kick{{font-size:28px;margin-bottom:14px}} .dp .key{{font-size:72px}}
.dp .sub{{font-size:26px;margin-top:16px}}
.fu{{background:#F4F1EA;color:#16130E}}
.fu .box{{align-items:center;justify-content:center;text-align:center;padding:0 160px}}
.fu .kick{{font-size:40px;margin-bottom:22px}} .fu .key{{font-size:110px}}
.fu .sub{{font-size:44px;margin-top:26px;color:#5f584d}}
'''
CLS={'sticker':'st','bento':'be','rail':'ra','terminal':'te','daepan':'dp','full':'fu'}

def block(c):
    k=kind_of(c); w,h=SIZE[k]
    kick=html.escape(c['kicker']); key=html.escape(c['keyword']); sub=html.escape(c['sub'])
    K=f'<div class="kick">{kick}</div>' if kick else ''
    S=f'<div class="sub">{sub}</div>' if sub else ''
    style=''
    if k=='daepan':
        lum,sd=BG[c['no']]; ink=lum>140
        col='#16130E' if ink else '#F7F4ED'
        sh='0 2px 10px rgba(255,255,255,.6)' if ink else '0 2px 14px rgba(0,0,0,.65)'
        style=f'style="color:{col};text-shadow:{sh}"'
    inner=f'<div class="box" {style}>{K}<div class="key">{key}</div>{S}</div>'
    if k=='sticker': inner=f'<div class="box"><div class="in"><div class="key">{key}</div></div></div>'
    return k,w,h,f'<div class="slot {CLS[k]}" style="width:{w}px;height:{h}px">{inner}</div>'

def shoot(items, pagew, out):
    """items = [(no,k,w,h,htmlblock)] 세로로 쌓아 한 장에 굽고 잘라낸다"""
    body=''.join(b for *_,b in items)
    css=BASE+f'body{{width:{pagew}px}}'
    hp='html/_batch_%s.html'%out
    os.makedirs('html',exist_ok=True)
    open(hp,'w',encoding='utf-8').write('<!doctype html><meta charset="utf-8"><style>'+css+'</style><body>'+body)
    total=sum(h for _,_,_,h,_ in items)
    cmd=[CHROME,'--headless','--disable-gpu','--hide-scrollbars',
         '--window-size=%d,%d'%(pagew,total),'--screenshot='+os.path.abspath('png/'+out),
         '--virtual-time-budget=4000']
    if items[0][1]!='full': cmd.append('--default-background-color=00000000')
    cmd.append('file://'+os.path.abspath(hp))
    subprocess.run(cmd,capture_output=True)
    if not os.path.exists('png/'+out): return False
    y=0
    for no,k,w,h,_ in items:
        subprocess.run([FF,'-v','error','-i','png/'+out,'-vf','crop=%d:%d:0:%d'%(w,h,y),
                        '-y','png/c%02d.png'%no],check=True)
        y+=h
    os.remove('png/'+out)
    return True

corner=[]; full=[]
for c in CARDS:
    k,w,h,b=block(c)
    (full if k=='full' else corner).append((c['no'],k,w,h,b))
print('코너 %d장 · 풀프레임 %d장'%(len(corner),len(full)))
ok1=shoot(corner, 940, 'batch_corner.png')
print('코너 배치:', '완료' if ok1 else '실패')
for i in range(0,len(full),4):
    part=full[i:i+4]
    print('  풀프레임 %d~%d ...'%(part[0][0],part[-1][0]), flush=True)
    shoot(part, W, 'batch_full_%d.png'%i)
import re as _re
made=sorted(int(m.group(1)) for f in os.listdir('png') if (m:=_re.fullmatch(r'c(\d{2})\.png',f)))
print('\n총 %d/72 굽기 완료'%len(made))
print('빠진 번호:', [c['no'] for c in CARDS if c['no'] not in made] or '없음')
print('\n무판대판 글자색:')
for no,(lum,sd) in sorted(BG.items()):
    print('   #%-3d 배경밝기 %5.1f · 얼룩 %4.1f → %s'%(no,lum,sd,'검은 글씨' if lum>140 else '흰 글씨'))
