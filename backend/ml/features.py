"""
피처 엔지니어링
- 관광지 특성 + 실시간 데이터 -> 피처 벡터
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
    "rating_norm",
]


class FeatureBuilder:
    """피처 빌더"""

    CATEGORY_MAP = {
        "nature": 0,
        "culture": 1,
        "food": 2,
        "activity": 3,
        "nightlife": 4,
    }

    def build_batch(
        self,
        spots: List[Dict],
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        comfort_data: Optional[Dict] = None,
        weather_data: Optional[Dict] = None,
    ) -> np.ndarray:
        """
        배치 피처 생성
        Returns:
            (N, D) numpy 배열
        """
        features = []
        now = datetime.now()

        for spot in spots:
            feat = self._build_single(
                spot, user_lat, user_lng,
                comfort_data, weather_data, now,
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
    ) -> List[float]:
        """단일 관광지 피처 벡터"""
        spot_id = spot.get("id", "")
        comfort = (comfort_data or {}).get(spot_id, {})

        # 카테고리 인코딩
        category = self.CATEGORY_MAP.get(spot.get("category", ""), 0)

        # 거리 계산
        distance = 0.0
        if user_lat and user_lng:
            distance = self._haversine(
                user_lat, user_lng,
                spot.get("lat", 0), spot.get("lng", 0),
            )

        # 혼잡도
        crowd_level = comfort.get("crowd_level", 0.5)

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

        # 인기도
        view_count = spot.get("view_count", 0)
        view_norm = min(view_count / 10000, 1.0)

        rating = spot.get("rating", 3.0)
        rating_norm = rating / 5.0

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
            rating_norm,
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
