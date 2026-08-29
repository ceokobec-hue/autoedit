#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OTS 카드 5종 렌더러.
   스티커 / 벤토(숫자) / 세로레일(공간) / 무판대판(키워드) / 데이터터미널(개발)
   card dict + tone → HTML → 투명 PNG.  ⛔외부 파이썬 패키지 없음."""
import os, sys, subprocess, tempfile, shutil, time, html as _h

# ── 저장소 뿌리의 도우미(ff_path·platform_tools)를 쓰려고 뿌리를 찾아 올라간다 ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import platform_tools

# ⛔ 크롬 위치를 코드에 박지 않는다 — 다른 데 깔았거나 안 깔았을 수 있고, OS 마다 자리도 다르다
CHROME = platform_tools.find_chrome()

# 폰트 창고는 한 곳뿐이다: $AUTOEDIT_FONTS (기본 ~/.autoedit/fonts) — get_fonts.sh 가 채운다.
#   OTS_ASSETS 를 주면 «그 폴더 밑의 fonts/» 를 본다(옛 방식 호환).
_ASSETS_ENV = os.environ.get('OTS_ASSETS')
FONTDIR = (os.path.join(_ASSETS_ENV, 'fonts') if _ASSETS_ENV
           else os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts')))
WOFF2   = ['Pretendard-Regular.woff2', 'Pretendard-Medium.woff2',
           'Pretendard-Bold.woff2',    'Pretendard-Black.woff2']

def check_fonts():
    """⛔ 폰트가 없어도 크롬은 «에러 없이» 시스템 기본 글꼴로 굽는다.

    이 저장소가 traps.md 에서 스스로 제일 무섭다고 한 고장이 바로 이것이다
    (「조용히 폴백된다. 경고도 에러도 없다」). 그래서 «여기서 죽인다»."""
    missing = [f for f in WOFF2 if not os.path.exists(os.path.join(FONTDIR, f))]
    if missing:
        sys.exit('⛔ 카드 폰트(woff2)가 없습니다 — 이대로 구우면 «에러 없이 다른 글꼴»로 나갑니다.\n'
                 '   찾은 곳: %s\n   없는 파일:\n     %s\n'
                 '   → %s\n'
                 '     (다른 곳에 두셨다면  AUTOEDIT_FONTS 환경변수로 알려 주세요)'
                 % (FONTDIR, '\n     '.join(missing), platform_tools.fonts_cmd()))

def check_chrome():
    platform_tools.require_chrome()

SIZE = {                       # 종류별 본체 크기 · 여백(그림자·돌출·스크림용)
    'sticker' : (780,  590, 130),
    'bento'   : (780,  590, 130),
    'rail'    : (470, 1010, 130),
    'terminal': (780,  590, 130),
    'daepan'  : (1700, 430, 400),   # ⛔260이면 그늘이 왼쪽에서 다 사라지기 전에 잘려 칼자국이 생긴다
}

FONTS = """
@font-face{font-family:'Pretendard';src:url('file://%(A)s/Pretendard-Regular.woff2') format('woff2');font-weight:400}
@font-face{font-family:'Pretendard';src:url('file://%(A)s/Pretendard-Medium.woff2') format('woff2');font-weight:500}
@font-face{font-family:'Pretendard';src:url('file://%(A)s/Pretendard-Bold.woff2') format('woff2');font-weight:700}
@font-face{font-family:'Pretendard';src:url('file://%(A)s/Pretendard-Black.woff2') format('woff2');font-weight:900}
"""

BASE = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;width:%(CW)dpx;height:%(CH)dpx}
body{display:flex;align-items:center;justify-content:center;
 font-family:'Pretendard',sans-serif;word-break:keep-all}
:root{--paper:#F4F1EA;--ink:#16130E;--sub:#6E675C;--red:#E8442E;--hair:#C8C1B2}
.grain{position:absolute;inset:0;pointer-events:none;mix-blend-mode:multiply;opacity:.05;
 background-size:420px 420px;background-image:url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='420' height='420'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='420' height='420' filter='url(%%23n)'/></svg>")}
"""

def _rows(rows, cls='row'):
    out=[]
    for r in rows:
        v = ('<span class="v">%s%s</span>' %
             (r['v'], '<em>%s</em>'%r['unit'] if r.get('unit') else '')) if r.get('v') else ''
        out.append('<div class="%s"><span class="t">%s</span>%s</div>' % (cls, r['t'], v))
    return '\n'.join(out)

def _page(kind, css, body):
    w,h,pad = SIZE[kind]
    ctx = dict(A=FONTDIR, CW=w+pad*2, CH=h+pad*2, W=w, H=h)
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>'
            + (FONTS % ctx) + (BASE % ctx) + (css % ctx)
            + '</style></head><body>' + body + '</body></html>')

# ─────────────────────────────────────────────── 1) 스티커 컷아웃 · 일상·에피소드
def sticker(c):
    css = """
.wrap{position:relative;width:%(W)dpx;height:%(H)dpx;flex:none}
.card{position:absolute;left:22px;top:34px;right:22px;bottom:34px;background:var(--paper);
 border:12px solid #fff;border-radius:34px;transform:rotate(-1.6deg);overflow:hidden;
 box-shadow:0 26px 56px rgba(0,0,0,.46)}
.pad{padding:44px 36px 26px;height:100%%;display:flex;flex-direction:column}
.kicker{font-size:25px;font-weight:700;letter-spacing:.20em;color:var(--red);line-height:1}
.head{font-size:52px;font-weight:900;letter-spacing:-.032em;line-height:1.14;margin-top:10px}
.rule{height:6px;background:var(--red);width:96px;margin:18px 0;border-radius:99px}
.rows{display:flex;flex-direction:column;gap:13px;flex:1}
.row{display:flex;align-items:baseline;gap:16px;border-bottom:1px solid var(--hair);padding-bottom:11px}
.row:last-child{border-bottom:0}
.row .t{font-size:32px;font-weight:700;flex:1}
.row .v{font-size:44px;font-weight:900;letter-spacing:-.02em;white-space:nowrap;font-feature-settings:'tnum'}
.row .v em{font-style:normal;font-size:26px;font-weight:700;color:var(--sub);
 display:inline-block;letter-spacing:normal;margin-left:.42em}  /* ⛔margin 5px 은 44px 글자 옆에서 0이나 마찬가지 → 제 크기 기준(.42em)으로 띄운다 */
.foot{margin-top:auto;padding-top:14px;border-top:2px solid var(--ink);font-size:20px;font-weight:500;
 letter-spacing:.06em;color:var(--sub);display:flex;justify-content:space-between}
.tag{position:absolute;left:-14px;top:-6px;background:var(--red);color:#fff;z-index:4;
 font-size:26px;font-weight:900;letter-spacing:.14em;padding:14px 26px;border-radius:99px;
 border:6px solid #fff;transform:rotate(-6deg);box-shadow:0 12px 26px rgba(0,0,0,.4)}
.st{position:absolute;z-index:5;background:#fff;border-radius:50%%;display:flex;
 align-items:center;justify-content:center;box-shadow:0 12px 26px rgba(0,0,0,.38)}
.st1{right:-16px;top:60px;width:124px;height:124px;font-size:64px;transform:rotate(9deg)}
.st2{right:56px;bottom:2px;width:88px;height:88px;font-size:44px;transform:rotate(-11deg)}
"""
    b = ['<div class="wrap"><div class="card"><div class="pad">']
    b.append('<div class="kicker">%s</div>' % c.get('kicker',''))
    b.append('<div class="head">%s</div><div class="rule"></div>' % c['head'])
    b.append('<div class="rows">%s</div>' % _rows(c.get('rows',[])))
    b.append('<div class="foot"><span>%s</span><span>%s</span></div>'
             % (c.get('foot',''), c.get('src','내 채널')))
    b.append('</div><div class="grain"></div></div>')
    if c.get('tag'):   b.append('<div class="tag">%s</div>' % c['tag'])
    if c.get('emoji'): b.append('<div class="st st1">%s</div>' % c['emoji'])
    if c.get('emoji2'):b.append('<div class="st st2">%s</div>' % c['emoji2'])
    b.append('</div>')
    return _page('sticker', css, ''.join(b))

# ─────────────────────────────────────────────── 2) 벤토 그리드 · 숫자 전용
def bento(c):
    rows = c.get('rows',[])[:2]          # 히어로 + 숫자 2칸이 이 판의 정원
    css = """
.wrap{position:relative;width:%(W)dpx;height:%(H)dpx;flex:none;display:grid;gap:14px;
 grid-template-columns:1fr 1fr;grid-template-rows:auto 1fr auto;
 filter:drop-shadow(0 30px 66px rgba(0,0,0,.5))}
.b{background:var(--paper);border-radius:26px;padding:26px 28px;position:relative;overflow:hidden}
.b.hero{grid-column:1/3;padding:32px 32px 28px}
.b.red{background:var(--red);color:#fff}
.b.ink{background:var(--ink);color:#fff}
.b.wide{grid-column:1/3;display:flex;justify-content:space-between;align-items:center;padding:20px 30px}
.kicker{font-size:25px;font-weight:700;letter-spacing:.20em;color:var(--red);margin-bottom:12px}
.head{font-size:56px;font-weight:900;letter-spacing:-.032em;line-height:1.12}
.lbl{font-size:24px;font-weight:700;opacity:.72;letter-spacing:.04em}
.num{font-size:82px;font-weight:900;letter-spacing:-.04em;line-height:1.05;margin-top:6px;
 font-feature-settings:'tnum'}
.num.txt{font-size:50px;letter-spacing:-.03em;line-height:1.14;margin-top:10px}
.num.txt.long{font-size:38px}
.num em{font-style:normal;font-size:30px;font-weight:700;opacity:.72;
 display:inline-block;letter-spacing:normal;margin-left:.32em}
.fw{font-size:21px;font-weight:600;letter-spacing:.05em;color:var(--sub)}
.emo{position:absolute;right:18px;bottom:6px;font-size:80px;opacity:.22}
"""
    cells=''
    for i,r in enumerate(rows):
        v = str(r.get('v',''))
        # 숫자가 아니면 82px로는 넘친다 → 글자용 크기로 내린다
        if any(ch.isdigit() for ch in v): ncls='num'
        elif len(v) > 4:                  ncls='num txt long'
        else:                             ncls='num txt'
        cells += ('<div class="b %s"><div class="lbl">%s</div><div class="%s">%s%s</div></div>'
                  % ('red' if i==0 else 'ink', r['t'], ncls, v,
                     '<em>%s</em>'%r['unit'] if r.get('unit') else ''))
    b = ('<div class="wrap">'
         '<div class="b hero"><div class="kicker">%s</div><div class="head">%s</div>%s</div>'
         '%s'
         '<div class="b wide"><span class="fw">%s</span><span class="fw">%s</span></div></div>'
         % (c.get('kicker',''), c['head'],
            '<div class="emo">%s</div>'%c['emoji'] if c.get('emoji') else '',
            cells, c.get('foot',''), c.get('src','내 채널')))
    return _page('bento', css, b)

# ─────────────────────────────────────────────── 3) 세로 레일 · 자리 없을 때·정보 3개+
def rail(c):
    rows  = c.get('rows',[])[:5]      # ⛔4개로 자르면 「원본 대조 체크리스트 5」가 잘린다
    tight = len(rows) >= 5            # 5행이면 좁혀야 판 밖으로 안 넘친다
    css = """
.rail{position:relative;width:%(W)dpx;height:%(H)dpx;flex:none;border-radius:44px;overflow:hidden;
 background:linear-gradient(180deg,rgba(16,19,18,.93),rgba(22,27,25,.88));color:#fff;
 border:1px solid rgba(255,255,255,.16);
 box-shadow:0 40px 90px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.14)}
.bar{position:absolute;left:0;top:0;bottom:0;width:8px;background:var(--red);z-index:3}
.hd{padding:38px 34px 26px;border-bottom:1px solid rgba(255,255,255,.14)}
.emo{font-size:76px;line-height:1;margin-bottom:20px}
.k{font-size:23px;font-weight:700;letter-spacing:.16em;color:var(--red)}
.h{font-size:52px;font-weight:900;letter-spacing:-.03em;line-height:1.12;margin-top:12px}
.bd{padding:14px 34px}
.it{padding:26px 0;border-bottom:1px solid rgba(255,255,255,.12)}
.it:last-child{border-bottom:0}
.l{font-size:24px;font-weight:600;color:#9AA5A0;letter-spacing:.04em}
.n{font-size:74px;font-weight:900;letter-spacing:-.045em;line-height:1.05;margin-top:4px;
 font-feature-settings:'tnum'}
.n em{font-style:normal;font-size:28px;font-weight:700;color:#9AA5A0;
 display:inline-block;letter-spacing:normal;margin-left:.32em}
.ft{position:absolute;left:0;right:0;bottom:0;padding:22px 34px;font-size:19px;font-weight:600;
 letter-spacing:.08em;color:#8A948F;border-top:1px solid rgba(255,255,255,.14)}
""" + ("""
.hd{padding:28px 34px 20px}
.emo{font-size:58px;margin-bottom:14px}
.h{font-size:44px}
.it{padding:15px 0}
.l{font-size:21px}
.n{font-size:52px}
.n em{font-size:23px}
""" if tight else "")
    items=''.join('<div class="it"><div class="l">%s</div><div class="n">%s%s</div></div>'
                  % (r['t'], r.get('v',''), '<em>%s</em>'%r['unit'] if r.get('unit') else '')
                  for r in rows)
    b = ('<div class="rail"><div class="bar"></div>'
         '<div class="hd">%s<div class="k">%s</div><div class="h">%s</div></div>'
         '<div class="bd">%s</div><div class="ft">%s</div></div>'
         % ('<div class="emo">%s</div>'%c['emoji'] if c.get('emoji') else '',
            c.get('kicker',''), c['head'], items,
            ' · '.join(x for x in [c.get('foot',''), c.get('src','내 채널')] if x)))
    return _page('rail', css, b)

# ─────────────────────────────────────────────── 4) 데이터 터미널 · 개발·기술 설명
def terminal(c):
    css = """
.wrap{position:relative;width:%(W)dpx;height:%(H)dpx;flex:none;
 filter:drop-shadow(0 28px 60px rgba(0,0,0,.55))}
.card{position:absolute;inset:0;background:rgba(14,17,20,.93);border-radius:18px;
 border:1px solid rgba(120,255,200,.22);overflow:hidden;color:#DCE6E2}
.bar{height:52px;background:rgba(255,255,255,.045);display:flex;align-items:center;
 padding:0 22px;gap:10px;border-bottom:1px solid rgba(255,255,255,.10);
 font-family:'SF Mono','Menlo',monospace;font-size:19px;letter-spacing:.10em;color:#6BE3A8}
.dot{width:11px;height:11px;border-radius:50%%;background:#FF5F57}
.dot2{background:#FEBC2E}.dot3{background:#28C840}
.pad{padding:30px 26px 24px;height:calc(100%% - 52px);display:flex;flex-direction:column}
.kicker{font-family:'SF Mono',monospace;color:#6BE3A8;font-size:21px;letter-spacing:.08em}
.head{color:#fff;margin-top:14px;font-size:50px;font-weight:900;letter-spacing:-.03em;line-height:1.14}
.rows{flex:1;margin-top:26px}
.row{border-bottom:1px dashed rgba(255,255,255,.16);padding:16px 0;display:flex;
 align-items:center;gap:16px}
.row:last-child{border-bottom:0}
.row .t{color:#95A29D;font-weight:500;font-size:29px;flex:1}
.row .v{color:#6BE3A8;font-family:'SF Mono',monospace;font-size:46px;font-weight:700;white-space:nowrap}
.row .v em{color:#5A6B64;font-family:'Pretendard',sans-serif;font-style:normal;
 font-size:26px;margin-left:5px}
.foot{margin-top:auto;border-top:1px solid rgba(255,255,255,.14);color:#5A6B64;padding-top:14px;
 font-family:'SF Mono',monospace;font-size:18px;display:flex;justify-content:space-between}
"""
    b = ('<div class="wrap"><div class="card">'
         '<div class="bar"><span class="dot"></span><span class="dot dot2"></span>'
         '<span class="dot dot3"></span><span style="margin-left:12px">%s</span></div>'
         '<div class="pad"><div class="kicker">&gt; %s</div><div class="head">%s</div>'
         '<div class="rows">%s</div>'
         '<div class="foot"><span>%s</span><span>%s</span></div></div></div></div>'
         % (c.get('path','~/'), c.get('kicker',''), c['head'],
            _rows(c.get('rows',[])), c.get('foot',''), c.get('src','내 채널')))
    return _page('terminal', css, b)

# ─────────────────────────────────────────────── 5) 무판 대판 · 큰 키워드
# mode: 'ink'(밝고 깨끗한 배경) / 'white'(어둡고 깨끗) / 'scrim'(얼룩 — 어디서나 안전)
# 그늘(스크림) 기하 — ⛔«중심 %% ≥ 반지름 %%» 이 아니면 가장자리에서 0이 안 돼 칼자국이 남는다.
#   요소 2460 폭(1700+380·2) · 가로반지름 43%% · 중심 44%% → 왼쪽 도달점 1%% (요소 안에서 소멸) ✓
#   세로는 -150 으로 조여 자막 띠(y1152)에 안 닿는다.
SCRIM = """.scrim{position:absolute;left:-380px;right:-380px;top:-150px;bottom:-150px;z-index:0;
 background:radial-gradient(ellipse 43%% 46%% at 44%% 50%%,
   rgba(0,0,0,.90) 0%%, rgba(0,0,0,.88) 40%%, rgba(0,0,0,.80) 58%%,
   rgba(0,0,0,.55) 74%%, rgba(0,0,0,.25) 86%%, rgba(0,0,0,.06) 94%%, rgba(0,0,0,0) 100%%)}"""

def daepan(c, mode='ink'):
    tone = {
     'ink':   """.d{color:var(--ink)}
.k{color:var(--red);text-shadow:0 2px 10px rgba(255,255,255,.9)}
.w{text-shadow:0 2px 0 rgba(255,255,255,.75),0 4px 22px rgba(255,255,255,.85)}
.r{box-shadow:0 3px 12px rgba(255,255,255,.8)}""",
     'white': """.d{color:#fff}
.k{color:#FF8A73;text-shadow:0 3px 14px rgba(0,0,0,.8)}
.w{text-shadow:0 4px 24px rgba(0,0,0,.85),0 1px 4px rgba(0,0,0,.9)}
.r{box-shadow:0 4px 16px rgba(0,0,0,.7)}""",
     'scrim': """.d{color:#fff}
.k{color:#FFB4A2}
.w{text-shadow:0 3px 20px rgba(0,0,0,.6)}
""" + SCRIM,
    }[mode]
    # 글자 수에 따라 크기를 바꾼다 — 4글자 「원본 대조」와 15글자 문장이 같은 크기면 짧은 쪽이 초라하다
    n = len(c['keyword'].replace('<br>','').replace(' ',''))
    ws = 240 if n<=5 else 190 if n<=9 else 155 if n<=14 else 128 if n<=20 else 106
    css = """
/* ⛔가운데 정렬이면 2줄짜리가 아래로 더 내려가 자막을 침범한다(D4 −30px 실측).
   «아래 기준»으로 붙여 줄 수와 무관하게 글자 아랫변을 같은 높이에 고정한다. */
.d{position:relative;width:%(W)dpx;height:%(H)dpx;flex:none;
 display:flex;flex-direction:column;justify-content:flex-end;padding:0 54px 50px}
.in{position:relative;z-index:1}
.k{font-size:38px;font-weight:900;letter-spacing:.18em;margin-bottom:20px}
.w{font-size:WSpx;font-weight:900;letter-spacing:-.055em;line-height:1.02}""".replace('WS',str(ws)) + """
.w em{font-style:normal;color:var(--red);white-space:nowrap}  /* ⛔강조 덩어리가 두 줄로 찢기면 안 된다 */
.r{height:9px;width:150px;margin-top:26px;border-radius:99px;background:var(--red)}
""" + tone
    word = c['keyword']
    if c.get('hi'):                      # 강조할 부분만 레드로
        word = word.replace(c['hi'], '<em>%s</em>' % c['hi'])
    inner = ('<div class="k">%s</div><div class="w">%s</div><div class="r"></div>'
             % (c.get('kicker',''), word))
    body = ('<div class="d">%s<div class="in">%s</div></div>'
            % ('<div class="scrim"></div>' if mode=='scrim' else '', inner))
    return _page('daepan', css, body)

BUILD = {'sticker':sticker, 'bento':bento, 'rail':rail, 'terminal':terminal}

def html_for(c):
    k = c['kind']
    return daepan(c, c.get('mode','ink')) if k=='daepan' else BUILD[k](c)

# ─────────────────────────────────────────────── 렌더
def shot(html_path, png, cw, ch, scale=1.0, deadline=30.0):
    """⛔크롬은 스크린샷을 다 쓰고도 안 죽는다.
       타임아웃을 꽉 기다리면 컷당 30초 → «파일이 다 써졌는지»를 보고 바로 죽인다(컷당 2~4초)."""
    prof = tempfile.mkdtemp()
    if os.path.exists(png): os.remove(png)
    proc = subprocess.Popen([CHROME,'--headless','--disable-gpu','--user-data-dir='+prof,
        '--default-background-color=00000000',
        '--force-device-scale-factor=%g'%scale,
        '--screenshot='+png,'--window-size=%d,%d'%(cw,ch),
        '--virtual-time-budget=3000','file://'+os.path.abspath(html_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + deadline
    last, stable = -1, 0
    try:
        while time.time() < end:
            if proc.poll() is not None: break          # 스스로 죽었으면 끝
            if os.path.exists(png):
                sz = os.path.getsize(png)
                # 크기가 두 번 연속 같고 충분히 크면 «다 쓴 것»
                stable = stable+1 if (sz == last and sz > 3000) else 0
                if stable >= 2: break
                last = sz
            time.sleep(0.25)
    finally:
        proc.kill()
        try: proc.wait(timeout=5)
        except Exception: pass
        subprocess.run(['pkill','-f',prof], capture_output=True)
        shutil.rmtree(prof, ignore_errors=True)
    return os.path.exists(png) and os.path.getsize(png) > 3000

def render(c, outdir, scale=1.0):
    check_fonts(); check_chrome()
    """scale = 영상폭/2560. 카드 규격은 QHD 기준이고, 다른 해상도면 통째로 배율 렌더한다."""
    os.makedirs(outdir, exist_ok=True)
    w,h,pad = SIZE[c['kind']]
    hp = os.path.join(outdir, '%s.html' % c['id'])
    pg = os.path.join(outdir, '%s.png'  % c['id'])
    open(hp,'w',encoding='utf-8').write(html_for(c))
    if os.path.exists(pg): os.remove(pg)
    ok = shot(hp, pg, w+pad*2, h+pad*2, scale)
    return dict(id=c['id'], kind=c['kind'], png=pg,
                w=round(w*scale), h=round(h*scale), pad=round(pad*scale), ok=ok)

if __name__=='__main__':
    import json
    if len(sys.argv) < 2:
        sys.exit('사용: python3 cards_v2.py <카드계획.json> [나갈폴더]\n'
                 '  카드계획.json 형식은 ots_v2/README.md 「카드 계획 JSON 스키마」 참고\n'
                 '  예:  python3 cards_v2.py check_cards.json fin')
    src = sys.argv[1]
    if not os.path.exists(src):
        sys.exit('⛔ %s 이(가) 없습니다.\n'
                 '   → approve.py 가 만드는 check_cards.json 을 주거나, 직접 쓴 카드 JSON 을 주세요.' % src)
    check_fonts(); check_chrome()
    cards = json.load(open(src, encoding='utf-8'))
    if not cards: sys.exit('⛔ %s 에 카드가 한 장도 없습니다.' % src)
    # ⛔ 이름이 같은 cards.json 이 두 가지다 — 잘못 온 것을 조용히 처리하지 않는다
    _bc = [c for c in cards if c.get('kind') in ('corner', 'full')]
    if _bc:
        sys.exit('⛔ %s 은(는) «방송형 인서트» 형식입니다 — 이 스크립트는 «OTS 카드»용입니다.\n'
                 '   섞여 있는 카드: %s\n'
                 '   → python3 auto-insert/scripts/mac/build_inserts.py --cards %s --place place.json'
                 % (src, ', '.join(c.get('id','?') for c in _bc), src))
    _un = [c for c in cards if c.get('kind') not in SIZE]
    if _un:
        sys.exit('⛔ %s 에 모르는 종류(kind)가 있습니다: %s\n   쓸 수 있는 것: %s'
                 % (src, ', '.join('%s=%r'%(c.get('id','?'), c.get('kind')) for c in _un[:5]),
                    ', '.join(sorted(SIZE))))
    out   = sys.argv[2] if len(sys.argv)>2 else 'out'
    for c in cards:
        r = render(c, out)
        print('%s %-6s %-9s %s' % ('✅' if r['ok'] else '❌', r['id'], r['kind'], r['png']), flush=True)
