"""
2차 QA — 혼잡도 추정 로직 테스트
- 시간대/요일/시즌/카테고리 가중치
- 클램핑 0~1
- 등급 텍스트 변환
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from backend.collector.crowd import (
    CrowdCollector,
    HOUR_WEIGHTS,
    DAY_MULTIPLIER,
    SEASON_MULTIPLIER,
    CATEGORY_PEAK,
)


@pytest.fixture
def collector():
    with patch("backend.config.settings") as mock_settings:
        mock_settings.DATA_API_KEY = "test_key"
        return CrowdCollector()


class TestHourWeights:
    def test_all_24_hours_covered(self):
        for h in range(24):
            assert h in HOUR_WEIGHTS, f"Hour {h} missing"

    def test_night_lower_than_day(self):
        assert HOUR_WEIGHTS[3] < HOUR_WEIGHTS[12]

    def test_peak_is_lunch_time(self):
        peak_hour = max(HOUR_WEIGHTS, key=HOUR_WEIGHTS.get)
        assert 11 <= peak_hour <= 13

    def test_all_weights_between_0_and_1(self):
        for h, w in HOUR_WEIGHTS.items():
            assert 0 <= w <= 1, f"Hour {h}: weight {w} out of range"


class TestDayMultiplier:
    def test_all_7_days_covered(self):
        for d in range(7):
            assert d in DAY_MULTIPLIER

    def test_weekend_higher_than_weekday(self):
        assert DAY_MULTIPLIER[5] > DAY_MULTIPLIER[0]  # 토 > 월
        assert DAY_MULTIPLIER[6] > DAY_MULTIPLIER[0]  # 일 > 월

    def test_sunday_is_peak(self):
        peak_day = max(DAY_MULTIPLIER, key=DAY_MULTIPLIER.get)
        assert peak_day == 6  # 일요일


class TestSeasonMultiplier:
    def test_all_12_months_covered(self):
        for m in range(1, 13):
            assert m in SEASON_MULTIPLIER

    def test_summer_is_peak(self):
        peak_month = max(SEASON_MULTIPLIER, key=SEASON_MULTIPLIER.get)
        assert peak_month in [7, 8]  # 7~8월 (부산 여름 성수기)

    def test_winter_is_low(self):
        assert SEASON_MULTIPLIER[1] < SEASON_MULTIPLIER[7]
        assert SEASON_MULTIPLIER[12] < SEASON_MULTIPLIER[8]


class TestCrowdEstimation:
    def test_estimate_crowd_returns_valid_fields(self, collector):
        spot = {"id": 1, "category_id": "nature", "lat": 35.0, "lng": 129.0}
        now = datetime(2026, 7, 15, 12, 0)  # 화요일 정오, 7월
        result = collector._estimate_crowd(spot, now)

        assert "spot_id" in result
        assert "crowd_level" in result
        assert "crowd_count" in result
        assert "crowd_ratio" in result
        assert "source" in result

    def test_crowd_ratio_0_to_100(self, collector):
        spot = {"id": 1, "category_id": "nature"}
        for month in range(1, 13):
            for hour in [0, 6, 12, 18, 23]:
                for weekday in [0, 5, 6]:  # 월, 토, 일
                    # 날짜를 구성 (대략적으로)
                    day = 1
                    # weekday에 맞추기
                    now = datetime(2026, month, 10, hour, 0)
                    result = collector._estimate_crowd(spot, now)
                    assert 0 <= result["crowd_ratio"] <= 100, (
                        f"crowd_ratio {result['crowd_ratio']} out of range: "
                        f"month={month}, hour={hour}"
                    )

    def test_crowd_level_text_valid(self, collector):
        spot = {"id": 1, "category_id": "nature"}
        valid_levels = {"여유", "보통", "혼잡", "매우혼잡"}
        for hour in range(24):
            now = datetime(2026, 8, 2, hour, 0)  # 일요일, 8월 성수기
            result = collector._estimate_crowd(spot, now)
            assert result["crowd_level"] in valid_levels, (
                f"Invalid level '{result['crowd_level']}' at hour {hour}"
            )

    def test_category_peak_boosts_score(self, collector):
        """음식점은 점심 시간에 더 혼잡"""
        food_spot = {"id": 1, "category_id": "food"}
        now_peak = datetime(2026, 7, 1, 12, 0)  # 점심
        now_off = datetime(2026, 7, 1, 3, 0)   # 새벽
        peak = collector._estimate_crowd(food_spot, now_peak)
        off = collector._estimate_crowd(food_spot, now_off)
        assert peak["crowd_ratio"] > off["crowd_ratio"]

    def test_nightview_peaks_at_night(self, collector):
        spot = {"id": 1, "category_id": "nightview"}
        # 야경 카테고리는 18~24시가 피크
        now_night = datetime(2026, 7, 5, 20, 0)
        now_morning = datetime(2026, 7, 5, 8, 0)
        night = collector._estimate_crowd(spot, now_night)
        morning = collector._estimate_crowd(spot, now_morning)
        assert night["crowd_ratio"] >= morning["crowd_ratio"]

    def test_visitor_count_is_non_negative(self, collector):
        spot = {"id": 1, "category_id": "nature"}
        now = datetime(2026, 1, 1, 3, 0)  # 최저 혼잡도 시간
        result = collector._estimate_crowd(spot, now)
        assert result["crowd_count"] >= 0


class TestVisitorCountEstimation:
    def test_nature_max_capacity(self, collector):
        count = collector._estimate_visitor_count(1.0, "nature")
        assert count == 5000

    def test_zero_crowd_zero_visitors(self, collector):
        count = collector._estimate_visitor_count(0.0, "nature")
        assert count == 0

    def test_unknown_category_uses_default(self, collector):
        count = collector._estimate_visitor_count(1.0, "unknown")
        assert count == 2000  # 기본값
