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

## 3. 컷

콘티 한 줄에 컷 하나(나눈 줄은 여럿). `democut_add_cut(slug, mode="ai_video", title="<줄 #> <요약>", after=<앞 컷>,
draft_spec={…})`.

### 춤·노래 컷(곡을 들려주며 만든다)

```json
{"mode": "ai_video", "host": "music", "duration_s": 8, "video_resolution": "720p",
 "image_prompt": "<장면 · 초 단위 사건 · 안무 · 카메라 · 고정 문단 · 공통 끝 문장>",
 "reference_character_ids": ["chr_…", "chr_…", "chr_…"],
 "reference_asset_ids": ["ast_…"]}
```

- `host: "music"` 이면 그 컷의 배경음악 구간을 영상 모델에 보내고, 모델이 만든 소리는 버린다. 노래는 완성본에서 깔린다.
  대사·목소리·나레이션 칸을 함께 주면 422 이고 자막은 꺼진다.
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

### 곡이 없는 연출 컷(인트로 등)

- `host` 를 비운다(영상 모델이 현장음·효과음을 만든다). 프롬프트에 소리를 적는다
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

1. 비율과 장면: `16:9 music-video chorus on a sunset rooftop disco, …`
2. 초 단위 사건(곡 없는 연출 컷), 또는 가사 줄 순서의 안무(춤 컷). 안무는 [`choreography.md`](choreography.md) 의 순서
3. 카메라: [`camera-moves.md`](camera-moves.md) 의 표현
4. 고정 문단: `CLEAR MEMBER POSITIONS locked: CENTER = …; LEFT = …; RIGHT = …`
5. 공통 끝 문장: `Motion timed to the beat of the attached music reference, photorealistic adults, no on-screen text
   no logos no watermarks, no real celebrity likeness`(곡 없는 컷은 첫 구를 빼고 소리 문장을 넣는다)

## 4. 견적, 동의, 만들기

```text
democut_estimate_cuts(slug, items=[{"cut_id": …}, …])   # 초안이 저장된 컷은 spec 없이 cut_id 만
→ total_krw · rate_version · notes 를 그대로 보여 주고 동의를 받는다
democut_make_cuts(slug, items=[{"cut_id": …}], confirmed_total_krw=<total_krw>, rate_version=<rate_version>)
democut_wait_jobs(…)
```

- 한 번에 많이 만들기 전에 대표 컷 하나(첫 후렴처럼 인물이 다 나오는 컷)를 먼저 만들어 인물·의상·자리가 맞는지 본다.
- 만든 영상이 마음에 안 들어 다시 만들면 재과금이다. 다시 만들기 전에 무엇을 바꿀지 사용자와 정한다.

## 5. 확인과 자르기

1. `democut_get_cut` 이 주는 버전의 `download.video` 로 영상을 받는다(새 빈 디렉터리).
2. `mv_timing.py sheet` 로 격자를 보고 콘티와 대조한다(인물 자리, 의상, 안무 순서, 사건 시각).
3. 춤 컷은 줄 길이로 자른다: `democut_set_cut_edit(edit={"trim_in_ms": 0, "trim_out_ms": <줄 길이 ms>})`.
   뮤직비디오 컷에서 되는 편집은 앞뒤 자르기뿐이다(구간·배속·멈춤 늘이기·무음 자르기는 422).
4. 웹 타임라인 미리보기에서 곡과 함께 듣는다.

## 6. 완성본

순서의 모든 컷에 영상이 있어야 한다. 영상이 없는 컷이 있으면 완성본 견적이 막힌다(실측 `VERSION_NOT_FOUND`).

```text
democut_estimate_export(slug, quality) → 동의 → democut_make_export(…) → democut_wait_jobs → democut_download_export
```
