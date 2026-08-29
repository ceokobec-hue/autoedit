#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""빠져 있던 연결고리 — 「자리 판정 결과」를 「검수·렌더가 읽는 파일」로 확정한다.

  plan_cards.py  →  plan_out.json        (자리·톤을 «재 본» 결과)
        여기 approve.py                   (뺄 카드·금지 구간을 반영해 «확정»)
  →  check_cards.json · plan_check.json · plan_final.json
        └ build_sheet.py 가 검수 시트를 그리고, render_ots_v2.py 가 이걸로 굽는다

세 파일이 나오는 이유:
  check_cards.json  = 살아남은 «카드 내용»(문구·시각·길이)
  plan_check.json   = 검수 시트가 읽는 «배치»
  plan_final.json   = 최종 렌더가 읽는 «배치»  (지금은 같은 내용 — 시트에서 뺄 게 생기면
                      --drop 을 붙여 이 스크립트를 다시 돌린다)

사용:
  python3 approve.py --cards cards.json --plan plan_out.json
  python3 approve.py --cards cards.json --plan plan_out.json --drop D1,S3
  python3 approve.py --cards cards.json --plan plan_out.json --never "1:28-1:39" --never "11:32-끝"
"""
import os, sys, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan_cards import apply_windows          # ⛔여기서만 쓰인다 — 없으면 금지구간 기능이 죽은 코드가 된다

ap = argparse.ArgumentParser(description='자리 판정 결과를 검수·렌더가 읽는 파일로 확정한다')
ap.add_argument('--cards', default='cards.json',    help='카드 계획 JSON (내가 쓴 것)')
ap.add_argument('--plan',  default='plan_out.json', help='plan_cards.py 산출')
ap.add_argument('--drop',  default='',  help='뺄 카드 id 를 쉼표로. 예: --drop D1,S3')
ap.add_argument('--keep',  default='',  help='이것만 남긴다(쉼표). --drop 과 같이 쓰지 않는다')
ap.add_argument('--never', action='append', default=[],
                help='카드가 «절대» 뜨면 안 되는 구간. 예: --never "1:28-1:39" (여러 번 가능)')
ap.add_argument('--must',  action='append', default=[],
                help='카드가 «반드시» 있어야 하는 구간. 비어 있으면 알려만 준다')
ap.add_argument('--max-shift', type=float, default=15.0, help='금지 구간을 피해 뒤로 밀 수 있는 최대 초')
ap.add_argument('--end', type=float,
                help='영상 길이(초). 주면 «밀다가 영상 밖으로 나간» 카드를 잡아 준다')
ap.add_argument('--outdir', default='.', help='세 파일을 쓸 폴더 (기본: 지금 폴더)')
a = ap.parse_args()

def need(p, who):
    if not os.path.exists(p): sys.exit('⛔ %s 이(가) 없습니다.\n   → %s' % (p, who))
need(a.cards, '카드 계획 JSON 을 만들어 주세요 (형식은 ots_v2/README.md 「카드 계획 JSON 스키마」)')
need(a.plan,  'python3 plan_cards.py <영상.mp4> %s  을 먼저 돌리세요' % a.cards)

CARDS = json.load(open(a.cards, encoding='utf-8'))
PLAN  = json.load(open(a.plan,  encoding='utf-8'))
PBY   = {r['id']: r for r in PLAN}

# ── 사람이 «뺀» 카드 반영 ────────────────────────────────
def ids(s): return [x.strip() for x in s.split(',') if x.strip()]
if a.keep and a.drop: sys.exit('⛔ --keep 과 --drop 은 같이 쓰지 않습니다. 하나만 쓰세요.')
if a.keep:
    want = set(ids(a.keep)); CARDS = [c for c in CARDS if c['id'] in want]
if a.drop:
    gone = set(ids(a.drop)); CARDS = [c for c in CARDS if c['id'] not in gone]

missing_plan = [c['id'] for c in CARDS if c['id'] not in PBY]
if missing_plan:
    sys.exit('⛔ 자리 판정이 없는 카드가 있습니다: %s\n'
             '   → plan_cards.py 를 다시 돌려 %s 를 새로 만드세요.'
             % (', '.join(missing_plan), a.plan))

# ── 금지 / 반드시 구간 적용 (밀기 → 그래도 안 되면 제외) ──
kept, dropped, missed = apply_windows(CARDS, never=a.never, must=a.must, max_shift=a.max_shift)
if not kept:
    sys.exit('⛔ 남는 카드가 없습니다. --never 구간이 너무 넓거나 --drop 이 과합니다.')

# ⛔ 뒤로 밀다가 영상 끝을 넘어가면 렌더는 성공하는데 «카드만 안 보인다» — 조용한 고장이다
if a.end:
    over = [c for c in kept if float(c['at']) >= a.end or float(c['at'])+c.get('dur',6) > a.end]
    if over:
        for c in over:
            dropped.append((c['id'], '영상 끝(%.1fs)을 넘어감 — %.1fs 에 놓였습니다' % (a.end, c['at'])))
        kept = [c for c in kept if c not in over]
        if not kept:
            sys.exit('⛔ 영상 안에 남는 카드가 없습니다. cards.json 의 at 을 앞으로 당기세요.')

FINAL = []
for c in kept:
    r = dict(PBY[c['id']])
    r['at'] = c['at']                      # 밀렸으면 새 시각을 배치에도 반영
    if c.get('shifted'): r['shifted'] = c['shifted']
    FINAL.append(r)
FINAL.sort(key=lambda r: r['at'])
kept.sort(key=lambda c: float(c['at']))

os.makedirs(a.outdir, exist_ok=True)
def dump(obj, name):
    p = os.path.join(a.outdir, name)
    json.dump(obj, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return p
dump(kept,  'check_cards.json')
dump(FINAL, 'plan_check.json')
dump(FINAL, 'plan_final.json')

print('✅ check_cards.json · plan_check.json · plan_final.json  — 카드 %d장' % len(kept))
if dropped:
    print('\n⛔ 뺀 카드 %d장 (그냥 넘어가지 않고 반드시 알립니다)' % len(dropped))
    for i, why in dropped: print('   - %s : %s' % (i, why))
shifted = [c for c in kept if c.get('shifted')]
if shifted:
    print('\n↪️ 금지 구간을 피해 뒤로 민 카드 %d장' % len(shifted))
    for c in shifted: print('   - %s : %+.1f초 → %.1fs' % (c['id'], c['shifted'], c['at']))
if missed:
    print('\n⚠️ 「반드시」 구간인데 카드가 없습니다')
    for m in missed: print('   - ' + m)
print('\n다음:  python3 cards_v2.py check_cards.json fin      (카드 PNG 굽기)')
print('       python3 build_sheet.py --video <영상.mp4> --srt <자막.srt>   (검수 시트)')
