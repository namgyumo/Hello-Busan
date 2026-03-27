"""
피처 엔지니어링
- 관광지 특성 + 실시간 데이터 -> 피처 벡터
- rating_norm 제거 (순환 논리 방지)
- 시간/요일/날씨/실내외/지역인기도/지하철혼잡도 피처 추가
"""
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import math
import logging

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "category_encoded",
    "distance_km",
    "crowd_level",
    "temperature",
    "humidity",
    "is_weekend",
    "hour_sin",
    "hour_cos",
    "accessibility_score",
    "view_count_norm",
    "hour_of_day",
    "day_of_week",
    "weather_condition",
    "subway_crowd_nearby",
    "is_indoor",
    "district_popularity",
]

# 카테고리별 실내/외 기본값
CATEGORY_INDOOR = {
    "culture": True,
    "food": True,
    "shopping": True,
    "nature": False,
    "activity": False,
    "nightview": False,
    "history": True,
    "landmark": False,
    "beach": False,
    "temple": False,
}

# 날씨 condition → 수치 인코딩
WEATHER_CONDITION_MAP = {
    "rain": 0,
    "cloudy": 1,
    "clear_cool": 2,
    "clear_hot": 3,
}


class FeatureBuilder:
    """피처 빌더"""

    CATEGORY_MAP = {
        "nature": 0,
        "culture": 1,
        "food": 2,
        "activity": 3,
        "shopping": 4,
        "nightview": 5,
        "history": 6,
        "landmark": 7,
        "beach": 8,
        "temple": 9,
    }

    def build_batch(
        self,
        spots: List[Dict],
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        comfort_data: Optional[Dict] = None,
        weather_data: Optional[Dict] = None,
        subway_crowd: Optional[Dict[str, float]] = None,
        district_visitors: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """
        배치 피처 생성
        Args:
            subway_crowd: {spot_id: 정규화된 가까운 역 하차 인원 (0~1)}
            district_visitors: {district_name: 정규화된 방문자 비율 (0~1)}
        Returns:
            (N, D) numpy 배열
        """
        features = []
        now = datetime.now()

        for spot in spots:
            feat = self._build_single(
                spot, user_lat, user_lng,
                comfort_data, weather_data, now,
                subway_crowd, district_visitors,
            )
            features.append(feat)

        return np.array(features, dtype=np.float32)

    def _build_single(
        self,
        spot: Dict,
        user_lat: Optional[float],
        user_lng: Optional[float],
        comfort_data: Optional[Dict],
        weather_data: Optional[Dict],
        now: datetime,
        subway_crowd: Optional[Dict[str, float]] = None,
        district_visitors: Optional[Dict[str, float]] = None,
    ) -> List[float]:
        """단일 관광지 피처 벡터"""
        spot_id = str(spot.get("id", ""))
        comfort = (comfort_data or {}).get(spot_id, {})

        # 카테고리 인코딩
        category = self.CATEGORY_MAP.get(spot.get("category_id", spot.get("category", "")), 0)

        # 거리 계산
        distance = 0.0
        if user_lat and user_lng:
            distance = self._haversine(
                user_lat, user_lng,
                spot.get("lat", 0), spot.get("lng", 0),
            )

        # 혼잡도 (crowd_score: 0~100 int, 높을수록 여유 → 0~1 float로 변환)
        raw_crowd_score = comfort.get("crowd_score", 50)
        if raw_crowd_score is None:
            raw_crowd_score = 50
        crowd_level = raw_crowd_score / 100.0

        # 날씨
        weather = weather_data or {}
        temperature = weather.get("temperature", 20.0)
        humidity = weather.get("humidity", 50.0)

        # 시간 피처
        is_weekend = 1.0 if now.weekday() >= 5 else 0.0
        hour = now.hour
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)

        # 접근성
        accessibility = spot.get("accessibility_score", 0.5)

        # 인기도 (view_count 정규화)
        view_count = spot.get("view_count", 0)
        view_norm = min(view_count / 10000, 1.0)

        # --- 새 피처 ---
        # hour_of_day (0~23 정규화)
        hour_of_day = hour / 23.0

        # day_of_week (0~6 정규화)
        day_of_week = now.weekday() / 6.0

        # weather_condition (rain=0, cloudy=1, clear_cool=2, clear_hot=3 → 정규화)
        weather_condition_str = weather.get("condition", "clear_cool")
        weather_condition = WEATHER_CONDITION_MAP.get(weather_condition_str, 2) / 3.0

        # subway_crowd_nearby (가장 가까운 역의 시간대별 정규화 하차 인원)
        subway_crowd_val = 0.0
        if subway_crowd:
            subway_crowd_val = subway_crowd.get(spot_id, 0.0)

        # is_indoor (카테고리 기반)
        cat_name = spot.get("category_id", spot.get("category", ""))
        is_indoor = 1.0 if CATEGORY_INDOOR.get(cat_name, False) else 0.0

        # district_popularity (구군 방문자 비율 정규화)
        district_pop = 0.5  # 기본값
        if district_visitors:
            address = spot.get("address", "")
            for district_name, ratio in district_visitors.items():
                if district_name in address:
                    district_pop = ratio
                    break

        return [
            float(category),
            distance,
            crowd_level,
            temperature,
            humidity,
            is_weekend,
            hour_sin,
            hour_cos,
            accessibility,
            view_norm,
            hour_of_day,
            day_of_week,
            weather_condition,
            subway_crowd_val,
            is_indoor,
            district_pop,
        ]

    @staticmethod
    def _haversine(
        lat1: float, lng1: float,
        lat2: float, lng2: float,
    ) -> float:
        """두 좌표 간 거리 (km)"""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
