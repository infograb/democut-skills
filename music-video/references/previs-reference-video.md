# 3D 프리비즈를 참고 영상으로

글로 적은 자리·박·카메라가 지켜지지 않는 컷은, 같은 컷을 3D 인형으로 먼저 만들어 영상 모델에 참고 영상으로 준다.

## 언제 쓰나

글만 적은 군무 컷에서 잰 실패가 이 방법의 근거다(Seedance 2.5, 8초, 세 명, A7 여러 버전).

- 의상은 다 맞는데 가운데와 왼쪽 멤버가 바뀌었다.
- 신발 클로즈업에서 0.92초 전신으로 빠지라고 적은 오프닝이 약 1.85초에 전신이 됐다.
- 박마다 다른 손 모양 16개를 적었는데 거의 나오지 않고 같은 팔 모양이 2~3박 이어졌다. 한 박씩 엇갈리게 적은 동작은
  셋이 같이 했다.

입은 옮기지 못한다. 프리비즈 인형에는 입이 없다. 부르는 줄은 [`democut-mv.md`](democut-mv.md) 「입을 맞춰 부르는 줄(단독샷)」대로
만든다.

## DemoCut 에서 받는 것

2026-11-21 배포 기준이다. 값은 `democut_get_options` 의 `video_models[].reference_video` 에서 다시 확인한다.

- 칸은 `reference_video_asset_ids`(영상 자산 id 목록)다. `democut_upload_asset(kind="video")` 로 올린 id 를 넣는다.
- Seedance 2.5 는 영상 10개, 한 개 2~30초, 합 30초까지 받는다. Seedance 2.5 Flash 는 5개, 나머지 모델은 3개·2~15초·합 15초다.
- 첫·끝 장면 그림과는 함께 쓰지 못한다(`SPEC_CONFLICT`). 참고 이미지, 참고 인물, 곡(`host: "music"`)과는 함께 쓴다.
- 8초 720p 컷에 8초 참고 영상을 넣은 견적은 3,118원, 빼면 2,616원이었다(요율 v5). 참고 영상의 입력 토큰이 따로 붙는다.
- Seedance 로 보낼 때 영상은 BytePlus 자산으로 등록돼 심사를 거친다. 참고 이미지와 같은 길이다.

## 만드는 법

1. **컷을 데이터로 적는다.** 박 n 의 프레임은 `round(n × 60 / BPM × fps)` 다(130 BPM·24fps 면 0, 11, 22, 33, 44 …).
   멤버의 자리와 의상 색, 대형이 바뀌는 박, 카메라 숏(거리·높이·바라보는 높이)과 그 숏에 도착하는 박, 박마다 동작을 적는다.
   동작의 박은 [`choreography.md`](choreography.md) 「곡의 강세에서 동작을 짠다」의 강세 지도에서 고른다.
2. **Blender 로 렌더한다.** `Blender -b --factory-startup --python <스크립트> -- --spec <컷.json>` 처럼 창 없이 돌린다
   (Blender 5.0.1, Workbench, 1280×720, 24fps, H.264 yuv420p, 소리 없음, 화면 글자 없음).
   - 인형은 의상 색으로 가른다. A7 에서는 흰 바지와 검은 포니테일(LEFT), 라벤더 상의와 금발(CENTER), 검은 무릎 부츠와
     빨간 머리(RIGHT)였다. 프롬프트도 자리를 이 색으로 부른다.
   - 동작은 박에 3프레임 안에 도착한다. 큰 동작은 예비 동작과 여운을 두고, 머리카락은 고개보다 늦게 따라오게 한다.
   - 손은 손바닥 가운데를 목표로 팔을 풀고, 손이 얼굴을 덮는 프레임이 없는지 잰다.
   - 카메라는 숏을 박에 키로 넣고 모션 블러를 쓰지 않는다.
   - 샌드박스 안에서는 Blender 가 그래픽(Metal) 초기화에서 죽은 적이 있다(Codex 샌드박스 실측). 그때는 샌드박스 밖에서 렌더한다.
3. **올리기 전에 확인한다.** 박마다 한 칸 격자(`mv_timing.py sheet <영상> <격자.jpg> --fps 0 --bpm <BPM>`), 곡을 입힌 확인용
   파일, 그리고 수치(첫 전신 프레임, 모든 프레임에서 머리가 화면 안인지, 손이 얼굴을 덮는 프레임 수, 디딘 발이 미끄러지는지)를 본다.

## 프롬프트

참고 영상이 무엇이고 무엇을 따르지 말아야 하는지를 맨 앞 문단에 둔다. A7 에서 쓴 문단이다.

```text
MOTION REFERENCE: the reference video is a rough 3D previs of THIS exact shot, timed to the same music. Follow it frame
for frame: where each dancer stands (LEFT = the white-pants black-ponytail figure, CENTER = the lavender-top blonde figure,
RIGHT = the black-knee-boot red-hair figure), every arm, hand position, knee bend and step and the beat it lands on, and the
camera path. Do NOT copy its look: no 3D cartoon figures, no plastic or doll skin, no blank faces, no blue-grey studio.
Faces, hair and outfits come from the character references; the set comes from the set reference and this text.
```

그 뒤는 평소 순서대로 장면, 의상, 맨손 문장, 박마다의 동작, 금지 목록을 적는다([`democut-mv.md`](democut-mv.md) 「프롬프트의 짜임」).

`image_prompt` 는 4,000자까지다. 넘쳐서 줄일 때는 참고 영상이 이미 담은 카운트별 몸 동작부터 줄이고, 손 모양, 세트 전환,
통과했던 카메라 문장은 남긴다.

## 만든 뒤 확인

```
python3 scripts/mv_timing.py follow previs.mp4 result.mp4 --from 22
```

프레임마다 앞 프레임과의 밝기 차(움직임 양)를 두 영상에서 재고, 결과를 몇 프레임 밀었을 때 둘이 가장 닮는지(상관 r)를 낸다.
r 이 0.5 아래면 결과가 참고 영상을 따르지 않은 것으로 보고, `sheet` 격자로 같은 프레임을 맞대어 본다. `--from` 은 오프닝
클로즈업처럼 두 영상의 화면 크기가 크게 다른 앞부분을 뺄 때 쓴다.

## 결과

실측(2026-11-22, A7 후렴 8초, Seedance 2.5 720p, 곡을 들려줌, 멤버 셋 + 세트 참고 + 8초 프리비즈, 3,118원, 한 번 생성).

- **자리.** 왼쪽부터 이담, 하이나, 신더가 8초 내내 맞았다. 사선(이담이 앞), 하이나가 한 걸음 나온 대형, 일자가 모두 나왔다.
  글만 적은 같은 컷(v13)은 이담과 하이나가 바뀌어 있었다.
- **박.** `follow` 로 22~192프레임을 재니 시차 0 에서 r=0.79 였다(앞 22~89 는 0.83, 89~166 은 0.67). 같은 프리비즈와 v13 은
  r=0.09 였다. 깊이 앉기(2.77초), 반 바퀴 돌기(3.23초), 차례로 몸 접기(3.69·4.15·4.62초)가 그 프레임에 나왔다.
- **카메라.** 0.92초(22프레임)에 머리부터 발까지 전신이었다. 그 뒤 허벅지와 전신 사이를 오가고, 멈춘 6.92초부터 끝까지
  카메라만 세 사람 쪽으로 다가갔다. 프리비즈의 경로와 같다.
- **손.** 6.00초 볼 옆 갈고리가 셋 모두 나와 끝까지 남았고, 얼굴을 가리지 않았다. 금지한 하트, 손가락 V 는 한 번도 나오지
  않았다(글만 적은 컷에서는 V 세 번, 끝 박 하트 셋). 5.54초 작은 고리는 손이 가슴 앞에 모이기만 하고 고리로 읽히지 않았다.
- **모양.** 인형의 모양은 묻어나지 않았다. 얼굴, 머리, 의상은 캐릭터 시트대로, 세트는 창고 참고대로 나왔다.
- **안 된 것.** 세트 전환은 글대로 되지 않았다. 0.92초에 이미 창고 뒷벽이 있었고, 슬라임은 1.4~2.9초 동안 뒷벽 앞에
  번들거리는 막으로 섰다가 3.25초에 무광 벽이 됐다. 프리비즈에는 세트가 없어서 이 부분은 글로만 정해진다. 프리비즈에
  솟는 벽을 넣으면 따라올지는 미확인이다.
