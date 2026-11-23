# 생성 구간의 프롬프트

생성 구간 하나에 프롬프트 하나다. 연기, 표정, 말투는 블록아웃에 없으므로 여기에만 있다. 영어로 쓰고 대사만 한국어로 둔다.
`image_prompt` 는 4,000자까지다.

## 짜임

Thomas Lundström 의 blockout-kit(MIT) 가 만드는 뼈대 순서다(kit `lib/blockout/prompt.py`, `skills/blockout/SKILL.md`
「Seedance run」).

1. **머리줄.** 길이, 비율, 장르, 장소, 샷 수를 맨 앞에 둔다([Higgsfield, Seedance prompting guide](https://higgsfield.ai/blog/seedance-prompting-guide)).
2. **블록아웃 줄.** 「Video 1 is a coarse-blockout reference. Follow it exactly for camera position, camera movement, lens
   perspective and cut timing, and for where each person is, how large they are in frame, which way they face and when they
   move. Do not copy how it looks.」 「reference video 1」만 적으면 모델이 쓰임을 모른다
   ([liyue-aigc/seedance-2-5-video-director](https://github.com/liyue-aigc/seedance-2-5-video-director)).
3. **색 안내(Colour key).** 알약마다 띠의 색과 사람 이름, 참고 번호를 한 줄씩 적는다. 소품 상자도 무엇인지 적는다. 회색
   덩어리는 「The grey geometry is the set, … of Image 1」로 장소 그림과 묶고 블록아웃에 있는 구조물을 나열한다.
4. **규칙(Rules).** kit 의 문장을 그대로 쓴다. 알약은 몸 동작을 싣지 않는다, 알약·띠·회색 덩어리는 결과에 나오지 않는다,
   회색 느낌을 버린다, 참고 인물은 얼굴만 주고 자세와 배경은 주지 않는다. 장소 그림은 장소의 배치와 재질만 준다는 줄을
   더한다.
5. **시각(Timing).** 샷 수와 구간 길이, 컷 시각을 적는다. 「Hard cut at exactly 4.00 s. The cut matches Video 1 to the
   frame. No dissolves.」 시각은 `shot_plan.py beats` 의 샷 경계를 쓴다.
6. **샷.** 샷마다 머리줄(「Shot 1, 4 s, wide, 24 mm, slow push in」) 다음에 일어나는 일을 순서대로 적는다. 샷 안에는 시각을
   적지 않는다(kit 「A multishot gets one header per shot with its duration, and no timestamps inside a shot」). 누구를
   보는지는 화면 방향과 이름으로 적고 렌즈를 보지 않는다는 말을 함께 둔다(아래 「실측」의 시선).
7. **렌즈와 결(Lens and look).** 샷마다 렌즈와 피사계 심도, 빛과 색, 질감을 적고 셔터 줄을 넣는다. 「Real 24 fps with a
   180-degree shutter: natural motion blur, every frame blending smoothly into the next. No frame interpolation, no
   morphing, no jitter.」 kit 의 기본 머리말도 「Camera: Physical cine lens. 180° shutter motion blur.」와 「Technical:
   24fps smooth motion … No jitter.」를 적는다(kit `skills/shotlist-director-thomas/SKILL.md`). `no motion blur` 는 쓰지
   않는다.
8. **끝줄.** 소리와 금지 목록. 「Natural sound only, no music.」은 kit 가 음악을 원하지 않을 때 넣으라는 줄이다. DemoCut 도
   대사가 있으면 음악 금지 문장을 붙인다([`democut-drama.md`](democut-drama.md) 「대사와 소리」).

참고는 종류와 번호로 부른다(Image 1, Video 1). 번호는 DemoCut 이 보내는 순서다. 장소 그림(`reference_asset_ids`)이 먼저,
그다음 `reference_character_ids` 순서로 인물의 캐릭터 시트다([`democut-drama.md`](democut-drama.md) 「컷」). 장소 하나와
두 사람이면 장소가 Image 1, 첫 사람이 Image 2, 둘째가 Image 3 이다.

참고 인물을 넣으면 외모 문단은 따로 적지 않아도 된다. A2 는 외모 문단 없이 시트대로 나왔다. 참고 인물이 없으면 사람마다
나이, 머리, 옷을 한 줄로 적는다. DemoCut 은 캐릭터의 `look_text` 를 영상 프롬프트에 붙이지 않는다
([`democut-drama.md`](democut-drama.md) 「인물」).

## 예시

drama A2 에 쓴 프롬프트다(8초, 두 샷, 2,870자쯤). 결과는 아래 「실측」.

```text
8 s 16:9 Korean drama scene in a small apartment living room and kitchen at dusk, 2 shots.

Video 1 is a coarse-blockout reference. Follow it exactly for camera position, camera movement, lens perspective and cut
timing, and for where each person is, how large they are in frame, which way they face and when they move. Do not copy
how it looks.

Colour key
The capsule with the black cap and navy band is 민지 (Minji), Image 2.
The capsule with the brown cap and grey band is 준호 (Junho), Image 3.
The small brown box is Minji's brown shoulder bag.
The grey geometry is the set, the living room and kitchen of Image 1: front door in the left wall, sofa in the middle,
kitchen counter with a pot along the back wall on the right, window at the back left, a floor lamp. There is no coffee
table: the floor between the door and the sofa is open.

Rules
The capsules carry no body motion. Give every character natural human movement that fits the action: real steps, weight
shifts, gestures, head turns, breathing. Each character keeps the position, path, speed and facing of their capsule.
No capsule, stripe, orange line, coloured block or grey blockout geometry may ever appear in the result.
Discard the grey look completely. Lighting, colour, texture and set detail come from this text and the reference images.
Use each character reference for identity: the face for the face only, never the pose or the background. Image 1 controls
the room's geography and materials only; its framing is never reproduced.

Timing
2 shots in one clip of 8.00 s. Hard cut at exactly 4.00 s. The cut matches Video 1 to the frame. No dissolves.

Shot 1, 4 s, wide, 24 mm, slow push in
Minji comes in through the front door at screen left, tired after work, walks to the sofa and drops her bag on it, then
turns back toward the room. Junho stands at the kitchen counter at the back right, his back half turned, stirring a pot.

Shot 2, 4 s, medium close-up, 50 mm, locked off
Minji by the sofa turns her head screen right toward the kitchen, surprised, then breaks into a half-smile and says,
lightly teasing, "뭐야, 오늘 일찍 왔네?" Junho is soft and out of focus at the far right or off screen.

Lens and look
Shot 1: 24 mm on full frame, deep focus. Shot 2: 50 mm, shallow depth of field, soft background.
Photoreal live-action film, not a 3D render, not a game engine. Soft dusk window light fading to a warm floor lamp, a
lived-in apartment with personal objects and a little mess, 35 mm film grain. Real 24 fps with a 180-degree shutter:
natural motion blur, every frame blending smoothly into the next. No frame interpolation, no morphing, no jitter. Real
skin texture, no plastic sheen.

Natural sound only, no music. No on-screen text, subtitles, logos, extra people or celebrity likeness.
```

`dialogue` 에는 「뭐야, 오늘 일찍 왔네?」 한 줄만 넣었다. 말하는 사람이 민지 하나라서 DemoCut 이 붙이는 「the on-screen
character speaks these lines」 와 어긋나지 않는다.

## 실측

같은 블록아웃(8초, 두 샷, 4.00초 컷, 민지와 준호의 알약, 가방 상자)으로 두 번 만들었다(2026-11-22, Seedance 2.5 480p,
`host: "model"`, 대사 한 줄, 한 번에 1,458원).

- **A.** 「BLOCKOUT REFERENCE: … Use it ONLY for …」 문단과 외모 문단을 쓰고 참고 인물과 장소 그림은 넣지 않았다. 준호는
  8초 내내 회색 알약 그대로 부엌에 서 있었고 민지는 아랫몸이 하늘색 알약이었다.
- **A2.** 위 예시 프롬프트에 장소 그림(Image 1)과 두 사람의 캐릭터 시트(Image 2, 3)를 넣었다. 알약, 띠, 회색 덩어리가
  한 프레임도 나오지 않았다. 민지는 문으로 들어와 소파에 가방을 내려놓고 돌아섰고 준호는 내내 냄비를 저었다. 컷은
  3.96초(블록아웃 4.00초)에 바뀌었고 대사는 적은 그대로였다(whisper 로 확인).
- **A2 의 흠, 시선.** 둘째 샷에서 민지가 부엌(화면 오른쪽)이 아니라 렌즈를 보고 말했다. 「turns her head screen right
  toward the kitchen」만으로는 모자랐다. 다음에는 「she looks at Junho off screen right and never at the lens」처럼 누구를
  보는지와 렌즈를 보지 않는다는 말을 함께 적는다(아직 시험 전).
- **A2 의 흠, 장소.** 장소 그림이 블록아웃에 없는 탁자를 더했고 영상에도 탁자가 나왔다. 「There is no coffee table」 줄보다
  그림이 이겼다. 민지는 탁자를 비켜 걸었다. 장소 그림은 블록아웃 스틸과 맞대 보고 다르면 그림을 다시 만든다.

## 고칠 때

- 초안의 오류는 원인별로 고친다. 프롬프트로 고칠 것(소품 개수, 행동, 말투, 시선), 자산으로 고칠 것(장소가 비었다, 장소
  그림에 없는 가구가 있다), 블록아웃으로 고칠 것(동선, 카메라, 컷 시각)이 다르다
  ([Thomas Lundström, 11:07~12:59](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
- 연기가 밋밋하면 블록아웃이 아니라 프롬프트의 연기 문장을 바꾼다. 「더 미친 듯이」 처럼 한 줄을 고쳐 두 번째 초안에서
  원하는 연기가 나온 사례가 있다([Thomas Lundström, 8:29](https://www.youtube.com/watch?v=mx1yjt4k73o)).
- 한 번에 하나만 바꾸고 무엇을 바꿨는지 구간마다 적어 둔다. 여럿을 함께 바꾸면 무엇이 고쳤는지 모른다. A 에서 A2 로는
  참고 그림, 블록아웃 줄, 규칙, 셔터 줄을 함께 바꿨으므로 어느 것이 알약을 없앴는지는 가르지 못했다.
