# 설치

## 자동 (권장)

에이전트에게:

```
DemoCut 스킬을 설치해줘.
`npx skills add infograb/democut-skills` 를 실행하고, 설치가 끝나면 알려줘.
```

## 수동

### Claude Code

```bash
npx skills add infograb/democut-skills
```

또는 저장소를 클론해 스킬 디렉토리를 `~/.claude/skills/` 로 복사한다.

```bash
git clone https://github.com/infograb/democut-skills.git
cp -r democut-skills/room-set-planner ~/.claude/skills/
```

### 그 외 에이전트

`SKILL.md` 는 표준 Markdown 이라 Cursor·Codex 등 Markdown 스킬을 읽는 도구에서
그대로 동작한다. 각 도구의 스킬 디렉토리에 복사한다.

## 스킬별 준비물

| 스킬 | 필요한 것 |
|---|---|
| `room-set-planner` | Python 3.8 이상(표준 라이브러리만). 오늘의집 페이지를 읽으려면 에이전트에 Tavily MCP(`tavily-search`, `tavily-extract`)가 연결돼 있어야 한다 — 오늘의집은 직접 요청을 403 으로 막는다 |

## 확인

설치 후 에이전트에게 「3m × 3.5m 방 하나를 서재로 꾸며줘」 라고 하면 `room-set-planner` 가 호출된다.
방 구조를 만들고, 오늘의집 제품을 찾아 실측을 확인하고, 평면도 HTML 을 내놓는 것이 정상 동작이다.
