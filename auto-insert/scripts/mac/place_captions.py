#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
place_captions.py — 큐마다 「화자가 어디 있나」를 재서 자막 놓을 자리를 정한다.

  영상 + SRT  →  큐별 프레임 1장  →  Vision(사람·얼굴·글자)  →  배치 결정 + 금지선

★ 프레임 전수를 돌리지 않는다. 큐 하나당 1장이다.
★ 못 찾은 큐는 지어내지 않는다. 직전 판정을 물려받고 'carried' 로 표시한다.
  (AI 영상 27규칙 — 빈자리를 지어내지 않는다)

사용:
  python3 place_captions.py --video v.mp4 --srt v.srt --out 작업폴더 [--every 1] [--keep-frames]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from srt_tools import read_srt, tc

HERE = os.path.dirname(os.path.abspath(__file__))
SWIFT = os.path.join(HERE, 'speaker_box.swift')

# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path

# ── 판정 기준 (실측으로 조정) ────────────────────────────────
PERSON_MIN_CONF = 0.45     # 이보다 낮으면 못 믿는다
PERSON_MIN_H    = 0.25     # 화면 높이의 25% 미만이면 화자가 아니다(지나가는 사람 등)
PERSON_MAX_W    = 0.92     # 화면 폭의 92% 넘으면 배경을 잡은 것이다
SUB_BAND_MIN_Y  = 0.58     # 이 아래에 있는 글자만 '구워진 자막'으로 본다
SAFE_MARGIN     = 20       # 금지선 여유 px


def ffmpeg_bin(name='ffmpeg'):
    """libass 가 있는 ffmpeg-full 을 우선 쓴다."""
    full = os.path.join(ff_path.BIN, name)
    return full if os.path.exists(full) else name


def grab_frames(video, times, outdir, jobs=4):
    os.makedirs(outdir, exist_ok=True)
    ff = ffmpeg_bin('ffmpeg')

    def one(i_t):
        i, t = i_t
        p = os.path.join(outdir, 'q%05d.png' % i)
        subprocess.run([ff, '-v', 'error', '-ss', '%.3f' % t, '-i', video,
                        '-frames:v', '1', '-y', p], check=True)
        return p

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        return list(ex.map(one, list(enumerate(times))))


def run_vision(frames, chunk=40):
    """swift 스크립트는 인자로 여러 장을 한 번에 받는다. 너무 길면 나눠 부른다."""
    out = []
    for i in range(0, len(frames), chunk):
        part = frames[i:i + chunk]
        r = subprocess.run(['swift', SWIFT] + part,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('speaker_box.swift 실패:\n' + r.stderr[:800])
        out.extend(json.loads(r.stdout))
    return out


def pick_person(fr):
    """화자 하나를 고른다. 조건을 못 넘으면 None — 지어내지 않는다."""
    W, H = fr['width'], fr['height']
    best = None
    for p in fr['persons']:
        if p['conf'] < PERSON_MIN_CONF:      continue
        if p['h'] < H * PERSON_MIN_H:        continue
        if p['w'] > W * PERSON_MAX_W:        continue
        if best is None or p['conf'] > best['conf']:
            best = p
    return best


def pick_face(fr, person):
    """사람 박스 안에 있는 얼굴만 인정한다."""
    if not fr['faces']:
        return None
    cand = fr['faces']
    if person:
        cand = [f for f in cand
                if f['x'] + f['w'] / 2 >= person['x'] - 40
                and f['x'] + f['w'] / 2 <= person['x'] + person['w'] + 40] or fr['faces']
    return max(cand, key=lambda f: f['conf'])


def sub_band_top(fr):
    """이미 구워진 자막 띠의 윗변. 없으면 None."""
    H = fr['height']
    ys = [t['y'] for t in fr['texts'] if t['y'] >= H * SUB_BAND_MIN_Y]
    return min(ys) if ys else None


def decide(fr):
    """한 프레임 → 배치 판정"""
    W, H = fr['width'], fr['height']
    person = pick_person(fr)
    face = pick_face(fr, person)
    band = sub_band_top(fr)

    if not person:
        return {'found': False, 'side': None, 'anchor_x': None, 'anchor_y': None,
                'person': None, 'face': face, 'band_top': band}

    cx = person['x'] + person['w'] / 2
    side = 'right' if cx < W / 2 else 'left'      # 사람이 왼쪽이면 자막은 오른쪽

    # 세로: 얼굴이 있으면 얼굴 높이에, 없으면 상체 위쪽에 건다
    if face:
        ay = face['y'] + face['h'] / 2
    else:
        ay = person['y'] + person['h'] * 0.18

    # 가로: 사람 박스 바깥쪽 빈 공간의 중앙
    if side == 'right':
        left_edge = min(W - 40, person['x'] + person['w'] + 40)
        ax = (left_edge + (W - 40)) / 2
    else:
        right_edge = max(40, person['x'] - 40)
        ax = (40 + right_edge) / 2

    return {'found': True, 'side': side,
            'anchor_x': round(ax, 1), 'anchor_y': round(ay, 1),
            'person': person, 'face': face, 'band_top': band}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--srt', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--every', type=int, default=1, help='N개 큐마다 1장만 재기(빠르게)')
    ap.add_argument('--offset', type=float, default=0.3, help='큐 시작 후 몇 초 지점을 볼지')
    ap.add_argument('--keep-frames', action='store_true')
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    cues = read_srt(a.srt)
    idx = list(range(0, len(cues), a.every))
    times = [min(cues[i].s + a.offset, cues[i].e - 0.05) for i in idx]
    print('큐 %d개 중 %d개 지점을 잰다' % (len(cues), len(idx)))

    fdir = os.path.join(a.out, '_frames')
    frames = grab_frames(a.video, times, fdir)
    print('프레임 %d장 추출 → Vision 분석' % len(frames))
    vis = run_vision(frames)

    # 금지선: 모든 표본에서 가장 높이 올라온 자막 윗변
    bands = [b for b in (sub_band_top(f) for f in vis) if b]
    guard = (min(bands) - SAFE_MARGIN) if bands else None

    rows, carried, last = [], 0, None
    for k, i in enumerate(idx):
        d = decide(vis[k])
        if not d['found'] and last:
            d = dict(last); d['found'] = False; d['carried'] = True
            carried += 1
        elif d['found']:
            d['carried'] = False
            last = d
        else:
            d['carried'] = False
        c = cues[i]
        rows.append({'n': c.n, 's': c.s, 'e': c.e, 'x': c.x, 'at': times[k],
                     'frame': os.path.basename(frames[k]), **{
                         kk: d.get(kk) for kk in
                         ('found', 'carried', 'side', 'anchor_x', 'anchor_y', 'band_top')}})

    found = sum(1 for r in rows if r['found'])
    res = {
        'video': os.path.abspath(a.video), 'srt': os.path.abspath(a.srt),
        'sampled': len(rows), 'detected': found,
        'detect_rate': round(found / len(rows), 3) if rows else 0,
        'carried': carried,
        'insert_bottom_guard': guard,
        'sub_band_samples': len(bands),
        'rows': rows,
    }
    p = os.path.join(a.out, 'placement.json')
    json.dump(res, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print('─' * 60)
    print('화자 검출 %d/%d (%.0f%%)   물려받음 %d건'
          % (found, len(rows), res['detect_rate'] * 100, carried))
    if guard:
        print('구워진 자막 윗변 %.0fpx (표본 %d) → 인서트 하단 금지선 %.0fpx'
              % (min(bands), len(bands), guard))
    else:
        print('⚠️ 하단 자막을 못 찾았다 — 무자막 영상이거나 자막이 더 위에 있다. 육안 확인 필요')
    sides = {}
    for r in rows:
        sides[r['side']] = sides.get(r['side'], 0) + 1
    print('배치: %s' % sides)
    print('→ %s' % p)

    if not a.keep_frames:
        shutil.rmtree(fdir, ignore_errors=True)


if __name__ == '__main__':
    main()
