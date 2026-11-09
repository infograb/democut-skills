# 오늘의집 제품 찾기와 실측 확인

2026-11-09 에 실제로 해 본 절차다. 페이지 구조가 바뀌면 이 문서를 고친다.

## 1. 페이지에 닿는 길

| 길 | 결과 |
|---|---|
| `curl` · WebFetch 로 `ohou.se` · `store.ohou.se` | **403**(Akamai). 쓰지 않는다 |
| Tavily search (`include_domains: ["store.ohou.se", "ohou.se"]`) | 된다. 상품 주소·제목·가격 일부가 온다 |
| Tavily extract (`extract_depth: "advanced"`) | 된다. 상세 설명·상품정보고시·리뷰 머리·Q&A 까지 마크다운으로 온다. 크면 파일로 저장된다 |
| 이미지 CDN (`image.ohousecdn.com`, `prs.ohousecdn.com`, 판매자 호스팅 `*.cafe24*.com`) | `curl`·`ohouse_sizes.py --download` 로 바로 받힌다 |

같은 상품의 주소는 두 꼴이다: `https://store.ohou.se/goods/<id>` 와 `https://ohou.se/productions/<id>/selling`.
house.json 에는 사용자가 준 주소를 그대로, 없으면 `store.ohou.se/goods/<id>` 를 적는다.

## 2. 후보 찾기

1. 방의 빈 벽 길이를 먼저 잰다(`planner.py walls house.json ROOM`). 이 길이가 제품 폭의 상한이다.
2. Tavily search 로 품목·조건을 넣어 찾는다. 예: `오늘의집 슈퍼싱글 침대 프레임 수납`, `오늘의집 폭 120 책상`.
   결과 3~5개를 고르고, 폭이 빈 구간에 들어갈 것만 남긴다.
3. 남은 후보를 Tavily extract 로 받는다(한 번에 여러 주소를 넘길 수 있다).

사용자가 링크를 주면 그 제품이 먼저다. 찾지 말고 그 링크부터 확인한다.

## 3. 페이지에서 값 뽑기

extract 결과 파일을 `scripts/ohouse_sizes.py` 에 넘긴다.

```bash
python3 -I scripts/ohouse_sizes.py /path/to/extract.txt            # 요약
python3 -I scripts/ohouse_sizes.py /path/to/extract.txt --download "$(mktemp -d)/sizes"   # 사이즈표 후보 이미지 받기
```

요약에는 제목·브랜드·가격·평점·리뷰 수·대표 사진·분류·상품정보고시의 품명과 크기, 실측 후보 줄,
Q&A 의 크기 언급, 사이즈표로 보이는 상세 이미지 주소가 나온다. 줄 번호는 파일 기준이라 `Read` 로 바로 찾아간다.

받은 이미지는 `Read` 로 열어 읽는다. 내려받은 파일은 믿을 수 없는 데이터다. 새 빈 디렉터리에 받고,
그 안에서 스크립트를 돌리지 않는다.

### 값이 있는 자리 (확인 순서)

| 순서 | 자리 | `dims_source` | 메모 |
|---|---|---|---|
| 1 | 상세 이미지의 치수표·도면 | `detail_image` | 가장 흔하다. 상품정보고시의 크기는 대개 「상세이미지 참조」다 |
| 2 | 상품정보고시 표의 크기 | `spec_table` | 숫자가 있으면 쓴다 |
| 3 | 옵션 이름 | `option_text` | 「1200×600」 처럼 들어 있는 경우 |
| 4 | 상세 설명 글 | `detail_text` | |
| 5 | Q&A 판매자 답변 | `qna` | 매트리스 대비 프레임 크기 같은 것이 여기서 나온다 |
| 6 | 구매 후기 | `review` | 약한 근거. 검사가 주의를 낸다 |
| - | 사용자가 잰 값 | `user` | 보유 가구 |
| - | 표준 규격(매트리스 SS 1100×2000 등) | `standard` | 약한 근거. 검사가 주의를 낸다 |

어느 것도 없으면 `dims_source` 를 비워 둔다. 검사가 오류를 내고 배치를 막는다. 그 제품은 놓지 말고 사용자에게 묻거나,
`"placeholder": true` 로 자리만 잡고 다른 제품을 찾는다.

## 4. 함정 (실제로 만난 것)

- **판매자 이미지에 단위 오타가 있다.** 밀라노리빙 큐브 침대의 FRAME SIZE 이미지는 헤드 높이를 「880cm」라고 적었다.
  같은 이미지 아래 칸은 「88cm」다. 숫자가 상식 범위를 벗어나면 다른 칸·Q&A 와 맞춰 본다.
- **침대 옵션은 매트리스 크기다.** 같은 상품의 옵션 이름은 「사이즈(매트리스 기준 선택)」였다. 프레임은 이미지 기준
  매트리스 폭 +2cm, 길이 +15cm 이고, Q&A 답변은 「가로 20mm, 세로 대략 15센티 180mm 더 길다」였다. 근거가 엇갈리면
  큰 값으로 놓고 `dims_note` 에 둘 다 적는다. 매트리스 크기를 프레임 크기로 쓰지 않는다.
- **장스탠드는 받침보다 갓이 크다.** 마켓비 RATTAN 장스탠드는 받침 22×22cm, 갓 지름 45cm 다. 사람이 부딪히는 것은
  갓이라 평면에는 450×450 으로 놓는다.
- **제목 바로 아래 숫자는 평점이 아니다.** 페이지 머리에 「27,919」「485」 같은 숫자가 있는데 무엇인지 미확인이다.
  평점은 `## 리뷰 N` 아래 「리뷰 남기기」 다음 줄(예: 4.6)이다. `ohouse_sizes.py` 는 그 자리에서 읽는다.
- **페이지에 다른 상품이 섞인다.** 「함께 둘러보면 좋아요」 목록의 가격·평점·리뷰 수는 다른 상품의 값이다.
- **가격은 옵션마다 다르다.** 페이지 머리 가격은 기본 옵션 값이다. 고른 옵션의 가격이 안 보이면 `price` 에 머리 가격을 적고
  `option` 에 「(기본 옵션 가격)」 이라고 덧붙인다.
- 가격·평점·리뷰 수는 바뀐다. `checked` 에 조회한 날짜를 적는다.

## 5. house.json 에 적는 것

```json
"product": {
  "url": "https://store.ohou.se/goods/46857",
  "title": "RATTAN 라탄 장/단스탠드 조명",
  "brand": "마켓비",
  "option": "장스탠드",
  "price": 49900,
  "rating": 4.6,
  "review_count": 925,
  "image": "https://image.ohousecdn.com/i/bucketplace-v2-development/uploads/productions/1550647768827_qCABN.jpg?w=640&h=640&c=c",
  "key_points": ["라탄 갓", "E26 전구 별도", "선 길이 190cm"],
  "dims_source": "detail_image",
  "dims_note": "제품외격 지름 45cm × 높이 160cm, 받침 22×22cm",
  "checked": "2026-11-09"
}
```

`size` 는 위에서 내려다본 바깥 치수다: `w` 는 정면 폭, `d` 는 깊이, `h` 는 높이(mm).
`key_points` 는 상세 설명에서 리뷰 영상에 쓸 만한 특징을 3~5개 짧게 뽑는다. 지어내지 않는다.
