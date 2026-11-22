# 블록아웃

블록아웃은 회색 세계에 인물 알약을 세우고 샷리스트대로 카메라를 움직인 짧은 영상이다. 영상 모델에는 자리, 이동,
카메라, 렌즈, 컷 시각만 알려 준다. 사람에게는 돈을 쓰기 전에 장면 전체를 처음으로 보여 준다.

## 무엇을 넣고 무엇을 빼는가

- **인물은 알약이다.** 사람 키의 캡슐에 색 가로띠를 둘러 인물을 가른다(머리색, 상의, 하의, 신발). 앞면에 채도 높은 세로줄
  하나를 그어 보는 방향을 보인다. 회색 화면에서 눈에 띄고 사람 모양이 아니라 연기가 옮겨지지 않는다
  ([Thomas Lundström, 4:00~5:05](https://www.youtube.com/watch?v=mx1yjt4k73o)).
- **필요한 것만 붙인다.** 총을 겨누는 팔이나 돌아보는 고개처럼 그 샷의 뜻에 꼭 필요한 것만 막대로 붙인다. 적을수록 좋다
  (같은 영상).
- **세트는 덩어리다.** 벽, 문, 창, 식탁, 소파는 회색 상자다. 모양이 결과에 새어 나가므로 결과에 남으면 안 되는 모양을
  만들지 않는다. 블록아웃의 다이아몬드 꽃이 결과에 그대로 나왔다([Thomas Lundström, 12:10](https://www.youtube.com/watch?v=jc0Qh09Qrlo)).
- **움직임은 실제처럼.** 차, 드론 카메라, 넘어지는 물건처럼 물리가 보이는 움직임은 실제와 가깝게 만든다. 그 움직임이
  결과로 옮겨진다([Thomas Lundström, 9:34](https://www.youtube.com/watch?v=mx1yjt4k73o)).
- **대사 자리.** 대사 샷에서는 카메라를 잠깐 멈추거나 아주 느리게 둔다
  ([Dan Kieft, 8:38](https://www.youtube.com/watch?v=miIDu04N7_4)).
- **넣지 않는 것.** 얼굴, 손가락, 표정, 화면 글자, 모션 블러, 화면 분할.

## 만드는 법

1. `shot_plan.py beats shots.json --json` 으로 샷마다 프레임 범위를 받는다.
2. 장면을 만든다. Workbench, 1280×720(9:16 이면 720×1280), 24fps, 회색 세계와 색 알약. 장소 목록의 장소마다 덩어리 세트.
3. 샷마다 카메라 하나를 두고 그 샷의 렌즈(초점 거리)를 넣는다. 카메라 전환은 타임라인 마커에 카메라를 묶어(bind camera
   to markers) 샷 경계 프레임에서 바뀌게 한다. 마커 이름은 샷 id 와 한 줄 설명이다(「S2 민지 어, 왔어?」).
4. 알약의 이동과 방향을 키로 넣는다. 걷기는 일정한 속도로, 멈춤은 멈춘다.
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

확인한 블록아웃에서 알약을 숨기고 장소마다 대표 카메라의 스틸을 1280×720 으로 렌더한다. 이 스틸을 참고로 실사 장소
그림을 만든다([`democut-drama.md`](democut-drama.md) 「장소 그림」). 한 장소가 여러 방향으로 보이면 방향마다 스틸을 둔다.

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
