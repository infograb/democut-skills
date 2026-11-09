# DemoCut Skills — 에이전트용 저장소 안내

이 저장소는 **DemoCut 쓰임새 스킬 모음**이다. DemoCut 제품 안에 넣기 애매하지만 DemoCut 으로 영상을 만들 때
앞뒤로 필요한 일을 스킬로 담는다. 스킬은 문서가 중심이고, 눈대중으로 하기 어려운 계산은 스킬 안 `scripts/` 가 맡는다.

## 구조

- `<skill-name>/SKILL.md` — 스킬 진입점. 프론트매터 + 워크플로우
- `<skill-name>/references/*.md` — 깊은 지식. 필요할 때만 읽는다
- `<skill-name>/scripts/` — 스킬이 부르는 도구(선택). 표준 라이브러리만 쓴다
- `<skill-name>/evals/<case>/` — 스킬 평가 케이스(선택). `claude plugin eval` 이 읽는 형식
- `scripts/validate-skills.sh` — 구조 검증 + 스킬 스크립트 문법 검사 (`npm run lint`)

## 수정할 때

- 실측으로 확인한 것만 적는다. 추측은 "미확인" 으로 표시한다.
- 외부 API 가 바뀌면 `references/` 를 같은 PR 에서 갱신한다.
- 프론트매터 `name` 은 디렉토리명과 같아야 한다 (검증 스크립트가 잡는다).

상세: [`CONTRIBUTING.md`](CONTRIBUTING.md)
