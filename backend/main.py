"""
Hello-Busan Backend Application
FastAPI 기반 비동기 백엔드 서버
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.cache.manager import CacheManager
from backend.ml.model import RecommendModel

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

# 글로벌 인스턴스
cache = CacheManager()
model = RecommendModel()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 라이프사이클 관리"""
    logger.info("Hello-Busan API 서버 시작")

    # XGBoost 모델 로드 (이미 생성자에서 시도하지만 명시적으로)
    if not model.is_loaded:
        logger.warning("XGBoost 모델 미로드 — 폴백 추천 모드로 동작")

    # 데이터 수집 스케줄러 시작 (API 키 설정된 경우만)
    scheduler = None
    if settings.DATA_API_KEY:
        try:
            from backend.collector.scheduler import CollectorScheduler
            scheduler = CollectorScheduler()
            scheduler.start()
            logger.info("데이터 수집 스케줄러 시작")

            # 첫 실행: 백그라운드에서 데이터 수집 (서버 시작 차단 방지)
            import asyncio

            async def _initial_collect():
                try:
                    logger.info("초기 데이터 수집 시작...")
                    results = await scheduler.run_all_now()
                    logger.info(f"초기 데이터 수집 완료: {results}")
                except Exception as e:
                    logger.error(f"초기 데이터 수집 실패: {e}")

            asyncio.create_task(_initial_collect())
        except Exception as e:
            logger.error(f"스케줄러 시작 실패: {e}")

    yield

    # 종료 정리
    if scheduler:
        scheduler.stop()
    await cache.clear()
    logger.info("Hello-Busan API 서버 종료")


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 팩토리"""
    app = FastAPI(
        title="Hello-Busan API",
        description="부산 관광지 스마트 추천 서비스 API",
        version="1.0.0",
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
    from backend.api.spots import router as spots_router
    from backend.api.recommend import router as recommend_router
    from backend.api.comfort import router as comfort_router
    from backend.api.events import router as events_router

    app.include_router(spots_router)
    app.include_router(recommend_router)
    app.include_router(comfort_router)
    app.include_router(events_router)

    # 프론트엔드 정적 파일 서빙
    frontend_dir = Path(__file__).parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/css", StaticFiles(directory=frontend_dir / "css"), name="css")
        app.mount("/js", StaticFiles(directory=frontend_dir / "js"), name="js")
        app.mount("/locales", StaticFiles(directory=frontend_dir / "locales"), name="locales")

    @app.get("/")
    async def index():
        """메인 페이지"""
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"service": "Hello-Busan", "docs": "/docs"}

    @app.get("/detail.html")
    async def detail():
        """상세 페이지"""
        detail_path = frontend_dir / "detail.html"
        if detail_path.exists():
            return FileResponse(detail_path)
        return {"error": "page not found"}

    @app.get("/api/v1/health")
    async def health_check():
        """서버 상태 확인 (API 설계서 API-009)"""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "components": {
                "xgboost_model": {
                    "status": "loaded" if model.is_loaded else "not_loaded",
                },
                "cache": {
                    "status": "active",
                    **cache.get_stats(),
                },
            },
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
