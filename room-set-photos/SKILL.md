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
2. **제품 보드** — 그 컷에 보이는 제품의 실제 사진을 모은다(한 장에 4칸까지, 다른 물건은 잘라 낸다). 생김새의 기준이다.
   제품마다 지킬 특징(`keep`)을 프롬프트에 적고, 틀린 제품은 편집(`fix`)으로 그것만 고친다
   ([`references/product-fidelity.md`](references/product-fidelity.md)).
3. **대표 컷** — 먼저 만든 넓은 컷 한 장을 나머지 컷의 레퍼런스 1번으로 넣는다. 벽지·바닥·창틀·빛·침구가 같아진다.
4. **프롬프트** — 같은 컨셉 문장, 품목마다 같은 `look` 문장, 화면 위치·거리·방향을 계산해서 적는다. 빛도 컷마다
   카메라 기준으로 디렉팅한다(어느 창에서 들어와 그림자가 어디로 지나). 질감은 사는 사람이 폰으로 찍은 사진을 겨눈다.

## 준비물

- room-set-planner 스킬(같은 스킬 디렉터리에 설치). `shots.py` 가 그 `planner.py` 로 도면을 계산한다
- 가구가 놓인 house.json(오류 0). 제품마다 `product.image`(대표 사진 https 주소)가 있어야 보드를 만든다.
  가구가 물리적으로 놓일 수 없는 자리(부딪침·책상보다 높은 의자를 책상 밑에·받침 밖)면 `plan` 이 멈춘다 — room-set-planner 로 고친다
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
- `plants` — 식물은 사용자가 원할 때만 넣는다. 원하면 `true`(작은 화분 한두 개) 또는 영어 문장. 없으면 프롬프트가 식물·꽃을 막는다.
- 그 밖의 키(`walls`·`floor`·`light`·`props`·`mood`·`ceiling`·`camera_height`·`shots`·`skip_rooms`·`rooms`)는
  아래 「house.json 에 더하는 것」.

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
- 크기나 다른 것과의 크기 관계(더 넓다, 둘레로 나온다, 선반처럼 튀어나온다)는 적지 않는다. 제품 사진은 고른 옵션과
  다른 크기를 찍었을 수 있다. 크기·여백은 치수와 [가구별 규칙](#가구별-규칙)이 정한다. 적으면 `plan` 이 경고한다.
- 리뷰할 제품과 모양이 독특한 제품에는 `items[].keep` 에 **그 제품을 그 제품이게 하는 특징**을 영어 구 하나로 적는다
  (부품의 자리·개수·비율·유광/무광). 품목 줄 끝에 `Keep exactly: …` 로 붙는다.
- 받은 사진을 보고 **보드에 넣을 사진**을 정한다. 다른 제품·조명·사람·글자가 함께 찍혔거나 여러 개가 쌓였으면
  `product.ref_image`(그 제품만 찍힌 상세 이미지 주소)와 `product.ref_crop`(`[왼, 위, 오른, 아래]` 0~1 비율)을 적는다.
  모델은 사진 속 다른 물건과 여백까지 옮긴다(2026-11-12 침대 사진의 다른 조명이 협탁 조명 자리에 그려졌다).
  대표 사진이 오염돼 있어도 **리뷰 제품은 보드에서 빼지 않는다**. 상세 이미지에는 제품 정보 그림, 흰 바탕 컷, 다른 물건 없이
  찍은 장면이 대개 있다. 빼면 그 제품은 글로만 그려지고 `plan` 이 경고한다(2026-11-13 침대를 뺐다가 사용자 지적).
  `product.ref: false` 는 리뷰하지 않는 소품에만 쓴다. 자세한 기준: [`references/product-fidelity.md`](references/product-fidelity.md).
  `ref_image` 를 적었으면 fetch 를 새 빈 디렉터리에 다시 돌린다.

```json
{"id": "desk", "look": "a simple white desk: thin white top with an exposed birch-plywood edge and slim round white metal legs, no drawers"}
{"id": "nightstand", "look": "a round light rubberwood stool",
 "keep": "four round legs outside the round top's rim, their ends rising just above it; a cross brace right under the top, none lower",
 "product": {"ref_image": "https://prs.ohou.se/…/descriptions/url/v1-267070310596608.jpg", "ref_crop": [0.21, 0.245, 0.745, 0.585]}}
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

컷은 자동으로 정한다. 가구가 있는 방(침실·주방·욕실·현관)마다 **전체 컷 한두 장**(모서리·문간 후보 중 보이는 제품과
창이 많은 자리, 서로 60° 이상 다른 방향)과 리뷰할 제품마다 **제품 컷 하나**(정면이나 3/4 방향, 제품이 화면의 약 30%).
큰 가구가 렌즈 0.75m 안을 막는 자리는 점수를 깎고, 둘째 전체 컷은 가까운 큰 가구가 화면 끝에 걸리지 않을 때만 만든다.
폭 2m 안팎의 주방·욕실은 둘째 자리가 대개 싱크대·변기에 렌즈를 붙인 그림이라 한 장만 나온다.
창이 보이는 전체 컷이 **대표 컷(★)** 이 된다. 다른 방의 첫 전체 컷은 대표 컷을 「같은 집 다른 방」 으로 받아 창틀·문·빛만
맞추고, 벽·바닥은 그 방 종류의 마감(욕실 타일 등, [`references/ohouse-look.md`](references/ohouse-look.md) 「방 종류별 마감」)을
따른다. 그 방의 나머지 컷은 그 방의 첫 전체 컷을 받는다. 트인 문간 너머로 다른 방이 화면의 3% 넘게 보이고 레퍼런스 칸이
남으면, 그 방의 첫 전체 컷을 3번(`role: neighbor`)으로 넣어 문간 너머를 그 사진대로 그리게 한다. 그래서 그 컷을 먼저 만든다
(2026-11-13 현관 컷이 문간 너머에 없는 상부장 주방을 지어 그렸다).

출력 끝의 경고를 처리한다.

- `look 이 없는 품목` — 2단계로 돌아가 적는다. 비우면 상품명이 프롬프트에 들어가 모양이 틀어진다.
- `프롬프트가 DemoCut 한도(4,000자)를 넘는다`·`가깝다` — 넘으면 DemoCut 이 거절한다. `look`·`keep`·`props` 를 줄인다.
  프롬프트 길이도 견적에 들어간다.
- `화면 … 끝에 잘려 걸린다` — 넓은 컷에서 카메라 가까이(1.5m 안) 있는 큰 가구가 절반 넘게 화면 밖이고 모서리만 걸렸다.
  생성 모델은 그 가구를 다른 가구보다 크고 높게 그린다. `photo.shots` 로 카메라를 옮겨 화면 밖으로 빼거나
  전체가 들어오게 한다. 그 가구는 제품 컷에서 보인다. 자동 컷은 이런 자리를 피한다.
- `look 에 크기 관계 말이 있다` — 그 말을 빼고 모양·색·재질만 남긴다(2단계).

스케치를 **반드시 열어 본다**(Read 로 PNG 를 본다). 이런 컷은 고친다.

- 앞 가구에 가려 주인공이 안 보인다, 벽만 보인다, 한 가구가 화면 절반을 덮는다
- 넓은 컷의 화면 끝에 가까운 큰 가구의 모서리만 걸린다(위 경고)
- 고치는 법: `photo.shots` 에 카메라를 직접 적는다(아래 형식). 컷을 적은 방은 그 방의 자동 컷 대신 적은 컷만 쓰고,
  적지 않은 방은 자동 컷을 그대로 쓴다(2026-11-13 전에는 방 하나만 적어도 주방·욕실·현관이 통째로 빠졌다).
  찍지 않을 방은 `photo.skip_rooms` 에 방 id 를 적는다.

### 4. 제품 보드를 만든다

```bash
python3 -I <스킬>/scripts/shots.py board photos/shots.json --images <2단계 디렉터리>/products
```

`photos/boards/<컷>.png` 에 그 컷에 보이는 제품 사진을 2×2 격자(1024px)로 모은다. `ref_crop` 이 있으면 먼저 자른다.
대표 컷은 보드 두 장(`<컷>.png`·`<컷>-2.png`, 8칸)까지, 나머지 컷은 한 장(4칸)이다 — 레퍼런스가 3장까지라서다.
넘치면 화면에 크게 보이는 제품부터 넣는다. **보드를 Read 로 열어** 다른 물건·글자가 남지 않았는지 본다.

### 5. 사람에게 먼저 보여 준다

돈을 쓰기 전에 보여 준다: `shots.svg` 스크린샷(컷 자리), 대표 컷 스케치, 컷 목록(`shots.md` 의 제목과 보이는 품목),
대표 컷 프롬프트. 컷을 빼거나 바꾸라는 말이 있으면 3단계로 돌아간다.

### 6. DemoCut 으로 만든다

정확한 호출 순서·업로드·비용·검증은 [`references/democut-image.md`](references/democut-image.md) 를 읽고 따른다. 요지:

1. 프로젝트를 고른다(`democut_list_projects`). 새로 만들려면 묻고 만든다. **비율은 `photo.ratio` 와 같아야 한다**.
   이미지 모델·품질은 `shots.json` 의 `model`·`quality`(house.json `photo.model`·`photo.quality`)를 견적과 제출에 같이 싣는다.
2. 레퍼런스를 자산으로 올린다(스케치·보드는 로컬 파일 → `democut_create_upload_url` + `curl -T`).
3. **대표 컷부터 한 장**: `democut_add_cut(mode=ai_image)` → `democut_estimate_cut_image` → 금액을 그대로 보여 주고 동의 →
   `democut_make_cut_image` → `democut_wait_jobs` → 그림을 받아 **눈으로 확인**(shots.md 의 확인 목록).
4. 대표 컷이 통과하면 그 그림을 나머지 컷의 레퍼런스 1번으로 넣고, 남은 컷의 견적을 표로 모아 동의를 받은 뒤 만든다.
   레퍼런스에 `role: neighbor` 가 있는 컷은 그 `shot` 을 먼저 만들어 확인하고, 그 그림을 넣은 뒤 만든다.
5. 컷마다 확인 목록으로 검사한다. 틀린 컷은 원인을 프롬프트에 적어 다시 만든다(다시 견적·동의).
   거의 맞고 **제품 한두 개만** 틀렸으면 다시 만들지 말고 `shots.py fix` 로 그 제품만 편집한다
   ([`references/product-fidelity.md`](references/product-fidelity.md) 「틀린 제품만 고치기」).
   받침 위 작은 소품이 크게 나오면 다시 만들어도 같다. 그림에서 재서 `fix --scale` 로 줄인다.
   대표 컷을 만든 뒤 집에서 작은 것(러그·침구)만 바꿨으면 그것도 `fix --change` 로 같은 편집에 싣는다.

### 7. 보고

컷마다 그림(서명 URL 또는 받은 파일), 확인 목록 결과, 쓴 금액. 틀린 채 남긴 것이 있으면 무엇이 틀렸는지.

## house.json 에 더하는 것

room-set-planner 의 house.json 에 아래를 더한다. room-set-planner 는 이 키를 읽지 않으므로 검사에 영향이 없다.

```jsonc
"photo": {
  "concept": "natural",            // 프리셋 이름 또는 자유 영어 문장
  "ratio": "9:16",                 // 9:16 | 1:1 | 16:9 (DemoCut 프로젝트 비율)
  "walls": "white silk wallpaper", // 프리셋 값 덮어쓰기(선택): walls · floor · light · props · mood
  "plants": false,                 // 식물. 요청이 있을 때만 true 또는 영어 문장(기본: 넣지 않는다)
  "curtains": "sheer curtains",    // 창에 거는 것(기본값). 암막이면 "beige blackout curtains pulled open"
  "view": "facing …",              // 창밖(선택). 없으면 집 유형으로 정한다: 원룸은 건너편 빌라, 그 밖은 적지 않는다.
                                   //   커튼을 친 방이면 false 로 두고 curtains 에 "… drawn closed" 를 적는다
  "model": "gpt-image-2.6-sunburst", // 이미지 모델(선택. 없으면 DemoCut 기본). democut_get_options 가 고를 수 있는 값을 말한다
  "quality": "medium",             // 품질(기본 medium)
  "ceiling": 2300,                 // 천장 높이 mm(기본 2300)
  "camera_height": 1200,           // 전체 컷 카메라 높이 mm(기본 1200)
  "shots": [                       // 선택. 적은 방은 그 방의 자동 컷 대신 이것만 쓴다(다른 방은 자동)
    {"id": "wide-window", "room": "room", "x": 400, "y": 3600, "look_at": [3000, 300]},
    {"id": "hero-desk", "room": "room", "kind": "hero", "target": "desk",
     "x": 2400, "y": 1500, "h": 1300, "yaw": -135, "pitch": -25, "lens": 28}
  ],
  "skip_rooms": ["entry"],         // 선택. 찍지 않을 방 id(없는 id 면 plan 이 멈춘다)
  "rooms": {                       // 선택. 방 종류(kind) 또는 방 id 별 마감 덮어쓰기: walls · floor · details · props
    "bathroom": {"floor": "dark gray hexagon mosaic floor tiles sloping to a floor drain"},
    "kitchen": {"props": "a cutting board and a kettle on the counter"}
  }
},
"items": [{"id": "desk", "look": "…", "label_en": "desk",
           "keep": "…",                                              // 지킬 특징(선택)
           "product": {"ref_image": "https://…", "ref_crop": [0, 0, 1, 0.5], "ref": true}},  // 보드 사진(선택)
          {"id": "bed", "look": "…", "mattress": {"w": 1100, "d": 2000},   // 선택. 아래 「가구별 규칙」
           "rules": [{"prompt": "…", "check": "…"}]}]
```

- 카메라 `x`·`y` 는 도면 좌표(mm). 방향은 `look_at`(바라볼 점) 또는 `yaw`(도, 0 = 도면 오른쪽, 90 = 아래).
  `pitch` 는 도(아래가 −), `lens` 는 35mm 환산 초점거리(전체 컷 18, 제품 컷 28 이 기본).
- 직접 적은 컷의 첫 전체 컷(창이 보이면 그것)이 대표 컷이 된다.

## 가구별 규칙

가구가 화면에 들어가면 그 가구에 걸린 규칙이 프롬프트의 그 품목 줄·`Avoid:` 줄·확인 목록에 붙는다. 규칙은
[`references/furniture-rules.json`](references/furniture-rules.json) 에 모여 있다. 사진에서 가구가 물리적으로 틀리게
나오면(매트리스가 프레임 밖으로 나왔다, 의자가 책상 밑에 들어갔다) 그 가구의 규칙을 고치거나 더하고 `plan` 부터 다시 돌린다.
프롬프트 문장을 손으로 고치지 않는다. 다음 컷·다음 방에서 같은 틀림이 다시 나온다.

```json
{"id": "bed-mattress", "match": {"category": "bed"},
 "prompt": "Made up with a {mattress} cm mattress {mattress_fit}; bedding top {top} cm high.",
 "avoid": "a mattress longer or wider than its bed frame",
 "check": "매트리스({mattress}cm)가 프레임 위에 머리부터 발치까지 놓였다 — {mattress_fit_ko}",
 "why": "2026-11-11 받침이 머리 쪽 벽까지 오지 않아 매트리스가 떴다 …"}
```

| 칸 | 뜻 |
|---|---|
| `match` | 어느 품목에 거나. 적은 조건이 모두 맞아야 건다. `category`(이름 하나 또는 목록) · `on: true`(다른 품목 위에 놓인 것) · `with`(짝과의 관계: `under` 짝 밑에 들어감 · `taller` 짝보다 높아 앞에 빠짐 · `beside` 곁) · `near: true`(이 컷에 보이는 다른 바닥 가구가 10cm 안에 있는 것. 둘 중 바닥 면이 작은 쪽) |
| `prompt` | 그 품목 줄 끝에 붙는 영어 문장 |
| `avoid` | 그 품목이 보이는 컷의 `Avoid:` 줄에 더하는 영어 구 |
| `check` | 확인 목록에 「품목 — 문장」 으로 붙는 한국어 |
| `why` | 규칙이 생긴 날짜와 틀렸던 그림. 프롬프트에 들어가지 않는다. 나중에 규칙을 지울지 판단하는 근거다 |

글 안의 `{이름}` 은 `shots.py` 가 house.json 치수로 계산해 넣는다(길이는 cm).

| 변수 | 어느 품목에 | 값 |
|---|---|---|
| `label` · `label_ko` · `w` · `d` · `h` · `top` | 모든 품목 | 영어·한국어 이름, 치수, 바닥에서 가장 높은 곳 |
| `support` · `support_ko` · `support_size` · `on_fit` · `on_fit_ko` | `on` 이 있는 품목 | 받침 이름과 윗면 크기, 받침 가장자리 안에 있는지(`inside its edges`) 몇 cm 나오는지 |
| `on_scale` · `on_scale_ko` | `on` 이 있는 품목 | 받침과의 비율(`about 1/4 that top's width and 1/5 the nightstand's height`). 납작한 것은 폭만 |
| `partner` · `partner_ko` · `partner_top` | `with` 가 있는 품목 | 짝 이름과 높이 |
| `near` · `near_ko` · `near_gap` · `near_fit` · `near_fit_ko` | `near` 가 맞는 품목 | 가장 가까운 곁 가구 이름과 사이(cm). `near_fit` 은 10cm 안의 곁 가구를 모두 적은 문장이다(`Bare floor shows between it and the desk (5 cm gap) and the bed (7 cm gap)` · 붙었으면 `It touches the … without overlapping`) |
| `mattress` · `mattress_fit` · `mattress_fit_ko` | 침대 | 프레임에 들어가는 가장 큰 표준 매트리스(폭 S 100 · SS 110 · D 140 · Q 150 · K 160, 길이 200)와 프레임 위에 놓인 모양 |

- 그 품목에 없는 변수를 쓰면 `plan` 이 멈춘다. `match` 로 그 관계가 있는 품목에만 건다.
- 제품 하나에만 걸 규칙은 house.json 의 그 품목에 `"rules": [{…}]` 로 적는다(모양은 같고 `match` 는 생략할 수 있다).
- 매트리스가 표준 크기가 아니면 그 침대에 `"mattress": {"w": 1000, "d": 1950}` 을 적는다.
- 덩어리 스케치의 모양(침대 = 프레임 + 매트리스, 책상 = 상판 + 다리)은 `shots.py` 의 `item_boxes` 가 정한다.

## 하지 않는 것

- 사람·반려동물·글자를 넣지 않는다. 목록에 없는 가구·가전·러그·액자를 넣지 않는다(프롬프트가 막는다).
- 식물·꽃을 요청 없이 넣지 않는다. 가구를 물리적으로 불가능한 자리(책상 밑 사무용 의자, 떠 있거나 겹친 가구,
  프레임 밖으로 나온 매트리스)에 그리게 두지 않는다. 틀리면 그 가구의 규칙을 고친다.
- 오늘의집 사진을 그대로 결과물로 쓰지 않는다. 제품 사진은 생김새 레퍼런스로만 쓴다.
- 확인 없이 다음 컷으로 넘어가지 않는다. 대표 컷이 틀리면 그 틀림이 모든 컷에 퍼진다.
