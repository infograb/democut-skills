# 3D 프리비즈를 참고 영상으로

글로 적은 자리·박·카메라가 지켜지지 않는 컷은, 같은 컷을 3D 인형으로 먼저 만들어 영상 모델에 참고 영상으로 준다.

## 언제 쓰나

글만 적은 군무 컷에서 잰 실패가 이 방법의 근거다(Seedance 2.5, 8초, 세 명, A7 여러 버전).

- 의상은 다 맞는데 가운데와 왼쪽 멤버가 바뀌었다.
- 신발 클로즈업에서 0.92초 전신으로 빠지라고 적은 오프닝이 약 1.85초에 전신이 됐다.
- 박마다 다른 손 모양 16개를 적었는데 거의 나오지 않고 같은 팔 모양이 2~3박 이어졌다. 한 박씩 엇갈리게 적은 동작은
  셋이 같이 했다.

입은 옮기지 못한다. 프리비즈 마네킹은 입을 움직이지 않는다. 부르는 줄은 [`democut-mv.md`](democut-mv.md) 「입을 맞춰 부르는 줄(단독샷)」대로
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
   동작의 박은 [`choreography.md`](choreography.md) 「곡의 강세에서 동작을 짠다」의 강세 지도에서 고른다. 가사가 있는
   컷은 단어를 `mv_timing.py lyrics` 로 박에 놓고, 같은 문서 「가사에서 동작으로」대로 뜻을 몸으로 옮긴다.
2. **마네킹을 만든다.** 아래 「마네킹」.
3. **Blender 로 렌더한다.** `Blender -b --factory-startup --python <스크립트> -- --spec <컷.json>` 처럼 창 없이 돌린다
   (Blender 5.1 이상, Workbench, 1280×720, 24fps, H.264 yuv420p, 소리 없음, 화면 글자 없음).
   Codex 에게 맡길 때는 아래 「Codex 가 Blender 를 쓰는 법」.
   - 마네킹은 의상 색으로 가른다. A7 에서는 흰 바지와 검은 포니테일(LEFT), 라벤더 상의와 금발(CENTER), 검은 무릎 부츠와
     빨간 머리(RIGHT)였다. 프롬프트도 자리를 이 색으로 부른다.
   - 동작은 박에 3프레임 안에 도착한다. 박마다 뼈에 키 자세를 넣고 사이는 완만한 베지어 곡선으로 잇는다(직선 보간은
     로봇처럼 보인다). 큰 동작은 예비 동작과 여운을 두고, 머리카락은 고개보다 2~4프레임 늦게 따라오게 한다. 체중이
     실린 발은 다리 IK 로 바닥에 고정한다.
   - 손은 손바닥 가운데를 목표로 팔을 풀고, 손이 얼굴을 덮는 프레임이 없는지 잰다. 손끝을 위로 세우고 두 손바닥을
     가슴 앞에서 마주 보게 하면 눈 감은 마네킹 얼굴과 겹쳐 기도하는 손이나 박수 직전으로 읽힌다(A7 v6). 누르는 동작은
     위 손바닥이 아래를, 아래 손바닥이 위를 보게 포개고 팔꿈치를 옆으로 연다.
   - 카메라는 숏을 박에 키로 넣고 모션 블러를 쓰지 않는다. 카메라는 하나이고 화면을 나누지 않는다. 클로즈업을 작은 창으로
     겹치면 영상 모델이 분할 화면으로 따라 한다.
4. **올리기 전에 확인한다.** 박마다 한 칸 격자(`mv_timing.py sheet <영상> <격자.jpg> --fps 0 --bpm <BPM>`), 곡을 입힌 확인용
   파일, 그리고 수치(첫 전신 프레임, 전신이 된 뒤 모든 프레임에서 머리가 화면 안인지, 손이 얼굴을 덮는 프레임 수, 디딘 발이
   미끄러지는지, 손과 팔뚝이 몸통을 뚫는지, 옷 껍데기와 몸 사이가 1mm 아래로 붙는 프레임)를 본다. 박 1 이 컷 0초가 아니면
   `--offset` 에 박 1 의 컷 시각을 준다(빼면 칸마다 한두 프레임 앞을 보여 준다). 카운트의 착지 프레임은 따로 뽑아 본다.

## 마네킹

v5 까지의 인형은 부품을 관절에 붙인 강체였다. 관절마다 공이 박히고 팔다리가 소시지처럼 끊겼으며, 그린 실눈에 팔이
길고 손이 커서 사용자가 기괴하다고 했다. 영상 모델은 참고 영상의 움직임을 거의 그대로 따른다. Seedance 2.5 가
Blender 인형의 부자연스러운 움직임까지 옮겼다는 실험이 있다
([Curious Refuge](https://curiousrefuge.com/blog/how-to-control-ai-videos-with-blender-and-claude)). 그래서 몸이
사람처럼 굽어야 한다.

- 몸은 [MPFB 2](https://github.com/makehumancommunity/mpfb2)(MakeHuman 의 Blender 확장. 코드는 GPLv3, 만든 사람 모델은
  CC0)로 만든다. 멤버 캐릭터(AI 인플루언서)의 `look_text` 에 적은 키(맨발, 바닥에서 정수리)를 0.5cm 안으로 맞춘다. 고정된 몸을
  늘리지 않고 키 매크로를 맞춰 다리와 몸통 비율이 키에 따라 바뀌게 한다.
- 비율은 키에 대한 비로 잰다(Winter 인체 계측). 턱 0.870, 어깨 0.818, 고관절 0.530, 위팔 0.186, 아래팔 0.146,
  손 0.108, 넓적다리 0.245, 정강이 0.246.
- MPFB 내장 뼈대(척추, 목, 머리, 쇄골, 팔, 다리, 발, 손가락)와 그 가중치를 쓴다. 몸은 이어진 메시 하나이고(옷은 아래의 껍데기) Armature
  모디파이어에 Preserve Volume 을 켠다. 부품을 관절에 붙인 것은 리깅이 아니다.
- 몸은 무광 단색 클레이이고 옷은 멤버마다 다른 단색이다. 코, 입술, 눈두덩 같은 얼굴 형태는 두고 눈, 눈썹, 속눈썹, 치아 메시와 그린
  이목구비는 없앤다. 손과 소품을 정교하게 만든 프리비즈는 결과에 CG 느낌이 묻어났다는 사례가 있어
  ([Evolink 사례 41](https://github.com/Evolink-AI/Awesome-Blender-Seedance-Workflow-Usecases)), 피부 질감이나 옷 주름은
  만들지 않는다.
- 의상은 몸에서 따로 떼어 낸 매끈한 껍데기다. 처음 판(A7 v6)은 몸 위에 색 구역만 칠해서 상의 위로 가슴 모양과 유두가,
  바지 위로 사타구니 굴곡이 그대로 보였다. 영상 모델이 그 몸을 따라 하고 BytePlus 심사에서 걸릴 수 있다. 옷 구역의 면을
  복제해 4~8mm(가슴은 더) 밖으로 밀고 세게 다듬어 굴곡을 없앤 뒤, 몸의 가중치를 옮겨 같은 뼈대로 굽힌다. 껍데기 밑의
  몸 면은 숨겨 춤 도중 살이 뚫고 나오지 않게 한다. 밑단은 두께가 있는 곧은 고리로, 쇼츠는 허벅지 위에서 잘라 기저귀처럼
  보이지 않게 한다. 부츠도 얇은 껍데기다.
- 머리는 매끈한 덩어리에 뼈 2~3개를 넣는다. 묶은 머리도 이마에 머리선을 내야 수영모처럼 보이지 않는다.
- 춤을 붙이기 전에 정면·옆 라인업(10cm 격자)과 무릎 위 근접 그림을 렌더해 사람이 본다. 키 차이, 옷이 몸 굴곡을
  덮는지, 부츠 길이, 머리선을 여기서 고친다.

## Codex 가 Blender 를 쓰는 법

Codex 의 셸 샌드박스는 GPU 장치(`iokit-open AGXDeviceUserClient`)를 막아 Blender 가 Metal 초기화에서 죽는다. 이를
허용하는 Codex 설정은 없다(Codex 0.171 실측). 그래서 Codex 에게는
[Blender Lab MCP](https://www.blender.org/lab/mcp-server/) 로 샌드박스 밖의 Blender 를 준다. Blender 5.1 이상이 필요하다.

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B --command extension install-file -r user_default -e mcp-1.0.3.zip            # lab.blender.org 의 MCP 애드온
$B --command extension install-file -r user_default -e add-on-mpfb-v2.0.18.zip  # extensions.blender.org 의 MPFB
uv tool install "git+https://projects.blender.org/lab/blender_mcp.git@v1.0.3#subdirectory=mcp"
codex mcp add blender-previs --env BLENDER_MCP_PORT=9877 -- ~/.local/bin/blender-mcp
$B -b --online-mode --command blender_mcp --port 9877   # 작업용 Blender. 창 없이 띄워 둔다
```

- `~/.codex/config.toml` 의 `[mcp_servers.blender-previs]` 에 `default_tools_approval_mode = "approve"` 와
  `tool_timeout_sec = 300` 을 넣는다. 없으면 `codex exec` 가 「MCP tool call requires approval, but approval policy is
  never」로 멈춘다. 사람이 쓰는 GUI Blender(기본 포트 9876)에는 넣지 않는다.
- MCP 애드온은 소켓을 열어서 Blender 의 온라인 접근 허용이 있어야 켜진다. 환경 설정을 바꾸지 않고 그 프로세스에만
  `--online-mode` 를 붙인다.
- 한 번의 호출은 300초 안에 끝나야 한다. 렌더처럼 긴 일은 MCP Blender 안에서 `subprocess.Popen` 으로 자식 Blender 를
  띄우고 로그를 셸에서 읽는다. 자식은 샌드박스 밖이라 GPU 를 쓴다. `--factory-startup` 으로 띄운 자식은 MPFB 를
  올리지 않으므로, 마네킹은 MCP Blender 에서 한 번 만들어 `.blend` 로 저장하고 렌더는 그 파일만 읽는다.
- MCP 는 LLM 이 쓴 코드를 Blender 안에서 막지 않고 돌린다(공식 페이지의 보안 경고). 작업용 Blender 는 빈 장면으로 띄우고
  사람이 쓰는 Blender 와 포트를 나눈다. 예전 커뮤니티판 `Blender MCP` 애드온(ahujasid)도 기본 포트가 9876 이라 같이 켜지 않는다.

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

v5 강체 인형으로 잰 실측(2026-11-22, A7 후렴 8초, Seedance 2.5 720p, 곡을 들려줌, 멤버 셋 + 세트 참고 + 8초 프리비즈, 3,118원, 한 번 생성).

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

MPFB 리깅 마네킹과 가사 안무로 바꾼 v6 실측(2026-11-22, 같은 컷과 조건, 3,118원, 한 번 생성).

- **박.** `follow` 로 15~192프레임을 재니 시차 0 에서 r=0.90 이었다(v5 는 0.79). 녹기, 주먹 쌓기, 웅크리기, V 로 피기,
  사선, 차례로 녹아 와이드 플리에, 높이가 다른 계단, 머리 위로 뻗기, 위아래로 포갠 손바닥이 모두 프리비즈의 착지 프레임에
  나왔다. 0.63초에 셋이 머리부터 발까지 보였다.
- **키.** 왼쪽부터 큰 순서(이담, 하이나, 신더)가 8초 내내 보였다.
- **모양.** 클레이 몸과 옷 껍데기는 묻어나지 않았다. 다만 마네킹은 눈꺼풀을 감은 얼굴이고, 프롬프트에 「Eyes open」을
  적었는데도 Squish 뒤 클로즈업에서 셋 중 둘이 눈을 감고 있었다. 마네킹 얼굴 때문인지 누르는 동작의 표정인지는 아직
  가리지 못했다.
- **안 된 것.** 세트 전환은 이번에도 글대로 되지 않았다. 0.63초에 이미 창고 뒷벽이 있었고 바닥만 젤리처럼 번들거렸다.
