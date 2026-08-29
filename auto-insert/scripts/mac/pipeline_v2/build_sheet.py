#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검토 게이트 ① — 인서트컷 검토표.

cards.json 을 «사람이 보고 판정할 수 있는 HTML» 한 장으로 그린다.
숫자(컷 수·길이·구간)는 전부 cards.json 과 SRT 에서 «계산»한다 — 여기에 박아 두지 않는다."""
import os, re, json, html
import sys, os as _os
sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import job
job.chdir()
SRT=job.SRT
def t2s(t):
    h,m,rest=t.split(':'); s,ms=rest.split(',')
    return int(h)*3600+int(m)*60+int(s)+int(ms)/1000
CUES=[]
for blk in re.split(r'\n\s*\n', open(SRT,encoding='utf-8-sig').read()):
    L=[x for x in blk.strip().split('\n') if x.strip()]
    if len(L)<2 or '-->' not in L[1]: continue
    a,b=[x.strip() for x in L[1].split('-->')]
    CUES.append((t2s(a),t2s(b),' '.join(L[2:]).strip()))
END=CUES[-1][1]
CARDS=json.load(open('cards.json',encoding='utf-8'))
if not CARDS: sys.exit('⛔ cards.json 이 비어 있습니다 — build_cards.py 를 먼저 돌리세요.')

# ── 이 회차의 숫자는 «전부 계산해서» 쓴다 ────────────────
N_CUE  = len(CUES)                                   # 자막 큐 수
N_TOT  = len(CARDS)                                  # 설계한 전체 컷
def hhmm(t): return '%d분 %02d초'%(t//60, t%60)
DUR_TXT = hhmm(END)

# 실습(화면공유) 구간 = zone B 카드가 실제로 놓인 범위. B 카드가 없으면 이 절은 통째로 빠진다.
_B=[c for c in CARDS if c['zone']=='B']
PRACTICE = (min(c['at'] for c in _B), max(c['at']+c['dur'] for c in _B)) if _B else None

# 단원표는 chapters.json 이 있으면 거기서 읽는다(broadcast_overlay.py 와 같은 형식).
# 없으면 «회차마다 직접 채우는 빈 표»로 둔다 — 남의 회차 내용을 여기 박아 두지 않는다.
CHAPTERS=[]
if os.path.exists('chapters.json'):
    try:
        CHAPTERS=[(float(c['at']), str(c['title'])) for c in json.load(open('chapters.json',encoding='utf-8'))]
        CHAPTERS.sort()
    except Exception as e:
        print('⚠️ chapters.json 을 읽지 못해 빈 표로 갑니다:', e)

def mmss(t): return '%d:%04.1f'%(t//60,t%60)
def quotes(at,dur,pad=1.2):
    a,b=at-pad,at+dur+pad
    q=' '.join(c[2] for c in CUES if c[0]<b and a<c[1])
    return q[:260]+'…' if len(q)>260 else q

KIND={'sticker':'스티커','bento':'벤토','rail':'세로레일','daepan':'무판대판','terminal':'터미널','full':'풀프레임'}
KCLS={'sticker':'k-st','bento':'k-be','rail':'k-ra','daepan':'k-dp','terminal':'k-te','full':'k-fu'}
ZONE={'A':('강의','z-a'),'B':('실습 · 화면공유','z-b'),'C':('마무리','z-c')}

def mock(c):
    """카드 실제 디자인 미리보기"""
    k,K,S = c['kind'], html.escape(c['keyword']), html.escape(c['sub'])
    kk = html.escape(c['kicker'])
    kick = f'<div class="m-kick">{kk}</div>' if kk else ''
    sub  = f'<div class="m-sub">{S}</div>' if S else ''
    if k=='sticker':  return f'<div class="m m-st">{K}</div>'
    if k=='daepan':   return f'<div class="m m-dp">{kick}<div class="m-key">{K}</div>{sub}</div>'
    if k=='terminal': return f'<div class="m m-te">{kick}<div class="m-key">{K}</div>{sub}</div>'
    if k=='rail':     return f'<div class="m m-ra">{kick}<div class="m-key">{K}</div>{sub}</div>'
    if k=='bento':    return f'<div class="m m-be">{kick}<div class="m-key">{K}</div>{sub}</div>'
    return f'<div class="m m-fu">{kick}<div class="m-key">{K}</div>{sub}</div>'

items=''
for c in CARDS:
    zl,zc = ZONE[c['zone']]
    chk = '' if c['spare'] else ' checked'
    sp  = '<span class="spare">예비</span>' if c['spare'] else ''
    items += f'''
<article class="it {zc}{' on' if not c['spare'] else ''}" id="c{c['no']}" data-zone="{c['zone']}" data-spare="{1 if c['spare'] else 0}">
 <header class="ih"><span class="no">{c['no']:02d}</span>
  <span class="kind {KCLS[c['kind']]}">{KIND[c['kind']]}</span>
  <span class="tm">{mmss(c['at'])}</span><span class="dur">{c['dur']:.1f}초</span>{sp}
  <label class="sw"><input type="checkbox" class="keep"{chk}><span>살림</span></label></header>
 <div class="mock">{mock(c)}</div>
 <div class="q"><span class="ql">이 말에 붙습니다</span>{html.escape(quotes(c['at'],c['dur']))}</div>
</article>'''

DATA=json.dumps([{ 'no':c['no'],'at':c['at'],'dur':c['dur'],'kind':c['kind'],
                   'zone':c['zone'],'key':c['keyword'],'spare':c['spare']} for c in CARDS], ensure_ascii=False)
nA=sum(1 for c in CARDS if c['zone']=='A'); nB=sum(1 for c in CARDS if c['zone']=='B'); nC=sum(1 for c in CARDS if c['zone']=='C')
nSp=sum(1 for c in CARDS if c['spare'])
N_KEEP = N_TOT - nSp
PACE_KEEP = '%.0f'%(END/N_KEEP) if N_KEEP else '—'
PACE_ALL  = '%.0f'%(END/N_TOT)

# ── 단원표 HTML (chapters.json 이 있으면 그것으로, 없으면 빈 표) ──
if CHAPTERS:
    _rows=''.join('<tr><td class="tm">%s</td><td><b>%s</b></td></tr>'%(mmss(a), html.escape(ti))
                  for a,ti in CHAPTERS)
    CHAP_HTML=('<h2>단원 구성</h2>'
      '<p class="note">chapters.json 에서 읽었습니다. 인서트는 이 단원 경계를 넘지 않게 배치합니다.</p>'
      '<table><tr><th style="width:130px">시작</th><th>단원</th></tr>'+_rows+'</table>')
else:
    CHAP_HTML=('<h2>단원 구성</h2>'
      '<p class="note">같은 폴더에 <b>chapters.json</b> 을 두면 여기에 단원표가 그려집니다 — '
      '형식은 <code>[{"at": 23.2, "title": "첫 번째 단원"}]</code>. <b>회차마다 직접 채웁니다.</b></p>'
      '<table><tr><th style="width:130px">시작</th><th>단원</th></tr>'
      '<tr><td class="tm">—</td><td>(chapters.json 없음)</td></tr></table>')

# ── 실습 구간 경고 HTML (zone B 카드가 있을 때만) ──
if PRACTICE:
    _nb = len(_B); _nfull = sum(1 for c in _B if c['kind']=='full')
    PRACTICE_HTML=('<h2>⛔ 실습 구간 %s~%s — 풀프레임 %d개</h2>'%(mmss(PRACTICE[0]),mmss(PRACTICE[1]),_nfull)+
      '<div class="warn">화면공유·실습 구간에는 <b>화면을 덮는 풀프레임을 넣지 않습니다</b>. '
      '지금 이 구간의 <b>%d컷</b> 중 풀프레임은 <b>%d컷</b>입니다%s<br>'%(_nb,_nfull,
        ' — 통과입니다.' if _nfull==0 else ' — ⛔ build_cards.py 에서 종류를 바꿔 주세요.')+
      '① 세로로 긴 자리(얼굴 아래 칸)가 잘 남으므로 이 구간은 <b>세로레일</b> 위주가 안전합니다.<br>'
      '② 최종 자리는 <b>영상이 오면 프레임마다 재서</b> 정합니다(얼굴·기존 자막·화면 글자 회피). '
      '자리를 못 찾으면 시각을 최대 15초까지 밀고, 그래도 없으면 그 컷을 빼고 알려 줍니다.</div>')
else:
    PRACTICE_HTML=''

H=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>인서트컷 검토표 — 예시 회차</title><style>
:root{{--paper:#F4F1EA;--ink:#16130E;--red:#E8442E;--sub:#5f584d;--line:#ded8cc;--card:#fff;
 --cool:#2d6a7a;--gold:#a67c1a;--green:#3d7a4e;--brown:#a6521a}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
 font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
 font-size:16px;line-height:1.65;word-break:keep-all;padding-bottom:96px}}
.wrap{{max-width:1280px;margin:0 auto;padding:26px 18px}}
header.top{{border-bottom:3px solid var(--ink);padding-bottom:14px}}
.kicker{{font-size:12.5px;letter-spacing:.14em;color:var(--red);font-weight:800;margin:0 0 5px}}
h1{{font-size:30px;margin:0 0 8px;letter-spacing:-.03em}}
.lede{{font-size:15.5px;color:var(--sub);margin:0}}
.stamp{{display:inline-block;background:#fdf6e3;border:1px solid #e6d9b0;color:#6b4e1e;
 font-size:12.5px;font-weight:800;padding:5px 12px;border-radius:99px;margin-top:12px}}
h2{{font-size:20px;margin:38px 0 6px;padding-top:12px;border-top:2px solid var(--line)}}
.note{{font-size:14.8px;color:var(--sub);margin:0 0 14px}}
.warn{{background:#fdf0ec;border-left:4px solid var(--red);border-radius:0 10px 10px 0;
 padding:13px 16px;font-size:14.8px;margin:14px 0}}
table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:14.5px;background:var(--card)}}
th,td{{border:1px solid var(--line);padding:8px 12px;text-align:left}}
th{{background:#efebe2;font-size:13px;letter-spacing:.04em}}
.tools{{position:sticky;top:0;z-index:30;background:var(--paper);border-bottom:1px solid var(--line);
 padding:11px 0;margin-top:20px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.tools button{{font:inherit;font-size:13.5px;font-weight:700;padding:7px 13px;border-radius:99px;
 border:1.5px solid var(--ink);background:#fff;color:var(--ink);cursor:pointer}}
.tools button.act{{background:var(--ink);color:#fff}}
.tools .sep{{margin-left:auto;font-size:13.5px;color:var(--sub);font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:16px}}
@media(max-width:940px){{.grid{{grid-template-columns:1fr}}}}
.it{{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:13px;align-self:start;
 opacity:.45;transition:opacity .15s,box-shadow .15s}}
.it.on{{opacity:1;box-shadow:0 1px 0 rgba(0,0,0,.05)}}
.it.z-b{{border-left:5px solid var(--cool)}}
.it.z-a{{border-left:5px solid var(--gold)}}
.it.z-c{{border-left:5px solid var(--green)}}
.ih{{display:flex;align-items:center;gap:7px;margin-bottom:10px;flex-wrap:wrap}}
.no{{background:var(--ink);color:#fff;font-size:13px;font-weight:900;border-radius:6px;padding:3px 9px;
 font-variant-numeric:tabular-nums}}
.kind{{font-size:11.5px;font-weight:800;border-radius:99px;padding:3px 10px;color:#fff}}
.k-st{{background:var(--red)}}.k-be{{background:var(--brown)}}.k-ra{{background:var(--cool)}}
.k-dp{{background:var(--ink)}}.k-te{{background:var(--green)}}.k-fu{{background:#7a2d6a}}
.tm{{font-size:13.5px;font-weight:800;color:var(--cool);font-variant-numeric:tabular-nums}}
.dur{{font-size:12px;color:#9a938a;font-weight:700}}
.spare{{font-size:11px;font-weight:800;color:#8a7f6c;background:#efebe2;border-radius:99px;padding:2px 8px}}
.sw{{margin-left:auto;display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none;
 font-size:13px;font-weight:800}}
.sw input{{width:17px;height:17px;accent-color:var(--red);cursor:pointer}}
.mock{{background:#2a2621;border-radius:11px;padding:20px 18px;min-height:104px;
 display:flex;align-items:center;justify-content:center}}
.m{{width:100%}}
.m-kick{{font-size:11.5px;letter-spacing:.11em;font-weight:800;color:var(--red);margin-bottom:5px}}
.m-key{{font-size:21px;font-weight:900;letter-spacing:-.025em;line-height:1.32}}
.m-sub{{font-size:13px;margin-top:6px;line-height:1.5;opacity:.85}}
.m-st{{display:inline-block;background:var(--red);color:#fff;font-size:17px;font-weight:900;
 border-radius:10px;padding:9px 15px;width:auto}}
.m-dp{{color:#fff}}.m-dp .m-key{{font-size:25px}}
.m-te{{background:#12100d;border:1px solid #3a352c;border-radius:8px;padding:12px 14px;color:#8fdca0;
 font-family:ui-monospace,Menlo,monospace}}.m-te .m-key{{font-size:18px;color:#d8f5e0}}
.m-ra{{border-left:5px solid var(--red);padding-left:13px;color:#fff}}
.m-be{{background:var(--paper);color:var(--ink);border-radius:9px;padding:13px 15px}}
.m-be .m-sub{{color:var(--sub);opacity:1}}
.m-fu{{background:var(--paper);color:var(--ink);border-radius:6px;padding:17px 18px;text-align:center}}
.m-fu .m-key{{font-size:23px}}.m-fu .m-sub{{color:var(--sub);opacity:1}}
.q{{margin-top:10px;background:#f4f1ea;border-left:4px solid var(--cool);border-radius:0 9px 9px 0;
 padding:9px 12px;font-size:13.4px;color:#3b3630;line-height:1.6}}
.ql{{display:block;font-size:10.5px;font-weight:900;letter-spacing:.09em;color:var(--cool);margin-bottom:3px}}
.foot{{position:fixed;left:0;right:0;bottom:0;z-index:40;background:rgba(22,19,14,.97);color:#fff;
 padding:12px 18px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}}
.foot .st{{font-size:14px;font-weight:700}}.foot .st b{{color:#FFB4A2;font-size:16px}}
.foot button{{margin-left:auto;font:inherit;font-size:15px;font-weight:800;padding:10px 22px;
 border-radius:99px;border:0;background:var(--red);color:#fff;cursor:pointer}}
.foot button:disabled{{opacity:.5;cursor:not-allowed}}
.toast{{position:fixed;left:50%;bottom:78px;transform:translateX(-50%) translateY(12px);z-index:50;
 background:var(--ink);color:#fff;padding:11px 20px;border-radius:99px;font-size:14.5px;font-weight:700;
 opacity:0;pointer-events:none;transition:.2s}}
.toast.show{{opacity:1;transform:translateX(-50%) translateY(0)}}
.toast.err{{background:var(--red)}}
.ask{{background:var(--ink);color:#fff;border-radius:15px;padding:22px 26px;margin-top:34px}}
.ask h3{{margin:0 0 12px;font-size:19px;color:#fff}}
.ask ol{{margin:0;padding-left:20px}}.ask li{{margin-bottom:9px;font-size:15px;color:#eae6dd}}
.ask b{{color:#FFB4A2}}
</style></head><body><div class="wrap">
<header class="top">
<p class="kicker">검토 게이트 ①</p>
<h1>인서트컷 검토표 — 예시 회차</h1>
<p class="lede">영상이 오기 전에 <b>무엇을 · 언제 · 어떤 종류로</b> 넣을지 먼저 정합니다.
카드마다 <b>실제 디자인 미리보기</b>와 <b>근거가 된 실제 대사</b>를 붙였습니다.<br>
자리·색은 영상이 오면 배경을 재서 자동으로 정합니다 — 지금 봐주실 건 <b>문구와 종류</b>입니다.</p>
<span class="stamp">자막 {N_CUE}큐 · {DUR_TXT} · {N_TOT}컷 설계 (예비 {nSp}컷 포함)</span>
</header>

{CHAP_HTML}
{PRACTICE_HTML}

<div class="tools">
 <button data-f="all" class="act">전체 {N_TOT}</button>
 <button data-f="A">강의 {nA}</button>
 <button data-f="B">실습 {nB}</button>
 <button data-f="C">마무리 {nC}</button>
 <button id="allon">전부 켜기</button>
 <button id="lite">추천 상태로 되돌리기</button>
 <span class="sep" id="pace"></span>
</div>

<div class="grid">{items}</div>

<div class="ask">
 <h3>봐주실 것</h3>
 <ol>
  <li><b>「살림」 체크만 하시면 됩니다.</b> 다 고르신 뒤 아래 <b>「결정 복사하기」</b>를 누르고 저에게 붙여넣어 주세요.</li>
  <li>제일 중요한 건 <b>문구가 대사와 맞는지</b>입니다. 카드 아래 파란 상자가 그 시각의 실제 대사입니다.</li>
  <li>문구를 고치실 땐 <b>번호로</b> 말씀해 주세요 — 「31번 문구 이렇게 바꿔」.</li>
  <li>지금은 <b>추천 {N_KEEP}컷</b>으로 열립니다 = <b>{PACE_KEEP}초에 한 컷</b>. <b>예비 {nSp}컷</b>은 꺼둔 채로 회색 표시했으니 필요하면 켜주세요 (전부 켜면 {N_TOT}컷 = {PACE_ALL}초에 한 컷).</li>
  <li>렌더가 끝나면 <b>자리·색을 재서</b> 화면에 얹은 <b>검수 시트</b>를 다시 만들고, 승인 후 최종 렌더합니다.</li>
 </ol>
</div>
</div>
<div class="foot"><span class="st">살림 <b id="sON">0</b>컷 · 실습 <b id="sB">0</b>컷 · <span id="sPace"></span></span>
<button id="copy">결정 복사하기</button></div>
<div class="toast" id="toast"></div>
<script>
const ITEMS={DATA}, DUR={END:.2f};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let busy=false;
function keptOf(){{return ITEMS.filter(it=>document.getElementById('c'+it.no).querySelector('.keep').checked);}}
function render(){{
  ITEMS.forEach(it=>{{const el=document.getElementById('c'+it.no);
    el.classList.toggle('on', el.querySelector('.keep').checked);}});
  const k=keptOf(), b=k.filter(x=>x.zone==='B').length;
  const pace = k.length? (DUR/k.length).toFixed(1)+'초에 한 컷' : '—';
  $('#sON').textContent=k.length; $('#sB').textContent=b;
  $('#sPace').textContent=pace; $('#pace').textContent='살림 '+k.length+'컷 · '+pace;
  try{{localStorage.setItem('autoedit_cards', JSON.stringify(k.map(x=>x.no)));}}catch(e){{}}
}}
function toast(m,err){{const t=$('#toast');t.textContent=m;t.className='toast show'+(err?' err':'');
  setTimeout(()=>t.className='toast',2300);}}
$$('.keep').forEach(el=>el.addEventListener('change',render));
$$('.tools button[data-f]').forEach(b=>b.addEventListener('click',()=>{{
  $$('.tools button[data-f]').forEach(x=>x.classList.remove('act')); b.classList.add('act');
  const f=b.dataset.f;
  $$('.it').forEach(el=>{{el.style.display = (f==='all'||el.dataset.zone===f)?'':'none';}});
}}));
$('#allon').addEventListener('click',()=>{{$$('.keep').forEach(c=>c.checked=true);render();toast('전부 켰습니다');}});
$('#lite').addEventListener('click',()=>{{
  ITEMS.forEach(it=>{{document.getElementById('c'+it.no).querySelector('.keep').checked = !it.spare;}});
  render(); toast('추천 {N_KEEP}컷으로 되돌렸습니다');}});
try{{const s=JSON.parse(localStorage.getItem('autoedit_cards')||'null');
  if(s){{const m=new Set(s); ITEMS.forEach(it=>
      document.getElementById('c'+it.no).querySelector('.keep').checked=m.has(it.no));
    toast('지난번 선택을 불러왔습니다');}}}}catch(e){{}}
render();
$('#copy').addEventListener('click', async e=>{{
  if(busy) return; busy=true;
  const btn=e.currentTarget, old=btn.textContent;
  btn.disabled=true; btn.textContent='복사 중…';
  try{{
    const k=keptOf().sort((a,b)=>a.at-b.at);
    const mm=t=>Math.floor(t/60)+':'+(t%60).toFixed(1).padStart(4,'0');
    const txt='인서트컷 결정 · 예시 회차 | 살림 '+k.length+'컷 (실습 '
      +k.filter(x=>x.zone==='B').length+') | '
      + k.map(x=>x.no+'@'+mm(x.at)+':'+x.kind).join(' ')
      + ' | 뺀 컷 '+ITEMS.filter(x=>!k.includes(x)).map(x=>x.no).join(',');
    await navigator.clipboard.writeText(txt);
    toast('복사했습니다 — 클로드에게 붙여넣어 주세요');
  }}catch(err){{
    toast('복사 실패 — 아래 줄을 직접 긁어 주세요',1);
    const p=document.createElement('pre');
    p.style.cssText='user-select:all;padding:14px;background:#fff;border-radius:10px;white-space:pre-wrap';
    p.textContent=keptOf().map(x=>x.no).join(',');
    $('.wrap').appendChild(p); p.scrollIntoView({{behavior:'smooth'}});
  }} finally {{ btn.disabled=false; btn.textContent=old; busy=false; }}
}});
</script></body></html>'''
open('검토표_인서트컷.html','w',encoding='utf-8').write(H)
print('✅ 검토표_인서트컷.html (%.0fKB) · %d컷'%(os.path.getsize('검토표_인서트컷.html')/1024,len(CARDS)))
