"""
FallbackRecommender 단위 테스트
- 폴백 추천 정렬
- 가중치 합
- limit 동작
"""
import pytest
from backend.ml.fallback import FallbackRecommender


@pytest.fixture
def recommender():
    return FallbackRecommender()


class TestFallbackRecommender:
    def test_returns_list(self, recommender, sample_spots):
        result = recommender.recommend(sample_spots, limit=10)
        assert isinstance(result, list)

    def test_respects_limit(self, recommender, sample_spots):
        result = recommender.recommend(sample_spots, limit=2)
        assert len(result) == 2

    def test_limit_larger_than_spots(self, recommender, sample_spots):
        result = recommender.recommend(sample_spots, limit=100)
        assert len(result) == len(sample_spots)

    def test_empty_spots(self, recommender):
        result = recommender.recommend([], limit=10)
        assert result == []

    def test_with_user_location(self, recommender, sample_spots):
        result = recommender.recommend(
            sample_spots, user_lat=35.16, user_lng=129.16, limit=3
        )
        assert len(result) <= 3

    def test_with_comfort_data(self, recommender, sample_spots, sample_comfort_data):
        result = recommender.recommend(
            sample_spots,
            comfort_data=sample_comfort_data,
            limit=3,
        )
        assert len(result) <= 3

    def test_ordering_deterministic(self, recommender, sample_spots):
        r1 = recommender.recommend(sample_spots, limit=10)
        r2 = recommender.recommend(sample_spots, limit=10)
        assert [s["id"] for s in r1] == [s["id"] for s in r2]


class TestFallbackWeights:
    def test_weights_sum_to_one(self):
        total = sum(FallbackRecommender.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_required_weight_keys(self):
        assert set(FallbackRecommender.WEIGHTS.keys()) == {
            "distance", "crowd", "popularity", "rating"
        }


class TestFallbackHaversine:
    def test_same_point(self):
        dist = FallbackRecommender._haversine(35.0, 129.0, 35.0, 129.0)
        assert dist == 0.0

    def test_positive_distance(self):
        dist = FallbackRecommender._haversine(35.0, 129.0, 35.1, 129.1)
        assert dist > 0
