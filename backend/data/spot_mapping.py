"""
관광지-지하철역 최근접 매핑
- haversine 거리 기반으로 관광지에서 가장 가까운 지하철역 탐색
"""
import math
from typing import Dict, List, Optional
from backend.data.subway_stations import SUBWAY_STATIONS


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
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


def find_nearest_stations(
    spot_lat: float,
    spot_lng: float,
    top_n: int = 3,
) -> List[Dict]:
    """
    관광지 좌표에서 가장 가까운 지하철역 top_n개 반환

    Returns:
        [{"name": "해운대", "line": 2, "distance_km": 0.5}, ...]
    """
    distances = []
    for name, info in SUBWAY_STATIONS.items():
        dist = haversine(spot_lat, spot_lng, info["lat"], info["lng"])
        distances.append({
            "name": name,
            "line": info["line"],
            "distance_km": round(dist, 3),
        })

    distances.sort(key=lambda x: x["distance_km"])
    return distances[:top_n]


def map_spots_to_stations(
    spots: List[Dict],
    top_n: int = 3,
) -> List[Dict]:
    """
    관광지 리스트 전체에 대해 최근접 지하철역 매핑

    Args:
        spots: [{"id": 1, "name": "해운대해수욕장", "lat": 35.16, "lng": 129.16}, ...]
        top_n: 반환할 최근접 역 수

    Returns:
        [{"spot_id": 1, "spot_name": "해운대해수욕장",
          "nearest_stations": [{"name": "해운대", "line": 2, "distance_km": 0.3}, ...]}, ...]
    """
    results = []
    for spot in spots:
        lat = spot.get("lat")
        lng = spot.get("lng")
        if lat is None or lng is None:
            continue

        nearest = find_nearest_stations(lat, lng, top_n=top_n)
        results.append({
            "spot_id": spot.get("id"),
            "spot_name": spot.get("name", ""),
            "nearest_stations": nearest,
        })

    return results
