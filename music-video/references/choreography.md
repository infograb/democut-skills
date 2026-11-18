# 안무

안무는 곡에 맞춘다. 박자(언제 움직이나), 구간 에너지(얼마나 크게), 가사(무엇을 하나) 셋이다.
콘티의 안무 칸에 적은 문장이 영상 프롬프트의 안무 문장이 된다.

## 세는 법

- 8카운트 = 8박 = 4/4 박자 두 마디다. 120 BPM 이면 4초, 130 BPM 이면 3.69초.
- 콘티 한 줄(4마디)은 8카운트 둘이다. 안무 칸은 8카운트 단위로 나누되, **프롬프트에는 카운트마다**
  발·몸·손가락·고개와(군무면) 멤버별 차이를 적는다.
- **밀도:** 한 박, 또는 반 박마다 서로 다른 동작을 둔다. 8초 컷이면 16카운트 가까이를 채운다.
  두 박에 동작 하나만 두거나, 앞으로 걸어 나오기만 하는 구간을 두면 애기 율동처럼 보인다.
- 실측: 밀집 안무를 적은 영상에서 지정한 동작이 일부만 나온 적이 있다. 그래도 성기게 줄이면
  「아이돌 안무가 아니라 율동 같다」는 피드백이 났다. 밀도를 유지하고, 만든 뒤 격자로 빠진
  동작을 확인한 다음, 정말 안 그려진 동작만 문장을 더 구체화하거나 반 박을 한 박으로 늘린다.
- **전환 중에는 멈추지 않는다.** 장면이 바뀌거나 구조물이 생기는 동안은 한 박 홀드가 아니다. 그 구간의 박마다
  발·손을 적고, 한 포즈로 얼어 있으면 검수에서 실패다([`camera-moves.md`](camera-moves.md) 「공간이 생겨나는 전환」).

## 화면에서 커 보이는 장치

동작이 커도 화면이 밋밋한 것은 대개 셋 중 하나다. 모두가 제자리에서 손만 움직이거나, 높이가 한 단계뿐이거나, 박마다 힘이
같다. 아이돌 안무가 쓰는 장치로 줄마다 하나 이상을 고른다. 근거는
[Stancz 힙합](https://stancz.com/en/guides/hip-hop-choreography)·[그룹](https://stancz.com/en/guides/group-choreography)·[대형](https://stancz.com/ko/guides/kpop-pomeisyeon),
[포인트 안무](https://ivywxy.medium.com/point-choreography-in-k-pop-d392a27089e2),
[NHSJS 분석](https://nhsjs.com/2025/analysis-of-mathematical-elements-and-physical-principles-in-k-pop-dance) 이다.

| 장치 | 무엇인가 | 프롬프트에 적는 꼴 |
|---|---|---|
| 1·5박 히트 | 8카운트의 1박과 5박에 근육을 순간 조여 크게 찍고, 3·7박은 부드럽게 잇는다 | `a sharp hit on beats 1 and 5, smooth flow on 3 and 7` |
| 홀드 | 박에 맞춰 딱 멈춘다. 움직임 사이의 정지가 대비를 만든다 | `freeze for one beat` |
| 유니즌(칼군무) | 전원이 같은 동작을 같은 순간에 한다. 후렴의 기본 | `all three in perfect unison` |
| 리플(웨이브 릴레이) | 한 명이 시작하면 차례로 받는다. 방향은 왼→오, 가운데→바깥. 실측 예는 멤버 사이 약 0.6초(130 BPM 에서 한 박 남짓) | `an arm wave ripples from LEFT to CENTER to RIGHT, one beat apart` |
| 캐논 | 같은 동작을 멤버마다 시작을 엇갈려 한다 | `the same move in canon, each member one beat later` |
| 대형 바꾸기 | 일자, V, 삼각형, 대각선, 두 줄. 부르는 멤버가 꼭짓점이나 앞 가운데로 나온다 | `they shift from a line into a V formation with CENTER at the front point` |
| 센터 교대 | 파트마다 부르는 멤버가 센터로 나오고 나머지가 맞춰 움직인다 | `RIGHT steps forward into the center while the others step back` |
| 높이 세 단계 | 서기, 무릎 굽히기, 웅크리기를 한 줄 안에서 오간다. 점프는 높이를 바꾸는 수단으로 쓰지 않는다(아래) | `drop into a low crouch on the beat, rise` |
| 핑거댄스(핑거 터팅) | 반 박~한 박마다 손가락 모양이 바뀐다. 각진 손가락 프레임(사각·계단·십자·등호·격자), 깍지와 엇걸기, 손끝으로 얼굴·가슴 둘레를 따라 긋는 선, 손이 맞물리며 다음 모양으로 넘기기, 손목 롤. 직각과 칼각, 손끝까지 힘을 준다. 훅 단어의 시그니처는 짧은 오리지널 핑거 프레이즈로 만들고, 멤버 사이에 한 박씩 어긋나게 리플한다. 쥐었다 펴기 같은 한 동작짜리 단순 손동작을 포인트로 쓰지 않는다 | `both index fingers and thumbs form a sharp rectangle frame in front of the left eye, then rotate it 90 degrees on the beat; finger tutting, precise geometric finger shapes snapping on every beat, no slow raising` |
| 무대 가로지르기·깊이 | 옆으로 이동하고 앞뒤로 나왔다 들어간다. 무대 전체를 써야 커 보인다 | `they travel sideways with big chasse steps, then run two steps toward the camera` |
| 대비·누적 | 느린 동작 옆에 터지는 동작을 둔다. 동작이나 사람을 하나씩 더해 간다 | `slow body roll, then an explosive jump` |
| 카운터포인트 | 한 명이 솔로를 하는 동안 나머지는 다른 동작을 한다 | `CENTER dances a solo while LEFT and RIGHT hold a low pose` |
| 반대 방향 회전 | 가운데는 돌고 바깥은 반대로 움직인다 | `CENTER spins clockwise while the outer two step counter-clockwise` |
| 소리 층에 맞춘 질감 | 베이스에는 바닥을 딛고, 스네어에는 끊어 치고, 신스에는 웨이브 | `a stomp on the bass hit, a body wave over the synth` |

- 줄마다 **높이를 한 번은 바꾸고, 자리를 한 번은 옮긴다.** 높이는 무릎 굽히기와 웅크리기로 바꾼다.
- **점프는 아낀다.** 영상 하나에 많아야 한 번, 강세가 가장 큰 박에만 둔다. 장면마다 점프를 넣은 군무 컷은
  「점프를 너무 많이 넣지 말고 손가락이나 손 디테일을 살리는 동작을 넣어 달라」는 피드백을 받았다.
- **손·손가락 동작을 줄마다 하나 이상 둔다.** 아이돌 안무의 볼거리는 손끝에 많다. 손이 화면 안에 다 보이게 적고
  (`fingers clearly visible in frame`), 곡 주제와 이어지는 손짓을 고른다. 실존 그룹의 시그니처 손 모양을
  이름이나 묘사로 지시하지 않는다.

### 율동처럼 보이지 않게

쓰지 말 것: 손을 크게 흔들기, 콩콩 뛰기, 토끼 점프, 두 손을 머리 위에서 흘리기, 주먹을 위로 쌓듯 올리기 같은
문자 그대로의 마임, 주먹을 쥐었다 펴기를 포인트로 쓰기, 두 박에 동작 하나만 두기, 앞으로 걸어 나오기만 하는 구간,
끝에 다 같이 점프, 아래로 향하거나 위로 향한 꺾쇠(셰브론), 손가락 V, 하트 모양 꺾쇠, 손가락 총, 전화 거는 손(콜미),
같은 손 모양을 유지한 채 손을 천천히 올리거나 내리기. 손바닥에 플러스(+) 같은 그래픽이 생기게 적지 않는다.

쓸 것: 한 박(또는 반 박)마다 다른 동작, 쉬지 않는 하체(탭, 크로스 백, 스톰프, 킥, 슬라이드, 무릎 인앤아웃, 무게 이동),
고개·가슴·골반을 따로 쓰는 아이솔레이션(가슴과 골반은 반대 방향), 히트와 플로우를 섞고 한 박 멈춤 뒤에 터뜨리기,
멤버 간 한 박 리플, 대형 전환 두 번 이상, 높낮이와 턴, 같은 포즈로 딱 멈추는 엔딩. 시선과 태도도 안무의 일부다.
훅에서 표정이 바뀐다(무표정에서 살짝 웃는 얼굴 등).
- 후렴은 유니즌, 벌스는 센터 교대·카운터포인트, 프리코러스는 리플·누적으로 쌓고, 후렴 직전 박에 홀드를 둔다.

## 가사에서 동작으로

가사 줄마다 동작 하나를 붙인다. 낱말을 몸으로 옮기면 기억에 남는다.

| 가사의 성격 | 동작으로 옮기는 법 | 예 |
|---|---|---|
| 동사(쥐다·돌리다·녹다·켜다) | 그 동작을 손이나 몸으로 그대로 | 「녹아내려」 머리부터 무릎까지 웨이브로 내려간다 |
| 나·너를 가리키는 말 | 가리키기(엄지로 자신, 검지로 카메라) | 「이제 내 차례야」 엄지로 자신을 가리키며 한 걸음 |
| 숫자·카운트 | 손가락을 펴고 한 박에 하나씩 접는다 | 「three, two, one」 |
| 곡 제목·후렴 구호 | 포인트 동작(아래) | |
| 감정·분위기 말 | 표정과 상체(윙크, 고개 기울이기, 어깨 바운스) | |

### 포인트 동작

후렴의 제목 구호에 붙는 동작 하나를 정하고 **후렴마다 되풀이한다**. 인트로에서 작게 미리 보여 주고, 1절 후렴에서
처음 크게 하고, 2절 후렴에서는 하체(런지·스텝)를 더해 더 크게 하고, 아웃트로에서 다시 작게 맺는다. 같은 모티프가
커지는 것이 곡의 기승전결이다.

## 구간 에너지와 동작 크기

`mv_timing.py energy` 로 잰 음량이 동작 크기를 정한다.

| 구간 | 동작 |
|---|---|
| 인트로(비트가 가벼우면) | 손과 상체 위주로 작고 정확하게. 비트가 크게 들어오는 박을 기다리는 자세로 끝낸다 |
| 벌스 | 군무 없이 파트 멤버의 걸음·손짓·시선. 나머지 멤버는 화면 밖이나 뒤에서 작게 |
| 프리코러스 | 대형을 모으며 점점 크게. 마지막 박에 멈춤 |
| 후렴 | 전원 같은 동작(유니즌). 포인트 동작 |
| 2절 후렴·마지막 후렴 | 하체까지 크게(사이드 런지, 바닥까지 내려가는 웨이브, 점프는 가장 큰 박 한 번), 대형 이동 |
| 소리 빈 자리 | 점프 정점에서 멈추거나 포즈로 정지 |
| 아웃트로 | 인트로 동작을 되풀이하며 한 명씩 맺는다 |

## 챌린지 구간

숏폼에서 따라 하게 할 구간 하나를 정한다(대개 후렴의 한 줄, 15초 안).

- 상체와 손이 세로(9:16) 구도에서 먼저 읽히게 하되, 하체를 멈추지 않는다. 세로로 가운데를 잘라도 멤버가 다 들어온다.
- 뮤직비디오용 전신 샷과 챌린지용 상반신 샷은 따로 잡는다.
- 8카운트 하나를 정하고 다음 8카운트는 좌우를 바꿔 되풀이한다.
- 카메라는 정면을 지키고 풀숏과 무릎 위 숏 사이로 박에 맞춰 작게 밀고 뺀다(따라 하는 사람이 보고 배우는 각도,
  [`camera-moves.md`](camera-moves.md) 「안무 장면은 카메라가 박자에 맞춰 앞뒤로 움직인다」).
- 동작마다 가사 낱말과 짝이 있다(따라 부르며 따라 한다).

## 영상 프롬프트로 옮기기

안무 칸을 영어로 옮길 때는 이 순서로 적는다.

1. 첫머리에 밀도 문장: `K-pop idol choreography, dense sharp beat hits, isolations and finger tutting, not a children's nursery dance`
2. 대형과 자리, 그리고 대형이 어떻게 바뀌는지: `the three members stand in a V formation, CENTER slightly in front, then shift into a line`
3. 박에 맞춘다는 말: `dancing in unison, every move lands on the beat of the attached music`
4. 카운트마다, 군무면 멤버(LEFT·CENTER·RIGHT)마다 발·몸·손가락·고개를 적는다. 「energetic dancing」처럼 덩어리로 적지 않는다.
   가사가 있는 줄은 그 순서도 함께 적는다: `on beat 1 CENTER: right toe tap, both index fingers and thumbs snap into a sharp rectangle frame in front of the chest; LEFT slightly deeper in the knee`
5. 동작 크기: `small, precise upper-body and hand moves because the intro beat is light`
6. 끝 자세: `on the final beat they hit the ending pose on the ground, no jump, and freeze`

동작은 형용사가 아니라 **이름 있는 동작을 순서대로** 적는다. 「energetic dancing」, 「dynamic moves」만 적으면 타이밍이 제멋대로이고
동작이 작게 나온다(`hit two chest pops on the beat, step right-left-right, half-turn, finish with a sharp arm lock` 꼴이 낫다,
[Seedance.tv](https://www.seedance.tv/blog/ai-dance-video-prompt-examples)). 끝 자세를 적지 않으면 마지막 1~2초가 쓸모없는 움직임으로
채워지기 쉽다. 카메라 문장은 동작 문장과 떼어 적는다([`camera-moves.md`](camera-moves.md)).
핑거댄스 구간에는 `finger tutting, precise geometric finger shapes snapping on every beat, no slow raising` 을 넣는다.

가사 줄이 영어가 아니면 가사를 따옴표로 넣지 말고 「second line」처럼 차례로 부른다. 안무 줄은 될 수 있으면 입모양 없이
안무에 집중한다. `nobody sings, every mouth stays closed` 처럼 입을 다문다고 적는다. 꼭 입을 보여야 하는 줄만
[`democut-mv.md`](democut-mv.md) 「입을 맞춰 부르는 줄(단독샷)」대로 부르는 멤버의 단독샷으로 만들고, 한국어 입모양은
그 문서의 「한국어 가사의 입모양」 MOUTH MAP 한 블록만 쓴다.

모델이 동작을 차례대로 다 그리는지는 미확인이다. 만든 뒤 `mv_timing.py sheet --bpm <곡 BPM>` 으로 동작 순서와 박을
확인하고, 빠진 동작이 많으면 문장을 더 구체화하거나 그려지지 않은 동작만 한 박으로 늘린다. 밀도 자체를 반으로 줄이지 않는다.
금지한 손 모양(꺾쇠, V, 하트 꺾쇠, 손가락 총, 콜미, 쥐었다 펴기)이 나왔는지도 격자로 본다.
