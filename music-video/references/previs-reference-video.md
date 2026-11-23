# 3D 블록아웃을 참고 영상으로

글로 적은 자리·박·카메라가 지켜지지 않는 컷은 같은 컷을 3D 블록아웃으로 먼저 만들어 영상 모델에 참고 영상으로 준다.
블록아웃은 자리, 이동, 대형, 보는 방향, 세트의 모양과 생기는 시각, 카메라만 정한다. 춤, 낮아지는 동작, 손, 표정은
프롬프트와 곡이 정한다.

## 언제 쓰나

글만 적은 군무 컷에서 잰 실패가 이 방법의 근거다(Seedance 2.5, 8초, 세 명, A7 여러 버전).

- 의상은 다 맞는데 가운데와 왼쪽 멤버가 바뀌었다.
- 신발 클로즈업에서 0.92초 전신으로 빠지라고 적은 오프닝이 약 1.85초에 전신이 됐다.
- 박마다 다른 손 모양 16개를 적었는데 거의 나오지 않고 같은 팔 모양이 2~3박 이어졌다. 한 박씩 엇갈리게 적은 동작은
  셋이 같이 했다.

입은 옮기지 못한다. 부르는 줄은 [`democut-mv.md`](democut-mv.md) 「입을 맞춰 부르는 줄(단독샷)」대로 만든다.

## 블록아웃은 몸 동작을 보이지 않는다

영상 모델은 참고 영상에 보이는 몸 동작을 그대로 따른다. 그래서 블록아웃에 넣은 연기는 결과의 연기가 된다.

- A7 v6 는 실제 비율의 리깅 마네킹(MPFB)이 안무 전체를 추게 하고 프롬프트에 「every rib, hip, shoulder … follow it
  frame for frame」을 적었다. 결과는 프리비즈를 r=0.90 으로 따랐고 마네킹의 흠도 그대로 옮겼다. 사용자는
  「자세가 엉거주춤하고 클레이 애니메이션처럼 프레임이 안 맞는다」고 했다. 마네킹을 재 보니 골반이 평균 14cm 내려가
  있었다. 키는 3프레임마다 있었고 손 모양이 1초에 5번 바뀌었다(곡은 1초에 2.2박).
- A7 v9b 는 알약에 막대 팔과 손판을 달아 히트 박마다 손이 그 자리로 가게 하고 앉는 박에는 알약 높이를 줄였다. 막대
  손은 몇 프레임 동안 프레임마다 20~34cm 움직였다가 오래 멈췄고(66~78, 123~140, 157~192프레임) 144→145프레임에는 한
  프레임에 약 85cm 뛰었다. 결과의 멤버도 같은 구간에서 멈춰 섰고 머리 위 자세로 서 있다가(132~141프레임) 약 3프레임
  만에 Squish 로 꺾였다. 다리, 골반, 상체는 거의 움직이지 않고 팔만 움직였다. 사용자는 다시 클레이 애니메이션 같다고 했다.
- 블록아웃의 모양도 새어 나간다. 눈꺼풀을 감은 마네킹 얼굴을 쓴 v6 에서는 끝 클로즈업에서 셋 중 둘이 눈을 감았다.
  다른 제작자의 광고에서는 블록아웃의 다이아몬드 모양 꽃이 결과에 그대로 나왔다
  ([Thomas Lundström, 12:10](https://www.youtube.com/watch?v=jc0Qh09Qrlo)). v12 에서는 쐐기 모양으로 솟는 벽이 뾰족한
  슬라임 기둥으로 나왔다(1.7~2.0초).
- 같은 제작자가 공개한 blockout-kit(MIT) 는 이렇게 적는다. 「Seedance copies whatever body motion the reference shows, so
  the stand-in must show none. A rigid striped capsule gives position, scale, facing and timing only.」 몸짓은 프롬프트가
  준다(kit `skills/blockout/SKILL.md`). kit 의 팔은 총을 겨누는 방향만 보이는 굳은 막대이고 고개는 보는 방향만 돌린다.
  둘 다 다른 몸 동작은 없다(kit `docs/shotfile.md`). 춤의 팔을 보일 방법은 kit 에 없다.
- 프롬프트에는 참고 영상의 쓰임을 한정하는 줄을 넣는다([Dan Kieft, 3:17](https://www.youtube.com/watch?v=miIDu04N7_4)).
  연기가 밋밋하면 블록아웃이 아니라 프롬프트를 고친다([Thomas Lundström, 8:29](https://www.youtube.com/watch?v=mx1yjt4k73o)).

## DemoCut 에서 받는 것

2026-11-22 배포 기준이다. 값은 `democut_get_options` 의 `video_models[]` 에서 다시 확인한다.

- 칸은 `reference_video_asset_ids`(영상 자산 id 목록)다. `democut_upload_asset(kind="video")` 로 올린 id 를 넣는다.
- Seedance 2.5 는 영상 10개, 한 개 2~30초, 합 30초까지 받는다. Seedance 2.5 flash 는 5개를 받고 720p 까지이며
  곡(참고 오디오)을 받지 못한다. 나머지 모델은 3개·2~15초·합 15초다.
- 첫·끝 장면 그림과는 함께 쓰지 못한다(`SPEC_CONFLICT`). 참고 이미지, 참고 인물, 곡(`host: "music"`)과는 함께 쓴다.
- 프롬프트는 참고를 종류와 번호로 부른다(Image 1, Video 1, Audio 1). 번호는 같은 종류 안의 순서다(BytePlus Seedance
  문서). DemoCut 은 `reference_asset_ids` 의 그림을 먼저 보내고 그 뒤에 `reference_character_ids` 순서로 멤버마다 고른
  사진의 캐릭터 시트를 보낸다(democut-app `services/cuts.py`). 창고 그림 하나와 멤버 셋이면 창고가 Image 1, 멤버가
  Image 2~4 다. 블록아웃은 Video 1, `host: "music"` 의 곡은 Audio 1 이다.
- 값은 토큰으로 매기고 참고 영상도 결과와 같은 해상도로 토큰을 센다. 8초 컷에 8초 참고 영상을 넣은 견적이다
  (2026-11-22, 요율 v5, `democut_estimate_cuts` 에 spec 을 주면 초안을 바꾸지 않고 값만 낸다).

  | 모델 | 720p | 480p |
  | --- | --- | --- |
  | Seedance 2.5 | 3,118원 | 1,458원 |
  | Seedance 2.5 flash | 2,100원 | 984원 |

  참고 영상을 빼면 Seedance 2.5 720p 가 2,616원이었다. 같은 모델에 곡(`host: "music"`)을 실어도 값은 같았다.
- Seedance 로 보낼 때 영상은 BytePlus 자산으로 등록돼 심사를 거친다. 참고 이미지와 같은 길이다.

## 만드는 법

1. **컷을 데이터로 적는다.** 박 n 의 프레임은 `round(n × 60 / BPM × fps)` 다(130 BPM·24fps 면 0, 11, 22, 33, 44 …).
   멤버의 자리, 대형이 바뀌는 박, 카메라 숏(거리·높이·바라보는 높이)과 그 숏에 도착하는 박을 적는다.
   대형의 간격은 [`choreography.md`](choreography.md) 「간격은 그 대형에서 하는 가장 큰 동작으로 정한다」대로 잡는다.
   가사 동작과 낮아지는 박은 블록아웃이 아니라 프롬프트에 적는다. 단어는 `mv_timing.py lyrics` 로 박에 놓고
   [`choreography.md`](choreography.md) 「가사에서 동작으로」대로 뜻을 몸으로 옮긴다.
2. **알약을 세운다.** 아래 「알약」.
3. **Blender 로 만든다.** Workbench, 1280×720, 24fps, H.264 yuv420p, 소리 없음, 화면 글자 없음. 길이는 정수 초다.
   Codex 에게 맡길 때는 아래 「Codex 가 Blender 를 쓰는 법」.
   - 세계는 회색이고 색은 알약에만 있다. 벽은 중간에서 어두운 회색으로 둔다. 화면 양쪽에 밝고 큰 면이 있으면 생성이
     깨진다(kit `skills/blockout/SKILL.md`). 세트가 컷 안에서 바뀌면 그 벽도 회색 덩어리로 넣는다. v11·v12 에서는
     블록아웃 벽이 솟는 자리와 시각에 슬라임이 솟아 창고가 됐다.
   - 카메라는 숏을 박에 키로 넣는다. 블록아웃 렌더에는 모션 블러를 넣지 않는다. 결과의 블러는 프롬프트의 셔터 줄이
     정한다(아래 「프롬프트」). 카메라는 하나이고 화면을 나누지 않는다. 클로즈업을 작은 창으로 겹치면 영상 모델이 분할
     화면으로 따라 한다.
   - 가사 단어와 히트 박에 이름 붙은 타임라인 마커를 넣고 카메라를 켠 `.blend` 로 저장한다.
4. **사람이 감독한다.** 렌더를 기다리지 않고 `.blend` 를 사람이 쓰는 Blender 에서 열어(Blender MCP, 포트 9876)
   스페이스바로 재생하게 한다. 메모는 「95~101프레임 사선이 너무 늦다」처럼 프레임 번호로 받아 고친다. 돈을 쓰는 생성은
   사람이 블록아웃을 확인한 뒤에 한다. A7 v6 에서는 Claude 가 숫자로만 검수하고 생성했다가, 사람이 한눈에 본 엉거주춤한
   자세를 3,118원을 쓴 뒤에 알았다.
5. **장소 그림을 넣는다.** 장소 하나에 그림 하나다. 같은 장소의 그림이 여럿이면 서로 다툰다. 새로 만들 때는 알약을
   숨긴 회색 세트를 가장 넓고 잘 보이는 카메라로 렌더하고 이미지 모델에 「Turn this grey blockout into a photoreal film
   still. Keep the layout exactly: …」로 시작하는 프롬프트를 준다. 배치는 그대로, 사람 없음, 읽히는 글자 없음, 렌즈와
   빛은 영화 말로 적는다(kit 「Location plates」). 실내는 「사람이 사는 듯한」 같은 말을 넣어야 텅 비어 보이지 않는다
   ([Thomas Lundström, 7:51](https://www.youtube.com/watch?v=jc0Qh09Qrlo)). 그림이 블록아웃에 없는 큰 가구를 더하면
   영상에도 나온다(drama-film A2 의 탁자). 그림을 블록아웃과 맞대 보고 다르면 그림을 다시 만든다.
6. **올리기 전에 확인한다.** 박마다 한 칸 격자(`mv_timing.py sheet <영상> <격자.jpg> --fps 0 --bpm <BPM>`), 곡을 입힌
   확인용 파일, 그리고 수치(첫 전신 프레임, 전신이 된 뒤 모든 프레임에서 알약 위아래가 화면 안인지, 알약끼리 3D 거리와
   화면 겹침)를 본다. 알약이 굳어 있는지(높이, 기울기, 팔이 없는지)도 프레임마다 본다. 박 1 이 컷 0초가 아니면
   `--offset` 에 박 1 의 컷 시각을 준다.
7. **480p 로 먼저 본다.** 제작자들은 draft 모드로 오류를 본 뒤 고화질로 다시 만든다. 군무 컷의 초안은 Seedance 2.5
   480p 로 만든다. 곡을 함께 실을 수 있고 값은 720p 의 절반 아래다(위 표). flash 는 더 싸지만 곡을 받지 못해 박을 확인할
   수 없다. 초안에서 자리, 대형, 카메라, 세트가 맞으면 같은 spec 의 해상도만 올려 다시 만든다. 다시 만든 컷은 새
   생성이라 초안과 같은 장면이 나오지 않는다. 초안은 프롬프트와 블록아웃의 오류를 찾는 데 쓴다.

## 알약

- 멤버마다 캡슐 하나. 높이는 멤버 캐릭터(AI 인플루언서)의 `look_text` 에 적은 키, 반지름 약 0.17m 다.
- 가로 띠로 멤버를 가른다. 위 캡은 머리색, 윗 띠는 상의, 아랫 띠는 바지나 쇼츠, 맨 아래 띠는 부츠 색이다. 앞면에
  주황색 세로줄 하나를 그어 어느 쪽을 보는지 알게 한다. kit 는 사람마다 한 색에 검은 줄무늬를 두고 그 색의 옷을 입힌다.
  여기서는 띠를 머리와 옷 색으로 칠했고 v11·v12 에서 띠가 결과에 나오지 않았고 멤버도 바뀌지 않았다. 주황 옆 노랑,
  파랑 옆 청록처럼 가까운 색 둘을 한 화면에 두지 않는다. 영상 모델이 섞는다(kit).
- **알약은 굳어 있다.** 옮기고 돌리기만 한다. 팔, 고개, 높이 바꾸기, 기울기, 통통 튀기를 넣지 않는다. 앉는 박에도
  알약은 제 키로 서 있고 낮아지는 동작은 프롬프트가 정한다. 막대 팔과 높이 줄이기를 넣은 v9b 의 결과는 위 「블록아웃은
  몸 동작을 보이지 않는다」.
- 프롬프트는 알약을 색, 자리, 이름, 그림 번호로 부른다(아래 「프롬프트」의 Colour key).

마네킹을 쓰지 않는 이유도 위와 같다. 그 전의 강체 인형(v5)은 관절마다 공이 박히고 그린 실눈에 팔이 길어 사용자가
기괴하다고 했다. 실제 비율의 MPFB 마네킹(v6)은 생김새는 나아졌지만 연기를 옮겼다.

## Codex 가 Blender 를 쓰는 법

Codex 의 셸 샌드박스는 GPU 장치(`iokit-open AGXDeviceUserClient`)를 막아 Blender 가 Metal 초기화에서 죽는다. 이를
허용하는 Codex 설정은 없다(Codex 0.171 실측). 그래서 Codex 에게는
[Blender Lab MCP](https://www.blender.org/lab/mcp-server/) 로 샌드박스 밖의 Blender 를 준다. Blender 5.1 이상이 필요하다.

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B --command extension install-file -r user_default -e mcp-1.0.3.zip   # lab.blender.org 의 MCP 애드온
uv tool install "git+https://projects.blender.org/lab/blender_mcp.git@v1.0.3#subdirectory=mcp"
codex mcp add blender-previs --env BLENDER_MCP_PORT=9877 -- ~/.local/bin/blender-mcp
$B -b --online-mode --command blender_mcp --port 9877   # 작업용 Blender. 창 없이 띄워 둔다
```

- `~/.codex/config.toml` 의 `[mcp_servers.blender-previs]` 에 `default_tools_approval_mode = "approve"` 와
  `tool_timeout_sec = 300` 을 넣는다. 없으면 `codex exec` 가 「MCP tool call requires approval, but approval policy is
  never」로 멈춘다. 사람이 쓰는 GUI Blender(기본 포트 9876)에는 넣지 않는다.
- MCP 애드온은 소켓을 열어서 Blender 의 온라인 접근 허용이 있어야 켜진다. 작업용 Blender 에는 `--online-mode` 를
  붙인다. 사람이 쓰는 Blender 는 `open -a Blender --args --online-mode` 로 열거나 Preferences > System > Network 에서
  허용한다. 애드온이 켜지면 Preferences > Add-ons 의 MCP 항목에 「Server is running」이 보인다.
- 한 번의 호출은 300초 안에 끝나야 한다. 렌더처럼 긴 일은 MCP Blender 안에서 `subprocess.Popen` 으로 자식 Blender 를
  띄우고 로그를 셸에서 읽는다. 자식은 샌드박스 밖이라 GPU 를 쓴다.
- git 저장소 밖 폴더에서는 `codex exec --skip-git-repo-check` 를 붙인다. 빠뜨리면 「Not inside a trusted directory」로 끝난다.
- MCP 는 LLM 이 쓴 코드를 Blender 안에서 막지 않고 돌린다(공식 페이지의 보안 경고). 작업용 Blender 는 빈 장면으로 띄우고
  사람이 쓰는 Blender 와 포트를 나눈다. 예전 커뮤니티판 `Blender MCP` 애드온(ahujasid)도 기본 포트가 9876 이라 같이 켜지 않는다.

## 프롬프트

kit 의 뼈대 순서를 따른다. 블록아웃 줄, 색 안내(Colour key), 규칙(Rules), 장면과 의상, 춤(Dance), 렌즈와 결, 끝줄이다
(kit 「Seedance run」, `lib/blockout/prompt.py`). 블록아웃이 춤을 정하지 않으므로 춤 문단이 연기의 전부다. 춤 문단은 그루브
한 단락과 정수 초 구간의 동작 서너 개다([`choreography.md`](choreography.md) 「영상 프롬프트로 옮기기」). 아래는 A7 v13
의 앞 컷(4초, 히트에서 나눈 앞쪽)에 쓴 프롬프트다(3,798자, 결과는 아래 「결과」). 뒤 컷은 머리줄, 세트, 춤 구간만 다르다.
4초는 정수 초로 나눈 길이라 마디에 맞지 않았다. 컷의 생성 길이와 곡 시작은 `cutplan` 으로 정한다(아래 「히트에서 컷을
나눈다」).

```text
4 s 16:9 K-pop dance performance, one continuous shot, to Audio 1. The first half of the chorus; the shot ends on the
low hit.

Video 1 is a coarse-blockout reference of this exact shot. Follow it exactly for camera position, camera movement, lens
perspective, where each dancer stands, how large she is in frame, which way she faces, when and where she travels, and
when and where the walls rise. Do not copy how it looks.

Colour key
The capsule with the blonde cap and lavender bands, in the centre, is 하이나 (Haina), Image 2.
The capsule with the black cap and white bottom band, on the left, is 이담 (Idam), Image 3.
The capsule with the red cap and black bottom band, on the right, is 신더 (Cinder), Image 4.
The grey walls are the warehouse of Image 1.

Rules
The capsules carry no body motion. Give every dancer real, fluid human dance movement from the first frame. Each dancer
keeps the position, path, speed and facing of her capsule.
No capsule, coloured band, orange stripe or grey blockout geometry may ever appear in the result.
Discard the grey look completely. Lighting, colour, texture and set detail come from this text and the reference images.
Use each character reference for identity: face, hair and body only, never the pose or the background. Image 1 controls
the warehouse's geography and materials only.

Set
An open jelly world first: glossy jelly floor, no walls. Liquid slime flows up out of the floor in one sticky wave,
front edge first, exactly where and when the blockout walls rise, and hardens into the warehouse of Image 1, never
bricks or blocks.

Stage look
하이나: silver-lavender high-neck crop, lavender faux-fur shrug, holographic shorts, white-silver fluffy boots. 이담: silver
high-neck crop, white slim pants, white pointed-toe ankle boots. 신더: silver round-neck crop and shorts with lavender
panels, black chunky knee boots. Bare empty hands.

Dance
Lovely, playful K-pop girl-group chorus choreography in perfect unison, groove first. From the first frame to the last
the knees bounce down on every beat and the weight rocks side to side with the hips; nobody ever stops moving, even
inside a held shape. Each named move grows out of the bounce: the arms speed up into the accent and ease out of it,
travelling through space, never snapping from one pose to the next.

The frame opens low on their boots, as in Video 1.
0-1 s, "Melt it down": a body wave rolls down from the chest through the hips into the knees while both hands slide down
from the cheeks to the hips.
1-2 s, "build it up": a body roll back up from the knees, two quick chest pops on the way up, wrists flicking beside the
shoulders.
2-3 s, "다시 태어나": arms cross softly over the chest, then the chest pops open and the hands open beside the face like a
flower, elbows soft and close; they step into the diagonal with bouncy hip-sway steps. Clear floor stays between them on
screen; no arm crosses another dancer.
3-4 s, the second "Melt it down": a quick body wave down into a low groove squat, knees bent deep and turned out, hands
landing on the knees, chins up. They land in the squat on the last beat; the last frame is this low squat.

Lens and look
35 mm on full frame. Photoreal live-action music video, not a 3D render, not claymation or stop motion. Real 24 fps with
a 180-degree shutter: natural motion blur on fast arms and hair, every frame blending smoothly into the next. No
morphing, jitter or high-shutter crispness. Real skin texture.

Lips closed, eyes open and focused. No text, logos or celebrity likeness. Never: ballet positions, tiptoe, arms
stretched straight out to the sides, heart shapes, prayer hands, clapping, finger V, finger-gun, OK sign, covering the
face, pointing down, jumping, hips thrust at the camera, lying on the floor, any ball or object in the hands.
```

- **구절이 끝나는 컷은 마지막 히트에서 멈춘다.** 위 프롬프트는 구절이 뒤 컷으로 이어지는 앞 컷이라 「From the first frame
  to the last」로 쓴다. 구절이 끝나는 컷은 그 문장을 「Until the final hit at N s」로 바꾸고 마지막 구간에 `cutplan` 의
  `stop=` 문장을 잇는다([`conti-and-timing.md`](conti-and-timing.md) 「구절이 끝나는 컷은 마지막 히트에서 멈춘다」). 블록아웃도
  그 초부터 끝까지 카메라만 움직이고 알약은 서 있게 굽는다.
- **알약을 색과 그림 번호로 부른다.** 「LEFT = 검은 캡 알약」만 적고 참고 인물의 번호를 적지 않은 v9b 이전 문단은 쓰지
  않는다. 규칙 네 줄은 kit 의 문장을 그대로 쓴다.
- **셔터 줄을 적는다.** v9b 까지는 `No motion blur` 를 적었다. 그 문장은 아크의 블러도 막지 못했고
  ([`camera-moves.md`](camera-moves.md) 「아크샷」) kit 는 반대로 「180° shutter motion blur」와 「24fps smooth motion …
  No jitter」를 적는다(kit `skills/shotlist-director-thomas/SKILL.md`). v11 에서 막대 팔을 빼면서 이 줄로 바꾸자 빠른
  팔과 머리카락에 자연스러운 블러가 생겼다. 두 가지를 함께 바꿔 어느 쪽의 효과인지는 가르지 못했다.
- **박에는 시각을 적지 않는 것이 kit 의 방식이다.** 한 테이크는 머리줄 달린 박으로 쓰고 시각을 넣지 않는다(kit 「A
  one-take is written as beats, with no timecodes」). 박을 순서로만 적은 v11 은 Squish 가 6.04초가 아니라 약 6.4초에
  닿았다. 다섯 박에 시각을 적은 v12 는 Squish 가 약 6.0초에 맞았지만 플리에와 V 는 v11 처럼 늦었다(「결과」). 막대
  팔로 몸 동작을 보인 v9b 는 박이 맞았던 대신 클레이 애니메이션처럼 움직였다. 굳은 알약은 자연스러운 움직임을 얻고 몸
  동작의 박을 글에 맡긴다. 곡의 끝 히트처럼 하나만 맞으면 되는 박에 시각을 적는다. 중간 박까지 맞아야 하면 그 박에서
  컷을 나눈다(아래 「히트에서 컷을 나눈다」, v13 에서 박은 맞았다).
- **보이면 안 되는 것을 이름으로 부르지 않는다.** 「a soft invisible ball between them」을 적은 v11 에서는 손 사이에
  투명한 공이 나왔다. 「nothing between the hands」로 바꾸고 금지 목록에 「any ball or object in the hands」를 넣은 v12
  에는 공이 없었다.
- **첫 화면을 글로도 적는다.** 블록아웃이 부츠를 낮게 잡고 시작해도 v11 은 전신으로 시작했다. 「The frame opens low on
  their boots, as in Video 1」을 넣은 v12 는 부츠로 시작했다.

`image_prompt` 는 4,000자까지다. 지시가 길수록 모델이 지어내는 부분이 늘어난다는 제작자 경험이 있어 여러 숏을 한 번에
만들면 15초 안쪽으로 끊는다([Thomas Lundström, 12:05](https://www.youtube.com/watch?v=mx1yjt4k73o)).

## 히트에서 컷을 나눈다

컷 안에 적은 시각은 박자 안내에 그친다. Runway 는 Seedance 2.5 의 시각을 「pacing guidance rather than frame-exact cut
points」로 다룬다([Runway](https://runway.com/resources/seedance-2-5-prompt-guide)). 시각 다섯 개를 적은 v12 도 마지막
히트만 맞았다. 가운데 히트까지 박에 맞아야 하면 그 박에서 컷을 둘로 나눈다. A7 v13 에서 쓴 순서다.

1. 나누는 자리는 초가 아니라 박이다. `cutplan` 에 마디로 컷 둘을 주고 구절이 끝나는 뒤 컷에는 `stop=` 을 준다
   (`--cut "bar:1..bar:3 tail id=A7a" --cut "bar:3..bar:5 head id=A7b stop=51.08s"`). 컷마다 생성 길이와
   `song_start_ms` 가 나온다. A7 은 A7a 5초(곡 44.508초부터), A7b 5초(곡 47.700초부터)다. v13 은 정수 초로 4.00초(곡
   48.508초)에서 나눴고 뒤 컷이 2절 첫 0.6초까지 덮었다([`conti-and-timing.md`](conti-and-timing.md) 「구절이 끝나는 컷은
   마지막 히트에서 멈춘다」).
2. 블록아웃을 컷마다 `song_start_ms` 부터 생성 길이만큼 자른다. 블록아웃 0초가 곡 44.508초이면 A7b 는 3.192~8.192초다.
   블록아웃이 그만큼 길지 않으면 Blender 에서 끝을 늘려 다시 굽는다. 자르는 명령은 `ffmpeg -i blockout.mp4 -vf
   "select='between(n\,77\,196)',setpts=N/24/TB" -an -r 24 -c:v libx264 -crf 16 b.mp4` 꼴이다. Seedance 는 4~15초만
   받는다(DemoCut `SEEDANCE_DURATION_S`). 조각을 올려 컷마다 `reference_video_asset_ids` 에 넣고 `democut_set_cut_bgm` 의
   `song_start_ms` 에 `cutplan` 값을 준다.
3. 앞 컷은 히트로 끝난다. 머리줄에 「the shot ends on the low hit」, 마지막 구간에 「the last frame is this low squat」을
   적는다. 뒤 컷은 같은 자세로 연다(「The shot opens with all three already in a low groove squat」).
4. 첫 장면 지정(`image_asset_id`)은 쓰지 않는다. 곡을 들려주는 컷(`host: "music"`)이면 DemoCut 이 첫 장면과 곡을 함께
   보내지 않고(`SPEC_CONFLICT`) 사용자도 쓰지 말라고 했다(2026-11-23).
5. 두 컷은 따로 만들고 `cutplan` 의 트림대로 잘라 이어 붙인다. 이어 붙일 때는 `ffmpeg -f concat -safe 0 -i list.txt -c copy`
   로 시각을 건드리지 않는다. `concat` 필터에 `-r 24` 를 주면 이음매에 프레임이 하나 겹쳐 들어가 192프레임이 194프레임이 됐다. 4초 컷은
   738원씩이라 8초 한 컷(1,458원)과 거의 같다.

v13 에서 박은 맞았고 이음매는 튀었다(「결과」). 뒤 컷은 블록아웃의 자리와 세트를 따르지 않았다. 다음에는 아래를
함께 바꾼다(아직 시험 전).

- 뒤 컷의 세트를 앞 컷 결과에 보이는 대로 적는다. 앞 컷이 회색 콘크리트 창고로 끝났으면 「the grey concrete
  warehouse of Image 1」라고 적고 슬라임 같은 다른 재질 낱말을 넣지 않는다.
- 자리를 문장으로도 적는다(「이담이 왼쪽 앞, 하이나가 가운데 뒤, 신더가 오른쪽 가장 뒤. 하이나는 앞으로 나오지 않는다」).
  카메라가 다가가는 끝 숏 크기도 적는다(「the last frame still shows all three head to toe」).
- 컷을 나누는 박에서 블록아웃 카메라도 바꾼다. 같은 숏 크기와 각도로 이으면 작은 차이도 점프 컷으로 보인다. 숏 크기나
  각도가 바뀌면 세트와 자세의 작은 차이가 편집으로 읽힌다(편집의 일반 원칙이고 이 파이프라인에서는 미확인).

## 만든 뒤 확인

```
python3 scripts/mv_timing.py follow previs.mp4 result.mp4 --from 22
```

프레임마다 앞 프레임과의 밝기 차(움직임 양)를 두 영상에서 재고 결과를 몇 프레임 밀었을 때 둘이 가장 닮는지(상관 r)를 낸다.
마네킹이 춤까지 춘 v5·v6 에서는 r 이 0.79·0.90 이었다. 알약 블록아웃은 춤을 담지 않으므로 r 은 카메라와 이동만 반영해
낮게 나올 수 있다. 그때는 `sheet` 격자로 자리, 대형, 카메라 도착을 같은 프레임에서 맞대어 보고 시각을 적은 박마다 앞뒤
1초를 10~12fps 로 잘라 동작이 닿는 프레임을 찾는다.

## 결과

모두 A7 후렴 8초, Seedance 2.5, 곡을 들려줌(`host: "music"`), 멤버 셋과 창고 참고, 한 번씩 생성한 실측이다.

v5 강체 인형(2026-11-22, 720p, 3,118원).

- **자리.** 왼쪽부터 이담, 하이나, 신더가 8초 내내 맞았다. 사선(이담이 앞), 하이나가 한 걸음 나온 대형, 일자가 모두 나왔다.
  글만 적은 같은 컷(v13)은 이담과 하이나가 바뀌어 있었다.
- **박.** `follow` 로 22~192프레임을 재니 시차 0 에서 r=0.79 였다(앞 22~89 는 0.83, 89~166 은 0.67). 같은 프리비즈와 v13 은
  r=0.09 였다. 깊이 앉기(2.77초), 반 바퀴 돌기(3.23초), 차례로 몸 접기(3.69·4.15·4.62초)가 그 프레임에 나왔다.
- **카메라.** 0.92초(22프레임)에 머리부터 발까지 전신이었다. 그 뒤 허벅지와 전신 사이를 오가고 멈춘 6.92초부터 끝까지
  카메라만 세 사람 쪽으로 다가갔다. 프리비즈의 경로와 같다.
- **손.** 6.00초 볼 옆 갈고리가 셋 모두 나와 끝까지 남았고 얼굴을 가리지 않았다. 금지한 하트, 손가락 V 는 한 번도 나오지
  않았다(글만 적은 컷에서는 V 세 번, 끝 박 하트 셋). 5.54초 작은 고리는 손이 가슴 앞에 모이기만 하고 고리로 읽히지 않았다.
- **모양.** 인형의 모양은 묻어나지 않았다. 얼굴, 머리, 의상은 캐릭터 시트대로, 세트는 창고 참고대로 나왔다.
- **안 된 것.** 세트 전환은 글대로 되지 않았다. 0.92초에 이미 창고 뒷벽이 있었고 슬라임은 1.4~2.9초 동안 뒷벽 앞에
  번들거리는 막으로 섰다가 3.25초에 무광 벽이 됐다. 프리비즈에는 세트가 없어서 이 부분은 글로만 정해졌다.

v6 MPFB 리깅 마네킹과 가사 안무(2026-11-22, 720p, 3,118원).

- **박.** `follow` 로 15~192프레임을 재니 시차 0 에서 r=0.90 이었다. 녹기, 주먹 쌓기, 웅크리기, V 로 피기, 사선, 차례로
  녹아 와이드 플리에, 높이가 다른 계단, 머리 위로 뻗기, 위아래로 포갠 손바닥이 모두 프리비즈의 착지 프레임에 나왔다.
  0.63초에 셋이 머리부터 발까지 보였다.
- **키.** 왼쪽부터 큰 순서(이담, 하이나, 신더)가 8초 내내 보였다.
- **연기.** 마네킹의 엉거주춤한 자세와 멈췄다 움직이는 흐름이 그대로 나왔다. 사용자가 받아들이지 않았다.
- **모양.** 클레이 몸과 옷 껍데기는 묻어나지 않았다. 끝 클로즈업에서 셋 중 둘이 눈을 감았다.
- **안 된 것.** 세트 전환은 이번에도 글대로 되지 않았다. 0.63초에 이미 창고 뒷벽이 있었고 바닥만 젤리처럼 번들거렸다.

v9b 막대 팔과 높이가 줄어드는 알약, 벽이 솟는 회색 세트(2026-11-22, 480p, 1,458원). 프롬프트는 「BLOCKOUT REFERENCE …
Use it ONLY for …」 문단, 히트 박의 손 자리, `No motion blur`.

- **연기.** 막대 손이 멈춘 구간에 멤버도 멈췄고 Squish 는 약 3프레임 만에 꺾였다. 다리, 골반, 상체가 거의 움직이지
  않았다. 사용자가 클레이 애니메이션 같다고 했다(위 「블록아웃은 몸 동작을 보이지 않는다」).
- **박.** 몸 동작이 블록아웃에 있어서 박은 맞았다. 부츠로 시작했고 3.96초에 셋이 손을 허벅지에 얹은 플리에였고
  Squish 는 약 6.0초에 닿았다.
- **안 나온 것.** 알약과 막대는 결과에 나오지 않았다.

v11 굳은 알약(팔과 높이 변화 없음, v9b 와 같은 자리·벽·카메라), kit 뼈대 프롬프트, 박은 순서만(2026-11-22, 480p, 1,458원).

- **연기.** 알약이 나오지 않았다. 무릎, 골반, 상체가 함께 움직이고 빠른 팔과 머리카락에 블러가 생겼다. Squish 는
  약 8프레임에 걸쳐 내려왔다.
- **박.** Squish 가 6.04초가 아니라 약 6.4초에 닿았다. 두 번째 「Melt it down」의 플리에는 약 0.7초 늦었고 몸 접기는
  3.0초에 일찍 시작했다.
- **안 된 것.** 첫 화면이 부츠가 아니라 전신이었다. 사선(3.96~4.67초)에서 팔을 옆으로 편 셋이 화면에서 겹쳤다. 「태어나」
  에서 팔이 머리 위로 하트 같은 고리를 지났다. Squish 의 손 사이에 투명한 공이 나왔다.

v12 같은 블록아웃, v11 프롬프트에 다섯 박의 시각과 위 다섯 줄을 고친 것(2026-11-23, 480p, 1,458원).

- **맞은 것.** 부츠를 낮게 잡고 시작했다. Squish 는 약 6.0초에 무릎을 모으고 손바닥을 포갰고 6.5초부터 끝까지 유지했다.
  손 사이에 공이 없었다. 4.67초 사선에서 셋이 겹치지 않았다.
- **안 맞은 것.** 플리에(3.96초로 적음)는 v11 처럼 약 4.6초에 닿았고 3.6~4.2초에는 팔을 옆으로 편 채 서 있었다. 이때
  팔 끝이 이웃과 겹친 프레임이 남았다. V(1.92초로 적음)는 약 2.5초에 열렸고 그 전에 팔꿈치를 굽혀 머리 위에서 손이
  모이는 고리를 지났다(2.2~2.4초). 이담은 5.13초 머리 위 자세 대신 아직 플리에였고 머리 위로 멈추는 구간(5.13~6.00초)
  없이 Squish 로 내려왔다.
- **움직임 양.** 카메라 움직임을 뺀 몸의 움직임(광학 흐름 잔차, 앞 148프레임)은 중앙값 v9b 3.92, v11 3.49, v12 5.42
  픽셀이었다. 거의 멈춘 프레임은 7, 15, 13개였다. v11·v12 에는 끝 Squish 를 유지하는 구간이 들어 있다. 프레임 사이
  움직임 양이 들쭉날쭉한 정도는 0.29, 0.22, 0.18 로 줄었다.

v13 v11 블록아웃을 4.00초(96프레임)에서 나눈 4초 컷 둘. 아이돌 춤 낱말, 그루브 문단, 정수 초 구간으로 다시 쓴 프롬프트
([`choreography.md`](choreography.md) 「끊겨 보이는 춤」 「영상 프롬프트로 옮기기」), 첫 장면 지정 없음(2026-11-23, 480p,
738원씩 1,476원).

- **박.** 앞 컷의 낮은 스쿼트가 약 3.65초(적은 박 3.96초)에 닿아 컷(4.00초)까지 이어졌다. v12 는 같은 자리가 약 4.6초였다.
  앞 컷의 정수 초 구간도 그 구간에 나왔다(2.4초 팔 감싸기, 3.0초 얼굴 옆으로 연 손). 뒤 컷의 팔 뻗기는 5.13초 무렵,
  Squish 는 약 6.0초에 닿았고 그 뒤 손바닥 누르기를 되풀이했다.
- **움직임.** `motion_check.py` 로 멈춘 프레임 14개(7%), 가장 빠른 프레임 36.5픽셀(너비의 4.3%)이었다. v12 는 42개(22%),
  44.2픽셀(5.2%)이었다. 두 파일 모두 겹치거나 섞인 프레임은 없었다.
- **안 된 것.** 뒤 컷이 블록아웃을 따르지 않았다. 하이나가 앞 가운데로 나와 화면을 채웠고 셋이 붙었으며 카메라는
  블록아웃보다 가깝게 시작해 끝에는 얼굴 클로즈업까지 들어갔다. 세트는 앞 컷의 회색 콘크리트 창고가 아니라 갈색으로
  번들거리는 슬라임 동굴이었다. 뒤 컷 프롬프트에 「walls of hardened slime」을 적은 탓으로 보인다(미확인). 자세는
  이어졌지만 4.00초 컷에서 세트, 대형, 숏 크기가 한꺼번에 바뀌었다. 앞 컷도 3.96초에 블록아웃보다 넓게 잡혔고 하이나와
  신더가 가깝게 붙었다.
- **끝.** 뒤 컷은 Squish 히트(약 6.0초) 뒤에도 손바닥 누르기를 이어 갔고 「시」(6.57초)를 지나 2절이 시작하는
  7.38초 뒤에도 춤췄다. 프롬프트가
  「2-4 s: they repeat the squish press on every beat」로 남는 초를 채우게 했기 때문이다. 사용자는 「Squish에서 안무가
  멈췄어야되」라고 했다(2026-11-23). `motion_check.py --hold-from 6.08` 로 재면 그 뒤 멈춘 프레임 13%, 몸 움직임 가운데값
  11.0픽셀로 춤 구간과 같았다. 끝까지 Squish 를 잡은 v12 는 74%, 2.5픽셀이었다. 컷도 마디가 아닌 정수 초(4.00초)로
  나눴다.
