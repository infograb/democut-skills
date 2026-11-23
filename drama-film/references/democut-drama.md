# DemoCut 으로 만들기

2026-11-22 기준이다. 값은 `democut_get_options(slug)` 로 다시 확인한다. 돈이 드는 호출은 모두 견적을 그대로 보여 주고 동의를
받은 뒤에 한다.

## 프로젝트

`democut_create_project(title, ratio)`. 비율은 나중에 바꾸지 못한다. 블록아웃과 장소 스틸도 같은 비율로 렌더한다.

## 인물

- `democut_create_character(name, look_text, persona_text)` → `democut_make_character_photo`(유료) → 사진을 고른다. 고른 사진이
  없으면 제출이 `PIP_PHOTO_REQUIRED` 로 막힌다. 참고 인물로 쓰려면 Pro 이상이다.
- `look_text` 는 캐릭터 사진과 이미지 컷 프롬프트에 붙고 영상 프롬프트에는 붙지 않는다(DemoCut 2026-11 코드 기준). 영상 프롬프트에는 `persona_text` 만
  「등장 인물의 성격과 태도」 로 붙고 인물이 여럿이면 이름을 붙여 사람마다 한 줄이다(democut-app `executors/ai_video.py`).
  그래서 외모는 프롬프트의 PEOPLE 문단에 적는다.
- `persona_text` 에 말하는 방식(「짧게 핵심만 말한다」)을 적으면 대사가 없는 컷에서도 입이 말하는 모양으로 움직였다(Seedance 2.0,
  democut-app 같은 파일의 주석에 남은 실측). 대사가 없는 구간은 프롬프트에 「lips closed」 를 적는다.
- `democut_put_character` 는 전체 교체다. 이름, 목소리, 성격을 함께 보낸다.
- 옷 색은 블록아웃 알약의 띠 색과 맞춘다. 모델이 색으로 누가 누구인지 안다. 캐릭터 시트에는 손에 든 소품을 넣지 않고 여러
  사람을 한 판에 넣지 않는다. 여럿이 든 판은 키프레임처럼 복사된다(blockout-kit `skills/blockout/SKILL.md` 「Seedance
  run」). drama A2 의 인물 사진은 한 사람에 133원(상한)이었다(2026-11-22).

## 장소 그림

1. 블록아웃 장소 스틸(인물을 숨긴 카메라 화면)을 자산으로 올린다. 로컬 파일은 `democut_create_upload_url` 로 주소를 받아
   `curl -T` 로 올린다.
2. `democut_add_cut(mode="ai_image")` 에 그 스틸을 참고로 넣고 kit 의 틀로 프롬프트를 적는다. 「Turn this grey blockout
   into a photoreal film still. Keep the layout exactly: the same camera angle and lens, every wall, …」 다음에 블록아웃의
   구조물을 자리와 함께 나열하고 장소와 시간, 빛을 적는다. 사람과 읽히는 글자는 넣지 않고 렌즈와 질감은 영화 말로 적는다
   (kit 「Location plates」). 실내는 「lived-in, personal objects, a little mess」 처럼 사람이 사는 흔적을 적는다. 같은 장소를
   적었을 때 이 말 하나로 텅 빈 방과 살아 있는 방이 갈렸다([Thomas Lundström, 7:51~8:25](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
3. `democut_estimate_cut_image` → 동의 → `democut_make_cut_image` → `democut_wait_jobs` → 받아서 사람이 본다. 그림
   한 장(1536×1024, 품질 보통, 참고 그림 하나)이 38원이었다(2026-11-22, 요율 v5). 그림을 블록아웃 스틸과 맞대 본다. drama A2 의
   그림은 블록아웃에 없는 탁자를 더했고 영상에도 탁자가 나왔다. 프롬프트에 「There is no coffee table」을 적어도 그림이
   이겼다. 다르면 그림을 다시 만든다.
4. 고른 그림을 `democut_upload_asset(kind="image")` 로 올려 영상 컷의 `reference_asset_ids` 에 넣는다.

같은 장소가 상태를 바꾸면(깨끗한 거실, 부서진 거실) 상태마다 그림을 만든다. 스케치에서 실사로 가는 이미지 컷의 자세한
요령은 room-set-photos 스킬의 `references/democut-image.md` 에 있다.

## 블록아웃 올리기

생성 구간마다 렌더한 블록아웃을 `democut_upload_asset(kind="video")` 로 올리고 `state` 가 `ready` 인지 본다. Seedance 2.5 는
참고 영상을 10개, 한 개 2~30초, 합 30초까지 받는다. 영상은 Seedance 로 보낼 때 BytePlus 자산으로 등록돼 심사를 거친다.

## 컷

구간 하나가 `mode="ai_video"` 컷 하나다. `democut_add_cut(slug, mode="ai_video", title, after, draft_spec)` 으로 만들고 고칠
때는 `democut_get_storyboard` 로 새 `rev` 를 받은 직후 `democut_put_cut_draft` 한다. `democut_get_cut` 의 응답에는 `rev` 가 없다.

```json
{
  "mode": "ai_video",
  "duration_s": 12,
  "video_model": "seedance-2.5",
  "video_resolution": "480p",
  "image_prompt": "12s 16:9 cinematic Korean drama scene, 3 shots …",
  "dialogue": [{"id": "ln_a1b2c3", "text": "어, 왔어?"}],
  "reference_character_ids": ["chr_…", "chr_…"],
  "reference_asset_ids": ["ast_… (장소 그림)"],
  "reference_video_asset_ids": ["ast_… (이 구간의 블록아웃)"]
}
```

- `duration_s` 는 정수 초, Seedance 2.5 는 4~15초다. 블록아웃 길이와 같게 한다.
- 참고 인물과 참고 이미지를 합쳐 4개까지다. 두 사람과 장소 하나면 하나가 남는다.
- 영상 모델에는 `reference_asset_ids` 의 그림이 먼저 가고 그 뒤에 `reference_character_ids` 순서로 사람마다 고른 사진의 캐릭터
  시트가 간다(democut-app `services/cuts.py`). 프롬프트는 이 순서로 Image 1, Image 2 … 라고 부르고 블록아웃은 Video 1 이다
  (BytePlus Seedance 문서의 참고 이름). 장소 그림 하나와 두 사람이면 장소가 Image 1 이다.
- 참고 인물과 장소 그림 없이 블록아웃만 넣으면 알약이 결과에 남았다(drama A). 둘을 넣은 A2 는 남지 않았다
  ([`prompt.md`](prompt.md) 「실측」).
- 참고 영상이 있으면 첫·끝 장면 그림(`image_asset_id`, `end_image`)을 쓰지 못한다(`SPEC_CONFLICT`).
- `host` 는 비워 둔다(기본 `model`). 영상 모델이 대사를 말하고 현장음을 만든다.

## 대사와 소리

- `host=model` 이고 `dialogue` 가 있으면 DemoCut 이 프롬프트 끝에 「화면 속 인물이 아래 말을 적힌 그대로 순서대로 한국어로
  말한다」와 그 줄들, 그리고 배경음악 금지 문장을 붙인다. 대사가 없으면 현장음만 담고 음악과 나레이션을 막는 문장을
  붙인다(democut-app `executors/ai_video.py` 의 `MODEL_DIALOGUE_SUFFIX`, `NO_MUSIC_SUFFIX`).
- `dialogue[]` 의 줄에는 말하는 사람 칸이 없다. 붙는 문장도 한 사람(「the on-screen character」)을 말한다. 두 사람이 말하는
  구간은 미확인이라, 말하는 사람마다 구간을 나누고 상대는 반응 샷으로 둔다.
- 자막은 만든 소리에 맞춰 정렬된다. 화면 글자를 바꾸려면 `subtitle_text` 를 쓴다(그 칸만 고치면 0원).
- `host=voice` 는 정해 둔 목소리(`voice_id`)로 읽게 하지만 화면 속 인물은 말하지 않는다. 내레이션 광고에 쓴다.

## 견적과 초안

```text
democut_estimate_cuts(slug, items=[{"cut_id": …}])     # 초안이 저장된 컷은 cut_id 만
→ total_krw · rate_version · notes 를 그대로 보여 주고 동의
democut_make_cuts(slug, items=[{"cut_id": …}], confirmed_total_krw=…, rate_version=…)
democut_wait_jobs(…)
```

값은 토큰으로 매기고 참고 영상도 결과와 같은 해상도로 센다. 실측 견적이다(2026-11-22, 요율 v5).

| 컷 | 견적 |
| --- | --- |
| 8초 Seedance 2.5 720p, 참고 영상 8초 | 3,118원 |
| 8초 Seedance 2.5 480p, 참고 영상 8초 | 1,458원 |
| 8초 Seedance 2.5 flash 720p, 참고 영상 8초 | 2,100원 |
| 8초 Seedance 2.5 flash 480p, 참고 영상 8초 | 984원 |
| 15초 Seedance 2.5 720p, 참고 영상 없음 | 4,881원 |

`democut_estimate_cuts` 에 `spec` 을 주면 초안을 바꾸지 않고 그 spec 의 값만 낸다. 초안 해상도와 최종 해상도의 값을 함께
보여 준다. 한 제작자는 47초 광고를 초안 4번과 1080p 3번으로 만들었다([Thomas Lundström, 15:29](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).

초안은 구간 하나부터 만든다. 맞으면 같은 spec 의 해상도만 올려 다시 만든다. 다시 만든 컷은 새 생성이라 초안과 같은 장면이
나오지 않는다. 초안은 오류를 찾는 데 쓴다.

## 확인

받은 영상은 `democut_get_cut` 의 `download.video` 로 새 빈 디렉터리에 받는다. 반 초마다 한 칸 격자를 만들어 샷리스트와
맞댄다.

```bash
ffmpeg -v error -i cut.mp4 -vf "fps=2,scale=320:-1,tile=6x4" -frames:v 1 sheet.jpg
```

- 샷 경계가 `beats` 의 시각에 왔는가, 화면 방향과 시선이 샷리스트대로인가. 말하는 사람이 상대가 아니라 렌즈를 보지
  않는가(drama A2 의 둘째 샷).
- 장소가 장소 그림대로인가, 회색 배경이나 블록아웃 덩어리가 남지 않았는가.
- 대사가 적은 그대로이고 말하는 사람의 입이 움직이는가. 말이 샷 안에 끝나는가(`speech_rate` 를 고칠 근거).

## 후반

- **소리.** 모델이 만든 대사와 현장음은 남기고 음악과 효과음은 따로 얹는다. 생성 소리에서 일부만 살리려면 Ultimate Vocal
  Remover 같은 음원 분리 도구로 목소리, 음악, 효과음을 나눈다([Thomas Lundström, 13:35](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
- **그레인.** 조금 넣으면 부드럽고 영화 같다(같은 영상 14:57). `ffmpeg -i in.mp4 -vf "noise=alls=6:allf=t" -c:a copy out.mp4`.
  세기는 눈으로 본다.
- **글자와 모션그래픽.** 생성에 넣지 않고 완성 타임라인 위에 따로 만든다. DemoCut 모션그래픽 컷이나 HyperFrames 를 쓴다.
- **완성본.** `democut_estimate_export` → 동의 → `democut_make_export` → `democut_download_export`. 모든 컷에 영상이 있어야 한다.
