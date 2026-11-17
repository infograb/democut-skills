# 카메라 움직임

장면마다 움직임 하나를 고른다. 무엇을 보여 줄 장면인지가 먼저고 움직임은 그것을 돕는다.

## 안무 장면은 카메라가 박자에 맞춰 앞뒤로 움직인다

춤추는 장면의 기본은 **박 밀고 빼기**다. 카메라가 박에 맞춰 멤버 쪽으로 밀고 들어가고, 다음 장면에서는 뒤로 빠진다.
고정 카메라로 만든 안무 컷(에이슬라임 MV A1b)은 동작이 커도 화면이 밋밋하다는 피드백을 받았다. 음악방송·MV 촬영도
큰 동작의 박에 카메라를 확 밀거나 빼서 진동감을 주고, 지미집으로 와이드에서 줌인·아웃하며 대형을 따라간다
([GDW 제작 과정](https://www.koreaboo.com/lists/kpop-music-video-production-step-step-youtube-evolution),
[인기가요 카메라 감독](https://www.youtube.com/watch?v=O6nnVhVxRKc)).

- **한 장면에 움직임 하나, 방향은 장면마다 바꾼다.** 영상 모델 가이드는 한 샷에 움직임을 겹치면 화면이 무너진다고 한다
  ([Morphic](https://morphic.com/resources/how-to/seedance-2-guide)). 그래서 한 장면 안에서 밀었다 빼지 않는다. 장면을 하드 컷으로
  나누고(두 박이나 한 마디) 밀기 장면과 빼기 장면을 번갈아 둔다. 앞뒤 리듬은 장면이 바뀌며 생긴다.
- **움직임은 박에서 시작해 박에서 선다.** 천천히 흘러가는 움직임은 박을 타지 않는다. 속도 낱말(`fast`, `snap`)과 시작·끝 구도를
  함께 적는다. 「dollies in」만 적으면 속도가 모델 마음대로다.
- **크게 치는 박(1박·5박의 히트, 포인트 동작)에 밀고 들어간다.** 대형이 드러나는 박, 이동이 시작하는 박에 뒤로 빠진다.
- **동작이 보이는 범위에서 민다.** 다리를 쓰는 동작(스텝 이동, 런지)은 풀숏에서 무릎 위 숏까지만, 손·상체 동작은 미디엄까지, 손가락 디테일이 보일 때까지 민다.
  한 줄에 머리부터 발끝까지 보이는 풀숏 장면을 하나 이상 둔다. 손끝과 발이 잘리면 안무가 읽히지 않는다.
- **챌린지 구간도 정면 각도는 지키되 움직인다.** 정면에서 풀숏과 무릎 위 숏 사이로 작게 밀고 뺀다. 따라 하는 사람이 동작을
  놓치지 않는 폭이다.
- 영상 모델 가이드 중에는 춤을 고정 와이드로 찍으라는 것도 있다. 빠른 카메라가 손발이 일그러지는 것을 가리기 때문이다
  ([Seedance.tv](https://www.seedance.tv/blog/ai-dance-video-prompt-examples)). 그 권고를 따르면 우리가 받은 「밋밋하다」가 된다.
  손발이 일그러지면 움직임을 빼지 말고 장면을 더 짧게 나눈다.

프롬프트에는 카메라 문장을 동작 문장과 떼어 장면마다 적는다. 「춤추는 사람 주위로 돈다」처럼 섞어 쓰면 누가 움직이는지 모호하다.

```text
The camera is never static: every shot has one fast camera move timed to the beat, alternating forward and back.
Shot 1, 0.00-1.85s, the camera snaps a fast dolly push-in from a frontal full shot to a knee-up shot on beat 1 and stops
sharply: they land the jump in a wide stance and punch both fists forward.
HARD CUT at 1.85s. Shot 2, 1.85-3.69s, the camera makes a quick pull-back from a medium shot to a frontal full shot on
beat 1, feet visible: they spread out into a V formation.
```

모델이 박에 맞춰 움직이는지는 미확인이다. 만든 뒤 `mv_timing.py sheet --fps 6` 으로 멤버의 키가 화면에서 커지거나 작아지는
칸을 잰다. 카메라가 거의 서 있으면 장면을 더 짧게 나누고 움직임 문장을 장면 문장 맨 앞에 둔다.

## 고르는 기준

1. **춤추는 장면인가.** 그렇다면 위의 박 밀고 빼기가 기본이다. 고정 카메라는 소리 빈 자리의 정지 포즈, 입을 맞추는 단독샷처럼
   멈춰 있어야 하는 장면에만 쓴다.
2. **누가 중심인가.** 파트 멤버 단독이면 클로즈업·미디엄. 셋이 함께면 와이드.
3. **구간 에너지.** 작은 구간은 느린 움직임, 큰 구간은 빠른 움직임(휩 팬, FPV, 원형 돌리).
4. **다음 컷으로 어떻게 넘어가나.** 렌즈를 덮는 장치, 휩 팬, 밀고 들어가기는 컷 경계를 숨긴다.

## 움직임 어휘

| 움직임 | 프롬프트 표현 | 쓰는 자리 |
|---|---|---|
| 박 밀고 빼기 | 장면마다 `fast dolly push-in` 과 `quick pull-back` 을 번갈아, 박에서 시작해 박에서 선다 | 춤추는 장면의 기본 |
| 히트 흔들기 | `on the hit the camera jolts with a short sharp shake` | 큰 강세 한 박 |
| 박에 밀기(펀치 인) | `fast dolly push-in on beat N from a full shot to a knee-up shot` | 포인트 동작, 강세 |
| 박에 빼기 | `quick pull-back on beat N to a frontal wide shot` | 대형이 드러나는 박, 이동이 시작하는 박 |
| 정면 고정 | `locked-off frontal shot, static, eye level` | 정지 포즈, 입을 맞추는 단독샷 |
| 천천히 밀기 | `slow push-in` | 춤 없는 장면에서 감정이 오르는 줄의 끝, 전환 직전 |
| 뒤로 빠지기 | `camera pulls back to a frontal wide shot` | 공간이나 다른 멤버를 드러낼 때 |
| 뒤로 물러나는 트래킹 | `backward tracking shot as she walks toward the camera` | 걸어 나오는 벌스 |
| 핸드헬드 | `handheld camera, subtle shake` | 랩, 거친 벌스 |
| 휩 팬 | `whip pan between her face and her hands` | 가사 줄이 바뀔 때, 멤버 사이 이동 |
| 스테디캠 군무 통과 | `steadicam gliding between the dancing members` | 대형 이동이 있는 후렴 |
| 원형 돌리 | `circular dolly shot orbiting the members clockwise` | 2절 후렴처럼 크게 가는 줄 |
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

- 한 장면에 움직임 둘을 섞으면(밀다가 돌기, 밀었다 빼기) 화면이 무너지거나 하나만 나온다. 둘이 필요하면 장면을 나눈다.
- 움직임의 시작·끝 구도를 함께 적는다. 「…에서 시작해 …로 끝난다」.
- 고정 카메라가 필요한 장면은 `static` 을 꼭 적는다. 적지 않으면 모델이 흔히 천천히 움직인다(미확인).
- 움직이는 장면은 움직임을 박과 함께 적는다. 카메라를 적지 않으면 화면이 제멋대로 흐르거나 서 버린다
  ([Pexo 비교](https://pexo.ai/blog/kling-ai-tips-better-results-8652), 한 사람의 시험이라 근거가 약하다).
- 「Dolly」「Crane」을 낱말 하나로 쓰지 말고 `dolly push-in shot`, `crane shot` 처럼 묶어 쓴다. 혼자 오면 고유명사로 읽힐 수 있다.
