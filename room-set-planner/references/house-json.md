# house.json — 집 구조와 가구 배치의 원본

평면도·검사·인벤토리는 전부 이 파일에서 나온다. 손으로 고치고 `planner.py check` 로 확인한다.

## 좌표

- 단위는 전부 **mm**.
- 원점은 도면 왼쪽 위, x 는 오른쪽, y 는 아래로 커진다.
- 벽 이름 `n` `s` `w` `e` 는 방위가 아니라 **도면의 위·아래·왼·오른쪽**이다.
- 방은 실내 사각형 `rect: [x, y, w, d]` 이다. 이웃한 방 사이는 벽 두께(`wall`, 기본 100)만큼 띄운다.
  50mm 보다 가까우면 검사가 「벽 두께가 없다」 오류를 낸다.
- `offset` 은 그 벽의 작은 좌표 끝에서 잰다: 위·아래 벽은 왼쪽 끝, 왼쪽·오른쪽 벽은 위쪽 끝.

## 맨 위

```json
{
  "version": 1,
  "name": "EP03 작업실",
  "type": "room",
  "units": "mm",
  "wall": 100,
  "budget": 1500000,
  "household": "1인, 재택근무",
  "meta": {"source": "template:room", "notes": ["창 자리를 받지 않아 위쪽 벽 가운데에 두었다"]},
  "rooms": [], "openings": [], "items": []
}
```

| 칸 | 뜻 |
|---|---|
| `type` | `room` 방 한 칸(촬영 세트·에피소드별 방, 현관 없음) · `oneroom` 원룸형(거실 없음) · `apartment` 아파트형(거실 있음) |
| `budget` | 원. 인벤토리 합계와 비교한다(선택) |
| `meta.notes` | 가정한 것·사용자에게 들은 것. HTML 「가정·메모」 에 나온다 |

## rooms

```json
{"id": "room", "kind": "bedroom", "name": "작업실", "rect": [0, 0, 3000, 3400]}
```

`kind`: `bedroom` 침실 · `living` 거실 · `kitchen` 주방 · `bathroom` 화장실 · `entrance` 현관 · `hall` 복도 ·
`dressroom` 드레스룸 · `utility` 다용도실. 목록에 없는 방(서재·작업실·홈카페)은 가장 가까운 `kind` 를 쓰고 `name` 으로 이름을 단다
(`kind` 는 바닥 색과 문 검사에 쓰인다. 화장실·현관이 아닌 방에 `bathroom`·`entrance` 를 고르지 않는다).

## openings — 문·개구부·창

```json
{"id": "d_room", "type": "door", "room": "room", "wall": "s", "offset": 1950, "width": 900,
 "to": "outside", "swing": "in", "hinge": "end"}
{"id": "w1", "type": "window", "room": "room", "wall": "n", "offset": "center", "width": 1800, "sill": 900}
```

| 칸 | 뜻 |
|---|---|
| `type` | `door` 여닫이 · `sliding` 미닫이 · `opening` 문 없는 개구부 · `window` 창 |
| `room` · `wall` · `offset` · `width` | 어느 방의 어느 벽, 어디서부터 얼마나. `offset` 에 `"center"` 를 줄 수 있다 |
| `to` | 반대편 방 id 또는 `"outside"`. 창에는 쓰지 않는다. 두 방의 마주 보는 벽이 문 폭만큼 겹쳐야 한다 |
| `swing` | 여닫이만. `in` 은 `room` 쪽으로, `out` 은 `to` 쪽으로 열린다 |
| `hinge` | 여닫이만. `start` 는 offset 쪽 끝, `end` 는 반대쪽 끝에 경첩 |
| `sill` | 창턱 높이. 이보다 높은 가구가 창 앞 300 안에 있으면 주의 |

바깥으로 나가는 문(`to: "outside"`)이 하나는 있어야 한다. 동선 검사가 그 문 밖에서 시작한다.

## items — 가구·가전·소품

```json
{
  "id": "bed", "room": "room", "category": "bed", "name": "큐브 패브릭 침대프레임 K",
  "size": {"w": 1620, "d": 2150, "h": 880},
  "place": {"wall": "w", "offset": 200, "gap": 0},
  "product": {"url": "...", "title": "...", "brand": "...", "option": "...", "price": 1270000,
              "rating": 5.0, "review_count": 6, "image": "...", "key_points": ["..."],
              "dims_source": "detail_image", "dims_note": "...", "checked": "2026-11-09"}
}
```

### size

위에서 내려다본 바깥 치수. `w` 는 정면 폭, `d` 는 깊이, `h` 는 높이. 셋 다 적는다(`h` 는 창 가림 검사에 쓰인다).

침대의 정면은 발치다. `w` 는 침대 폭(슈퍼싱글이면 1100 남짓), `d` 는 길이(2000 남짓)이고, `place.wall` 은 **머리를 붙일 벽**이다.

```json
{"id": "bed", "category": "bed", "size": {"w": 1120, "d": 2150, "h": 900}, "place": {"wall": "w", "offset": 0, "gap": 100}}
```

이 침대는 머리가 왼쪽 벽에 붙고 발치가 오른쪽을 본다. 내려다본 크기는 가로 2150 × 세로 1120 이다.

### place — 둘 중 하나

**벽에 등을 붙인다** (대부분):

```json
{"wall": "w", "offset": 200, "gap": 0}
{"wall": "n", "offset_end": 0}
{"wall": "e", "offset": "center"}
```

- 가구의 등이 `wall` 에 붙고 정면은 반대쪽을 본다(`wall: "w"` 이면 정면이 오른쪽).
- `offset` 은 벽 시작점에서 가구 모서리까지, `offset_end` 는 벽 끝에서, `"center"` 는 가운데.
- `gap` 은 벽에서 띄우는 거리(침대 100 정도 띄우면 침구 정리가 쉽다).

**자유 배치** (소파를 방 가운데에, 식탁 등):

```json
{"x": 1200, "y": 1500, "facing": "s"}
```

`x`, `y` 는 그 방의 왼쪽 위 모서리에서 가구 왼쪽 위 모서리까지. 내려다본 크기는 `facing` 이 `n`/`s` 면 w×d, `e`/`w` 면 d×w 다.

### 품목 성격

| 칸 | 뜻 |
|---|---|
| `category` | [clearances.md](clearances.md) 의 품목. 비울 자리와 벽 붙임이 여기서 정해진다 |
| `label` | 도면에 쓸 짧은 이름(없으면 품목 이름) |
| `qty` | 개수(가격에 곱한다) |
| `on` | 올려 두는 가구 id(TV 를 TV장 위에). 바닥 장애물이 아니다 |
| `with` | 딸린 가구 id(책상 의자, 식탁 의자). 바닥 장애물로 치지 않고 자리도 요구하지 않는다 |
| `z` | 바닥에서 띄운 높이. 1200 이상이면 벽걸이로 보고 장애물에서 뺀다 |
| `door` | 옷장만. `"sliding"` 이면 앞 여유를 미닫이 값으로 잰다 |
| `seat_sides` | 식탁만. 의자를 놓는 변 목록(예: `["n", "s"]`) |
| `clearance` | 품목 하나만 여유 값을 바꾼다. `{"front": [min, rec]}` · `{"side": [...]}` · `{"seat": [...]}` |
| `owned` | 사용자가 이미 가진 가구. 제품 링크가 없어도 되고 가격 합계에서 빠진다. 치수는 `product.dims_source: "user"` |
| `placeholder` | 제품 미정. 자리만 잡은 가상 크기라 주의가 뜬다. 리뷰 카드에 안 나온다 |

### product — 오늘의집 제품

실측 칸(`dims_source`, `dims_note`)과 리뷰 칸(`title` … `checked`)은 [ohouse-sizing.md](ohouse-sizing.md) 5절.
`url` 이 없거나 `dims_source` 가 비면 검사가 오류를 낸다(`owned`·`placeholder` 는 예외).

## 평면 틀 입력(spec) — `planner.py shell`

**방 한 칸** (촬영 세트):

```json
{"type": "room", "name": "EP03 작업실",
 "rooms": [{"kind": "bedroom", "name": "작업실", "w": 3000, "d": 3400}],
 "door": {"wall": "s", "offset": 1950, "width": 900, "swing": "in", "hinge": "end"},
 "windows": [{"wall": "n", "offset": "center", "width": 1800, "sill": 900}]}
```

`door`·`windows` 를 빼면 문은 아래쪽 벽 오른쪽 끝(안으로 열림), 창은 위쪽 벽 가운데 60% 폭이다. 가정은 `meta.notes` 에 남는다.

**원룸형 · 아파트형**:

```json
{"type": "oneroom", "name": "자취방",
 "rooms": [{"kind": "bedroom", "w": 3200, "d": 4000},
           {"kind": "bathroom", "w": 1400, "d": 2000},
           {"kind": "entrance", "w": 1000, "d": 1200}]}
```

- 침실은 하나 이상 있어야 한다. 현관·화장실·주방(아파트형은 거실도)이 없으면 기본 크기로 넣고 메모를 남긴다.
- 원룸형 침실 1개: 위에 방, 아래 줄에 [화장실 | 주방 복도 | 현관]. 가로가 좁으면 현관을 주방 아래에 둔다.
- 아파트형·투룸: 아래 줄 [작은 방 | 거실(또는 주방 겸 거실) | 안방], 그 위 복도 띠, 위 줄에 주방·현관·화장실·나머지 방.

틀은 출발점이다. 실제 집과 다르면 rooms·openings 를 손으로 고친다.

## 사용자가 도면을 줄 때

도면 이미지나 치수를 받으면 틀을 쓰지 않고 house.json 을 직접 쓴다.

1. 방마다 실내 치수를 읽어 `rect` 로 옮긴다. 도면 치수가 벽 중심선 기준이면 벽 두께 절반씩 뺀다.
2. 이웃한 방 사이를 `wall` 만큼 띄운다. 벽 두께가 다르면 실제 간격대로 두고 검사가 받는 범위(20~400)인지 본다.
3. 문은 경첩 쪽과 열리는 쪽을 도면의 호를 보고 정한다(`hinge`, `swing`).
4. 읽지 못한 치수는 지어내지 말고 사용자에게 묻거나, 가정이면 `meta.notes` 에 적는다.
5. `meta.source` 를 `"user-plan"` 으로 둔다.
