"""
콘텐츠 기반 유사 관광지 추천 엔진
- 카테고리, 위치, 평점 피처로 코사인 유사도 계산
"""
import numpy as np
import math
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# 피처별 가중치
WEIGHT_CATEGORY = 0.5
WEIGHT_LOCATION = 0.3
WEIGHT_RATING = 0.2

# 지원하는 카테고리 목록 (one-hot 인코딩용)
CATEGORIES = ["nature", "culture", "food", "activity", "shopping", "nightview"]


class SimilarityEngine:
    """코사인 유사도 기반 유사 관광지 추천"""

    def find_similar(
        self,
        spot_id: str,
        all_spots: List[Dict],
        top_k: int = 5,
    ) -> List[Dict]:
        """
        대상 관광지와 유사한 관광지 top_k개 반환.

        Args:
            spot_id: 기준 관광지 ID
            all_spots: 전체 관광지 목록 (각 dict에 id, category_id, lat, lng, rating 포함)
            top_k: 반환할 유사 관광지 수

        Returns:
            유사도 내림차순으로 정렬된 관광지 목록 (similarity_score 포함)
        """
        target = None
        others = []
        for spot in all_spots:
            if str(spot.get("id", "")) == str(spot_id):
                target = spot
            else:
                others.append(spot)

        if target is None or not others:
            return []

        target_vec = self._build_feature_vector(target, all_spots)

        scored = []
        for spot in others:
            vec = self._build_feature_vector(spot, all_spots)
            sim = self._cosine_similarity(target_vec, vec)
            scored.append((spot, sim))

        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for spot, sim in scored[:top_k]:
            result = dict(spot)
            result["similarity_score"] = round(sim, 4)
            results.append(result)

        return results

    def _build_feature_vector(
        self, spot: Dict, all_spots: List[Dict]
    ) -> np.ndarray:
        """
        관광지를 가중 피처 벡터로 변환.
        - 카테고리: one-hot 인코딩 * WEIGHT_CATEGORY
        - 위치: 정규화된 위도/경도 * WEIGHT_LOCATION
        - 평점: 정규화된 평점 * WEIGHT_RATING
        """
        # 카테고리 one-hot
        cat = spot.get("category_id", spot.get("category", ""))
        cat_vec = np.zeros(len(CATEGORIES), dtype=np.float32)
        if cat in CATEGORIES:
            cat_vec[CATEGORIES.index(cat)] = 1.0
        cat_vec *= WEIGHT_CATEGORY

        # 위치 정규화 (부산 위도 34.8~35.3, 경도 128.8~129.3 범위 기준)
        lat = spot.get("lat", 0.0) or 0.0
        lng = spot.get("lng", 0.0) or 0.0
        lat_min, lat_max = self._get_range(all_spots, "lat")
        lng_min, lng_max = self._get_range(all_spots, "lng")
        lat_norm = self._normalize(lat, lat_min, lat_max)
        lng_norm = self._normalize(lng, lng_min, lng_max)
        loc_vec = np.array([lat_norm, lng_norm], dtype=np.float32) * WEIGHT_LOCATION

        # 평점 정규화 (0~5 범위)
        rating = spot.get("rating", 3.0)
        if rating is None:
            rating = 3.0
        rating_norm = rating / 5.0
        rating_vec = np.array([rating_norm], dtype=np.float32) * WEIGHT_RATING

        return np.concatenate([cat_vec, loc_vec, rating_vec])

    @staticmethod
    def _normalize(value: float, min_val: float, max_val: float) -> float:
        """min-max 정규화 (0~1)"""
        if max_val == min_val:
            return 0.5
        return (value - min_val) / (max_val - min_val)

    @staticmethod
    def _get_range(spots: List[Dict], key: str) -> tuple:
        """전체 관광지에서 특정 필드의 min/max 반환"""
        values = [s.get(key, 0.0) or 0.0 for s in spots]
        if not values:
            return (0.0, 1.0)
        return (min(values), max(values))

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """코사인 유사도 계산"""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))
