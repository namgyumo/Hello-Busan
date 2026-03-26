"""
LocationService 단위 테스트
- haversine 거리 계산
- 부산 경계 체크
- 거리 정렬 / 반경 필터
"""
import pytest
from backend.services.location import LocationService, BUSAN_CENTER, BUSAN_BOUNDS


@pytest.fixture
def svc():
    return LocationService()


# ── haversine ──

class TestHaversine:
    def test_same_point_returns_zero(self):
        dist = LocationService.haversine(35.1796, 129.0756, 35.1796, 129.0756)
        assert dist == 0.0

    def test_known_distance_haeundae_to_gwangalli(self):
        # 해운대 → 광안리: 약 3~5km
        dist = LocationService.haversine(35.1587, 129.1604, 35.1531, 129.1186)
        assert 3.0 < dist < 6.0

    def test_known_distance_busan_station_to_haeundae(self):
        # 부산역 → 해운대: 약 13~17km
        dist = LocationService.haversine(35.1152, 129.0414, 35.1587, 129.1604)
        assert 10.0 < dist < 20.0

    def test_symmetry(self):
        d1 = LocationService.haversine(35.0, 129.0, 35.5, 129.5)
        d2 = LocationService.haversine(35.5, 129.5, 35.0, 129.0)
        assert abs(d1 - d2) < 0.001

    def test_returns_float(self):
        dist = LocationService.haversine(35.0, 129.0, 36.0, 130.0)
        assert isinstance(dist, float)


# ── is_in_busan ──

class TestIsInBusan:
    def test_busan_center_is_in_busan(self):
        assert LocationService.is_in_busan(*BUSAN_CENTER) is True

    def test_haeundae_is_in_busan(self):
        assert LocationService.is_in_busan(35.1587, 129.1604) is True

    def test_seoul_is_not_in_busan(self):
        assert LocationService.is_in_busan(37.5665, 126.9780) is False

    def test_boundary_south(self):
        assert LocationService.is_in_busan(BUSAN_BOUNDS["south"], 129.0) is True
        assert LocationService.is_in_busan(BUSAN_BOUNDS["south"] - 0.01, 129.0) is False

    def test_boundary_north(self):
        assert LocationService.is_in_busan(BUSAN_BOUNDS["north"], 129.0) is True
        assert LocationService.is_in_busan(BUSAN_BOUNDS["north"] + 0.01, 129.0) is False


# ── sort_by_distance ──

class TestSortByDistance:
    def test_sorts_nearest_first(self, svc, sample_spots):
        # 해운대 근처 좌표 기준
        result = svc.sort_by_distance(sample_spots, 35.16, 129.16)
        assert result[0]["name"] == "해운대 해수욕장"

    def test_adds_distance_km_field(self, svc, sample_spots):
        result = svc.sort_by_distance(sample_spots, 35.16, 129.16)
        for spot in result:
            assert "distance_km" in spot
            assert isinstance(spot["distance_km"], float)


# ── filter_by_radius ──

class TestFilterByRadius:
    def test_filter_includes_nearby(self, svc, sample_spots):
        # 해운대 근처에서 5km 반경 → 해운대만 포함
        result = svc.filter_by_radius(sample_spots, 35.16, 129.16, radius_km=5.0)
        names = [s["name"] for s in result]
        assert "해운대 해수욕장" in names

    def test_filter_excludes_far(self, svc, sample_spots):
        # 매우 작은 반경이면 아무것도 안 잡힘
        result = svc.filter_by_radius(sample_spots, 35.16, 129.16, radius_km=0.01)
        assert len(result) == 0

    def test_large_radius_includes_all(self, svc, sample_spots):
        result = svc.filter_by_radius(sample_spots, 35.13, 129.08, radius_km=50.0)
        assert len(result) == len(sample_spots)
