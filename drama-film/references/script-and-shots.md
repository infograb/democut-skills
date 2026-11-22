# 콘셉트, 대사, 샷리스트

## 콘셉트를 함께 다듬기

사용자의 씨앗이 먼저다. 씨앗이 없으면 Claude 가 안을 늘어놓기 전에 아래를 묻는다.

- 누가 보는가, 길이는 얼마인가, 화면 비율은 무엇인가(DemoCut 프로젝트 비율은 나중에 바꾸지 못한다).
- 주인공은 누구이고 무엇을 원하는가. 무엇이 막는가. 끝에서 무엇이 바뀌는가.
- 광고면 제품의 어떤 점 하나를 보여 주는가. 한 제작자는 헤드폰 광고에서 노이즈 캔슬링 하나만 골라 「시끄러운 하루에서
  헤드폰을 쓰면 다른 세계로 빠져나간다」는 구조로 키웠다([Thomas Lundström, 2:26~3:32](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
- 화면의 결(시대, 빛, 색, 카메라 스타일, 참고할 영화나 광고)은 무엇인가.

Claude 의 첫 안이 씨앗을 다른 방향으로 틀면 그대로 두지 않고 사용자와 한 요소씩 정한다. 정한 것은 `concept.md` 에
한 쪽으로 적는다. 장면 목록, 인물 목록(이름, 나이, 외모 한 줄, 성격 한 줄), 장소 목록, 결이다.

## 대사

- 대사를 블록아웃보다 먼저 확정한다. 블록아웃은 대사가 들어갈 자리와 멈춤을 남겨야 한다
  ([Thomas Lundström, 5:05](https://www.youtube.com/watch?v=mx1yjt4k73o)).
- 사람이 실제로 말하듯 쓴다. 군말, 끊기, 말 자르기를 넣으면 덜 AI 같다(같은 영상 11:34). 문어체 완결 문장을 피한다.
- 한 샷에 말하는 사람 한 명, 대사 한 줄이다. 길면 줄을 나눠 다음 샷으로 넘기거나 줄인다. 모델에게 빠르게 말하게 하느니
  대사를 줄이라는 지침이 여럿 있다([liyue-aigc/seedance-2-5-video-director](https://github.com/liyue-aigc/seedance-2-5-video-director),
  [Kapwing](https://www.kapwing.com/resources/how-to-prompt-seedance-2-5-a-guide-for-ai-video-creators/)).
- 대사가 들어가는지는 `shot_plan.py check` 가 어림으로 잰다. 한글 음절 수를 `speech_rate`(기본 초당 5음절)로 나누고
  0.5초를 더한다. 영어 낱말은 하나에 2음절로 어림한다. 이 속도는 재지 않은 어림값이다. 첫 초안에서 실제 말 길이를 재서 `shots.json` 의 `speech_rate` 를 고친다.
- 반응이 대사보다 많이 말한다. 반응은 감정 하나와 몸의 단서 하나로 적는다(「멈칫하고 컵을 내려놓는다」)
  ([Emily2040/seedance-2.0](https://github.com/Emily2040/seedance-2.0)).

## 샷리스트

`shots.json` 이 샷리스트의 원본이다. 블록아웃, 프롬프트 시각, 견적이 모두 여기서 나온다.

```json
{
  "fps": 24,
  "speech_rate": 5.0,
  "shots": [
    {"id": "S1", "generation": 1, "seconds": 4, "size": "wide", "lens_mm": 24,
     "camera": "slow push-in from the doorway", "action": "민지 enters, drops her bag on the sofa",
     "location": "living-room"},
    {"id": "S2", "generation": 1, "seconds": 3, "size": "medium close-up", "lens_mm": 50,
     "camera": "static", "action": "민지 looks toward the kitchen", "speaker": "민지", "line": "어, 왔어?"}
  ]
}
```

- `generation` 은 한 번에 만드는 구간 번호다. 같은 구간의 샷은 이어서 적고 합은 4~15초 정수 초다.
- 같은 구간의 샷은 같은 장소, 같은 시간대로 묶는다. 장소가 바뀌면 구간을 나누고 장소 그림도 따로 둔다.
- `camera_moves_during_line: true` 를 적은 샷은 `check` 가 경고한다(대사 동안 카메라를 옮기면 따라가지 않았다).
- 샷 길이는 대사가 정하고 대사가 없으면 행동 하나가 끝나는 길이다. 한 샷에 행동 하나를 적고 나머지 사람은 그 자리에서
  산다([Emily2040/seedance-2.0](https://github.com/Emily2040/seedance-2.0)).
- 샷마다 앞 샷에서 무엇을 이어받는지(시선 방향, 손에 든 것, 자리)를 `action` 에 적는다. 영상 모델은 프롬프트가 다시 말하지
  않은 것을 컷 너머로 기억하지 않는다(같은 출처).

## 영화 문법

AI 컷에서도 그대로 쓴다. 샷리스트에서 정하고 프롬프트에서 샷마다 다시 적는다.

- **설정샷 다음 커버리지.** 장면의 첫 샷은 어디인지 보이는 와이드다. 얼굴 클로즈업으로 열었던 첫 블록아웃을 와이드에서
  카메라가 내려오는 샷으로 바꾼 사례가 있다([Thomas Lundström, 5:41](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
- **렌즈.** 설정샷은 넓은 렌즈(24mm 안팎), 클로즈업은 좁은 렌즈(50~85mm)다
  ([Thomas Lundström, 11:34](https://www.youtube.com/watch?v=mx1yjt4k73o)). 렌즈는 블록아웃 카메라에도 같은 값으로 넣는다.
- **180도 선.** 두 사람을 잇는 선의 한쪽에만 카메라를 둔다. 샷마다 「민지는 화면 오른쪽을 본다」처럼 방향을 적는다.
- **숏-리버스-숏과 시선.** 말하는 사람마다 샷 하나, 시선 방향을 서로 맞춘다. 보는 샷 뒤에 본 것을 보여 주는 샷을 둔다.
- **액션에서 자르기.** 컷 경계를 움직임이 끝나는 순간에 둔다(문을 닫는 손, 앉는 몸).
- **반응 샷.** 중요한 대사 뒤에는 듣는 사람의 얼굴을 둔다. 대사가 없는 반응 샷은 말소리 문제를 피하는 길이기도 하다.

## 샷리스트를 넘기기 전에

```bash
python3 -I <스킬>/scripts/shot_plan.py check shots.json
python3 -I <스킬>/scripts/shot_plan.py beats shots.json
```

`check` 가 오류 없이 지나고 경고(두 사람의 대사가 한 구간, 대사 중 카메라 이동)는 사용자와 이야기해 남길지 정한다.
`beats` 의 블록아웃 프레임을 그대로 Blender 마커로 쓴다.
