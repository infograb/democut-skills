# 생성 구간의 프롬프트

생성 구간 하나에 프롬프트 하나다. 연기, 표정, 말투는 블록아웃에 없으므로 여기에만 있다. 영어로 쓰고 대사만 한국어로 둔다.
`image_prompt` 는 4,000자까지다.

## 짜임

1. **머리줄.** 길이, 비율, 장르, 샷 수를 맨 앞에 둔다([Higgsfield, Seedance prompting guide](https://higgsfield.ai/blog/seedance-prompting-guide)).
2. **블록아웃 문단.** 참고 영상에서 가져올 것과 가져오지 말 것. 「reference video 1」만 적으면 모델이 쓰임을 모른다
   ([liyue-aigc/seedance-2-5-video-director](https://github.com/liyue-aigc/seedance-2-5-video-director)).
3. **참고마다 할 일.** 장소 그림은 장소만, 캐릭터는 얼굴·머리·옷만 준다는 것을 적는다.
4. **결.** 모든 샷이 따를 빛, 색, 카메라, 질감 한 문단([aicontentskills/ai-video-storyboard-skill](https://github.com/aicontentskills/ai-video-storyboard-skill)).
5. **인물.** 사람마다 이름과 외모 한 줄. DemoCut 은 캐릭터의 `look_text` 를 영상 프롬프트에 붙이지 않는다
   ([`democut-drama.md`](democut-drama.md) 「인물」).
6. **샷.** `shot_plan.py beats` 의 시각 그대로 「0-4s Shot 1 (wide, 24mm)」 로 시작한다. 시각은 빈틈 없이 이어지고 합이 구간
   길이와 같다. 샷마다 카메라, 화면 방향, 행동 하나, 대사와 말투를 적고 끝에 그 샷의 고정 줄(빛, 누가 어디에 서 있는지)을
   다시 적는다([Emily2040/seedance-2.0](https://github.com/Emily2040/seedance-2.0)).
7. **금지.** 화면 글자, 자막, 로고 실존 인물 닮음, 샷리스트에 없는 사람.

소리 문장은 적지 않는다. DemoCut 이 대사 목록과 음악 금지 문장을 프롬프트 끝에 붙인다([`democut-drama.md`](democut-drama.md) 「대사와 소리」).

## 블록아웃 문단

```text
BLOCKOUT REFERENCE: video 1 is a rough grey 3D blockout of this exact sequence. Use it ONLY for where each
person stands and moves, which way they face, the camera position, lens and movement, and the moment each
shot cuts. The coloured pills are placeholders for the people: the pill with the black cap and navy band is
MINJI, the pill with the brown cap and grey band is JUNHO. Copy nothing else from it: no pills, no grey boxes,
no flat lighting, no stiff or robotic motion. Faces, bodies, clothes and acting come from the character
references and this text. The room comes from the location reference.
```

Thomas Lundström 은 이 문단을 프롬프트 도우미 스킬에 꼭 넣으라고 한다([7:17](https://www.youtube.com/watch?v=mx1yjt4k73o)).
Dan Kieft 는 「video 1 as a camera movement reference only」 한 문장으로 카메라를 맞췄다([3:17](https://www.youtube.com/watch?v=miIDu04N7_4)).
Curious Refuge 의 실험은 「3D 인물은 자리 표시이니 자세와 몸놀림을 베끼지 말라」를 적었다
([Curious Refuge](https://curiousrefuge.com/blog/how-to-control-ai-videos-with-blender-and-claude)).

## 예시

```text
12s 16:9 cinematic Korean drama scene, 3 shots, one apartment living room at dusk.

BLOCKOUT REFERENCE: … (위 문단)

REFERENCES: the location image is the living room, use it for the room only. The character references give
MINJI's and JUNHO's faces, hair and clothes only.

LOOK: naturalistic, soft window light fading to warm practical lamps, 35mm film texture, handheld only where
noted, shallow depth of field on close-ups.

PEOPLE: MINJI, late 20s woman, shoulder-length black hair, navy cardigan. JUNHO, early 30s man, short brown
hair, grey hoodie.

0-4s Shot 1 (wide, 24mm): slow push-in from the front door. MINJI comes in, drops her bag on the sofa, she
moves screen left to right. Lock: dusk window light from the left, JUNHO is in the kitchen at the back right.
4-8s Shot 2 (medium close-up, 50mm): static. MINJI stops and looks screen right toward the kitchen, tired,
half-smiling, says "어, 왔어?". Lock: same light, MINJI by the sofa, JUNHO off screen right.
8-12s Shot 3 (medium close-up, 50mm): static, reverse angle. JUNHO looks screen left at MINJI, pauses, puts
the cup down without a word. Lock: warm lamp behind JUNHO, MINJI off screen left.

Never: on-screen text, subtitles, logos, extra people, real celebrity likeness.
```

예시의 `dialogue` 에는 「어, 왔어?」 한 줄만 넣는다. 말하는 사람이 MINJI 하나라서 DemoCut 이 붙이는 「the on-screen
character speaks these lines」 와 어긋나지 않는다.

## 고칠 때

- 초안의 오류는 원인별로 고친다. 프롬프트로 고칠 것(소품 개수, 행동, 말투), 자산으로 고칠 것(장소가 비었다, 잎이 날리지
  않는다), 블록아웃으로 고칠 것(모양, 동선, 카메라)이 다르다([Thomas Lundström, 11:07~12:59](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
- 연기가 밋밋하면 블록아웃이 아니라 프롬프트의 연기 문장을 바꾼다. 「더 미친 듯이」 처럼 한 줄을 고쳐 두 번째 초안에서
  원하는 연기가 나온 사례가 있다([Thomas Lundström, 8:29](https://www.youtube.com/watch?v=mx1yjt4k73o)).
- 한 번에 하나만 바꾸고 무엇을 바꿨는지 구간마다 적어 둔다. 여럿을 함께 바꾸면 무엇이 고쳤는지 모른다.
