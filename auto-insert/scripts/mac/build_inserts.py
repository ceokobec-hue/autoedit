#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인서트컷(코너 카드 + 풀프레임) HTML 생성 → Chrome 스크린샷.

사용:
  python3 build_inserts.py --cards cards.json --place place.json --out inserts.json
  python3 build_inserts.py --cards cards.json --from-measure ots_measure.json

  cards.json       카드 원고 (내가 쓴다)
  place.json       카드별 «크기·모서리·시각». 없으면 --from-measure 로 ots_place.py 산출에서 만든다
  나가는 것        shots/<id>.png · inserts.json · (중간물) build/<id>.html
"""
import json, os, re, subprocess, sys, argparse

# ⛔ 크롬 위치를 코드에 박지 않는다
CH = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
# 폰트 창고는 한 곳뿐 — get_fonts.sh 가 채운다
FONTDIR = os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts'))
S       = os.path.dirname(os.path.abspath(__file__))
CARD_CSS = os.path.normpath(os.path.join(S, '..', '..', 'assets', 'broadcast', 'card.css'))
PAD = 80

def card_css():
    """⛔ <link href="card.css"> 로 걸면 HTML 은 build/ 에 있고 css 는 assets/ 에 있어
       «에러 하나 없이 민무늬 카드»가 나온다 → 내용을 통째로 넣고 폰트도 절대경로로 바꾼다."""
    if not os.path.exists(CARD_CSS):
        sys.exit('⛔ 카드 스타일을 못 찾았습니다: %s' % CARD_CSS)
    css = open(CARD_CSS, encoding='utf-8').read()
    return css.replace("url('../fonts/", "url('file://%s/" % FONTDIR) \
              .replace("url('fonts/",    "url('file://%s/" % FONTDIR)

def check_fonts():
    want = ['Pretendard-Regular.woff2','Pretendard-Medium.woff2',
            'Pretendard-Bold.woff2','Pretendard-Black.woff2']
    miss = [f for f in want if not os.path.exists(os.path.join(FONTDIR,f))]
    if miss:
        sys.exit('⛔ 카드 폰트(woff2)가 없습니다 — 이대로 구우면 «에러 없이 다른 글꼴»로 나갑니다.\n'
                 '   찾은 곳: %s\n   없는 파일: %s\n'
                 '   → bash auto-insert/scripts/mac/get_fonts.sh' % (FONTDIR, ', '.join(miss)))

def check_chrome():
    if not os.path.exists(CH):
        sys.exit('⛔ 크롬을 못 찾았습니다: %s\n'
                 '   인서트 PNG 는 크롬이 굽습니다(무료).\n'
                 '   → brew install --cask google-chrome   /   export CHROME=<경로>' % CH)

# ── 카드 «형식» 판별 ─────────────────────────────────────
# 이 저장소에는 이름이 같은 cards.json 이 두 가지 있다. 종류(kind)로 구분된다.
OTS_KINDS = ('sticker', 'bento', 'rail', 'daepan', 'terminal')   # → ots_v2 파이프라인
BC_KINDS  = ('corner', 'full')                                   # → 여기(방송형 인서트)

def check_format(cards, path):
    """⛔ 관대한 앞단 + 엄격한 뒷단 = 최악. 여기서 «먼저» 잡아 어디로 가야 하는지 알려준다."""
    ots = sorted({c.get('kind') for c in cards if c.get('kind') in OTS_KINDS})
    if ots:
        ids = ', '.join(c['id'] for c in cards if c.get('kind') in OTS_KINDS)
        sys.exit('⛔ %s 은(는) «OTS 카드» 형식입니다 — 이 스크립트는 «방송형 인서트»용입니다.\n'
                 '   섞여 있는 카드: %s  (종류: %s)\n\n'
                 '   OTS 카드는 이쪽으로 가세요:\n'
                 '     python3 ots_v2/plan_cards.py <영상.mp4> %s\n'
                 '     python3 ots_v2/approve.py --cards %s --plan plan_out.json\n'
                 '     python3 ots_v2/cards_v2.py check_cards.json fin\n\n'
                 '   두 형식의 차이는 파일형식.md 를 보세요 '
                 '(방송형 kind = corner·full / OTS kind = %s).'
                 % (path, ids, ', '.join(ots), path, path, '·'.join(OTS_KINDS)))
    bad = [c for c in cards if c.get('kind') not in BC_KINDS]
    if bad:
        sys.exit('⛔ %s 에 모르는 종류(kind)가 있습니다: %s\n'
                 '   방송형 인서트는 «corner»(모서리 카드) 또는 «full»(풀프레임)만 씁니다.'
                 % (path, ', '.join('%s=%r' % (c.get('id', '?'), c.get('kind')) for c in bad[:5])))

def rows_html(rows):
    return '\n'.join('<div class="row">%s<span class="t">%s</span>%s</div>' % (
        '<span class="n">%s</span>'%r['n'] if r.get('n') else '', r['t'],
        '<span class="v">%s%s</span>'%(r['v'],'<em>%s</em>'%r['unit'] if r.get('unit') else '')
        if r.get('v') else '') for r in rows)

def corner_html(c, w, h):
    b=['<div class="kicker">%s</div>'%c['kicker'], '<div class="head">%s</div>'%c['head'], '<div class="rule"></div>']
    if c.get('big'): b.append('<div class="big">%s<em>%s</em></div>'%(c['big'],c.get('bigunit','')))
    if c.get('desc'): b.append('<div class="desc">%s</div>'%c['desc'])
    if c.get('rows'): b.append('<div class="rows">%s</div>'%rows_html(c['rows']))
    if c.get('foot') or c.get('src'):
        b.append('<div class="foot"><span>%s</span><span>%s</span></div>'%(c.get('foot',''),c.get('src','')))
    sc = 1.0 if w>=880 else 0.90     # 780짜리는 타이포를 살짝 줄인다
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
      '<style>' + card_css() +
      'html,body{width:%dpx;height:%dpx;background:transparent}'
      'body{display:flex;align-items:center;justify-content:center}.card{width:%dpx;height:%dpx;flex:none}'
      '.kicker{font-size:%.0fpx}.head{font-size:%.0fpx}.row .t{font-size:%.0fpx}.row .v{font-size:%.0fpx}'
      '.row .v em{font-size:%.0fpx}.row .n{font-size:%.0fpx;min-width:%.0fpx}.big{font-size:%.0fpx}'
      '.big em{font-size:%.0fpx}.desc{font-size:%.0fpx}.foot{font-size:%.0fpx}.rule{width:118px;height:7px}'
      '</style></head><body><div class="card"><div class="pad">%s</div><div class="grain"></div></div></body></html>'
      %(w+PAD*2,h+PAD*2,w,h, 30*sc,64*sc,40*sc,54*sc,31*sc,31*sc,40*sc,120*sc,46*sc,33*sc,24*sc,'\n'.join(b)))

def full_html(c):
    items=''.join(
      '<div class="it"><div class="num">%s</div><div><div class="tt">%s</div>%s</div></div>'
      % (n, t, '<div class="dd">%s</div>'%d if d else '') for n,t,d in c['items'])
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
      '<style>' + card_css() +
      'html,body{width:2560px;height:1440px;background:#F4F1EA}'
      ".ff{position:relative;width:2560px;height:1440px;background:#F4F1EA;color:#16130E;"
      "font-family:'Pretendard',sans-serif;word-break:keep-all;overflow:hidden;padding:88px 132px}"
      '.mast{display:flex;justify-content:space-between;align-items:center;border-bottom:5px solid #16130E;'
      'padding-bottom:20px;font-size:30px;font-weight:500;letter-spacing:.14em;color:#6E675C}'
      '.mast b{color:#16130E;font-weight:900;letter-spacing:.04em}'
      '.kick{font-size:34px;font-weight:700;letter-spacing:.22em;color:#E8442E;margin:46px 0 18px}'
      '.h1{font-size:%dpx;font-weight:900;letter-spacing:-.042em;line-height:1.05}'
      '.h1 u{text-decoration:none;box-shadow:inset 0 -20px 0 rgba(232,68,46,.30)}'
      '.list{margin-top:%dpx;display:flex;flex-direction:column}'
      '.it{display:flex;gap:40px;align-items:flex-start;padding:%dpx 0;border-top:2px solid #C8C1B2}'
      '.it:last-child{border-bottom:2px solid #C8C1B2}'
      ".it .num{font-size:46px;font-weight:900;color:#E8442E;min-width:%dpx;font-feature-settings:'tnum';line-height:1.15}"
      '.it .tt{font-size:%dpx;font-weight:900;letter-spacing:-.028em;line-height:1.14}'
      '.it .dd{font-size:34px;font-weight:500;color:#6E675C;margin-top:10px;line-height:1.4}'
      '.polio{position:absolute;left:132px;right:132px;bottom:52px;display:flex;justify-content:space-between;'
      'font-size:28px;font-weight:500;letter-spacing:.16em;color:#6E675C}'
      '.ghost{position:absolute;right:118px;top:236px;font-size:480px;font-weight:900;'
      'color:rgba(22,19,14,.055);line-height:1;letter-spacing:-.05em}'
      '</style></head><body><div class="ff">'
      '<div class="mast"><span><b>내 채널</b></span><span>부제 · 자료 성격</span></div>'
      '<div class="ghost">%s</div><div class="kick">%s</div><div class="h1">%s</div>'
      '<div class="list">%s</div>'
      '<div class="polio"><span>내 채널</span><span>부제</span></div>'
      '<div class="grain"></div></div></body></html>'
      % (132 if len(c['items'])>=4 else 150,
         44 if len(c['items'])>=4 else 60,
         26 if len(c['items'])>=4 else 34,
         92, 58 if len(c['items'])>=4 else 64,
         c['no'], c['kick'], c['h1'], items))

def head_of(c):
    """큰 글씨로 쓸 문구. ⛔c['head'] 만 찾으면 그 칸이 없는 카드에서 KeyError 로 죽는다.

    ⚠️ ots_place.label_of() 와 «순서가 다른 것은 일부러»다. 맞추지 말 것.
       label_of  = 표에 찍을 «이름»    → label 이 제일 정확하다
       head_of   = 화면에 띄울 «큰 글씨» → head 가 제일 정확하다(label 은 설명용이라 뒤로)"""
    for k in ('head', 'h1', 'keyword', 'label', 'kicker'):
        v = c.get(k)
        if v: return str(v)
    return c.get('id', '·')

def promote(c):
    """코너 원고를 풀프레임 원고로 승격"""
    items=[]
    if c.get('rows'):
        for r in c['rows']:
            v = ('%s%s'%(r['v'],r.get('unit','')) ) if r.get('v') else ''
            items.append((r.get('n',''), r['t'], v))
    if c.get('big'):
        items.append(('', '%s %s'%(c['big'],c.get('bigunit','')), ''))
    if c.get('desc'):
        items.append(('', re.sub('<br>',' ', re.sub('</?b>','',c['desc'])), ''))
    if not items: items=[('', c.get('foot','') or '—', '')]
    return {'no':c.get('no','·'), 'kick':c.get('kicker',''),
            'h1':head_of(c).replace('<b>','<u>').replace('</b>','</u>'),
            'items':items[:4]}

def shot(html_path, png, w, h, transparent):
    args=[CH,'--headless=new','--disable-gpu','--hide-scrollbars','--force-device-scale-factor=1']
    if transparent: args.append('--default-background-color=00000000')
    args+=['--screenshot=%s'%png,'--window-size=%d,%d'%(w,h),'file://%s'%os.path.abspath(html_path)]
    r=subprocess.run(args,capture_output=True,text=True)
    # ⛔ 반환코드를 안 보면 «크롬이 죽었는데도» 조용히 넘어간다
    if r.returncode != 0:
        print('   ⚠️ 크롬이 %d 로 끝났습니다: %s' % (r.returncode, (r.stderr or '')[-200:]))
    return os.path.exists(png)

# render_final.py 는 모서리를 «좌/우 · 상/하» 한글로 읽는다. 영어 약자로 써도 받아 준다.
CORNER = {'tl':'좌상','tr':'우상','bl':'좌하','br':'우하',
          'lt':'좌상','rt':'우상','lb':'좌하','rb':'우하'}
def norm_corner(v):
    v = str(v or '좌상').strip()
    return CORNER.get(v.lower(), v)

def place_from_measure(mpath):
    """ots_place.py 가 잰 결과(ots_measure.json)를 «어디에 얼마만큼» 으로 바꾼다.

    규칙은 단순하다 — 사람이 덜 걸치는 쪽(여백이 넓은 쪽) 위에 놓는다.
    아래쪽은 구워진 자막이 있으므로 쓰지 않는다."""
    M = json.load(open(mpath, encoding='utf-8'))
    W = M.get('W', 2560); k = W/2560.0
    w, h = round(780*k), round(590*k)
    out = {}
    for c in M['cards']:
        corner = '좌상' if c.get('left_free',0) >= c.get('right_free',0) else '우상'
        out[c['id']] = {'w':w, 'h':h, 'corner':corner,
                        'at':c['at'], 'dur':c.get('dur', 5.0)}
        print('  %-4s → %s (좌여백 %s · 우여백 %s)'
              % (c['id'], corner, c.get('left_free','?'), c.get('right_free','?')))
    return out

if __name__=='__main__':
    ap=argparse.ArgumentParser(description='인서트컷 HTML → PNG')
    ap.add_argument('--cards', default='cards.json', help='카드 원고 JSON')
    ap.add_argument('--place', default='place.json',
                    help='카드별 크기·모서리·시각. 없으면 --from-measure 를 쓰세요')
    ap.add_argument('--from-measure', dest='measure',
                    help='ots_place.py 가 만든 ots_measure.json 에서 배치를 계산한다')
    ap.add_argument('--out', default='inserts.json', help='산출 목록 JSON')
    ap.add_argument('--builddir', default='build', help='중간 HTML 이 쌓이는 곳')
    ap.add_argument('--shotsdir', default='shots', help='PNG 가 나가는 곳')
    A=ap.parse_args()
    B, OUT = A.builddir, A.shotsdir

    if not os.path.exists(A.cards):
        sys.exit('⛔ %s 이(가) 없습니다 — 카드 원고 JSON 을 --cards 로 주세요.\n'
                 '   형식은 auto-insert/scripts/mac/README.md 참고' % A.cards)
    check_fonts(); check_chrome()

    # ⛔ build/ 를 안 만들면 첫 카드에서 FileNotFoundError 로 죽는다 (둘 다 만든다)
    os.makedirs(B, exist_ok=True); os.makedirs(OUT, exist_ok=True)

    ALL=json.load(open(A.cards,encoding='utf-8'))
    if not ALL: sys.exit('⛔ %s 에 카드가 한 장도 없습니다.'%A.cards)
    check_format(ALL, A.cards)          # ⛔ 형식이 다르면 «여기서» 멈춘다
    if A.measure:
        if not os.path.exists(A.measure):
            sys.exit('⛔ %s 이(가) 없습니다 — python3 ots_place.py <영상.mp4> %s 를 먼저 돌리세요.'
                     % (A.measure, A.cards))
        print('배치를 %s 에서 계산합니다:'%A.measure)
        PL=place_from_measure(A.measure)
        json.dump(PL, open(A.place,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
        print('  → %s 에 저장했습니다 (고치고 싶으면 이 파일을 손보세요)\n'%A.place)
    elif os.path.exists(A.place):
        PL=json.load(open(A.place,encoding='utf-8'))
    else:
        sys.exit('⛔ %s 이(가) 없습니다.\n'
                 '   → 코너 카드 자리를 정하려면 둘 중 하나:\n'
                 '      ① python3 ots_place.py <영상.mp4> %s   후  --from-measure ots_measure.json\n'
                 '      ② %s 를 직접 쓰기:\n'
                 '         {"C1": {"w":780, "h":590, "corner":"좌상", "at":10.0, "dur":5.0}}\n'
                 '         corner 는 좌상·우상·좌하·우하 (영어 tl/tr/bl/br 도 받습니다)'
                 % (A.place, A.cards, A.place))
    made=[]
    fno=0
    for c in ALL:
        cid=c['id']; p=PL.get(cid) or {}
        # ⛔ 시각·길이가 없으면 render_final.py 가 KeyError 로 죽는다 → 여기서 잡아 알려 준다
        at  = p.get('at',  c.get('at'))
        dur = p.get('dur', c.get('dur', 5.0))
        if at is None:
            sys.exit('⛔ %s 카드에 «언제 띄울지»(at)가 없습니다.\n'
                     '   → %s 의 그 카드에 "at": 초 를 넣거나, %s 에 넣어 주세요.'
                     % (cid, A.cards, A.place))
        if c['kind']=='corner' and p:
            w,h=p['w'],p['h']
            hp=os.path.join(B,'i_%s.html'%cid); open(hp,'w',encoding='utf-8').write(corner_html(c,w,h))
            png=os.path.join(OUT,'%s.png'%cid)
            ok=shot(hp,png,w+PAD*2,h+PAD*2,True)
            made.append({**c,'render':'corner','corner':norm_corner(p.get('corner')),
                         'w':w,'h':h,'at':at,'dur':dur,'png':png,'ok':ok})
        else:
            fno+=1
            spec = dict(c) if c['kind']=='full' else (dict(c['full_spec']) if c.get('full_spec') else promote(c))
            spec['no']='%02d'%fno      # ★시간순 통번호 — 원고에 박힌 번호를 쓰면 승격분과 겹친다
            hp=os.path.join(B,'i_%s.html'%cid); open(hp,'w',encoding='utf-8').write(full_html(spec))
            png=os.path.join(OUT,'%s.png'%cid)
            ok=shot(hp,png,2560,1440,False)
            made.append({**c,'render':'full','at':at,'dur':dur,'png':png,'ok':ok})
    json.dump(made,open(A.out,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    good=sum(1 for m in made if m['ok'])
    print('생성 %d/%d  (코너 %d · 풀 %d) → %s'%(good,len(made),
        sum(1 for m in made if m['render']=='corner'),
        sum(1 for m in made if m['render']=='full'), A.out))
    for m in made:
        if not m['ok']: print('  ⛔ %s — PNG 가 안 나왔습니다'%m['id'])
    if good < len(made): sys.exit(1)
