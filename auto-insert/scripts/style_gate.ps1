# 자막 스타일 결재 게이트
#
# 색·글자체·크기를 고정값으로 정하지 않는다. 회차마다 화면과 옷 색을
# 실측해 후보를 만들고, 실제 프레임에 얹은 비교 시트를 띄워 결재받는다.
#
#   1) analyze  화면 색 실측 → 후보 생성 → 축별 비교 시트 굽기
#   2) commit   고른 번호를 받아 caption_style.json 저장
#
# 사용
#   style_gate.ps1 -Mode analyze -Video v1.mp4 -Srt sub.srt -Out D:\작업폴더
#   style_gate.ps1 -Mode commit  -Out D:\작업폴더 -Size 130 -BoxPick 1 -EmphPick 2 -FontPick 1
param(
  [ValidateSet('analyze','commit')][string]$Mode = 'analyze',
  [string]$Video,
  [string]$Srt,
  [Parameter(Mandatory)][string]$Out,
  [string]$FontDir = $(if ($env:AUTOEDIT_FONTS) { $env:AUTOEDIT_FONTS } else { "$env:USERPROFILE\.autoedit\fonts" }),
  [double]$Size = 130,
  [int]$BoxPick = 1, [int]$EmphPick = 1, [int]$FontPick = 1, [int]$AlphaPct = 80
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\srt_tools.ps1"
$WORK = Join-Path $Out '_style'
New-Item -ItemType Directory -Force -Path $WORK | Out-Null
# ★ 경로 변수와 데이터 변수의 이름이 대소문자만 다르면 안 된다.
#   PowerShell 은 변수명 대소문자를 안 가려서 $CAND 와 $cand 가 같은 변수다.
#   실제로 $cand = [ordered]@{...} 가 경로를 덮어써 파일이 안 써졌다.
$CandPath  = Join-Path $WORK 'candidates.json'
$FinalPath = Join-Path $Out 'caption_style.json'

# ── 색 유틸 ───────────────────────────────────────────────────
function ToBGR([int]$r,[int]$g,[int]$b) { '&H{0:X2}{1:X2}{2:X2}' -f $b,$g,$r }
function ToHex([int]$r,[int]$g,[int]$b) { '#{0:X2}{1:X2}{2:X2}' -f $r,$g,$b }
function Lin([double]$v) { $v = $v/255.0; if ($v -le 0.03928) { $v/12.92 } else { [math]::Pow(($v+0.055)/1.055, 2.4) } }
function Lum($c) { 0.2126*(Lin $c[0]) + 0.7152*(Lin $c[1]) + 0.0722*(Lin $c[2]) }
# 흰 글씨 대비. 박스가 반투명이라 아래 화면과 섞인 색으로 계산해야 실제와 맞는다.
function ContrastOnWhite($box, $under, [double]$a) {
  $m = @(0,0,0)
  for ($i=0; $i -lt 3; $i++) { $m[$i] = [int]([math]::Round($box[$i]*$a + $under[$i]*(1-$a))) }
  $l = Lum $m
  return [math]::Round((1.0 + 0.05) / ($l + 0.05), 2)
}
function Shade($c, [double]$k) { @([int][math]::Max(0,[math]::Min(255,$c[0]*$k)), [int][math]::Max(0,[math]::Min(255,$c[1]*$k)), [int][math]::Max(0,[math]::Min(255,$c[2]*$k))) }

if ($Mode -eq 'analyze') {
  if (-not $Video) { throw "-Video 가 필요하다" }

  # ── 프레임 샘플 ─────────────────────────────────────────────
  $dur = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 $Video)
  $shots = @(); for ($i=1; $i -le 12; $i++) { $shots += [math]::Round($dur * $i / 13.0, 2) }
  $k=0; foreach ($t in $shots) { $k++; & ffmpeg -y -loglevel error -ss $t -i $Video -frames:v 1 (Join-Path $WORK ("f{0:d2}.png" -f $k)) }

  # ── 영역별 대표색 (중앙값 — 평균은 조명 튐에 흔들린다) ──────
  Add-Type -AssemblyName System.Drawing
  $wear = @(); $wall = @(); $all = @()
  foreach ($f in (Get-ChildItem $WORK -Filter 'f??.png')) {
    $bmp = [System.Drawing.Bitmap]::FromFile($f.FullName)
    try {
      $W = $bmp.Width; $H = $bmp.Height
      for ($x = [int]($W*0.36); $x -lt [int]($W*0.64); $x += [int]($W*0.03)) {
        for ($y = [int]($H*0.62); $y -lt [int]($H*0.92); $y += [int]($H*0.04)) {
          $p = $bmp.GetPixel($x,$y); $wear += ,@($p.R,$p.G,$p.B); $all += ,@($p.R,$p.G,$p.B)
        }
      }
      foreach ($xr in @(@(0.04,0.24), @(0.76,0.96))) {
        for ($x = [int]($W*$xr[0]); $x -lt [int]($W*$xr[1]); $x += [int]($W*0.03)) {
          for ($y = [int]($H*0.10); $y -lt [int]($H*0.38); $y += [int]($H*0.05)) {
            $p = $bmp.GetPixel($x,$y); $wall += ,@($p.R,$p.G,$p.B); $all += ,@($p.R,$p.G,$p.B)
          }
        }
      }
    } finally { $bmp.Dispose() }
  }
  function Median($rows) {
    $o=@(0,0,0); for ($i=0;$i -lt 3;$i++) { $s=@($rows | ForEach-Object { $_[$i] } | Sort-Object); $o[$i]=[int]$s[[int]($s.Count/2)] }; $o
  }
  $cWear = Median $wear; $cWall = Median $wall; $cAll = Median $all
  $bright = (Lum $cAll) -gt 0.35

  # ── 후보 ────────────────────────────────────────────────────
  $a = $AlphaPct / 100.0
  $boxes = @(
    @{ name='의상 톤온톤'; rgb=(Shade $cWear 0.62) },
    @{ name='시리즈 네이비'; rgb=@(27,36,56) },
    @{ name='중립 딥차콜'; rgb=@(20,16,14) }
  )
  foreach ($b in $boxes) {
    $b.hex = ToHex $b.rgb[0] $b.rgb[1] $b.rgb[2]
    $b.bgr = ToBGR $b.rgb[0] $b.rgb[1] $b.rgb[2]
    # 밝은 벽 위 / 어두운 의상 위 두 경우의 대비를 모두 본다. 낮은 쪽이 실제 최악값이다.
    $b.contrast = [math]::Min((ContrastOnWhite $b.rgb $cWall $a), (ContrastOnWhite $b.rgb $cWear $a))
    $b.ok = $b.contrast -ge 4.5
  }
  $emphs = @(
    @{ name='밝은 앰버'; rgb=@(255,194,75) },
    @{ name='시리즈 오렌지'; rgb=@(217,138,31) },
    @{ name='라이트 시안'; rgb=@(120,214,255) }
  )
  foreach ($e in $emphs) { $e.hex = ToHex $e.rgb[0] $e.rgb[1] $e.rgb[2]; $e.bgr = ToBGR $e.rgb[0] $e.rgb[1] $e.rgb[2] }

  # 글자체 — 실제로 열리는 파일만. libass 는 woff2 를 못 읽고, 깨진 파일은 조용히 폴백된다.
  # ★ ASS 의 Fontname 은 파일명이 아니라 「패밀리 이름」이다. 파일명을 넣으면 libass 가
  #   폰트를 못 찾아 조용히 기본 폰트로 폴백한다 — 에러도 경고도 없다.
  $fonts = @()
  foreach ($f in (Get-ChildItem $FontDir -Include *.otf,*.ttf -File -Recurse)) {
    if ($f.Length -lt 50000) { Write-Output "  ⚠ 건너뜀(깨진 파일로 보임): $($f.Name) $($f.Length)B"; continue }
    try {
      $g = Get-CaptionFont $f.FullName
      $fam = @($g.FamilyNames.Values)[0]
      if (-not $fam) { $fam = $f.BaseName }
      $fonts += @{ name=$fam; label=$f.BaseName; file=$f.FullName; weight=$g.Weight.ToOpenTypeWeight() }
    } catch { }
  }
  # 같은 패밀리는 하나로 묶는다 — ASS Fontname 이 같으면 libass 가 Bold 플래그로 고르므로
  # Bold/Black 을 따로 후보로 내밀어도 실제 화면에서는 구별되지 않는다.
  # 글자체를 진짜로 바꾸려면 다른 패밀리의 OTF/TTF 를 FontDir 에 넣어야 한다.
  $fonts = @($fonts | Group-Object { $_.name } | ForEach-Object {
    $pick = @($_.Group | Sort-Object { -$_.weight })[0]
    if ($_.Count -gt 1) { $pick.label = "$($pick.label) (같은 패밀리 $($_.Count)종 중 가장 굵은 것)" }
    $pick
  })

  # ★ 글리프 커버리지 — 이 회차 자막에 실제로 쓰이는 글자를 그 폰트가 다 갖고 있는지 본다.
  #   한글은 멀쩡한데 「—」나 「‘’」 같은 문장부호가 빠진 폰트가 흔하다. 빠지면 화면에 □ 가 뜬다.
  if ($Srt -and (Test-Path $Srt)) {
    $cuesForCheck = @(Read-Srt $Srt)
    $usedChars = @((($cuesForCheck.x -join '')).ToCharArray() | Sort-Object -Unique)
    foreach ($f in $fonts) {
      $gg = Get-CaptionFont $f.file
      $miss = @($usedChars | Where-Object { -not $gg.CharacterToGlyphMap.ContainsKey([int][char]$_) })
      $f.missing = $miss.Count
      $f.missingChars = ($miss -join '')
    }
  } else {
    foreach ($f in $fonts) { $f.missing = -1; $f.missingChars = '' }
  }
  # 글자가 다 있는 폰트를 앞으로 — 누락이 있는 폰트는 골라도 □ 가 뜬다
  $fonts = @($fonts | Sort-Object @{E={ if ($_.missing -lt 0) { 0 } else { $_.missing } }}, @{E={ -$_.weight }})

  $sizes = @(120, 130, 140)
  $bundle = [ordered]@{
    measured = @{ wear = (ToHex $cWear[0] $cWear[1] $cWear[2]); wall = (ToHex $cWall[0] $cWall[1] $cWall[2]); bright = $bright }
    boxes = $boxes; emphs = $emphs; fonts = $fonts; sizes = $sizes; alphaPct = $AlphaPct
  }
  $bundle | ConvertTo-Json -Depth 6 | Set-Content $CandPath -Encoding UTF8
  if (-not (Test-Path $CandPath)) { throw "후보 파일을 못 썼다: $CandPath" }

  Write-Output "실측 — 의상 $(ToHex $cWear[0] $cWear[1] $cWear[2]) · 배경 $(ToHex $cWall[0] $cWall[1] $cWall[2]) · 화면 $(if($bright){'밝음'}else{'어두움'})"
  Write-Output "배경 박스 후보"
  $i=0; foreach ($b in $boxes) { $i++; "  {0}) {1,-12} {2}  대비 {3}:1 {4}" -f $i, $b.name, $b.hex, $b.contrast, $(if($b.ok){''}else{'← 4.5 미만, 권하지 않음'}) }
  Write-Output "강조 글자색 후보"
  $i=0; foreach ($e in $emphs) { $i++; "  {0}) {1,-12} {2}" -f $i, $e.name, $e.hex }
  Write-Output "글자체 후보"
  $i=0; foreach ($f in $fonts) { $i++
    $warn = if ($f.missing -gt 0) { "  ⚠ 이 회차 자막 글자 $($f.missing)종 누락 [$($f.missingChars)] — 화면에 □ 로 뜬다" } elseif ($f.missing -eq 0) { '  ✅ 커버리지 이상 없음' } else { '' }
    "  {0}) {1} ({2}, weight {3}){4}" -f $i, $f.name, $f.label, $f.weight, $warn }
  Write-Output "크기 후보: $($sizes -join ' / ') px"

  # ── 비교 시트 ───────────────────────────────────────────────
  # 대표 프레임 2장(밝은 곳·어두운 곳)에 후보를 실제로 얹어 굽는다. 숫자로는 못 고른다.
  $samples = @((Join-Path $WORK 'f04.png'), (Join-Path $WORK 'f09.png')) | Where-Object { Test-Path $_ }
  $demo = '이 문장으로 크기와 배경을 봅니다'
  $demoEmph = '배경'

  function Bake([string]$img, [string]$outPng, [double]$sz, $box, $emph, $font, [string]$label) {
    $g = Get-CaptionFont $font.file
    $lineH = $sz * $g.Height
    $txt = $demo.Replace($demoEmph, "{\c$($emph.bgr)&}$demoEmph{\c}")
    $lw = Get-TextWidth $demo $g $sz
    $top = 1440 - 96 - $lineH
    $ass = Join-Path $WORK 'tmp.ass'
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("[Script Info]`nScriptType: v4.00+`nWrapStyle: 2`nScaledBorderAndShadow: yes`nPlayResX: 2560`nPlayResY: 1440`n")
    [void]$sb.AppendLine('[V4+ Styles]')
    [void]$sb.AppendLine('Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding')
    [void]$sb.AppendLine("Style: Base,$($font.name),$sz,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,8,0,2,140,140,96,1")
    [void]$sb.AppendLine("Style: HL,$($font.name),1,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1")
    [void]$sb.AppendLine("Style: Tag,$($font.name),46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1")
    [void]$sb.AppendLine("`n[Events]`nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    $bx = [math]::Round(1280 - $lw/2 - 28,1); $by = [math]::Round($top + 10,1)
    $bw = [math]::Round($lw + 56,1); $bh = [math]::Round($lineH - 20,1)
    $al = '&H{0:X2}' -f [int](255 * (1 - $AlphaPct/100.0))
    [void]$sb.AppendLine("Dialogue: 0,0:00:00.00,0:00:10.00,HL,,0,0,0,,{\pos($bx,$by)\p1\1c$($box.bgr)&\alpha$al&\bord0\shad0}m 0 0 l $bw 0 l $bw $bh l 0 $bh{\p0}")
    [void]$sb.AppendLine("Dialogue: 1,0:00:00.00,0:00:10.00,Base,,0,0,0,,$txt")
    [void]$sb.AppendLine("Dialogue: 2,0:00:00.00,0:00:10.00,Tag,,0,0,0,,{\pos(60,54)}$label")
    [System.IO.File]::WriteAllText($ass, $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
    Push-Location $WORK
    & ffmpeg -y -loglevel error -i $img -vf "subtitles=tmp.ass:fontsdir=$($FontDir -replace '\\','/' -replace ':','\\:')" -frames:v 1 $outPng
    Pop-Location
  }

  $sheets = @()
  # 크기 축
  $j=0; $imgs=@()
  foreach ($sz in $sizes) { $j++; $o = Join-Path $WORK ("sz{0}.png" -f $j); Bake $samples[0] $o $sz $boxes[0] $emphs[0] $fonts[0] ("크기 $j) $sz px"); $imgs += $o }
  $s1 = Join-Path $WORK 'sheet_size.png'
  & ffmpeg -y -loglevel error -i $imgs[0] -i $imgs[1] -i $imgs[2] -filter_complex "[0:v]scale=1100:-1[a];[1:v]scale=1100:-1[b];[2:v]scale=1100:-1[c];[a][b][c]vstack=inputs=3" -frames:v 1 $s1
  $sheets += $s1
  # 배경 축
  $j=0; $imgs=@()
  foreach ($b in $boxes) { $j++; $o = Join-Path $WORK ("bx{0}.png" -f $j); Bake $samples[0] $o $Size $b $emphs[0] $fonts[0] ("배경 $j) $($b.name) $($b.hex) 대비 $($b.contrast):1"); $imgs += $o }
  $s2 = Join-Path $WORK 'sheet_box.png'
  & ffmpeg -y -loglevel error -i $imgs[0] -i $imgs[1] -i $imgs[2] -filter_complex "[0:v]scale=1100:-1[a];[1:v]scale=1100:-1[b];[2:v]scale=1100:-1[c];[a][b][c]vstack=inputs=3" -frames:v 1 $s2
  $sheets += $s2
  # 강조 축
  $j=0; $imgs=@()
  foreach ($e in $emphs) { $j++; $o = Join-Path $WORK ("em{0}.png" -f $j); Bake $samples[[math]::Min(1,$samples.Count-1)] $o $Size $boxes[0] $e $fonts[0] ("강조 $j) $($e.name) $($e.hex)"); $imgs += $o }
  $s3 = Join-Path $WORK 'sheet_emph.png'
  & ffmpeg -y -loglevel error -i $imgs[0] -i $imgs[1] -i $imgs[2] -filter_complex "[0:v]scale=1100:-1[a];[1:v]scale=1100:-1[b];[2:v]scale=1100:-1[c];[a][b][c]vstack=inputs=3" -frames:v 1 $s3
  $sheets += $s3
  # 글자체 축
  if ($fonts.Count -ge 2) {
    $j=0; $imgs=@()
    foreach ($f in ($fonts | Select-Object -First 4)) { $j++; $o = Join-Path $WORK ("ft{0}.png" -f $j)
      $tag = if ($f.missing -gt 0) { " ⚠글자 $($f.missing)종 누락" } else { '' }
      Bake $samples[0] $o $Size $boxes[0] $emphs[0] $f ("글자체 $j) $($f.name)$tag"); $imgs += $o }
    $s4 = Join-Path $WORK 'sheet_font.png'
    $fc = ($imgs | ForEach-Object -Begin {$n=0} -Process { "[$n`:v]scale=1100:-1[v$n]"; $n++ }) -join ';'
    $st = (0..($imgs.Count-1) | ForEach-Object { "[v$_]" }) -join ''
    $ins = @(); foreach ($im in $imgs) { $ins += @('-i', $im) }
    # ★ "$st`vstack" 으로 쓰면 안 된다 — PowerShell 이 `v 를 수직 탭으로 바꿔 필터 이름이 깨진다.
    $fg = "$fc;" + $st + "vstack=inputs=$($imgs.Count)"
    & ffmpeg -y -loglevel error @ins -filter_complex $fg -frames:v 1 $s4
    $sheets += $s4
  }

  Write-Output ""
  Write-Output "비교 시트 (사람이 보고 고를 것)"
  $sheets | ForEach-Object { "  $_" }
  Write-Output "고른 뒤: style_gate.ps1 -Mode commit -Out `"$Out`" -Size <px> -BoxPick <n> -EmphPick <n> -FontPick <n>"
}
else {
  if (-not (Test-Path $CandPath)) { throw "후보 파일이 없다. -Mode analyze 를 먼저 돌릴 것: $CandPath" }
  $c = Get-Content $CandPath -Raw -Encoding UTF8 | ConvertFrom-Json
  $box = $c.boxes[$BoxPick-1]; $emph = $c.emphs[$EmphPick-1]; $font = $c.fonts[$FontPick-1]
  $al = '&H{0:X2}' -f [int](255 * (1 - $AlphaPct/100.0))
  $style = [ordered]@{
    fontFile = $font.file; fontName = $font.name; size = $Size
    marginV = 96; marginLR = 140; outline = 8
    boxBGR = $box.bgr; boxAlpha = $al; boxPadX = 28; boxTrim = 10
    emphBGR = $emph.bgr
    bandFont = 58; bandH = 82; bandAccentBGR = '&H2E64D9'
    bubbleFont = 84; bubbleY = 178
    bands = @(); bubbles = @()
    _decided = @{ box = $box.name; boxHex = $box.hex; emph = $emph.name; emphHex = $emph.hex; contrast = $box.contrast; alphaPct = $AlphaPct }
  }
  $style | ConvertTo-Json -Depth 6 | Set-Content $FinalPath -Encoding UTF8
  "확정: $($font.name) $Size px · 배경 $($box.name) $($box.hex) $AlphaPct% (대비 $($box.contrast):1) · 강조 $($emph.name) $($emph.hex)"
  "저장: $FinalPath   ← make_ass.ps1 -StyleJson 으로 넘긴다"
}
