#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인서트컷 설계 + 검토 게이트 HTML.

아래 C 배열이 «무엇을 언제 몇 초 동안 띄울지»의 전부다. 여기만 고쳐 쓴다."""
import os, re, json, html
import sys, os as _os
sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
import job
job.chdir()
SRT=job.SRT

def t2s(t):
    h,m,rest = t.split(':'); s,ms = rest.split(',')
    return int(h)*3600+int(m)*60+int(s)+int(ms)/1000
def load(p):
    cues=[]
    for blk in re.split(r'\n\s*\n', open(p,encoding='utf-8-sig').read()):
        L=[x for x in blk.strip().split('\n') if x.strip()]
        if len(L)<2 or '-->' not in L[1]: continue
        a,b=[x.strip() for x in L[1].split('-->')]
        cues.append((t2s(a),t2s(b),' '.join(L[2:]).strip()))
    return cues
CUES = load(SRT); END = CUES[-1][1]

# 실습(화면공유) 구간 — ⛔풀프레임 금지
PRACTICE = (413.0, 994.0)   # 예시값 06:53 ~ 16:34 — 자기 영상의 화면공유 구간으로 바꾼다
# ⚠️ 아래는 «예시 카드»다. 자기 회차 내용으로 통째로 갈아끼워 쓴다.
#    (kind, at, dur, kicker, keyword, sub)
#    kind: sticker 스티커 · bento 벤토 · rail 세로레일 · daepan 무판대판 · terminal 터미널 · full 풀프레임
C = [
 # ── A 구간: 말로 설명하는 대목 (풀프레임 가능) ──
 ('daepan'  ,   0.0, 4.5, '시리즈 이름', '오늘 다룰 것', ''),
 ('sticker' ,  12.0, 3.5, '',            '첫 번째 요점', ''),
 ('full'    ,  30.0, 5.0, '질문',        '이런 적 있으신가요?', ''),
 ('bento'   ,  60.0, 6.0, '두 가지로 나누면', '이쪽과 저쪽', '왼쪽 · 오른쪽'),
 ('terminal', 120.0, 4.0, '',            '명령 한 줄', '화면에 이렇게 나온다'),
 # ── B 구간: 화면공유·실습 (⛔풀프레임 금지 — 화면을 가린다) ──
 ('rail'    , 450.0, 5.0, '지금 하는 것', '순서대로 따라간다', ''),
 ('sticker' , 600.0, 3.5, '',            '여기서 자주 막힌다', ''),
 ('rail'    , 800.0, 5.0, '확인',        '이 화면이 나오면 성공', ''),
 # ── C 구간: 마무리 ──
 ('daepan'  ,1050.0, 5.0, '정리',        '오늘의 한 줄', ''),
]

# ── 큐 경계로 스냅 ──────────────────────────────────────
starts = [c[0] for c in CUES]
def snap(t):
    return min(starts, key=lambda s: abs(s-t))
cards=[]; snaps=[]
for i,(kind,at,dur,kick,key,sub) in enumerate(C,1):
    sa = snap(at)
    if abs(sa-at) > 2.0: snaps.append((i, at, sa))
    zone = 'B' if PRACTICE[0] <= sa < PRACTICE[1] else ('A' if sa < PRACTICE[0] else 'C')
    cards.append({'id':'%s%02d'%(zone,i),'no':i,'kind':kind,'at':round(sa,2),'dur':dur,
                  'kicker':kick,'keyword':key,'sub':sub,'zone':zone})
# 「없어도 되는 컷」 번호. 검토표에서 회색으로 표시된다. 자기 회차에 맞게 바꾼다.
SPARE = {2, 7}
for c in cards: c['spare'] = c['no'] in SPARE
json.dump(cards, open('cards.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)

# ── 정합성 검사 ────────────────────────────────────────
fail=[]
for a,b in zip(cards, cards[1:]):
    if a['at']+a['dur'] > b['at']+0.01:
        fail.append('겹침 #%d(%.1f+%.1f) ↔ #%d(%.1f)'%(a['no'],a['at'],a['dur'],b['no'],b['at']))
for c in cards:
    if c['at']+c['dur'] > END: fail.append('영상 밖 #%d'%c['no'])
    if c['zone']=='B' and c['kind']=='full': fail.append('⛔실습 구간 풀프레임 #%d'%c['no'])
print('스냅 2초 초과:', snaps if snaps else '없음')
print('FAIL:', len(fail))
for f in fail: print('  -', f)
from collections import Counter
print('구간:', Counter(c['zone'] for c in cards), '· 종류:', Counter(c['kind'] for c in cards))
print('총 %d컷 · 영상 %.1fs · 평균 %.1f초에 한 컷'%(len(cards), END, END/len(cards)))
