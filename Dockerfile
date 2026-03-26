FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 소스 코드 복사
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 환경변수
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

EXPOSE 8000

# FastAPI 서버 실행
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
