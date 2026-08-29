#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검토 게이트 ② — OTS 카드 검수 시트.

«실제 화면에 카드를 얹은 그림»을 카드 수만큼 만들어 한 장의 HTML 로 묶는다.
사람이 번호로 지적하라고 있는 단계다. ⛔자동으로 통과시키지 않는다.

사용:
  python3 build_sheet.py [--video 영상.mp4] [--srt 자막.srt]
                         [--plan plan_check.json] [--cards check_cards.json]
                         [--out 검수시트.html]

입력을 만드는 사람:
  plan_check.json · check_cards.json → approve.py
  fin/<카드id>.png                    → cards_v2.py
숫자(길이·해상도·카드 수·간격)는 전부 «여기서 계산»한다 — 회차 값을 박아 두지 않는다.
"""
import os, re, json, html, sys, argparse, subprocess
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cards_v2 import SIZE                      # 종류별 (본체폭, 본체높이, 여백)

# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF = ff_path.FFMPEG
FP = ff_path.FFPROBE

ap = argparse.ArgumentParser(description='OTS 카드 검수 시트 HTML 을 만든다')
ap.add_argument('--video', default=os.environ.get('OTS_VIDEO', 'source.mp4'),
                help='자막이 구워진 원본 영상 (기본: $OTS_VIDEO 또는 source.mp4)')
ap.add_argument('--srt',   default=os.environ.get('OTS_SRT', 'captions.srt'),
                help='자막 SRT — 카드 옆에 «이 말에 붙습니다»로 보여준다')
ap.add_argument('--plan',  default='plan_check.json', help='approve.py 가 만든 배치 계획')
ap.add_argument('--cards', default='check_cards.json', help='approve.py 가 만든 카드 목록')
ap.add_argument('--pngdir', default='fin', help='cards_v2.py 가 구운 카드 PNG 폴더')
ap.add_argument('--out',   default='검수시트.html')
ap.add_argument('--rebuild', action='store_true',
                help='sheet/ 의 그림을 무조건 다시 굽는다 (기본도 카드 PNG 가 더 새것이면 다시 굽는다)')
a = ap.parse_args()

def need(path, who):
    if not os.path.exists(path):
        sys.exit('⛔ %s 이(가) 없습니다.\n   → %s' % (path, who))

need(a.srt,   '자막 파일 경로를 --srt 로 알려 주세요 (whisper 등으로 먼저 만듭니다)')
need(a.plan,  'python3 approve.py --cards cards.json --plan plan_out.json  을 먼저 돌리세요')
need(a.cards, 'python3 approve.py --cards cards.json --plan plan_out.json  을 먼저 돌리세요')
need(a.video, '영상 경로를 --video 로 알려 주세요 (또는 $OTS_VIDEO)')

def t2s(t):
    h,m,r=t.split(':'); s,ms=r.split(',')
    return int(h)*3600+int(m)*60+int(s)+int(ms)/1000
CUES=[]
for blk in re.split(r'\n\s*\n', open(a.srt,encoding='utf-8-sig').read()):
    L=[x for x in blk.strip().split('\n') if x.strip()]
    if len(L)<2 or '-->' not in L[1]: continue
    x,y=[t.strip() for t in L[1].split('-->')]
    CUES.append((t2s(x),t2s(y),' '.join(L[2:])))

P     = json.load(open(a.plan,encoding='utf-8'))
CARDS = {c['id']:c for c in json.load(open(a.cards,encoding='utf-8'))}
if not P: sys.exit('⛔ %s 에 카드가 한 장도 없습니다.'%a.plan)
KIND={'sticker':'스티커','bento':'벤토','rail':'세로레일','daepan':'무판대판','terminal':'터미널'}
KCLS={'sticker':'k-st','bento':'k-be','rail':'k-ra','daepan':'k-dp','terminal':'k-te'}

os.makedirs('sheet', exist_ok=True)
def mmss(t): return '%d:%04.1f'%(t//60,t%60)

# ── 영상 제원은 «파일에서 읽는다» ────────────────────────
def probe(*ent):
    r = subprocess.run([FP,'-v','error','-select_streams','v:0','-show_entries',
                        ','.join(ent),'-of','csv=p=0:s=x',a.video],
                       capture_output=True,text=True)
    return r.stdout.strip()
try:
    VW,VH = [int(float(x)) for x in probe('stream=width,height').split('x')[:2]]
except Exception:
    VW,VH = 0,0
try:
    VDUR = float(subprocess.run([FP,'-v','error','-show_entries','format=duration',
                                 '-of','csv=p=0',a.video],capture_output=True,text=True).stdout.strip())
except Exception:
    VDUR = CUES[-1][1] if CUES else 0.0

# ── 카드를 «실제 화면에 얹은» 그림을 만든다 (없을 때만) ──
def compose(r, c, web):
    """원본에서 카드 시각의 한 프레임을 뽑아 그 위에 카드 PNG 를 얹는다."""
    png = os.path.join(a.pngdir, '%s.png'%r['id'])
    at  = c['at'] + c.get('dur',6)/2.0            # 스팬 한가운데
    if not os.path.exists(png):
        # 카드 PNG 가 아직 없으면 «맨 화면»이라도 보여 준다
        subprocess.run([FF,'-v','error','-ss','%.3f'%at,'-i',a.video,'-frames:v','1',
                        '-vf','scale=1180:-2','-q:v','4','-y',web],check=True)
        return False
    pad = r.get('pad')
    if pad is None:                                # 카드 PNG 는 그림자용 여백을 두르고 있다
        pad = round(SIZE[r['kind']][2] * r.get('scale',1.0))
    x, y = int(r['x'])-int(pad), int(r['y'])-int(pad)
    subprocess.run([FF,'-v','error','-ss','%.3f'%at,'-i',a.video,'-i',png,
                    '-filter_complex','[0:v][1:v]overlay=%d:%d[o];[o]scale=1180:-2[s]'%(x,y),
                    '-map','[s]','-frames:v','1','-q:v','4','-y',web],check=True)
    return True

items=''; made=0; nocard=[]
for i,r in enumerate(P,1):
    c=CARDS.get(r['id'])
    if c is None:
        sys.exit('⛔ %s 에 %s 카드가 없습니다 — approve.py 를 다시 돌리세요.'%(a.cards, r['id']))
    web='sheet/%s.jpg'%r['id']
    # ⛔⛔ 여기서 «이미 있으면 건너뛰기»를 하면 카드를 새로 구워도 시트는 «옛 그림»을 보여준다.
    #     이 시트는 사람이 보고 승인하는 화면이다 — 승인 화면이 틀리면 도구 전체의 전제가 무너진다.
    #     그래서 카드 PNG 가 더 새것이면 반드시 다시 굽는다. 애매하면 «다시 굽는» 쪽을 고른다.
    png = os.path.join(a.pngdir, '%s.png'%r['id'])
    stale = True
    if os.path.exists(web) and not a.rebuild:
        srcs = [p for p in (png, a.video) if os.path.exists(p)]
        stale = any(os.path.getmtime(p) > os.path.getmtime(web) for p in srcs)
    if stale or a.rebuild:
        src_jpg = os.path.join(a.pngdir,'%s.jpg'%r['id'])
        if os.path.exists(src_jpg):               # 이미 얹은 그림이 있으면 그걸 줄이기만
            subprocess.run([FF,'-v','error','-i',src_jpg,'-vf','scale=1180:-2',
                            '-q:v','4','-y',web],check=True)
        else:
            if not compose(r,c,web): nocard.append(r['id'])
        made+=1
    elif not os.path.exists(png):
        nocard.append(r['id'])
    at,bt=c['at'],c['at']+c.get('dur',6)
    q=' '.join(x[2] for x in CUES if x[0]<bt+1 and at-1<x[1])
    if len(q)>230: q=q[:230]+'…'
    mode = ('<span class="md">%s</span>'%r['mode']) if r.get('mode') else ''
    sc = r.get('sub_clear')
    scs = ('<span class="cl">자막여유 %.0fpx</span>'%sc) if isinstance(sc,(int,float)) else ''
    items+=f'''
<div class="it">
 <div class="ih"><span class="no">{i:02d}</span><span class="kind {KCLS[c['kind']]}">{KIND[c['kind']]}</span>
  {mode}<span class="tm">{mmss(at)} ~ {mmss(bt)}</span>
  <span class="sp">{html.escape(str(r.get('spot','—')))}</span>{scs}</div>
 <img src="{web}" alt="">
 <div class="q"><span class="ql">이 말에 붙습니다</span>{html.escape(q)}</div>
</div>'''

# ── 안전 점검도 «계산해서» 채운다 ────────────────────────
subs = [r['sub_clear'] for r in P if isinstance(r.get('sub_clear'),(int,float))]
worst_sub = min(subs) if subs else None
by_kind = Counter(c['kind'] for c in CARDS.values() if c['id'] in {r['id'] for r in P})
modes   = Counter(r['mode'] for r in P if r.get('mode'))
seq = sorted(((CARDS[r['id']]['at'], CARDS[r['id']]['at']+CARDS[r['id']].get('dur',6)) for r in P))
gaps = [b0-a1 for (a0,a1),(b0,b1) in zip(seq,seq[1:])]
min_gap = min(gaps) if gaps else None
avg_gap = (sum(b0-a0 for (a0,a1),(b0,b1) in zip(seq,seq[1:]))/len(gaps)) if gaps else None
shifted = [r['id'] for r in P if CARDS[r['id']].get('shifted')]

def row(name, ok, txt):
    cls = 'ok' if ok else 'bad'
    mark = '✅' if ok else '⛔'
    return '<tr><td>%s</td><td class="%s">%s</td><td>%s</td></tr>'%(name,cls,mark,txt)

checks  = row('본 자막 침범',
              worst_sub is None or worst_sub >= 0,
              ('제일 빠듯한 카드의 자막 여유 <b>%.0fpx</b>'%worst_sub) if worst_sub is not None
              else '측정값이 없습니다 (plan 에 sub_clear 가 없음)')
checks += row('카드 간 최소 간격', min_gap is None or min_gap >= 0,
              ('제일 좁은 간격 <b>%.1f초</b>'%min_gap + (' · 평균 %.0f초에 한 장'%avg_gap if avg_gap else ''))
              if min_gap is not None else '카드가 한 장뿐입니다')
checks += row('카드 PNG', not nocard,
              '전부 준비됐습니다' if not nocard
              else '없는 카드: <b>%s</b> — cards_v2.py 를 먼저 돌리세요'%', '.join(nocard))
checks += row('금지 구간 회피로 밀린 카드', True,
              '없음' if not shifted else '<b>%s</b> (approve.py 가 밀었습니다 — 자리가 맞는지 봐주세요)'%', '.join(shifted))

kind_txt = ' · '.join('%s %d'%(KIND[k],n) for k,n in by_kind.most_common())
mode_txt = (' &nbsp;|&nbsp; 대판 모드: ' + ' · '.join('%s %d'%(m,n) for m,n in modes.most_common())) if modes else ''
STAMP = '%dx%d · %.1f초 · 카드 %d장'%(VW,VH,VDUR,len(P)) if VW else '%.1f초 · 카드 %d장'%(VDUR,len(P))

H=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OTS 카드 검수 시트</title><style>
:root{{--ink:#1a1a1a;--sub:#5a5a5a;--line:#e2e0dc;--paper:#faf8f5;--card:#fff;
 --hot:#c8442e;--hot-bg:#fdf0ec;--cool:#2d6a7a;--cool-bg:#eaf3f5;--gold:#a67c1a;--gold-bg:#fdf6e3;
 --green:#3d7a4e;--dark:#16130E}}
*{{box-sizing:border-box}}
body{{margin:0;background:#0e0c0a;color:#eae6dd;
 font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
 font-size:16px;line-height:1.6;word-break:keep-all}}
.wrap{{max-width:1320px;margin:0 auto;padding:26px 20px 90px}}
header{{border-bottom:3px solid #3a352d;padding-bottom:14px}}
.kicker{{font-size:12.5px;letter-spacing:.13em;color:#FF8A73;font-weight:800;margin:0 0 5px}}
h1{{font-size:29px;margin:0 0 8px;letter-spacing:-.025em;color:#fff}}
.lede{{font-size:15.5px;color:#a9a296;margin:0}}
.stamp{{display:inline-block;background:#2a2318;border:1px solid #5a4a28;color:#e0c98a;
 font-size:12px;font-weight:800;padding:4px 11px;border-radius:99px;margin-top:12px}}
h2{{font-size:20px;margin:40px 0 6px;padding-top:12px;border-top:2px solid #29241d;color:#fff}}
.note{{font-size:14.5px;color:#a9a296;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:14px;background:#17140f}}
th,td{{border:1px solid #2e2820;padding:8px 12px;text-align:left}}
th{{background:#211d17;font-size:12.5px;letter-spacing:.04em;color:#c9c1b2}}
.ok{{color:#7fd39b;font-weight:800}}.bad{{color:#ff8a73;font-weight:800}}
.grid{{display:grid;grid-template-columns:1fr;gap:20px;margin-top:18px}}
.it{{background:#17140f;border:1px solid #2e2820;border-radius:14px;padding:13px}}
.ih{{display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap}}
.no{{background:#E8442E;color:#fff;font-size:15px;font-weight:900;border-radius:7px;padding:3px 11px;
 font-variant-numeric:tabular-nums}}
.kind{{font-size:12px;font-weight:800;border-radius:99px;padding:3px 10px;color:#fff}}
.k-st{{background:#c8442e}}.k-be{{background:#a6521a}}.k-ra{{background:#2d6a7a}}
.k-dp{{background:#4a4238}}.k-te{{background:#3d7a4e}}
.md{{font-size:11.5px;font-weight:800;color:#0e0c0a;background:#e0c98a;border-radius:99px;padding:3px 9px}}
.tm{{font-size:13.5px;font-weight:800;color:#8fd0e0;font-variant-numeric:tabular-nums}}
.sp{{font-size:12px;color:#a9a296;background:#221e18;border-radius:6px;padding:3px 9px}}
.cl{{margin-left:auto;font-size:12px;color:#7fd39b;font-weight:700}}
.it img{{width:100%;display:block;border-radius:9px}}
.q{{margin-top:10px;background:#12100c;border-left:4px solid #2d6a7a;border-radius:0 8px 8px 0;
 padding:9px 13px;font-size:13.4px;color:#bab2a4;line-height:1.6}}
.ql{{display:block;font-size:11px;font-weight:900;letter-spacing:.09em;color:#8fd0e0;margin-bottom:3px}}
.ask{{background:#E8442E;color:#fff;border-radius:14px;padding:22px 26px;margin-top:34px}}
.ask h3{{margin:0 0 12px;font-size:19px;color:#fff}}
.ask ol{{margin:0;padding-left:20px}}.ask li{{margin-bottom:8px;font-size:15px}}
.ask b{{color:#ffe9e4}}
</style></head><body><div class="wrap">
<header>
<p class="kicker">검토 게이트 ② · 최종 렌더 전</p>
<h1>OTS 카드 검수 시트 — {len(P)}장</h1>
<p class="lede"><b>실제 화면에 얹은 그림</b>입니다. 최종 렌더 전 마지막 관문입니다.<br>
<b>번호로 지적해 주세요</b> — 「7번 문구 바꿔」, 「14번 위치 내려」, 「20번 빼」.</p>
<span class="stamp">{STAMP}</span>
</header>

<h2>안전 점검</h2>
<table>
<tr><th style="width:230px">점검 항목</th><th style="width:90px">결과</th><th>내용</th></tr>
{checks}
</table>

<h2>카드 {len(P)}장</h2>
<p class="note">{kind_txt}{mode_txt}</p>
<div class="grid">{items}</div>

<div class="ask">
 <h3>이제 판정입니다</h3>
 <ol>
  <li><b>번호로 말씀해 주세요.</b> 고칠 것만 짚으면 됩니다.</li>
  <li>뺄 카드가 있으면 <code>approve.py --drop 번호</code> 로 다시 만든 뒤 이 시트를 새로 뽑습니다.</li>
  <li>이대로 좋으면 <code>render_ots_v2.py</code> 로 한 패스 렌더합니다.</li>
 </ol>
</div>
</div></body></html>'''
open(a.out,'w',encoding='utf-8').write(H)
print('✅ %s (%.0fKB) · %d장 · 새로 만든 그림 %d장 (그대로 둔 것 %d장)'
      %(a.out, os.path.getsize(a.out)/1024, len(P), made, len(P)-made))
if nocard:
    print('⚠️ 카드 PNG 가 없어 «맨 화면»만 넣은 카드:', ', '.join(nocard))
