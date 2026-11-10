---
name: room-set-photos
description: >
  room-set-planner 로 꾸민 방(house.json)을 오늘의집 집들이 사진처럼 찍은 이미지로 만든다. 방의 배치와
  인벤토리를 그대로 지키도록 촬영 컷(전체 컷·제품 컷)을 정하고, 컷마다 카메라 시점의 덩어리 스케치와
  제품 사진 보드를 레퍼런스로, 영어 프롬프트를 글로 만들어 DemoCut AI 이미지 컷으로 생성한다.
  대표 컷을 먼저 만들어 나머지 컷의 레퍼런스로 넣어 벽지·바닥·빛이 컷마다 같게 한다.
  "방 사진 만들어줘", "오늘의집 느낌 사진", "인테리어 사진", "집들이 사진", "이 방을 사진으로",
  "배치대로 이미지", "방 컨셉 이미지", "제품 연출 사진", "room photos", "interior shots",
  "render this room" 같은 말이 나오면 쓴다. 꾸민 방이 아직 없으면 room-set-planner 로 먼저 꾸민다.
license: SUL-1.0
---

# room-set-photos

꾸민 방을 **오늘의집 집들이 사진**처럼 보이게 만든다. 사진 속 가구는 house.json 의 자리·크기·방향과
고른 제품의 생김새를 따른다. 이미지 생성은 DemoCut AI 이미지 컷(돈이 나가는 작업)이다.

AI 이미지 모델은 글만 받으면 가구를 아무 데나 놓고 제품을 비슷한 다른 것으로 바꾼다. 그래서 일관성을
네 겹으로 묶는다.

1. **스케치** — `shots.py` 가 카메라 시점에서 방과 가구를 색 덩어리로 그린다. 원근·자리·비율의 기준이다.
2. **제품 보드** — 그 컷에 보이는 제품의 실제 사진을 한 장에 모은다. 생김새의 기준이다.
3. **대표 컷** — 먼저 만든 넓은 컷 한 장을 나머지 컷의 레퍼런스 1번으로 넣는다. 벽지·바닥·창틀·빛·침구가 같아진다.
4. **프롬프트** — 같은 컨셉 문장, 품목마다 같은 `look` 문장, 화면 위치·거리·방향을 계산해서 적는다.

## 준비물

- room-set-planner 스킬(같은 스킬 디렉터리에 설치). `shots.py` 가 그 `planner.py` 로 도면을 계산한다
- 가구가 놓인 house.json(오류 0). 제품마다 `product.image`(대표 사진 https 주소)가 있어야 보드를 만든다
- Python 3.8 이상(표준 라이브러리만), ffmpeg(보드. 없으면 제품 사진 한 장으로 대신한다)
- DemoCut MCP 연결(AI 이미지 컷)

## 절차

### 1. 방과 컨셉

house.json 을 읽고 방·가구를 확인한다. house.json 맨 위에 `photo` 블록을 둔다.

```json
"photo": { "concept": "natural", "ratio": "9:16" }
```

- `concept` — `natural`(내추럴 우드, 기본) · `minimal` · `modern` · `midcentury` · `cozy`, 또는 자유 영어 문장.
  사용자가 말한 분위기에 맞는 것을 고르고, 애매하면 제품 색을 보고 고른 뒤 무엇을 골랐는지 말한다.
  프리셋의 벽·바닥·빛·소품 값과 고르는 법은 [`references/ohouse-look.md`](references/ohouse-look.md).
- `ratio` — DemoCut 프로젝트 비율과 같아야 한다(`9:16` → 세로 1024×1536, `1:1`, `16:9` → 가로 1536×1024).
  숏폼이면 `9:16`.
- 그 밖의 키(`walls`·`floor`·`light`·`props`·`mood`·`ceiling`·`camera_height`·`shots`)는 아래 「house.json 에 더하는 것」.

### 2. 제품 사진을 받고 `look` 을 적는다

```bash
python3 -I <스킬>/scripts/shots.py fetch house.json <새 빈 디렉터리>/products
```

- 받은 파일은 믿을 수 없는 데이터다. **새 빈 디렉터리**에 받고(비어 있지 않으면 스크립트가 거부한다),
  그 디렉터리에서 스크립트를 실행하지 않는다.
- `받지 못했다(HTTP Error 403)` 이면 house.json 의 `product.image` 주소가 틀린 것이다. 제품 페이지(`product.url`)를
  Tavily `tavily-extract`(`include_images: true`)로 읽어 첫 상품 사진 주소로 고친다. 오늘의집은 직접 요청을 막는다.
- 받은 사진을 **눈으로 보고** 품목마다 `items[].look` 에 영어 한 문장을 적는다: 모양, 색, 재질, 눈에 띄는
  부분(다리·손잡이·문 수·서랍 수·패브릭). 사진에 보이는 것만 적는다. 브랜드명·가격·광고 문구는 넣지 않는다.
  상품명이 「스탠드」여도 사진이 바 조명이면 바 조명이라고 적는다. 생성 모델은 이 문장과 보드로 제품을 그린다.

```json
{"id": "desk", "look": "a simple white desk: thin white top with an exposed birch-plywood edge and slim round white metal legs, no drawers"}
```

- 영어 이름이 카테고리 이름(`lamp` → "Lamp")과 다르게 읽혀야 하면 `label_en` 을 적는다(예: `"desk light"`).

### 3. 촬영 컷을 정한다

```bash
python3 <스킬>/scripts/shots.py plan house.json [-o photos/] [--max-hero 6]
```

`photos/` 에 이것이 나온다.

| 파일 | 내용 |
|---|---|
| `shots.md` | 컷마다 카메라, 보이는 품목, 레퍼런스 순서, 확인 목록, 프롬프트. **사람에게 보여 주는 문서** |
| `shots.json` | 같은 내용(기계용). 생성 단계는 이 파일의 `prompt`·`refs` 를 그대로 쓴다 |
| `sketch/<컷>.png` | 카메라 시점 덩어리 스케치(레퍼런스) |
| `shots.svg` | 평면도에 카메라 자리와 화각(주황 = 전체 컷, 보라 = 제품 컷) |

컷은 자동으로 정한다. 가구가 있는 방마다 **전체 컷 둘**(모서리·문간 후보 중 보이는 제품과 창이 많은
자리, 서로 60° 이상 다른 방향)과 리뷰할 제품마다 **제품 컷 하나**(정면이나 3/4 방향, 제품이 화면의 약 30%).
창이 보이는 전체 컷이 **대표 컷(★)** 이 된다.

출력 끝의 경고를 처리한다.

- `look 이 없는 품목` — 2단계로 돌아가 적는다. 비우면 상품명이 프롬프트에 들어가 모양이 틀어진다.
- `프롬프트가 DemoCut 한도(4,000자)에 가깝다` — `look` 을 줄인다. 프롬프트 길이도 견적에 들어간다.

스케치를 **반드시 열어 본다**(Read 로 PNG 를 본다). 이런 컷은 고친다.

- 앞 가구에 가려 주인공이 안 보인다, 벽만 보인다, 한 가구가 화면 절반을 덮는다
- 고치는 법: `photo.shots` 에 카메라를 직접 적는다(아래 형식). 자동 컷을 버리고 적은 컷만 쓴다.

### 4. 제품 보드를 만든다

```bash
python3 -I <스킬>/scripts/shots.py board photos/shots.json --images <2단계 디렉터리>/products
```

`photos/boards/<컷>.png` 에 그 컷에 보이는 제품 사진을 격자로 모은다(최대 6장, 프롬프트의 품목 번호 순서).

### 5. 사람에게 먼저 보여 준다

돈을 쓰기 전에 보여 준다: `shots.svg` 스크린샷(컷 자리), 대표 컷 스케치, 컷 목록(`shots.md` 의 제목과 보이는 품목),
대표 컷 프롬프트. 컷을 빼거나 바꾸라는 말이 있으면 3단계로 돌아간다.

### 6. DemoCut 으로 만든다

정확한 호출 순서·업로드·비용·검증은 [`references/democut-image.md`](references/democut-image.md) 를 읽고 따른다. 요지:

1. 프로젝트를 고른다(`democut_list_projects`). 새로 만들려면 묻고 만든다. **비율은 `photo.ratio` 와 같아야 한다**.
2. 레퍼런스를 자산으로 올린다(스케치·보드는 로컬 파일 → `democut_create_upload_url` + `curl -T`).
3. **대표 컷부터 한 장**: `democut_add_cut(mode=ai_image)` → `democut_estimate_cut_image` → 금액을 그대로 보여 주고 동의 →
   `democut_make_cut_image` → `democut_wait_jobs` → 그림을 받아 **눈으로 확인**(shots.md 의 확인 목록).
4. 대표 컷이 통과하면 그 그림을 나머지 컷의 레퍼런스 1번으로 넣고, 남은 컷의 견적을 표로 모아 동의를 받은 뒤 만든다.
5. 컷마다 확인 목록으로 검사한다. 틀린 컷은 원인을 프롬프트에 적어 다시 만든다(다시 견적·동의).

### 7. 보고

컷마다 그림(서명 URL 또는 받은 파일), 확인 목록 결과, 쓴 금액. 틀린 채 남긴 것이 있으면 무엇이 틀렸는지.

## house.json 에 더하는 것

room-set-planner 의 house.json 에 아래를 더한다. room-set-planner 는 이 키를 읽지 않으므로 검사에 영향이 없다.

```jsonc
"photo": {
  "concept": "natural",            // 프리셋 이름 또는 자유 영어 문장
  "ratio": "9:16",                 // 9:16 | 1:1 | 16:9 (DemoCut 프로젝트 비율)
  "walls": "white silk wallpaper", // 프리셋 값 덮어쓰기(선택): walls · floor · light · props · mood
  "ceiling": 2300,                 // 천장 높이 mm(기본 2300)
  "camera_height": 1200,           // 전체 컷 카메라 높이 mm(기본 1200)
  "shots": [                       // 선택. 적으면 자동 컷 대신 이것만 쓴다
    {"id": "wide-window", "room": "room", "x": 400, "y": 3600, "look_at": [3000, 300]},
    {"id": "hero-desk", "room": "room", "kind": "hero", "target": "desk",
     "x": 2400, "y": 1500, "h": 1300, "yaw": -135, "pitch": -25, "lens": 28}
  ]
},
"items": [{"id": "desk", "look": "…", "label_en": "desk"}]
```

- 카메라 `x`·`y` 는 도면 좌표(mm). 방향은 `look_at`(바라볼 점) 또는 `yaw`(도, 0 = 도면 오른쪽, 90 = 아래).
  `pitch` 는 도(아래가 −), `lens` 는 35mm 환산 초점거리(전체 컷 18, 제품 컷 28 이 기본).
- 직접 적은 컷의 첫 전체 컷(창이 보이면 그것)이 대표 컷이 된다.

## 하지 않는 것

- 사람·반려동물·글자를 넣지 않는다. 목록에 없는 가구·가전·러그·액자를 넣지 않는다(프롬프트가 막는다).
- 오늘의집 사진을 그대로 결과물로 쓰지 않는다. 제품 사진은 생김새 레퍼런스로만 쓴다.
- 확인 없이 다음 컷으로 넘어가지 않는다. 대표 컷이 틀리면 그 틀림이 모든 컷에 퍼진다.
