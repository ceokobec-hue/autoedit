# 1단계 — 인서트 47컷 + 덮어쓰기 범퍼 2장을 편집 원본 위에 얹는다.
# 인서트는 '덮어쓰기'라 길이가 변하지 않는다: 원본 조각과 인서트를 번갈아 이어 붙여
# 영상 트랙을 다시 만들고, 원본 음성을 통째로 다시 씌운다.
param([Parameter(Mandatory)][string]$PlanPs1)   # ★ 경로 하드코딩 금지 — 사본에서 옛 회차를 물면 옛 인서트로 합성된다
. $PlanPs1
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $WORK, "$WORK\seg" | Out-Null
Remove-Item "$WORK\seg\*" -Force -ErrorAction SilentlyContinue

$ENC = @('-c:v','h264_nvenc','-preset','p5','-rc','vbr','-cq','20','-b:v','0','-pix_fmt','yuv420p',
         '-g','60','-r','30','-video_track_timescale','30000','-an')

# 덮어쓸 구간 목록 (인서트 + 덮어쓰기 범퍼)을 시각순으로
$OV = @()
foreach ($c in $INS)      { $OV += @{ f = (Join-Path $INSD ($c.id + '.mp4')); ts = [double]$c.ts; d = [double]$c.d; n = $c.id } }
foreach ($b in $BMP_OVER) { $OV += @{ f = (Join-Path $BMPD $b.file);          ts = [double]$b.ts; d = [double]$b.d; n = $b.file } }
$OV = $OV | Sort-Object { $_.ts }

$total = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 $SRC)
Write-Output "원본 길이 $([math]::Round($total,2))초 · 덮어쓸 구간 $($OV.Count)개"

$list = New-Object System.Collections.Generic.List[string]
$cur = 0.0; $k = 0
foreach ($o in $OV) {
  # 1) 원본 조각 (앞 구간)
  $gap = [math]::Round($o.ts - $cur, 3)
  if ($gap -gt 0.02) {
    $k++; $p = "$WORK\seg\s{0:d3}.mp4" -f $k
    & ffmpeg -y -loglevel error -ss $cur -i $SRC -t $gap @ENC $p
    $list.Add("file '$p'")
  }
  # 2) 덮어쓰는 그림
  $k++; $p = "$WORK\seg\s{0:d3}.mp4" -f $k
  & ffmpeg -y -loglevel error -i $o.f -t $o.d @ENC $p
  $list.Add("file '$p'")
  $cur = [math]::Round($o.ts + $o.d, 3)
}
# 3) 마지막 꼬리
if ($total - $cur -gt 0.02) {
  $k++; $p = "$WORK\seg\s{0:d3}.mp4" -f $k
  & ffmpeg -y -loglevel error -ss $cur -i $SRC @ENC $p
  $list.Add("file '$p'")
}
Write-Output "조각 $k 개 생성"

$lf = "$WORK\concat1.txt"
[System.IO.File]::WriteAllLines($lf, $list, [System.Text.UTF8Encoding]::new($false))
& ffmpeg -y -loglevel error -f concat -safe 0 -i $lf -c copy "$WORK\v_only.mp4"
# 원본 음성 다시 씌우기
& ffmpeg -y -loglevel error -i "$WORK\v_only.mp4" -i $SRC -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -movflags +faststart "$WORK\v1.mp4"

$d1 = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK\v1.mp4")
Write-Output ("1단계 완료: v1.mp4  {0}초 (원본 {1}초, 차이 {2}초)" -f [math]::Round($d1,2), [math]::Round($total,2), [math]::Round($d1-$total,2))
