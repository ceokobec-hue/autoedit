#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compose_mac.py — 합성 3단계 (맥판). compose1~3.ps1 통합 이식.

    1 인서트 덮어쓰기  →  2 자막 굽기  →  3 범퍼 삽입
         길이 그대로        길이 그대로      여기서만 늘어남

★ 순서가 규약이다. 범퍼는 시간을 밀어내므로 자막을 나중에 구우면
  자막 수백 개의 타임코드를 전부 다시 계산해야 한다.

윈도우 원본(compose1~3.ps1)에서 바뀐 것 두 가지
  · 인코더를 코드에 박지 않는다 — 이 컴퓨터에 맞는 것을 platform_tools.py 가 고른다
    (맥 h264_videotoolbox · 윈도우 h264_nvenc 또는 libx264)
  · 조각(seg)을 이어 붙인 즉시 지운다 — 중간 조각이 디스크를 크게 먹는다

계획 파일(JSON) 예:
{
  "work": "~/작업폴더/내영상",
  "src":  "편집원본.mp4",
  "ass":  "deco.ass",              // 2단계용 (없으면 2단계 건너뜀)
  "fontsdir": "~/.autoedit/fonts",
  "inserts_dir": "09_inserts",
  "inserts":     [{"id":"INS-01","ts":12.5,"d":4}],
  "bumpers_dir": "10_bumpers",
  "bumpers_over":[{"file":"b_over.mp4","ts":300,"d":2}],
  "bumpers_ins": [{"file":"b_ch1.mp4","at":95.0,"d":2.5}],
  "out": "완성본.mp4"
}
사용:  python3 compose_mac.py --plan plan.json [--stages 1,2,3] [--bitrate 14M]
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
import platform_tools               # 인코더는 OS 마다 다르다 (맥·윈도우·리눅스)
FF_FULL = ff_path.BIN
FFMPEG = os.path.join(FF_FULL, 'ffmpeg') if os.path.exists(os.path.join(FF_FULL, 'ffmpeg')) else 'ffmpeg'
FFPROBE = os.path.join(FF_FULL, 'ffprobe') if os.path.exists(os.path.join(FF_FULL, 'ffprobe')) else 'ffprobe'


def sh(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('ffmpeg 실패:\n%s\n%s' % (' '.join(args[:14]), r.stderr[-1200:]))
    return r


def dur(p):
    return float(subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration',
                                 '-of', 'csv=p=0', p], capture_output=True, text=True,
                                check=True).stdout.strip())


def venc(bitrate, gop=60):
    """이 컴퓨터에 맞는 인코더. concat -c copy 로 이어 붙이려면 모든 조각이 같은 설정이어야 한다.

    ★ platform_tools.venc 는 언제나 같은 답을 주므로 조각들의 설정이 어긋날 일이 없다."""
    return platform_tools.venc(bitrate) + ['-pix_fmt', 'yuv420p',
            '-g', str(gop), '-r', '30', '-video_track_timescale', '30000']


AENC = ['-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2']


def concat(list_path, out, segs, drop=True):
    sh([FFMPEG, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
        '-i', list_path, '-c', 'copy', out])
    if drop:                                  # 이어 붙였으면 조각은 바로 버린다 (디스크)
        for s in segs:
            try: os.remove(s)
            except OSError: pass


def stage1(P, work, bitrate):
    """인서트 덮어쓰기 — 그림만 바꾸고 목소리는 원본을 통째로 다시 씌운다."""
    src = P['src']
    seg = os.path.join(work, 'seg1'); os.makedirs(seg, exist_ok=True)
    for f in os.listdir(seg): os.remove(os.path.join(seg, f))

    ov = [{'f': os.path.join(P.get('inserts_dir', ''), c['id'] + '.mp4'),
           'ts': float(c['ts']), 'd': float(c['d']), 'n': c['id']} for c in P.get('inserts', [])]
    ov += [{'f': os.path.join(P.get('bumpers_dir', ''), b['file']),
            'ts': float(b['ts']), 'd': float(b['d']), 'n': b['file']} for b in P.get('bumpers_over', [])]
    ov.sort(key=lambda o: o['ts'])

    total = dur(src)
    print('원본 %.2f초 · 덮어쓸 구간 %d개' % (total, len(ov)))
    missing = [o['n'] for o in ov if not os.path.exists(o['f'])]
    if missing:
        raise SystemExit('⛔ 인서트 파일이 없다: %s' % ', '.join(missing[:8]))

    E = venc(bitrate) + ['-an']
    files, cur, k = [], 0.0, 0
    for o in ov:
        gap = round(o['ts'] - cur, 3)
        if gap > 0.02:
            k += 1; p = os.path.join(seg, 's%03d.mp4' % k)
            sh([FFMPEG, '-y', '-loglevel', 'error', '-ss', '%.3f' % cur, '-i', src,
                '-t', '%.3f' % gap] + E + [p]); files.append(p)
        k += 1; p = os.path.join(seg, 's%03d.mp4' % k)
        sh([FFMPEG, '-y', '-loglevel', 'error', '-i', o['f'], '-t', '%.3f' % o['d']] + E + [p])
        files.append(p)
        cur = round(o['ts'] + o['d'], 3)
    if total - cur > 0.02:
        k += 1; p = os.path.join(seg, 's%03d.mp4' % k)
        sh([FFMPEG, '-y', '-loglevel', 'error', '-ss', '%.3f' % cur, '-i', src] + E + [p])
        files.append(p)
    print('조각 %d개' % k)

    lf = os.path.join(work, 'concat1.txt')
    open(lf, 'w', encoding='utf-8').write('\n'.join("file '%s'" % f for f in files) + '\n')
    vonly = os.path.join(work, 'v_only.mp4')
    concat(lf, vonly, files)

    v1 = os.path.join(work, 'v1.mp4')
    sh([FFMPEG, '-y', '-loglevel', 'error', '-i', vonly, '-i', src,
        '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart', v1])
    os.remove(vonly)
    d1 = dur(v1)
    ok = abs(d1 - total) <= 0.05
    print('1단계 %s v1.mp4  %.2f초 (원본 %.2f · 차이 %+.2f)'
          % ('✅' if ok else '⛔', d1, total, d1 - total))
    if not ok:
        raise SystemExit('⛔ 길이가 어긋났다 — 덮어쓰기는 길이가 변하면 안 된다')
    print('★ 길이가 맞아도 내용은 틀릴 수 있다. 콘택트시트로 눈으로 볼 것')
    return v1


def stage2(P, work, bitrate):
    """자막 굽기 — 원본 타임라인 그대로라 시각을 손댈 필요가 없다."""
    v1 = os.path.join(work, 'v1.mp4')
    src = v1 if os.path.exists(v1) else P['src']
    ass = P.get('ass')
    if not ass or not os.path.exists(ass):
        print('2단계 건너뜀 — ass 파일 없음'); return src
    fd = P.get('fontsdir', os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts')))
    v2 = os.path.join(work, 'v2.mp4')
    # ass 는 작업 디렉토리 기준 상대 경로가 안전하다
    cwd = os.getcwd(); os.chdir(os.path.dirname(os.path.abspath(ass)) or '.')
    try:
        sh([FFMPEG, '-y', '-loglevel', 'error', '-i', os.path.abspath(src),
            '-vf', 'subtitles=%s:fontsdir=%s' % (os.path.basename(ass), fd)]
           + venc(bitrate) + ['-c:a', 'copy', '-movflags', '+faststart', v2])
    finally:
        os.chdir(cwd)
    print('2단계 ✅ v2.mp4  %.2f초  %.1f MB' % (dur(v2), os.path.getsize(v2) / 1e6))
    print('★ 강조 큐 시작 시각을 직접 집어 프레임을 뽑아 볼 것 — 색·자간은 눈으로만 잡힌다')
    return v2


def stage3(P, work, bitrate, prev):
    """범퍼 삽입 — 여기서만 길이가 늘어난다. 범퍼는 무음이라 무음 트랙을 붙여야 이어 붙는다."""
    bl = P.get('bumpers_ins', [])
    if not bl:
        print('3단계 건너뜀 — 삽입 범퍼 없음'); return prev
    seg = os.path.join(work, 'seg3'); os.makedirs(seg, exist_ok=True)
    for f in os.listdir(seg): os.remove(os.path.join(seg, f))

    V, A = venc(bitrate), AENC
    mid = sorted([b for b in bl if float(b['at']) < 99000], key=lambda b: float(b['at']))
    tail = [b for b in bl if float(b['at']) >= 99000]
    print('중간 삽입 %d장 · 끝 붙임 %d장' % (len(mid), len(tail)))

    files, cur, k = [], 0.0, 0
    for b in mid:
        at = float(b['at']); gap = round(at - cur, 3)
        if gap > 0.02:
            k += 1; p = os.path.join(seg, 's%03d.mp4' % k)
            sh([FFMPEG, '-y', '-loglevel', 'error', '-ss', '%.3f' % cur, '-i', prev,
                '-t', '%.3f' % gap] + V + A + [p]); files.append(p)
        k += 1; p = os.path.join(seg, 's%03d.mp4' % k)
        sh([FFMPEG, '-y', '-loglevel', 'error', '-i', os.path.join(P.get('bumpers_dir', ''), b['file']),
            '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-map', '0:v:0', '-map', '1:a:0',
            '-t', '%.3f' % float(b['d']), '-shortest'] + V + A + [p]); files.append(p)
        cur = at
    k += 1; p = os.path.join(seg, 's%03d.mp4' % k)
    sh([FFMPEG, '-y', '-loglevel', 'error', '-ss', '%.3f' % cur, '-i', prev] + V + A + [p])
    files.append(p)
    for b in tail:
        k += 1; p = os.path.join(seg, 's%03d.mp4' % k)
        sh([FFMPEG, '-y', '-loglevel', 'error', '-i', os.path.join(P.get('bumpers_dir', ''), b['file']),
            '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-map', '0:v:0', '-map', '1:a:0',
            '-t', '%.3f' % float(b['d']), '-shortest'] + V + A + [p]); files.append(p)

    lf = os.path.join(work, 'concat3.txt')
    open(lf, 'w', encoding='utf-8').write('\n'.join("file '%s'" % f for f in files) + '\n')
    out = P.get('out') or os.path.join(work, '완성본.mp4')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    concat(lf, out, files)

    d, expect = dur(out), dur(prev) + sum(float(b['d']) for b in bl)
    ok = abs(d - expect) <= 0.2
    print('3단계 %s %s  %d:%02d  %.1f MB  (기대 %.1f초 · 차이 %+.2f)'
          % ('✅' if ok else '⛔', os.path.basename(out), int(d // 60), int(d % 60),
             os.path.getsize(out) / 1e6, expect, d - expect))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True)
    ap.add_argument('--stages', default='1,2,3')
    ap.add_argument('--bitrate', default='14M',
                    help='목표 비트레이트 (libx264 로 굽을 때는 «상한선»이 됩니다)')
    a = ap.parse_args()

    P = json.load(open(a.plan, encoding='utf-8'))
    base = os.path.dirname(os.path.abspath(a.plan))
    for k in ('work', 'src', 'ass', 'fontsdir', 'inserts_dir', 'bumpers_dir', 'out'):
        if P.get(k):
            v = os.path.expanduser(P[k])
            P[k] = v if os.path.isabs(v) else os.path.join(base, v)
    work = P['work']; os.makedirs(work, exist_ok=True)

    st = set(a.stages.split(','))
    cur = P['src']
    if '1' in st: cur = stage1(P, work, a.bitrate)
    elif os.path.exists(os.path.join(work, 'v1.mp4')): cur = os.path.join(work, 'v1.mp4')
    if '2' in st: cur = stage2(P, work, a.bitrate)
    elif os.path.exists(os.path.join(work, 'v2.mp4')): cur = os.path.join(work, 'v2.mp4')
    if '3' in st: cur = stage3(P, work, a.bitrate, cur)
    print('\n최종: %s' % cur)


if __name__ == '__main__':
    main()
