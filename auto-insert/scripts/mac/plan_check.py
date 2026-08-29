#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plan_check.py — 정합성 검사. 하나라도 걸리면 제작에 들어가지 않는다.

원본 plan_check.ps1 이식. 윈도우판이 겪은 함정 하나가 여기서 사라진다 —
PowerShell 은 배열 리터럴 안의 산술식을 두 원소로 쪼개서 겹침 검사를 통째로
무력화시켰다(에러 없이 "✅ 겹침 없음"이 떴다). 파이썬엔 그 함정이 없다.
대신 새 함정을 만들지 않도록 원소 수를 여기서도 확인한다.

사용:
  python3 plan_check.py --plan plan.json [--protect 440:455 --protect 1020:1035]
"""
import argparse
import json
import os
import subprocess
import sys

# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
FF_FULL = ff_path.FFPROBE
FFPROBE = FF_FULL if os.path.exists(FF_FULL) else 'ffprobe'


def tc(s):
    return '%02d:%04.1f' % (int(s // 60), s % 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True)
    ap.add_argument('--protect', action='append', default=[],
                    help='살릴 구간 "시작초:끝초" — 여러 번 줄 수 있다')
    a = ap.parse_args()

    base = os.path.dirname(os.path.abspath(a.plan))
    P = json.load(open(a.plan, encoding='utf-8'))
    fail = 0

    def rel(k):
        v = P.get(k)
        if not v: return None
        v = os.path.expanduser(v)
        return v if os.path.isabs(v) else os.path.join(base, v)

    # 덮어쓰기 구간 (인서트 + 덮어쓰기 범퍼)
    ov = []
    for c in P.get('inserts', []):
        ov.append((float(c['ts']), float(c['ts']) + float(c['d']), c['id']))
    for b in P.get('bumpers_over', []):
        ov.append((float(b['ts']), float(b['ts']) + float(b['d']), b['file']))
    for t in ov:
        if len(t) != 3:
            print('⛔ 내부 오류: 구간 원소 수 %d (3이어야 함)' % len(t)); sys.exit(1)
    ov.sort(key=lambda t: t[0])

    # 1. 겹침
    n = 0
    for k in range(1, len(ov)):
        if ov[k][0] < ov[k - 1][1] - 1e-6:
            print('⛔ 겹침: %s 끝 %s > %s 시작 %s  → 앞 컷을 짧게 자를 것'
                  % (ov[k - 1][2], tc(ov[k - 1][1]), ov[k][2], tc(ov[k][0]))); n += 1
    print('✅ 덮어쓰기 겹침 없음 (%d구간)' % len(ov) if n == 0 else '')
    fail += n

    # 2. 범퍼 삽입점이 인서트 내부에 떨어지는가 → 인서트가 반으로 잘린다
    n = 0
    for b in P.get('bumpers_ins', []):
        at = float(b['at'])
        if at >= 99000: continue
        for s, e, name in ov:
            if s < at < e:
                print('⛔ 삽입점 %s 이 %s 구간 내부 → 인서트가 잘린다' % (tc(at), name)); n += 1
    if n == 0: print('✅ 삽입점 충돌 없음')
    fail += n

    # 3. 보호 구간 침범 — 보호가 항상 이긴다
    prot = []
    for p in a.protect:
        s, e = p.split(':'); prot.append((float(s), float(e)))
    n = 0
    for ps, pe in prot:
        for s, e, name in ov:
            if s < pe and e > ps:
                print('⛔ 보호구간 %s~%s 침범: %s  → 밀거나 자르거나 뺀다(보호가 우선)'
                      % (tc(ps), tc(pe), name)); n += 1
        for b in P.get('bumpers_ins', []):
            at = float(b['at'])
            if at < 99000 and ps < at < pe:
                print('⛔ 보호구간 안에 범퍼 삽입점: %s' % tc(at)); n += 1
    if prot and n == 0: print('✅ 보호구간 %d개 침범 없음' % len(prot))
    fail += n

    # 4. 파일 실재 — 없는 인서트를 걸러야 합성 도중에 안 죽는다
    n = 0
    for c in P.get('inserts', []):
        p = os.path.join(rel('inserts_dir') or '', c['id'] + '.mp4')
        if not os.path.exists(p): print('⛔ 인서트 파일 없음: %s' % p); n += 1
    for b in P.get('bumpers_over', []) + P.get('bumpers_ins', []):
        p = os.path.join(rel('bumpers_dir') or '', b['file'])
        if not os.path.exists(p): print('⛔ 범퍼 파일 없음: %s' % p); n += 1
    if n == 0: print('✅ 자산 파일 전부 있음')
    fail += n

    # 5. 길이 — 원본을 넘어가는 인서트, 완성 예상 길이
    src = rel('src')
    if src and os.path.exists(src):
        vd = float(subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration',
                                   '-of', 'csv=p=0', src], capture_output=True, text=True,
                                  check=True).stdout.strip())
        over = [t for t in ov if t[1] > vd + 0.02]
        for s, e, name in over:
            print('⛔ %s 가 원본 끝(%s)을 넘는다 → %s' % (name, tc(vd), tc(e)))
        fail += len(over)
        add = sum(float(b['d']) for b in P.get('bumpers_ins', []))
        print('원본 %s + 삽입 %.1f초 → 완성 예상 %s' % (tc(vd), add, tc(vd + add)))

    print('\n' + ('✅ 전부 통과 — 제작 진행 가능' if fail == 0
                  else '⛔ %d건 — 해소한 뒤 다시 검사할 것' % fail))
    sys.exit(0 if fail == 0 else 2)


if __name__ == '__main__':
    main()
