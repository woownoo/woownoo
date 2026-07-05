# 🗺️ 구글맵 ↔ 카카오맵 비교 자동화

**구글맵에는 있지만 카카오맵에는 없는 장소**를 자동으로 찾아, 카카오맵
`신규 장소 등록(제보)`에 바로 쓸 수 있는 후보 리스트를 뽑아주는 도구입니다.
제보 후보에는 카카오 등록 폼의 **필수 항목(장소명·위치)** 이 반드시 채워져
있으며, 선택 항목(업종·전화번호·영업시간·웹사이트)도 가능한 만큼 채워
승인율을 높입니다.

## ⚠️ 먼저 읽어주세요 — 제보 제출은 자동화하지 않습니다

이 도구는 **후보 발굴까지만** 자동화하고, 카카오맵에 실제로 제보를 넣는
행위는 자동화하지 않습니다.

- 봇으로 리워드(포인트) 제보를 대량 자동 제출하는 것은 카카오 이용약관의
  어뷰징 금지에 해당하며, 계정 정지 위험이 있습니다.
- 따라서 사람이 CSV를 보고 **직접 확인 후 등록**하는 것을 전제로 합니다.
  실제로 존재하는 장소만 걸러 제보하므로 반려율도 낮고 안전합니다.

공식 API(구글 Places API, 카카오 로컬 API)만 사용하며 웹 스크래핑은 하지
않습니다.

## 📦 준비

```bash
pip install -r requirements.txt
cp .env.example .env   # .env 에 API 키 입력
```

발급할 키 2개:

| 키 | 발급처 |
|----|--------|
| `GOOGLE_PLACES_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) → **Places API (New)** 활성화 후 발급 |
| `KAKAO_REST_API_KEY` | [Kakao Developers](https://developers.kakao.com) → 앱 → 앱 키 → **REST API 키** |

> `.env` 는 `.gitignore`에 포함되어 커밋되지 않습니다. 키를 코드에 직접
> 넣지 마세요.

## 🚀 사용법

### 1) 단일 지점 (동네 하나 빠르게)

```bash
python -m src.main --lat 37.4979 --lng 127.0276 --radius-km 0.5 \
    --types restaurant cafe store
```

### 2) 전국 배치 (지역 목록 순회 · 중단/재개 가능)

`data/korea_regions.csv` 에 주요 도시 도심 21곳이 들어 있습니다.
(헤더: `name,lat,lng,radius_km` — 원하는 시/군/구를 추가·수정하세요.)

```bash
# 먼저 비용/규모만 추정 (API 호출 안 함)
python -m src.main --regions-file data/korea_regions.csv --estimate

# 실제 실행 (예산 상한을 걸어 안전하게)
python -m src.main --regions-file data/korea_regions.csv \
    --run-name korea --max-kakao-calls 90000
```

- 같은 `--run-name` 으로 다시 실행하면 **처리한 격자를 건너뛰고 이어서** 진행합니다.
- 결과는 후보가 나올 때마다 `output/<run-name>_candidates.csv` 에 즉시 누적 저장됩니다(중단돼도 보존).
- 진행 상태는 `output/<run-name>_progress.json` 에 기록됩니다.

주요 옵션:

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--lat`, `--lng`, `--radius-km` | 단일 지점 모드 | — / 0.5km |
| `--regions-file` | 전국 모드: 지역 목록 CSV | — |
| `--run-name` | 전국 모드: 재개용 실행 이름 | korea |
| `--grid-step-m` | 격자 간격(m) | 400 |
| `--cell-radius-m` | 격자점당 검색 반경(m) | 300 |
| `--types` | 구글 장소 타입 | restaurant cafe store |
| `--max-cells` | 이번 실행 최대 격자 수 | 무제한 |
| `--max-kakao-calls` | 이번 실행 카카오 호출 상한 | 무제한 |
| `--estimate` | 비용만 추정하고 종료 | off |

### ⚠️ '전국 전체 격자'는 왜 안 하나요?

남한 육지를 400m 격자로 다 훑으면 **약 60만+ 격자점 → 구글 API만 약 $19,000
(2,600만 원), 카카오 무료 쿼터로 수주~수개월**이 걸립니다. 대부분은 바다·산
등 빈 호출입니다. 그래서 **미등록 장소가 나올 확률이 높은 도심을 지역 단위로
쪼개** 순차·재개 실행하는 방식을 씁니다. 시작 목록 21곳 기준 추정치:

```
격자점 ≈ 6,500  ·  구글 ≈ $208  ·  카카오 ≈ 5.2만 회(무료 하루치)
```

지역을 넓히고 싶으면 `data/korea_regions.csv` 에 시/군/구를 추가하면 됩니다.

## 📄 결과 예시 (CSV 열)

| 열 | 카카오 폼 매핑 |
|----|----------------|
| `장소명(필수)` | 장소명 (필수) |
| `위치_주소(필수)`, `위치_위도(필수)`, `위치_경도(필수)` | 위치 (필수) |
| `업종` | 업종 (선택) |
| `전화번호` | 전화번호 (선택) |
| `SNS_웹사이트` | SNS (선택) |
| `영업시간` | 영업시간 (선택) |
| `kakao_check_url` | 카카오맵에서 실제로 없는지 재확인용 링크 |
| `google_maps_url` | 구글맵 원본 링크 |

## 🧠 동작 원리

1. **격자 탐색** — 중심 좌표 주변을 격자점으로 나눠 각 지점을 구글
   Places API(Nearby Search)로 훑어 장소를 수집.
2. **중복 제거** — 같은 place_id 는 한 번만.
3. **카카오 대조** — 각 구글 장소의 이름으로, 그 좌표 반경 안에서 카카오
   로컬 API를 검색. 이름 유사도(rapidfuzz)와 거리(하버사인)로 같은 장소인지
   판정.
4. **후보 선별** — 카카오에서 매칭이 없고 **필수 항목이 모두 채워진** 장소만
   후보로 남김.
5. **저장** — CSV/JSON 출력.

매칭 임계값은 `src/comparator.py` 상단 상수(`MATCH_RADIUS_M`,
`NAME_SIMILARITY_THRESHOLD`)로 조정할 수 있습니다.

## 🧪 테스트

```bash
python -m pytest tests/ -v
```

## 📁 구조

```
src/
  google_maps.py   # 구글 Places API 클라이언트 + 공통 Place 모델
  kakao_maps.py    # 카카오 로컬 API 클라이언트
  comparator.py    # 이름/거리 기반 동일 장소 판정 + 후보 선별
  regions.py       # 지역 정의 · 격자 생성 · 비용 추정
  runner.py        # 전국 배치 러너 (체크포인트/재개 · 누적 저장)
  reporter.py      # 단일 지점 결과 CSV/JSON 저장
  main.py          # CLI (단일 지점 / 전국 모드)
data/
  korea_regions.csv  # 전국 시작 지역 목록 (주요 도시 도심 21곳)
tests/
  test_comparator.py
  test_regions.py
output/            # 결과물 · 진행 상태 저장 위치
```
