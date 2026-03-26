"""
폴백 추천 로직
- ML 모델 미사용 시 규칙 기반 추천
- 거리 + 혼잡도 + 인기도 가중 점수
"""
from typing import Dict, List, Optional
import math
import logging

logger = logging.getLogger(__name__)


class FallbackRecommender:
    """규칙 기반 폴백 추천기"""

    WEIGHTS = {
        "distance": 0.3,
        "crowd": 0.3,
        "popularity": 0.2,
        "rating": 0.2,
    }

    def recommend(
        self,
        spots: List[Dict],
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        comfort_data: Optional[Dict] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """
        규칙 기반 추천
        점수 = w1*거리점수 + w2*쾌적도점수 + w3*인기도 + w4*평점
        """
        scored = []
        for spot in spots:
            score = self._calc_score(
                spot, user_lat, user_lng, comfort_data,
            )
            scored.append((spot, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:limit]]

    def _calc_score(
        self,
        spot: Dict,
        user_lat: Optional[float],
        user_lng: Optional[float],
        comfort_data: Optional[Dict],
    ) -> float:
        """개별 관광지 점수 계산"""
        # 거리 점수 (가까울수록 높음)
        distance_score = 1.0
        if user_lat and user_lng:
            dist = self._haversine(
                user_lat, user_lng,
                spot.get("lat", 0), spot.get("lng", 0),
            )
            distance_score = max(0, 1 - dist / 20)  # 20km 이내

        # 쾌적도 점수 (낮을수록 좋음 = 덜 혼잡)
        crowd_score = 0.5
        if comfort_data:
            comfort = comfort_data.get(spot.get("id", ""), {})
            crowd_level = comfort.get("crowd_level", 0.5)
            crowd_score = 1 - crowd_level

        # 인기도 점수
        view_count = spot.get("view_count", 0)
        popularity_score = min(view_count / 10000, 1.0)

        # 평점 점수
        rating = spot.get("rating", 3.0)
        rating_score = rating / 5.0

        total = (
            self.WEIGHTS["distance"] * distance_score
            + self.WEIGHTS["crowd"] * crowd_score
            + self.WEIGHTS["popularity"] * popularity_score
            + self.WEIGHTS["rating"] * rating_score
        )
        return total

    @staticmethod
    def _haversine(
        lat1: float, lng1: float,
        lat2: float, lng2: float,
    ) -> float:
        """Haversine 거리 (km)"""
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
