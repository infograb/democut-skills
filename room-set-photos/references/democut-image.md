# DemoCut 으로 사진 만들기

`shots.json` 의 컷을 DemoCut AI 이미지 컷(`ai_image`)으로 만드는 순서. 도구 이름은 DemoCut MCP 의 것이다
(연결 이름에 따라 `mcp__democut__…`·`mcp__democut-xxxx__…` 처럼 앞이 붙는다).

**돈이 나가는 것은 견적 → 사람의 동의 → 제출이다.** 견적 금액을 그대로 보여 주고, 동의한 금액과
`rate_version` 을 제출에 싣는다. 409 `QUOTE_MISMATCH` 는 다시 보내지 말고 견적을 새로 받는다.
제출이 실패해도 같은 것을 다시 보내지 않는다(같은 spec 이 돌고 있으면 기존 잡이 돌아온다).

## 0. 연결과 프로젝트

- DemoCut 연결은 워크스페이스 하나에 묶여 있다. 연결이 여럿이면 어느 워크스페이스에 만들지 묻는다.
- `democut_list_projects` 로 쓸 프로젝트를 고른다. 새로 만들어야 하면 사용자에게 묻고
  `democut_create_project(title, ratio)` 로 만든다. **비율은 `shots.json` 의 `ratio` 와 같아야 한다**.
  그림 크기가 프로젝트 비율에서 나오고(9:16 → 1024×1536, 1:1 → 1024×1024, 16:9 → 1536×1024), 만든 뒤에는 못 바꾼다.

## 1. 레퍼런스를 올린다

스케치·보드는 로컬 파일이다.

```text
democut_create_upload_url(kind="image", project_slug=<slug>, filename="wide-1-sketch.png")
→ 응답의 upload_url 로 15분 안에:  curl -sS -T photos/sketch/wide-1.png "<upload_url>"
→ 그 응답(또는 democut_get_asset)의 state 가 ready 면 asset_id 를 쓴다
```

- 주소는 한 번만 쓴다. 실패하면 새 주소를 받는다.
- 보드 대신 제품 사진 한 장을 쓰는 컷(ffmpeg 가 없을 때, `role: product`)은 그 https 주소를
  `democut_upload_asset(kind="image", source_url=<url>, project_slug=<slug>)` 로 올린다.
- 올린 asset_id 를 컷 id 옆에 적어 둔다(다음 단계에서 순서대로 넣는다).

## 2. 대표 컷 한 장

`shots.json` 에서 `"master": true` 인 컷.

```text
democut_add_cut(slug, mode="ai_image", title="<컷 id> <제목>",
  draft_spec={"mode": "ai_image",
              "image_prompt": <shots.json 의 prompt 그대로>,
              "reference_asset_ids": [<refs 순서대로 asset_id>]})
```

- `after` 를 주지 않는다(ai_image 컷은 순서에 들어가지 않는다. 주면 422).
- **`reference_asset_ids` 는 `refs` 와 같은 순서**여야 한다. 프롬프트가 「Reference image 1 is …」 처럼 번호로 가리킨다.
  레퍼런스는 3장까지다(`shots.py` 는 대표 컷·스케치·보드 셋을 넘기지 않는다).
- 프롬프트는 4,000자까지다.

```text
democut_estimate_cut_image(slug, cut_id, model=<shots.json 의 model>, quality=<shots.json 의 quality>)
→ 금액·rate_version 을 사용자에게 그대로 보여 주고 동의를 받는다
democut_make_cut_image(slug, cut_id, confirmed_cost_krw=<동의한 금액>, rate_version=<그대로>, model=…, quality=…)
democut_wait_jobs(...)
```

- 견적과 제출의 `model`·`quality`(와 `prompt` 를 줬다면 그것도)는 같아야 한다. `model` 이 없으면 둘 다 빼서 DemoCut 기본을 쓴다.
- 대표 컷의 레퍼런스는 스케치 + 보드 두 장일 수 있다(`refs` 가 셋).
- 금액은 상한이고 실제로 든 만큼 정산된다. 참고 이미지마다 입력 이미지 토큰이, 프롬프트 길이만큼 글 토큰이 붙는다.
- `quality` 는 `medium` 으로 시작한다. 대표 컷이 맞게 나온 뒤 결과물 품질이 더 필요하면 `high` 견적을 따로 보여 준다.

## 3. 그림을 보고 확인한다

```text
democut_get_cut(slug, cut_id)  → draft_spec.image_asset_id
democut_get_asset(asset_id)    → 서명 URL
```

서명 URL 을 **새 빈 디렉터리**에 받아 Read 로 연다. `shots.md` 의 그 컷 「확인할 것」 을 하나씩 본다.

- 품목마다 화면 위치(왼쪽·가운데·오른쪽)와 거리(가까이·멀리)가 맞나
- 제품 생김새가 보드와 같나(색·재질·다리·문·서랍 수)
- 창·문이 맞는 벽에 있나, 빛이 그 창에서 들어와 그림자가 확인 목록의 「빛」 방향으로 지나
- 목록 밖 가구·러그·액자·가전이 생기지 않았나. 요청하지 않은 식물·꽃이 없나
- 물리적으로 놓일 수 있나: 가구가 바닥(또는 받침) 위에 서 있고 서로 뚫지 않나, 등받이 높은 의자가 책상 밑에 들어가 있지 않나,
  매트리스·가전·조명이 받침 가장자리 밖으로 나오지 않았나(확인 목록에 가구별 규칙의 항목이 붙는다)
- 오늘의집 사진처럼 보이나(폰으로 찍은 실사 질감, 차분한 색, 바닥에 햇빛 무늬·HDR 광이 없나, 정돈)

## 4. 나머지 컷

대표 컷이 통과하면 그 그림의 asset_id(`image_asset_id`)를 나머지 컷의 레퍼런스 1번(`role: master`)으로 쓴다.
대표 컷이 틀린 채로 넘어가면 그 틀림이 모든 컷에 퍼진다.

1. 남은 컷을 2단계처럼 `democut_add_cut` 으로 만든다.
2. 컷마다 `democut_estimate_cut_image` 를 받아 **표로 모으고 합계**를 보여 준다. 동의한 컷만 만든다.
3. 컷마다 `democut_make_cut_image` 에 그 컷의 견적 금액·rate_version 을 싣는다. `democut_wait_jobs` 로 함께 기다린다.
4. 컷마다 3단계처럼 확인한다.

## 틀렸을 때

원인을 짚고 고친 프롬프트로 다시 만든다. 다시 만들 때도 견적 → 동의 → 제출이다.

| 증상 | 고치는 법 |
|---|---|
| 색 덩어리·회색 상자가 그대로 나온다 | 프롬프트의 스케치 문장 앞에 `Photorealistic interior photo.` 를 더한다. 그래도 나오면 그 컷은 스케치를 빼고(대표 컷·보드만) 만든다 |
| 가구가 다른 자리에 있다 | 스케치를 다시 본다. 가려진 가구는 생성 모델도 놓친다. 3단계(`photo.shots`)로 카메라를 옮긴다 |
| 제품이 다른 모양이다 | 먼저 보드를 연다. 다른 물건·다른 옵션·여러 개가 찍혔으면 `ref_image`·`ref_crop`·`ref: false` 로 고친다. 그다음 `keep` 에 다른 점을 적고 plan·board 를 다시 돌린다. 그 제품만 틀렸으면 아래 「틀린 제품만 고치기」 ([product-fidelity.md](product-fidelity.md)) |
| 작은 소품이 실제보다 크다 | 먼저 그 품목 줄에 받침과의 비율(`about 1/4 that top's width …`)이 있는지 본다(`rests-on` 의 `on_scale`). 있는데도 크면 다시 만들어서는 고쳐지지 않는다(2026-11-13 세 번 모두 약 2배). 그 그림을 `fix --scale` 로 편집해 그것만 줄인다(아래 「틀린 제품만 고치기」, [product-fidelity.md](product-fidelity.md) 「크기만 틀렸을 때」). 대표 컷을 줄여도 다른 컷은 따라오지 않으니 그 소품이 보이는 컷마다 잰다 |
| 받침만 나오고 그 위 소품이 빠졌다(협탁 윗면이 비었다) | 스케치에서 받침이 화면 끝에 조금 걸치고 소품은 화면 밖인 자리다. 모델은 걸친 받침을 화면 안으로 더 들이는데, 소품을 모르면 윗면을 비워 그린다. 받침 줄에 「Its … stands on its top just out of frame」 이 있는지 본다(2026-11-13 에 더했다). 없으면 plan 을 다시 돌린다. `fix` 는 그 컷에 보이는 품목만 고치므로 빠진 소품은 편집으로 더하지 못한다. 그 컷을 다시 만든다 |
| 목록 밖 가구·러그·TV 가 생겼다 | 그 물건을 `Avoid:` 줄에 이름으로 더한다 |
| 식물·꽃이 생겼다 | `photo.plants` 가 꺼져 있는지 본다. 대표 컷에 식물이 있으면 레퍼런스 1번을 따라 다른 컷에도 생기므로 대표 컷부터 다시 만든다 |
| 의자가 책상 밑에 들어가 있다·가구가 겹치거나 떠 있다 | 그 품목 줄에 「Pulled out in front of …, not under it」 이 있는지 본다. 없으면 house.json 의 `with`·높이(`size.h`)를 확인하고 plan 을 다시 돌린다. 대표 컷에 그렇게 그려졌으면 대표 컷부터 다시 만든다 |
| 놓인 것이 받침 밖으로 나왔다(매트리스가 프레임보다 길다, 가전이 상판 끝에 걸쳤다)·가구 하나가 물리적으로 이상하다 | 그 가구의 look 에 크기 관계 말(둘레로 나온다, 선반처럼)이 없는지 본다. 제품 사진이 다른 크기 옵션이면 그 말이 치수와 부딪친다. 그다음 그 가구에 걸린 규칙(`references/furniture-rules.json`)이 받침과 놓인 것의 크기를 적는지 보고, 없으면 규칙을 더한다(SKILL.md 「가구별 규칙」). plan 부터 다시 돌린다 |
| 나란히 선 두 가구가 겹쳐 보인다(침대 받침이 협탁 밑으로 파고든다) | 그 품목 줄에 「Bare floor shows between it and the … (N cm gap)」 이 있는지 본다(가구별 규칙 `stands-near`, 10cm 안의 곁 가구에 붙는다). 도면에서 사이가 몇 cm 뿐이면 모델은 붙여 그리기 쉽다. room-set-planner 에서 작은 쪽 가구를 5~10cm 떼고 plan 을 다시 돌린다 |
| 한 가구만 실제보다 크게(높은 탁자처럼) 나오고 안쪽 가구는 작게 밀려났다 | 넓은 컷의 화면 끝에 가까운 큰 가구의 모서리만 걸린 자리다. 모서리만으로는 크기를 가늠할 단서가 없고 광각은 가장자리의 가까운 물체를 늘린다. `plan` 의 「화면 … 끝에 잘려 걸린다」 경고를 보고 `photo.shots` 로 카메라를 옮겨 그 가구를 화면 밖으로 빼거나 전체가 들어오게 한다. 대표 컷이면 대표 컷부터 다시 만든다 |
| 벽지·바닥·빛이 대표 컷과 다르다 | 레퍼런스 1번이 대표 컷인지 확인한다. 그 컷의 `reference_asset_ids` 순서를 본다 |
| 천장·벽만 많다 | `photo.camera_height` 를 낮추거나(1,000~1,100) 카메라를 방 안쪽으로 옮긴다 |

- 프롬프트만 바꿀 때는 `democut_estimate_cut_image`·`democut_make_cut_image` 의 `prompt` 에 같은 글을 넣는다
  (초안의 `image_prompt` 대신 쓴다).
- 레퍼런스를 바꿀 때는 `democut_get_cut` 으로 초안과 rev 를 읽고 `reference_asset_ids` 만 고쳐
  `democut_put_cut_draft` 로 같은 rev 에 보낸다(초안은 통째로 교체된다).
- 다시 만든 뒤 `democut_get_cut` 의 결과 그림이 새 그림인지 확인한다. 아니면 `democut_select_cut_image` 로 고른다.

## 틀린 제품만 고치기

컷이 거의 맞고 제품 한두 개만 틀렸을 때(모양이든 크기든), 또는 그 컷을 만든 뒤 집에서 작은 것만 바뀌었을 때.
전체를 다시 만들면 다른 곳이 틀어지기 쉽다.

1. `shots.py fix photos/shots.json <컷> <품목…> --images <제품 사진 디렉터리>` → `fixes/<컷>--<품목>.json` 과 보드.
   크기만 틀렸으면 `--scale <배율>`, 집에서 바뀐 것은 `--change "<영어 문장>"` 을 더한다
   ([product-fidelity.md](product-fidelity.md) 「크기만 틀렸을 때」·「집에서 바뀐 것도 같은 편집에 싣기」).
2. 보드(`boards/fix-….png`)를 1단계처럼 올린다.
3. 같은 컷에서 `democut_get_cut` 으로 초안·rev 를 읽고 `image_prompt` 를 fix 프롬프트로, `reference_asset_ids` 를
   `[그 컷의 지금 image_asset_id, fix 보드]` 로 바꿔 `democut_put_cut_draft`.
   원래 프롬프트·레퍼런스는 `shots.json` 에 남아 있으니 처음부터 다시 만들 때 그것으로 되돌린다.
4. 견적 → 동의 → 제출(같은 `model`·`quality`). 그림을 받아 fix 의 확인 목록으로 본다 — 고친 제품이 맞고 **다른 곳이 그대로**인지.
   다른 곳이 바뀌었으면 `democut_select_cut_image` 로 앞 그림을 다시 고른다.
