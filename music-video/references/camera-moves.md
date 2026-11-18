# 카메라 움직임

장면마다 움직임 하나를 고른다. 무엇을 보여 줄 장면인지가 먼저고 움직임은 그것을 돕는다.

## 안무 장면은 카메라가 박자에 맞춰 앞뒤로 움직인다

춤추는 장면의 기본은 **박자에 맞춘 밀고 빼기**다. 카메라가 음악 박자에 맞춰 앞으로 들어갔다 뒤로 빠지는 무빙을 반복해야
화면이 음악에 붙는다. 고정 카메라로 만든 군무 컷은 동작이 커도 화면이 밋밋하다는 피드백을 받았다. 음악방송·MV 촬영도
큰 동작의 박에 카메라를 확 밀거나 빼서 진동감을 주고, 지미집으로 와이드에서 줌인·아웃하며 대형을 따라간다
([GDW 제작 과정](https://www.koreaboo.com/lists/kpop-music-video-production-step-step-youtube-evolution),
[인기가요 카메라 감독](https://www.youtube.com/watch?v=O6nnVhVxRKc)).

'박마다' 왕복하는 것이 아니라 '박자에 맞춰' 움직이는 것이다. 박마다 튕기면 너무 빨라 정신없어진다. 고정 와이드로
오래 버티지도 않는다.

- **주기:** 한 번 들어가는 데 약 2박, 빠지는 데 약 2박(4박에 한 번 왕복, 130 BPM 이면 약 1.85초). 8초 컷이면
  2~3회 왕복한다. 가장 강한 히트 한두 곳에서만 짧게 빨리 들어가는 강조를 쓴다.
- **박 맞추기:** 움직임의 시작과 도착을 박(특히 마디 첫 박)에 맞춘다. 움직이는 동안은 부드럽게 흐르되, 박에 도착해
  잠깐 머문다. 정처 없이 흐르는 느린 줌은 아니다. 속도 낱말(`fast`, `snap`)과 시작·끝 구도·시각을 함께 적는다.
  「dollies in」만 적으면 속도가 모델 마음대로다.
- **크기:** 들어갈 때는 무릎 위~허벅지 미디엄(핑거댄스가 읽히는 거리), 빠질 때는 발까지 나오는 전신 와이드.
  매번 같은 거리로 왕복하지 말고 깊이를 조금씩 바꾼다. 한 줄에 머리부터 발끝까지 보이는 풀숏을 하나 이상 둔다.
  손끝과 발이 잘리면 안무가 읽히지 않는다.
- **선명하게:** 모션 블러는 쓰지 않거나 최소로 하고 도착 프레임은 선명하게 둔다. 핸드헬드로 적어도 도착은 선명하다.
- **피사체를 자르지 않기:** 들어갈 때 머리와 손이 프레임 안에 남게 한다. 머리를 자르는 과한 클로즈업은 쓰지 않는다.
- **밀고 빼기만 반복하지 않는다.** 정면 푸시·풀백은 기본이되, 왕복 사이에 횡트래킹, 하이·로우 앵글, 짧은 아크, 휩 팬을
  1회 정도 섞되 왕복 리듬은 유지한다. 같은 정면 돌리만 이어지면 동작이 커도 앵글이 단조롭다는 피드백이 났다(실측).
- **다른 종류의 움직임을 한 순간에 겹치지 않는다.** 영상 모델 가이드는 한 샷에 서로 다른 움직임을 겹치면(밀면서 돌기)
  화면이 무너진다고 한다([Morphic](https://morphic.com/resources/how-to/seedance-2-guide)). 같은 종류의 앞뒤 왕복을
  박자에 맞춰 반복하는 것과, 밀기와 아크를 동시에 시키는 것은 다르다. 다른 종류가 필요하면 박이 바뀌는 자리에 잇거나
  하드 컷으로 장면을 나눈다.
- **하드 컷으로 나눈 짧은 장면**에서는 장면마다 움직임 하나를 두고 방향을 바꿔도 된다(밀기 장면과 빼기 장면을 번갈아).
  앞뒤 리듬은 장면이 바뀌며 생긴다. 두 방식 중 어느 쪽을 쓸지는 그 줄의 콘티가 정한다.
- **챌린지 구간도 정면 각도는 지키되 움직인다.** 정면에서 풀숏과 무릎 위 숏 사이로 작게 밀고 뺀다. 따라 하는 사람이
  동작을 놓치지 않는 폭이다.
- 영상 모델 가이드 중에는 춤을 고정 와이드로 찍으라는 것도 있다. 빠른 카메라가 손발이 일그러지는 것을 가리기 때문이다
  ([Seedance.tv](https://www.seedance.tv/blog/ai-dance-video-prompt-examples)). 그 권고를 따르면 우리가 받은 「밋밋하다」가 된다.
  손발이 일그러지면 움직임을 빼지 말고 장면을 더 짧게 나눈다.

프롬프트에는 카메라 문장을 동작 문장과 떼어 적고, 이동 시작·도착 시각을 박 단위로 적는다. 「춤추는 사람 주위로 돈다」처럼
섞어 쓰면 누가 움직이는지 모호하다.

```text
camera rhythmically pushes in and pulls back in time with the music, each move spanning about two beats and landing
on the beat, not every beat, sharp landing frames, no motion blur.
0.00-0.92s camera glides in to mid-thigh medium, landing on the downbeat; 0.92-1.85s pulls back out to full-body wide
with feet visible, landing on the next downbeat.
```

하드 컷으로 나눈 줄의 예:

```text
The camera is never static: every shot has one fast camera move timed to the beat, alternating forward and back.
Shot 1, 0.00-0.92s, the camera snaps a fast dolly push-in from a frontal full shot to a mid-thigh medium on beat 1
and stops sharply, no motion blur: they land a sharp chest hit, fingers in a rectangle frame.
HARD CUT at 0.92s. Shot 2, 0.92-1.85s, the camera makes a quick pull-back from a medium shot to a frontal full shot
on the downbeat, feet visible: they spread out into a V formation.
```

만든 뒤 `mv_timing.py sheet --bpm <곡 BPM>` 으로 왕복 횟수(너무 잦지 않은지), 도착 시각이 박에 맞는지, 블러·잘림이
없는지, 멤버의 키가 화면에서 커지거나 작아지는 칸을 잰다. 카메라가 거의 서 있으면 움직임 문장을 장면 문장 맨 앞에 두고
시각을 더 구체화한다. 박마다 튕기면 주기를 2박으로 늘린다.

## 확정된 연출은 줄이지 않는다

사람이 정한 카메라 연출(앵글, 패닝 방향과 각도, 아크샷, 오프닝 클로즈업, 줌 속도, 핸드헬드 여부)은 그 컷의 고정 조건이다.
초안을 고치거나 줄일 때 'or', '가능하면', '또는 정면' 같은 선택지로 약하게 바꾸지 않는다.

- 초안을 쓰기 전에 그 컷의 확정 카메라 결정을 콘티와 결정 기록에서 모두 뽑아 체크리스트로 만든다. 새 초안이 그중
  하나라도 빠뜨리거나 약하게 바꾸면 내보내지 않는다.
- 결과가 콘티와 안 맞아 프롬프트를 줄여야 할 때는 확정 카메라와 핵심 전환을 남기고, 안무 세부(카운트별 손 모양 개수 등)를
  먼저 줄인다. 실패를 이유로 구도를 단순화하지 않는다.
- 검수 때 확정 카메라 항목은 하나씩 시각(초)과 함께 됐다, 안 됐다로 판정한다.
- 새로 확정된 구도나 잘 나온 문장, 실패한 표현은 아래 레시피에 계속 더한다.

## 구도 레시피

- **하이 앵글 노래 컷:** 인물보다 위에서 내려다보고, 인물은 고개를 들어 카메라를 보며 부른다. 얼굴 전체와 상반신이
  보이고 눈 위가 잘리지 않는다. `high-angle shot looking down, she lifts her head up to the lens while singing`.
- **노래 직전 앵글 하드 컷:** 노래 직전에 카메라를 하이 앵글 같은 새 앵글로 박에 맞춰 하드 컷한다. 인물은 반 박
  늦게 그 카메라를 쳐다보며 부르기 시작한다(130 BPM 이면 약 0.23초). 입모양은 카메라 문장에 모음을 한 덩어리로
  적지 않는다. 프롬프트에는 단어·구의 시작과 끝만 적은 MOUTH MAP 한 블록을 둔다
  ([`democut-mv.md`](democut-mv.md) 「한국어 가사의 입모양」).
  `HARD CUT on the beat to a new angle just before the singing starts; half a beat later she looks into the new camera`.
- **전환 중에도 안무는 이어진다:** 장면이 바뀌거나 구조물이 생기는 동안 군무를 멈추지 않는다. 첫 포즈를 잡은 채
  전환이 끝나길 기다리지 않는다. 전환 구간의 박마다 발·손 동작을 따로 적는다. 검수 때 한 포즈로 얼어 있으면 실패다.
- **패닝으로 함께 담기:** 주인공에서 정한 방향으로 약 45도처럼 각도를 숫자로 적어 박에 맞춰 패닝하고, 관련 인물(소품을
  건넨 사람 등)을 같은 프레임에 넣는다. 방향, 각도, 시작과 도착 박을 적는다.
- **디테일 클로즈업 오프닝:** 신발이나 손 클로즈업에서 빠르게(약 2박 안에) 빠져 머리부터 발까지 전신에 착지한다.
  안무는 0초부터 이미 진행 중이고, 카메라가 빠질 때까지 서서 기다리지 않는다.
- **핸드헬드 앞뒤 무빙:** 박자 앞뒤 무빙에 `handheld` 를 명시한다. 핸드헬드 느낌이어도 모션 블러는 쓰지 않고 도착 프레임은
  선명하다.
- **아크샷:** 블러 없이 돌고, 기준이 되는 인물이나 소품이 화면에 남는다.
- **시간 단축:** 동작을 빨리 감지 않는다. 걷기나 주고받기 같은 동작은 자연 속도로 두고, 카메라가 박에 맞춰 끊어 넘기며
  장면을 진행시켜 시간을 줄인다.

## 공간이 생겨나는 전환

재료로 벽이나 구조물이 생기는 전환은 겉면 질감만 바뀌는 것으로 나오기 쉽다. 프롬프트 첫머리에 첫 프레임에는
그 구조물이 없다고 적는다(`open space, no walls at frame 1`). 재료가 바닥에서 일어나 두께 있는 구조물이 되며,
조명 같은 부속은 그 안에서 생긴다고 적는다. `structure is built from the material, not a texture or color change on
existing walls` 를 넣는다.

생기는 방식은 그 재료와 같아야 한다. 액체(슬라임 등)로 벽이 생기면 벽돌이나 블록을 쌓은 것처럼 보이면 안 된다.
한 번의 연속된 변화로 적는다. 액체가 끈적한 파도처럼 바닥에서 솟아 위로 흐르고, 그 자리에서 굳어 매끈한 벽이 된다.
프롬프트에 `bricks`, `blocks`, `stacked`, `layer by layer` 를 넣지 않는다. `liquid flows up and hardens into the walls`
를 쓴다.

전환이 진행되는 동안에도 군무는 박마다 이어진다. 장면이 바뀌거나 구조물이 생기는 동안 첫 포즈를 잡은 채 기다리지
않는다. 전환 구간의 박마다 발·손 동작을 따로 적고 `dance never pauses while the walls rise` 를 넣는다.
검수 때 첫 프레임에 구조물이 이미 있거나, 액체 벽이 벽돌·블록처럼 보이거나, 전환 동안 인물이 한 포즈로 멈춰 있으면
실패로 본다.

## 고르는 기준

1. **춤추는 장면인가.** 그렇다면 위의 박자 앞뒤 무빙이 기본이다. 고정 카메라는 소리 빈 자리의 정지 포즈처럼
   멈춰 있어야 한다고 *정한* 장면에만 쓴다. 입을 맞추는 단독샷도 하이 앵글이나 패닝이 확정이면 고정으로 바꾸지 않는다.
2. **누가 중심인가.** 파트 멤버 단독이면 클로즈업·미디엄. 셋이 함께면 와이드. 관련 인물을 같은 프레임에 넣어야 하면
   각도를 적은 패닝 레시피를 쓴다.
3. **구간 에너지.** 작은 구간은 느린 움직임, 큰 구간은 빠른 움직임(휩 팬, FPV, 원형 돌리). 다만 앞뒤 왕복의 기본 주기는
   약 2박이다. 박마다 왕복하지 않는다.
4. **다음 컷으로 어떻게 넘어가나.** 렌즈를 덮는 장치, 휩 팬, 밀고 들어가기는 컷 경계를 숨긴다.

## 움직임 어휘

| 움직임 | 프롬프트 표현 | 쓰는 자리 |
|---|---|---|
| 박자 앞뒤 무빙 | `camera rhythmically pushes in and pulls back in time with the music, each move spanning about two beats and landing on the beat, not every beat, sharp landing frames` | 춤추는 장면의 기본. 시작·도착 시각을 박 단위로 적는다 |
| 히트 흔들기 | `on the hit the camera jolts with a short sharp shake` | 큰 강세 한 박. 왕복 주기를 깨지 않게 한두 번만 |
| 박에 밀기(펀치 인) | `0.00-0.92s camera glides in to mid-thigh medium, landing on the downbeat, no motion blur` | 포인트 동작, 강세. 머리와 손이 프레임 안에 남는다 |
| 박에 빼기 | `0.92-1.85s pulls back out to full-body wide, feet visible, landing on the next downbeat` | 대형이 드러나는 박, 이동이 시작하는 박 |
| 핸드헬드 앞뒤 무빙 | `handheld camera rhythmically pushes in and pulls back, no motion blur, sharp landing frames` | 핸드헬드가 확정된 군무 컷 |
| 하이 앵글 노래 | `high-angle shot looking down, she lifts her head up to the lens while singing` | 부르는 단독·중심 샷이 하이 앵글로 확정된 줄 |
| 노래 직전 앵글 하드 컷 | `HARD CUT on the beat to a new angle just before the singing starts; half a beat later she looks into the new camera` | 노래가 시작하기 직전. 새 앵글이 확정된 줄. 입은 MOUTH MAP 한 블록 |
| 각도를 적은 패닝 | `on the beat the camera pans about 45 degrees to the right, bringing the other members into the same frame` | 관련 인물을 같은 화면에 넣어야 하는 줄. 방향·각도·박을 숫자로 적는다 |
| 디테일에서 빠른 풀아웃 | `opens on a close-up of the shoes (or hands), the dance already in progress, then pulls out within about two beats to a head-to-toe full shot, landing on the downbeat` | 클로즈업으로 시작하는 군무. 카메라가 빠질 때까지 기다리지 않는다 |
| 정면 고정 | `locked-off frontal shot, static, eye level` | 멈춰 있어야 한다고 *정한* 정지 포즈. 입을 맞추는 샷의 기본값은 아니다 |
| 천천히 밀기 | `slow push-in` | 춤 없는 장면에서 감정이 오르는 줄의 끝, 전환 직전 |
| 뒤로 빠지기 | `camera pulls back to a frontal wide shot` | 공간이나 다른 멤버를 드러낼 때 |
| 뒤로 물러나는 트래킹 | `backward tracking shot as she walks toward the camera` | 걸어 나오는 벌스 |
| 핸드헬드 | `handheld camera, subtle shake, no motion blur` | 랩, 거친 벌스. 군무의 앞뒤 무빙이면 위의 「핸드헬드 앞뒤 무빙」을 쓴다 |
| 휩 팬 | `whip pan between her face and her hands` | 가사 줄이 바뀔 때, 멤버 사이 이동 |
| 스테디캠 군무 통과 | `steadicam gliding between the dancing members` | 대형 이동이 있는 후렴 |
| 원형 돌리 | `circular dolly shot orbiting the members clockwise` | 2절 후렴처럼 크게 가는 줄 |
| 피사체를 지키는 아크 | `a fast arc around the subject, no motion blur, the subject (and the mirror, if any) stays fully inside the frame for every frame; the camera never travels behind the subject or the mirror so that they leave the shot` | 거울 장면, 멤버를 한 바퀴 도는 줄. 궤도만 적으면 대상이 화면 밖으로 나간다(실측) |
| 느려지는 옆모습 트래킹 | `a profile tracking shot that slows to a near halt, and as it decelerates the repeating motif (a double, a prop) appears just behind the member, still in frame` | 분신·소품이 멤버 뒤에서 드러나는 줄 |
| FPV 드론 진입 | `FPV drone flies in from the skyline, passes between the members and stops in front` | 클라이맥스 첫 줄 |
| 달리 줌 | `dolly zoom, the face stays the same size while the background stretches` | 숨은 모습이 드러나는 순간 |
| 로우 앵글 | `low-angle shot` | 강해 보여야 하는 단독 |
| 극접사 | `extreme macro close-up` | 손끝·눈·소품, 전환의 시작 |
| 틸트 업 | `tilt up following …` | 떠오르는 대상 |
| 점프 정점 정지 | `freeze at the apex of the jump` | 소리 빈 자리 |
| 셀카·소형 카메라 시점 | `arm-length selfie POV with a compact digital camera, on-camera flash` | 아웃트로, 비하인드 느낌 |

## 컷 경계를 숨기는 전환

- **렌즈 덮기.** 물체(반복 장치)가 렌즈로 날아와 화면을 다 덮는다. 앞 컷은 다 덮인 칸에서 끝내고, 다음 컷은 덮인 화면에서
  시작해 걷히며 새 장면을 보인다. 앞 컷의 끝 칸은 `mv_timing.py sheet` 로 잰다(덮개에 구멍이 생기기 직전 칸).
- **휩 팬.** 앞 컷이 한쪽으로 빠르게 쓸려 끝나고 다음 컷이 같은 방향으로 쓸려 들어온다.
- **밀고 들어가기.** 앞 컷이 얼굴이나 물체로 밀고 들어가 화면이 한 색이 되고, 다음 컷이 그 색에서 빠져나온다.

## AI 영상에서 주의할 것

- 한 순간에 서로 다른 종류의 움직임 둘을 섞으면(밀면서 돌기) 화면이 무너지거나 하나만 나온다. 둘이 필요하면 박이
  바뀌는 자리에 잇거나 장면을 나눈다. 같은 종류의 앞뒤 왕복을 약 2박 주기로 반복하는 것은 여기에 넣지 않는다.
- 움직임의 시작·끝 구도와 시각을 함께 적는다. 「…에서 시작해 …로 끝난다」.
- 고정 카메라가 필요한 장면은 `static` 을 꼭 적는다. 적지 않으면 모델이 흔히 천천히 움직인다(미확인).
- 움직이는 장면은 움직임을 박과 함께 적는다. 카메라를 적지 않으면 화면이 제멋대로 흐르거나 서 버린다
  ([Pexo 비교](https://pexo.ai/blog/kling-ai-tips-better-results-8652), 한 사람의 시험이라 근거가 약하다).
- 「Dolly」「Crane」을 낱말 하나로 쓰지 말고 `dolly push-in shot`, `crane shot` 처럼 묶어 쓴다. 혼자 오면 고유명사로 읽힐 수 있다.
- 아크·원형 돌리는 시작·끝 구도만이 아니라 **매 프레임에 담을 대상**(사람, 거울, 반복 장치)을 적는다.
  「뒤로 돌아간다」만 적으면 카메라가 대상 뒤로 넘어가 빈 벽을 찍는다. 거울 장면은 거울과 사람이 함께 보이게
  앞쪽 반원 안에만 둔다. 아크는 블러 없이 돈다.
- 핸드헬드나 아크, 빠른 줌아웃을 적어도 `no motion blur, sharp landing frames` 를 함께 적는다.
