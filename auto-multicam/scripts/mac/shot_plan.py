#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shot_plan.py — 문장 목록 + 판서 구간으로 «촘촘한 샷 계획»을 짠다.

⛔ 메인은 «고정 와이드 카메라»다. 클로즈업(짐벌·핸드헬드)은 컷인 전용이다 —
   메인으로 쓰면 화면이 계속 움직여 보는 사람이 지친다.

샷 네 가지
  W  메인캠 100%  와이드 (기본)
  Z  메인캠 135%  판서 확대 — 판서 중에만
  M  메인캠 120%  살짝 당긴 와이드 — 같은 그림이 이어지는 걸 깨는 세 번째 톤
  D  컷인캠       클로즈업 — 강조어·물음표·리듬

박자가 뻔해지지 않게 하는 법
  ① 목표 길이를 «직전 샷과 반대로» 잡는다. 앞이 짧았으면 길게, 길었으면 짧게.
  ② 자르는 자리는 «말하는 사람이 숨 쉬는 곳»(문장 사이 쉼)을 우선한다.
  ③ 같은 그림이 3연속 나오지 않게 한다.
  ④ 판서 중에는 컷인캠으로 나가지 않는다 — 글씨 쓰는 걸 놓치면 안 되므로 Z↔W 안에서만 바꾼다.

★ 순서가 중요하다: «길이를 다 정리한 뒤»에 카메라를 배정한다.
  먼저 배정하고 나중에 쪼개면 쪼갠 두 조각이 같은 그림이라 화면이 안 바뀐다.
"""
import argparse, json
import statistics as st

ANCH = {'board': (740, 390), 'center': (960, 540), 'face': (960, 520)}
NAMES = {'W': '메인캠 와이드', 'Z': '메인캠 135% 보드', 'D': '컷인캠 클로즈업'}
# 보드를 가리키며 말하는 신호 — 이때는 보드를 크게 보여준다
POINT = ['여기', '이거', '이걸', '이렇게', '보시면', '보면', '보세요', '적어', '써놨', '쓴 것',
         '이 단어', '요거', '위에', '아래', '오른쪽', '왼쪽', '동그라미', '표시']


def on_board(s, e, segs, frac=0.4):
    for g in segs:
        ov = min(e, g['end']) - max(s, g['start'])
        if ov > 0 and ov >= (e - s) * frac:
            return True
    return False


def group(S, short, long_, mx):
    """① 문장을 이어붙여 샷을 만든다 — 목표 길이를 직전과 반대로 잡는다"""
    shots, i, prev = [], 0, short
    while i < len(S):
        target = long_ if prev <= (short + long_) / 2 else short
        board0 = S[i]['board']
        j = i + 1
        while j < len(S):
            if S[j]['board'] != board0:
                break
            cur = S[j - 1]['e'] - S[i]['s']
            if cur >= target:
                break
            if cur >= target * 0.62 and S[j]['gap_before'] >= 0.35:
                break
            if S[j]['e'] - S[i]['s'] > mx:
                break
            j += 1
        shots.append({'s': S[i]['s'], 'e': S[j - 1]['e'], 'board': board0, 'grp': S[i:j]})
        prev = shots[-1]['e'] - shots[-1]['s']
        i = j
    return shots


def cutpoints(S):
    """자를 수 있는 자리를 한 번만 모아 둔다 — 문장 경계가 1순위, 문장 안 숨 자리가 2순위."""
    pts = [(x['s'], x['gap_before'] + 1.0) for x in S]
    pts += [(b['t'], b['gap']) for x in S for b in x.get('breaths', [])]
    return sorted(set(pts))


def tie(shots, dur):
    """샷 사이 틈(말 없는 구간)을 앞 샷에 붙여 «빈틈 없는 타임라인»으로 만든다."""
    for k in range(len(shots) - 1):
        shots[k]['e'] = shots[k + 1]['s']
    shots[0]['s'] = 0.0
    shots[-1]['e'] = dur
    return shots


def cleanup(shots, pts, mn, mx, rounds=6):
    """짧은 건 합치고 긴 건 쪼갠다. 서로 영향을 주므로 안정될 때까지 반복한다.
    ★ 짧은 샷(깜빡임)이 긴 샷보다 훨씬 나쁘다 — 최소 길이를 최대 길이보다 우선한다."""
    for _ in range(rounds):
        changed = False
        # ① 짧은 샷 제거 — 이웃 중 «합쳐도 덜 길어지는 쪽»에 붙인다
        out = []
        for sh in shots:
            if out and (sh['e'] - sh['s']) < mn:
                out[-1]['e'] = sh['e']; out[-1]['grp'] += sh['grp']; changed = True
            else:
                out.append(sh)
        if len(out) > 1 and (out[0]['e'] - out[0]['s']) < mn:
            out[1]['s'] = out[0]['s']; out[1]['grp'] = out[0]['grp'] + out[1]['grp']
            out.pop(0); changed = True
        shots = out

        # ② 긴 샷 쪼개기
        out = []
        for sh in shots:
            d = sh['e'] - sh['s']
            if d <= mx:
                out.append(sh); continue
            n = max(2, int(round(d / (mx * 0.7))))
            cand = [(t, w) for t, w in pts if sh['s'] + mn < t < sh['e'] - mn]
            if not cand:                       # 자를 자리가 아예 없으면 균등 분할
                cand = [(sh['s'] + d * q / n, 0.0) for q in range(1, n)]
            cuts = sorted(t for t, _ in sorted(cand, key=lambda c: -c[1])[:n - 1])
            prev = sh['s']
            for c in list(cuts) + [sh['e']]:
                if c - prev < mn:
                    continue
                out.append({'s': prev, 'e': c, 'board': sh['board'],
                            'grp': [x for x in sh['grp']
                                    if min(x['e'], c) - max(x['s'], prev) > 0.4] or sh['grp']})
                prev = c
            if out and prev < sh['e'] - 0.01:
                out[-1]['e'] = sh['e']
            changed = True
        shots = out
        if not changed:
            break
    return shots


def assign(shots, MAIN, CUT, budget, B, ink_at, max_run=11.0):
    """④ 길이가 다 정해진 뒤에 카메라·확대를 고른다.

    실패한 시도 넷 (전부 «박자가 뻔해지는» 같은 원인)
      ⛔ 직전 샷으로 다음을 정함 → 상태기계가 되어 W→M→D 3박자 61%
      ⛔ 메인캠 확대를 118/132/135% 로 잘게 나눔 → 크기가 비슷해 «점프컷»(실수처럼 보임)
      ⛔ 매 경계마다 무조건 그림을 바꾸라 강제 → 바꿀 이유가 없는데 바꾸니 W↔Z 62% 교대
      ⛔ 억지 교대를 아예 없앰 → 판서 구간 전체가 한 그림이 되어 114초짜리 샷이 나옴

    ★ 답은 «한 그림이 이어지는 시간»(run)을 관리하는 것이다.
      바꿀 이유가 있으면 바꾸고, 이유가 없어도 한 그림이 13초를 넘기면 바꾼다.
      W(100%) ↔ Z(135%) 는 크기가 35% 차이라 제대로 «컷»으로 읽힌다.
    """
    used, last_d, run_kind, run_len = 0.0, -999.0, None, 0.0
    for n, sh in enumerate(shots):
        d = sh['e'] - sh['s']
        txt = ' '.join(x['text'] for x in sh['grp'])
        hot = sum(1 for x in sh['grp'] if x.get('emph'))
        q = sum(1 for x in sh['grp'] if x.get('question'))
        point = any(w in txt for w in POINT)
        near = any(min(sh['e'], g['end']) - max(sh['s'], g['start']) > 1.5 for g in B)
        stay = sh['board'] or near or (point and ink_at(sh['s']) > 0.55)
        tired = run_len >= max_run                      # 한 그림이 오래됐다

        if n == 0:
            kind = 'W'          # ★ 오프닝은 메인 와이드로 연다. 컷인 카메라로 시작하면 뜬금없다
        elif stay:
            # 판서·보드 설명 — 메인캠만. 확대와 와이드를 오가며 글씨와 상황을 번갈아 본다
            kind = 'W' if run_kind == 'Z' else 'Z'
        elif run_kind == 'D':
            kind = 'W'                                  # 컷인캠 다음은 반드시 메인으로 복귀
        else:
            reason = bool(hot or q) or d <= 8.5 or (sh['s'] - last_d) > 40 or tired
            kind = 'D' if (reason and used + d <= budget) else 'W'
            if kind == 'W' and tired:
                kind = 'Z' if ink_at(sh['s']) > 0.55 else 'W'   # 예산이 없으면 확대로라도 바꾼다

        if kind == 'D':
            cam, zoom, anc = CUT, 100, 'face'
            used += d; last_d = sh['e']
        else:
            cam, zoom, anc = MAIN, (135 if kind == 'Z' else 100), 'board'
        sh.update(kind=kind, cam=cam, zoom=zoom, anchor=anc, hot=hot + q)
        run_len = run_len + d if kind == run_kind else d
        run_kind = kind
    return shots


def merge_same(shots):
    """같은 그림이 이어지면 실제로는 «한 샷»이다 — 합쳐서 샷 수를 정직하게 센다."""
    out = []
    for sh in shots:
        if out and out[-1]['kind'] == sh['kind']:
            out[-1]['e'] = sh['e']; out[-1]['grp'] += sh['grp']
        else:
            out.append(sh)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sentences', required=True); ap.add_argument('--segs', required=True)
    ap.add_argument('--dur', type=float, required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--short', type=float, default=4.5)
    ap.add_argument('--long', type=float, default=9.5)
    ap.add_argument('--max', type=float, default=16.0)
    ap.add_argument('--min', type=float, default=3.2)
    ap.add_argument('--cutin-share', type=float, default=0.28,
                    help='컷인캠(클로즈업)이 차지할 비율. 0.28 = 전체의 28%%')
    ap.add_argument('--main-cam', type=int, default=2)
    ap.add_argument('--ink', default='', help='board_bg.json — 보드에 글씨가 있는지 판단용')
    a = ap.parse_args()

    S = json.load(open(a.sentences))
    B = json.load(open(a.segs))['segs']
    MAIN, CUT = a.main_cam, 3 - a.main_cam
    for x in S:
        x['board'] = on_board(x['s'], x['e'], B)

    shots = group(S, a.short, a.long, a.max)
    shots = tie(shots, a.dur)                       # ★ 틈을 먼저 메워 길이를 확정한 뒤
    shots = cleanup(shots, cutpoints(S), a.min, a.max)   # ★ 짧은·긴 것을 정리하고
    if a.ink:
        bg = json.load(open(a.ink))
        it_, ik_ = bg['t'], bg['ink']
        mx_ = max(ik_) or 1.0
        def ink_at(t):
            k = min(range(len(it_)), key=lambda q: abs(it_[q] - t))
            return ik_[k] / mx_
    else:
        def ink_at(t):
            return 1.0
    shots = assign(shots, MAIN, CUT, a.cutin_share * a.dur, B, ink_at)  # ★ 그다음에 카메라를 고른다
    shots = merge_same(shots)                       # 같은 그림 연속은 한 샷으로 정직하게 합친다

    items = [{'no': k, 'kind': sh['kind'], 'cam': sh['cam'], 'zoom': sh['zoom'],
              'anchor': sh['anchor'], 'start': round(sh['s'], 3), 'end': round(sh['e'], 3),
              'dur': round(sh['e'] - sh['s'], 2), 'keep': True,
              'why': ' '.join(x['text'] for x in sh['grp'])[:80]}
             for k, sh in enumerate(shots, 1)]
    json.dump({'dur': a.dur, 'anchors': ANCH, 'main': MAIN, 'items': items},
              open(a.out, 'w'), ensure_ascii=False, indent=1)

    L = [x['dur'] for x in items]
    cnt = {}
    for x in items:
        cnt[x['kind']] = cnt.get(x['kind'], 0) + x['dur']
    sw = sum(1 for k in range(1, len(items)) if items[k]['cam'] != items[k - 1]['cam'])
    dup = sum(1 for k in range(1, len(items)) if items[k]['kind'] == items[k - 1]['kind'])
    print('샷 %d개 · 평균 %.1f초 (중앙값 %.1f · 최단 %.1f · 최장 %.1f)'
          % (len(items), sum(L) / len(L), st.median(L), min(L), max(L)))
    print('  화면 변화 %d회 · 그중 카메라 전환 %d회 · 같은 그림 연속 %d곳'
          % (len(items) - 1, sw, dup))
    for k in ('W', 'M', 'Z', 'D'):
        if k in cnt:
            print('  %-16s %6.0f초 (%4.1f%%) · %d샷'
                  % (NAMES[k], cnt[k], cnt[k] / a.dur * 100, sum(1 for x in items if x['kind'] == k)))
    import collections
    seq = ''.join(x['kind'] for x in items)
    tri = collections.Counter(seq[i:i + 3] for i in range(len(seq) - 2))
    top = tri.most_common(3)
    print('  3연속 패턴 최다: ' + ' · '.join('%s %.0f%%' % (k, v / (len(seq) - 2) * 100) for k, v in top)
          + '  (상위3 합계 %.0f%% — 낮을수록 안 뻔하다)'
          % (sum(v for _, v in top) / (len(seq) - 2) * 100))
    mono = sum(1 for k in range(2, len(L))
               if max(L[k - 2:k + 1]) / max(min(L[k - 2:k + 1]), .1) < 1.25)
    print('  길이가 거의 같은 3연속: %d곳 (%.0f%%) — 낮을수록 박자가 안 뻔하다'
          % (mono, mono / max(len(L) - 2, 1) * 100))


if __name__ == '__main__':
    main()
