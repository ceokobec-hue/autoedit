#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""broadcast_overlay.py — 채널 버그(상시) + 단원 소제목 ASS 생성.

판 폭을 폰트 폭으로 실측해서 정한다. ⛔고정폭이면 긴 소제목이 판 밖으로 삐져나온다(실측).
사용: python3 broadcast_overlay.py --chapters chapters.json --out overlay.ass [--channel "내 채널"] [--end 1227.78]
chapters.json = [{"at": 23.2, "title": "첫 번째 단원"}, ...]"""
import json, sys, os
S=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,S)
from srt_tools import CaptionFont, get_text_width
FONTS = os.environ.get('AUTOEDIT_FONTS', os.path.expanduser('~/.autoedit/fonts'))
FONT=os.path.join(FONTS,'Pretendard-Bold.otf')
W,H=2560,1440
import argparse
_ap=argparse.ArgumentParser()
_ap.add_argument('--chapters',required=True); _ap.add_argument('--out',default='overlay.ass')
_ap.add_argument('--channel',default='내 채널'); _ap.add_argument('--end',type=float,required=True)
_a=_ap.parse_args()
CH=[(float(c['at']),c['title']) for c in json.load(open(_a.chapters,encoding='utf-8'))]
CH.sort()
END=_a.end
CHANNEL=_a.channel
def t(s):
    h=int(s//3600); s-=h*3600; m=int(s//60); s-=m*60
    return '%d:%02d:%05.2f'%(h,m,s)
def rect(w,h): return 'm 0 0 l %d 0 l %d %d l 0 %d'%(w,w,h,h)
f=CaptionFont(FONT); fam=f.family()
TS, SS = 42, 30                      # 타이틀 / 소제목 크기
wt = get_text_width(CHANNEL, f, TS)
ev=[]
# ── 버그 판 + 타이틀 : 0초~끝, 소제목 없는 구간은 짧은 판
for i,(a,sub) in enumerate(CH):
    b = CH[i+1][0] if i+1<len(CH) else END
    ws = get_text_width(sub, f, SS)
    plate = int(max(wt+24, ws) + 64); line=int(max(wt+24, ws)+8)
    ev.append('Dialogue: 0,%s,%s,Plate,,0,0,0,,{\\pos(64,46)\\an7\\p1\\c&H000000&\\1a&H6C&\\bord0\\shad0}%s{\\p0}'%(t(a),t(b),rect(plate,126)))
    ev.append('Dialogue: 1,%s,%s,Plate,,0,0,0,,{\\pos(84,64)\\an7\\p1\\c&H2E44E8&\\bord0\\shad0}%s{\\p0}'%(t(a),t(b),rect(9,48)))
    ev.append('Dialogue: 2,%s,%s,Title,,0,0,0,,{\\pos(108,60)\\an7}%s'%(t(a),t(b),CHANNEL))
    ev.append('Dialogue: 1,%s,%s,Plate,,0,0,0,,{\\pos(84,124)\\an7\\p1\\c&HFFFFFF&\\1a&HA6&\\bord0\\shad0}%s{\\p0}'%(t(a),t(b),rect(line,2)))
    ev.append('Dialogue: 2,%s,%s,Sub,,0,0,0,,{\\pos(84,133)\\an7\\fad(300,0)}%s'%(t(a),t(b),sub))
# 첫 단원 전(0~23.2초)은 타이틀만
plate0=int(wt+24+64)
ev.insert(0,'Dialogue: 0,0:00:00.00,%s,Plate,,0,0,0,,{\\pos(64,46)\\an7\\p1\\c&H000000&\\1a&H6C&\\bord0\\shad0}%s{\\p0}'%(t(CH[0][0]),rect(plate0,86)))
ev.insert(1,'Dialogue: 1,0:00:00.00,%s,Plate,,0,0,0,,{\\pos(84,64)\\an7\\p1\\c&H2E44E8&\\bord0\\shad0}%s{\\p0}'%(t(CH[0][0]),rect(9,48)))
ev.insert(2,'Dialogue: 2,0:00:00.00,%s,Title,,0,0,0,,{\\pos(108,60)\\an7}%s'%(t(CH[0][0]),CHANNEL))
hdr=f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{fam},{TS},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Sub,{fam},{SS},&H00A0C9E8,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Plate,{fam},20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open(_a.out,'w',encoding='utf-8').write(hdr+'\n'.join(ev)+'\n')
print('✅ %s  글자체'%_a.out if False else '✅ '+_a.out+'  글자체=%s  단원 %d개  이벤트 %d개'%(fam,len(CH),len(ev)))
