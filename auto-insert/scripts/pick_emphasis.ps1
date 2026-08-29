# 강조 후보 뽑기 — 「무엇을 강조할지」만 정한다. 어떻게 보일지는 make_ass.ps1 이 색으로 처리한다.
# 규칙: 한 큐에 하나만 · 최소 간격을 둬서 몰리지 않게
#
# ★ 예전에는 「순수 한글만 · 30자 넘는 큐 제외」 제한이 있었다. 형광펜 띠를 그리려면
#   글자 폭을 계산해야 했고, 라틴·숫자가 섞이거나 두 줄로 갈리면 좌표가 어긋났기 때문이다.
#   강조가 색으로 바뀌면서 계산할 좌표가 없어졌으므로 두 제한 모두 풀었다.
param([string]$SrtPath, [string]$OutCsv, [int]$MinGapCues = 9)

. "$PSScriptRoot\srt_tools.ps1"
$cues = Read-Srt $SrtPath

# ⚠️ 여기는 «내 회차의 개념어»로 채운다. 앞에 올수록 우선.
#    자막에서 이 낱말이 나오는 대목을 강조 자막 후보로 뽑는다.
$KEY = @(
 '핵심','기준','순서','원칙','차이','이유','방법','주의','결론','예시'
)

$picked = @(); $lastN = -999
foreach ($c in $cues) {
  if ($c.n - $lastN -lt $MinGapCues) { continue }
  foreach ($k in $KEY) {
    $i = $c.x.IndexOf($k)
    if ($i -lt 0) { continue }
    # 어절 경계까지 좌우로 넓힌다. 왼쪽을 안 넓히면 「집주인이」가 「주인이」로 잘린다.
    $st = $i
    while ($st -gt 0 -and $c.x[$st-1] -match '[가-힣]' -and ($i - $st) -lt 3) { $st-- }
    $end = $i + $k.Length
    while ($end -lt $c.x.Length -and $c.x[$end] -match '[가-힣]' -and ($end - $st) -lt 8) { $end++ }
    $w = $c.x.Substring($st, $end - $st).Trim()
    if ($w.Length -lt 2) { break }
    $picked += [pscustomobject]@{ n=$c.n; s=$c.s; e=$c.e; line=$c.x; word=$w; key=$k }
    $lastN = $c.n
    break
  }
}
"후보 $($picked.Count)개 (큐 $($cues.Count)개 · 평균 $([math]::Round($cues.Count/[math]::Max($picked.Count,1),1))큐에 한 번)"
$picked | Export-Csv -Path $OutCsv -Encoding UTF8 -NoTypeInformation
Write-Output "CSV: $OutCsv"
