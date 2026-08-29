#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sentences.py — whisper JSON(토큰 시각)에서 «문장» 단위 목록을 만든다.

왜 자막 큐를 그대로 못 쓰나
  whisper 의 큐는 «시간»으로 잘린 덩어리라 문장 한가운데서 끊긴다.
  («…첫 시간 시작 한번 해 / 보도록 하겠습니다.») 그 자리에서 카메라를 바꾸면 말이 잘린 느낌이 난다.
  그래서 토큰 시각을 이어붙여 «마침표·물음표»와 «숨 쉬는 쉼»으로 다시 자른다.

산출: [{i, s, e, text, gap_before, emph, question, exclam, nwords}]

⛔ 낱말 시각(t_dtw)은 «-nfa» 없이는 전부 −1 로 나온다. 에러는 안 난다.
   자막을 이렇게 만들어야 한다:
     whisper-cli -m ggml-small.bin -f A.wav -l ko -ojf -dtw small -nfa -of captions
   (-ojf = 낱말 단위 JSON · -dtw small = 낱말 시각 계산 · -nfa = flash attention 끄기)
"""
import argparse, json, os, re, sys

WHISPER_HOWTO = (
    '   자막을 이렇게 다시 만들어 주세요:\n'
    '     whisper-cli -m ggml-small.bin -f <소리.wav> -l ko -ojf -dtw small -nfa -of captions\n'
    '     ⛔ «-nfa» 가 핵심입니다. 이게 없으면 whisper 가 낱말 시각을 전부 −1 로 내보내면서\n'
    '        에러는 내지 않습니다. 그러면 문장이 «시간 덩어리»로 잘려 컷이 말 한가운데서 끊깁니다.')

END = '.?!'
EMPH = ['핵심', '중요', '반드시', '포인트', '기억하', '결론', '명심', '절대', '꼭 ', '정말',
        '제일', '가장', '바로 이', '이것만', '딱 하나']


def load(path):
    if not os.path.exists(path):
        raise SystemExit('⛔ %s 이(가) 없습니다.\n%s' % (path, WHISPER_HOWTO))
    d = json.load(open(path, encoding='utf-8'))
    if 'transcription' not in d:
        raise SystemExit('⛔ %s 은(는) whisper.cpp 의 «낱말 단위» JSON 이 아닙니다.\n%s'
                         % (path, WHISPER_HOWTO))
    toks = []
    n_dtw = 0                     # 낱말 시각이 «실제로» 들어 있는 토큰 수
    for seg in d['transcription']:
        for t in seg.get('tokens', []):
            tx = t.get('text', '')
            if tx.startswith('[_') or not tx.strip():
                continue
            o = t.get('t_dtw', -1)
            off = t['offsets']
            a = off['from'] / 1000.0
            b = off['to'] / 1000.0
            if isinstance(o, (int, float)) and o >= 0:
                a = o / 100.0                      # t_dtw 는 1/100초 단위
                n_dtw += 1
            toks.append({'x': tx, 's': a, 'e': max(b, a)})
    if not toks:
        raise SystemExit('⛔ %s 에서 낱말을 하나도 못 읽었습니다.\n%s' % (path, WHISPER_HOWTO))
    # ⛔⛔ 여기가 «조용한 실패»의 자리다. t_dtw 가 전부 −1 이어도 코드는 그냥 돌아가고
    #     자막 큐 시각(offsets)으로 문장을 자른다 — 결과는 «말 한가운데서 끊기는 컷»이다.
    #     에러도 경고도 없이 품질만 나빠지므로, 여기서 «명시적으로» 세우고 알린다.
    if n_dtw == 0:
        raise SystemExit(
            '⛔ 낱말 시각(t_dtw)이 하나도 없습니다 — 낱말 %d개가 전부 −1 입니다.\n'
            '   «-nfa» 를 빼먹으셨을 가능성이 큽니다.\n%s' % (len(toks), WHISPER_HOWTO))
    if n_dtw < len(toks) * 0.5:
        print('⚠️ 낱말 시각이 %d/%d (%.0f%%) 뿐입니다 — 문장 경계가 거칠어집니다.'
              % (n_dtw, len(toks), n_dtw * 100.0 / len(toks)))
        print(WHISPER_HOWTO)
    toks.sort(key=lambda t: t['s'])
    return toks


def build(toks, gap_split=0.75, min_len=1.2, max_len=14.0):
    out, cur = [], []
    for i, t in enumerate(toks):
        gap = t['s'] - toks[i - 1]['e'] if i else 0.0
        if cur and gap >= gap_split and (t['s'] - cur[0]['s']) >= min_len:
            out.append(cur); cur = []
        cur.append(t)
        txt = t['x'].strip()
        long_enough = (cur[-1]['e'] - cur[0]['s']) >= min_len
        if long_enough and txt and txt[-1] in END:
            out.append(cur); cur = []
        elif (cur[-1]['e'] - cur[0]['s']) >= max_len:
            out.append(cur); cur = []
    if cur:
        out.append(cur)

    res, prev_end = [], 0.0
    for k, g in enumerate(out):
        text = ''.join(t['x'] for t in g).strip()
        s, e = g[0]['s'], g[-1]['e']
        # 문장 «안»의 숨 자리 — 긴 문장은 여기서도 자를 수 있다.
        # 사람은 한 문장을 한 호흡에 다 말하지 않는다.
        breaths = [{'t': round(g[q]['s'], 3), 'gap': round(g[q]['s'] - g[q - 1]['e'], 3)}
                   for q in range(1, len(g))
                   if g[q]['s'] - g[q - 1]['e'] >= 0.22 and s + 2.5 < g[q]['s'] < e - 2.5]
        res.append({'i': k, 's': round(s, 3), 'e': round(e, 3), 'text': text, 'breaths': breaths,
                    'gap_before': round(max(s - prev_end, 0.0), 3),
                    'emph': bool(next((w for w in EMPH if w in text), None)),
                    'question': text.endswith('?'),
                    'nwords': len(text.split())})
        prev_end = e
    return res


def main():
    ap = argparse.ArgumentParser(description='whisper JSON 을 «문장 목록»으로 바꾼다')
    ap.add_argument('--json', required=True,
                    help='whisper.cpp 의 --output-json-full 결과 (낱말 시각 t_dtw 가 있어야 한다)')
    ap.add_argument('--out', required=True, help='나갈 문장 목록 JSON')
    ap.add_argument('--dur', type=float, required=True, help='영상 길이(초)')
    a = ap.parse_args()

    S = build(load(a.json))
    S = [x for x in S if x['s'] < a.dur]
    json.dump(S, open(a.out, 'w'), ensure_ascii=False, indent=1)

    import statistics as st
    L = [x['e'] - x['s'] for x in S]
    G = [x['gap_before'] for x in S[1:]]
    print('문장 %d개 · 평균 %.1f초 (중앙값 %.1f · 최단 %.1f · 최장 %.1f)'
          % (len(S), sum(L) / len(L), st.median(L), min(L), max(L)))
    print('  1분당 %.1f문장 · 강조어 포함 %d개 · 물음표 %d개'
          % (len(S) / (a.dur / 60), sum(x['emph'] for x in S), sum(x['question'] for x in S)))
    # ⛔ 문장이 1개면 «사이»가 없어 G 가 빈 리스트다 → st.median 이 죽는다
    if G:
        print('  문장 사이 쉼: 중앙값 %.2f초 · 0.5초 이상 %d곳 · 1.0초 이상 %d곳'
              % (st.median(G), sum(g >= 0.5 for g in G), sum(g >= 1.0 for g in G)))
    else:
        print('  문장이 1개뿐이라 «문장 사이 쉼»은 잴 것이 없습니다.')
    print('\n앞 12문장')
    for x in S[:12]:
        print('  %6.1f~%6.1f (%4.1f초, 쉼%.2f) %s%s %s'
              % (x['s'], x['e'], x['e'] - x['s'], x['gap_before'],
                 '★' if x['emph'] else ' ', '?' if x['question'] else ' ', x['text'][:52]))


if __name__ == '__main__':
    main()
