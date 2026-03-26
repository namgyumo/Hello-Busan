"""
위치 서비스
- 좌표 기반 거리 계산
- 관광지 근처 검색
"""
from typing import Dict, List, Optional, Tuple
import math
import logging

logger = logging.getLogger(__name__)

BUSAN_CENTER = (35.1796, 129.0756)
BUSAN_BOUNDS = {
    "north": 35.35,
    "south": 34.88,
    "east": 129.35,
    "west": 128.75,
}


class LocationService:
    """위치 기반 서비스"""

    @staticmethod
    def haversine(
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

    @staticmethod
    def is_in_busan(lat: float, lng: float) -> bool:
        """부산 영역 내인지 확인"""
        return (
            BUSAN_BOUNDS["south"] <= lat <= BUSAN_BOUNDS["north"]
            and BUSAN_BOUNDS["west"] <= lng <= BUSAN_BOUNDS["east"]
        )

    def sort_by_distance(
        self,
        spots: List[Dict],
        user_lat: float,
        user_lng: float,
    ) -> List[Dict]:
        """거리 기준 정렬"""
        for spot in spots:
            spot["distance_km"] = self.haversine(
                user_lat, user_lng,
                spot.get("lat", 0), spot.get("lng", 0),
            )
        return sorted(spots, key=lambda x: x.get("distance_km", 999))

    def filter_by_radius(
        self,
        spots: List[Dict],
        user_lat: float,
        user_lng: float,
        radius_km: float = 5.0,
    ) -> List[Dict]:
        """반경 내 관광지 필터"""
        result = []
        for spot in spots:
            dist = self.haversine(
                user_lat, user_lng,
                spot.get("lat", 0), spot.get("lng", 0),
            )
            if dist <= radius_km:
                spot["distance_km"] = dist
                result.append(spot)
        return result
