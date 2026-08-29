# 콘택트시트 — 이 파이프라인에서 가장 값어치 있는 검증.
# 길이·해상도·개수 검증은 "엉뚱한 그림이 들어갔다"를 절대 못 잡는다. 눈으로 봐야 잡힌다.
#
# 사용:
#   & contact_sheet.ps1 -Video v1.mp4 -Times 4.6,33,94,640 -Out .\chk
#   & contact_sheet.ps1 -Dir .\인서트 -Out .\chk                     # 폴더의 각 클립에서 1장씩
param(
  [string]$Video, [double[]]$Times, [string]$Dir,
  [string]$Out = "$env:TEMP\csheet", [int]$Cols = 4, [int]$W = 440, [double]$At = 2.5
)
New-Item -ItemType Directory -Force -Path $Out | Out-Null
Get-ChildItem $Out -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force
$h = [int]($W * 9 / 16)
$i = 0

if ($Dir) {
  # 폴더 모드 — 클립마다 $At 초 지점 1장 (움직임이 끝나고 멈춘 상태)
  foreach ($f in (Get-ChildItem "$Dir\*.mp4" | Sort-Object Name)) {
    $i++
    & ffmpeg -y -loglevel error -ss $At -i $f.FullName -frames:v 1 -vf "scale=${W}:${h}" (Join-Path $Out ("{0:d3}.png" -f $i))
  }
  # 용량 이상 감지 — 정지 그래픽이 실사급이면 잘못된 소스를 자른 것이다
  $mb = [math]::Round((Get-ChildItem "$Dir\*.mp4" | Measure-Object Length -Sum).Sum / 1MB, 1)
  $sec = 0.0
  foreach ($f in (Get-ChildItem "$Dir\*.mp4")) { $sec += [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 $f.FullName) }
  $mbpm = if ($sec -gt 0) { [math]::Round($mb / ($sec/60), 1) } else { 0 }
  "클립 $i 개 · 합계 ${mb} MB · ${mbpm} MB/분"
  if ($mbpm -gt 25) { "⚠ 분당 ${mbpm} MB — 정지 그래픽치고 너무 크다. 실사 소스를 자른 게 아닌지 확인할 것 (정상 대략 4~8 MB/분)" }
} else {
  foreach ($t in $Times) {
    $i++
    & ffmpeg -y -loglevel error -ss $t -i $Video -frames:v 1 -vf "scale=${W}:${h}" (Join-Path $Out ("{0:d3}.png" -f $i))
  }
}

$rows = [math]::Ceiling($i / $Cols)
$sheet = Join-Path $Out "sheet.png"
& ffmpeg -y -loglevel error -i (Join-Path $Out "%03d.png") `
  -filter_complex "tile=${Cols}x${rows}:margin=6:padding=6:color=0x555555" -frames:v 1 $sheet
"시트: $sheet  ($i 장 · ${Cols}x${rows})"
