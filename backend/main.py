"""
Hello-Busan Backend Application
FastAPI 기반 비동기 백엔드 서버
"""

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings


# Sentry 초기화 (DSN이 설정된 경우만)
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
    )

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 라이프사이클 관리"""
    logger.info("Hello-Busan API 서버 시작")
    # TODO: 데이터 수집 스케줄러 시작
    # TODO: XGBoost 모델 로드
    # TODO: 메모리 캐시 초기화
    yield
    logger.info("Hello-Busan API 서버 종료")


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 팩토리"""
    app = FastAPI(
        title="Hello-Busan API",
        description="부산 관광지 스마트 추천 서비스 API",
        version="0.1.0",
        docs_url="/docs",
        lifespan=lifespan,
    )

    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API 라우터 등록
    # from api.routes.spots import router as spots_router
    # from api.routes.comfort import router as comfort_router
    # from api.routes.sse import router as sse_router
    # app.include_router(spots_router, prefix="/api/v1")
    # app.include_router(comfort_router, prefix="/api/v1")
    # app.include_router(sse_router, prefix="/api/v1")

    @app.get("/")
    async def root():
        return {
            "service": "Hello-Busan",
            "description": "부산 관광지 스마트 추천 API",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
        }

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
