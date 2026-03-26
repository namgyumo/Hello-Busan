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
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key"

    # Supabase 설정
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # 공공데이터포털 API
    DATA_API_KEY: str = ""

    # Sentry 모니터링
    SENTRY_DSN: str = ""

    # AWS 설정 (배포 시)
    AWS_REGION: str = "ap-northeast-2"

    # 캐시 설정
    CACHE_TTL_SECONDS: int = 300  # 5분

    # SSE 설정
    SSE_RETRY_TIMEOUT: int = 5000  # ms

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """설정 싱글턴 (캐시됨)"""
    return Settings()


settings = get_settings()"""
Hello-Busan 설정 파일
환경 변수 및 Supabase 연결 설정
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """기본 설정"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = False

    # Supabase 설정
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

    # AWS 설정 (배포 시 사용)
    AWS_REGION = os.getenv('AWS_REGION', 'ap-northeast-2')


class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True


class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
