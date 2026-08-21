# DemoCut Skills

DemoCut 에이전트 스킬 컬렉션 — AI 영상 생성과 자동 편집 파이프라인을
Claude Code·Cursor·Codex 같은 에이전트에서 바로 쓰기 위한 절차 지식.

## 설치

에이전트에게 아래 문장을 그대로 붙여넣으세요.

```
DemoCut 스킬을 설치해줘.
1. `npx skills add infograb/infograb-democut-skills` 를 실행한다.
2. BYTEPLUS_API_KEY 환경변수가 설정돼 있는지 확인하고, 없으면 어디서 발급하는지 알려준다.
설치가 끝나면 알려줘.
```

수동 설치는 [`docs/install.md`](docs/install.md) 참조.

## 스킬

| 스킬 | 하는 일 |
|---|---|
| [`democut-seedance`](democut-seedance/SKILL.md) | BytePlus Seedance 로 AI 영상 생성 — 비용 사전 계산, 제출·폴링·다운로드, 모델 선택 |

## 이 스킬이 다루지 않는 것

- **립싱크 아바타** — Seedance 는 진짜 립싱크가 아니다(오디오를 음색 참조로만 쓴다).
  토킹헤드는 OmniHuman 1.5 나 기존 Higgsfield 경로를 쓴다.
- **음성 합성** — 나레이션은 TTS 담당이다.

## 왜 스킬인가

영상 생성은 호출 한 번이 실제 돈이다(1080p 15초 ≈ $3.16). 그런데 API 문서는
"어떻게 호출하는가"만 알려주고 **"언제 호출하면 안 되는가"** 는 알려주지 않는다.

이 스킬은 실측으로 확인된 함정을 담는다 — 멱등 키가 없어서 재시도가 재과금이라는 것,
결과 URL 이 24시간 만에 만료된다는 것, 리소스 팩 없이는 모델 활성화조차 안 된다는 것.
에이전트가 이걸 모르면 조용히 돈이 샌다.

## 개발

```bash
npm run lint    # 스킬 구조 검증
```

기여 규약은 [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

© 2026 InfoGrab · [SUL-1.0](LICENSE.md)
