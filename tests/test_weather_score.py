"""
ScoreCalculator._calc_weather_score 단위 테스트
- 기온/습도/강수/하늘 조합별 점수 검증
"""
import pytest
from backend.services.score_calculator import ScoreCalculator


@pytest.fixture
def calc():
    return ScoreCalculator()


class TestCalcWeatherScore:
    def test_empty_weather_returns_default(self, calc):
        assert calc._calc_weather_score({}) == 60

    def test_perfect_weather(self, calc):
        weather = {
            "temperature": 22,
            "humidity": 50,
            "rain_type": "없음",
            "sky_code": "1",
        }
        score = calc._calc_weather_score(weather)
        # 전부 100점 → 100
        assert score == 100

    def test_rain_penalizes_heavily(self, calc):
        sunny = {
            "temperature": 22, "humidity": 50,
            "rain_type": "없음", "sky_code": "1",
        }
        rainy = {
            "temperature": 22, "humidity": 50,
            "rain_type": "비", "sky_code": "4",
        }
        assert calc._calc_weather_score(sunny) > calc._calc_weather_score(rainy)

    def test_extreme_cold(self, calc):
        weather = {
            "temperature": -5, "humidity": 50,
            "rain_type": "없음", "sky_code": "1",
        }
        score = calc._calc_weather_score(weather)
        assert score < 70

    def test_extreme_hot(self, calc):
        weather = {
            "temperature": 38, "humidity": 85,
            "rain_type": "없음", "sky_code": "4",
        }
        score = calc._calc_weather_score(weather)
        assert score < 50

    def test_optimal_temperature_range(self, calc):
        for temp in [18, 20, 22, 25]:
            weather = {
                "temperature": temp, "humidity": 50,
                "rain_type": "없음", "sky_code": "1",
            }
            score = calc._calc_weather_score(weather)
            assert score >= 90, f"Temp {temp} should give high score, got {score}"

    def test_high_humidity_lowers_score(self, calc):
        low_humidity = {
            "temperature": 22, "humidity": 50,
            "rain_type": "없음", "sky_code": "1",
        }
        high_humidity = {
            "temperature": 22, "humidity": 90,
            "rain_type": "없음", "sky_code": "1",
        }
        assert calc._calc_weather_score(low_humidity) > calc._calc_weather_score(high_humidity)

    def test_score_range(self, calc):
        """어떤 날씨든 0~100 범위"""
        test_cases = [
            {"temperature": -20, "humidity": 100, "rain_type": "눈", "sky_code": "4"},
            {"temperature": 45, "humidity": 0, "rain_type": "없음", "sky_code": "1"},
            {},
        ]
        for weather in test_cases:
            score = calc._calc_weather_score(weather)
            assert 0 <= score <= 100, f"Score {score} out of range for {weather}"
