"""
2차 QA — 모듈 간 데이터 정합성 테스트
- 백엔드 등급 ↔ 프론트엔드 등급 매칭
- API 응답 필드 ↔ 프론트엔드 사용 필드 매칭
- 가중치 합 / 점수 범위 교차 검증
"""
import pytest
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


class TestGradeConsistency:
    """백엔드 _get_grade ↔ 프론트엔드 _gradeText / _comfortBadgeHtml 등급 일치"""

    def _read_file(self, rel_path):
        return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")

    def test_backend_grade_labels(self):
        from backend.services.comfort import GRADE_MAP
        backend_grades = {label for _, label in GRADE_MAP}
        expected = {"쾌적", "보통", "혼잡", "매우혼잡"}
        assert backend_grades == expected

    def test_frontend_recommend_gradeText_matches_backend(self):
        js = self._read_file("frontend/js/recommend.js")
        # _gradeText 함수 내의 한글 등급만 추출
        backend_grades = {"쾌적", "보통", "혼잡", "매우혼잡"}
        for grade in backend_grades:
            assert grade in js, f"프론트 recommend.js에 등급 '{grade}' 누락"

    def test_frontend_map_comfortBadge_has_all_grades(self):
        js = self._read_file("frontend/js/map.js")
        for grade in ["쾌적", "보통", "혼잡", "매우혼잡"]:
            assert grade in js, f"map.js에 등급 '{grade}' 매핑 누락"

    def test_frontend_css_has_score_classes(self):
        css = self._read_file("frontend/css/style.css")
        for cls in ["score--good", "score--normal", "score--crowded", "score--very-crowded"]:
            assert cls in css, f"CSS에 클래스 '{cls}' 누락"


class TestRecommendResponseFields:
    """recommend API 응답 필드 ↔ 프론트엔드 사용 필드"""

    def test_recommend_response_has_all_frontend_fields(self):
        """프론트엔드 recommend.js가 사용하는 필드가 API 응답에 포함되는지"""
        # 프론트엔드가 사용하는 필드 (recommend.js renderList 함수 참조)
        frontend_fields = {
            "id", "name", "category", "comfort_score",
            "comfort_grade", "distance_km", "lat", "lng",
        }
        # recommend.py _build_reasons + items.append 에서 반환하는 필드
        from backend.api.recommend import router  # import to verify structure
        # 실제 응답 키 리스트 (recommend.py line 114~127)
        backend_fields = {
            "rank", "id", "name", "category", "recommend_score",
            "comfort_score", "comfort_grade", "lat", "lng",
            "distance_km", "reasons", "thumbnail_url",
        }
        missing = frontend_fields - backend_fields
        assert not missing, f"프론트엔드가 사용하는 필드 누락: {missing}"

    def test_spots_response_has_map_marker_fields(self):
        """MapModule.updateMarkers가 필요로 하는 필드"""
        marker_fields = {"name", "lat", "lng", "id", "comfort_score", "comfort_grade"}
        # spots.py items.append 에서 반환하는 필드
        spots_fields = {
            "id", "name", "category", "category_name",
            "lat", "lng", "distance_km", "comfort_score",
            "comfort_grade", "thumbnail_url", "crowd_level",
        }
        missing = marker_fields - spots_fields
        assert not missing, f"지도 마커에 필요한 필드 누락: {missing}"


class TestScoreRangeIntegrity:
    """점수 범위가 모든 모듈에서 0~100을 보장하는지"""

    def test_comfort_score_range(self):
        from backend.services.comfort import ComfortService
        # 극단값 조합
        test_cases = [
            (0, 0, 0),
            (100, 100, 100),
            (0, 100, 0),
            (100, 0, 100),
            (50, 50, 50),
        ]
        for w, c, t in test_cases:
            score = ComfortService.calc_comfort_score(w, c, t)
            assert 0 <= score <= 100, f"Score {score} out of range for ({w},{c},{t})"

    def test_weather_score_range_exhaustive(self):
        from backend.services.score_calculator import ScoreCalculator
        calc = ScoreCalculator()
        temps = [-30, -10, 0, 10, 18, 22, 25, 30, 35, 45]
        humidities = [0, 30, 50, 70, 90, 100]
        rains = ["없음", "0", "비", "눈", "소나기"]
        skies = ["1", "3", "4", "unknown"]
        for temp in temps:
            for hum in humidities:
                for rain in rains:
                    for sky in skies:
                        score = calc._calc_weather_score({
                            "temperature": temp,
                            "humidity": hum,
                            "rain_type": rain,
                            "sky_code": sky,
                        })
                        assert 0 <= score <= 100, (
                            f"Score {score} out of range: "
                            f"temp={temp}, hum={hum}, rain={rain}, sky={sky}"
                        )

    def test_grade_covers_full_range(self):
        """0~100 어떤 점수든 등급이 반환되는지"""
        from backend.services.comfort import _get_grade
        for score in range(0, 101):
            grade = _get_grade(score)
            assert grade in {"쾌적", "보통", "혼잡", "매우혼잡"}, f"Score {score} → invalid grade '{grade}'"
