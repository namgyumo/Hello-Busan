"""
CacheManager 단위 테스트
- TTL 기반 만료
- get/set/delete/clear
- 싱글턴 패턴
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from backend.cache.manager import CacheManager, CacheEntry


@pytest.fixture
async def cache():
    cm = CacheManager()
    await cm.clear()
    yield cm
    await cm.clear()
    # 싱글턴 리셋
    CacheManager._instance = None
    CacheManager._store = {}


# ── 기본 동작 ──

class TestCacheBasic:
    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        await cache.set("key1", {"data": "hello"}, ttl=60)
        result = await cache.get("key1")
        assert result == {"data": "hello"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        await cache.set("key1", "value", ttl=60)
        await cache.delete("key1")
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self, cache):
        await cache.delete("nonexistent")  # 에러 없이 통과

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        await cache.set("a", 1, ttl=60)
        await cache.set("b", 2, ttl=60)
        await cache.clear()
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_size(self, cache):
        assert cache.size == 0
        await cache.set("a", 1, ttl=60)
        assert cache.size == 1
        await cache.set("b", 2, ttl=60)
        assert cache.size == 2


# ── TTL 만료 ──

class TestCacheTTL:
    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self, cache):
        await cache.set("key1", "value", ttl=1)
        await asyncio.sleep(1.1)
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired(self, cache):
        await cache.set("expired", "old", ttl=1)
        await cache.set("fresh", "new", ttl=300)
        await asyncio.sleep(1.1)
        await cache.cleanup()
        assert cache.size == 1
        assert await cache.get("fresh") == "new"


# ── CacheEntry ──

class TestCacheEntry:
    def test_not_expired_immediately(self):
        entry = CacheEntry("value", ttl=60)
        assert entry.is_expired is False

    def test_expired_after_ttl(self):
        entry = CacheEntry("value", ttl=0)
        # ttl=0이면 즉시 만료 (또는 거의 즉시)
        import time
        time.sleep(0.01)
        assert entry.is_expired is True


# ── 캐시 통계 ──

class TestCacheStats:
    @pytest.mark.asyncio
    async def test_get_stats(self, cache):
        await cache.set("a", 1, ttl=300)
        await cache.set("b", 2, ttl=300)
        stats = cache.get_stats()
        assert stats["total"] == 2
        assert stats["active"] == 2
        assert stats["expired"] == 0
