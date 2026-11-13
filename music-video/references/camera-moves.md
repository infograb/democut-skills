# 카메라 움직임

한 줄(컷)에 움직임 하나를 고른다. 무엇을 보여 줄 줄인지가 먼저고 움직임은 그것을 돕는다.

## 고르는 기준

1. **안무 전체를 보여 줄 줄인가.** 군무·챌린지 줄은 정면 고정 풀숏이나 아주 느린 밀기. 카메라가 움직이면 동작이 안 보인다.
2. **누가 중심인가.** 파트 멤버 단독이면 클로즈업·미디엄. 셋이 함께면 와이드.
3. **구간 에너지.** 작은 구간은 느린 움직임, 큰 구간은 빠른 움직임(휩 팬, FPV, 원형 돌리).
4. **다음 컷으로 어떻게 넘어가나.** 렌즈를 덮는 장치, 휩 팬, 밀고 들어가기는 컷 경계를 숨긴다.

## 움직임 어휘

| 움직임 | 프롬프트 표현 | 쓰는 자리 |
|---|---|---|
| 정면 고정 풀숏 | `locked-off frontal full shot, static, eye level` | 군무, 챌린지 |
| 천천히 밀기 | `slow push-in` | 감정이 오르는 줄의 끝, 전환 직전 |
| 뒤로 빠지기 | `camera pulls back to a frontal wide shot` | 공간이나 다른 멤버를 드러낼 때 |
| 뒤로 물러나는 트래킹 | `backward tracking shot as she walks toward the camera` | 걸어 나오는 벌스 |
| 핸드헬드 | `handheld camera, subtle shake` | 랩, 거친 벌스 |
| 휩 팬 | `whip pan between her face and her hands` | 가사 줄이 바뀔 때, 멤버 사이 이동 |
| 스테디캠 군무 통과 | `steadicam gliding between the dancing members` | 대형 이동이 있는 후렴 |
| 원형 돌리 | `circular dolly orbiting the members` | 2절 후렴처럼 크게 가는 줄 |
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

- 한 컷에 움직임 둘을 섞으면(밀다가 돌기) 하나만 나오기 쉽다(미확인, 경험칙). 둘이 필요하면 컷을 나눈다.
- 움직임의 시작·끝 구도를 함께 적는다. 「…에서 시작해 …로 끝난다」.
- 고정 카메라가 필요한 줄은 `static` 을 꼭 적는다. 적지 않으면 모델이 흔히 천천히 움직인다(미확인).
