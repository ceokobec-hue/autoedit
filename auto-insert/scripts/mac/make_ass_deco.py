#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_ass_deco.py — 장식 자막(ASS)을 굽는다. 본문 자막은 만들지 않는다.

이 공정은 컷편집 때 **본문 자막이 이미 구워져 있는** 영상을 전제로 한다.
그래서 우리가 얹는 건 세 층뿐이다.

  layer 1  인물 옆 자막   placement.json 의 화자 좌표 옆에 말풍선
  layer 2  예능형 자막    리액션 한마디 — 대사를 옮기지 않는다
  layer 3  강조 배지      숫자·핵심어를 크게

★ 박스 폭은 폰트 파일의 advance width 로 잰다(srt_tools.CaptionFont).
  브라우저를 띄우지 않는다. 윈도우판과 같은 방식·같은 숫자.
★ 형광펜 띠는 만들지 않는다 — 좌표가 몇 px 어긋나면 옆 글자를 침범한다(3편 실측).
  강조는 글자색으로 한다.

사용:
  python3 make_ass_deco.py --placement 작업폴더/placement.json \
      --font ~/.autoedit/fonts/NanumSquareNeo-ExtraBold.otf \
      [--variety variety.json] --out deco.ass
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from srt_tools import CaptionFont, get_text_width, split_caption_line

PLAY_W, PLAY_H = 1920, 1080


def ass_time(sec: float) -> str:
    if sec < 0:
        sec = 0
    h = int(sec // 3600); sec -= h * 3600
    m = int(sec // 60);   sec -= m * 60
    return '%d:%02d:%05.2f' % (h, m, sec)


def bgr(hex_rgb: str, alpha: int = 0) -> str:
    """'#RRGGBB' → ASS &HAABBGGRR (ASS 는 BGR 순서다)"""
    s = hex_rgb.lstrip('#')
    r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    return '&H%02X%02X%02X%02X' % (alpha, b, g, r)


def rounded_box(w: float, h: float, r: float = 14) -> str:
    """ASS \\p1 드로잉 — 좌상단 원점 기준 둥근 사각형"""
    w, h, r = round(w), round(h), min(r, w / 2, h / 2)
    return ('m %d %d ' % (r, 0) +
            'l %d 0 ' % (w - r) + 'b %d 0 %d %d %d %d ' % (w, w, r, w, r) +
            'l %d %d ' % (w, h - r) + 'b %d %d %d %d %d %d ' % (w, h, w, h, w - r, h) +
            'l %d %d ' % (r, h) + 'b 0 %d 0 %d 0 %d ' % (h, h, h - r) +
            'l 0 %d ' % r + 'b 0 0 0 0 %d 0' % r)


def clamp_box(x, y, w, h, margin=32):
    x = max(margin, min(x, PLAY_W - margin - w))
    y = max(margin, min(y, PLAY_H - margin - h))
    return x, y


def header(style_side, style_var, guard):
    return f"""[Script Info]
; auto-insert 맥 이식본 — 장식 자막 전용 (본문 자막 없음)
; 인서트 하단 금지선: {guard if guard else '미측정'}
ScriptType: v4.00+
PlayResX: {PLAY_W}
PlayResY: {PLAY_H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Side,{style_side['family']},{style_side['size']},{bgr(style_side['fg'])},&H000000FF,{bgr(style_side['outline'])},&H00000000,0,0,0,0,100,100,0,0,1,{style_side['ow']},0,7,0,0,0,1
Style: Var,{style_var['family']},{style_var['size']},{bgr(style_var['fg'])},&H000000FF,{bgr(style_var['outline'])},&H00000000,0,0,0,0,100,100,0,0,1,{style_var['ow']},2,5,0,0,0,1
Style: Draw,{style_side['family']},20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def subtract_spans(s, e, spans, min_keep=0.4):
    """[s,e) 에서 인서트 구간을 빼고 남는 토막들.

    ★ 인서트 구간엔 인물 옆 자막을 달지 않는다.
      인서트는 화면을 통째로 덮으므로 그 위엔 사람이 없다 — 옆에 달 '옆'이 없다.
      게다가 인서트 자체 글자를 가린다(실측: 인서트의 큰 글씨가 자막에 반쯤 가려졌다).
      윈도우판 키워드 띠도 같은 규칙이다 — caption-style.md 「인서트 구간 자동 숨김」.
    """
    segs = [(s, e)]
    for a, b in sorted(spans):
        nxt = []
        for x, y in segs:
            if b <= x or a >= y:
                nxt.append((x, y)); continue
            if x < a: nxt.append((x, min(a, y)))
            if y > b: nxt.append((max(b, x), y))
        segs = nxt
    return [(x, y) for x, y in segs if y - x >= min_keep]


def build_side_captions(rows, font, st, only_found=False, insert_spans=None):
    """인물 옆 자막 — 말풍선 박스 + 글자"""
    ev = []
    size, pad, lead = st['size'], st['pad'], st['lead']
    for r in rows:
        if not r.get('anchor_x'):
            continue
        if only_found and not r['found']:
            continue
        lines = split_caption_line(r['x'], font, size, st['maxw'])
        tw = max(get_text_width(l, font, size) for l in lines)
        th = len(lines) * size * lead
        bw, bh = tw + pad * 2, th + pad * 1.5
        bx, by = clamp_box(r['anchor_x'] - bw / 2, r['anchor_y'] - bh / 2, bw, bh)

        txt = '\\N'.join(lines)
        for a, b in subtract_spans(r['s'], r['e'], insert_spans or []):
            s, e = ass_time(a), ass_time(b)
            # 박스 (layer 1)
            ev.append('Dialogue: 1,%s,%s,Draw,,0,0,0,,{\\pos(%d,%d)\\an7\\p1\\c%s\\1a&H%02X&\\bord0\\shad0}%s{\\p0}'
                      % (s, e, bx, by, bgr(st['box']), st['box_alpha'], rounded_box(bw, bh)))
            # 글자 (layer 2)
            ev.append('Dialogue: 2,%s,%s,Side,,0,0,0,,{\\pos(%d,%d)\\an7}%s'
                      % (s, e, bx + pad, by + pad * 0.75, txt))
    return ev


def build_variety(items, font, st, spans=None):
    """예능형 자막 — 리액션 한마디. 대사를 옮기지 않는다."""
    ev = []
    for it in items:
        if spans and not subtract_spans(it['s'], it['e'], spans, 0.3):
            continue                      # 인서트에 통째로 묻히면 뺀다
        size = it.get('size', st['size'])
        x = it.get('x', PLAY_W / 2)
        y = it.get('y', 180)
        col = it.get('color')
        pre = '{\\pos(%d,%d)\\an5\\fs%d%s}' % (x, y, size,
                                              ('\\c' + bgr(col)) if col else '')
        # 등장 팝 — 0.18초
        pop = '{\\fscx86\\fscy86\\t(0,180,\\fscx100\\fscy100)}'
        ev.append('Dialogue: 3,%s,%s,Var,,0,0,0,,%s%s%s'
                  % (ass_time(it['s']), ass_time(it['e']), pre, pop, it['t']))
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--placement', required=True)
    ap.add_argument('--font', required=True)
    ap.add_argument('--variety')
    ap.add_argument('--out', required=True)
    ap.add_argument('--size', type=float, default=52)
    ap.add_argument('--var-size', type=float, default=104)
    ap.add_argument('--maxw', type=float, default=520)
    ap.add_argument('--fg', default='#FFFFFF')
    ap.add_argument('--box', default='#1A1712')
    ap.add_argument('--box-alpha', type=int, default=0x28, help='0=불투명 255=투명')
    ap.add_argument('--var-fg', default='#FFE24B')
    ap.add_argument('--outline', default='#141414')
    ap.add_argument('--plan', help='compose plan.json — 인서트 구간을 읽어 그 위엔 자막을 안 단다')
    ap.add_argument('--only-found', action='store_true',
                    help='화자를 실제로 찾은 큐에만 단다(물려받은 건 건너뜀)')
    a = ap.parse_args()

    pl = json.load(open(a.placement, encoding='utf-8'))
    font = CaptionFont(a.font)
    fam = font.family()

    st_side = {'family': fam, 'size': a.size, 'fg': a.fg, 'outline': a.outline,
               'ow': 3, 'pad': 26, 'lead': 1.24, 'maxw': a.maxw,
               'box': a.box, 'box_alpha': a.box_alpha}
    st_var = {'family': fam, 'size': a.var_size, 'fg': a.var_fg,
              'outline': a.outline, 'ow': 7}

    spans = []
    if a.plan:
        pj = json.load(open(a.plan, encoding='utf-8'))
        for c in pj.get('inserts', []):
            spans.append((float(c['ts']), float(c['ts']) + float(c['d'])))
        for b in pj.get('bumpers_over', []):
            spans.append((float(b['ts']), float(b['ts']) + float(b['d'])))

    ev = build_side_captions(pl['rows'], font, st_side, a.only_found, spans)
    nvar = 0
    if a.variety:
        items = json.load(open(a.variety, encoding='utf-8'))
        vev = build_variety(items, font, st_var, spans)
        ev += vev
        nvar = len(vev)

    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(header(st_side, st_var, pl.get('insert_bottom_guard')))
        f.write('\n'.join(ev) + '\n')

    print('글자체   : %s' % fam)
    print('인물 옆 자막: %d개  (물려받은 것 %s)'
          % (sum(1 for r in pl['rows'] if r.get('anchor_x') and (r['found'] or not a.only_found)),
             '제외' if a.only_found else '포함'))
    print('예능형 자막: %d개' % nvar)
    if spans:
        print('인서트 구간 %d곳 — 그 위엔 자막을 달지 않았다' % len(spans))
    print('→ %s' % a.out)


if __name__ == '__main__':
    main()
