<div align="center">

# 🌊 Hello, Busan!

**부산의 쾌적한 관광지를 실시간으로 추천해드립니다.**

[![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/ko/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)](https://developer.mozilla.org/ko/docs/Web/CSS)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/ko/docs/Web/JavaScript)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![AWS EC2](https://img.shields.io/badge/AWS_EC2-FF9900?style=for-the-badge&logo=amazonec2&logoColor=white)](https://aws.amazon.com/ec2/)
[![Google Stitch](https://img.shields.io/badge/Google_Stitch-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://stitch.withgoogle.com/)

</div>

---

## 📖 프로젝트 소개

**Hello, Busan!** 은 부산을 방문하는 관광객들에게 실시간 혼잡도, 날씨, 리뷰 등의 데이터를 기반으로 쾌적한 관광지를 추천해주는 웹 서비스입니다.

### 주요 기능

- 🗺️ **실시간 관광지 추천** — 혼잡도 및 날씨 데이터를 분석하여 쾌적한 관광지 추천
- 📊 **실시간 혼잡도 확인** — 주요 관광지의 현재 방문자 수 및 혼잡도 시각화
- 🌤️ **날씨 정보 연동** — 관광지별 실시간 날씨 정보 제공
- ⭐ **관광지 리뷰 & 평점** — 사용자 리뷰 및 평점 시스템
- 📍 **맞춤형 코스 추천** — 사용자 취향에 맞는 관광 코스 추천

---

## 🛠️ 기술 스택

| 분류 | 기술 |
|------|------|
| **Frontend** | HTML5, CSS3, JavaScript (Vanilla) |
| **UI/Design** | Google Stitch |
| **Backend** | Python |
| **Database** | Supabase (PostgreSQL) |
| **Deployment** | AWS EC2 |
| **Version Control** | Git & GitHub |

---

## 📁 디렉토리 구조

```
Hello-Busan/
├── 📄 README.md
├── 📄 CONTRIBUTING.md
├── 📄 .gitignore
├── 📁 frontend/
│   ├── 📁 css/
│   │   ├── reset.css
│   │   ├── common.css
│   │   └── pages/
│   ├── 📁 js/
│   │   ├── 📁 api/
│   │   ├── 📁 components/
│   │   ├── 📁 utils/
│   │   └── app.js
│   ├── 📁 assets/
│   │   ├── 📁 images/
│   │   ├── 📁 icons/
│   │   └── 📁 fonts/
│   └── index.html
├── 📁 backend/
│   ├── 📁 api/
│   │   ├── __init__.py
│   │   └── routes/
│   ├── 📁 services/
│   ├── 📁 models/
│   ├── 📁 utils/
│   ├── config.py
│   ├── requirements.txt
│   └── app.py
├── 📁 docs/
│   └── 📁 images/
└── 📁 .github/
    ├── 📁 ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 🚀 시작하기

### 사전 요구사항

- [Python 3.10+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/)
- [Supabase 계정](https://supabase.com/)

### 설치 및 실행

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
# .env 파일에 Supabase URL, API Key 등 입력

# 5. 서버 실행
python backend/app.py
```

### 환경변수 설정

`.env` 파일에 아래 변수를 설정하세요:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SECRET_KEY=your_secret_key
DEBUG=True
```

---

## 🌐 배포

AWS EC2 인스턴스를 활용하여 배포할 예정입니다.

> 📌 배포 가이드는 추후 `docs/deployment.md`에 정리될 예정입니다.

---

## 🤝 기여 방법

프로젝트에 기여하고 싶으시다면 [CONTRIBUTING.md](./CONTRIBUTING.md) 문서를 참고해주세요.

해당 문서에는 아래 내용이 포함되어 있습니다:
- Git 브랜치 전략 (Git Flow)
- 커밋 메시지 컨벤션
- 코드 작성 규칙
- PR 및 이슈 작성 가이드

---

## 📜 라이선스

이 프로젝트는 개인 프로젝트입니다.

---

<div align="center">

**⭐ 이 프로젝트가 도움이 되셨다면 Star를 눌러주세요! ⭐**

</div>
