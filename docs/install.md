# 설치

## 자동 (권장)

에이전트에게:

```
DemoCut 스킬을 설치해줘.
1. `npx skills add infograb/infograb-democut-skills` 를 실행한다.
2. BYTEPLUS_API_KEY 환경변수가 설정돼 있는지 확인하고, 없으면 어디서 발급하는지 알려준다.
설치가 끝나면 알려줘.
```

## 수동

### Claude Code

```bash
npx skills add infograb/infograb-democut-skills
```

또는 저장소를 클론해 스킬 디렉토리를 `~/.claude/skills/` 로 복사한다.

```bash
git clone https://github.com/infograb/infograb-democut-skills.git
cp -r infograb-democut-skills/democut-seedance ~/.claude/skills/
```

### 그 외 에이전트

`SKILL.md` 는 표준 Markdown 이라 Cursor·Codex 등 Markdown 스킬을 읽는 도구에서
그대로 동작한다. 각 도구의 스킬 디렉토리에 복사한다.

## 자격증명

`BYTEPLUS_API_KEY` 가 필요하다.

1. [BytePlus 콘솔](https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey) 에서 API Key 발급
2. **리소스 팩 구매** — 이게 없으면 모델 활성화가 `400 No available resource packs` 로 거부된다
3. 콘솔에서 사용할 모델 활성화

```bash
export BYTEPLUS_API_KEY="ark-..."
```

⚠️ 키를 저장소나 대화에 붙여넣지 않는다. 환경변수나 시크릿 관리자를 쓴다.

## 확인

설치 후 에이전트에게 "seedance로 4초짜리 테스트 영상 만들어줘" 라고 하면
스킬이 호출된다. 비용($0.17)을 먼저 알려주고 확인을 요청하는 것이 정상 동작이다.
