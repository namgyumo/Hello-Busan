"""
2차 QA — 엣지 케이스 + 에러 경로 테스트
"""
import pytest
import numpy as np
from backend.services.location import LocationService
from backend.ml.features import FeatureBuilder
from backend.ml.fallback import FallbackRecommender
from backend.cache.manager import CacheManager, CacheEntry
from backend.models.common import SuccessResponse, Meta


# ── Location 엣지 케이스 ──

class TestLocationEdge:
    def test_haversine_antipodal_points(self):
        """지구 반대편 — 최대 거리 약 20,000km"""
        dist = LocationService.haversine(0, 0, 0, 180)
        assert 19000 < dist < 21000

    def test_haversine_equator_one_degree(self):
        """적도에서 경도 1도 ≈ 111km"""
        dist = LocationService.haversine(0, 0, 0, 1)
        assert 100 < dist < 120

    def test_is_in_busan_exact_boundary_corners(self):
        svc = LocationService()
        # 4개 꼭짓점 전부 포함
        from backend.services.location import BUSAN_BOUNDS
        assert svc.is_in_busan(BUSAN_BOUNDS["south"], BUSAN_BOUNDS["west"]) is True
        assert svc.is_in_busan(BUSAN_BOUNDS["north"], BUSAN_BOUNDS["east"]) is True

    def test_sort_by_distance_empty_list(self):
        svc = LocationService()
        result = svc.sort_by_distance([], 35.0, 129.0)
        assert result == []

    def test_filter_by_radius_zero_radius(self):
        svc = LocationService()
        spots = [{"lat": 35.0, "lng": 129.0}]
        result = svc.filter_by_radius(spots, 35.0, 129.0, radius_km=0.0)
        # 동일 좌표 → 거리 0 → 0.0 <= 0.0 → 포함
        assert len(result) == 1

    def test_sort_with_missing_coords(self):
        svc = LocationService()
        spots = [
            {"name": "A"},  # lat/lng 없음 → default 0
            {"name": "B", "lat": 35.0, "lng": 129.0},
        ]
        result = svc.sort_by_distance(spots, 35.0, 129.0)
        # B가 더 가까움 (35,129), A는 (0,0)으로 매우 멀리
        assert result[0]["name"] == "B"


# ── Features 엣지 케이스 ──

class TestFeaturesEdge:
    def test_empty_spot_list(self):
        builder = FeatureBuilder()
        features = builder.build_batch([])
        # np.array([]) → shape (0,), 빈 배열이 반환되면 OK
        assert features.shape[0] == 0

    def test_spot_with_no_fields(self):
        """완전 빈 딕셔너리도 처리 가능"""
        builder = FeatureBuilder()
        features = builder.build_batch([{}])
        assert features.shape == (1, 11)
        assert not np.isnan(features).any()

    def test_large_batch(self):
        builder = FeatureBuilder()
        spots = [{"id": i, "lat": 35.0 + i * 0.01, "lng": 129.0} for i in range(500)]
        features = builder.build_batch(spots)
        assert features.shape == (500, 11)

    def test_negative_coords(self):
        builder = FeatureBuilder()
        spot = {"id": 1, "lat": -33.8688, "lng": 151.2093}  # 시드니
        features = builder.build_batch([spot], user_lat=35.0, user_lng=129.0)
        assert features[0, 1] > 0  # distance > 0


# ── Fallback 엣지 케이스 ──

class TestFallbackEdge:
    def test_single_spot(self):
        rec = FallbackRecommender()
        spots = [{"id": 1, "lat": 35.0, "lng": 129.0}]
        result = rec.recommend(spots, limit=5)
        assert len(result) == 1

    def test_limit_zero(self):
        rec = FallbackRecommender()
        spots = [{"id": 1}, {"id": 2}]
        result = rec.recommend(spots, limit=0)
        assert result == []

    def test_spots_with_extreme_view_counts(self):
        rec = FallbackRecommender()
        spots = [
            {"id": 1, "view_count": 0, "rating": 1.0, "lat": 35.0, "lng": 129.0},
            {"id": 2, "view_count": 999999, "rating": 5.0, "lat": 35.0, "lng": 129.0},
        ]
        result = rec.recommend(spots, limit=2)
        # 인기도 + 평점이 높은 쪽이 먼저
        assert result[0]["id"] == 2

    def test_distance_score_at_20km_boundary(self):
        """20km 이상이면 distance_score = 0"""
        rec = FallbackRecommender()
        # 부산에서 서울까지는 20km 초과
        spots = [{"id": 1, "lat": 37.5, "lng": 126.9}]  # 서울
        result = rec.recommend(spots, user_lat=35.1, user_lng=129.0, limit=1)
        assert len(result) == 1  # 에러 없이 반환


# ── Cache 엣지 케이스 ──

class TestCacheEdge:
    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self):
        cm = CacheManager()
        await cm.clear()
        await cm.set("key", "old", ttl=300)
        await cm.set("key", "new", ttl=300)
        assert await cm.get("key") == "new"
        CacheManager._instance = None
        CacheManager._store = {}

    @pytest.mark.asyncio
    async def test_store_complex_objects(self):
        cm = CacheManager()
        await cm.clear()
        data = {
            "nested": {"list": [1, 2, 3], "dict": {"a": True}},
            "tuple_as_list": [1, "two", 3.0],
        }
        await cm.set("complex", data, ttl=300)
        assert await cm.get("complex") == data
        CacheManager._instance = None
        CacheManager._store = {}

    @pytest.mark.asyncio
    async def test_store_none_value(self):
        cm = CacheManager()
        await cm.clear()
        await cm.set("none_val", None, ttl=300)
        # None도 저장 가능해야 하지만 get이 None을 반환하면 구분 불가
        # 현재 구현에서는 entry가 존재하므로 None 반환
        result = await cm.get("none_val")
        assert result is None
        CacheManager._instance = None
        CacheManager._store = {}


# ── Pydantic 모델 엣지 케이스 ──

class TestModelEdge:
    def test_success_response_with_empty_list(self):
        resp = SuccessResponse(data=[])
        assert resp.success is True
        assert resp.data == []

    def test_meta_with_zero_total(self):
        meta = Meta(total=0)
        assert meta.total == 0

    def test_success_response_roundtrip(self):
        """직렬화 → 역직렬화 왕복"""
        original = SuccessResponse(
            data=[{"id": 1, "name": "test"}],
            meta=Meta(total=1, limit=20, offset=0),
        )
        dumped = original.model_dump()
        restored = SuccessResponse(**dumped)
        assert restored.data == original.data
        assert restored.meta.total == original.meta.total
