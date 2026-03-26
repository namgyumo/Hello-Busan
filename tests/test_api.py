"""
FastAPI 엔드포인트 통합 테스트
- /health
- /api/v1/spots
- /api/v1/recommend
- /api/v1/comfort
Supabase는 모킹 처리
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from tests.conftest import FakeSupabase


# ── 앱 fixture ──

@pytest.fixture
def mock_supabase():
    """Supabase 모킹 — 기본 데이터 포함"""
    spots = [
        {
            "id": 1,
            "external_id": "EXT001",
            "name": "해운대 해수욕장",
            "category_id": "nature",
            "lat": 35.1587,
            "lng": 129.1604,
            "address": "부산 해운대구",
            "description": "부산 대표 해수욕장",
            "images": ["https://example.com/haeundae.jpg"],
            "is_active": True,
        },
        {
            "id": 2,
            "external_id": "EXT002",
            "name": "감천문화마을",
            "category_id": "culture",
            "lat": 35.0975,
            "lng": 129.0108,
            "address": "부산 사하구",
            "description": "알록달록 마을",
            "images": [],
            "is_active": True,
        },
    ]
    categories = [
        {"id": "nature", "name_ko": "자연", "name_en": "Nature", "icon": "🌊", "sort_order": 1},
        {"id": "culture", "name_ko": "문화", "name_en": "Culture", "icon": "🏛️", "sort_order": 2},
        {"id": "food", "name_ko": "맛집", "name_en": "Food", "icon": "🍜", "sort_order": 3},
    ]
    comfort = [
        {
            "spot_id": 1,
            "total_score": 82,
            "grade": "쾌적",
            "weather_score": 80,
            "crowd_score": 85,
            "transport_score": 75,
            "timestamp": "2026-03-26T10:00:00Z",
        },
    ]

    fake = FakeSupabase(table_data={
        "tourist_spots": spots,
        "categories": categories,
        "comfort_scores": comfort,
        "crowd_data": [],
        "weather_data": [],
        "transport_data": [],
    })
    return fake


@pytest.fixture
def app(mock_supabase):
    # 싱글턴 캐시 리셋하여 다른 테스트 간 격리
    from backend.cache.manager import CacheManager
    CacheManager._instance = None
    CacheManager._store = {}

    # Supabase 싱글턴을 mock으로 주입
    import backend.db.supabase as sb_mod
    sb_mod._supabase_client = mock_supabase

    with patch("backend.db.supabase.get_supabase", return_value=mock_supabase):
        with patch("backend.collector.scheduler.CollectorScheduler"):
            from backend.main import create_app
            yield create_app()

    # 테스트 후 싱글턴 정리
    sb_mod._supabase_client = None


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health Check ──

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_structure(self, client):
        resp = await client.get("/api/v1/health")
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "components" in data

    @pytest.mark.asyncio
    async def test_health_has_model_status(self, client):
        data = (await client.get("/api/v1/health")).json()
        assert "xgboost_model" in data["components"]


# ── Spots API ──

class TestSpotsEndpoint:
    @pytest.mark.asyncio
    async def test_spots_list(self, client):
        resp = await client.get("/api/v1/spots")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_spots_with_category_filter(self, client):
        resp = await client.get("/api/v1/spots?category=nature")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_spots_categories(self, client):
        resp = await client.get("/api/v1/spots/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ── Recommend API ──

class TestRecommendEndpoint:
    @pytest.mark.asyncio
    async def test_recommend_default(self, client):
        resp = await client.get("/api/v1/recommend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "data" in data
        assert "meta" in data

    @pytest.mark.asyncio
    async def test_recommend_with_location(self, client):
        resp = await client.get("/api/v1/recommend?lat=35.16&lng=129.16")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_recommend_with_category(self, client):
        resp = await client.get("/api/v1/recommend?categories=nature")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_recommend_pagination(self, client):
        resp = await client.get("/api/v1/recommend?limit=1&offset=0")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_recommend_meta_has_fallback(self, client):
        data = (await client.get("/api/v1/recommend")).json()
        assert "fallback_used" in data["meta"]


# ── Comfort API ──

class TestComfortEndpoint:
    @pytest.mark.asyncio
    async def test_comfort_single(self, client):
        resp = await client.get("/api/v1/comfort/1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_comfort_bulk(self, client):
        resp = await client.get("/api/v1/comfort/bulk?spot_ids=1,2")
        assert resp.status_code == 200


# ── 메인 페이지 ──

class TestFrontendServing:
    @pytest.mark.asyncio
    async def test_index_page(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
