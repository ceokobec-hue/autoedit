#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_plan.py — 판서 구간 + 대본으로 «전환·확대 후보»를 만든다.

후보 네 종류
  판서/지움  보드 잉크가 늘거나 급감 → CAM2 (근거 = 실측 잉크 변화)
  리듬       CAM1이 너무 오래 이어질 때 끼우는 짧은 CAM2 (기본 끔)
  확대       강조 신호어 근처 CAM1 → 120% (기본 끔)

시작·끝은 «문장 경계»(SRT 큐)로 옮긴다. 문장 한가운데서 카메라가 바뀌면 어색하다.
"""
import argparse, json, os, re
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (전환 후보 계산).\n'
        '   이 도구의 부품은 ~/.autoedit/venv 라는 \u00ab작은 방\u00bb 안에 있습니다.\n'
        '   그 방의 파이썬으로 부르세요:\n'
        '     {} {} {}'.format(_v, _o.path.abspath(__file__), ' '.join(_s.argv[1:])) +
        '\n   방이 아직 없다면 설치.md 2단계를 보세요 (python3 doctor.py 로 확인).')

EMPH = ['핵심', '중요', '반드시', '포인트', '정리하', '기억', '결론', '명심', '절대']

# 확대 기본 틀 — 화면에서 어디를 남길지.
# ⛔ 절대좌표(픽셀)로 적으면 1080p 아닌 영상에서 엉뚱한 자리를 가리킨다 → «비율(0~1)»로 적는다.
#    (옛 계획 파일의 절대좌표도 vgeom.as_ratio 가 알아서 받아 준다)
ANCHOR = {
    'board':  (0.385, 0.361),   # CAM2 · 판서 + 강사 얼굴이 같이 들어오는 자리
    'center': (0.500, 0.500),
    'face':   (0.500, 0.481),   # CAM1 · 천장을 덜어내고 얼굴을 키운다
}


def read_srt(path):
    txt = open(path, encoding='utf-8').read()
    out = []
    for m in re.finditer(r'\n?(\d+)\n(\d\d):(\d\d):(\d\d),(\d\d\d) --> (\d\d):(\d\d):(\d\d),(\d\d\d)\n(.*?)(?=\n\n|\Z)', txt, re.S):
        g = m.groups()
        out.append({'s': int(g[1]) * 3600 + int(g[2]) * 60 + int(g[3]) + int(g[4]) / 1000,
                    'e': int(g[5]) * 3600 + int(g[6]) * 60 + int(g[7]) + int(g[8]) / 1000,
                    'x': ' '.join(g[9].split())})
    return out


def snap(v, cues, win=2.5):
    best, bd = v, win
    for c in cues:
        for cand in (c['s'], c['e']):
            if abs(cand - v) < bd:
                best, bd = cand, abs(cand - v)
    return round(best, 3)


def main():
    ap = argparse.ArgumentParser(description='판서 구간 + 자막으로 «전환 후보»를 만든다')
    ap.add_argument('--segs', required=True, help='판서 구간 JSON (analyze_bg.py 산출)')
    ap.add_argument('--srt', required=True, help='자막 SRT — 문장 경계에서 자르려고 쓴다')
    ap.add_argument('--dur', type=float, required=True, help='영상 길이(초)')
    ap.add_argument('--out', required=True, help='나갈 전환 후보 JSON')
    ap.add_argument('--rhythm-gap', type=float, default=100.0,
                    help='리듬용 컷을 몇 초마다 넣을지 (기본 100초)')
    ap.add_argument('--board-zoom', type=int, default=135,
                    help='판서 확대 배율 %% (기본 135)')
    ap.add_argument('--main', type=int, default=1, choices=(1, 2),
                    help='빈 구간을 채울 «메인 카메라». 나머지 한 대가 컷인용이 된다')
    a = ap.parse_args()

    for _p, _who in ((a.segs, 'python3 analyze_bg.py --dir <프레임폴더> --dur <초> 를 먼저 돌리세요'),
                     (a.srt,  '자막 SRT 를 --srt 로 주세요')):
        if not os.path.exists(_p):
            raise SystemExit('⛔ %s 이(가) 없습니다.\n   → %s' % (_p, _who))
    S = json.load(open(a.segs)); cues = read_srt(a.srt)
    items = []
    BOARD_CAM = 2          # 판서가 보이는 카메라(고정 삼각대) — 실측으로 확인된 값
    CUTIN_CAM = 1 if a.main == 2 else 2
    for s in S['segs']:
        items.append({'kind': s['kind'], 'cam': BOARD_CAM,
                      'start': snap(max(0.0, s['start']), cues), 'end': snap(min(a.dur, s['end']), cues),
                      'zoom': a.board_zoom, 'anchor': 'board', 'keep': True,
                      'why': '보드 잉크 %+.2f (실측)' % s['gain'], 'i0': s['i0'], 'i1': s['i1']})

    # 겹치거나 붙은 것 합치기 — 지우고 바로 새로 쓰면 두 구간이 겹친다
    items.sort(key=lambda c: c['start'])
    merged = []
    for c in items:
        if merged and c['start'] <= merged[-1]['end'] + 3.0:
            m = merged[-1]
            m['end'] = max(m['end'], c['end']); m['i1'] = max(m['i1'], c['i1'])
            if c['kind'] not in m['kind']:
                m['kind'] += '+' + c['kind']
            m['why'] += ' / ' + c['why']
        else:
            merged.append(dict(c))
    items = merged

    # ── 리듬 컷 ──────────────────────────────────────────────
    marks = [(0.0, items[0]['start'] if items else a.dur)]
    for i, c in enumerate(items):
        nxt = items[i + 1]['start'] if i + 1 < len(items) else a.dur
        marks.append((c['end'], nxt))
    rhythm = []
    for gs, ge in marks:
        span = ge - gs
        if span < a.rhythm_gap:
            continue
        k = int(span // a.rhythm_gap)
        for j in range(1, k + 1):
            c0 = gs + span * j / (k + 1)
            s = snap(c0, cues); e = snap(s + 10.0, cues)
            if e - s >= 6.0 and e < ge - 12:
                rhythm.append({'kind': '리듬', 'cam': CUTIN_CAM, 'start': s, 'end': e, 'zoom': 100,
                               'anchor': 'face' if CUTIN_CAM == 1 else 'center', 'keep': False,
                               'why': '메인이 %.0f초 연속 — 화면 환기' % span})

    # ── 확대 후보 ────────────────────────────────────────────
    busy = items + rhythm
    inside = lambda t: any(c['start'] - 1 <= t <= c['end'] + 1 for c in busy)
    zooms, last = [], -99
    for c in cues:
        if c['s'] - last < 50 or inside(c['s']) or inside(c['e'] + 4):
            continue
        w = next((k for k in EMPH if k in c['x']), None)
        if not w:
            continue
        s, e = snap(c['s'], cues), snap(min(c['e'] + 4.0, a.dur), cues)
        if e - s < 4.5:
            continue
        zooms.append({'kind': '강조', 'cam': CUTIN_CAM, 'start': s, 'end': e,
                      'zoom': 100 if CUTIN_CAM == 1 else 120,
                      'anchor': 'face' if CUTIN_CAM == 1 else 'center', 'keep': False,
                      'why': '강조어 「%s」 · %s' % (w, c['x'][:38])})
        last = c['s']

    allc = sorted(items + rhythm + zooms, key=lambda c: c['start'])
    for i, c in enumerate(allc, 1):
        c['no'] = i; c['dur'] = round(c['end'] - c['start'], 2)

    json.dump({'dur': a.dur, 'anchors': ANCHOR, 'items': allc}, open(a.out, 'w'), ensure_ascii=False, indent=1)

    on = [c for c in allc if c['keep']]
    print('후보 %d개 (기본 켜짐 %d개 · %.0f초 = %.0f%%)'
          % (len(allc), len(on), sum(c['dur'] for c in on), sum(c['dur'] for c in on) / a.dur * 100))
    print('\n| 번호 | 시각 | 길이 | CAM | 종류 | 기본 | 근거 |')
    for c in allc:
        print('| %2d | %02d:%02d~%02d:%02d | %5.1f초 | %d | %-6s | %s | %s |'
              % (c['no'], int(c['start']) // 60, int(c['start']) % 60, int(c['end']) // 60,
                 int(c['end']) % 60, c['dur'], c['cam'], c['kind'],
                 '켬 %d%%' % c['zoom'] if c['keep'] else '끔   ', c['why'][:46]))


if __name__ == '__main__':
    main()
