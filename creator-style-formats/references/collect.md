# 공개 글을 모으는 법

`scripts/collect_posts.py` 가 표를 만든다. 판단(무엇을 상위 스타일로 볼지)은 스타일 프로파일이 하고, 중앙값·배수·날짜 형식은 스크립트가 한다.

## 표에 들어가는 것

한 글은 `posts.json` 의 `posts[]` 한 객체다.

| 칸 | 내용 |
|---|---|
| `platform` | `youtube` · `instagram` · `tiktok` · `unknown` |
| `id`, `url` | 글 id 와 페이지 주소. 재생 서버 주소는 넣지 않는다 |
| `creator`, `creator_id` | 채널·계정 |
| `title`, `caption` | 제목과 설명. 캡션은 8,000자에서 자른다 |
| `hashtags` | 제목·캡션의 `#태그` 와, 응답의 태그 목록 |
| `duration_s` | 초. 없으면 `null` |
| `view_count`, `like_count`, `comment_count` | 없으면 `null`. 0 으로 바꾸지 않는다 |
| `upload_date` | `YYYY-MM-DD` |
| `width`, `height`, `aspect` | 영상 크기. `9:16` `4:5` `1:1` `16:9` 또는 약분한 비. 없으면 `null` |
| `is_short_form` | 주소가 쇼츠·릴스이거나 틱톡이거나 세로로 길면 `true`. 가로로 길면 `false`. 모르면 `null` |
| `thumbnail_url` | 썸네일 주소 하나 |
| `subtitle_langs` | 응답에 적힌 자막 언어. 자막 본문은 파일이 있을 때만 |
| `rank` | 같은 작성자 안의 중앙값, 배수, `above_median` · `at_median` · `below_median` · `unranked` |

`summary.creators[]` 는 작성자마다 `view_median`, `view_p75`, `duration_median_s`, `top_posts` 를 준다.
상위는 `view_count` 가 그 작성자의 중앙값보다 큰 글이다. 모두 같으면 상위가 없다.
짝수 개일 때 중앙값은 가운데 둘의 평균이다. 중앙값이 0 이면 배수는 `null` 이다.

`posts.csv` 는 같은 칸을 엑셀이 열 수 있게 UTF-8 BOM 으로 쓴다. 캡션 본문은 JSON 에만 있다.

비공개, 일부 공개, 로그인 필요, 구독자 전용은 표에서 빼고 `notes` 에 건수만 남긴다.

## 어떤 명령부터 쓰나

1. **유튜브 채널**이고 환경 변수 `YOUTUBE_API_KEY` 가 있으면 `youtube-api`.
   핸들(`@이름`), `youtube.com/@이름`, `youtube.com/channel/UC…`, `UC` 로 시작하는 채널 id 를 받는다.
   공식 Data API `channels` → 업로드 재생목록 `playlistItems` → `videos`(`snippet`, `contentDetails`, `statistics`, `status`) 순서로 읽는다.
   `status.privacyStatus` 가 비공개·일부 공개면 표에서 뺀다. 그 칸이 없으면 공개 여부를 비우고 글은 남긴다.
   키는 환경 변수만 본다. 오류 문장에 키가 들어가면 지운다. 원문 응답 전체는 저장하지 않는다.
   이 API 응답에는 가로·세로가 없다. `aspect` 와 `is_short_form` 은 비운다. 썸네일 크기로 추정하지 않는다.
   `/shorts` 탭 주소를 넘겨도 업로드 목록은 숏츠만이 아니다. `notes` 가 그 사실을 남긴다.
   이번 스킬을 만들 때 이 API 를 실제 키로 호출해 보지는 않았다. 필드 이름은 공개 문서의 이름이고, 호출이 실패하면 그 오류를 적고 표를 확정하지 않는다.

2. **개별 주소, 틱톡, 인스타그램, 키가 없는 유튜브**는 `fetch`.
   PATH 의 `yt-dlp` 를 `--ignore-config --no-update --dump-single-json --skip-download --playlist-items 1:N --sleep-requests 1` 로 부른다.
   `N` 은 1~50 이고 기본 30 이다. 쿠키 옵션은 넣지 않는다. 영상 포맷을 고르는 `-f` 도 넣지 않는다.
   원문 stdout 은 `raw/` 에 둔다. 정규화한 표만 `posts.json` 이다.
   `--subs` 는 자막만 다시 받아 `subs/` 에 vtt 로 둔다(`--write-subs --write-auto-subs --convert-subs vtt`). 영상은 여전히 받지 않는다.
   `--thumbnails` 는 썸네일 그림만 `thumbs/` 에 둔다.
   2026-11-20 에 yt-dlp 2025.10.14 의 도움말·옵션 정의에서 위 플래그가 있는 것을 확인했다. `--playlist-end` 는 그 버전에 있으나 도움말이 숨겨져 있어 쓰지 않는다.

3. 사용자가 이미 받아 둔 yt-dlp JSON 이면 `normalize`. 받은 파일은 새 빈 디렉터리에서 `-I` 로 읽는다.

4. 제목만이라도 남겨야 하면 `oembed`. 유튜브와 틱톡만 호출한다. 순위는 만들지 못한다.

인스타그램 공식 oEmbed 는 이번 작성에서 호출하지 않았다. 토큰이 필요한 경로로 짐작해 호출하지 않는다.
틱톡 Display API·Research API 도 키가 없고 이번 작성에서 호출하지 않았다. 주소가 있으면 `fetch` 를 시도하고, 실패하면 그 오류를 적는다.

## 2026-11-20 에 이 환경에서 확인한 한계

- 공개 영상 `https://www.youtube.com/watch?v=jNQXAC9IVRw` 를 yt-dlp 2025.10.14 의 `--dump-single-json --skip-download` 로 읽으면 `Sign in to confirm you're not a bot` 으로 실패했다. `player_client=android_vr` 도 같은 오류였다. 쿠키로 넘는 방법은 적지 않는다. 이 환경에서 유튜브 메타데이터의 실측 경로는 oEmbed 와, 키가 있을 때의 Data API 설계뿐이다.
- 같은 영상의 유튜브 oEmbed(`https://www.youtube.com/oembed?url=…&format=json`)는 `title` `Me at the zoo`, `author_name` `jawed`, `thumbnail_url`, `width` 200, `height` 150 을 줬다. 조회수, 길이, 업로드 시각은 없었다. 200×150 은 임베드 크기라 화면비로 쓰지 않는다.
- 틱톡 개발자 문서의 oEmbed 예시(`https://www.tiktok.com/oembed?url=https://www.tiktok.com/@scout2015/video/6718335390845095173`, 문서의 Last updated 2026-10-23)를 같은 날 호출했다. 응답 키는 `version`, `type`, `width` `"325"`, `height` `"578"`, `html`, `provider_name`, `provider_url`, `embed_product_id`, `embed_type` 뿐이었다. 제목, 작성자, 조회수, 길이는 없었다. 325×578 도 화면비로 쓰지 않는다. 틱톡 주소라는 이유로만 `is_short_form` 을 true 로 둔다.

그래서 oEmbed 표만 생겼으면 프로파일을 확정하지 않는다. 사용자에게 자기 컴퓨터의 yt-dlp JSON(공개 글, `--skip-download`)이나 API 키를 요청하고, 오기 전에는 포맷을 쓰지 않는다.

## 자막과 키프레임

첫 3초·6초의 말은 자막이 있을 때 `cues FILE.vtt --to 3` 과 `--to 6` 의 JSON 을 근거로 적는다.
자동 자막은 틀릴 수 있다. 프로파일에 「자동 자막」이라고 적는다.

키프레임은 컷 수를 세기 위한 것이다. `frames` 는 로컬 파일만 받는다. URL 을 주면 멈춘다.
사용자가 공개 영상 파일을 써도 된다고 하기 전에는 받지 않고, 컷 칸은 미확인으로 둔다.
기본은 1초마다 한 장이다. 뽑은 뒤에는 그림을 직접 보고, 안 본 초를 본 것처럼 적지 않는다.

## 출력 디렉터리

`--out` 은 없거나 비어 있어야 한다. 웹에서 받은 원문은 그 안의 `raw/` 에만 둔다.
이미 표가 있는 디렉터리에 다시 받지 말고 새 디렉터리를 만든다.
