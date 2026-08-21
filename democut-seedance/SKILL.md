---
name: democut-seedance
description: >
  BytePlus ModelArk(Dreamina Seedance)로 AI 영상을 생성한다. 텍스트나 이미지에서
  4~30초 영상을 만들고, 비용을 사전 계산하며, 작업을 폴링해 결과를 내려받는다.
  "영상 만들어줘", "seedance", "AI 영상 생성", "text to video", "image to video",
  "영상 비용 얼마" 관련 요청 시 자동 호출.
license: SUL-1.0
metadata:
  category: video
  locale: ko-KR
  author: infograb
  phase: v1
---

# DemoCut Seedance — AI 영상 생성

BytePlus ModelArk 의 Dreamina Seedance 모델로 영상을 생성하는 스킬.
**제출 → 폴링 → 다운로드** 3박자이며, 생성 한 번이 실제 비용이므로 **제출 전 비용을
계산하고 사람에게 확인받는 것이 기본 절차**다.

## What this skill does

- 텍스트 프롬프트 또는 참조 이미지에서 4~30초 영상 생성
- 제출 전 **결정론적 비용 계산** (토큰 = duration × W × H × fps / 1024)
- 비동기 작업 폴링 및 결과 다운로드 (결과 URL 은 24시간 만료)
- 모델별 duration·해상도 제약 사전 검증으로 4xx 실패 방지
- 중복 제출 방어 (BytePlus 는 Idempotency-Key 를 지원하지 않는다)

## When to use

- "이런 장면의 영상 만들어줘"
- "이 이미지를 움직이게 해줘"
- "1080p 15초 영상 비용이 얼마야?"
- "생성 중인 영상 다 됐어?"

## When not to use

- **토킹헤드 / 립싱크 아바타** — Seedance 는 오디오를 음색 참조로만 쓰고 발화는
  프롬프트 대사에서 합성한다(진짜 립싱크가 아니다). 립싱크가 필요하면 OmniHuman 1.5
  또는 기존 Higgsfield 경로를 쓴다.
- **음성 합성** — 나레이션은 TTS(ElevenLabs/Fish)가 담당한다. `generate_audio` 는
  끄고 오디오는 따로 mux 하는 것이 DemoCut 파이프라인의 전제다.
- 30초를 넘는 영상 — 모델 상한이다. 여러 컷으로 나눠 생성하고 이어붙인다.

## Prerequisites

**필수**: `BYTEPLUS_API_KEY` 환경변수.
BytePlus 콘솔 → ModelArk → API Key 에서 발급한다.

⚠️ **키만으로는 호출되지 않는다.** 두 가지가 선행되어야 한다:
1. 콘솔에서 **모델 활성화**
2. **리소스 팩(선불 토큰) 구매** — 미구매 시 활성화 자체가
   `400 No available resource packs` 로 거부된다. 팩은 **모델 전용**이라 2.0 팩으로
   2.5 를 열 수 없고, **환불되지 않으며 90일 만료**다. 볼륨 할인이 없으므로
   최소 팩부터 사는 것이 합리적이다.

**동시 실행 상한**은 계정 유형이 정한다 — 개인 3 / 기업 10. Organization 을 만들어도
바뀌지 않는다(계정 유형은 가입 시 확정되며 변경 불가).

## 환경 컨텍스트 (자동 수집)

- API 키: !`[ -n "$BYTEPLUS_API_KEY" ] && echo "설정됨" || echo "미설정 — 생성 불가"`
- curl: !`which curl >/dev/null 2>&1 && echo available || echo unavailable`
- ffprobe: !`which ffprobe >/dev/null 2>&1 && echo available || echo "unavailable (결과 검증 제한)"`

## Workflow

### 1) 비용을 먼저 계산하고 사람에게 확인받는다

토큰은 **완전히 결정론적**이다. 프롬프트 내용·오디오 유무와 무관하게
해상도·길이·프레임레이트만으로 정해진다.

```
토큰 = duration(초) × 가로 × 세로 × 24 / 1024
비용 = 토큰 × $4.30 / 1,000,000     (리소스 팩 기준)
```

실측 기준선 (`references/cost.md` 에 전체 표):

| 사양 | 토큰 | 비용 |
|---|---|---|
| 480p 4초 | 40,594 | **$0.17** |
| 720p 10초 | 216,000 | $0.93 |
| 1080p 15초 | 734,400 | $3.16 |

**$1 을 넘는 요청은 반드시 사람에게 확인받고 진행한다.**

### 2) 제출한다

```bash
curl -X POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BYTEPLUS_API_KEY" \
  -d '{
    "model": "dreamina-seedance-2-0-260128",
    "content": [{ "type": "text", "text": "<프롬프트>" }],
    "duration": 5,
    "ratio": "16:9",
    "resolution": "720p",
    "watermark": false,
    "generate_audio": false
  }'
```

응답은 `{"id": "cgt-..."}` 뿐이다. **이 id 를 반드시 보존한다** — 잃어버리면
같은 영상을 다시 만들어야 하고 그건 재과금이다.

이미지에서 생성할 때는 `content` 에 `{"type":"image_url","image_url":{"url":"https://..."}}`
를 추가하고, **프롬프트 본문에서 `[Image 1]` 로 명시 참조**한다(넣기만 하면 무시될 수 있다).
URL 은 **공개 HTTPS** 여야 한다 — 로컬 경로도 base64 도 받지 않는다.

### 3) 폴링한다

```bash
curl -s https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/<id> \
  -H "Authorization: Bearer $BYTEPLUS_API_KEY"
```

`status` 는 `queued` → `running` → `succeeded` / `failed` / `cancelled`.
**5~10초 간격**으로 폴링한다. 실측 생성 시간은 480p 4초 기준 **약 90초**이며
해상도·길이에 따라 늘어난다.

### 4) 즉시 내려받는다

성공하면 `content.video_url` 이 온다. **24시간 만료 서명 URL** 이므로
확인 후로 미루지 말고 바로 저장한다.

```bash
curl -sL "<video_url>" -o out.mp4
ffprobe -v error -show_entries format=duration -show_entries stream=codec_type,width,height out.mp4
```

## 반드시 지킬 것

- **실패해도 같은 요청을 무작정 재시도하지 않는다.** BytePlus 는 `Idempotency-Key` 를
  지원하지 않아 재시도가 곧 재과금이다. 먼저 작업 조회로 상태를 확인한다.
- **타임아웃은 실패가 아니다.** 폴링 시한을 넘겨도 작업은 서버에서 계속 돈다.
  새로 제출하지 말고 `job_id` 로 다시 조회한다.
- **생성 실패(`failed`)는 과금되지 않는다.** 다만 같은 프롬프트는 같은 이유로 다시
  실패하므로, 프롬프트를 바꾸지 않은 재시도는 무의미하다.
- **테스트는 mini/fast 로 한다.** 품질 비교가 목적이 아니라면 `dreamina-seedance-2-0-mini-260615`
  720p 가 정품의 일부 비용으로 같은 파이프라인을 검증해 준다.

## References

- `references/models.md` — 모델 카탈로그(duration·해상도·특성)와 선택 기준
- `references/cost.md` — 토큰 공식, 해상도별 비용표, 리소스 팩 운영
- `references/pitfalls.md` — 실측으로 확인된 함정 모음
