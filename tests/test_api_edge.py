"""
2차 QA — API 엣지 케이스 + 에러 경로
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from tests.conftest import FakeSupabase, FakeQueryBuilder


@pytest.fixture
def empty_supabase():
    """데이터가 없는 Supabase"""
    return FakeSupabase(table_data={
        "tourist_spots": [],
        "categories": [],
        "comfort_scores": [],
        "crowd_data": [],
        "weather_data": [],
        "transport_data": [],
    })


@pytest.fixture
def app_empty(empty_supabase):
    from backend.cache.manager import CacheManager
    CacheManager._instance = None
    CacheManager._store = {}

    import backend.db.supabase as sb_mod
    sb_mod._supabase_client = empty_supabase

    with patch("backend.db.supabase.get_supabase", return_value=empty_supabase):
        with patch("backend.collector.scheduler.CollectorScheduler"):
            from backend.main import create_app
            yield create_app()

    sb_mod._supabase_client = None


@pytest.fixture
async def client_empty(app_empty):
    transport = ASGITransport(app=app_empty)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── 빈 데이터 시나리오 ──

class TestEmptyData:
    @pytest.mark.asyncio
    async def test_recommend_empty_returns_empty_list(self, client_empty):
        resp = await client_empty.get("/api/v1/recommend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []
        assert data["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_spots_empty_returns_empty(self, client_empty):
        resp = await client_empty.get("/api/v1/spots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_categories_empty_returns_fallback(self, client_empty):
        """카테고리가 비어있으면 하드코딩 폴백"""
        resp = await client_empty.get("/api/v1/spots/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) > 0  # CATEGORY_MAP 폴백

    @pytest.mark.asyncio
    async def test_heatmap_empty(self, client_empty):
        resp = await client_empty.get("/api/v1/heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["points"] == []

    @pytest.mark.asyncio
    async def test_comfort_bulk_empty(self, client_empty):
        resp = await client_empty.get("/api/v1/comfort/bulk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == []


# ── 잘못된 파라미터 ──

class TestInvalidParams:
    @pytest.fixture
    def mock_supabase(self):
        return FakeSupabase(table_data={
            "tourist_spots": [
                {"id": 1, "name": "Test", "category_id": "nature",
                 "lat": 35.1, "lng": 129.0, "is_active": True, "images": []},
            ],
            "categories": [],
            "comfort_scores": [],
        })

    @pytest.fixture
    def app(self, mock_supabase):
        from backend.cache.manager import CacheManager
        CacheManager._instance = None
        CacheManager._store = {}

        import backend.db.supabase as sb_mod
        sb_mod._supabase_client = mock_supabase

        with patch("backend.db.supabase.get_supabase", return_value=mock_supabase):
            with patch("backend.collector.scheduler.CollectorScheduler"):
                from backend.main import create_app
                yield create_app()

        sb_mod._supabase_client = None

    @pytest.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_spots_invalid_lat(self, client):
        """위도 범위 밖 (ge=33, le=38)"""
        resp = await client.get("/api/v1/spots?lat=10.0&lng=129.0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_spots_invalid_limit(self, client):
        """limit=0 (ge=1)"""
        resp = await client.get("/api/v1/spots?limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_spots_limit_over_max(self, client):
        """limit=200 (le=100)"""
        resp = await client.get("/api/v1/spots?limit=200")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_recommend_invalid_lat(self, client):
        resp = await client.get("/api/v1/recommend?lat=99.0&lng=129.0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_recommend_negative_offset(self, client):
        resp = await client.get("/api/v1/recommend?offset=-1")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_comfort_nonexistent_spot(self, client):
        """존재하지 않는 spot_id → 404"""
        resp = await client.get("/api/v1/comfort/99999")
        assert resp.status_code == 404


# ── SSE 엔드포인트 기본 테스트 ──
# SSE는 스트리밍 응답이라 httpx로 직접 테스트 시 블로킹됨
# broadcast 로직은 test_sse_broadcast.py에서 별도 테스트


# ── Heatmap 데이터 형식 검증 ──

class TestHeatmapFormat:
    @pytest.fixture
    def mock_supabase(self):
        return FakeSupabase(table_data={
            "tourist_spots": [
                {"id": 1, "lat": 35.1, "lng": 129.0, "is_active": True},
                {"id": 2, "lat": 35.2, "lng": 129.1, "is_active": True},
            ],
            "comfort_scores": [],
        })

    @pytest.fixture
    def app(self, mock_supabase):
        from backend.cache.manager import CacheManager
        CacheManager._instance = None
        CacheManager._store = {}

        import backend.db.supabase as sb_mod
        sb_mod._supabase_client = mock_supabase

        with patch("backend.db.supabase.get_supabase", return_value=mock_supabase):
            with patch("backend.collector.scheduler.CollectorScheduler"):
                from backend.main import create_app
                yield create_app()

        sb_mod._supabase_client = None

    @pytest.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_heatmap_points_are_arrays(self, client):
        """히트맵 points가 [lat, lng, intensity] 배열 형태인지"""
        resp = await client.get("/api/v1/heatmap")
        data = resp.json()
        points = data["data"]["points"]
        for pt in points:
            assert isinstance(pt, list), f"Point should be list, got {type(pt)}"
            assert len(pt) == 3, f"Point should have 3 elements, got {len(pt)}"

    @pytest.mark.asyncio
    async def test_heatmap_intensity_range(self, client):
        """intensity는 0~1 범위"""
        resp = await client.get("/api/v1/heatmap")
        points = resp.json()["data"]["points"]
        for pt in points:
            assert 0 <= pt[2] <= 1, f"Intensity {pt[2]} out of range"

    @pytest.mark.asyncio
    async def test_heatmap_has_config(self, client):
        resp = await client.get("/api/v1/heatmap")
        config = resp.json()["data"]["config"]
        assert "radius" in config
        assert "gradient" in config
