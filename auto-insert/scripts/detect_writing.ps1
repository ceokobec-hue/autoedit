# 자동 보호 후보 제안 — 강사가 화이트보드에 새로 쓰는 구간을 찾는다.
# 그 위에 풀프레임 인서트를 덮으면 수업이 통째로 날아가므로, 후보 목록을 먼저 뽑아
# 사용자에게 × 표시만 받는다. 초 단위로 직접 찾아 적을 필요가 없어진다.
#
# 사용: & detect_writing.ps1 -Video "...\편집 원본.mp4" -Crop "1000:900:120:200" -Thresh 0.010
#   -Crop  화이트보드 영역만 자른다 (w:h:x:y). 강사 몸이 들어가면 오검출이 는다.
#          Phase 1 콘택트시트를 보고 판서 영역 좌표를 정한다.
#   -Thresh 장면 변화 임계치. 낮출수록 후보가 많아진다.
param(
  [string]$Video,
  [string]$Crop = "",
  [double]$Thresh = 0.010,
  [double]$Merge = 6.0,     # 이 초 안에 붙은 후보는 한 구간으로 합친다
  [double]$Pad = 1.5        # 앞뒤로 남기는 여유
)
$vf = if ($Crop) { "crop=$Crop,select='gt(scene,$Thresh)'" } else { "select='gt(scene,$Thresh)'" }
$tmp = Join-Path $env:TEMP "wdetect.txt"
& ffmpeg -y -loglevel info -i $Video -vf "$vf,showinfo" -f null NUL 2> $tmp

$times = @()
foreach ($l in (Get-Content $tmp)) {
  if ($l -match 'pts_time:([0-9.]+)') { $times += [double]$Matches[1] }
}
$times = $times | Sort-Object

if ($times.Count -eq 0) { "후보 없음 — Thresh 를 낮추거나 Crop 영역을 확인할 것"; return }

# 붙은 것끼리 구간으로 묶는다
$seg = @(); $s = $times[0]; $p = $times[0]
foreach ($t in $times) {
  if ($t - $p -gt $Merge) { $seg += ,@($s, $p); $s = $t }
  $p = $t
}
$seg += ,@($s, $p)

"판서 변화 후보 $($seg.Count) 구간 — 살릴 것만 남기고 × 하세요"
""
"| 살릴 | 구간 | 길이 |"
"|---|---|---|"
foreach ($g in $seg) {
  $a = [math]::Max(0, $g[0] - $Pad); $b = $g[1] + $Pad
  "| [ ] | {0} ~ {1} | {2}초 |" -f ([TimeSpan]::FromSeconds($a).ToString('mm\:ss')), ([TimeSpan]::FromSeconds($b).ToString('mm\:ss')), [math]::Round($b-$a,1)
}
""
"※ 이 목록은 '기계가 화면 변화를 잰 것'이라 강사 몸짓도 섞여 든다. 반드시 사람이 골라낸다."
