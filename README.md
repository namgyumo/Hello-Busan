<div align="center">

# 🌊 Hello, Busan!

**부산의 쾌적한 관광지를 실시간으로 추천해드립니다.**

[![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/ko/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)](https://developer.mozilla.org/ko/docs/Web/CSS)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/ko/docs/Web/JavaScript)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![XGBoost](https://img.shields.io/badge/XGBoost-EC4E20?style=for-the-badge&logo=xgboost&logoColor=white)](https://xgboost.readthedocs.io/)
[![Leaflet](https://img.shields.io/badge/Leaflet-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![AWS EC2](https://img.shields.io/badge/AWS_EC2-FF9900?style=for-the-badge&logo=amazonec2&logoColor=white)](https://aws.amazon.com/ec2/)

</div>

## 📖 프로젝트 소개

**Hello, Busan!** 은 부산을 방문하는 관광객들에게 **"덜 붐비면서 나한테 맞는 관광지"** 를 실시간으로 추천해주는 스마트 웹 서비스입니다.

공공데이터포털의 실시간 데이터(혼잡도, 날씨, 교통)를 수집·분석하고, **XGBoost 머신러닝 모델**로 개인 맞춤 추천 점수를 예측하여 최적의 관광지를 제안합니다.

### 차별점

- 🔥 **실시간 혼잡도 + XGBoost 스마트 추천** — 단순 인기순이 아닌 ML 기반 개인화 추천
- 🌤️ **쾌적함 지수** — 날씨 + 혼잡도 + 교통을 종합한 독자적 지표
- 📡 **SSE 실시간 갱신** — 페이지 새로고침 없이 데이터 자동 업데이트

### 타겟 사용자

국내 관광객 (우선) → 외국인 관광객 → 부산 시민 순으로 확장 예정

> 📌 **1인 바이브 코딩 프로젝트** — 포트폴리오 + 대회 출품용

## 🗺️ 주요 기능 (MVP)

| 기능 | 설명 |
|------|------|
| 📍 **위치 기반 추천** | 사용자 현재 위치 기반으로 가까운 관광지 추천 |
| 🤖 **카테고리 가중치 추천 (XGBoost)** | 자연/문화/음식 등 카테고리별 선호도를 반영한 ML 추천 |
| 📊 **쾌적함 지수 대시보드** | 날씨 + 혼잡도 + 교통 종합 쾌적함 점수 시각화 |
| 🏖️ **관광지 상세 페이지** | 실시간 혼잡도, 날씨, 교통 정보를 한 눈에 확인 |
| 🗺️ **지도 히트맵** | Leaflet.js 기반 혼잡도 히트맵 시각화 |
| 📡 **실시간 데이터 갱신** | SSE 서버 푸시로 자동 갱신 |
| 🌐 **다국어 지원** | 부산 관광 API 5개국어 데이터 활용 |

### MVP 제외 기능 (추후 확장)

- 동선 코스 생성
- 즐겨찾기 / 방문 기록
- 리뷰 / 평점

## 🛠️ 기술 스택

| 분류 | 기술 |
|------|------|
| **Frontend** | HTML5, CSS3, JavaScript (Vanilla) |
| **UI/Design** | Google Stitch |
| **Backend** | Python + FastAPI (비동기 네이티브) |
| **Database** | Supabase (PostgreSQL) — 캐시 + XGBoost 학습 데이터 |
| **ML** | XGBoost (추천 점수 예측) |
| **지도** | Leaflet.js + Leaflet.heat (히트맵) |
| **실시간** | SSE (Server-Sent Events) |
| **외부 API** | 공공데이터포털 (~10개, 비동기 병렬, API키 1개) |
| **배포** | AWS EC2 + Docker (docker-compose) |
| **모니터링** | Python logging + Sentry |
| **Version Control** | Git & GitHub |

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────┐
│                    Frontend                      │
│         HTML/CSS/JS + Leaflet.js 지도            │
│              (SSE 실시간 수신)                    │
└──────────────────────┬──────────────────────────┘
                       │ REST API + SSE
┌──────────────────────▼──────────────────────────┐
│              FastAPI Backend                      │
│  ┌──────────┬──────────┬──────────┬──────────┐  │
│  │  api/    │collector/│   ml/    │  cache/   │  │
│  │ 라우터   │데이터수집│ XGBoost  │메모리캐시 │  │
│  └──────────┴──────────┴──────────┴──────────┘  │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Supabase │ │공공데이터│ │  Sentry  │
    │(PostgreSQL)│ │ 포털 API │ │ 모니터링 │
    └──────────┘ └──────────┘ └──────────┘
```

- **패턴**: 모듈 분리 모놀리식 (`api/`, `collector/`, `ml/`, `cache/`)
- **통신**: REST API + SSE (서버 푸시)
- **캐싱**: 서버 메모리 캐시 (빠른 응답) + Supabase (히스토리 축적 / 학습)

## 📁 디렉토리 구조

```
Hello-Busan/
├── 📄 README.md
├── 📄 CONTRIBUTING.md
├── 📄 .gitignore
├── 📄 .env.example
├── 📄 docker-compose.yml
├── 📄 Dockerfile
│
├── 📁 frontend/
│   ├── 📁 css/
│   │   ├── reset.css
│   │   ├── common.css
│   │   └── 📁 pages/
│   ├── 📁 js/
│   │   ├── 📁 api/          # API 통신 모듈
│   │   ├── 📁 components/   # UI 컴포넌트
│   │   ├── 📁 utils/        # 유틸리티
│   │   └── app.js
│   ├── 📁 assets/
│   │   ├── 📁 images/
│   │   ├── 📁 icons/
│   │   └── 📁 fonts/
│   └── index.html
│
├── 📁 backend/
│   ├── 📁 api/               # FastAPI 라우터
│   │   ├── __init__.py
│   │   └── 📁 routes/
│   │       ├── __init__.py
│   │       ├── spots.py      # 관광지 엔드포인트
│   │       ├── comfort.py    # 쾌적함 지수
│   │       └── sse.py        # SSE 실시간 스트림
│   ├── 📁 collector/         # 외부 API 데이터 수집
│   │   ├── __init__.py
│   │   ├── weather.py        # 기상청 API
│   │   ├── congestion.py     # 혼잡도 API
│   │   ├── transport.py      # 교통 API
│   │   └── tourism.py        # 부산 관광 API
│   ├── 📁 ml/                # XGBoost 추천 엔진
│   │   ├── __init__.py
│   │   ├── model.py          # 모델 학습/예측
│   │   └── features.py       # 피처 엔지니어링
│   ├── 📁 cache/             # 서버 메모리 캐시
│   │   ├── __init__.py
│   │   └── memory_cache.py
│   ├── 📁 models/            # 데이터 스키마
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── 📁 services/          # 비즈니스 로직
│   │   ├── __init__.py
│   │   └── comfort_index.py  # 쾌적함 지수 계산
│   ├── 📁 utils/             # 유틸리티
│   │   ├── __init__.py
│   │   └── error_codes.py    # 커스텀 에러 코드
│   ├── config.py
│   ├── main.py               # FastAPI 앱 엔트리포인트
│   └── requirements.txt
│
├── 📁 docs/
│   └── 📁 images/
│
└── 📁 .github/
    ├── 📁 ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    └── PULL_REQUEST_TEMPLATE.md
```

## 🔌 API 설계

RESTful 자원 기반 설계 (`/api/v1/...`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/v1/spots` | 관광지 목록 (추천 점수순) |
| `GET` | `/api/v1/spots/{id}` | 관광지 상세 정보 |
| `GET` | `/api/v1/spots/nearby` | 위치 기반 주변 관광지 |
| `GET` | `/api/v1/comfort` | 쾌적함 지수 대시보드 데이터 |
| `GET` | `/api/v1/comfort/{spot_id}` | 특정 관광지 쾌적함 지수 |
| `GET` | `/api/v1/heatmap` | 히트맵 데이터 |
| `GET` | `/api/v1/stream/updates` | SSE 실시간 업데이트 스트림 |
| `GET` | `/health` | 헬스체크 |

### 에러 처리

커스텀 에러 코드 체계 사용 (예: `COMFORT_001`, `SPOT_002`)

### API 문서

FastAPI Swagger 자동 생성 → `/docs`에서 확인 가능

## 🚀 시작하기

### 사전 요구사항

- [Python 3.10+](https://www.python.org/downloads/)
- [Docker & Docker Compose](https://www.docker.com/get-started)
- [Git](https://git-scm.com/)
- [Supabase 계정](https://supabase.com/)
- [공공데이터포털 API 키](https://www.data.go.kr/)

### 설치 및 실행 (로컬)

```bash
# 1. 레포지토리 클론
git clone https://github.com/namgyumo/Hello-Busan.git
cd Hello-Busan

# 2. Python 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r backend/requirements.txt

# 4. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 등 입력

# 5. 서버 실행
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker로 실행

```bash
# Docker Compose로 실행
docker-compose up --build

# 백그라운드 실행
docker-compose up -d --build
```

### 환경변수 설정

`.env` 파일에 아래 변수를 설정하세요:

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key

# 공공데이터포털 API
DATA_API_KEY=your_data_portal_api_key

# 앱 설정
SECRET_KEY=your_secret_key
DEBUG=True
APP_ENV=development

# Sentry 모니터링
SENTRY_DSN=your_sentry_dsn

# AWS (배포 시)
AWS_REGION=ap-northeast-2
```

## 🌐 배포

AWS EC2 + Docker 기반으로 배포합니다.

```bash
# EC2에서 Docker Compose로 배포
docker-compose -f docker-compose.yml up -d --build
```

📌 배포 가이드는 추후 `docs/deployment.md`에 정리될 예정입니다.

## 📅 개발 계획

| 주차 | 목표 |
|------|------|
| **1주차** | 환경 세팅 + 데이터 수집 파이프라인 + 최소 프론트(지도 마커) |
| **2주차** | XGBoost 추천 + 쾌적함 지수 + 히트맵 + SSE 실시간 갱신 |
| **3주차** | 관광지 상세 + 카테고리 UI 고도화 + 다국어 |
| **4주차** | 디자인(Google Stitch) + 테스트 + 대회 발표 준비 |

## 🤝 기여 방법

프로젝트에 기여하고 싶으시다면 [CONTRIBUTING.md](CONTRIBUTING.md) 문서를 참고해주세요.

해당 문서에는 아래 내용이 포함되어 있습니다:

- Git 브랜치 전략 (Git Flow)
- 커밋 메시지 컨벤션
- 코드 작성 규칙
- PR 및 이슈 작성 가이드

## 📜 라이선스

이 프로젝트는 개인 프로젝트입니다.

---

<div align="center">

⭐ **이 프로젝트가 도움이 되셨다면 Star를 눌러주세요!** ⭐

</div>
