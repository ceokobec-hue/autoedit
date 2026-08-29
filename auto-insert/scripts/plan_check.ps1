# 정합성 검사 — 진행 전 필수. 하나라도 걸리면 제작에 들어가지 않는다.
# 사용: & plan_check.ps1 -PlanPath .\plan.ps1 -VideoPath ".\편집 원본.mp4"
param([string]$PlanPath, [string]$VideoPath, [double[]]$ProtectStart = @(), [double[]]$ProtectEnd = @())

. $PlanPath
$fail = 0
function TC([double]$s){ [TimeSpan]::FromSeconds($s).ToString('mm\:ss\.f') }

# ── 1. 덮어쓰기 구간 겹침 ────────────────────────────────
# ★ 괄호 필수. `[double]$c.ts + [double]$c.d` 처럼 쓰면 PowerShell 이 배열 리터럴 안에서
#   이걸 두 원소로 쪼갠다 → 끝 시각 자리에 시작 시각이 들어가 겹침 검사가 통째로 무력화된다.
#   에러는 안 난다. "✅ 겹침 없음" 이 뜨면서 아무것도 안 잡는다.
$ov = @()
foreach ($c in $INS)      { $ov += ,@( ([double]$c.ts), ([double]$c.ts + [double]$c.d), $c.id ) }
foreach ($b in $BMP_OVER) { $ov += ,@( ([double]$b.ts), ([double]$b.ts + [double]$b.d), $b.file ) }
foreach ($a in $ov) { if ($a.Count -ne 3) { "⛔ 내부 오류: 구간 배열 원소 수 $($a.Count) (3이어야 함)"; exit 1 } }
$ov = $ov | Sort-Object { $_[0] }
for ($k = 1; $k -lt $ov.Count; $k++) {
  if ($ov[$k][0] -lt $ov[$k-1][1]) {
    "⛔ 겹침: {0} 끝 {1} > {2} 시작 {3}  → 앞 컷을 짧게 자를 것" -f $ov[$k-1][2], (TC $ov[$k-1][1]), $ov[$k][2], (TC $ov[$k][0]); $fail++
  }
}
if ($fail -eq 0) { "✅ 덮어쓰기 겹침 없음 ($($ov.Count)구간)" }

# ── 2. 범퍼 삽입점이 인서트 내부에 떨어지는가 ──────────────
# 떨어지면 인서트가 반으로 잘린다.
$f2 = 0
foreach ($b in $BMP_INS) {
  $at = [double]$b.at
  if ($at -ge 99000) { continue }
  foreach ($a in $ov) {
    if ($at -gt $a[0] -and $at -lt $a[1]) { "⛔ 삽입점 {0} 이 {1} 구간 내부 → 인서트가 잘린다" -f (TC $at), $a[2]; $f2++ }
  }
}
if ($f2 -eq 0) { "✅ 삽입점 충돌 없음" } ; $fail += $f2

# ── 3. 보호 구간 침범 ───────────────────────────────────
$f3 = 0
for ($p = 0; $p -lt $ProtectStart.Count; $p++) {
  $ps = $ProtectStart[$p]; $pe = $ProtectEnd[$p]
  foreach ($a in $ov) {
    if ($a[0] -lt $pe -and $a[1] -gt $ps) { "⛔ 보호구간 {0}~{1} 침범: {2}  → 밀거나 자르거나 뺀다(보호가 우선)" -f (TC $ps), (TC $pe), $a[2]; $f3++ }
  }
  foreach ($b in $BMP_INS) {
    $at = [double]$b.at
    if ($at -lt 99000 -and $at -gt $ps -and $at -lt $pe) { "⛔ 보호구간 안에 범퍼 삽입점: {0}" -f (TC $at); $f3++ }
  }
}
if ($ProtectStart.Count -gt 0 -and $f3 -eq 0) { "✅ 보호구간 $($ProtectStart.Count)개 침범 없음" }
$fail += $f3

# ── 4. 길이 예측 ────────────────────────────────────────
if ($VideoPath -and (Test-Path $VideoPath)) {
  $vd = [double](& ffprobe -v error -show_entries format=duration -of csv=p=0 $VideoPath)
  $add = 0.0; foreach ($b in $BMP_INS) { $add += [double]$b.d }
  "원본 {0} + 삽입 {1}초 → 완성 예상 {2}" -f (TC $vd), $add, (TC ($vd + $add))
}

if ($fail -eq 0) { "`n✅ 전부 통과 — 제작 진행 가능" } else { "`n⛔ $fail 건 — 해소한 뒤 다시 검사할 것" }
