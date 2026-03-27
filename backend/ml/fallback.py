"""
폴백 추천 로직
- ML 모델 미사용 시 규칙 기반 추천
- 거리 + 혼잡도 + 인기도 가중 점수
- 시간대/요일/날씨에 따른 동적 가중치 조정
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import math
import logging

logger = logging.getLogger(__name__)

# 카테고리별 실내/외 기본값 및 최적 시간대
CATEGORY_META = {
    "culture":   {"is_indoor": True,  "best_time": "anytime"},
    "food":      {"is_indoor": True,  "best_time": "anytime"},
    "shopping":  {"is_indoor": True,  "best_time": "afternoon"},
    "nature":    {"is_indoor": False, "best_time": "morning"},
    "activity":  {"is_indoor": False, "best_time": "afternoon"},
    "nightview": {"is_indoor": False, "best_time": "night"},
    "history":   {"is_indoor": True,  "best_time": "morning"},
    "landmark":  {"is_indoor": False, "best_time": "afternoon"},
    "beach":     {"is_indoor": False, "best_time": "afternoon"},
    "temple":    {"is_indoor": False, "best_time": "morning"},
}

# best_time을 시간 범위로 매핑 (검증용)
BEST_TIME_HOURS = {
    "morning":   (6, 12),
    "afternoon": (12, 18),
    "evening":   (17, 21),
    "night":     (18, 24),
    "anytime":   (0, 24),
}


class FallbackRecommender:
    """규칙 기반 폴백 추천기 (컨텍스트 인식)"""

    BASE_WEIGHTS = {
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
        context: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        규칙 기반 추천
        점수 = w1*거리점수 + w2*쾌적도점수 + w3*인기도 + w4*평점 + 카테고리 부스트
        context: {"weather": "rain"|"clear_hot"|"clear_cool"|"cloudy",
                  "hour": int, "is_weekend": bool}
        """
        if context is None:
            context = self._build_default_context()

        weights = self._dynamic_weights(context)

        scored = []
        for spot in spots:
            score = self._calc_score(
                spot, user_lat, user_lng, comfort_data, weights, context,
            )
            scored.append((spot, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:limit]]

    @staticmethod
    def _build_default_context() -> Dict:
        """현재 시각 기반 기본 컨텍스트"""
        kst = datetime.now(timezone(timedelta(hours=9)))
        return {
            "weather": "clear_cool",
            "hour": kst.hour,
            "is_weekend": kst.weekday() >= 5,
        }

    def _dynamic_weights(self, context: Dict) -> Dict[str, float]:
        """시간대/요일에 따라 기본 가중치를 동적으로 조정"""
        w = dict(self.BASE_WEIGHTS)
        is_weekend = context.get("is_weekend", False)

        if is_weekend:
            # 주말: 혼잡도 가중치 상향
            w["crowd"] = 0.35
            w["distance"] = 0.25
        else:
            # 평일: 거리 가중치 상향 (이동 효율 중시)
            w["distance"] = 0.35
            w["crowd"] = 0.25

        return w

    def _category_boost(self, spot: Dict, context: Dict) -> float:
        """카테고리와 컨텍스트 조합에 따른 부스트/디부스트 점수"""
        category = spot.get("category_id", "")
        weather = context.get("weather", "clear_cool")
        hour = context.get("hour", 12)
        meta = CATEGORY_META.get(category, {})
        is_indoor = meta.get("is_indoor", False)
        boost = 0.0

        # --- 날씨 기반 ---
        if weather == "rain":
            if is_indoor:
                boost += 0.12  # 비 올 때 실내 부스트
            else:
                boost -= 0.10  # 비 올 때 야외 디부스트
        elif weather == "clear_hot":
            if is_indoor:
                boost += 0.05  # 폭염 시 실내 약간 부스트

        # --- 시간대 기반 ---
        if 18 <= hour or hour < 5:
            # 야간
            if category == "nightview":
                boost += 0.15
            elif category == "food":
                boost += 0.08
            elif category == "nature":
                boost -= 0.08
        elif 6 <= hour < 11:
            # 오전
            if category in ("nature", "culture", "temple"):
                boost += 0.08
        # 식사 시간
        if (11 <= hour <= 13) or (17 <= hour <= 19):
            if category == "food":
                boost += 0.10

        # --- best_time 매칭 보너스 ---
        best_time = meta.get("best_time", "anytime")
        if best_time != "anytime":
            start_h, end_h = BEST_TIME_HOURS.get(best_time, (0, 24))
            if start_h <= hour < end_h:
                boost += 0.05

        return boost

    def _calc_score(
        self,
        spot: Dict,
        user_lat: Optional[float],
        user_lng: Optional[float],
        comfort_data: Optional[Dict],
        weights: Dict[str, float],
        context: Dict,
    ) -> float:
        """개별 관광지 점수 계산 (컨텍스트 인식)"""
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
            comfort = comfort_data.get(str(spot.get("id", "")), {})
            raw_crowd_score = comfort.get("crowd_score", 50)
            if raw_crowd_score is None:
                raw_crowd_score = 50
            crowd_score = raw_crowd_score / 100.0

        # 인기도 점수
        view_count = spot.get("view_count", 0)
        popularity_score = min(view_count / 10000, 1.0)

        # 평점 점수
        rating = spot.get("rating", 3.0)
        rating_score = rating / 5.0

        base_total = (
            weights["distance"] * distance_score
            + weights["crowd"] * crowd_score
            + weights["popularity"] * popularity_score
            + weights["rating"] * rating_score
        )

        # 카테고리 부스트 적용
        boost = self._category_boost(spot, context)

        return base_total + boost

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
