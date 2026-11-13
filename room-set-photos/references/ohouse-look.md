# 오늘의집 사진의 느낌

오늘의집 「집들이」 글의 사진은 광고 렌더가 아니라 **사는 사람이 자기 집을 잘 찍은 사진**이다. 생성 모델이
그쪽으로 가도록 `shots.py` 가 모든 프롬프트 맨 앞에 같은 문장(`COMMON_LOOK`)을 넣는다. 이 문서는 그 문장이
무엇을 겨누는지와, 컨셉 프리셋을 고르는 법을 적는다.

## 공통으로 겨누는 것

| 항목 | 겨누는 모습 | 피하는 모습 |
|---|---|---|
| 빛 | 창으로 들어오는 크림톤 낮빛, 퍼진 빛, 부드러운 그림자 | 바닥에 떨어진 선명한 햇빛 무늬·빛줄기, 스튜디오 조명, 어두운 밤 |
| 색·질감 | 폰으로 찍은 사진의 질감: 차분한 색, 낮은 대비, 약한 센서 노이즈 | 채도 과장, HDR 광, 매끈하게 반짝이는 표면, 필터 낀 색 |
| 정돈 | 깔끔하지만 사는 흔적(접힌 담요, 책 몇 권) | 텅 빈 쇼룸, 어지러운 방, 요청하지 않은 식물·꽃 |
| 물리 | 가구가 바닥(또는 받침) 위에 서 있고 서로 뚫지 않는다. 등받이 높은 의자는 책상 앞에 빠져 있다. 놓인 것은 받침 가장자리 안에 있다 | 책상 밑에 밀어 넣은 사무용 의자, 떠 있거나 겹친 가구, 프레임 밖으로 나온 매트리스 |
| 카메라 | 가슴 높이(약 1.2m), 수직선이 서 있는 사진, 세로 사진 | 어안 왜곡, 높은 부감, 극단적 광각 |
| 한국 집 디테일 | 흰 PVC 이중창 샷시, 흰 걸레받이, 실크 벽지, 원형 평판 LED 천장등, 강마루·장판 | 서양식 몰딩·벽난로·카펫 바닥 |
| 창밖 | 집 유형에 맞는 바깥. 원룸은 몇 미터 앞 건너편 빌라의 벽과 창, 아니면 커튼을 친 창 | 원룸 창밖의 고층 아파트 단지 |
| 사람 | 없다 | 사람·반려동물·글자·로고 |

「좋은 카메라로 찍은 밝은 자연광 사진」 이라고 쓰면 생성 모델은 바닥에 햇빛 무늬를 깔고 색과 표면을 매끈하게 다듬는다.
그 그림은 한눈에 AI 가 만든 티가 난다(2026-11-11 실제 생성에서 사용자가 지적). 그래서 공통 문장은 「사는 사람이 폰으로 찍은
사진」 쪽 질감을 겨누고, `Avoid:` 줄이 HDR 광·과한 채도·선명한 햇빛 무늬를 막는다.

창밖을 적지 않으면 모델은 한국 집 창밖에 아파트 단지를 그린다. 원룸은 보통 3~4층 빌라에 있어서 그 창밖은 맞지 않는다
(2026-11-13 사용자 지적). 그래서 `shots.py` 는 `type: "oneroom"` 이면 방을 「빌라 원룸」 으로 적고 창밖에 건너편 빌라를 넣고
`Avoid:` 에 아파트 단지를 넣는다. 커튼을 쳐서 바깥을 가리려면 `photo.view` 를 `false` 로 두고 `photo.curtains` 에 친 커튼을 적는다.

**식물은 요청할 때만 넣는다.** 「화분 한두 개」 라고만 써도 모델은 서랍장·협탁·창가마다 화분을 늘어놓는다(2026-11-11 사용자 지적).
프리셋 소품에는 식물이 없고 `Avoid:` 줄이 식물·꽃을 막는다. 사용자가 식물을 원하면 `photo.plants` 를 켠다(`true` 면 작은 화분
한두 개, 문장이면 그 문장).

**가구는 물리적으로 놓일 수 있는 자리에만 그린다.** 모델은 책상이 보이면 의자를 책상 밑에 밀어 넣어 그리는데, 등받이가 상판보다
높은 의자는 들어가지 않는다(같은 날 사용자 지적). 이런 가구별 요령은 [`furniture-rules.json`](furniture-rules.json) 의
규칙으로 둔다(형식은 SKILL.md 「가구별 규칙」). 그 가구가 화면에 들어가면 규칙이 높이·크기를 숫자로 비교한 문장을 붙인다:
짝보다 높은 의자는 「Pulled out in front of the desk, not under it (120 cm tall vs the 74 cm desk).」, 다른 품목 위에 놓인
것은 「It stands on the kitchen counter (140x60 cm top), inside its edges.」, 침대는 「Made up with a 110x200 cm mattress lying
flush on the frame from head to foot」, 10cm 안에 다른 가구가 선 것은 「Bare floor shows between
it and the bed (7 cm gap).」. 짝은 보이는데 자기는 화면 밖이면 「Its chair is out of
frame: draw no chair at it.」 를 붙인다(한 픽셀도 그려지지 않을 때만. 짝에 가려진 것은 아래 붙박이). 받침은 보이는데 그 위 소품이 화면 밖이면 「Its bedside lamp stands on its top just
out of frame past the right edge: show no more of the nightstand than the sketch does; if more of its top shows, the bedside
lamp stands there too.」 를 붙인다. 짝과 달리 소품은 그 받침 위에 있으므로 「그리지 말라」 고 쓰지 않는다. 2026-11-13
끝에 조금 걸친 협탁을 모델이 거의 다 그리고 그 위 조명은 빼 맨 윗면이 나왔다. 배치 자체가 불가능하면(부딪침·짝보다 높은데 밑에 들어감·받침 밖) `plan` 이 멈추고
room-set-planner 로 돌려보낸다.

짝의 바닥 면 안에 든 붙박이(`with: counter` 로 싱크대 밑에 넣은 세탁기)는 화면 안이어도 짝의 상자에 가려 목록에 오르지
않는다. 그대로 두면 `Avoid:` 의 「목록 밖 가전」 때문에 그 자리에 수납장 문이 그려지므로, 짝의 줄에 「Built into it at its
right end: a white front-loading washing machine …, its front flush with the kitchen counter's front.」 를 붙인다. 2026-11-13
전에는 이 세탁기에 「Its washer is out of frame: draw no washer at it.」 가 붙어 싱크대 look 과 부딪쳤다.

**크기는 치수가, 생김새는 제품 사진이 정한다.** 오늘의집 대표 사진은 고른 옵션과 다른 크기를 찍었을 때가 많다. 2026-11-11
SS 침대 프레임(110×204cm, SS 매트리스와 거의 같은 크기)의 대표 사진은 더 큰 받침에 매트리스를 올려 옆으로 선반 같은 여백이
있었다. 그 여백을 look 에 「둘레로 나온 넓은 받침」 이라고 적었더니, 모델이 치수와 맞추려고 받침을 줄여 매트리스 머리 쪽이
떠 버렸다(사용자 지적). 그래서 look 에는 크기 관계를 적지 않고(`plan` 이 경고한다), 보드 문장은 「크기는 숫자에서만 가져오라」
고 적는다. 받침과 놓인 것의 크기 관계는 가구별 규칙이 치수로 계산해 적는다.

## 방 종류별 마감

컨셉 프리셋의 벽·바닥·소품은 침실·거실에 맞춘 값이다. 원룸형 집의 주방·욕실·현관에 그대로 쓰면 욕실에 강마루와 린넨 침구,
현관에 니트 담요가 들어간다(2026-11-13 처음 다른 방을 찍으며 확인). 그래서 `shots.py` 는 방의 `kind` 로 마감을 바꾼다.

| 방 종류 | 벽 · 바닥 | 디테일 · 소품 |
|---|---|---|
| `bedroom`·`living`·`dressroom` | 프리셋 그대로 | 한국 집 디테일(샷시·걸레받이·실크 벽지·원형 LED) · 프리셋 소품 |
| `kitchen` | 프리셋 벽 + 싱크대 뒤 흰 타일 · 프리셋 바닥 | 같은 디테일 · 건조대의 그릇, 흰 전기포트, 접은 행주 |
| `bathroom` | 바닥부터 천장까지 흰 유광 타일 · 배수구로 기운 연회색 논슬립 타일 | 타일 벽·바닥, 배수구, 문턱, 사각 평판 LED · 벽 고리의 흰 수건, 세면대 옆 디스펜서·칫솔컵 |
| `entrance` | 프리셋 벽 · 옆 방보다 한 단 낮은 회색 포세린 타일 | 같은 디테일 · 바닥 타일 위 흰 운동화 한 켤레 |

값은 `photo.rooms` 에 방 종류나 방 id 를 키로 덮어쓴다(`walls`·`floor`·`details`·`props`). 방 이름은 원룸이면
「the bathroom of a one-room studio in a 4-story Korean villa」 처럼 그 집 안의 공간으로 적는다. 대표 컷(침실)을 레퍼런스로
받을 때 벽이나 바닥이 다르면 「use the same window frames, door and trim colors and light; the floor follows the text above,
not that photo」 처럼 같은 것만 맞추라고 적는다. 모델은 「같은 집」 이라는 말만 들으면 침실의 강마루를 욕실에 깐다.

## 문간 너머

트인 문간(문짝 없는 개구부)을 비워 두면 모델은 그 너머 방을 모르는 채로 지어 그린다. 같은 집의 그 방 컷과 다른 가구·마감이
나온다(2026-11-13 현관 컷의 문간 너머에 그 집 주방에 없는 상부장이 그려졌다). 그래서 `shots.py` 는 문간 자리에 너머 방을 같은
카메라로 그려 넣는다. 벽 두께 면, 너머 방의 벽·바닥, 그 방 가구의 상자다. 프롬프트에는 문간마다 그 방의 벽·바닥 마감(그 방
종류의 값, 위 「방 종류별 마감」)을 적고, 보이는 가구를 이 방 가구에 이어지는 번호로 적는다.

```text
Through the open doorway on the right wall (far right) is the kitchen (walls: …; floor: …). Draw only these there, at true scale:
3. Fridge (purple box): a small white two-door fridge … 48x50x85 cm. Lower far right, foreground; front faces camera.
```

- 너머 방 상자는 이 방 상자와 겹치지 않는 색을 받는다. `keep` 은 적지 않는다. 제품 생김새는 그 방 컷이 맡는다.
- 너머가 화면의 1% 안 되는 가는 띠면 스케치에만 그리고 글로 적지 않는다. 가구가 없는 방이면 「No furniture shows there」 다.
- 스케치 범례는 실제로 칠해진 색만 적는다. 너머 방이 그려진 문간은 짙은 회색이 아니다.
- 프롬프트가 한도(4,000자)를 넘으면 너머 가구의 생김새를 빼고 크기·자리만 적는다(경고가 나온다).
- 너머 방이 화면의 3% 넘게 보이고, 그 방의 첫 전체 컷이 먼저 만들어지고, 레퍼런스 칸이 남으면 그 그림을 `role: neighbor`
  로 넣는다. 소품과 제품 생김새까지 같아진다. 칸은 제품 보드가 먼저 쓴다. `shots.md` 는 그 컷을 앞 번호로 당기고, 두 방이
  서로 들여다보면 기본 순서(대표 컷 → 전체 컷 → 제품 컷)에서 앞선 컷이 먼저이고 그 컷은 글과 스케치로만 받는다.
- 문(갈색)은 닫힌 것으로 그리므로 너머를 그리지 않는다.

## 소품은 적은 것만

`Styling:` 줄은 「{소품}; nothing else on any surface.」 로 끝나고, 소품이 없는 방은 「Styling: nothing on any surface.」 다.
`Avoid:` 줄은 「any object that is not listed」 로 끝난다. 소품의 종류만 적으면(전에 쓰던 「Small soft props only」) 모델은
그런 소품을 더 지어 받침 위에 올린다(2026-11-13 수납장 위에 목록에 없는 켜진 조명과 상자가 생겼다). 금지할 물건을 하나씩
이름으로 더하는 대신 「적은 것 말고는 없다」 를 모든 방에 같은 문장으로 건다. 방마다 놓을 소품은
`photo.rooms.<종류 또는 방 id>.props` 로 바꾼다.

## 빛 디렉팅

빛은 두 겹으로 적는다. 프롬프트의 `Light:` 줄이 둘을 잇는다.

- **빛의 질** — 색·시간대·세기. 컨셉 프리셋의 `light` 값이다(`photo.light` 로 바꾼다).
- **빛의 방향** — `shots.py` 가 컷마다 카메라 기준으로 계산한다. 방에서 가장 넓은 창이 유일한 빛이고, 그 창이 화면의 어느
  벽(화면 밖이면 그렇다고)에 있는지, 빛이 화면의 어느 쪽으로 퍼지는지, 그래서 가구의 어느 면이 밝고 그림자가 어디로 지는지를
  적는다. 천장등은 끈다. 예: `Daylight comes only from the window on the far-left wall and travels to the right and toward
  the camera: furniture sides facing the window are brighter, soft shadows fall to the right and toward the camera. The
  ceiling light is off.`

방향을 적지 않으면 생성 모델은 컷마다 빛을 다른 데서 끌어오고(대표 컷과 제품 컷의 그림자가 반대로 진다), 창 없는 벽 쪽에서
햇빛을 비추기도 한다. 창이 없는 방(욕실 등)은 천장등의 고른 빛과 문간으로 새는 낮빛으로 적는다. `shots.md` 의 확인 목록에
「빛 — 창(정면 왼쪽 벽)에서 빛이 들어와 그림자가 오른쪽·카메라 쪽으로 진다」 처럼 나오니 그림의 그림자 방향과 맞춰 본다.

세로 사진(9:16 프로젝트 → 2:3 그림)에서 천장이 화면 위를 덮지 않게, 전체 컷 스케치는 수평선을 화면 위쪽
38% 높이에 둔다(시프트 렌즈처럼 수직선은 세운 채 바닥을 더 담는다).

## 컨셉 프리셋

`photo.concept` 값. 프리셋은 분위기(`mood`)·벽(`walls`)·바닥(`floor`)·빛(`light`)·소품(`props`) 다섯 값을 정한다.
값 하나만 바꾸려면 `photo` 에 그 키를 적는다(예: `"floor": "gray tile-look vinyl flooring"`). 소품에 식물은 없다(위 「식물」).

| 값 | 이름 | 이럴 때 | 벽 · 바닥 | 빛 · 소품 |
|---|---|---|---|---|
| `natural` | 내추럴 우드(기본) | 원목·화이트 제품이 많다. 숏폼 자취방 | 흰 실크 벽지 · 밝은 오크 강마루 | 크림톤 낮빛(바닥에 직사광 없음) · 흰·베이지 린넨, 니트 담요, 책 |
| `minimal` | 화이트 미니멀 | 흰 가구 위주, 물건이 적다 | 흰 벽지 · 화이트워시 오크 | 고른 낮빛 · 흰 침구, 책 몇 권 |
| `modern` | 모던 그레이 | 회색·검정 금속 제품 | 따뜻한 연회색 벽지 · 회베이지 오크 | 흐린 날 고른 빛 · 차콜 침구, 검정 소품 |
| `midcentury` | 미드센추리 빈티지 | 월넛·머스터드·라운드 디자인 | 아이보리 벽지 · 중간 갈색 오크 | 늦은 오후 햇빛 · 머스터드·올리브 침구, 빈 도자기, LP |
| `cozy` | 아늑한 웜톤 | 크림·베이지 패브릭이 많다 | 크림 벽지 · 허니 오크 | 이른 저녁 노을빛 + 실내등 · 부클레 쿠션, 캔들 |

고르는 기준: **제품 색이 먼저다.** 고른 제품이 하얗고 원목이면 `natural`, 회색·검정이면 `modern`. 사용자가
말한 분위기와 제품 색이 부딪히면(예: 「빈티지」인데 제품이 전부 흰 하이그로시) 그 사실을 말하고 고르게 한다.
자유 문장도 된다: `"concept": "Japandi style: pale wood, off-white, black accents, very calm"` 이면 분위기에
그 문장을 쓰고 나머지는 `natural` 값을 쓴다.

## look 문장을 쓰는 법

생성 모델에게 제품을 설명하는 유일한 글이다. 보드 사진과 함께 간다.

- 영어 한 문장, 120자 안팎. 모양 → 색 → 재질 → 눈에 띄는 부분 순서.
- 사진에 보이는 것만. 치수는 쓰지 않는다(스크립트가 붙인다). 브랜드·가격·「프리미엄」 같은 말은 쓰지 않는다.
- 크기 관계(wider than, sticks out, ledge, overhangs)도 쓰지 않는다. 사진이 다른 크기 옵션일 수 있다(위 「크기는 치수가」).
- 같은 제품이 여러 컷에 나오므로 한 번 적은 문장을 바꾸지 않는다. 바꾸면 컷마다 제품이 달라진다.

| 나쁜 예 | 좋은 예 |
|---|---|
| `포커스 컴퓨터 책상 1200` | `a simple white desk: thin white top with an exposed birch-plywood edge and slim round white metal legs, no drawers` |
| `nice modern chair` | `a high-back office chair with a gray mesh back and headrest, dark gray seat, white frame and white five-star base on casters` |
| `wardrobe 80cm` | `a compact solid-rubberwood cabinet in honey-colored wood: two doors on top, three wide drawers below, on a low wooden base` |
