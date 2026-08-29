# 2단계 — 자막 굽기. 원본 타임라인 그대로이므로 SRT 시각을 손댈 필요가 없다.
# (범퍼 삽입은 3단계라 아직 시간이 안 밀렸다 — 이 순서라서 계산이 필요 없다)
#
# ★ 경로를 하드코딩하지 않는다. 사본을 떠서 쓰다가 dot-source 가 옛 회차를 가리키면
#   「옛 인서트로 합성」이 되고, 길이·용량·해상도 검증은 전부 통과한다.
param(
  [Parameter(Mandatory)][string]$PlanPs1,     # 회차 설정 ($WORK, $SRT, $FONTD ...)
  [string]$StyleJson,                          # style_gate.ps1 확정값
  [string]$EmphCsv,                            # pick_emphasis.ps1 산출
  [int]$Cq = 20
)
$ErrorActionPreference = 'Stop'
. $PlanPs1

$ASSPATH = Join-Path $WORK 'sub.ass'
if (-not $StyleJson) { $StyleJson = Join-Path $WORK 'caption_style.json' }
if (-not $EmphCsv)   { $EmphCsv   = Join-Path $WORK 'emph.csv' }
if (-not $FONTD)     { $FONTD     = $(if ($env:AUTOEDIT_FONTS) { $env:AUTOEDIT_FONTS } else { "$env:USERPROFILE\.autoedit\fonts" }) }

# 자막 네 층을 한 번에 만든다 — 나중에 한 층을 따로 얹으면 3단계를 통째로 다시 돌려야 한다
& "$PSScriptRoot\make_ass.ps1" -SrtPath $SRT -AssPath $ASSPATH `
    -EmphCsv $(if (Test-Path $EmphCsv) { $EmphCsv } else { $null }) `
    -StyleJson $(if (Test-Path $StyleJson) { $StyleJson } else { $null }) `
    -PlanPs1 $PlanPs1

if (-not (Test-Path $ASSPATH)) { throw "자막 파일이 안 만들어졌다: $ASSPATH" }

# fontsdir 의 콜론은 이스케이프하고, ass 는 작업 디렉토리 기준 상대 경로로 준다
$fd = ($FONTD -replace '\\','/') -replace ':','\\:'
Push-Location $WORK
& ffmpeg -y -loglevel error -i "$WORK\v1.mp4" `
  -vf "subtitles=sub.ass:fontsdir=$fd" `
  -c:v h264_nvenc -preset p5 -rc vbr -cq $Cq -b:v 0 -pix_fmt yuv420p `
  -g 60 -r 30 -video_track_timescale 30000 `
  -c:a copy -movflags +faststart "$WORK\v2.mp4"
Pop-Location

$d = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK\v2.mp4")
$d1 = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK\v1.mp4")
Write-Output ("2단계 완료: v2.mp4  {0}초  {1} MB  (v1 대비 {2}초)" -f `
  [math]::Round($d,2), [math]::Round((Get-Item "$WORK\v2.mp4").Length/1MB,1), [math]::Round($d-$d1,2))
Write-Output "★ 강조어가 있는 큐의 시작 시각을 직접 집어 프레임을 뽑아 볼 것 — 자간 침범과 색은 눈으로만 잡힌다"
