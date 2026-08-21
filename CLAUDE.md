# DemoCut Skills — 에이전트용 저장소 안내

이 저장소는 **스킬 문서 모음**이다. 실행 코드가 없다.

## 구조

- `<skill-name>/SKILL.md` — 스킬 진입점. 프론트매터 + 워크플로우
- `<skill-name>/references/*.md` — 깊은 지식. 필요할 때만 읽는다
- `scripts/validate-skills.sh` — 구조 검증 (`npm run lint`)

## 수정할 때

- 실측으로 확인한 것만 적는다. 추측은 "미확인" 으로 표시한다.
- 외부 API 가 바뀌면 `references/` 를 같은 PR 에서 갱신한다.
- 프론트매터 `name` 은 디렉토리명과 같아야 한다 (검증 스크립트가 잡는다).

상세: [`CONTRIBUTING.md`](CONTRIBUTING.md)
