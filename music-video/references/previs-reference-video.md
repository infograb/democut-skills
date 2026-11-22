# 3D 블록아웃을 참고 영상으로

글로 적은 자리·박·카메라가 지켜지지 않는 컷은 같은 컷을 3D 블록아웃으로 먼저 만들어 영상 모델에 참고 영상으로 준다.
블록아웃은 자리, 이동, 대형, 낮아지는 박, 세트의 모양과 생기는 시각, 카메라만 정한다. 춤과 표정은 프롬프트와 곡이 정한다.

## 언제 쓰나

글만 적은 군무 컷에서 잰 실패가 이 방법의 근거다(Seedance 2.5, 8초, 세 명, A7 여러 버전).

- 의상은 다 맞는데 가운데와 왼쪽 멤버가 바뀌었다.
- 신발 클로즈업에서 0.92초 전신으로 빠지라고 적은 오프닝이 약 1.85초에 전신이 됐다.
- 박마다 다른 손 모양 16개를 적었는데 거의 나오지 않고 같은 팔 모양이 2~3박 이어졌다. 한 박씩 엇갈리게 적은 동작은
  셋이 같이 했다.

입은 옮기지 못한다. 부르는 줄은 [`democut-mv.md`](democut-mv.md) 「입을 맞춰 부르는 줄(단독샷)」대로 만든다.

## 블록아웃이 정하지 않는 것

영상 모델은 참고 영상의 움직임을 거의 그대로 따른다. 그래서 블록아웃에 넣은 연기는 결과의 연기가 된다.

- A7 v6 는 실제 비율의 리깅 마네킹(MPFB)이 안무 전체를 추게 하고 프롬프트에 「every rib, hip, shoulder … follow it
  frame for frame」을 적었다. 결과는 프리비즈를 r=0.90 으로 따랐고 마네킹의 흠도 그대로 옮겼다. 사용자는
  「자세가 엉거주춤하고 클레이 애니메이션처럼 프레임이 안 맞는다」고 했다. 마네킹을 재 보니 골반이 평균 14cm 내려가
  있었다. 키는 3프레임마다 있었고 손 모양이 1초에 5번 바뀌었다(곡은 1초에 2.2박).
- 블록아웃의 모양도 새어 나간다. 눈꺼풀을 감은 마네킹 얼굴을 쓴 v6 에서는 끝 클로즈업에서 셋 중 둘이 눈을 감았다.
  다른 제작자의 광고에서는 블록아웃의 다이아몬드 모양 꽃이 결과에 그대로 나왔다
  ([Thomas Lundström, 12:10](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
- Blender 와 Seedance 로 작업하는 제작자들은 사람 대신 색 줄무늬 알약을 세운다. 연기가 옮겨질 위험이 없고 회색
  화면에서 눈에 띄기 때문이다. 팔이나 고개는 꼭 필요한 박에만 붙인다
  ([Thomas Lundström, 4:00](https://www.youtube.com/watch?v=mx1yjt4k73o)). 프롬프트에는 참고 영상을 카메라 참고로만
  쓰라는 한 문장을 넣는다([Dan Kieft, 3:17](https://www.youtube.com/watch?v=miIDu04N7_4)). 연기가 밋밋하면
  블록아웃이 아니라 프롬프트를 고친다(Thomas Lundström 8:29, 같은 첫 영상).

알약 블록아웃으로 춤 컷을 생성해 잰 실측은 아직 없다. 자리와 박이 v5·v6 만큼 지켜지는지, 손 모양이 글만으로 나오는지는
미확인이다. 결과가 나오면 아래 「결과」에 적는다.

## DemoCut 에서 받는 것

2026-11-22 배포 기준이다. 값은 `democut_get_options` 의 `video_models[]` 에서 다시 확인한다.

- 칸은 `reference_video_asset_ids`(영상 자산 id 목록)다. `democut_upload_asset(kind="video")` 로 올린 id 를 넣는다.
- Seedance 2.5 는 영상 10개, 한 개 2~30초, 합 30초까지 받는다. Seedance 2.5 flash 는 5개를 받고 720p 까지이며
  곡(참고 오디오)을 받지 못한다. 나머지 모델은 3개·2~15초·합 15초다.
- 첫·끝 장면 그림과는 함께 쓰지 못한다(`SPEC_CONFLICT`). 참고 이미지, 참고 인물, 곡(`host: "music"`)과는 함께 쓴다.
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
   멤버의 자리, 대형이 바뀌는 박, 낮아지는 박, 카메라 숏(거리·높이·바라보는 높이)과 그 숏에 도착하는 박을 적는다.
   대형의 간격은 [`choreography.md`](choreography.md) 「간격은 그 대형에서 하는 가장 큰 동작으로 정한다」대로 잡는다.
   가사 동작은 블록아웃이 아니라 프롬프트에 적는다. 단어는 `mv_timing.py lyrics` 로 박에 놓고
   [`choreography.md`](choreography.md) 「가사에서 동작으로」대로 뜻을 몸으로 옮긴다.
2. **알약을 세운다.** 아래 「알약」.
3. **Blender 로 만든다.** Workbench, 1280×720, 24fps, H.264 yuv420p, 소리 없음, 화면 글자 없음. 길이는 정수 초다.
   Codex 에게 맡길 때는 아래 「Codex 가 Blender 를 쓰는 법」.
   - 세계는 회색이고 색은 알약에만 있다. 세트가 컷 안에서 바뀌면 그 벽도 회색 덩어리로 넣는다(아래 「결과」의
     세트 전환 실패 참고. 넣었을 때 따라오는지는 미확인).
   - 카메라는 숏을 박에 키로 넣고 모션 블러를 쓰지 않는다. 카메라는 하나이고 화면을 나누지 않는다. 클로즈업을 작은
     창으로 겹치면 영상 모델이 분할 화면으로 따라 한다.
   - 가사 단어와 히트 박에 이름 붙은 타임라인 마커를 넣고 카메라를 켠 `.blend` 로 저장한다.
4. **사람이 감독한다.** 렌더를 기다리지 않고 `.blend` 를 사람이 쓰는 Blender 에서 열어(Blender MCP, 포트 9876)
   스페이스바로 재생하게 한다. 메모는 「95~101프레임 사선이 너무 늦다」처럼 프레임 번호로 받아 고친다. 돈을 쓰는 생성은
   사람이 블록아웃을 확인한 뒤에 한다. A7 v6 에서는 Claude 가 숫자로만 검수하고 생성했다가, 사람이 한눈에 본 엉거주춤한
   자세를 3,118원을 쓴 뒤에 알았다.
5. **장소 그림을 만든다.** 알약을 숨기고 카메라 자리에서 세트 스틸을 렌더한다. 이미지 모델로 그 구도의 실사 장소
   그림을 만들어 참고 이미지로 넣으면 장소가 블록아웃과 맞는다
   ([Thomas Lundström, 9:53](https://www.youtube.com/watch?v=mx1yjt4k73o)). 실내는 「사람이 사는 듯한」 같은 말을 넣어야
   텅 비어 보이지 않는다(같은 제작자의 광고 영상 7:51).
6. **올리기 전에 확인한다.** 박마다 한 칸 격자(`mv_timing.py sheet <영상> <격자.jpg> --fps 0 --bpm <BPM>`), 곡을 입힌
   확인용 파일, 그리고 수치(첫 전신 프레임, 전신이 된 뒤 모든 프레임에서 알약 위아래가 화면 안인지, 알약끼리 겹치는지)를
   본다. 매 프레임 멤버끼리(알약, 팔, 손) 3D 거리가 0.3m 이상인지, 화면에서 서로 겹치지 않는지도 잰다. 걸리면 동작을
   줄이지 않고 대형을 넓힌다. 박 1 이 컷 0초가 아니면 `--offset` 에 박 1 의 컷 시각을 준다.
7. **480p 로 먼저 본다.** 제작자들은 draft 모드로 오류를 본 뒤 고화질로 다시 만든다. 군무 컷의 초안은 Seedance 2.5
   480p 로 만든다. 곡을 함께 실을 수 있고 값은 720p 의 절반 아래다(위 표). flash 는 더 싸지만 곡을 받지 못해 박을 확인할
   수 없다. 초안에서 자리, 대형, 카메라, 세트가 맞으면 같은 spec 의 해상도만 올려 다시 만든다. 다시 만든 컷은 새
   생성이라 초안과 같은 장면이 나오지 않는다. 초안은 프롬프트와 블록아웃의 오류를 찾는 데 쓴다.

## 알약

- 멤버마다 캡슐 하나. 높이는 멤버 캐릭터(AI 인플루언서)의 `look_text` 에 적은 키, 반지름 약 0.17m 다.
- 가로 띠로 멤버를 가른다. 위 캡은 머리색, 윗 띠는 상의, 아랫 띠는 바지나 쇼츠, 맨 아래 띠는 부츠 색이다. 앞면에
  주황색 세로줄 하나를 그어 어느 쪽을 보는지 알게 한다. 팔, 머리, 얼굴은 넣지 않는다.
- 몸의 움직임은 이동, 방향, 높이뿐이다. 앉는 박(와이드 플리에, 웅크리기)은 알약의 높이를 발 기준으로 줄여 보인다.
  흔들기는 넣지 않는다.
- 팔은 막대 두 마디(위팔 0.186, 아래팔 0.146, 키에 대한 비)와 납작한 손판이다. 평소에는 몸 옆에 늘어뜨리고 가사의 히트
  박에만 손이 그 자리(배, 가슴, 머리 위, V, 허벅지, 포갠 손바닥)로 가서 그 박에 닿는다. 손판의 손바닥 면은 주황색이라
  손바닥 방향이 보인다. 팔 없는 알약으로는 손 모양과 히트 박이 전해지지 않는다는 판단에서 사용자가 이 안을 골랐다
  (2026-11-22. 글만 적은 v13 에서 손 모양 16개가 거의 나오지 않았다).
- 그림으로 어떻게 읽히는지 카메라 화면으로 본다. 머리 위에서 팔꿈치를 굽혀 손을 모으면 머리 위에 고리가 생겨 하트나
  후광으로 읽힌다. 팔꿈치를 155도 넘게 펴서 좁은 Λ 로 만든다. 어깨가 가까운 대형에서 팔꿈치를 옆으로 벌리면 이웃 팔과
  화면에서 엉킨다(A7 v9). 손끝을 위로 세우고 손바닥을 마주 보게 하면 기도하는 손이다(A7 v6).
- 프롬프트는 자리를 이 색으로 부른다(예: LEFT = 검은 캡과 흰 아랫 띠).

마네킹을 쓰지 않는 이유는 위 「블록아웃이 정하지 않는 것」이다. 그 전의 강체 인형(v5)은 관절마다 공이 박히고 그린 실눈에
팔이 길어 사용자가 기괴하다고 했다. 실제 비율의 MPFB 마네킹(v6)은 생김새는 나아졌지만 연기를 옮겼다.

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

참고 영상에서 무엇만 가져오고 무엇은 가져오지 말지를 맨 앞 문단에 둔다. 알약 블록아웃용 문단이다(생성 실측 전).

```text
BLOCKOUT REFERENCE: video 1 is a rough grey blockout of THIS shot, timed to the same music. Use it ONLY for where each
dancer stands and travels (LEFT = the pill with the black cap and white bottom band, CENTER = the pill with the blonde
cap and lavender bands, RIGHT = the pill with the red cap and black bottom band), when they go low, where the hands are
on each hit beat (the stick arms; orange shows the palm side), when the set forms, and the camera path. Copy nothing
else from it: no pills, no stick arms, no grey world, no stiff motion. Real arms move fluidly with the whole body
between the hits. The dancers' bodies, the dance itself, faces, hair and outfits come from this text, the music and
the character references.
```

그 뒤에 춤을 적는다. 블록아웃이 춤을 정하지 않으므로 이 부분이 연기의 전부다. 가사마다 동작과 그 박의 시각, 그리고
춤의 결(예: 「sharp K-pop idol choreography, confident, every move lands on the beat, standing tall between hits」)을
적는다. 장면, 의상, 맨손 문장, 금지 목록은 평소 순서대로 둔다([`democut-mv.md`](democut-mv.md) 「프롬프트의 짜임」).

`image_prompt` 는 4,000자까지다. 지시가 길수록 모델이 지어내는 부분이 늘어난다는 제작자 경험이 있어 여러 숏을 한 번에
만들면 15초 안쪽으로 끊는다([Thomas Lundström, 12:05](https://www.youtube.com/watch?v=mx1yjt4k73o)).

## 만든 뒤 확인

```
python3 scripts/mv_timing.py follow previs.mp4 result.mp4 --from 22
```

프레임마다 앞 프레임과의 밝기 차(움직임 양)를 두 영상에서 재고 결과를 몇 프레임 밀었을 때 둘이 가장 닮는지(상관 r)를 낸다.
마네킹이 춤까지 춘 v5·v6 에서는 r 이 0.79·0.90 이었다. 알약 블록아웃은 춤을 담지 않으므로 r 은 카메라와 이동만 반영해
낮게 나올 수 있다. 그때는 `sheet` 격자로 자리, 대형, 낮아지는 박, 카메라 도착을 같은 프레임에서 맞대어 본다.

## 결과

v5 강체 인형으로 잰 실측(2026-11-22, A7 후렴 8초, Seedance 2.5 720p, 곡을 들려줌, 멤버 셋 + 세트 참고 + 8초 프리비즈, 3,118원, 한 번 생성).

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

MPFB 리깅 마네킹과 가사 안무로 바꾼 v6 실측(2026-11-22, 같은 컷과 조건, 3,118원, 한 번 생성).

- **박.** `follow` 로 15~192프레임을 재니 시차 0 에서 r=0.90 이었다. 녹기, 주먹 쌓기, 웅크리기, V 로 피기, 사선, 차례로
  녹아 와이드 플리에, 높이가 다른 계단, 머리 위로 뻗기, 위아래로 포갠 손바닥이 모두 프리비즈의 착지 프레임에 나왔다.
  0.63초에 셋이 머리부터 발까지 보였다.
- **키.** 왼쪽부터 큰 순서(이담, 하이나, 신더)가 8초 내내 보였다.
- **연기.** 마네킹의 엉거주춤한 자세와 멈췄다 움직이는 흐름이 그대로 나왔다. 사용자가 받아들이지 않았다(위
  「블록아웃이 정하지 않는 것」).
- **모양.** 클레이 몸과 옷 껍데기는 묻어나지 않았다. 끝 클로즈업에서 셋 중 둘이 눈을 감았다.
- **안 된 것.** 세트 전환은 이번에도 글대로 되지 않았다. 0.63초에 이미 창고 뒷벽이 있었고 바닥만 젤리처럼 번들거렸다.
