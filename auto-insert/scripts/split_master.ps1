param([Parameter(Mandatory)][string]$Master, [Parameter(Mandatory)][string]$OutDir,
      [Parameter(Mandatory)][string]$PlanPs1)
# 4K 마스터 → QHD(2560x1440) 컷 분할. 앞 세 컷은 겹침 회피로 짧게 자른다.
# ★ 파라미터 이름을 $Src 로 두면 안 된다 — PowerShell 은 대소문자를 안 가려서
#   plan.ps1 의 $SRC(편집 원본)가 파라미터를 덮어쓴다. 그러면 촬영 원본을 잘라낸다.
$MasterPath = $Master
$OutRoot    = $OutDir
. $PlanPs1
$OutDir = $OutRoot   # plan.ps1 에 같은 이름이 있어도 파라미터가 이긴다
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$tmp = Join-Path $env:TEMP "inscut"; New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$i = 0
foreach ($c in $INS) {
  $i++
  $t = Join-Path $tmp ("c{0:d2}.mp4" -f $i)
  if (Test-Path $t) { Remove-Item $t -Force }
  & ffmpeg -y -loglevel error -ss $c.ms -i $MasterPath -t $c.d `
    -vf "scale=2560:1440:flags=lanczos" `
    -c:v h264_nvenc -preset p5 -rc vbr -cq 19 -b:v 0 -pix_fmt yuv420p -movflags +faststart -an $t
  $final = Join-Path $OutDir ($c.id + ".mp4")
  if (Test-Path $final) { Remove-Item $final -Force }
  Move-Item $t $final
}
$n = (Get-ChildItem "$OutDir\*.mp4" | Measure-Object).Count
$mb = [math]::Round((Get-ChildItem "$OutDir\*.mp4" | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Output "분할 완료: ${n}개 · ${mb} MB"
