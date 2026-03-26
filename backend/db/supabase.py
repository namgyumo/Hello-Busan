"""
Supabase 클라이언트
- 싱글턴 Supabase 인스턴스
"""
from supabase import create_client, Client
from backend.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_supabase_client: Optional[Client] = None


def get_supabase() -> Client:
    """Supabase 클라이언트 싱글턴"""
    global _supabase_client

    if _supabase_client is None:
        try:
            _supabase_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY,
            )
            logger.info("Supabase 클라이언트 초기화 완료")
        except Exception as e:
            logger.error(f"Supabase 연결 실패: {e}")
            raise

    return _supabase_client


def reset_client():
    """클라이언트 리셋 (테스트용)"""
    global _supabase_client
    _supabase_client = None
