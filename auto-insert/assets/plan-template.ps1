# 합성 계획 «양식» — 이 파일을 복사해서 자기 회차 값으로 채운다.
#   ⛔ 여기 있는 숫자는 전부 «예시»다. 실제 회차 타임라인을 이 파일에 남기지 않는다.
#
# ms = 마스터(통렌더한 인서트 모음) 안에서의 시작 시각
# d  = 잘라낼 길이 (겹치는 앞 컷들은 원본보다 짧게 자른다)
# ts = 편집 원본 타임라인에서 덮어쓸 시작 시각

$INS = @(
 @{id='INS-01';ms=0.5;  d=3.5;ts=4.5},    @{id='INS-02';ms=4.5;  d=4.3;ts=8.0},
 @{id='INS-03';ms=9.5;  d=4.0;ts=12.3},   @{id='INS-04';ms=13.5; d=4.0;ts=18.1},
 @{id='INS-05';ms=17.5; d=7.0;ts=28.2},   @{id='INS-06';ms=24.5; d=5.0;ts=48.7}
 # … 필요한 만큼 줄을 늘린다. ms 는 앞 컷의 ms+d 를 이어 붙이면 된다.
)

# 덮어쓰기 범퍼 — 길이가 «안» 늘어난다. 인서트와 같은 단계에서 처리
$BMP_OVER = @(
 @{file='BMP-16_지난편리캡.mp4'; d=5.0; ts=91.9},
 @{file='BMP-50_다음편예고.mp4'; d=6.0; ts=1445.6}
)

# 삽입 범퍼 — 시간을 «밀어낸다». 자막까지 다 구운 뒤 맨 마지막에 끼운다.
#   at=99999 는 «맨 끝에 붙인다»는 뜻이다.
$BMP_INS = @(
 @{file='BMP-00_시리즈아이덴트.mp4'; d=4.0; at=55.5},
 @{file='BMP-01_1막표지.mp4';        d=4.0; at=87.1},
 @{file='BMP-30_구독CTA.mp4';        d=5.0; at=808.0},
 @{file='BMP-60_아웃트로.mp4';       d=5.0; at=99999}
)

# ── 경로 — 자기 폴더로 바꾼다 (⛔개인 경로를 그대로 두지 않는다) ──
$SRC   = "$env:USERPROFILE\Desktop\편집 원본.mp4"
$BMPD  = "$env:USERPROFILE\Videos\범퍼"
$INSD  = "$env:USERPROFILE\Videos\인서트"
$WORK  = if ($env:AUTOEDIT_WORK)  { $env:AUTOEDIT_WORK }  else { "$env:USERPROFILE\Videos\_작업" }
$FONTD = if ($env:AUTOEDIT_FONTS) { $env:AUTOEDIT_FONTS } else { "$env:USERPROFILE\.autoedit\fonts" }
$SRT   = "$env:USERPROFILE\Desktop\자막-한국어.srt"
