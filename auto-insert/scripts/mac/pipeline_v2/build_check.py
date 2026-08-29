#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검수 시트 — 카드를 «그 시각의 진짜 화면»에 얹어 번호표와 함께 낸다."""
import os, json, subprocess, base64, html
import sys, os as _os
sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import job
job.chdir()
FF=job.FF
V=job.VIDEO
CARDS=json.load(open('cards.json',encoding='utf-8'))
PLACE=json.load(open('placement.json'))
os.makedirs('chk',exist_ok=True)

KIND={'sticker':'스티커','bento':'벤토','rail':'세로레일','daepan':'무판대판',
      'terminal':'터미널','full':'풀프레임'}
def mmss(t): return '%d:%04.1f'%(t//60,t%60)

for c in CARDS:
    out='chk/c%02d.jpg'%c['no']
    if os.path.exists(out): continue
    p=PLACE.get(str(c['no']))
    t = p['t'] if p else c['at']
    png='png/c%02d.png'%c['no']
    if p:
        vf="[0][1]overlay=%d:%d[o];[o]scale=760:-1"%(p['x'],p['y'])
    else:
        vf="[0][1]overlay=0:0[o];[o]scale=760:-1"
    subprocess.run([FF,'-v','error','-ss','%.2f'%t,'-i',V,'-i',png,
        '-filter_complex',vf,'-frames:v','1','-q:v','4','-y',out],check=True)
    if c['no']%12==0: print('  ...%d/72'%c['no'],flush=True)

def b64(p):
    return 'data:image/jpeg;base64,'+base64.b64encode(open(p,'rb').read()).decode()

# 조정 기록
ADJ={}
for c in CARDS:
    p=PLACE.get(str(c['no']))
    if not p: continue
    if p['kind']!=c['kind']: ADJ[c['no']]='%s → %s 강등 (배경이 안 받침)'%(KIND[c['kind']],KIND[p['kind']])
    elif p.get('shift',0)>0: ADJ[c['no']]='자리가 없어 시각 +%.1f초'%p['shift']

items=''
for c in CARDS:
    p=PLACE.get(str(c['no']))
    k=p['kind'] if p else 'full'
    t=p['t'] if p else c['at']
    tag=f'<div class="adj">⚠️ {html.escape(ADJ[c["no"]])}</div>' if c['no'] in ADJ else ''
    pos=f'x{p["x"]} y{p["y"]} · {p["w"]}×{p["h"]}' if p else '화면 전체'
    items+=f'''
<figure class="it" id="c{c['no']}">
 <figcaption><span class="no">{c['no']:02d}</span><span class="kd k-{k}">{KIND[k]}</span>
  <span class="tm">{mmss(t)}</span><span class="pos">{pos}</span></figcaption>
 <img src="{b64('chk/c%02d.jpg'%c['no'])}" alt="">
 {tag}
 <div class="txt">{html.escape(c['kicker']+' · ' if c['kicker'] else '')}<b>{html.escape(c['keyword'])}</b>{html.escape(' — '+c['sub'] if c['sub'] else '')}</div>
</figure>'''

H=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>검수 시트 — 인서트컷 72컷</title><style>
:root{{--paper:#F4F1EA;--ink:#16130E;--red:#E8442E;--sub:#5f584d;--line:#ded8cc;--cool:#2d6a7a}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
 font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
 font-size:16px;line-height:1.6;word-break:keep-all}}
.wrap{{max-width:1500px;margin:0 auto;padding:26px 18px 70px}}
h1{{font-size:29px;margin:0 0 8px;letter-spacing:-.03em}}
.kicker{{font-size:12.5px;letter-spacing:.14em;color:var(--red);font-weight:800;margin:0 0 5px}}
.lede{{font-size:15.5px;color:var(--sub);margin:0 0 14px}}
.warn{{background:#fdf0ec;border-left:4px solid var(--red);border-radius:0 10px 10px 0;
 padding:13px 16px;font-size:15px;margin:16px 0}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:18px}}
@media(max-width:1000px){{.grid{{grid-template-columns:1fr}}}}
.it{{margin:0;background:#fff;border:1px solid var(--line);border-radius:14px;padding:11px;
 align-self:start}}
figcaption{{display:flex;align-items:center;gap:7px;margin-bottom:8px;flex-wrap:wrap}}
.no{{background:var(--ink);color:#fff;font-size:13px;font-weight:900;border-radius:6px;padding:3px 9px;
 font-variant-numeric:tabular-nums}}
.kd{{font-size:11.5px;font-weight:800;border-radius:99px;padding:3px 10px;color:#fff}}
.k-sticker{{background:var(--red)}}.k-bento{{background:#a6521a}}.k-rail{{background:var(--cool)}}
.k-daepan{{background:var(--ink)}}.k-terminal{{background:#3d7a4e}}.k-full{{background:#7a2d6a}}
.tm{{font-size:13.5px;font-weight:800;color:var(--cool);font-variant-numeric:tabular-nums}}
.pos{{margin-left:auto;font-size:11.5px;color:#9a938a;font-weight:700}}
.it img{{width:100%;display:block;border-radius:9px}}
.adj{{margin-top:8px;background:#fdf6e3;border:1px solid #e6d9b0;color:#6b4e1e;
 font-size:13px;font-weight:700;border-radius:8px;padding:6px 11px}}
.bugimg{{width:100%;max-width:900px;border-radius:12px;border:1px solid var(--line);display:block;margin:12px 0}}
h2{{font-size:21px;margin:34px 0 6px;padding-top:12px;border-top:2px solid var(--line)}}
table{{width:100%;max-width:900px;border-collapse:collapse;margin-top:10px;font-size:14.5px;background:#fff}}
th,td{{border:1px solid var(--line);padding:7px 12px;text-align:left}}
th{{background:#efebe2;font-size:13px}}
.txt{{margin-top:8px;font-size:14px;color:#3b3630;background:#f4f1ea;border-radius:8px;padding:8px 11px}}
</style></head><body><div class="wrap">
<p class="kicker">내 채널 · 검수 게이트</p>
<h1>검수 시트 — 인서트컷 72컷</h1>
<p class="lede">카드를 <b>그 시각의 진짜 화면에 얹은 그림</b>입니다. 최종 렌더 전 마지막 확인입니다.</p>
<div class="warn"><b>봐주실 것 — 번호로만 말씀해 주세요.</b> 「17번 자리 옮겨」, 「31번 문구 바꿔」, 「44번 빼」.<br>
아래 <b>노란 딱지 {len(ADJ)}건</b>은 제가 자동으로 손댄 것입니다 — 특히 이것만은 꼭 봐주세요.</div>
<h2>채널 버그 + 단원 소제목 9개</h2>
<p class="lede">좌상단 <b>「내 채널」은 0초부터 끝까지 상시</b>, 소제목은 <b>단원이 바뀔 때만</b> 6초씩 뜹니다.
판 폭은 글자 폭을 실측해 정했습니다(324~482px, 제목마다 다름).</p>
<img class="bugimg" src="{{BUGIMG}}" alt="">
<table>{{CHROWS}}</table>
<h2>인서트컷 72컷</h2>
<div class="grid">{items}</div>
</div></body></html>'''
BUG=json.load(open('bug.json',encoding='utf-8'))
CHROWS='<tr><th style="width:110px">시각</th><th>단원 소제목</th><th style="width:110px">판 폭</th></tr>'
for ch in BUG['chapters']:
    CHROWS+='<tr><td class="tm">%s</td><td>%s</td><td>%dpx</td></tr>'%(
        mmss(ch['t']), html.escape(ch['title']), BUG['ch%02d'%ch['i']]['w'])
H=H.replace('{BUGIMG}', b64('bugchk/preview.jpg')).replace('{CHROWS}', CHROWS)
open('검수시트.html','w',encoding='utf-8').write(H)
print('✅ 검수시트.html (%.1fMB) · 조정 %d건'%(os.path.getsize('검수시트.html')/1048576,len(ADJ)))
