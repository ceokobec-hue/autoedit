#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRT 도구 (맥 이식본) — 파싱 · 블록 스캔 · 앵커 탐색 · 규격대조 · 폭 실측 · 줄나눔 · 큐 병합

원본: scripts/srt_tools.ps1 (윈도우 PowerShell)
이식 시 바뀐 것은 딱 하나 — 글자 폭을 재는 방법이다.
  윈도우: System.Windows.Media.GlyphTypeface (WPF, 윈도우 전용)
  맥    : fontTools 의 hmtx/cmap 테이블 직접 읽기
둘 다 "폰트 파일 안에 적힌 글자별 advance width"를 읽는 것이라 결과가 같다.
브라우저를 띄우지 않는다.

사용:
  python3 srt_tools.py blocks   자막.srt [--size 20]
  python3 srt_tools.py anchor   자막.srt "출발할게요" "결과물"
  python3 srt_tools.py sync     자막.srt 영상.mp4
  python3 srt_tools.py fontcheck 폰트.otf
  python3 srt_tools.py merge    자막.srt --font 폰트.otf --size 130 --maxw 2280 --out merged.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict, field


# ══════════════════════════════════════════════════════════════
#  파싱
# ══════════════════════════════════════════════════════════════

@dataclass
class Cue:
    n: int
    s: float      # 시작(초)
    e: float      # 끝(초)
    x: str        # 본문


def _parse_tc(t: str) -> float:
    """'00:01:23,456' 또는 '00:01:23.456' → 초"""
    t = t.strip().replace(',', '.')
    parts = t.split(':')
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = '0', parts[0], parts[1]
    else:
        return float(t)
    return int(h) * 3600 + int(m) * 60 + float(s)


def read_srt(path: str) -> list:
    """SRT 파일 → Cue 목록. BOM·CRLF 허용."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        raw = f.read().replace('\r\n', '\n').replace('\r', '\n').split('\n')

    out, i = [], 0
    while i < len(raw):
        if re.match(r'^\s*\d+\s*$', raw[i]) and i + 1 < len(raw) and '-->' in raw[i + 1]:
            a_s, b_s = raw[i + 1].split('-->')[:2]
            a, b = _parse_tc(a_s), _parse_tc(b_s)
            txt, j = '', i + 2
            while j < len(raw) and raw[j].strip() != '':
                txt += raw[j].strip() + ' '
                j += 1
            out.append(Cue(n=int(raw[i].strip()), s=a, e=b, x=txt.strip()))
            i = j
        else:
            i += 1
    return out


def tc(sec: float) -> str:
    """초 → 'mm:ss.f'"""
    neg = sec < 0
    sec = abs(sec)
    m, s = divmod(sec, 60)
    return ('-' if neg else '') + '%02d:%04.1f' % (int(m), s)


def tc_hms(sec: float) -> str:
    """초 → 'mm:ss' (유튜브 챕터용)"""
    m, s = divmod(int(round(sec)), 60)
    return '%02d:%02d' % (m, s)


# ══════════════════════════════════════════════════════════════
#  서사 훑기 · 앵커 · 규격대조
# ══════════════════════════════════════════════════════════════

def show_blocks(cues: list, size: int = 20) -> list:
    """대본 전체를 size초 블록으로 묶어 서사 구조를 한눈에."""
    groups = {}
    for c in cues:
        groups.setdefault(int(c.s // size), []).append(c)
    lines = []
    for k in sorted(groups):
        g = groups[k]
        body = re.sub(r'\s+', ' ', ' '.join(c.x for c in g))
        lines.append('%s #%-4d %s' % (tc_hms(k * size), g[0].n, body))
    return lines


def find_anchor(cues: list, key: str, take: int = 1) -> list:
    """키워드로 정확한 큐 시작 시각을 찾는다. 삽입 지점은 반드시 큐 경계여야 한다."""
    hits = [c for c in cues if key in c.x][:take]
    if not hits:
        return ['  ??:??      [%s]  못 찾음 — 큐가 두 줄로 갈렸을 수 있다. 더 짧은 조각으로 다시' % key]
    return ['%s  #%-4d [%s]  %s' % (tc(c.s), c.n, key, c.x) for c in hits]


def test_sync(cues: list, video_path: str, ffprobe: str = 'ffprobe') -> dict:
    """영상과 SRT가 같은 컷편집본인지. 0.5초를 넘으면 진행하면 안 된다."""
    vd = float(subprocess.run(
        [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', video_path],
        capture_output=True, text=True, check=True).stdout.strip())
    sd = cues[-1].e if cues else 0.0
    gap = round(vd - sd, 2)
    ok = abs(gap) <= 0.5
    return {
        'video_dur': vd, 'srt_end': sd, 'gap': gap, 'ok': ok,
        'msg': ('영상 %s  ·  SRT 끝 %s  ·  차이 %s초\n' % (tc(vd), tc(sd), gap)) +
               ('✅ 같은 컷편집본' if ok else
                '⛔ 싱크 불일치 — 컷을 더 손본 뒤 SRT를 다시 뽑아야 한다. 이 상태로 진행하면 모든 컷이 어긋난다.')
    }


def export_chapters(marks: list) -> list:
    """marks = [{'at': 55.5, 't': '첫 번째 단원'}, ...]  ※ 범퍼 삽입 후 시각으로 줘야 한다"""
    out = ['00:00 시작']
    for m in sorted(marks, key=lambda m: m['at']):
        out.append('%s %s' % (tc_hms(m['at']), m['t']))
    return out


# ══════════════════════════════════════════════════════════════
#  자막 폭 실측 — 폰트 파일의 advance width 를 직접 읽는다
# ══════════════════════════════════════════════════════════════

class CaptionFont:
    """libass 가 실제로 쓸 파일과 같은 것을 줘야 계산이 맞는다."""

    def __init__(self, font_file: str):
        from fontTools.ttLib import TTFont
        self.path = font_file
        self.ttf = TTFont(font_file, fontNumber=0, lazy=True)
        self.upem = self.ttf['head'].unitsPerEm
        self.cmap = self.ttf.getBestCmap()
        self.hmtx = self.ttf['hmtx']
        self._cache = {}

    def advance_em(self, ch: str) -> float:
        """글자 하나의 advance 를 em 비율로. 폰트에 없으면 0.5 (원본과 동일)."""
        cp = ord(ch)
        if cp in self._cache:
            return self._cache[cp]
        g = self.cmap.get(cp)
        if g is None:
            v = 0.5
        else:
            try:
                v = self.hmtx[g][0] / self.upem
            except KeyError:
                v = 0.5
        self._cache[cp] = v
        return v

    def has(self, ch: str) -> bool:
        return ord(ch) in self.cmap

    def family(self) -> str:
        """ASS Fontname 은 파일명이 아니라 패밀리 이름이다 (traps.md 11-b)."""
        best = ''
        for rec in self.ttf['name'].names:
            if rec.nameID == 1:
                try:
                    best = rec.toUnicode()
                except Exception:
                    continue
                if rec.platformID == 3:
                    return best
        return best


def get_text_width(text: str, font: CaptionFont, font_size: float) -> float:
    """글자 폭(px). Pretendard 한글 advance = 0.864em —
    1.0em 으로 어림하면 두 줄 비율을 몇 배로 과대추정한다(추정 27% ↔ 실측 3.4%)."""
    return sum(font.advance_em(ch) for ch in text) * font_size


def missing_glyphs(text: str, font: CaptionFont) -> set:
    """폰트에 없는 글자 — 화면에 □ 로 뜬다."""
    return {ch for ch in text if not ch.isspace() and not font.has(ch)}


def split_caption_line(text: str, font: CaptionFont, font_size: float, max_w: float) -> list:
    """한 줄에 안 들어가면 어절 단위로 두 줄. 두 줄 폭이 가장 비슷해지는 곳에서 자른다."""
    if get_text_width(text, font, font_size) <= max_w:
        return [text]
    ws = [w for w in re.split(r'\s+', text) if w]
    if len(ws) < 2:
        h = -(-len(text) // 2)          # ceil
        return [text[:h], text[h:]]

    best, best_diff = -1, float('inf')
    for k in range(1, len(ws)):
        a, b = ' '.join(ws[:k]), ' '.join(ws[k:])
        wa, wb = get_text_width(a, font, font_size), get_text_width(b, font, font_size)
        if wa > max_w or wb > max_w:
            continue
        d = abs(wa - wb)
        if d < best_diff:
            best_diff, best = d, k
    if best < 0:
        best = max(1, len(ws) // 2)
    return [' '.join(ws[:best]), ' '.join(ws[best:])]


# ══════════════════════════════════════════════════════════════
#  큐 최소 병합
# ══════════════════════════════════════════════════════════════
# 받은 SRT 는 시간/길이 기준으로 기계적으로 잘려 있어 「AI ／ 에이전트에게」처럼
# 한 단어가 두 큐로 갈라진다. 그 자리만 붙인다. 리듬과 타이밍은 건드리지 않는다.
#
#   A 뒤 큐가 조사 하나로 시작   「결과물 ／ 을 만들어」
#   B 앞뒤가 한 낱말을 이룸      「AI ／ 에이전트」 「포장 ／ 이사」
#
# ★ 조사 목록에서 「이·가·은·는·도·만·로·서」를 뺐다. 관형사·부사와 글자가 겹쳐
#   「말한 ／ 이 다섯 가지를」처럼 멀쩡한 경계를 붙여 버린다(실측 오탐 다수).
# ★ 복합어도 앞조각만 보면 「데이터 ／ 아니면」처럼 오탐이 난다. 반드시 쌍으로 본다.

CAPTION_JOSA_HEADS = ['을', '를', '의', '와', '과', '께', '에게', '에서', '한테']

CAPTION_COMPOUND_PAIRS = {
    'AI':       ['에이전트', '비서', '도구', '기술', '모델', '서비스'],
    '포장':     ['이사'],
    '인공':     ['지능'],
    '데이터':   ['베이스', '센터', '분석'],
    '프롬프트': ['엔지니어링'],
    '도메인':   ['지식'],
    '개인':     ['정보'],
    '자동':     ['화'],
    '반자동':   ['화'],
    '에이':     ['전트'],
    '워크':     ['숍', '플로'],
    '이메':     ['일'],
    '스마트':   ['폰', '워치'],
    '비즈니':   ['스'],
    '커뮤니':   ['티', '케이션'],
}

_ENDED_RE_A = re.compile(r'(다|요|죠|까|네|함|음|우|자)\s*[.?!”"\'」]*$')
_ENDED_RE_B = re.compile(r'[.?!”"\'」]\s*$')


def merge_broken_words(cues: list, font: CaptionFont, font_size: float, max_w: float,
                       max_gap: float = 0.12, extra_pairs: dict = None) -> dict:
    pairs = dict(CAPTION_COMPOUND_PAIRS)
    if extra_pairs:
        pairs.update(extra_pairs)

    out, log, cur = [], [], None
    for q in cues:
        if cur is None:
            cur = Cue(q.n, q.s, q.e, q.x)
            continue

        gap = q.s - cur.e
        tail = re.split(r'\s+', cur.x)[-1]
        head = re.split(r'\s+', q.x)[0]

        ended = bool(_ENDED_RE_A.search(cur.x)) or bool(_ENDED_RE_B.search(cur.x))
        is_josa = head in CAPTION_JOSA_HEADS
        is_pair = any(head.startswith(nx) for nx in pairs.get(tail, []))
        fits = get_text_width(cur.x + ' ' + q.x, font, font_size) <= (max_w * 2)

        if gap <= max_gap and not ended and fits and (is_josa or is_pair):
            why = '조사분리' if is_josa else '복합어'
            log.append('  #%-4d [%s] %s ／ %s' % (cur.n, why, cur.x, q.x))
            cur.e = q.e
            cur.x = cur.x + ' ' + q.x
        else:
            out.append(cur)
            cur = Cue(q.n, q.s, q.e, q.x)
    if cur:
        out.append(cur)

    # 번호를 다시 매긴다 — 강조어 표가 큐 번호로 물리기 때문
    for i, c in enumerate(out):
        c.n = i + 1

    return {'cues': out, 'merged': len(log), 'log': log}


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description='SRT 도구 (맥 이식본)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('blocks', help='서사 구조를 N초 블록으로 훑기')
    p.add_argument('srt'); p.add_argument('--size', type=int, default=20)

    p = sub.add_parser('anchor', help='키워드로 정확한 큐 시작 시각 찾기')
    p.add_argument('srt'); p.add_argument('keys', nargs='+')
    p.add_argument('--take', type=int, default=1)

    p = sub.add_parser('sync', help='영상 ↔ SRT 규격 대조 (0.5초 초과면 중단)')
    p.add_argument('srt'); p.add_argument('video')
    p.add_argument('--ffprobe', default='ffprobe')

    p = sub.add_parser('fontcheck', help='폰트 advance width 실측 (0.864em 기준 대조)')
    p.add_argument('font'); p.add_argument('--srt', help='이 회차 자막에 쓰이는 글자가 다 있는지 검사')

    p = sub.add_parser('merge', help='갈라진 낱말 큐 병합')
    p.add_argument('srt'); p.add_argument('--font', required=True)
    p.add_argument('--size', type=float, default=130)
    p.add_argument('--maxw', type=float, default=2280)
    p.add_argument('--maxgap', type=float, default=0.12)
    p.add_argument('--out')

    a = ap.parse_args()

    if a.cmd == 'blocks':
        for ln in show_blocks(read_srt(a.srt), a.size):
            print(ln)

    elif a.cmd == 'anchor':
        cues = read_srt(a.srt)
        for k in a.keys:
            for ln in find_anchor(cues, k, a.take):
                print(ln)

    elif a.cmd == 'sync':
        r = test_sync(read_srt(a.srt), a.video, a.ffprobe)
        print(r['msg'])
        sys.exit(0 if r['ok'] else 2)

    elif a.cmd == 'fontcheck':
        f = CaptionFont(a.font)
        print('파일     : %s' % os.path.basename(a.font))
        print('패밀리   : %s   ← ASS Fontname 에 이 이름을 쓴다' % f.family())
        print('unitsPerEm: %d' % f.upem)
        for ch, label in [('가', '한글'), ('A', '영문 대문자'), ('0', '숫자'), ('—', 'em dash')]:
            if f.has(ch):
                print('  %s(%s) advance = %.4f em' % (ch, label, f.advance_em(ch)))
            else:
                print('  %s(%s) ⛔ 폰트에 없음 — 화면에 □ 로 뜬다' % (ch, label))
        ko = '가나다라마바사아자차카타파하국어글자'
        print('한글 평균 advance = %.4f em  (Pretendard 문서값 0.864 / NanumSquareNeo 0.948)'
              % (sum(f.advance_em(c) for c in ko) / len(ko)))
        if a.srt:
            allt = ''.join(c.x for c in read_srt(a.srt))
            miss = missing_glyphs(allt, f)
            print('이 회차 자막 글자 검사: %s' % ('✅ 빠진 글자 없음' if not miss
                  else '⛔ 빠진 글자 %d개 → %s' % (len(miss), ''.join(sorted(miss))[:60])))

    elif a.cmd == 'merge':
        cues = read_srt(a.srt)
        f = CaptionFont(a.font)
        r = merge_broken_words(cues, f, a.size, a.maxw, a.maxgap)
        print('큐 %d개 → %d개  (병합 %d건)' % (len(cues), len(r['cues']), r['merged']))
        for ln in r['log']:
            print(ln)
        if a.out:
            with open(a.out, 'w', encoding='utf-8') as fh:
                json.dump({'cues': [asdict(c) for c in r['cues']],
                           'merged': r['merged'], 'log': r['log']},
                          fh, ensure_ascii=False, indent=2)
            print('→ %s' % a.out)


if __name__ == '__main__':
    main()
