---
name: creator-style-formats
description: >
  레퍼런스 크리에이터의 공개 숏폼을 먼저 모아 스타일을 읽고, 그 문법으로 아무 가상 인플루언서의
  세로(9:16) 영상 포맷을 설계한다. 특정 캐릭터에 묶이지 않는다. 유튜브 쇼츠·인스타 릴스·틱톡
  주소나 핸들을 주면 공개 메타데이터로 채널 중앙값과 상위 영상을 가리고, 훅·길이·자막·샷·
  제품 장면·엔딩을 스타일 프로파일로 남긴 다음 타깃용 포맷 표(컷 초, 샷, 훅 문장, 제품이
  증명되는 장면)를 만든다. 가상 인물은 써 본 사람처럼 말하지 않고, 화면에 있는 동안 가까이
  '가상인물' 표시를 둔다. 포맷 파일에는 영상 구조만 둔다.
  "레퍼런스 스타일로 포맷", "이 쇼츠처럼 구성", "UGC 포맷 설계", "가상 인플루언서 숏폼",
  "크리에이터 분석해서 포맷", "creator style formats", "short-form format from this creator"
  같은 말이 나오면 쓴다. 영상 생성·업로드는 이 스킬 밖이다.
license: SUL-1.0
metadata:
  category: shortform
  locale: ko-KR
  author: infograb
  phase: v1
---

# creator-style-formats

레퍼런스 크리에이터가 이미 올린 공개 숏폼을 먼저 읽고, 그 문법으로 **타깃 가상 인물**의 세로 영상 포맷을 설계한다.

순서는 바뀌지 않는다. 수집한 표가 있기 전에 스타일을 단정하지 않고, 스타일 프로파일이 있기 전에 포맷 표를 쓰지 않는다.
포맷은 영상 구조만 담는다. 조사 순서, 견적, 생성, 업로드는 이 파일과 참고 문서에만 있고 포맷 결과물에는 넣지 않는다.

타깃은 사용자가 이름을 붙인 가상 인물이다. 외모·방·말투의 고정 문장은 그 사람이 준 프로필에만 있다.
연재는 [references/example-yeonjae.md](references/example-yeonjae.md) 의 예시로만 나온다.

영상 생성(DemoCut 컷)은 돈이 드는 다음 일이다. 이 스킬은 포맷 표까지 만들고 멈추며, 승인 없이 생성·결제·업로드를 하지 않는다.

## 원칙

- **측정값이 없는 칸은 비운다.** 조회수·길이·자막 시각은 스크립트 출력을 그대로 옮긴다. 화면을 보기 전에 컷 수, 샷, 조명을 확정하지 않는다. 추측은 「미확인」이다.
- **순위는 채널 중앙값이다.** 조회수가 없는 글을 0 으로 넣지 않는다. 상위는 그 작성자 안에서 중앙값보다 높은 글이다. 작성자가 둘이면 평균 내지 않고 따로 순위를 매긴다.
- **문장과 얼굴은 가져오지 않는다.** 가져오는 것은 유형과 리듬이다. 레퍼런스의 훅 문장, 유행어, 집, 얼굴, 로고를 타깃에 붙이지 않는다.
- **가상 인물은 경험의 주체가 아니다.** 「써 봤다」「먹어 봤다」「샀다」를 타깃의 입으로 쓰지 않는다. 신뢰는 출처가 있는 공식 후기 전언, 공식 수치, 공식 사진으로 만든다.
- **가상인물 표시는 포맷의 일부다.** 추천·보증 포맷에서 가상 인물이 화면에 있는 동안, 그 가까이 「가상인물」을 계속 둔다. 근거와 경제적 이해관계 표시는 [references/disclosure.md](references/disclosure.md).
- **제품이 잘리거나 오려 붙인 사진으로 보이지 않게 한다.** 사진 컷 기준은 [references/photo-cuts.md](references/photo-cuts.md). 레퍼런스가 제품을 잘라 써도 이 기준을 낮추지 않는다.
- **공개된 글만 본다.** 비공개·일부 공개, 로그인 뒤의 글, 쿠키로 권한을 넓히는 일은 하지 않는다. 영상 파일은 사용자가 이미 가지고 있거나 받자고 한 뒤에만 다룬다.

## 도구

스크립트는 이 스킬 디렉터리의 `scripts/` 에 있다. 표준 라이브러리만 쓴다(Python 3.8+).
내려받은 JSON 을 읽는 파이썬은 `-I` 로 돌린다.

```bash
P=<이 스킬 디렉터리>/scripts
python3 -I $P/collect_posts.py fetch URL [URL...] --out <빈 디렉터리> [--limit 30] [--subs] [--thumbnails]
python3 -I $P/collect_posts.py normalize DUMP.json --out <빈 디렉터리>
python3 -I $P/collect_posts.py youtube-api '@핸들' --out <빈 디렉터리> [--limit 30]
python3 -I $P/collect_posts.py oembed URL --out <빈 디렉터리>
python3 -I $P/collect_posts.py cues FILE.vtt --to 6
python3 -I $P/collect_posts.py frames VIDEO.mp4 --out <빈 디렉터리> [--every 1]
```

`fetch` 는 PATH 의 `yt-dlp` 를 `--skip-download` 로 부른다. 영상 파일은 받지 않는다.
유튜브 데이터 API 키는 환경 변수 `YOUTUBE_API_KEY` 만 읽는다. 명령 인자에 넣지 않는다.
받는 법, 막히는 경우, 2026-11-20 에 확인한 한계는 [references/collect.md](references/collect.md).

참고 문서는 필요할 때 읽는다.

| 문서 | 언제 |
|---|---|
| [references/collect.md](references/collect.md) | 주소를 받고, 실패하고, 순위를 읽을 때 |
| [references/style-rubric.md](references/style-rubric.md) | 스타일 프로파일의 칸을 채울 때 |
| [references/format-design.md](references/format-design.md) | 프로파일을 포맷 표로 바꿀 때 |
| [references/photo-cuts.md](references/photo-cuts.md) | 제품·음식 사진 컷을 넣을 때 |
| [references/disclosure.md](references/disclosure.md) | 가상인물 표시, 경험 표현, 광고 표시를 적을 때 |
| [references/review.md](references/review.md) | 포맷을 넘기기 전에 검사할 때 |
| [references/example-yeonjae.md](references/example-yeonjae.md) | 결과 파일이 어떤 모양인지 볼 때. 규칙의 원본이 아니다 |
| [templates/](templates/) | 결과 디렉터리에 복사해 칸을 채울 빈 문서 |

## 작업 순서

출력 디렉터리는 사용자가 정한 곳, 없으면 `~/creator-formats/<slug>/` 다.
`<slug>` 는 영문 소문자와 하이픈이다. 스크립트의 `--out` 은 없거나 비어 있어야 하므로, 표는 그 하위 `data/` 처럼 빈 곳에 받는다.

결과 파일은 이렇게 나눈다.

| 파일 | 내용 |
|---|---|
| `inputs.md` | 사용자가 준 입력 |
| `data/posts.json`, `data/posts.csv` | 정규화된 글과 순위 |
| `style-profile.md` | 측정한 스타일. 주장마다 글 id |
| `formats.md` | 영상 구조만 |
| `review.md` | 포맷을 검사한 체크리스트 |

### 1. 입력을 받는다

[templates/inputs.md](templates/inputs.md) 를 복사해 채운다. 사용자가 이미 말한 것은 다시 묻지 않고 「이렇게 알고 있다」고만 적는다.

있어야 다음으로 가는 것:

- 레퍼런스: 핸들 또는 공개 글·채널 주소. 유튜브 쇼츠, 인스타그램 릴스, 틱톡. 주 레퍼런스가 둘 이상이면 어느 쪽을 기준으로 포맷을 짤지 정한다.
- 타깃: 이름, 누구로 보이게 할지, 말투, 배경이 되는 장소, 하면 안 되는 말.
- 이번에 다룰 제품·주제.
- 제약: 길이, 금지 표현, 돈·협찬·제휴 링크가 있는지.

없는 항목은 비운 채로 두지 말고 사용자에게 묻는다. 프로필을 지어 채우지 않는다.

### 2. 공개 글을 모은다

collect.md 의 순서를 따른다. 요점만 적으면 이렇다.

1. 유튜브 채널이고 `YOUTUBE_API_KEY` 가 있으면 `youtube-api` 를 먼저 쓴다.
2. 없거나 주소가 틱톡·인스타그램·개별 영상이면 `fetch` 를 쓴다. 기본 30개, 최대 50개. 요청 사이에 스크립트가 쉰다.
3. `fetch` 가 봇 확인이나 로그인으로 막히면 쿠키로 넘지 않는다. 사용자에게 자기 환경에서 받은 yt-dlp JSON 을 받아 `normalize` 하거나, 키가 생기면 `youtube-api` 로 다시 받는다.
4. 그것도 없으면 `oembed` 는 제목·작성자·썸네일만 남긴다. 조회수와 길이가 없으면 순위를 만들지 못하고, 그 표만으로 프로파일을 확정하지 않는다.
5. 자막 파일이 있으면 `cues --to 3` 과 `--to 6` 으로 첫 대사만 뽑는다. 키프레임은 `frames` 로, 이미 있는 파일에만, 사용자가 그 파일을 써도 된다고 한 뒤에만 뽑는다.

표가 0건이면 멈춘다. 상위 글을 기억으로 채우지 않는다.

`posts.json` 의 `summary.creators[].view_median` 과 `top_posts` 를 프로파일에 그대로 적는다.
`notes` 에 있는 빠진 글, 조회수 없음, 세로 여부 미확인도 같이 적는다.

### 3. 스타일 프로파일을 쓴다

[templates/style-profile.md](templates/style-profile.md) 를 복사한다. 채우는 법은 [references/style-rubric.md](references/style-rubric.md).

프로파일은 상위 글(중앙값 초과)을 본문으로 하고, 중앙값 이하와 어떻게 다른지 한 줄로 적는다.
반복이 상위 글 두 개 이상에서 보여야 패턴이다. 한 글에서만 보이면 패턴이 아니라 그 글의 특징이고, 포맷으로 올리지 않는다.

자막·제목·캡션만으로 알 수 있는 것과, 화면을 봐야 아는 것을 섞지 않는다.
컷 수, 샷, 조명, 손과 제품의 위치는 화면 근거(키프레임을 봄, 사용자가 본 메모, 공개 영상의 특정 초)가 있을 때만 확정이다.

### 4. 포맷을 설계한다

[templates/formats.md](templates/formats.md) 를 복사해 `formats.md` 만 채운다.
이 파일에 작업 순서, 스크립트 명령, 견적, 승인 문장을 넣지 않는다. 그 문장이 필요하면 대화와 `inputs.md` 에 둔다.

설계 규칙은 [references/format-design.md](references/format-design.md). 요점:

- 포맷 수는 상위 글에서 반복된 구조의 수다. 억지로 개수를 채우지 않는다. 사용자가 개수를 정했으면 그 수를 넘기지 않고, 근거가 부족한 자리는 만들지 말고 그렇다고 적는다.
- 각 포맷에 컷 표(초), 샷, 화면 글, 말의 자리, 새로 쓴 훅 예, 제품이 증명되는 장면, 가상 인물이라 바꾼 점을 넣는다.
- 초는 상위 글의 길이 중앙값 안에 둔다. 컷을 어떻게 나누었는지는 화면 근거가 있을 때만 확정이고, 없으면 그 행에 미확인을 적는다.
- 훅 문장은 새로 쓴다. 레퍼런스 문장을 인용해 보여주는 일은 프로파일의 근거 칸에서만 한다.
- 사진 컷은 photo-cuts.md, 표시 문구는 disclosure.md 를 따른다. 타깃 프로필과 이 두 기준이 레퍼런스와 부딪히면 프로필과 두 기준을 따른다.

### 5. 체크리스트로 본다

[references/review.md](references/review.md) 를 `review.md` 로 복사해 포맷마다 표시한다.
통과하지 않은 항목은 포맷을 고친 뒤 다시 본다. 고칠 수 없는 빈칸은 미확인으로 남기고, 그 포맷을 확정이라고 말하지 않는다.

### 6. 보고

다음 순서로 짧게 쓴다.

1. 결과 경로(`posts.json`, `style-profile.md`, `formats.md`, `review.md`)
2. 레퍼런스, 모은 글 수, 조회수 중앙값, 상위 글 id 와 중앙값 대비 배수
3. 포맷 이름과 길이, 각 포맷이 어느 상위 글의 구조를 따랐는지
4. 가상 인물 때문에 레퍼런스와 다르게 둔 점
5. 못 받은 것, 미확인 칸, 사용자가 다음에 볼 것(화면 근거가 없는 컷, 협찬 여부, 공식 후기 원문)

## 함정

- 레퍼런스 없이 「UGC 는 원래 이렇다」로 포맷을 쓰지 않는다. 일반 골격 이름은 format-design.md 에 있지만, 이번 레퍼런스에서 반복되지 않으면 포맷이 아니다.
- oEmbed 의 가로·세로는 임베드 크기다. 영상 화면비로 쓰지 않는다. 2026-11-20 실측은 collect.md.
- 썸네일 한 장으로 컷 리듬을 단정하지 않는다.
- 잘된 글의 문장을 살짝 바꿔 훅 예로 쓰지 않는다. 유형만 맞추고 문장은 타깃과 제품에 맞게 새로 쓴다.
- 음식의 「한 입」, 사용 전후, 택배 개봉은 타깃이 직접 써 본 이야기처럼 보이기 쉽다. 공식 사진과 공식 사용법으로 바꿀 수 없으면 그 컷을 넣지 않는다.
- 캐릭터 프로필에만 있는 규칙(특정 방, 말 속도, 옷)을 다른 타깃의 포맷에 복사하지 않는다.
