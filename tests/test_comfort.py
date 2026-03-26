"""
쾌적도 로직 단위 테스트
- _get_grade 등급 판정
- ComfortService.calc_comfort_score 가중 합산
- COMFORT_WEIGHTS 합이 1.0
"""
import pytest
from backend.services.comfort import _get_grade, ComfortService, COMFORT_WEIGHTS


# ── 등급 판정 ──

class TestGetGrade:
    @pytest.mark.parametrize("score,expected", [
        (100, "쾌적"),
        (80, "쾌적"),
        (79, "보통"),
        (60, "보통"),
        (59, "혼잡"),
        (40, "혼잡"),
        (39, "매우혼잡"),
        (0, "매우혼잡"),
    ])
    def test_grade_boundaries(self, score, expected):
        assert _get_grade(score) == expected

    def test_negative_score_returns_매우혼잡(self):
        assert _get_grade(-10) == "매우혼잡"


# ── 가중 합산 ──

class TestCalcComfortScore:
    def test_all_perfect(self):
        score = ComfortService.calc_comfort_score(
            weather_score=100, crowd_score=100, transport_score=100
        )
        assert score == 100

    def test_all_zero(self):
        score = ComfortService.calc_comfort_score(
            weather_score=0, crowd_score=0, transport_score=0
        )
        assert score == 0

    def test_weights_applied_correctly(self):
        # weather=100, crowd=0, transport=0 → 0.3*100 = 30
        score = ComfortService.calc_comfort_score(
            weather_score=100, crowd_score=0, transport_score=0
        )
        assert score == 30

    def test_crowd_dominates(self):
        # crowd 가중치가 0.5로 가장 높음
        score = ComfortService.calc_comfort_score(
            weather_score=0, crowd_score=100, transport_score=0
        )
        assert score == 50

    def test_default_values(self):
        # 기본값 50, 50, 50 → 50
        score = ComfortService.calc_comfort_score()
        assert score == 50


# ── 가중치 무결성 ──

class TestComfortWeights:
    def test_weights_sum_to_one(self):
        total = sum(COMFORT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_weights_positive(self):
        for k, v in COMFORT_WEIGHTS.items():
            assert v > 0, f"{k} weight should be positive"

    def test_required_keys(self):
        assert set(COMFORT_WEIGHTS.keys()) == {"weather", "crowd", "transport"}
