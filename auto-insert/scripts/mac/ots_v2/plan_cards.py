#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카드 배치·톤 결정기 — «가독성이 내용보다 먼저».

  카드 하나가 5~8초 떠 있는 동안 배경은 계속 바뀐다.
  ⛔한 프레임만 보고 정하면 중간에 글씨가 묻힌다 → 스팬 전체를 표본으로 «최악의 순간» 기준으로 판정한다.

  결정하는 것: ① 어느 자리에 ② 어떤 톤/모드로 ③ (안 되면) 무엇으로 강등할지
"""
import os, sys, subprocess, tempfile, json
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bg_read import read
from cards_v2 import SIZE

# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF = os.environ.get('FFFULL', ff_path.FFMPEG)

SUB_TOP = 1152    # ★구워진 본 자막 윗변 — 어떤 QHD 영상에서 잰 예(1152~1163).
                  #   ⚠️ 자막 위치는 영상마다 다르다 — 자기 영상에서 재서 바꿔 쓴다.
                  #   카드 아랫변은 반드시 이 위에서 끝나야 한다
CR_MIN  = 3.0     # WCAG 큰글씨 대비 하한
STD_MAX = 35.0    # 얼룩 상한 — 넘으면 «판 없이는 위험»
SAMPLES = 5       # 스팬당 표본 프레임 수

# 자리 후보 — (x, y) 는 카드 «본체» 좌상단. 2560x1440 기준
SPOTS = {
    'corner': {'좌': (90, 300), '우': (1690, 300)},
    'rail'  : {'좌세로': (90, 118), '우세로': (2000, 118)},   # ⛔200이면 118+1010=1210 > 자막 윗변 1152 침범
    'daepan': {'대판': (430, 760)},   # ⛔620이면 얼굴·눈을 덮는다. 760=눈 아래·자막 위
}
KIND_SPOT = {'sticker':'corner','bento':'corner','terminal':'corner',
             'rail':'rail','daepan':'daepan'}

def grab(video, times, outdir):
    """⛔파일명을 «표본 번호»로 지으면 카드마다 0~4가 겹쳐 첫 카드 프레임을 계속 재사용한다.
       에러도 안 나고 숫자도 그럴듯해서 못 알아챈다(실제로 당한 사고) → 이름에 «시각»을 넣는다."""
    os.makedirs(outdir, exist_ok=True)
    def one(a):
        i,t = a; p = os.path.join(outdir,'t%09.3f.png'%t)
        if not os.path.exists(p):
            subprocess.run([FF,'-v','error','-ss','%.3f'%t,'-i',video,
                            '-frames:v','1','-y',p], check=True)
        return p
    with ThreadPoolExecutor(max_workers=4) as ex:
        return list(ex.map(one, list(enumerate(times))))

def span_times(at, dur, n=SAMPLES):
    return [at] if n<=1 else [at + dur*k/(n-1) for k in range(n)]

def worst(frames, x, y, w, h):
    """스팬 전체에서 «제일 나쁜» 값을 모은다 — 평균을 쓰면 중간에 묻히는 걸 놓친다"""
    rs = [read(f, x, y, w, h) for f in frames]
    return dict(cr_white=min(r['cr_white'] for r in rs),
                cr_black=min(r['cr_black'] for r in rs),
                std     =max(r['std']      for r in rs),
                mean    =sum(r['mean'] for r in rs)/len(rs),
                n=len(rs))

def decide_daepan(m):
    """무판 대판의 3모드 결정. ⛔실측상 흰 글씨 순수는 거의 안 나온다"""
    clean = m['std'] <= STD_MAX
    if clean and m['cr_black'] >= CR_MIN:
        return 'ink',   '배경이 밝고 깨끗 → 검은 글씨 (제일 가볍다)'
    if clean and m['cr_white'] >= CR_MIN:
        return 'white', '배경이 어둡고 깨끗 → 흰 글씨'
    return 'scrim', '얼룩짐(편차 %.0f) 또는 대비 부족 → 스크림 자동 추가' % m['std']


# ─────────────────────────────────────────────── 사용자가 지정한 구간 («반드시» / «절대»)
END_OF_VIDEO = 1e9        # 「끝」= 영상 끝까지. 실제 길이를 몰라도 «그 뒤 전부»를 막는다

def parse_t(x):
    """「1:28」「1:28.5」「00:01:28,520」「88」 다 받는다. 「끝」·「end」 는 영상 끝."""
    if isinstance(x,(int,float)): return float(x)
    t = str(x).strip().replace(',', '.')
    if t in ('끝', '끝까지', 'end', 'END', ''): return END_OF_VIDEO
    parts = t.split(':')
    sec = 0.0
    for p in parts:
        try: sec = sec*60 + float(p)
        except ValueError:
            raise SystemExit('⛔ 시각을 못 읽었습니다: %r\n'
                             '   이렇게 써 주세요 —  88  ·  1:28  ·  1:28.5  ·  00:01:28,520  ·  끝' % x)
    return sec

def parse_range(x):
    """「1:28-1:39」 또는 [시작,끝]"""
    if isinstance(x,(list,tuple)): return (parse_t(x[0]), parse_t(x[1]))
    a,b = str(x).replace('~','-').split('-')
    return (parse_t(a), parse_t(b))

def _hit(a0,a1,b0,b1): return a0 < b1 and b0 < a1

def _t(sec):
    """사람이 읽을 시각 문자열. END_OF_VIDEO 는 「끝」으로 보여 준다."""
    return '끝' if sec >= END_OF_VIDEO else '%d:%04.1f'%(sec//60, sec%60)

def apply_windows(cards, never=(), must=(), max_shift=15.0, gap=0.3):
    """절대 금지 구간과 겹치면 뒤로 밀고, 그래도 안 되면 뺀다. 뺀 건 반드시 보고한다."""
    never = [parse_range(r) for r in never]
    must  = [parse_range(r) for r in must]
    kept, dropped = [], []
    for c in cards:
        dur = c.get('dur', 6)
        a0, a1 = float(c['at']), float(c['at']) + dur
        blk = next((r for r in never if _hit(a0, a1, *r)), None)
        if blk is None:
            kept.append(c); continue
        newat = blk[1] + gap                                  # 금지 구간 끝난 직후로 민다
        if (newat - a0) <= max_shift and not any(_hit(newat, newat+dur, *r) for r in never):
            c2 = dict(c); c2['at'] = round(newat, 2); c2['shifted'] = round(newat - a0, 2)
            kept.append(c2)
        else:
            dropped.append((c['id'], '금지구간 %s~%s 과 겹침 · %.0fs 밀어도 못 피함'
                                     % (_t(blk[0]), _t(blk[1]), max_shift)))
    # ⛔밀린 카드끼리 같은 자리에 겹칠 수 있다 — 시간순으로 훑어 최소 간격을 강제한다
    kept.sort(key=lambda c: float(c['at']))
    MIN_GAP = 8.0                       # 앞 카드가 끝나고 최소 8초는 비운다
    prev_end = -1e9
    survivors = []
    for c in kept:
        at, dur = float(c['at']), c.get('dur', 6)
        if at < prev_end + MIN_GAP:
            push = (prev_end + MIN_GAP) - at
            newat = at + push
            if push > max_shift or any(_hit(newat, newat+dur, *r) for r in never):
                dropped.append((c['id'], '앞 카드와 %.1fs 간격 부족 · 밀 자리도 없음' % (at - prev_end)))
                continue
            c = dict(c); c['at'] = round(newat, 2)
            c['shifted'] = round(c.get('shifted', 0) + push, 2)
            at = newat
        survivors.append(c); prev_end = at + dur
    kept = survivors

    # «반드시» 구간에 카드가 하나도 없으면 알린다 (조용히 넘어가면 누락으로 읽힌다)
    missing = []
    for m0, m1 in must:
        if not any(_hit(float(c['at']), float(c['at'])+c.get('dur',6), m0, m1) for c in kept):
            missing.append('%s~%s 에 카드 없음 — 채워야 함' % (_t(m0), _t(m1)))
    return kept, dropped, missing

def plan_one(video, card, workdir, k=1.0):
    kind = card['kind']
    w, h, _ = SIZE[kind]
    w, h = round(w*k), round(h*k)
    spots = {n:(round(x*k), round(y*k)) for n,(x,y) in SPOTS[KIND_SPOT[kind]].items()}
    frames = grab(video, span_times(card['at'], card.get('dur',6)), workdir)

    cands = []
    for name,(x,y) in spots.items():
        m = worst(frames, x, y, w, h)
        cands.append((name, x, y, m))

    if kind == 'daepan':
        name, x, y, m = cands[0]
        mode, why = decide_daepan(m)
        # ⛔대판은 «판»이 없다 — 상자 아랫변이 아니라 «글자 잉크» 아랫변으로 재야 한다.
        #   아래 기준 정렬 + padding-bottom 50 → 잉크 아랫변 = 상자 아랫변 − 51 (실측)
        return dict(id=card['id'], kind=kind, spot=name, x=x, y=y, mode=mode,
                    why=why, sub_clear=round(SUB_TOP*k - (y+h-51*k), 1),
                    **{kk:round(v,2) for kk,v in m.items() if kk!='n'})

    # 판이 있는 카드 — 판 자체가 대비를 주니 «얼룩이 적은 쪽»을 고른다
    cands.sort(key=lambda c: c[3]['std'])
    name, x, y, m = cands[0]
    return dict(id=card['id'], kind=kind, spot=name, x=x, y=y, mode=None,
                why='편차가 더 낮은 쪽 선택(%.0f)' % m['std'],
                sub_clear=round(SUB_TOP*k - (y+h), 1),
                **{kk:round(v,2) for kk,v in m.items() if kk!='n'})

def vsize(video):
    probe = os.path.join(os.path.dirname(FF), 'ffprobe')   # ⛔경로에도 'ffmpeg'이 들어있어 통째 치환하면 깨진다
    r = subprocess.run([probe,'-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height','-of','csv=p=0:s=x',video],
        capture_output=True, text=True)
    w,h = r.stdout.strip().split('x')[:2]
    return int(w), int(h)

def plan(video, cards, workdir='_plan_frames'):
    W,_ = vsize(video)
    k = W/2560.0                      # 규격은 QHD 기준 — 다른 해상도면 좌표·크기를 같은 비율로
    out=[]
    for c in cards:
        r = plan_one(video, c, workdir, k)
        r['scale']=round(k,4); out.append(r)
    return out

if __name__=='__main__':
    # ⛔ sys.argv[1] 을 그냥 집으면 «IndexError» 만 나온다 — 무엇을 달라는 건지 알 수 없다
    if len(sys.argv) < 3:
        raise SystemExit(
            '사용: python3 plan_cards.py <영상.mp4> <카드계획.json>\n'
            '  하는 일: 카드마다 «어느 자리에 · 어떤 톤으로» 놓을지 배경을 재서 정한다\n'
            '  나가는 것: plan_out.json\n'
            '  카드계획.json 형식은 ots_v2/README.md 「카드 계획 JSON 스키마」 참고\n'
            '  다음 단계: python3 approve.py --cards <카드계획.json> --plan plan_out.json')
    video = sys.argv[1]
    for p in (video, sys.argv[2]):
        if not os.path.exists(p): raise SystemExit('⛔ %s 이(가) 없습니다.'%p)
    cards = json.load(open(sys.argv[2], encoding='utf-8'))
    out = plan(video, cards)
    print('%-6s %-9s %-7s %-7s %6s %6s %6s  %s' %
          ('id','종류','자리','모드','흰대비','검대비','편차','판정 사유'))
    for r in out:
        print('%-6s %-9s %-7s %-7s %6.2f %6.2f %6.1f  %s' %
              (r['id'], r['kind'], r['spot'], r['mode'] or '-',
               r['cr_white'], r['cr_black'], r['std'], r['why']))
    json.dump(out, open('plan_out.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n→ plan_out.json')
