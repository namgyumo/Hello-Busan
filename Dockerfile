FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

# Python 의존성 (캐시 레이어)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY sql/ ./sql/

# ML 모델 데이터 (ml_data/ 디렉토리에 .gitkeep이 있으므로 COPY 가능)
COPY ml_data/ ./ml_data/

# 환경변수
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
