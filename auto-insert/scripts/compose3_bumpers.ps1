# 3단계 — 삽입 범퍼 13장. 여기서만 길이가 늘어난다.
# 범퍼는 무음이므로 v2 와 같은 규격의 무음 트랙을 붙여 줘야 이어 붙일 수 있다.
param([Parameter(Mandatory)][string]$PlanPs1)   # ★ 경로 하드코딩 금지 — 사본에서 옛 회차를 물면 옛 자산으로 합성된다
. $PlanPs1
$ErrorActionPreference = 'Stop'
$SEG = Join-Path $WORK "seg3"
New-Item -ItemType Directory -Force -Path $SEG | Out-Null
Get-ChildItem $SEG -Filter *.mp4 -ErrorAction SilentlyContinue | Remove-Item -Force

$V = @('-c:v','h264_nvenc','-preset','p5','-rc','vbr','-cq','18','-b:v','0','-pix_fmt','yuv420p',
       '-g','60','-r','30','-video_track_timescale','30000')
$A = @('-c:a','aac','-b:a','192k','-ar','48000','-ac','2')

$src = "$WORK\v2.mp4"
$total = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 $src)

$mid  = @($BMP_INS | Where-Object { $_.at -lt 99000 } | Sort-Object { $_.at })
$tail = @($BMP_INS | Where-Object { $_.at -ge 99000 })
Write-Output "중간 삽입 $($mid.Count)장 · 끝 붙임 $($tail.Count)장"

$list = New-Object System.Collections.Generic.List[string]
$cur = 0.0; $k = 0
foreach ($b in $mid) {
  $gap = [math]::Round($b.at - $cur, 3)
  if ($gap -gt 0.02) {
    $k++; $p = Join-Path $SEG ("s{0:d3}.mp4" -f $k)
    & ffmpeg -y -loglevel error -ss $cur -i $src -t $gap @V @A $p
    $list.Add("file '$p'")
  }
  $k++; $p = Join-Path $SEG ("s{0:d3}.mp4" -f $k)
  & ffmpeg -y -loglevel error -i (Join-Path $BMPD $b.file) -f lavfi -i anullsrc=r=48000:cl=stereo `
    -map 0:v:0 -map 1:a:0 -t $b.d -shortest @V @A $p
  $list.Add("file '$p'")
  $cur = $b.at
}
# 남은 본편
$k++; $p = Join-Path $SEG ("s{0:d3}.mp4" -f $k)
& ffmpeg -y -loglevel error -ss $cur -i $src @V @A $p
$list.Add("file '$p'")
# 끝에 붙이는 범퍼
foreach ($b in $tail) {
  $k++; $p = Join-Path $SEG ("s{0:d3}.mp4" -f $k)
  & ffmpeg -y -loglevel error -i (Join-Path $BMPD $b.file) -f lavfi -i anullsrc=r=48000:cl=stereo `
    -map 0:v:0 -map 1:a:0 -t $b.d -shortest @V @A $p
  $list.Add("file '$p'")
}
Write-Output "조각 $k 개"

$lf = "$WORK\concat3.txt"
[System.IO.File]::WriteAllLines($lf, $list, [System.Text.UTF8Encoding]::new($false))
$OUT = "$env:USERPROFILE\Videos\완성본"
New-Item -ItemType Directory -Force -Path $OUT | Out-Null
$final = Join-Path $OUT "완성본.mp4"
& ffmpeg -y -loglevel error -f concat -safe 0 -i $lf -c copy -movflags +faststart $final

$d = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 $final)
Write-Output ("3단계 완료: {0}  {1}  {2} MB" -f (Split-Path $final -Leaf), [TimeSpan]::FromSeconds($d).ToString('mm\:ss'), [math]::Round((Get-Item $final).Length/1MB,1))
