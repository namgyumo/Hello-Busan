"""
Hello-Busan 설정 파일
Pydantic Settings 기반 환경 변수 관리
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """애플리케이션 설정 (환경변수에서 자동 로드)"""

    # 앱 설정
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-key"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # 공공데이터포털 API
    DATA_API_KEY: str = ""

    # 기상청 API
    WEATHER_API_KEY: str = ""

    # 부산 관광 API
    BUSAN_TOUR_API_KEY: str = ""

    # Sentry 모니터링
    SENTRY_DSN: str = ""

    # AWS
    AWS_REGION: str = "ap-northeast-2"

    # 캐시 TTL (초)
    CACHE_TTL_CROWD: int = 300       # 5분
    CACHE_TTL_WEATHER: int = 1800    # 30분
    CACHE_TTL_SPOTS: int = 86400     # 24시간

    # ML
    MODEL_PATH: str = "ml_data/model.joblib"
    FALLBACK_ENABLED: bool = True

    # SSE
    SSE_RETRY_TIMEOUT: int = 5000    # ms

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache()
def get_settings() -> Settings:
    """설정 싱글턴 (캐시됨)"""
    return Settings()


settings = get_settings()
