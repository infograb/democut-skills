# 블록아웃

블록아웃은 회색 세계에 인물 알약을 세우고 샷리스트대로 카메라를 움직인 짧은 영상이다. 영상 모델에는 자리, 이동,
카메라, 렌즈, 컷 시각만 알려 준다. 사람에게는 돈을 쓰기 전에 장면 전체를 처음으로 보여 준다.

## 무엇을 넣고 무엇을 빼는가

- **인물은 굳은 알약이다.** 사람 키의 캡슐에 색 가로띠를 둘러 인물을 가른다(머리색, 상의, 하의, 신발). 앞면에 채도 높은
  세로줄 하나를 그어 보는 방향을 보인다([Thomas Lundström, 4:00~5:05](https://www.youtube.com/watch?v=mx1yjt4k73o)). 같은
  제작자의 blockout-kit(MIT) 가 까닭을 적는다. 「Seedance copies whatever body motion the reference shows, so the
  stand-in must show none. A rigid striped capsule gives position, scale, facing and timing only.」(kit
  `skills/blockout/SKILL.md`). 알약은 옮기고 돌리기만 한다. 늘이거나 줄이거나 기울이지 않는다. 막대 팔로 춤의 손 자리를
  보이고 앉는 박에 알약 키를 줄인 music-video A7 v9b 는 그 멈췄다 꺾이는 흐름까지 결과에 옮겨 클레이 애니메이션처럼
  보였다(2026-11-22).
- **겨누는 팔과 돌아보는 고개만 붙인다.** kit 의 팔은 어깨에서 나온 굳은 막대 하나에 총 덩어리를 단 것이고 겨누는 방향만
  바뀐다. 고개는 알약의 키 77% 위를 떼어 몸은 두고 85도까지만 돌린다(kit `docs/shotfile.md`). 손짓, 팔 흔들기, 걷는
  다리는 넣지 않는다. 몸짓은 프롬프트가 준다.
- **색.** kit 는 인물마다 한 색에 검은 줄무늬를 두고 그 색의 옷을 입힌다. 이 스킬은 띠를 그 인물의 머리와 옷 색으로
  칠한다(drama A2 에서 띠가 결과에 나오지 않았고 두 사람이 바뀌지 않았다). 주황 옆 노랑, 파랑 옆 청록처럼 가까운 색
  둘을 한 화면에 두지 않는다. 영상 모델이 섞는다(kit).
- **세트는 덩어리다.** 벽, 문, 창, 식탁, 소파는 회색 상자다. 벽은 중간에서 어두운 회색으로 둔다. 화면 양쪽에 밝고 큰 면이
  있으면 생성이 깨진다(kit). 모양이 결과에 새어 나가므로 결과에 남으면 안 되는 모양을 만들지 않는다. 블록아웃의
  다이아몬드 꽃이 결과에 그대로 나왔다([Thomas Lundström, 12:10](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
- **움직임은 실제처럼.** 차, 드론 카메라, 넘어지는 물건처럼 물리가 보이는 움직임은 실제와 가깝게 만든다. 그 움직임이
  결과로 옮겨진다([Thomas Lundström, 9:34](https://www.youtube.com/watch?v=mx1yjt4k73o)). 알약은 예외다. 알약은 자리,
  방향, 시각만 맞으면 되고 몸짓은 프롬프트에서 온다(kit 「Motion is copied, so it has to be real」).
- **인물 사이 간격.** 인물끼리 닿는 동작(포옹, 몸싸움, 손잡기)이 아니면 그 샷의 가장 큰 동작에서도 팔 끝이 서로 0.3m 넘게
  떨어지게 세우고, 매 프레임 화면에서 인물끼리 겹치지 않는지 본다. music-video 블록아웃에서 붙여 세운 대형이 팔을 펴는
  박에 겹쳤고, 사용자가 큰 동작에는 공간이 있어야 한다고 했다(A7 v9a, 2026-11-22).
- **대사 자리.** 대사 샷에서는 카메라를 잠깐 멈추거나 아주 느리게 둔다
  ([Dan Kieft, 8:38](https://www.youtube.com/watch?v=miIDu04N7_4)).
- **넣지 않는 것.** 얼굴, 손가락, 표정, 화면 글자, 화면 분할. 블록아웃 렌더에는 모션 블러를 넣지 않는다. 결과의 블러는
  프롬프트의 180도 셔터 줄이 정한다([`prompt.md`](prompt.md)).

## 만드는 법

1. `shot_plan.py beats shots.json --json` 으로 샷마다 프레임 범위를 받는다.
2. 장면을 만든다. Workbench, 1280×720(9:16 이면 720×1280), 24fps, 회색 세계와 색 알약. 장소 목록의 장소마다 덩어리 세트.
3. 샷마다 카메라 하나를 두고 그 샷의 렌즈(초점 거리)를 넣는다. 카메라 전환은 타임라인 마커에 카메라를 묶어(bind camera
   to markers) 샷 경계 프레임에서 바뀌게 한다. 마커 이름은 샷 id 와 한 줄 설명이다(「S2 민지 어, 왔어?」).
4. 알약의 이동과 방향을 키로 넣는다. 걷기는 일정한 속도로, 멈춤은 멈춘다. 키, 크기, 기울기는 바꾸지 않는다.
5. 카메라가 활성인 `.blend` 로 저장한다. 렌더는 사람이 확인한 뒤에 한다.

## 감독 리뷰

`.blend` 를 사람이 쓰는 Blender 에서 연다. Claude 는 Blender MCP(포트 9876)로 파일을 열 수 있다. 사용자는 스페이스바로
재생하고 프레임 번호로 메모를 준다. 렌더를 기다리지 않으니 한 바퀴가 빠르다
([Thomas Lundström, 6:13](https://www.youtube.com/watch?v=jc0Qh09Qrlo)). 메모는 샷 단위로 받아 처음부터 고쳐 나간다.
흔한 메모는 카메라 흔들림을 부드럽게, 다음 사람에게 넘어가기 전 잠깐 멈춤, 배경 단순하게, 끝에 전체가 보이게다
([Thomas Lundström, 5:05~5:39](https://www.youtube.com/watch?v=mx1yjt4k73o)).

확인이 끝나면 생성 구간마다 따로 렌더한다. H.264 yuv420p, 소리 없음, 길이는 그 구간의 정수 초와 같다.

```bash
python3 -I <스킬>/scripts/shot_plan.py beats shots.json   # 구간 2 가 전체 241-360 프레임이면 그 범위만 렌더
```

## 장소 스틸

확인한 블록아웃에서 인물, 소품, 탈것을 숨기고 회색 세트만 렌더한다. 장소마다 그 장소가 가장 넓고 잘 보이는 카메라 하나를
고른다. 장소 하나에 그림 하나다. 같은 장소의 그림이 여럿이면 서로 다툰다(kit 「Location plates」). drama A2 는 S1 카메라의
첫 프레임(24mm)을 1280×720 으로 렌더했다. 이 스틸로 실사 장소 그림을 만든다([`democut-drama.md`](democut-drama.md)
「장소 그림」).

## Claude 와 Codex 가 Blender 를 쓰는 법

- Claude Code 는 Blender Lab MCP(`blender`, 포트 9876)로 사람이 쓰는 Blender 를 직접 다룬다. MCP 애드온은 온라인 접근이
  허용된 Blender 에서만 켜진다(`open -a Blender --args --online-mode` 또는 Preferences > System > Network).
- Codex 에게 맡기면 Codex 의 셸 샌드박스가 GPU 를 막아 Blender 를 직접 띄우지 못한다. 작업용 Blender 를 창 없이 따로
  띄워 MCP 로 준다.

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender
$B --command extension install-file -r user_default -e mcp-1.0.3.zip   # lab.blender.org 의 MCP 애드온
uv tool install "git+https://projects.blender.org/lab/blender_mcp.git@v1.0.3#subdirectory=mcp"
codex mcp add blender-previs --env BLENDER_MCP_PORT=9877 -- ~/.local/bin/blender-mcp
$B -b --online-mode --command blender_mcp --port 9877   # 작업용 Blender
codex exec --skip-git-repo-check -s workspace-write -C <작업 폴더> "<지시서를 읽고 수행>" < /dev/null
```

- `~/.codex/config.toml` 의 `[mcp_servers.blender-previs]` 에 `default_tools_approval_mode = "approve"` 와
  `tool_timeout_sec = 300` 을 넣는다. 없으면 `codex exec` 가 승인을 기다리다 멈춘다.
- 한 호출은 300초 안에 끝나야 한다. 렌더는 MCP Blender 안에서 `subprocess.Popen` 으로 자식 Blender 를 띄운다.
- MCP 는 LLM 이 쓴 코드를 Blender 안에서 막지 않고 돌린다. 작업용 Blender 는 빈 장면으로 띄우고 사람이 쓰는 Blender 와
  포트를 나눈다.

music-video 스킬에서 이 설정으로 블록아웃을 만들었다(같은 스킬 `references/previs-reference-video.md`).
