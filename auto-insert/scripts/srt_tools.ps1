# SRT 도구 — 파싱 · 블록 스캔 · 앵커 탐색 · 챕터 산출
# 사용:
#   . srt_tools.ps1
#   $cues = Read-Srt $path
#   Show-Blocks $cues 20            # 20초 블록으로 서사 훑기
#   Find-Anchor $cues '출발할게요'   # 정확한 큐 시작 시각
#   Export-Chapters $cues $marks

function Read-Srt([string]$Path) {
  $raw = Get-Content $Path -Encoding UTF8
  $out = @(); $i = 0
  while ($i -lt $raw.Count) {
    if ($raw[$i] -match '^\s*\d+\s*$' -and $i+1 -lt $raw.Count -and $raw[$i+1] -match '-->') {
      $p = $raw[$i+1] -split '-->'
      $a = [TimeSpan]::Parse($p[0].Trim().Replace(',','.'))
      $b = [TimeSpan]::Parse($p[1].Trim().Replace(',','.'))
      $t = ''; $j = $i + 2
      while ($j -lt $raw.Count -and $raw[$j].Trim() -ne '') { $t += $raw[$j].Trim() + ' '; $j++ }
      $out += [pscustomobject]@{ n=[int]$raw[$i]; s=$a.TotalSeconds; e=$b.TotalSeconds; x=$t.Trim() }
      $i = $j
    } else { $i++ }
  }
  Write-Output $out
}

function TC([double]$sec) { [TimeSpan]::FromSeconds($sec).ToString('mm\:ss\.f') }

# 서사 구조를 한눈에 — 대본 전체를 블록으로 묶어 출력
function Show-Blocks($Cues, [int]$Size = 20) {
  $Cues | Group-Object { [math]::Floor($_.s / $Size) } | Sort-Object { [int]$_.Name } | ForEach-Object {
    $st = [int]$_.Name * $Size
    "{0} #{1,-4} {2}" -f ([TimeSpan]::FromSeconds($st).ToString('mm\:ss')), ($_.Group | Select-Object -First 1).n,
      (($_.Group.x -join ' ') -replace '\s+',' ')
  }
}

# 컷 앵커 — 키워드로 정확한 큐 시작 시각을 찾는다. 삽입 지점은 반드시 큐 경계여야 한다.
function Find-Anchor($Cues, [string]$Key, [int]$Take = 1) {
  $h = $Cues | Where-Object { $_.x -like "*$Key*" } | Select-Object -First $Take
  if (-not $h) { Write-Output ("  ??:??      [{0}]  못 찾음 — 큐가 두 줄로 갈렸을 수 있다. 더 짧은 조각으로 다시" -f $Key); return }
  foreach ($c in $h) { "{0}  #{1,-4} [{2}]  {3}" -f (TC $c.s), $c.n, $Key, $c.x }
}

function Find-Anchors($Cues, [string[]]$Keys) { foreach ($k in $Keys) { Find-Anchor $Cues $k } }

# 규격 대조 — 영상과 SRT가 같은 컷편집본인지. 0.5초를 넘으면 진행하면 안 된다.
function Test-Sync($Cues, [string]$VideoPath) {
  $vd = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 $VideoPath)
  $sd = ($Cues | Select-Object -Last 1).e
  $gap = [math]::Round($vd - $sd, 2)
  "영상 {0}  ·  SRT 끝 {1}  ·  차이 {2}초" -f (TC $vd), (TC $sd), $gap
  if ([math]::Abs($gap) -gt 0.5) { "⛔ 싱크 불일치 — 컷을 더 손본 뒤 SRT를 다시 뽑아야 한다. 이 상태로 진행하면 모든 컷이 어긋난다." }
  else { "✅ 같은 컷편집본" }
}

# 유튜브 챕터 — $Marks = @(@{at=55.5;t='첫 번째 단원'}, ...) 단, 범퍼 삽입 후 시각으로 줘야 한다
function Export-Chapters($Marks) {
  "00:00 시작"
  foreach ($m in ($Marks | Sort-Object { $_.at })) {
    "{0} {1}" -f ([TimeSpan]::FromSeconds($m.at).ToString('mm\:ss')), $m.t
  }
}

# ══════════════════════════════════════════════════════════════
#  자막 폭 실측 · 줄 나눔 · 큐 병합
#  브라우저를 띄우지 않는다 — 폰트 파일의 advance width 를 직접 읽는다.
# ══════════════════════════════════════════════════════════════

# 폰트 로드. libass 가 실제로 쓸 파일과 같은 것을 줘야 계산이 맞는다.
function Get-CaptionFont([string]$FontFile) {
  Add-Type -AssemblyName PresentationCore
  New-Object System.Windows.Media.GlyphTypeface ([Uri]("file:///" + ($FontFile -replace '\\','/')))
}

# 글자 폭(px). Pretendard 한글 advance = 0.864em — 1.0em 으로 어림하면 두 줄 비율을 몇 배로 과대추정한다.
function Get-TextWidth([string]$Text, $Font, [double]$FontSize) {
  $w = 0.0
  foreach ($ch in $Text.ToCharArray()) {
    $c = [int][char]$ch
    if ($Font.CharacterToGlyphMap.ContainsKey($c)) { $w += $Font.AdvanceWidths[$Font.CharacterToGlyphMap[$c]] }
    else { $w += 0.5 }
  }
  return $w * $FontSize
}

# 한 줄에 안 들어가면 어절 단위로 두 줄. 두 줄 폭이 가장 비슷해지는 곳에서 자른다.
# ★ 반환은 반드시 @(...) — 앞에 쉼표를 붙이면 배열이 한 겹 더 감싸져 $lines[0] 이 문자열이 아닌
#   배열이 되고, 줄 나눔과 강조어 탐색이 에러 없이 조용히 전부 실패한다.
function Split-CaptionLine([string]$Text, $Font, [double]$FontSize, [double]$MaxW) {
  if ((Get-TextWidth $Text $Font $FontSize) -le $MaxW) { return @($Text) }
  $ws = @($Text -split '\s+' | Where-Object { $_ -ne '' })
  if ($ws.Count -lt 2) {
    $h = [int][math]::Ceiling($Text.Length / 2)
    return @($Text.Substring(0, $h), $Text.Substring($h))
  }
  $best = -1; $bestDiff = [double]::MaxValue
  for ($k = 1; $k -lt $ws.Count; $k++) {
    $a = ($ws[0..($k-1)] -join ' '); $b = ($ws[$k..($ws.Count-1)] -join ' ')
    $wa = Get-TextWidth $a $Font $FontSize; $wb = Get-TextWidth $b $Font $FontSize
    if ($wa -gt $MaxW -or $wb -gt $MaxW) { continue }
    $d = [math]::Abs($wa - $wb)
    if ($d -lt $bestDiff) { $bestDiff = $d; $best = $k }
  }
  if ($best -lt 0) { $best = [math]::Max(1, [int]($ws.Count / 2)) }
  return @(($ws[0..($best-1)] -join ' '), ($ws[$best..($ws.Count-1)] -join ' '))
}

# ── 큐 최소 병합 ──────────────────────────────────────────────
# 받은 SRT 는 시간/길이 기준으로 기계적으로 잘려 있어 「AI ／ 에이전트에게」처럼
# 한 단어가 두 큐로 갈라진다. 그 자리만 붙인다. 리듬과 타이밍은 건드리지 않는다.
#
# 붙이는 경우는 둘뿐이다.
#   A 뒤 큐가 조사 하나로 시작          「결과물 ／ 을 만들어」
#   B 앞뒤가 한 낱말을 이룸              「AI ／ 에이전트」 「포장 ／ 이사」
#
# ★ 조사 목록에서 「이·가·은·는·도·만·로·서」를 뺐다. 이들은 관형사·부사와 글자가 겹쳐
#   「말한 ／ 이 다섯 가지를」처럼 멀쩡한 경계를 붙여 버린다(실측 오탐 다수).
#   큐 첫 어절로 조사가 홀로 나오는 일 자체가 드물다 — 좁게 잡는 편이 맞다.
#
# ★ 복합어도 앞조각만 보면 「데이터 ／ 아니면」처럼 오탐이 난다. 반드시 쌍으로 본다.
$script:CaptionJosaHeads = @('을','를','의','와','과','께','에게','에서','한테')
$script:CaptionCompoundPairs = @{
  'AI'       = @('에이전트','비서','도구','기술','모델','서비스')
  '포장'     = @('이사')
  '인공'     = @('지능')
  '데이터'   = @('베이스','센터','분석')
  '프롬프트' = @('엔지니어링')
  '도메인'   = @('지식')
  '개인'     = @('정보')
  '자동'     = @('화')
  '반자동'   = @('화')
  '에이'     = @('전트')
  '워크'     = @('숍','플로')
  '이메'     = @('일')
  '스마트'   = @('폰','워치')
  '비즈니'   = @('스')
  '커뮤니'   = @('티','케이션')
}

function Merge-BrokenWords {
  param($Cues, $Font, [double]$FontSize, [double]$MaxW,
        [double]$MaxGap = 0.12, $ExtraPairs = @{})
  $pairs = @{}
  foreach ($k in $script:CaptionCompoundPairs.Keys) { $pairs[$k] = $script:CaptionCompoundPairs[$k] }
  foreach ($k in $ExtraPairs.Keys) { $pairs[$k] = $ExtraPairs[$k] }

  $out = New-Object System.Collections.Generic.List[object]
  $log = New-Object System.Collections.Generic.List[string]
  $cur = $null
  foreach ($q in $Cues) {
    if ($null -eq $cur) { $cur = [pscustomobject]@{ n=$q.n; s=$q.s; e=$q.e; x=$q.x }; continue }

    $gap  = $q.s - $cur.e
    $tail = ($cur.x -split '\s+')[-1]
    $head = ($q.x   -split '\s+')[0]

    $ended  = $cur.x -match '(다|요|죠|까|네|함|음|우|자)\s*[.?!”"''」]*$' -or $cur.x -match '[.?!”"''」]\s*$'
    $isJosa = $script:CaptionJosaHeads -contains $head
    $isPair = $false
    if ($pairs.ContainsKey($tail)) { foreach ($nx in $pairs[$tail]) { if ($head.StartsWith($nx)) { $isPair = $true; break } } }
    $fits   = (Get-TextWidth ($cur.x + ' ' + $q.x) $Font $FontSize) -le ($MaxW * 2)

    if ($gap -le $MaxGap -and -not $ended -and $fits -and ($isJosa -or $isPair)) {
      $why = if ($isJosa) { '조사분리' } else { '복합어' }
      $log.Add(("  #{0,-4} [{1}] {2} ／ {3}" -f $cur.n, $why, $cur.x, $q.x))
      $cur.e = $q.e
      $cur.x = $cur.x + ' ' + $q.x
    } else {
      $out.Add($cur)
      $cur = [pscustomobject]@{ n=$q.n; s=$q.s; e=$q.e; x=$q.x }
    }
  }
  if ($cur) { $out.Add($cur) }

  # 번호를 다시 매긴다 — 강조어 표가 큐 번호로 물리기 때문
  for ($i = 0; $i -lt $out.Count; $i++) { $out[$i].n = $i + 1 }

  Write-Output ([pscustomobject]@{ Cues = $out.ToArray(); Merged = $log.Count; Log = $log.ToArray() })
}
