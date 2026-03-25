# 🤝 Contributing Guide (기여 가이드)

Hello, Busan! 프로젝트에 기여해주셔서 감사합니다.
이 문서는 프로젝트의 코드 작성 규칙, Git 사용법, 브랜치 전략 등을 안내합니다.

---

## 📌 목차

1. [브랜치 전략](#-브랜치-전략)
2. [커밋 메시지 컨벤션](#-커밋-메시지-컨벤션)
3. [코드 작성 규칙](#-코드-작성-규칙)
4. [PR (Pull Request) 가이드](#-pr-pull-request-가이드)
5. [이슈 작성 가이드](#-이슈-작성-가이드)
6. [Git 작업 플로우](#-git-작업-플로우)

---

## 🌿 브랜치 전략

본 프로젝트는 **Git Flow** 기반의 브랜치 전략을 사용합니다.

### 브랜치 종류

| 브랜치 | 목적 | 네이밍 규칙 |
|--------|------|-------------|
| `main` | 배포 가능한 안정 버전 | - |
| `develop` | 개발 통합 브랜치 | - |
| `feature/*` | 새로운 기능 개발 | `feature/기능명` |
| `hotfix/*` | 긴급 버그 수정 | `hotfix/버그명` |
| `release/*` | 배포 준비 | `release/v1.0.0` |

### 브랜치 네이밍 예시

```
feature/user-login          # 사용자 로그인 기능
feature/map-integration     # 지도 연동 기능
feature/weather-api         # 날씨 API 연동
hotfix/login-error          # 로그인 오류 긴급 수정
release/v1.0.0              # 1.0.0 버전 배포 준비
```

### 브랜치 흐름

```
main ← release ← develop ← feature
                    ↑
                  hotfix → main
```

1. `develop` 브랜치에서 `feature` 브랜치를 생성합니다.
2. 기능 개발이 완료되면 `develop` 브랜치로 PR을 생성합니다.
3. 배포 준비가 되면 `develop`에서 `release` 브랜치를 생성합니다.
4. 테스트 후 `main` 브랜치에 병합하고 태그를 생성합니다.
5. 긴급 수정이 필요하면 `main`에서 `hotfix` 브랜치를 생성합니다.

---

## 📝 커밋 메시지 컨벤션

### 커밋 메시지 형식

```
<type>: <subject>

[optional body]

[optional footer]
```

### 커밋 타입 (Type)

| 타입 | 설명 | 예시 |
|------|------|------|
| `feat` | 새로운 기능 추가 | `feat: 관광지 검색 기능 추가` |
| `fix` | 버그 수정 | `fix: 지도 마커 클릭 오류 수정` |
| `docs` | 문서 수정 | `docs: README 설치 가이드 업데이트` |
| `style` | 코드 스타일 변경 (기능 변경 X) | `style: 들여쓰기 수정` |
| `refactor` | 코드 리팩토링 | `refactor: API 호출 로직 개선` |
| `test` | 테스트 코드 추가/수정 | `test: 로그인 유닛 테스트 추가` |
| `chore` | 빌드, 설정 파일 수정 | `chore: .gitignore 업데이트` |
| `perf` | 성능 개선 | `perf: 이미지 로딩 속도 최적화` |
| `ci` | CI/CD 설정 변경 | `ci: GitHub Actions 워크플로우 추가` |
| `remove` | 파일 삭제 | `remove: 사용하지 않는 이미지 삭제` |

### 커밋 메시지 규칙

- 제목은 **50자 이내**로 작성합니다.
- 제목은 **명령문** 형태로 작성합니다. (예: "추가", "수정", "삭제")
- 제목 끝에 **마침표를 사용하지 않습니다.**
- 본문은 **"무엇을"과 "왜"** 를 중심으로 작성합니다.
- 본문은 72자마다 줄바꿈합니다.

### 커밋 메시지 예시

```
feat: 관광지 실시간 혼잡도 표시 기능 추가

- Supabase에서 실시간 혼잡도 데이터 조회
- 혼잡도에 따른 색상 표시 (초록/노랑/빨강)
- 5분 간격 자동 갱신 구현

Closes #12
```

---

## 💻 코드 작성 규칙

### 공통 규칙

- 들여쓰기: **스페이스 2칸** (HTML, CSS, JS) / **스페이스 4칸** (Python)
- 파일 인코딩: **UTF-8**
- 파일 끝에 **빈 줄 1개** 추가
- 불필요한 주석 및 console.log는 커밋 전 삭제

### HTML

- 시맨틱 태그를 사용합니다. (`<header>`, `<main>`, `<section>`, `<article>` 등)
- 속성 순서: `id` → `class` → `data-*` → `src/href` → `alt/title`
- 클래스명은 **kebab-case**를 사용합니다. (예: `tourist-spot-card`)
- alt 속성은 반드시 작성합니다.

```html
<!-- 좋은 예 -->
<section class="tourist-spot-list">
  <article id="spot-1" class="spot-card" data-id="1">
    <img src="./assets/images/haeundae.jpg" alt="해운대 해수욕장 전경">
    <h3 class="spot-title">해운대 해수욕장</h3>
  </article>
</section>
```

### CSS

- BEM 네이밍 방법론을 사용합니다. (`block__element--modifier`)
- 속성 순서: 위치 → 크기 → 스타일 → 기타
- 색상은 변수로 관리합니다.
- 미디어 쿼리는 모바일 퍼스트로 작성합니다.

```css
/* CSS 변수 정의 */
:root {
  --color-primary: #0066CC;
  --color-secondary: #FF6B35;
  --color-success: #28A745;
  --color-warning: #FFC107;
  --color-danger: #DC3545;
  --font-size-base: 16px;
}

/* BEM 네이밍 예시 */
.spot-card { }
.spot-card__title { }
.spot-card__badge--crowded { }
.spot-card__badge--comfortable { }
```

### JavaScript

- `const`를 기본으로 사용하고, 재할당이 필요할 때만 `let`을 사용합니다.
- `var`는 사용하지 않습니다.
- 함수는 **화살표 함수**를 기본으로 사용합니다.
- 변수명과 함수명은 **camelCase**를 사용합니다.
- 상수는 **UPPER_SNAKE_CASE**를 사용합니다.
- 비동기 처리는 **async/await**를 사용합니다.
- DOM 요소 선택 시 `querySelector` / `querySelectorAll`을 사용합니다.

```javascript
// 상수 정의
const API_BASE_URL = '/api/v1';
const MAX_RETRY_COUNT = 3;

// 함수 정의
const fetchTouristSpots = async (category) => {
  try {
    const response = await fetch(\`\${API_BASE_URL}/spots?category=\${category}\`);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('관광지 데이터 조회 실패:', error);
    throw error;
  }
};

// DOM 요소 선택
const spotContainer = document.querySelector('.spot-container');
const searchInput = document.querySelector('#search-input');
```

### Python

- [PEP 8](https://peps.python.org/pep-0008/) 스타일 가이드를 따릅니다.
- 변수명과 함수명은 **snake_case**를 사용합니다.
- 클래스명은 **PascalCase**를 사용합니다.
- 함수에는 **docstring**을 작성합니다.
- f-string을 사용합니다.

```python
class TouristSpotService:
    """관광지 관련 비즈니스 로직을 처리하는 서비스 클래스"""

    def __init__(self, supabase_client):
        self.db = supabase_client

    def get_comfortable_spots(self, max_congestion=60):
        """혼잡도가 기준 이하인 쾌적한 관광지를 조회합니다.

        Args:
            max_congestion (int): 최대 혼잡도 기준 (기본값: 60)

        Returns:
            list: 쾌적한 관광지 목록
        """
        response = self.db.table("tourist_spots") \
            .select("*") \
            .lte("congestion", max_congestion) \
            .execute()
        return response.data
```

---

## 🔀 PR (Pull Request) 가이드

### PR 작성 규칙

- PR 제목은 커밋 메시지 컨벤션을 따릅니다.
- PR 본문에 **변경 사항**, **테스트 방법**, **스크린샷**(UI 변경 시)을 포함합니다.
- 관련 이슈가 있다면 `Closes #이슈번호`를 포함합니다.
- PR 생성 전 최신 `develop` 브랜치를 rebase 합니다.

### PR 체크리스트

- [ ] 코드가 정상적으로 동작하는가?
- [ ] 코딩 컨벤션을 준수했는가?
- [ ] 불필요한 console.log / 주석을 제거했는가?
- [ ] 관련 문서를 업데이트했는가?

---

## 📋 이슈 작성 가이드

### 이슈 제목

- 간결하고 명확하게 작성합니다.
- 태그를 활용합니다: `[Bug]`, `[Feature]`, `[Docs]`, `[Refactor]`

### 이슈 예시

```
[Feature] 관광지 즐겨찾기 기능 추가
[Bug] 모바일에서 지도 마커가 표시되지 않는 문제
[Docs] API 문서 업데이트
```

---

## 🔄 Git 작업 플로우

### 새 기능 개발 시

```bash
# 1. develop 브랜치에서 최신 코드 가져오기
git checkout develop
git pull origin develop

# 2. feature 브랜치 생성
git checkout -b feature/기능명

# 3. 작업 진행 및 커밋
git add .
git commit -m "feat: 기능 설명"

# 4. 원격 저장소에 푸시
git push origin feature/기능명

# 5. GitHub에서 develop 브랜치로 PR 생성
```

### 긴급 버그 수정 시

```bash
# 1. main 브랜치에서 hotfix 브랜치 생성
git checkout main
git pull origin main
git checkout -b hotfix/버그명

# 2. 수정 후 커밋
git add .
git commit -m "fix: 버그 설명"

# 3. main과 develop 모두에 반영
git push origin hotfix/버그명
# GitHub에서 main과 develop 브랜치로 각각 PR 생성
```

### 주의사항

- `main` 브랜치에 직접 커밋하지 않습니다.
- 커밋 전 `git diff`로 변경사항을 확인합니다.
- 충돌 발생 시 `rebase`를 사용하여 해결합니다.
- 의미 있는 단위로 커밋합니다. (1 커밋 = 1 작업)

---

## 📂 파일 및 폴더 네이밍 규칙

| 대상 | 규칙 | 예시 |
|------|------|------|
| HTML 파일 | kebab-case | `tourist-spot-detail.html` |
| CSS 파일 | kebab-case | `spot-card.css` |
| JS 파일 | camelCase | `touristSpotApi.js` |
| Python 파일 | snake_case | `tourist_spot_service.py` |
| 이미지 파일 | kebab-case | `haeundae-beach.jpg` |
| 폴더명 | kebab-case 또는 lowercase | `api/`, `tourist-spots/` |

---

> 💡 이 가이드에 대한 개선 사항이나 질문이 있으시면 이슈를 생성해주세요!
