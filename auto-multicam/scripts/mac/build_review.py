#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_review.py — 사람이 보고 판정하는 «검토표» HTML 한 장을 만든다.

이 표가 이 파이프라인의 핵심이다. 기계는 «화면이 이렇게 변했다»까지만 말할 수 있고,
«그러니 카메라를 바꿔라»는 판단은 사람이 한다. 그래서 후보마다
  · 지금 화면(CAM1)   · 바꾸면 이렇게(CAM2/확대)   · 이 구간에 «추가된 글씨»
셋을 나란히 보여준다. 10초면 판정된다.

산출물은 자체완결 HTML (그림을 전부 안에 넣어 어디서 열어도 보인다).
"""
import argparse, base64, io, json, os, subprocess
# ⛔ 부품이 «작은 방»(~/.autoedit/venv) 안에 있어 그냥 python3 로는 안 보인다 →
#    스택트레이스 대신 «어떻게 하면 되는지»를 한국어로 알려 준다.
try:
    import numpy as np
except ModuleNotFoundError:
    import sys as _s, os as _o
    _v = _o.path.expanduser('~/.autoedit/venv/bin/python')
    raise SystemExit(
        '\u26d4 numpy 가 없습니다 (검토표 만들기).\n'
        '   이 도구의 부품은 ~/.autoedit/venv 라는 \u00ab작은 방\u00bb 안에 있습니다.\n'
        '   그 방의 파이썬으로 부르세요:\n'
        '     {} {} {}'.format(_v, _o.path.abspath(__file__), ' '.join(_s.argv[1:])) +
        '\n   방이 아직 없다면 설치.md 2단계를 보세요 (python3 doctor.py 로 확인).')

import sys
# ── ffmpeg 경로는 ff_path.py 한 곳에서만 정한다 (저장소 뿌리에 있다) ──
_R = os.path.dirname(os.path.abspath(__file__))
while _R != os.path.dirname(_R) and not os.path.exists(os.path.join(_R, 'ff_path.py')):
    _R = os.path.dirname(_R)
sys.path.insert(0, _R)
import ff_path
import vgeom
FF = ff_path.FFMPEG


def sh(args, inp=None):
    r = subprocess.run(args, capture_output=True, input=inp)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode()[-900:])
    return r.stdout


def frame_jpg(video, t, vf, w=380):
    return sh([FF, '-v', 'error', '-ss', '%.3f' % max(t, 0), '-i', video, '-map', '0:v:0',
               '-frames:v', '1', '-vf', '%s,scale=%d:-1' % (vf, w),
               '-q:v', '5', '-f', 'image2', '-vcodec', 'mjpeg', '-'])


def rgb_jpg(arr, w=380):
    h, wd, _ = arr.shape
    return sh([FF, '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (wd, h),
               '-i', '-', '-vf', 'scale=%d:-1' % w, '-q:v', '5', '-f', 'image2', '-vcodec', 'mjpeg', '-'],
              inp=arr.astype(np.uint8).tobytes())


def b64(jpg):
    return 'data:image/jpeg;base64,' + base64.b64encode(jpg).decode()


def boxblur(img, r):
    H, W = img.shape
    pad = np.pad(img.astype(np.float64), r + 1, mode='edge')
    ii = pad.cumsum(0).cumsum(1)
    y0, y1 = np.arange(H), np.arange(H) + 2 * r + 1
    x0, x1 = np.arange(W), np.arange(W) + 2 * r + 1
    return (ii[np.ix_(y1, x1)] - ii[np.ix_(y0, x1)] - ii[np.ix_(y1, x0)] + ii[np.ix_(y0, x0)]) / ((2 * r + 1) ** 2)


def inkmap(b, r=25, thr=7.0):
    return np.clip(boxblur(b, r) - b.astype(np.float64) - thr, 0, None)


def crop_for(zoom, anchor, anchors, W, H):
    # ⛔ 1920×1080 을 박아 두면 1280×720 원본에서 자르는 사각형이 화면 밖으로 나가
    #    ffmpeg 이 «패킷이 하나도 안 왔다»며 빈 파일을 만든다 → 크기는 영상에서 읽는다.
    return vgeom.crop_vf(zoom, anchors[anchor], W, H) or 'null'


def mmss(v):
    v = max(v, 0)
    return '%02d:%02d' % (int(v) // 60, int(v) % 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cands', required=True); ap.add_argument('--camA', required=True)
    ap.add_argument('--camB', required=True); ap.add_argument('--offset', type=float, required=True)
    ap.add_argument('--bgdir', required=True); ap.add_argument('--sync', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--main', type=int, default=1, choices=(1, 2))
    ap.add_argument('--names', default='CAM1,CAM2',
                    help='두 카메라 이름을 쉼표로. 예: --names "고정캠,짐벌"')
    ap.add_argument('--title', default='멀티캠 전환 검토표')
    a = ap.parse_args()

    C = json.load(open(a.cands)); anchors = C['anchors']; dur = C['dur']
    VW, VH = vgeom.video_size(a.camA)          # ⛔해상도를 코드에 박지 않는다
    print('영상 %dx%d' % (VW, VH))
    NAME = {1: a.names.split(',')[0], 2: a.names.split(',')[1]}
    SRC = {1: a.camA, 2: a.camB}
    MAIN = a.main
    S = json.load(open(a.sync))
    bgs = np.load(os.path.join(a.bgdir, 'bgs.npy'))

    cards = []
    for c in C['items']:
        t = c['start'] + min(2.5, c['dur'] / 3)
        print('  #%02d %s %s' % (c['no'], c['kind'], mmss(c['start'])))
        tm = t + (a.offset if MAIN == 2 else 0.0)
        now = b64(frame_jpg(SRC[MAIN], tm, 'null'))
        tc = t + (a.offset if c['cam'] == 2 else 0.0)
        after = b64(frame_jpg(SRC[c['cam']], tc, crop_for(c['zoom'], c['anchor'], anchors, VW, VH)))

        diff = None
        # ⛔ 'i0' in c 는 «값이 null» 이어도 참이다 → bgs[None] 이 되어 낯선 에러가 난다
        if c.get('i0') is not None and c.get('i1') is not None:
            m0, m1 = inkmap(bgs[c['i0']]), inkmap(bgs[c['i1']])
            base = bgs[c['i1']].astype(np.float32)
            img = np.stack([base * 0.35 + 165] * 3, axis=-1)
            add = np.clip(m1 - m0 - 3, 0, None)
            gone = np.clip(m0 - m1 - 3, 0, None)
            k = lambda x: np.clip(x / 12.0, 0, 1)[..., None]
            img = img * (1 - k(add)) + np.array([214., 32., 32.]) * k(add)      # 추가 = 빨강
            img = img * (1 - k(gone)) + np.array([40., 120., 220.]) * k(gone)   # 지움 = 파랑
            diff = b64(rgb_jpg(np.clip(img, 0, 255)))
        cards.append({**c, 'now': now, 'after': after, 'diff': diff})

    js = json.dumps([{k: v for k, v in c.items() if k not in ('now', 'after', 'diff')} for c in cards], ensure_ascii=False)

    def card_html(c):
        badge = {'판서': 'w', '지움': 'e', '리듬': 'r', '강조': 'z', '확대': 'z'}.get(c['kind'].split('+')[0], 'w')
        same = (c['cam'] == MAIN)
        zopts = ''.join(
            '<label class="zo"><input type="radio" name="z%d" value="%d"%s><span>%d%%</span></label>'
            % (c['no'], z, ' checked' if c['zoom'] == z else '', z)
            for z in (100, 120, 135, 150))
        d = ('<figure><img src="%s" alt="추가된 글씨"><figcaption>이 구간에 <b class="add">추가된 글씨</b> · '
             '<b class="del">지워진 글씨</b></figcaption></figure>' % c['diff']) if c['diff'] else ''
        return f'''<article class="card {'on' if c['keep'] else ''}" id="c{c['no']}" data-no="{c['no']}">
<header><span class="no">{c['no']:02d}</span><span class="bdg b-{badge}">{c['kind']}</span>
<span class="tm">{mmss(c['start'])} ~ {mmss(c['end'])}</span><span class="du">{c['dur']:.0f}초</span>
<span class="cam cam{c['cam']}">{NAME[c['cam']]}{'' if not same else ' (메인 유지)'}</span>
<label class="sw"><input type="checkbox" class="keep"{' checked' if c['keep'] else ''}><span>살림</span></label></header>
<p class="why">{c['why']}</p>
<div class="shots"><figure><img src="{c['now']}" alt="지금"><figcaption>지금 · 메인 {NAME[MAIN]}</figcaption></figure>
<figure><img src="{c['after']}" alt="바꾸면"><figcaption>바꾸면 · {NAME[c['cam']]}{' · %d%%' % c['zoom'] if c['zoom'] > 100 else ''}{' (확대만)' if same else ''}</figcaption></figure>{d}</div>
<div class="zoom">확대 <div class="zs">{zopts}</div></div></article>'''

    on = [c for c in cards if c['keep']]
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{a.title}</title>
<style>
:root{{--bg:#f7f6f3;--pa:#fff;--tx:#1f2328;--mu:#6b7280;--ln:#e3e1dc;--c1:#d8402a;--c2:#1d6fb8;--ok:#1a7f4b}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font:16px/1.65 Pretendard,-apple-system,"Apple SD Gothic Neo",sans-serif;padding-bottom:96px}}
.wrap{{max-width:1180px;margin:0 auto;padding:28px 20px}}
h1{{font-size:29px;margin:0 0 6px;letter-spacing:-.02em}}
.sub{{color:var(--mu);margin:0 0 22px}}
.facts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:22px}}
.f{{background:var(--pa);border:1px solid var(--ln);border-radius:12px;padding:13px 15px}}
.f b{{display:block;font-size:23px;letter-spacing:-.02em}}
.f span{{color:var(--mu);font-size:13px}}
.tl{{background:var(--pa);border:1px solid var(--ln);border-radius:12px;padding:15px;margin-bottom:22px}}
.bar{{position:relative;height:34px;background:var(--c1);border-radius:7px;overflow:hidden}}
.bar i{{position:absolute;top:0;height:100%;background:var(--c2)}}
.bar i.z{{background:#f0a500}}
.bar i.m{{background:#d8402a}}
.lg{{display:flex;gap:16px;font-size:13px;color:var(--mu);margin-top:9px;flex-wrap:wrap}}
.lg s{{display:inline-block;width:13px;height:13px;border-radius:3px;vertical-align:-2px;margin-right:5px}}
.note{{background:#fff8e6;border:1px solid #f0d9a0;border-radius:12px;padding:14px 16px;margin-bottom:22px;font-size:14.5px}}
.card{{background:var(--pa);border:1px solid var(--ln);border-radius:14px;padding:15px 17px;margin-bottom:13px;opacity:.55;transition:.15s}}
.card.on{{opacity:1;border-color:#c9c6bf;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.card header{{display:flex;align-items:center;gap:9px;flex-wrap:wrap}}
.no{{font-weight:700;font-size:19px;min-width:30px}}
.bdg{{font-size:12.5px;font-weight:600;padding:3px 9px;border-radius:20px;color:#fff}}
.b-w{{background:#1d6fb8}}.b-e{{background:#8b5cf6}}.b-r{{background:#6b7280}}.b-z{{background:#f0a500;color:#3a2a00}}
.tm{{font-variant-numeric:tabular-nums;font-weight:600}}
.du{{color:var(--mu);font-size:14px}}
.cam{{font-size:12.5px;font-weight:700;padding:2px 8px;border-radius:5px;border:1.5px solid}}
.cam1{{color:var(--c1);border-color:var(--c1)}}.cam2{{color:var(--c2);border-color:var(--c2)}}
.sw{{margin-left:auto;display:flex;align-items:center;gap:7px;cursor:pointer;user-select:none;
background:#f0efec;border-radius:20px;padding:5px 13px;font-size:14px;font-weight:600}}
.card.on .sw{{background:#e2f3e9;color:var(--ok)}}
.why{{color:var(--mu);font-size:14px;margin:7px 0 11px}}
.shots{{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:11px;align-items:start}}
.shots figure{{margin:0}}
.shots img{{width:100%;height:206px;object-fit:contain;background:#edebe6;border-radius:9px;display:block}}
.shots figcaption{{font-size:12.5px;color:var(--mu);margin-top:4px}}
.add{{color:#d62020}}.del{{color:#2878dc}}
.zoom{{margin-top:11px;display:flex;align-items:center;gap:11px;font-size:14px;color:var(--mu)}}
.zs{{display:flex;gap:6px}}
.zo input{{display:none}}
.zo span{{display:inline-block;padding:5px 12px;border:1px solid var(--ln);border-radius:7px;cursor:pointer;font-size:13.5px;background:#fafaf8}}
.zo input:checked+span{{background:var(--tx);color:#fff;border-color:var(--tx)}}
.foot{{position:fixed;left:0;right:0;bottom:0;background:rgba(255,255,255,.97);border-top:1px solid var(--ln);
padding:13px 20px;display:flex;align-items:center;gap:18px;backdrop-filter:blur(8px);flex-wrap:wrap}}
.foot .st{{font-size:14.5px}}.foot .st b{{font-size:18px}}
button{{margin-left:auto;background:var(--tx);color:#fff;border:0;border-radius:9px;padding:11px 21px;
font-size:15px;font-weight:600;cursor:pointer;font-family:inherit}}
button:disabled{{opacity:.5;cursor:not-allowed}}
.toast{{position:fixed;left:50%;bottom:88px;transform:translateX(-50%) translateY(14px);background:var(--tx);color:#fff;
padding:12px 22px;border-radius:10px;font-size:14.5px;opacity:0;pointer-events:none;transition:.22s}}
.toast.show{{opacity:1;transform:translateX(-50%) translateY(0)}}
.toast.err{{background:#b3261e}}
@media(max-width:640px){{.shots{{grid-template-columns:1fr 1fr}}}}
</style></head><body><div class="wrap">
<h1>{a.title}</h1>
<p class="sub">{mmss(dur)} · <b>메인 = {NAME[MAIN]}</b> · 컷인 = {NAME[3-MAIN]}</p>

<div class="facts">
<div class="f"><b>{S['intercept']:+.3f}초</b><span>두 카메라 시작 차이</span></div>
<div class="f"><b>{S['spread']*29.97:.1f}프레임</b><span>{mmss(dur)} 동안 벌어진 양</span></div>
<div class="f"><b>{len(C['items'])}개</b><span>기계가 찾은 후보</span></div>
<div class="f"><b id="fON">{len(on)}개</b><span>지금 켜진 것</span></div>
<div class="f"><b id="fPCT">{sum(c['dur'] for c in on if c['cam']!=MAIN)/dur*100:.0f}%</b><span>컷인 카메라 노출</span></div>
</div>

<div class="tl"><div class="bar" id="bar"></div><div class="lg">
<span><s style="background:#d8402a"></s>메인 {NAME[MAIN]}</span>
<span><s style="background:#1d6fb8"></s>컷인 {NAME[3-MAIN]}</span>
<span><s style="background:#f0a500"></s>메인 확대</span></div></div>

<div class="note"><b>🙋 이 표는 기계가 «화면이 이렇게 변했다»까지만 말한 것입니다.</b><br>
「판서」는 보드 잉크가 실제로 늘어난 것을 재서 뽑았고 오른쪽 그림에 <b class="add">추가된 글씨</b>가 빨간색으로 표시됩니다.
메인 카메라가 이미 판서를 잡고 있으므로 <b>카메라를 바꾸지 않고 확대만</b> 합니다.<br>
「강조」와 「리듬」은 <b>{NAME[3-MAIN]} 클로즈업으로 컷인</b>하는 제안입니다.<br>
다 고르셨으면 아래 <b>결정 복사하기</b>를 누르고 저에게 붙여넣어 주시면 그대로 렌더합니다.</div>

{''.join(card_html(c) for c in cards)}
</div>
<div class="foot"><span class="st">켜짐 <b id="sON">{len(on)}</b>개 · 컷인 <b id="sPCT">{sum(c['dur'] for c in on if c['cam']!=MAIN)/dur*100:.0f}</b>% · 전환 <b id="sSW">{sum(1 for c in on if c['cam']!=MAIN)*2}</b>회</span>
<button id="copy">결정 복사하기</button></div>
<div class="toast" id="toast"></div>
<script>
const ITEMS={js}, DUR={dur}, MAIN={MAIN};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let busy=false;
function state(){{
  return ITEMS.map(it=>{{
    const el=document.getElementById('c'+it.no);
    return {{...it, keep:el.querySelector('.keep').checked,
      zoom:+el.querySelector('input[name=z'+it.no+']:checked').value}};
  }});
}}
function render(){{
  const st=state().filter(x=>x.keep).sort((a,b)=>a.start-b.start);
  const bar=$('#bar'); bar.innerHTML='';
  let cam2=0;
  st.forEach(x=>{{
    const i=document.createElement('i');
    i.style.left=(x.start/DUR*100)+'%'; i.style.width=Math.max(x.dur/DUR*100,0.25)+'%';
    if(x.cam===MAIN){{ if(x.zoom>100) i.className='z'; else i.className='m'; }} else cam2+=x.dur;
    i.title='#'+x.no+' '+x.kind; bar.appendChild(i);
  }});
  const pct=(cam2/DUR*100).toFixed(0);
  $('#fON').textContent=st.length+'개'; $('#sON').textContent=st.length;
  $('#fPCT').textContent=pct+'%'; $('#sPCT').textContent=pct;
  $('#sSW').textContent=st.filter(x=>x.cam!==MAIN).length*2;
  ITEMS.forEach(it=>document.getElementById('c'+it.no)
    .classList.toggle('on', document.getElementById('c'+it.no).querySelector('.keep').checked));
  try{{ localStorage.setItem('mc260825b', JSON.stringify(st.map(x=>[x.no,x.zoom]))); }}catch(e){{}}
}}
function toast(msg,err){{
  const t=$('#toast'); t.textContent=msg; t.className='toast show'+(err?' err':'');
  setTimeout(()=>t.className='toast',2200);
}}
$$('.keep,.zo input').forEach(el=>el.addEventListener('change',render));
try{{
  const s=JSON.parse(localStorage.getItem('mc260825b')||'null');
  if(s){{ const m=new Map(s);
    ITEMS.forEach(it=>{{ const el=document.getElementById('c'+it.no);
      el.querySelector('.keep').checked=m.has(it.no);
      if(m.has(it.no)) el.querySelector('input[name=z'+it.no+'][value="'+m.get(it.no)+'"]').checked=true; }});
    toast('지난번 선택을 불러왔습니다'); }}
}}catch(e){{}}
render();
$('#copy').addEventListener('click', async e=>{{
  if(busy) return; busy=true;
  const b=e.currentTarget, old=b.textContent;
  b.disabled=true; b.textContent='복사 중…';
  try{{
    const st=state().filter(x=>x.keep).sort((a,b)=>a.start-b.start);
    const txt='멀티캠 결정 260825 | '+st.map(x=>
      x.no+':CAM'+x.cam+':'+x.zoom).join(' ')+' | 총'+st.length+'구간';
    await navigator.clipboard.writeText(txt);
    toast('복사했습니다 — 클로드에게 붙여넣어 주세요');
  }}catch(err){{ toast('복사 실패 — 아래 줄을 직접 긁어 주세요',1);
    const p=document.createElement('pre'); p.style.cssText='user-select:all;padding:12px';
    p.textContent=state().filter(x=>x.keep).map(x=>x.no+':CAM'+x.cam+':'+x.zoom).join(' ');
    $('.wrap').appendChild(p);
  }} finally {{ b.disabled=false; b.textContent=old; busy=false; }}
}});
</script></body></html>'''
    open(a.out, 'w', encoding='utf-8').write(html)
    print('\n저장: %s (%.1fMB)' % (a.out, os.path.getsize(a.out) / 1e6))


if __name__ == '__main__':
    main()
