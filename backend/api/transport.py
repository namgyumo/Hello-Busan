"""
대중교통 실시간 길찾기 API 라우터
- 출발지 → 도착지 경로 검색
- 버스/지하철/도보 조합 경로 옵션
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from backend.models.common import SuccessResponse, Meta
from backend.services.location import LocationService
from backend.db.supabase import get_supabase
from backend.cache.manager import CacheManager
from backend.config import settings
import httpx
import logging
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/transport", tags=["transport"])
logger = logging.getLogger(__name__)
cache = CacheManager()
location_service = LocationService()

# 부산 대중교통 상수
BUS_AVG_SPEED_KMH = 18.0
SUBWAY_AVG_SPEED_KMH = 35.0
WALK_SPEED_KMH = 4.5
TRANSFER_PENALTY_MIN = 5
BUS_BASE_FARE = 1400
SUBWAY_BASE_FARE = 1450
TRANSFER_DISCOUNT = 0


@router.get("/directions")
async def get_directions(
    origin_lat: float = Query(..., ge=33.0, le=38.0, description="출발지 위도"),
    origin_lng: float = Query(..., ge=124.0, le=132.0, description="출발지 경도"),
    dest_id: Optional[str] = Query(None, description="도착지 관광지 ID"),
    dest_lat: Optional[float] = Query(None, ge=33.0, le=38.0, description="도착지 위도"),
    dest_lng: Optional[float] = Query(None, ge=124.0, le=132.0, description="도착지 경도"),
    lang: str = Query("ko"),
):
    """대중교통 길찾기 — 출발지에서 도착지까지 경로 옵션 제공"""

    # 도착지 좌표 결정
    if dest_id:
        spot = await _get_spot_by_id(dest_id)
        if not spot:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")
        dest_lat = spot.get("lat")
        dest_lng = spot.get("lng")
        dest_name = spot.get("name", "")
    elif dest_lat is not None and dest_lng is not None:
        dest_name = ""
    else:
        raise HTTPException(
            status_code=400,
            detail="dest_id 또는 dest_lat/dest_lng가 필요합니다",
        )

    if dest_lat is None or dest_lng is None:
        raise HTTPException(status_code=400, detail="도착지 좌표가 유효하지 않습니다")

    # 캐시 확인
    cache_key = f"directions:{origin_lat:.4f}:{origin_lng:.4f}:{dest_lat:.4f}:{dest_lng:.4f}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        # 직선 거리 계산
        direct_distance = location_service.haversine(
            origin_lat, origin_lng, dest_lat, dest_lng
        )

        # 주변 정류장 정보 수집
        origin_stations = await _fetch_nearby_stations(origin_lat, origin_lng)
        dest_stations = await _fetch_nearby_stations(dest_lat, dest_lng)

        # 경로 옵션 생성
        routes = _build_route_options(
            origin_lat, origin_lng,
            dest_lat, dest_lng,
            direct_distance,
            origin_stations,
            dest_stations,
        )

        # 경로를 소요 시간순으로 정렬
        routes.sort(key=lambda r: r["total_time"])

        response = SuccessResponse(
            data={
                "origin": {"lat": origin_lat, "lng": origin_lng},
                "destination": {
                    "lat": dest_lat,
                    "lng": dest_lng,
                    "name": dest_name,
                    "id": dest_id,
                },
                "direct_distance_km": round(direct_distance, 2),
                "routes": routes,
                "timestamp": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            meta=Meta(total=len(routes)),
        )

        await cache.set(cache_key, response.model_dump(), ttl=180)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"길찾기 실패: {e}")
        raise HTTPException(status_code=500, detail="길찾기 중 오류 발생")


async def _get_spot_by_id(spot_id: str) -> Optional[dict]:
    """관광지 ID로 조회"""
    try:
        sb = get_supabase()
        result = (
            sb.table("tourist_spots")
            .select("id, name, lat, lng")
            .eq("id", spot_id)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return result.data[0]
    except Exception as e:
        logger.error(f"관광지 조회 실패: {e}")
    return None


async def _fetch_nearby_stations(lat: float, lng: float) -> list:
    """좌표 근처 버스 정류장 조회 (공공데이터포털 API)"""
    if not settings.DATA_API_KEY:
        return []

    try:
        params = {
            "serviceKey": settings.DATA_API_KEY,
            "numOfRows": "5",
            "pageNo": "1",
            "_type": "json",
            "gpsLati": str(lat),
            "gpsLong": str(lng),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "http://apis.data.go.kr/1613000/BusSttnInfoInqireService/getCrdntPrxmtSttnList",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        body = data.get("response", {}).get("body", {})
        items_wrapper = body.get("items", {})
        items = (
            items_wrapper.get("item", [])
            if isinstance(items_wrapper, dict)
            else []
        )
        if not isinstance(items, list):
            items = [items] if isinstance(items, dict) else []

        stations = []
        for item in items:
            stations.append(
                {
                    "name": item.get("nodenm", ""),
                    "id": item.get("nodeid", ""),
                    "distance_m": int(float(item.get("dist", 0))),
                    "lat": float(item.get("gpslati", lat)),
                    "lng": float(item.get("gpslong", lng)),
                }
            )
        return stations

    except Exception as e:
        logger.warning(f"정류장 조회 실패: {e}")
        return []


def _build_route_options(
    o_lat: float, o_lng: float,
    d_lat: float, d_lng: float,
    distance_km: float,
    origin_stations: list,
    dest_stations: list,
) -> list:
    """경로 옵션 생성 — 버스, 지하철+버스, 도보"""
    routes = []

    # 1) 도보 경로 (3km 이하일 때만)
    if distance_km <= 3.0:
        walk_distance = distance_km * 1.3  # 도보 우회 계수
        walk_time = round((walk_distance / WALK_SPEED_KMH) * 60)
        routes.append({
            "type": "walk",
            "summary": "도보",
            "total_time": walk_time,
            "total_distance_km": round(walk_distance, 2),
            "fare": 0,
            "transfers": 0,
            "segments": [
                {
                    "mode": "walk",
                    "from": {"lat": o_lat, "lng": o_lng, "name": "출발지"},
                    "to": {"lat": d_lat, "lng": d_lng, "name": "도착지"},
                    "distance_km": round(walk_distance, 2),
                    "time_min": walk_time,
                },
            ],
            "polyline": [
                [o_lat, o_lng],
                [d_lat, d_lng],
            ],
        })

    # 2) 버스 경로
    bus_route = _build_bus_route(
        o_lat, o_lng, d_lat, d_lng,
        distance_km, origin_stations, dest_stations,
    )
    if bus_route:
        routes.append(bus_route)

    # 3) 지하철 + 버스 환승 경로 (5km 이상일 때)
    if distance_km >= 5.0:
        subway_route = _build_subway_bus_route(
            o_lat, o_lng, d_lat, d_lng,
            distance_km, origin_stations, dest_stations,
        )
        if subway_route:
            routes.append(subway_route)

    # 4) 버스 환승 경로 (거리가 멀 때)
    if distance_km >= 3.0:
        transfer_route = _build_bus_transfer_route(
            o_lat, o_lng, d_lat, d_lng,
            distance_km, origin_stations, dest_stations,
        )
        if transfer_route:
            routes.append(transfer_route)

    return routes


def _build_bus_route(
    o_lat, o_lng, d_lat, d_lng,
    distance_km, origin_stations, dest_stations,
):
    """버스 직행 경로"""
    walk_to_station = 0.3  # 기본 정류장까지 도보 거리 (km)
    walk_from_station = 0.3

    if origin_stations:
        walk_to_station = origin_stations[0]["distance_m"] / 1000
        o_station = origin_stations[0]
    else:
        o_station = {"name": "가까운 정류장", "lat": o_lat, "lng": o_lng}

    if dest_stations:
        walk_from_station = dest_stations[0]["distance_m"] / 1000
        d_station = dest_stations[0]
    else:
        d_station = {"name": "가까운 정류장", "lat": d_lat, "lng": d_lng}

    bus_distance = max(distance_km * 1.2 - walk_to_station - walk_from_station, 0.5)
    bus_time = round((bus_distance / BUS_AVG_SPEED_KMH) * 60)
    walk_to_time = round((walk_to_station / WALK_SPEED_KMH) * 60)
    walk_from_time = round((walk_from_station / WALK_SPEED_KMH) * 60)
    total_time = walk_to_time + bus_time + walk_from_time

    # 중간 경유 포인트 (폴리라인용)
    mid_lat = (o_lat + d_lat) / 2 + (d_lng - o_lng) * 0.05
    mid_lng = (o_lng + d_lng) / 2 - (d_lat - o_lat) * 0.05

    return {
        "type": "bus",
        "summary": "버스",
        "total_time": total_time,
        "total_distance_km": round(walk_to_station + bus_distance + walk_from_station, 2),
        "fare": BUS_BASE_FARE,
        "transfers": 0,
        "segments": [
            {
                "mode": "walk",
                "from": {"lat": o_lat, "lng": o_lng, "name": "출발지"},
                "to": {
                    "lat": o_station.get("lat", o_lat),
                    "lng": o_station.get("lng", o_lng),
                    "name": o_station.get("name", ""),
                },
                "distance_km": round(walk_to_station, 2),
                "time_min": walk_to_time,
            },
            {
                "mode": "bus",
                "from": {
                    "lat": o_station.get("lat", o_lat),
                    "lng": o_station.get("lng", o_lng),
                    "name": o_station.get("name", ""),
                },
                "to": {
                    "lat": d_station.get("lat", d_lat),
                    "lng": d_station.get("lng", d_lng),
                    "name": d_station.get("name", ""),
                },
                "distance_km": round(bus_distance, 2),
                "time_min": bus_time,
            },
            {
                "mode": "walk",
                "from": {
                    "lat": d_station.get("lat", d_lat),
                    "lng": d_station.get("lng", d_lng),
                    "name": d_station.get("name", ""),
                },
                "to": {"lat": d_lat, "lng": d_lng, "name": "도착지"},
                "distance_km": round(walk_from_station, 2),
                "time_min": walk_from_time,
            },
        ],
        "polyline": [
            [o_lat, o_lng],
            [o_station.get("lat", o_lat), o_station.get("lng", o_lng)],
            [mid_lat, mid_lng],
            [d_station.get("lat", d_lat), d_station.get("lng", d_lng)],
            [d_lat, d_lng],
        ],
    }


def _build_subway_bus_route(
    o_lat, o_lng, d_lat, d_lng,
    distance_km, origin_stations, dest_stations,
):
    """지하철 + 버스 환승 경로"""
    # 지하철 구간은 직선 거리의 60% 커버, 나머지 버스
    subway_distance = distance_km * 0.6
    bus_distance = distance_km * 0.4 * 1.2
    walk_to = 0.5
    walk_from = 0.3

    if origin_stations:
        walk_to = min(origin_stations[0]["distance_m"] / 1000, 0.8)
    if dest_stations:
        walk_from = min(dest_stations[0]["distance_m"] / 1000, 0.8)

    subway_time = round((subway_distance / SUBWAY_AVG_SPEED_KMH) * 60)
    bus_time = round((bus_distance / BUS_AVG_SPEED_KMH) * 60)
    walk_to_time = round((walk_to / WALK_SPEED_KMH) * 60)
    walk_from_time = round((walk_from / WALK_SPEED_KMH) * 60)
    total_time = walk_to_time + subway_time + TRANSFER_PENALTY_MIN + bus_time + walk_from_time

    # 환승 지점 (중간 지점)
    transfer_lat = o_lat + (d_lat - o_lat) * 0.6
    transfer_lng = o_lng + (d_lng - o_lng) * 0.6

    return {
        "type": "subway_bus",
        "summary": "지하철 + 버스",
        "total_time": total_time,
        "total_distance_km": round(walk_to + subway_distance + bus_distance + walk_from, 2),
        "fare": SUBWAY_BASE_FARE + BUS_BASE_FARE - TRANSFER_DISCOUNT,
        "transfers": 1,
        "segments": [
            {
                "mode": "walk",
                "from": {"lat": o_lat, "lng": o_lng, "name": "출발지"},
                "to": {"lat": o_lat, "lng": o_lng, "name": "지하철역"},
                "distance_km": round(walk_to, 2),
                "time_min": walk_to_time,
            },
            {
                "mode": "subway",
                "from": {"lat": o_lat, "lng": o_lng, "name": "지하철역"},
                "to": {"lat": transfer_lat, "lng": transfer_lng, "name": "환승 정류장"},
                "distance_km": round(subway_distance, 2),
                "time_min": subway_time,
            },
            {
                "mode": "bus",
                "from": {"lat": transfer_lat, "lng": transfer_lng, "name": "환승 정류장"},
                "to": {"lat": d_lat, "lng": d_lng, "name": "가까운 정류장"},
                "distance_km": round(bus_distance, 2),
                "time_min": bus_time,
            },
            {
                "mode": "walk",
                "from": {"lat": d_lat, "lng": d_lng, "name": "가까운 정류장"},
                "to": {"lat": d_lat, "lng": d_lng, "name": "도착지"},
                "distance_km": round(walk_from, 2),
                "time_min": walk_from_time,
            },
        ],
        "polyline": [
            [o_lat, o_lng],
            [transfer_lat, transfer_lng],
            [d_lat, d_lng],
        ],
    }


def _build_bus_transfer_route(
    o_lat, o_lng, d_lat, d_lng,
    distance_km, origin_stations, dest_stations,
):
    """버스 환승 경로"""
    walk_to = 0.3
    walk_from = 0.3

    if origin_stations:
        walk_to = min(origin_stations[0]["distance_m"] / 1000, 0.8)
    if dest_stations:
        walk_from = min(dest_stations[0]["distance_m"] / 1000, 0.8)

    # 환승 지점
    transfer_lat = o_lat + (d_lat - o_lat) * 0.45
    transfer_lng = o_lng + (d_lng - o_lng) * 0.45

    bus1_distance = distance_km * 0.5 * 1.2
    bus2_distance = distance_km * 0.5 * 1.2

    bus1_time = round((bus1_distance / BUS_AVG_SPEED_KMH) * 60)
    bus2_time = round((bus2_distance / BUS_AVG_SPEED_KMH) * 60)
    walk_to_time = round((walk_to / WALK_SPEED_KMH) * 60)
    walk_from_time = round((walk_from / WALK_SPEED_KMH) * 60)
    total_time = walk_to_time + bus1_time + TRANSFER_PENALTY_MIN + bus2_time + walk_from_time

    return {
        "type": "bus_transfer",
        "summary": "버스 (환승)",
        "total_time": total_time,
        "total_distance_km": round(walk_to + bus1_distance + bus2_distance + walk_from, 2),
        "fare": BUS_BASE_FARE,
        "transfers": 1,
        "segments": [
            {
                "mode": "walk",
                "from": {"lat": o_lat, "lng": o_lng, "name": "출발지"},
                "to": {"lat": o_lat, "lng": o_lng, "name": "정류장"},
                "distance_km": round(walk_to, 2),
                "time_min": walk_to_time,
            },
            {
                "mode": "bus",
                "from": {"lat": o_lat, "lng": o_lng, "name": "정류장"},
                "to": {"lat": transfer_lat, "lng": transfer_lng, "name": "환승 정류장"},
                "distance_km": round(bus1_distance, 2),
                "time_min": bus1_time,
            },
            {
                "mode": "bus",
                "from": {"lat": transfer_lat, "lng": transfer_lng, "name": "환승 정류장"},
                "to": {"lat": d_lat, "lng": d_lng, "name": "정류장"},
                "distance_km": round(bus2_distance, 2),
                "time_min": bus2_time,
            },
            {
                "mode": "walk",
                "from": {"lat": d_lat, "lng": d_lng, "name": "정류장"},
                "to": {"lat": d_lat, "lng": d_lng, "name": "도착지"},
                "distance_km": round(walk_from, 2),
                "time_min": walk_from_time,
            },
        ],
        "polyline": [
            [o_lat, o_lng],
            [transfer_lat, transfer_lng],
            [d_lat, d_lng],
        ],
    }
