# DemoCut 으로 만들기

도구 이름은 DemoCut MCP 의 것이다(연결 이름에 따라 `mcp__democut__…`·`mcp__democut-xxxx__…` 처럼 앞이 붙는다).
컷 계획의 모양은 도구 스키마에 없다. 자원 `democut://guide` 와 `democut_get_options` 가 말한다. 아래는 MV 에 걸리는 것만 적는다.

**돈이 나가는 것은 견적, 사람의 동의, 제출 순서다.** 견적 금액과 `rate_version` 을 그대로 보여 주고 동의받은 값을
제출에 싣는다. 409 `QUOTE_MISMATCH` 는 다시 보내지 말고 견적을 새로 받는다. 실패한 제출을 그대로 다시 보내지 않는다.

## 0. 프로젝트

- `democut_list_projects` 로 쓸 프로젝트가 있는지 보고 사용자에게 묻는다. 새로 만들면
  `democut_create_project(title, ratio)`. 비율은 만든 뒤 못 바꾼다(가로 MV `16:9`, 숏폼 `9:16`).
  가로 MV 와 세로 숏폼을 둘 다 내려면 프로젝트를 둘 만든다.
- `democut_get_recipe` 로 그 영상 종류의 레시피가 있는지 본다. 있으면 그 구성을 따른다.

## 1. 곡 만들기(곡이 없을 때)

1. `democut_plan_music(prompt, length_s)` 로 구성표(구간·가사 초안)를 받는다(0원). prompt 에 장르·분위기·빠르기(BPM)·
   목소리(보컬 성별·톤)를 적는다.
2. 구성표의 구간과 가사를 사용자와 고친다. 가사의 후렴 구호는 짧고 되풀이되게 한다(포인트 동작이 붙는다).
3. `democut_estimate_music(plan=…, model=…)` 견적, 동의, `democut_make_music(plan=…, confirmed_cost_krw, rate_version,
   project_slug, title)`, `democut_wait_jobs`.
4. 결과 자산의 `meta.duration_ms` 가 곡 길이다. 생성 응답에는 BPM·가사 시각이 없다. 파일을 받아
   `mv_timing.py tempo`·`energy` 로 잰다.

곡이 이미 있으면 올리고 곡 목록에 넣는다(`democut_add_music(slug, asset_id, kind="song")`). 공개 https 주소가 있으면
`democut_upload_asset(kind="audio", source_url=…)`, 로컬 파일뿐이면 `democut_create_upload_url` 로 주소를 받아 셸에서 올린다.
곡의 권리를 가진 사람인지 먼저 묻는다.

## 2. 출연자

- `democut_list_characters` 로 멤버 캐릭터가 있는지 본다. 없으면 `democut_create_character(name, look_text, persona_text)`.
  `look_text` 에 얼굴·머리를 적고, 사진을 만들어(`democut_make_character_photo`, 유료) 하나를 선택한다.
- 선택된 사진이 없는 캐릭터를 컷에 넣으면 제출이 `PIP_PHOTO_REQUIRED` 로 막힌다(청구 전).
- 컷 하나에 참고 인물과 참고 이미지를 **합쳐 4개까지** 넣는다.
- 한 컷 안에서 의상이나 장면 세계가 바뀌면, 바뀌기 전 의상의 인물 사진과 바뀐 뒤 의상 시트를 참고로 나눈다.
  인물+이미지 합쳐 4개를 넘기지 못한다. 예: 멤버 세 명의 시작 의상 인물 사진 셋 + 도착 의상 시트 하나.
  멤버가 셋보다 많으면 컷을 나누거나, 앞줄만 참고로 넣고 나머지는 고정 문단으로 그린다.

## 3. 컷

콘티 한 줄에 컷 하나(나눈 줄은 여럿). `democut_add_cut(slug, mode="ai_video", title="<줄 #> <요약>", after=<앞 컷>,
draft_spec={…})`.

- 한 생성 안에서 장면을 나누는 줄은 컷 하나이고, 장면 목록은 프롬프트에 적는다(아래 「프롬프트의 짜임」).
- 짧은 컷 여럿으로 나눈 줄(`7a`·`7b`·`7c`)은 컷마다 `song_start_ms` 를 그 컷이 맡은 곡 시작으로 주고, 만든 뒤
  `trim_out_ms` 로 맡은 길이만 남긴다(130 BPM 한 줄 7,385ms 를 셋으로 나누면 2,462ms).
- 이미 만든 줄에 컷을 더하거나 나눌 때는 콘티 표를 먼저 고치고 초안을 고친다.

### 초안을 고칠 때

`democut_put_cut_draft`(또는 같은 저장 도구)를 호출하기 **직전**에 `democut_get_cut` 으로 그 컷을 새로 읽는다.
대화 중에 다른 도구가 `rev` 를 올려 두면, 예전에 받은 초안으로 저장이 거절되거나 그 사이 수정이 덮인다.
읽은 `rev` 와 `draft_spec` 을 기준으로 고친 뒤 바로 저장한다. 확정된 카메라 연출이 초안에서 빠지거나 약해지지
않았는지도 이 단계에서 본다([`camera-moves.md`](camera-moves.md) 「확정된 연출은 줄이지 않는다」).

### 춤·노래 컷(곡을 들려주며 만든다)

```json
{"mode": "ai_video", "host": "music", "duration_s": 8, "video_resolution": "720p",
 "image_prompt": "<장면 · 초 단위 사건 · 안무 · 카메라 · 고정 문단 · 공통 끝 문장>",
 "reference_character_ids": ["chr_…", "chr_…", "chr_…"],
 "reference_asset_ids": ["ast_…"]}
```

- `host: "music"` 이면 그 컷의 배경음악 구간을 영상 모델에 레퍼런스로 보내고, 모델이 만든 소리는 버린다. 노래는
  완성본에서 깔린다. 대사·목소리·나레이션 칸을 함께 주면 422 이고 자막은 꺼진다.
- 실측: 이 레퍼런스가 제공자의 민감 콘텐츠 필터에 걸려 생성이 무효가 된 적이 있다. 무효면 요금은 환불된다.
  자동으로 같은 명세를 다시 넣지 말고, 사람에게 알린 뒤 다음 중 하나를 고른다.
  (1) 프롬프트를 다듬고 `host: "music"` 을 유지한 채 견적부터 다시,
  (2) `host` 를 비우거나 `host: "voice"` 로 바꿔 곡을 보내지 않는다. (2)는 필터를 피할 수 있으나 춤이 박에
  떨어지지 않을 수 있다.
- 음악을 받는 영상 모델만 된다. `video_model` 을 비우면 서버가 음악을 받는 모델로 정한다. 음악을 못 받는 모델을 적으면
  거부되고, 거부 문구가 쓸 수 있는 모델을 알려 준다. 어떤 모델이 받는지는 `democut_get_options` 가 말한다.
- Seedance 계열은 곡과 함께 **참고 이미지나 참고 인물이 있어야** 한다.
- **첫 장면 그림(`image`·`image_asset_id`)을 함께 쓸 수 없다**(422 `SPEC_CONFLICT`). 그 그림은 `reference_asset_ids` 로 옮긴다.
- 해상도(`video_resolution`)를 고르지 않으면 720p 를 넘지 않는다. 고르면 그 값으로 만들고 값이 오른다.
- 새로 만드는 컷에는 곡을 함께 붙일 수 없다. `add_cut` 으로 컷을 만들고, 곡을 붙이고, 그 `cut_id` 로 견적을 받는다
  (곡 없이 제출하면 `MUSIC_REQUIRED`).
- 길이는 정수 초다(4~15). 줄 길이를 올림한 값으로 만들고 나중에 `trim_out_ms` 로 자른다.

컷마다 곡을 붙인다.

```text
democut_set_cut_bgm(slug, cut_id, rev, bgm={"asset_id": <곡>, "song_start_ms": <그 줄의 곡 시작 ms>})
```

- `song_start_ms` 는 `mv_timing.py grid` 의 값이다. 비우면 「앞 컷에서 이어받기」인데 뮤직비디오 컷은 만들 때 그 자리를 알
  수 없어 `MUSIC_START_REQUIRED` 로 막힌다. 반드시 숫자로 준다.
- 저장할 때 숫자로 굳는다. 순서를 바꾸거나 앞 컷 길이를 바꿔도 따라 움직이지 않으므로, 바꿨으면 다시 지정한다.
- 곡 길이를 서버가 모르면(자산에 `duration_ms` 가 없으면) 확정하지 못하고 만들 때 막힌다.

### 콘티에서 부르는 줄을 나눈다

콘티를 짤 때, 가사를 부르는 순간은 그 순간만의 컷으로 둔다. 걷기, 전환, 포즈, 소품 건네기처럼 움직임이 많은
장면과 한 컷에 넣지 않는다. 부르기 전에 그걸 한 컷에 몰아 넣으면 모델이 시간을 다 써, 입이 앞서거나 늦고,
하드 컷이 박에 떨어지지 않는다.

콘티의 카메라 컷 전환은 생성에 샷 바뀜을 시키지 않는다. DemoCut 타임라인에 컷 둘을 이어 붙여 편집으로 한다.
바뀌는 시각은 앞 컷의 trim 길이가 정한다. 앞 컷은 그 시각까지 가고, 다음 컷은 바뀐 샷에서 시작한다.
인물은 그 컷에서 반 박 늦게 카메라를 본다
([`camera-moves.md`](camera-moves.md) 「노래 직전 카메라 컷 전환」).

부르는 컷은 2–3초다. 카메라는 고정이거나 느리다. 움직임은 시선, 고개, 박에 맞춘 가벼운 흔들림만 둔다.
입은 단어·구의 MOUTH MAP 으로 적는다. 영상은 4초부터라 4초로 만들고 `trim_out_ms` 로 그 구절만 남긴다.

움직임이 적은 부르는 컷은 싼 모델(Seedance Flash 등)로 견적을 먼저 받는다. 제출은 그 견적에 동의한 뒤다.
앞 컷은 새로 만들기 전에, 이미 있는 버전을 trim 으로 쓸 수 있는지 본다. 그 trim 은 0원이다.

콘티 표의 부르는 컷마다 실제 곡 시각 범위와 그 안의 가사 구를 적는다. 값은 소리에서 잰 것이고, 박 칸을
눈대중으로 채운 값이 아니다.

실측: SQUISH MV A4 는 걷기, 녹아내림, 아크, 포즈, 마이크, 하이 앵글, 부르기를 8초 컷 하나에 넣었고 입이
계속 어긋났다. 마이크를 건네받기까지는 이미 있는 버전의 trim 으로 두고, 하이 앵글 부르기는 Flash 의 짧은
컷으로 나눴다.

### 입을 맞춰 부르는 줄(단독샷)

화면 구성은 콘티의 립싱크 칸이 정한다. 기본은 「없음」이다. 될 수 있으면 입모양 없이 안무에 집중하고,
꼭 입을 보여야 하는 줄만 단독샷으로 만든다.

| 립싱크 칸 | 화면 | 프롬프트에 넣는 것 |
|---|---|---|
| 멤버 이름 | 그 멤버 한 명만 나오는 단독샷. 얼굴을 크게 잡는다 | 아래 MOUTH MAP 한 블록 |
| 없음 | 단체샷이면 아무도 노래하지 않고 입을 다문 채 안무만 한다. 노래하지 않는 다른 장면(분신·소품, 넓은 샷)이어도 된다 | `nobody sings, every mouth stays closed` |

- 한 단체샷 안에서 입을 맞추게 하지 않는다. 여럿이 함께 부르는 줄(후렴 구호 등)의 입을 보이려면 줄을 나눠
  부르는 멤버마다 단독샷을 만든다.
- 단체샷에서 부르지 않는 멤버에게 입을 다물라고 적었는데도 그 멤버가 입을 벌린 프레임이 나왔다(한 번).
  입 다문 단체샷도 만든 뒤 「5. 확인과 자르기」의 확인용 파일로 입을 본다.

입 문장은 아래 MOUTH MAP 한 블록만 넣는다. 가사 음절과 박 위치(초, 단어 시각으로 잰 값)를 적는다.
노래하는 동안에도 몸은 박에 맞춰 가볍게 흔든다.
노래 구간 전에 동작을 너무 많이 넣으면 모델이 입을 늦게 열고 몰아 부른다. 노래 직전 동작은 줄인다.
노래 직전 카메라 컷 전환은 위 「콘티에서 부르는 줄을 나눈다」대로 타임라인에 컷 둘을 이어 붙여 편집으로 한다.
바뀌는 시각은 앞 컷의 trim 길이가 정하고, 부르는 컷은 바뀐 샷에서 시작한다.
인물은 반 박 늦게 그 카메라를 본다. 구도는 [`camera-moves.md`](camera-moves.md) 「노래 직전 카메라 컷 전환」.
입은 그 구도의 문장에 다시 적지 않고 MOUTH MAP 을 가리킨다.

#### 한국어 가사의 입모양 (MOUTH MAP)

영상 모델은 한글 음절의 자음과 받침을 조음하지 못한다. 자음과 받침은 빼고, 음절마다 핵심 모음 하나만 입모양으로 적는다.
이 대응은 이 블록에만 둔다. 프롬프트의 다른 곳과 다른 문서에서는 이 절을 가리키고 표를 다시 적지 않는다.

| 모음 | 적는 모양 | 입 |
|---|---|---|
| ㅏ · ㅑ · ㅘ | 아 | small relaxed open jaw |
| ㅣ · ㅟ · ㅢ | 이 | lips slightly spread |
| ㅓ · ㅕ · ㅝ | 어 | small rounded opening |
| ㅗ · ㅛ | 오 | rounded lips |
| ㅜ · ㅠ | 우 | pursed lips |
| ㅡ | 으 | nearly closed, lips spread |
| ㅐ · ㅔ · ㅒ · ㅖ | 에 | slightly open, lips spread |

받침이 ㅁ·ㅂ·ㅍ 인 음절만, 그 박의 끝에서 입을 잠깐 다문다(`brief lip close at the end of the beat`).

모음은 음절마다 고르되, 프롬프트의 MOUTH MAP 은 단어나 구로 묶는다. 음절마다 시각을 주면 모델은
음절을 떼어 끊어서 발음한다. 짧은 말은 박보다 앞서고, 긴 말은 음절마다 잘려 화면보다 늦는다.
실측: 「다시」는 빨랐고, 「일어서」는 음절마다 잘려 늦었다.

구의 시작은 실제 소리의 onset 이고, 구의 끝(마지막 모음이 앉고 입이 닫히는 자리)은 그 박에 떨어진다.
음절별 시각은 검수표에만 두고 프롬프트에 넣지 않는다. 이어지는 음절이 같은 모음이면(일·어·서 = 어)
입을 음절마다 여닫지 않고, 한 번 벌린 채 살짝만 움직인다.

방향은 긍정형으로 적는다. 구마다 시작과 끝만 주고, 안은 이어지는 모음 흐름이다
(`sung smoothly as one phrase, legato, like a real singer`). 크기는 긍정 낱말로 준다
(`small relaxed jaw`, `soft`, `slightly`). 다음 가사부터는 `lips stay together` 로 적는다.
부정 문장은 블록 맨 끝 한 줄만 둔다(`Avoid only syllable-by-syllable chopping.`).
금지를 반복하면 피해야 할 모양이 강조되고 `image_prompt` 약 8,000자 한도를 낭비한다.
'아이 어어어'처럼 모음만 한 덩어리로 나열하는 것은 사람에게 설명할 때 쓴다.

```text
MOUTH MAP:
<시작>–<끝> "<단어>" = <모음 흐름>, one quick connected word, sung smoothly as one phrase, legato, like a real singer
<시작>–<끝> "<구>" = <모음>, one smooth legato phrase flowing into the beat, the mouth holds one opening with a slight movement
<컷 시각> lips stay together
Avoid only syllable-by-syllable chopping.
```

위 블록은 적는 꼴만 보인다. 시각은 아래 실측처럼 실제 소리에서 잰 컷 시각이고, 박 칸을 눈대중으로 채운 값이 아니다.

카메라 문장은 그 줄에서 확정한 구도를 그대로 적는다. 하이 앵글이면 정면 고정의 예로 바꾸지 않는다.
입 문장은 위의 MOUTH MAP 한 블록이고, 카메라 문장 안에 다시 적지 않는다.

```text
Solo shot, only one performer in frame: the CENTER member alone.
Camera: high-angle shot looking down, she lifts her head up to the lens while singing, her full face and upper
body visible, nothing cropped above the eyes.
On the beat the camera pans about 45 degrees to the right, bringing the members who handed her the prop into
the same frame.
MOUTH MAP: the single block for this shot, one phrase at a time, in the form above.
She keeps a light body sway on the beat while singing.
```

정면 고정이 확정된 줄만 `locked-off frontal medium shot from the waist up, eye level` 을 쓴다.

#### 음절 시각은 실제 소리에서 잰다

MOUTH MAP 의 시각은 그 컷 아래에 깔리는 실제 BGM 구간에서 온다. 박 칸을 눈대중으로 채우지 않는다.
구간을 고를 때 BGM 자산, `song_start_ms`, `cut_start_ms`, trim 을 모두 반영한다. 보컬 음절의 시작은
onset·에너지와 듣기로 잰다.

확인할 것:

- 그 구간의 가사 전체. 앞줄과 뒷줄을 포함한다.
- 음절 수.
- 각 음절의 시작.
- 마지막 음절의 끝.
- 다음 가사가 시작하는 시각.

곡 파일에서 잰 시각은 컷 시각으로 바꾼다. 컷 안 초는 `(곡 ms - song_start_ms) / 1000` 이다
([`conti-and-timing.md`](conti-and-timing.md) 「가사 시각을 단어로 재기」). `trim_in_ms` 로 컷 앞을 잘랐으면
그 초를 더 뺀다. `cut_start_ms` 는 타임라인에서 그 컷이 시작하는 시각이라, 컷 안 초에 더하지 않고
구간이 그 컷이 맞는지 대조할 때 쓴다. 다음 가사부터는 `lips stay together` 로 적는다.

실패(실측): 「다시 일어서」의 박 칸을 눈대중으로 채워(4.62·4.85·5.31) 「일」이 불리는 박을 쉼으로 적었다.
「일」과 「어」가 반 박 늦어, 화면에서는 「일」인 동안 이미 다른 모음이었고 「서」 뒤에 음절이 하나 더 있는 것처럼 보였다.
음절마다 시각을 준 프롬프트에서는 「다시」가 박보다 앞서고, 「일어서」가 음절마다 잘려 화면보다 늦었다.

프롬프트에 넣는 MOUTH MAP 은 구의 시작과 끝만 적는다.

```text
4.68–5.05 "다시" = 아→이, one quick connected word, sung smoothly as one phrase, legato, like a real singer
5.14–6.06 "일어서" = 어, one smooth legato phrase flowing into the beat, the mouth holds one opening with a slight movement
6.21s lips stay together
Avoid only syllable-by-syllable chopping.
```

음절 시각은 검수표다. 프롬프트에 넣지 않는다.

| 음절 | 모음 | 컷 시각 |
|---|---|---|
| 다 | 아 | 4.68 |
| 시 | 이 | 4.91 |
| 일 | 어 | 5.14 |
| 어 | 어 | 5.37 |
| 서 | 어 | 5.83–6.06 |
| 다음 가사 | lips stay together | 6.21부터 |

#### 모델이 만든 소리

Seedance 같은 모델은 자기 소리를 만든다(`host` 가 모델). 입은 그 소리에 맞는다. 그 소리는 실제 곡과 다르고,
늦거나 음절이 더 붙을 수 있다. 검수 기준은 보는 사람이 듣는 실제 BGM 이다. BGM 음절 시작, 모델 소리,
24fps 입 프레임(`mv_timing.py sheet --fps 24`)을 나란히 놓고, 음절마다 들은 음절과 본 입을 짝짓는다.
입이 벌어진 프레임만 옛 맵과 대조해 판정하지 않는다.

`host: "music"` 이 립싱크에 도움이 될 수 있다. 미확인.

- 입 검수는 「음절 시각은 실제 소리에서 잰다」와 「모델이 만든 소리」를 따른다.

### 곡이 없는 연출 컷(인트로 등)

- 곡을 보내지 않으려면 `host` 를 비우거나 `host: "voice"` 로 둔다. 둘 다 노래 레퍼런스는 없다.
  어느 값이 그 요금제에서 통과하는지는 `democut_get_options` 와 견적으로 확인한다. `host` 를 비우면 영상 모델이
  현장음·효과음을 만든다. 프롬프트에 소리를 적는다
  (`Sound: only the cute scream and the wet splat, then quiet room tone; no music, no singing`).
- 이 컷과 다음 춤 컷의 경계가 노래가 시작하는 순간이다. 경계를 숨기려면 렌즈 덮기 전환을 쓴다
  ([`camera-moves.md`](camera-moves.md)). 만든 뒤 `mv_timing.py sheet` 로 덮인 마지막 칸을 재서 `trim_out_ms` 로 자른다.
- 이 컷의 소리를 어느 시점부터 끄려면 구간을 나누고 뒤 구간을 끈다.

```text
democut_set_cut_edit(slug, cut_id, rev, edit={"segments": [
  {"start_ms": 0, "end_ms": 7667}, {"start_ms": 7667, "volume_db": -40}]})
```

`volume_db: -40` 은 끔이다. 구간 좌표는 그 컷 원본의 ms 다. 구간을 쓰면 `trim_in_ms`·`trim_out_ms` 는 비운다.

### 프롬프트의 짜임

한 컷의 `image_prompt` 는 이 순서로 쓴다.

1. 비율과 장면, 춤 컷이면 밀도 문장: `16:9 music-video chorus on a sunset rooftop disco, K-pop idol choreography,
   dense sharp beat hits, isolations and finger tutting, not a children's nursery dance`
2. 초 단위 사건(곡 없는 연출 컷), 또는 카운트별·멤버별 안무(춤 컷). 안무는 [`choreography.md`](choreography.md) 의 순서.
   장면을 나눈 줄은 머리에 장면 수와 간격을 말하고 장면마다 시각·구도·동작을 한 문장씩 쓴다.

```text
16:9 music-video chorus, 8 seconds, a fast multi-shot edit of 8 shots separated by HARD CUTS (instant cuts, no
transitions), one shot every two beats, every cut landing exactly on the beat of the attached music reference (130 BPM).
The camera rhythmically pushes in and pulls back in time with the music, each move spanning about two beats
and landing on the beat, not every beat, sharp landing frames, no motion blur.
Shot 1, 0.00-0.92s, frontal wide shot, fast push-in to a mid-thigh medium on the first beat: <카운트·멤버별 동작>.
HARD CUT at 0.92s. Shot 2, 0.92-1.85s, floor-level low-angle close shot, pulling back on the beat: <동작>.
…
HARD CUT at 6.46s. Shot 8, 6.46-7.30s, frontal wide shot: <동작>, holding the pose to the end.
```

3. 카메라: [`camera-moves.md`](camera-moves.md) 의 표현
4. 고정 문단: `CLEAR MEMBER POSITIONS locked: CENTER = …; LEFT = …; RIGHT = …`
5. 공통 끝 문장: `Motion timed to the beat of the attached music reference, photorealistic adults, no on-screen text
   no logos no watermarks, no real celebrity likeness`(곡 없는 컷은 첫 구를 빼고 소리 문장을 넣는다)

입을 맞추는 단독샷의 입 문장은 「한국어 가사의 입모양」 MOUTH MAP 블록 하나다. 카메라 문장이나 끝 문장에 입모양을
다시 적지 않는다.

## 모델 고르기

`video_model` 을 비우면 서버가 음악을 받는 기본 모델로 정한다. 사람이 모델을 고르면 그 값을 넣고, 견적 금액과
`rate_version` 을 보여 준 뒤 동의받는다. 아래는 한 뮤직비디오에서 8초 컷을 만든 실측이다(요율 버전 5, 2026-11).
요금은 바뀌므로 이 숫자를 견적 대신 쓰지 않는다.

| 모델 | 출력 | 8초 실측 | 4초 실측 | 잘 나온 것 | 약한 것 |
|---|---|---|---|---|---|
| Seedance 2.5 | 720p | 2,616원 | 1,322원 | 박에 맞춘 움직임, 지정한 카메라가 비교적 잘 나옴 | 값이 더 비싸다 |
| Seedance 2.5 Flash | 720p | 1,716원 | (해당 실측 없음) | 값이 싸다 | 약 4,000자의 카운트별 안무·카메라 시각·금지 손 모양을 대부분 따르지 않았다. 어떤 요금제·시점에서는 곡 레퍼런스(`host: "music"`)를 받지 못하고, 한 번은 모델이 열려 있지 않아 거절된 뒤 요금이 환불되었다. 구도와 전환이 중요한 컷은 일반 모델을 쓰거나, 이 모델에는 확정 구도와 전환 위주의 짧은 프롬프트를 쓴다 |
| MiniMax H3 | 768p(1344×768) | 910원 | (해당 실측 없음) | 값이 싸고, 어떤 립싱크 줄에서는 입 타이밍이 더 나았다 | 아크샷이 약하고 대상이 프레임을 벗어나기 쉽다. 해상도가 다른 컷(720p)과 섞이면 완성본에서 화질이 달라 보일 수 있다. 노래를 따라가는지는 Seedance 만큼 검증되지 않았다 |

실사 군무·아크·정확한 박 전환이 중요하면 일반 Seedance 쪽을 먼저 권한다. 같은 콘티로 모델만 바꿔 비교하고 싶으면
견적을 나눠 보여 주고 사람이 고른다. 한 프로젝트 안에서 모델을 섞을 때는 출력 크기가 다른지 완성본 전에 알린다.

## 4. 견적, 동의, 만들기

```text
democut_estimate_cuts(slug, items=[{"cut_id": …}, …])   # 초안이 저장된 컷은 spec 없이 cut_id 만
→ total_krw · rate_version · notes 를 그대로 보여 주고 동의를 받는다
democut_make_cuts(slug, items=[{"cut_id": …}], confirmed_total_krw=<total_krw>, rate_version=<rate_version>)
democut_wait_jobs(…)
```

- 한 번에 많이 만들기 전에 대표 컷 하나(첫 후렴처럼 인물이 다 나오는 컷)를 먼저 만들어 인물·의상·자리가 맞는지 본다.
  장면을 두 박마다 나눈 줄이 있으면 그 줄을 대표 컷으로 골라 전환이 박에 떨어지는지도 함께 본다.
- 만든 영상이 마음에 안 들어 다시 만들면 재과금이다. 다시 만들기 전에 무엇을 바꿀지 사용자와 정한다.

## 5. 확인과 자르기

1. `democut_get_cut` 이 주는 버전의 `download.video` 로 영상을 받는다(새 빈 디렉터리).
2. `mv_timing.py sheet --bpm <곡 BPM>` 로 격자를 보고 콘티와 대조한다(인물 자리, 의상, 안무 순서, 사건 시각,
   박 착지, 확정 카메라, 금지 손 모양, 공간이 생겨나는 전환의 첫 프레임과 재료에 맞는 생김새, 전환 중 멈춘 포즈).
   한 박에 칸 하나가 필요하면 `--fps 0`.
3. 춤 컷은 줄 길이로 자른다: `democut_set_cut_edit(edit={"trim_in_ms": 0, "trim_out_ms": <줄 길이 ms>})`.
   뮤직비디오 컷에서 되는 편집은 앞뒤 자르기뿐이다(구간·배속·멈춤 늘이기·무음 자르기는 422).
4. 웹 타임라인 미리보기에서 곡과 함께 듣는다.
5. 입모양이 맞는지는 사람이 보고 정한다. 에이전트는 소리를 듣지 못하고 컷 파일에는 소리가 없다. 그 줄의 곡 구간을 입힌 확인용
   파일을 만들어 사람에게 보인다. 음절 시각과 모델 소리 대조는 「음절 시각은 실제 소리에서 잰다」.

```bash
ffmpeg -i cut.mp4 -ss <song_start_ms ÷ 1000> -t <줄 길이 초> -i song.mp3 \
  -map 0:v -map 1:a -t <줄 길이 초> -c:v libx264 -crf 18 -c:a aac check.mp4
```

## 6. 완성본

순서의 모든 컷에 영상이 있어야 한다. 영상이 없는 컷이 있으면 완성본 견적이 막힌다(실측 `VERSION_NOT_FOUND`).

- 내려받은 컷 파일에는 소리가 없다. 노래는 완성본을 만들 때 타임라인에 깔린다.
- 컷 경계에 페이드 인·아웃을 넣지 않는다. 곡과 화면은 콘티의 자르는 자리에서 바로 붙는다.
  보내기 전에 완성본 미리보기에서 경계가 끊기지 않았는지만 본다.

```text
democut_estimate_export(slug, quality) → 동의 → democut_make_export(…) → democut_wait_jobs → democut_download_export
```
