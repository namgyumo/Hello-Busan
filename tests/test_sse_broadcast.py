"""
2차 QA — SSE broadcast + BaseCollector 로직
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from backend.api.events import broadcast_update, active_connections
from backend.collector.base import BaseCollector


# ── SSE Broadcast ──

class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_to_empty(self):
        """연결이 없을 때 브로드캐스트 → 에러 없음"""
        active_connections.clear()
        await broadcast_update("test_event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_broadcast_to_connected_clients(self):
        """큐에 이벤트가 전달되는지"""
        active_connections.clear()
        q1 = asyncio.Queue()
        q2 = asyncio.Queue()
        active_connections.extend([q1, q2])

        await broadcast_update("comfort_update", {"spots": []})

        msg1 = await q1.get()
        msg2 = await q2.get()
        assert msg1["event"] == "comfort_update"
        assert msg2["event"] == "comfort_update"
        assert msg1["data"] == {"spots": []}

        active_connections.clear()


# ── BaseCollector 응답 파싱 ──

class TestBaseCollectorParsing:
    def _make_collector(self):
        """테스트용 concrete collector"""
        class TestCollector(BaseCollector):
            async def collect(self):
                return []
            async def save(self, data):
                return 0
        return TestCollector(api_key="test", base_url="http://example.com")

    def test_parse_valid_response(self):
        collector = self._make_collector()
        data = {
            "response": {
                "header": {"resultCode": "0000", "resultMsg": "OK"},
                "body": {"items": {"item": [{"id": 1}]}},
            }
        }
        result = collector._parse_response(data)
        assert result is not None
        assert "items" in result

    def test_parse_error_response(self):
        collector = self._make_collector()
        data = {
            "response": {
                "header": {"resultCode": "9999", "resultMsg": "SERVICE_ERROR"},
                "body": {},
            }
        }
        result = collector._parse_response(data)
        assert result is None

    def test_parse_malformed_response(self):
        collector = self._make_collector()
        result = collector._parse_response({"garbage": True})
        assert result is None

    def test_parse_empty_response(self):
        collector = self._make_collector()
        result = collector._parse_response({})
        assert result is None


# ── BaseCollector run 파이프라인 ──

class TestBaseCollectorRun:
    @pytest.mark.asyncio
    async def test_run_success(self):
        class SuccessCollector(BaseCollector):
            async def collect(self):
                return [{"id": 1}, {"id": 2}]
            async def save(self, data):
                return len(data)

        c = SuccessCollector(api_key="test", base_url="http://example.com")
        result = await c.run()
        assert result["status"] == "success"
        assert result["collected"] == 2
        assert result["saved"] == 2

    @pytest.mark.asyncio
    async def test_run_empty_collect(self):
        class EmptyCollector(BaseCollector):
            async def collect(self):
                return []
            async def save(self, data):
                return 0

        c = EmptyCollector(api_key="test", base_url="http://example.com")
        result = await c.run()
        assert result["status"] == "success"
        assert result["collected"] == 0
        assert result["saved"] == 0

    @pytest.mark.asyncio
    async def test_run_collect_failure(self):
        class FailCollector(BaseCollector):
            async def collect(self):
                raise ConnectionError("API down")
            async def save(self, data):
                return 0

        c = FailCollector(api_key="test", base_url="http://example.com")
        result = await c.run()
        assert result["status"] == "failed"
        assert "error" in result
