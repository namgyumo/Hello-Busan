"""
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
