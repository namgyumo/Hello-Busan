"""
캐시 매니저
- 인메모리 TTL 캐시
- 비동기 get/set/delete
"""
from typing import Any, Optional
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


class CacheEntry:
    """캐시 항목"""

    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expires_at = datetime.now() + timedelta(seconds=ttl)

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class CacheManager:
    """인메모리 TTL 캐시 매니저"""

    _instance: Optional["CacheManager"] = None
    _store: dict = {}
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._store = {}
        return cls._instance

    async def get(self, key: str) -> Optional[Any]:
        """캐시 조회"""
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._store[key]
            return None
        return entry.value

    async def set(self, key: str, value: Any, ttl: int = 300):
        """캐시 저장 (기본 TTL: 5분)"""
        self._store[key] = CacheEntry(value, ttl)

    async def delete(self, key: str):
        """캐시 삭제"""
        self._store.pop(key, None)

    async def clear(self):
        """전체 캐시 초기화"""
        self._store.clear()
        logger.info("캐시 전체 초기화")

    async def cleanup(self):
        """만료된 캐시 정리"""
        expired_keys = [
            k for k, v in self._store.items() if v.is_expired
        ]
        for key in expired_keys:
            del self._store[key]
        if expired_keys:
            logger.debug(f"만료 캐시 {len(expired_keys)}건 정리")

    @property
    def size(self) -> int:
        """현재 캐시 크기"""
        return len(self._store)

    def get_stats(self) -> dict:
        """캐시 통계"""
        now = datetime.now()
        active = sum(1 for v in self._store.values() if not v.is_expired)
        expired = len(self._store) - active
        return {
            "total": len(self._store),
            "active": active,
            "expired": expired,
        }
