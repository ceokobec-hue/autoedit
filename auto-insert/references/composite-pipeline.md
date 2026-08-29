# 합성 파이프라인 — 3단계

```
1 인서트 덮어쓰기  →  2 자막 굽기  →  3 범퍼 삽입
      길이 그대로        길이 그대로       여기서만 늘어남
```

**순서가 규약이다.** 범퍼는 시간을 밀어내므로 자막을 나중에 구우면 자막 수백 개의 타임코드를 전부 다시 계산해야 한다. 인서트와 자막을 **원본 타임라인에서 먼저 끝내면 계산이 아예 필요 없다.**

## 공통 인코딩 설정

```
-c:v h264_nvenc -preset p5 -rc vbr -cq {18~20} -b:v 0 -pix_fmt yuv420p
-g 60 -r 30 -video_track_timescale 30000
```

concat demuxer로 `-c copy` 하려면 **모든 조각이 같은 설정으로 인코딩**돼야 한다. 조각마다 설정이 다르면 이어 붙일 때 깨진다.

세대가 쌓이므로 cq는 단계마다 조금씩 낮춘다(20 → 20 → 18).

## 1단계 — 인서트 덮어쓰기

인서트는 **그림만 바꾸고 목소리는 그대로 흘러야 한다.** 그래서 이렇게 한다.

```
① 원본을 [조각 → 인서트 → 조각 → 인서트 → …] 로 이어 붙여 영상 트랙을 만든다
② 그 위에 원본 음성을 통째로 다시 씌운다
```

**음성을 마지막에 씌우는 게 핵심**이다. 그림이 47번 바뀌어도 목소리는 한 번도 안 끊긴다.

덮어쓰기 범퍼(있다면)도 이 단계에서 같이 처리한다.

```powershell
# 조각 (원본)
ffmpeg -ss $cur -i $SRC -t $gap @ENC -an $seg
# 조각 (인서트)
ffmpeg -i $clip -t $dur @ENC -an $seg
# 이어 붙이고 음성 재부착
ffmpeg -f concat -safe 0 -i list.txt -c copy v_only.mp4
ffmpeg -i v_only.mp4 -i $SRC -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k v1.mp4
```

**검증**: `v1` 길이 == 원본 길이 (차이 0). 그리고 **반드시 콘택트시트로 인서트가 제자리에 붙었는지 본다.** 길이가 맞아도 내용이 틀릴 수 있다.

## 2단계 — 자막 굽기

SRT를 ASS로 바꿔 굽는다. 원본 타임라인 그대로라 **시각을 손댈 필요가 없다.**

### ASS 규격 → `references/caption-style.md`

네 층 구조·세로 예산·줄 나눔·강조·큐 병합은 전부 그 문서에 있다. 여기서는 **굽는 방법**만 다룬다.

크기·색·글자체는 **회차마다 `scripts/style_gate.ps1`로 결재받는다.** 고정값을 쓰지 않는다.

```powershell
scripts\make_ass.ps1 -SrtPath $SRT -AssPath $ASS -EmphCsv $EMPH `
                     -StyleJson "{작업폴더}\caption_style.json" -PlanPs1 $PLAN
```

### 폰트 조달

libass는 woff2를 못 읽는다. OTF/TTF가 필요하다.

```
https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/public/static/Pretendard-Bold.otf
```
GitHub raw와 jsDelivr **gh** 경로는 404/끊김. **npm** 경로를 쓴다.

```bash
# 맥
ffmpeg -i v1.mp4 -vf "subtitles=sub.ass:fontsdir=$AUTOEDIT_FONTS" ... -c:a copy v2.mp4
```
```powershell
# 윈도우 — 드라이브 문자 뒤 콜론은 `\\:` 로 이스케이프한다
ffmpeg -i v1.mp4 -vf "subtitles=sub.ass:fontsdir=D\\:/fonts" ... -c:a copy v2.mp4
```
그리고 **작업 디렉토리로 이동한 뒤 상대 경로**로 ass를 지정하는 편이 안전하다.

### 네 층을 **한 패스에서** 굽는다

배경 박스 · 키워드 띠 · 글자(강조 포함) · 말풍선을 `make_ass.ps1` 하나가 만든다. 나중에 한 층을 따로 얹으면 자막→범퍼를 통째로 다시 돌려야 한다 — **한 번은 형광펜을 못 넣고 납품했다**(형광펜 ASS가 완성된 시각이 영상이 이미 렌더된 뒤였다).

별도 알파 레이어로 만들지 않는다 — 24분짜리 알파 렌더는 몇 시간이 걸린다.

**강조는 글자색이다.** 예전에는 `\p1` 드로잉으로 형광펜 띠를 그렸는데, 띠를 어느 x에 놓을지 알아내려고 ① 후보 뽑기 ② HTML 생성 ③ 브라우저 폰트 로딩 확인 ④ 폭 실측 ⑤ 좌표 계산을 거쳤다. 그러고도 **몇 px 어긋나 옆 글자를 침범**했다. 색으로 바꾸면서 ②~⑤가 통째로 없어졌다.

폭이 필요한 곳(배경 박스·줄 나눔)은 **폰트 파일의 advance width를 직접 읽는다** — `srt_tools.ps1`의 `Get-TextWidth`. 브라우저를 띄우지 않는다.

**강조 후보는 사용자 검토를 거친다.** 개념어 사전으로 뽑으면 「섭외하고」처럼 동사 어미가 섞인다. 표로 내고 × 표시를 받는다.

**확인은 큐 시작 시각을 직접 집어** 프레임을 뽑는다. 강조 큐는 0.5초짜리도 있어 1초 간격 샘플에는 안 걸린다.

## 3단계 — 범퍼 삽입

여기서만 길이가 늘어난다. 범퍼는 무음이라 **v2와 같은 규격의 무음 오디오 트랙을 붙여야** 이어 붙일 수 있다.

```powershell
ffmpeg -i $bumper -f lavfi -i anullsrc=r=48000:cl=stereo `
  -map 0:v:0 -map 1:a:0 -t $dur -shortest @ENC @AENC $seg
```

중간 삽입점에서 v2를 자르고 그 사이에 범퍼를 끼운다. 끝에 붙이는 범퍼는 마지막에 이어 붙인다.

**검증**: 최종 길이 == 원본 + 삽입 범퍼 합계. 그리고 콘택트시트.

## QHD 파이프라인

HyperFrames `--resolution`은 **정수배 프리셋만** 지원한다(1080p / 4K). QHD(2560×1440)는 1.333배라 직접 못 뽑는다.

```
1080p로 작성  →  --resolution landscape-4k 로 렌더  →  lanczos 로 2560:1440 축소
```

QHD로 직접 그리는 것보다 이 편이 깨끗하다.

**촬영 원본이 1080p여도 QHD 업로드는 이득이다.** 유튜브가 1440p 이상에만 VP9 코덱을 붙인다(1080p는 AVC). 같은 1080p로 시청해도 VP9이 눈에 띄게 깨끗하고, **글자·그래픽이 많은 영상이 이득을 가장 크게 본다.**

## 납품

```powershell
rclone copy $local "gdrive:<내 폴더>" --transfers 2 --drive-chunk-size 64M
```
(`gdrive:` 는 `rclone config` 에서 여러분이 붙인 이름이다. 이 도구가 대신 올려 주지는 않는다)
업로드 후 **로컬/원격 파일 개수를 대조**한다. rclone은 NOTICE를 stderr로 뱉어 PowerShell이 에러처럼 보이게 하는데, 전송은 성공한 것이다. 개수로 판단한다.
