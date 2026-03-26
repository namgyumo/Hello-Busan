"""
FeatureBuilder 단위 테스트
- 피처 벡터 차원
- 카테고리 인코딩
- 시간 피처 범위
"""
import pytest
import numpy as np
from backend.ml.features import FeatureBuilder, FEATURE_COLUMNS


@pytest.fixture
def builder():
    return FeatureBuilder()


class TestFeatureBuilder:
    def test_output_shape(self, builder, sample_spots):
        features = builder.build_batch(sample_spots)
        assert features.shape == (3, len(FEATURE_COLUMNS))

    def test_output_dtype(self, builder, sample_spots):
        features = builder.build_batch(sample_spots)
        assert features.dtype == np.float32

    def test_single_spot(self, builder):
        spot = {"id": 1, "category": "nature", "lat": 35.15, "lng": 129.06}
        features = builder.build_batch([spot])
        assert features.shape == (1, len(FEATURE_COLUMNS))

    def test_category_encoding(self, builder):
        spot_nature = {"id": 1, "category": "nature"}
        spot_food = {"id": 2, "category": "food"}
        f1 = builder.build_batch([spot_nature])
        f2 = builder.build_batch([spot_food])
        assert f1[0, 0] == 0.0  # nature → 0
        assert f2[0, 0] == 2.0  # food → 2

    def test_unknown_category_defaults_zero(self, builder):
        spot = {"id": 1, "category": "unknown_cat"}
        features = builder.build_batch([spot])
        assert features[0, 0] == 0.0

    def test_distance_zero_without_user_location(self, builder, sample_spots):
        features = builder.build_batch(sample_spots, user_lat=None, user_lng=None)
        # distance_km column (index 1) should be 0
        assert all(features[:, 1] == 0.0)

    def test_distance_nonzero_with_user_location(self, builder, sample_spots):
        features = builder.build_batch(sample_spots, user_lat=35.16, user_lng=129.16)
        # 적어도 하나는 0이 아님 (해운대 근처)
        assert any(features[:, 1] > 0.0)

    def test_hour_sin_cos_range(self, builder):
        spot = {"id": 1}
        features = builder.build_batch([spot])
        hour_sin = features[0, 6]
        hour_cos = features[0, 7]
        assert -1.0 <= hour_sin <= 1.0
        assert -1.0 <= hour_cos <= 1.0

    def test_no_nan_values(self, builder, sample_spots):
        features = builder.build_batch(sample_spots)
        assert not np.isnan(features).any()
