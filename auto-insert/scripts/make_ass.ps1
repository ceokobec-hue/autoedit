# SRT → ASS. 자막 한 파일에 네 층을 함께 굽는다.
#
#   Layer 0  배경 박스   줄마다 글자 폭에 맞춘 사각형
#   Layer 1  키워드 띠   시리즈 진행 위치 (인서트 구간은 자동으로 숨김)
#   Layer 2  자막 글자   강조어는 인라인 색 태그로
#   Layer 3·4 말풍선     회차당 2~3회
#
# ★ 강조는 「형광펜 띠」가 아니라 「글자색」이다. 띠는 좌표를 계산해야 해서
#   폭이 몇 px만 어긋나도 옆 글자를 침범했다(3편 실측). 색은 계산할 좌표가 없다.
#
# ★ 줄 나눔은 우리가 \N 으로 확정한다. libass 자동 줄바꿈에 맡기면
#   배경 박스를 어디에 그릴지 알 수 없다.
param(
  [Parameter(Mandatory)][string]$SrtPath,
  [Parameter(Mandatory)][string]$AssPath,
  [string]$EmphCsv,                                   # pick_emphasis.ps1 산출 (없으면 강조 없음)
  [string]$StyleJson,                                 # style_gate.ps1 이 결재받아 저장한 확정값
  [string]$PlanPs1,                                   # 인서트 구간 — 키워드 띠를 숨길 자리
  [switch]$NoMerge                                    # 큐 병합을 끄고 원본 그대로
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\srt_tools.ps1"

# ── 스타일 ────────────────────────────────────────────────────
# 기본값은 「무난한 출발점」일 뿐이다. 회차마다 style_gate.ps1 로 화면을 분석해
# 후보를 띄우고 결재받은 값을 쓴다 — 색·크기·글자체를 고정하지 않는다.
$S = [ordered]@{
  fontFile = Join-Path $(if ($env:AUTOEDIT_FONTS) { $env:AUTOEDIT_FONTS } else { "$env:USERPROFILE\.autoedit\fonts" }) 'Pretendard-Bold.otf'
  fontName = 'Pretendard'
  size     = 130
  marginV  = 96
  marginLR = 140
  outline  = 8
  boxBGR   = '&H1A1E2A'      # #2A1E1A 를 BGR 로 뒤집은 값
  boxAlpha = '&H33'          # 80% 불투명
  boxPadX  = 28
  boxTrim  = 10
  emphBGR  = '&H4BC2FF'      # #FFC24B 앰버
  bandFont = 58
  bandH    = 82
  bandAccentBGR = '&H2E64D9'
  bubbleFont = 84
  bubbleY    = 178
  bands   = @()              # @(@{s=..;e=..;t='① 결과물'}, ...)
  bubbles = @()              # @(@{at=..;d=..;t='멍청한 게 아니다'}, ...)
}
if ($StyleJson -and (Test-Path $StyleJson)) {
  $j = Get-Content $StyleJson -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($k in @($S.Keys)) { if ($null -ne $j.$k) { $S[$k] = $j.$k } }
}

$GT    = Get-CaptionFont $S.fontFile
$MAXW  = 2560 - $S.marginLR * 2
$LINEH = $S.size * $GT.Height
$CX    = 1280

function AT([double]$sec) {
  $t = [TimeSpan]::FromSeconds($sec)
  "{0}:{1:d2}:{2:d2}.{3:d2}" -f [int]$t.TotalHours, $t.Minutes, $t.Seconds, [int][math]::Floor($t.Milliseconds/10)
}
function Draw([double]$x, [double]$y, [double]$w, [double]$h, [string]$col, [string]$alpha) {
  $x=[math]::Round($x,1); $y=[math]::Round($y,1); $w=[math]::Round($w,1); $h=[math]::Round($h,1)
  "{\pos($x,$y)\p1\1c$col&\alpha$alpha&\bord0\shad0}m 0 0 l $w 0 l $w $h l 0 $h{\p0}"
}

# ── 큐 읽기 · 병합 ────────────────────────────────────────────
$cues = @(Read-Srt $SrtPath)
$nMerged = 0
if (-not $NoMerge) {
  $m = Merge-BrokenWords -Cues $cues -Font $GT -FontSize $S.size -MaxW $MAXW
  $cues = $m.Cues; $nMerged = $m.Merged
  if ($nMerged -gt 0) { Write-Output "큐 병합 $nMerged 건 (단어가 두 큐로 갈라진 자리)"; $m.Log | ForEach-Object { Write-Output $_ } }
}

# ── 강조어 표 ─────────────────────────────────────────────────
# 큐 번호는 병합으로 다시 매겨지므로 번호가 아니라 「문장 + 단어」로 물린다.
$emph = @{}
if ($EmphCsv -and (Test-Path $EmphCsv)) {
  foreach ($r in (Import-Csv $EmphCsv -Encoding UTF8)) {
    $key = ([string]$r.line).Trim()
    if ($key -and -not $emph.ContainsKey($key)) { $emph[$key] = [string]$r.word }
  }
}
function Get-EmphWord([string]$cueText) {
  if ($emph.ContainsKey($cueText)) { return $emph[$cueText] }
  foreach ($k in $emph.Keys) { if ($cueText.Contains($k)) { return $emph[$k] } }   # 병합된 큐
  return $null
}

# ── ASS 머리 ──────────────────────────────────────────────────
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('[Script Info]')
[void]$sb.AppendLine('ScriptType: v4.00+')
[void]$sb.AppendLine('WrapStyle: 2')
[void]$sb.AppendLine('ScaledBorderAndShadow: yes')
[void]$sb.AppendLine('PlayResX: 2560')
[void]$sb.AppendLine('PlayResY: 1440')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('[V4+ Styles]')
[void]$sb.AppendLine('Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding')
[void]$sb.AppendLine("Style: Base,$($S.fontName),$($S.size),&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,$($S.outline),0,2,$($S.marginLR),$($S.marginLR),$($S.marginV),1")
[void]$sb.AppendLine("Style: HL,$($S.fontName),1,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1")
[void]$sb.AppendLine("Style: Band,$($S.fontName),$($S.bandFont),&H00F0E6D2,&H00F0E6D2,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,0,0,7,0,0,0,1")
[void]$sb.AppendLine("Style: Bub,$($S.fontName),$($S.bubbleFont),&H00121A1E,&H00121A1E,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1")
[void]$sb.AppendLine('')
[void]$sb.AppendLine('[Events]')
[void]$sb.AppendLine('Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text')

# ── 자막 본체 ─────────────────────────────────────────────────
$n2 = 0; $nEmph = 0
foreach ($c in $cues) {
  $lines = @(Split-CaptionLine $c.x $GT $S.size $MAXW)
  if ($lines.Count -gt 1) { $n2++ }
  $blockTop = 1440 - $S.marginV - $lines.Count * $LINEH
  $t0 = AT $c.s; $t1 = AT $c.e

  # Layer 0 — 배경 박스. 블록의 맨 위·아래만 깎아야 두 줄이 틈 없이 붙는다.
  for ($i = 0; $i -lt $lines.Count; $i++) {
    $lw = Get-TextWidth $lines[$i] $GT $S.size
    $cutT = $(if ($i -eq 0) { $S.boxTrim } else { 0 })
    $cutB = $(if ($i -eq $lines.Count - 1) { $S.boxTrim } else { 0 })
    [void]$sb.AppendLine("Dialogue: 0,$t0,$t1,HL,,0,0,0,,$(Draw ($CX - $lw/2 - $S.boxPadX) ($blockTop + $i*$LINEH + $cutT) ($lw + $S.boxPadX*2) ($LINEH - $cutT - $cutB) $S.boxBGR $S.boxAlpha)")
  }

  # Layer 2 — 글자. 강조어는 색 태그로 감싼다(\c 단독은 스타일 기본색 복귀).
  $word = Get-EmphWord $c.x
  $disp = @()
  $done = $false
  foreach ($ln in $lines) {
    if ($word -and -not $done -and $ln.Contains($word)) {
      $disp += $ln.Replace($word, "{\c$($S.emphBGR)&}$word{\c}")
      $done = $true; $nEmph++
    } else { $disp += $ln }
  }
  [void]$sb.AppendLine("Dialogue: 2,$t0,$t1,Base,,0,0,0,,$($disp -join '\N')")
}

# ── 키워드 띠 ─────────────────────────────────────────────────
# 인서트가 뜬 동안은 숨긴다 — 인서트에 같은 역할의 kicker 라벨이 이미 있고,
# 겹치면 카드를 더 위로 올려야 해서 인서트 디자인이 눌린다.
$blocks = @()
if ($PlanPs1 -and (Test-Path $PlanPs1)) {
  . $PlanPs1
  foreach ($i in $INS)      { $blocks += @{s=[double]$i.ts; e=[double]$i.ts + [double]$i.d} }
  foreach ($b in $BMP_OVER) { $blocks += @{s=[double]$b.ts; e=[double]$b.ts + [double]$b.d} }
}
function Cut-Out([double]$s, [double]$e, $bl) {
  $segs = @(@{s=$s; e=$e})
  foreach ($b in $bl) {
    $next = @()
    foreach ($g in $segs) {
      if ($b.e -le $g.s -or $b.s -ge $g.e) { $next += $g; continue }
      if ($b.s -gt $g.s) { $next += @{s=$g.s; e=$b.s} }
      if ($b.e -lt $g.e) { $next += @{s=$b.e; e=$g.e} }
    }
    $segs = $next
  }
  @($segs | Where-Object { ($_.e - $_.s) -ge 1.2 })   # 1.2초를 못 채우는 조각은 깜빡여 보인다
}

# 띠 세로 위치 — 두 줄 자막 기준으로 고정한다. 한 줄일 때 따라 내려오면 산만하다.
$bandY = 1440 - $S.marginV - 2*$LINEH - 20 - $S.bandH
$nBand = 0
foreach ($bd in $S.bands) {
  foreach ($g in (Cut-Out ([double]$bd.s) ([double]$bd.e) $blocks)) {
    $tw = (Get-TextWidth ([string]$bd.t) $GT $S.bandFont)
    $g0 = AT $g.s; $g1 = AT $g.e
    [void]$sb.AppendLine("Dialogue: 1,$g0,$g1,HL,,0,0,0,,$(Draw $S.marginLR $bandY ($tw + 56) $S.bandH $S.boxBGR $S.boxAlpha)")
    [void]$sb.AppendLine("Dialogue: 1,$g0,$g1,HL,,0,0,0,,$(Draw $S.marginLR $bandY 13 $S.bandH $S.bandAccentBGR '&H10')")
    $ty = $bandY + ($S.bandH - $S.bandFont * $GT.Height) / 2
    [void]$sb.AppendLine("Dialogue: 1,$g0,$g1,Band,,0,0,0,,{\pos($($S.marginLR + 36),$([math]::Round($ty,1)))}$($bd.t)")
    $nBand++
  }
}

# ── 말풍선 ────────────────────────────────────────────────────
$nBub = 0
foreach ($b in $S.bubbles) {
  $tw = Get-TextWidth ([string]$b.t) $GT $S.bubbleFont
  $W  = [math]::Round($tw + 88, 1)
  $H  = [math]::Round($S.bubbleFont * $GT.Height + 48, 1)
  $x  = [math]::Round(2560 - $S.marginLR - $W, 1)
  $b0 = AT ([double]$b.at); $b1 = AT ([double]$b.at + [double]$b.d)
  $tail = "l 96 $H l 52 $([math]::Round($H + 34,1)) l 44 $H l 0 $H"
  [void]$sb.AppendLine("Dialogue: 3,$b0,$b1,HL,,0,0,0,,{\pos($x,$($S.bubbleY))\fad(160,200)\frz-2\p1\1c&HD2E6F0&\alpha&H10&\bord0\shad0}m 0 0 l $W 0 l $W $H $tail{\p0}")
  [void]$sb.AppendLine("Dialogue: 4,$b0,$b1,Bub,,0,0,0,,{\pos($([math]::Round($x + 44,1)),$([math]::Round($S.bubbleY + 24,1)))\fad(160,200)\frz-2}$($b.t)")
  $nBub++
}

[System.IO.File]::WriteAllText($AssPath, $sb.ToString(), [System.Text.UTF8Encoding]::new($false))

# ★ 처리 건수를 반드시 찍는다. 배열이 조용히 망가지면 여기 0 이 뜬다 — 그것 말고는 알 길이 없다.
"자막 {0}개 · 두 줄 {1}개({2}%) · 강조 {3}개 · 키워드 띠 {4}조각 · 말풍선 {5}개" -f `
  $cues.Count, $n2, [math]::Round(100*$n2/[math]::Max($cues.Count,1),1), $nEmph, $nBand, $nBub
"글꼴 {0} {1}px · 줄높이 {2} · 한 줄 최대 {3}px · ASS {4}" -f `
  (Split-Path $S.fontFile -Leaf), $S.size, [math]::Round($LINEH,1), $MAXW, $AssPath
