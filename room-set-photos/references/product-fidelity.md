# 제품을 사진에 실제와 같게 넣기

가구·소품·옷을 생성 그림에 **고른 제품 그대로** 넣는 방법. 2026-11-13 조사와 v8 방 사진의 실패에서 나왔다.
`shots.py` 가 아래 대부분을 자동으로 하고, 사람이 정할 것은 house.json 품목의 `keep`·`product.ref_image`·
`product.ref_crop`·`product.ref` 다.

## 왜 틀리게 나오나 (v8 에서 본 것)

2026-11-12 대표 컷 7·8번째에서 조명은 두 단 갓이 한 단 돔으로, 스툴은 다리 자리와 X 살이, 침대는 매트리스 둘레의
받침이 틀렸다. 보드(모델이 받은 제품 사진)를 열어 보니 원인은 대부분 **레퍼런스 사진**에 있었다.

| 원인 | 본 것 |
|---|---|
| 제품 사진 속 **다른 물건** | 침대 사진과 의자 사진에 한 단 돔 조명이 함께 찍혀 있었다. 모델은 그 조명을 옮겼다 |
| 고른 것과 **다른 옵션**의 사진 | 침대 사진은 매트리스보다 넓은 받침(큰 옵션)이었다. 모델은 그 받침 여백을 옮겼다 |
| 여러 개·소품이 함께 찍힌 사진 | 스툴 대표 사진은 스툴 다섯 개가 쌓여 있고 꽃병이 올라가 있었다 |
| 보드 축소 | 여섯 칸 보드(1536×1024)를 DemoCut 이 긴 변 1024 로 줄여 칸이 약 340px, 조명은 60~80px 였다 |
| 사진 속 글자 | 조명 옵션 사진 밑에 「White (Shade : White)」 가 찍혀 있었다 |
| 칸 순서로 가리키기 | 「items … in reading order」 — 모델은 보드 칸 순서를 잘 따르지 않는다 |
| 이름만 있는 생김새 | look 이 「two-tier round shade」 처럼 짧아 무엇을 지켜야 하는지가 약했다 |
| 부딪치는 금지어 | Avoid 의 「glossy」 가 유광 갓과 부딪쳤다 |
| 작은 소품의 크기 | 8×8×10 cm 를 cm 로만 적었더니 1.5배쯤 크게 나왔다 |

## 조사에서 가져온 원칙

1. **레퍼런스는 그 제품만 또렷이.** 흰·단색 바탕, 제품 전체가 보이고, 정면이나 3/4 방향, 다른 물건·사람·글자 없음.
   생성 결과는 레퍼런스의 깨끗함을 넘지 못한다([getimg](https://getimg.ai/blog/how-to-create-product-photos-with-ai),
   [The New Black](https://thenewblack.ai/blog/virtual-try-on-ai), [Krea](https://www.krea.ai/blog/ai-product-photography-in-2026-tools-prompts-pipeline)).
2. **레퍼런스는 번호보다 내용으로 가리킨다.** 배열 순서는 믿을 만하지 않다. 「the product photos of the lamp and the
   stool」 처럼 무엇이 찍혔는지로 말하고 품목 줄과는 생김새로 짝짓게 한다
   ([Runware — GPT-Image-2.5 Flare subject consistency](https://runware.ai/docs/models/openai-gpt-image-2-5-flare/guides/subject-consistency.md),
   [OpenAI 이미지 프롬프트 가이드](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)).
3. **지킬 특징을 이름으로 적는다(preserve clause).** 「Keep exactly: …」 에 모양·비율·부품 자리·마감(유광/무광)을 적는다.
   물건 이름만으로는 비슷한 다른 것이 나온다. 장면 설명 뒤에, 짧게 둔다(Runware).
4. **불변 조건을 매번 다시 적는다.** 편집할 때 「change only X」 와 「keep everything else the same」 을 함께, 매 반복마다
   (OpenAI 가이드의 interior swap·multi-image compositing 꼴).
5. **한 번에 하나씩 고친다.** 전체를 다시 만들기보다 틀린 제품만 편집으로 고친다([Krea](https://www.krea.ai/blog/ai-product-photography-in-2026-tools-prompts-pipeline) 의
   「생성 → 틀린 부분만 지역 편집」, OpenAI 가이드의 작은 단일 변경 반복).
6. **정확함은 보장되지 않는다.** gpt-image 계열의 레퍼런스 충실도는 높아졌지만 닮음이지 복제가 아니다. 로고·글자·정확한
   비율이 꼭 맞아야 하면 합성(실제 제품 사진을 잘라 붙이기)이 답이다
   ([OpenAI 포럼 — high fidelity 로도 어긋난다](https://community.openai.com/t/inconsistent-character-images-despite-input-fidelity-high/1354610),
   [Runware](https://runware.ai/docs/models/openai-gpt-image-2-5-flare/guides/subject-consistency.md)).

참고: `input_fidelity` 옵션은 gpt-image-1 계열의 것이고 gpt-image-2 이후로는 기본이 높은 충실도라 꺼져 있다
([OpenAI images.edit](https://developers.openai.com/api/reference/resources/images/methods/edit),
[high input fidelity 쿡북](https://developers.openai.com/cookbook/examples/generate_images_with_high_input_fidelity)).
DemoCut 도 이 값을 보내지 않는다. 충실도는 레퍼런스와 프롬프트로 끌어올린다.

## 이 스킬에서 하는 일

| 무엇 | 어디서 |
|---|---|
| 보드 한 장은 2×2(512px 칸, 1024px). DemoCut 의 레퍼런스 상자(긴 변 1024)에서 줄지 않는다. 대표 컷은 보드 두 장(8칸)까지 | `shots.py plan`·`board` |
| 보드 문장은 「Reference images 2 and 3 show product photos of the chair, …: copy each exactly …, matched to its line by look; ignore anything else in them」 | `build_prompt` |
| 품목 줄 끝에 `Keep exactly: <keep>` | house.json `items[].keep` |
| 받침 위 소품은 받침과의 비율 「about 1/4 that top's width and 1/5 the nightstand's height」 | 가구별 규칙 `rests-on`(`on_scale`) |
| Avoid 는 「glossy」 대신 「a glossy ad look」 | `negative` |
| 틀린 제품만 고치는 편집 프롬프트 | `shots.py fix` |

### 사람이 정하는 것: 제품 사진 고르기

fetch 로 받은 사진을 **눈으로 보고** 품목마다 정한다.

- `product.ref_image` — 대표 사진에 다른 물건이 많거나 여러 개가 찍혔으면, 상세 이미지에서 **그 제품만 찍힌 사진**의
  주소를 적는다. 상세 이미지 주소는 `m.ohou.se/productions/<id>/selling` 을 Tavily extract 로 받으면 「상품정보」 아래
  `prs.ohou.se/…/descriptions/url/…` 로 나온다. 옵션 사진(색별 단독 컷)이 가장 깨끗한 경우가 많다.
- `product.ref_crop` — `[왼, 위, 오른, 아래]`(사진 폭·높이에 대한 0~1 비율). 다른 제품·글자·사람을 잘라 낸다.
  긴 상세 이미지에서 그 제품 칸만 고를 때도 쓴다. 자른 뒤 `board` 결과를 Read 로 열어 확인한다.
- `product.ref: false` — 보드에서 뺀다. 그 품목은 `look`·`keep`·치수로만 그려져 실제 제품과 같다는 보장이 없다.
  **리뷰 제품에는 쓰지 않는다**(`plan` 이 경고한다). 2026-11-13 침대 대표 사진에 다른 조명이 함께 찍혀 침대를 뺐는데,
  상세 이미지에 매트리스만 올린 흰 벽 앞 컷과 프레임만 그린 제품 정보 그림이 있었다. 대표 사진이 오염됐으면 상세 이미지를
  끝까지 내려 그런 컷을 찾고 `ref_crop` 으로 다른 물건(식물·조명)을 잘라 낸다.
- `keep` — 그 제품을 그 제품이게 하는 특징을 영어 구 하나로. 모양·비율·부품의 자리·마감·개수를 적는다.
  크기 관계(더 넓다·튀어나온다)는 적지 않는다(SKILL.md 2단계). 길면 프롬프트 한도(4,000자)를 넘는다.

```json
{"id": "bedlamp", "look": "a small white cordless lamp, glowing warm",
 "keep": "two stacked glossy white shade tiers (a wide flat brim under a smaller dome) on a short, narrower matte white cylinder",
 "product": {"image": "https://…/v1-479413302362176.jpg?w=640&h=640&c=c", "ref_crop": [0.35, 0.33, 0.65, 0.68]}}
```

`look` 은 무엇인지(「a round light rubberwood stool」), `keep` 은 그것을 다른 스툴과 가르는 것
(「four round legs outside the round top's rim, their ends rising just above it; a cross brace right under the top, none lower」)이다.

## 틀린 제품만 고치기 (`fix`)

전체를 다시 만들면 고친 곳 대신 다른 곳이 틀어지기 쉽다. 대표 컷이 거의 맞고 제품 한두 개만 틀렸으면 편집으로 고친다.

```bash
python3 -I <스킬>/scripts/shots.py fix photos/shots.json <컷 id> <품목 id> [<품목 id> …] --images <제품 사진 디렉터리>
```

- `photos/fixes/<컷>--<품목>.json`(프롬프트·레퍼런스·확인 목록)과 `photos/boards/fix-<컷>--<품목>.png` 가 나온다.
- 레퍼런스 1번은 **그 컷에서 만든 그림**(DemoCut 자산), 2번은 고칠 제품의 보드다.
- 프롬프트 꼴: 「Image 1 is a finished photo … change only the X and nothing else」 → 품목마다 생김새·`keep`·자리·크기 →
  「Keep everything else in image 1 exactly as it is: camera angle, framing, … Match image 1's light, shadows and color
  temperature so … look photographed in the room, not pasted in」.
- DemoCut 에서 하는 순서는 [democut-image.md](democut-image.md) 「틀린 제품만 고치기」.
- 고친 그림도 확인 목록으로 본다. 다른 곳이 바뀌었으면 그 그림을 쓰지 않는다(이전 그림이 버전으로 남아 있다).

### 크기만 틀렸을 때 (`--scale`)

받침 위에 놓인 손바닥만 한 소품(조명·시계·디퓨저)은 모양이 맞아도 크게 나온다. 새로 만들어서는 고쳐지지 않았다.
2026-11-13 gpt-image-2.6 은 8×8×10cm 조명을 cm, 받침과의 비율, 「머그잔만 하다」 를 다 적어도 생성마다 받침 높이의
36~40%(실제 22%)로 그렸다. 편집에서는 그림 속 지금 크기를 자로 삼아 배율로 줄인다.

1. 그림에서 그 소품과 받침(또는 곁 가구)의 높이·폭을 픽셀로 잰다. 배율은 (실제 비율) ÷ (그림 속 비율)이다.
   예: 조명 높이가 스툴 높이의 36% 이고 실제는 10/45 = 22% 면 0.6 이다.
2. `fix … <품목> --scale 0.6` 을 돌린다. 프롬프트가 「is drawn too large. Shrink it to about 60% of its current height and
   width in image 1 … Fill the space it no longer covers with what is behind it」 로 바뀐다. 모양은 `keep` 과 보드로 붙잡는다.
3. 고친 그림에서 다시 잰다. 2026-11-13 에 50% 를 요청했더니 높이는 80%, 폭은 73% 로 줄었다. 요청한 줄임의 절반쯤만
   들어간 셈이다. 그 그림을 레퍼런스 1번으로 두고 60% 를 한 번 더 요청했더니 크기가 픽셀까지 그대로였다.
   두 번째 편집은 크기를 바꾸지 않으니 돈을 다시 쓰지 않는다. 남은 차이가 크면 처음 그림으로 돌아가 더 작은 배율로
   한 번에 편집해 본다(이 방법은 아직 재 보지 않았다).
4. 대표 컷을 고쳐도 다른 컷의 소품은 따라 작아지지 않는다. 2026-11-13 조명을 1.3배로 줄인 대표 컷을 레퍼런스 1번으로
   협탁 제품 컷을 만들었더니 그 조명은 다시 약 1.5배(받침 높이의 32%, 윗면 폭의 37%)였다. 그 소품이 보이는 컷마다
   재고 따로 편집한다.

### 집에서 바뀐 것도 같은 편집에 싣기 (`--change`)

대표 컷을 만든 뒤 집에서 작은 것이 바뀌었으면(러그를 뺐다, 시트를 씌웠다) 대표 컷을 처음부터 다시 만들지 않는다.
다시 만들면 맞춰 둔 제품과 창밖이 다시 틀어지기 쉽다. house.json 을 먼저 고치고 plan·board 를 다시 돌린 뒤, 그 변경을
영어 문장으로 같은 편집에 싣는다.

```bash
python3 -I <스킬>/scripts/shots.py fix photos/shots.json wide-window bedlamp --scale 0.5 --images <제품 사진 디렉터리> \
  --change "remove the oval cream rug from the floor; show the bare wood floor there" \
  --change "put a white fitted sheet on the mattress, covering its top and sides, so no gray mattress fabric shows"
```

2026-11-13 에 조명 줄이기, 러그 지우기, 시트 씌우기를 한 번에 편집했고 나머지(가구·창밖·빛·침구)는 그대로였다.
가구를 더하거나 옮기는 변경은 싣지 않는다. 스케치가 바뀌므로 그 컷은 다시 만든다.

## 옷 (사람이 입은 제품)

이 스킬의 방 사진에는 사람이 없지만, 같은 원칙을 옷에 쓰는 꼴을 적어 둔다(조사: [The New Black](https://thenewblack.ai/blog/virtual-try-on-ai),
OpenAI 가이드의 virtual try-on 꼴).

- 레퍼런스: 옷만 찍은 사진(바닥에 펼친 사진이나 마네킹 컷, 앞면 전체, 단색 바탕). 모델이 입은 착용 컷은 그 모델의 얼굴·자세가 섞인다.
- 사람: DemoCut 의 캐릭터(`reference_character_ids`)로 얼굴·체형을 잠근다. 레퍼런스는 캐릭터와 합쳐 4장까지다.
- 프롬프트: 「Dress the person from image 1 in the exact garment from image 2. Keep exactly: <무늬·단추 수·목선·소매 길이·
  기장·소재의 질감>. Change only the clothes: keep the face, hair, body, pose, background and light exactly as in image 1.
  Match the light so the fabric drapes and folds naturally.」
- 무늬·로고·글자가 꼭 맞아야 하면 생성이 아니라 합성을 쓴다(원칙 6).

## 출처

읽은 범위를 적는다. OpenAI 쿡북은 편집·합성·가상 피팅 절을 읽었고 전문을 다 읽지는 않았다.

- [OpenAI — Image generation models prompting guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)
- [OpenAI — Generate images with high input fidelity](https://developers.openai.com/cookbook/examples/generate_images_with_high_input_fidelity)
- [OpenAI API — images.edit](https://developers.openai.com/api/reference/resources/images/methods/edit)
- [Runware — GPT-Image-2.5 Flare subject consistency](https://runware.ai/docs/models/openai-gpt-image-2-5-flare/guides/subject-consistency.md)
- [OpenAI 커뮤니티 — Inconsistent character images despite input_fidelity high](https://community.openai.com/t/inconsistent-character-images-despite-input-fidelity-high/1354610)
- [Krea — AI product photography in 2026](https://www.krea.ai/blog/ai-product-photography-in-2026-tools-prompts-pipeline)
- [motiful/product-shots](https://github.com/motiful/product-shots) — 제품 정체를 지키는 「identity anchor」 꼴
- [getimg — How to create product photos with AI](https://getimg.ai/blog/how-to-create-product-photos-with-ai)
- [The New Black — Virtual try-on AI](https://thenewblack.ai/blog/virtual-try-on-ai)
- [Scenario — GPT Image 2: the essentials](https://help.scenario.com/articles/8473821828-gpt-image-2-the-essentials)
- [Magnific — GPT Image 2 edit API](https://docs.magnific.com/api-reference/text-to-image/gpt-image-2-edit/edit.md)
- [fal — GPT Image 1.5 edit](https://fal.ai/models/fal-ai/gpt-image-1.5/edit/llms.txt)
