"""
코스 추천 API 라우터 — 코스 생성/동선 플래너
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from backend.models.common import SuccessResponse, Meta
from backend.services.comfort import ComfortService
from backend.services.location import LocationService
from backend.db.supabase import get_supabase
from backend.cache.manager import CacheManager
import logging
import random

router = APIRouter(prefix="/api/v1/course", tags=["course"])
logger = logging.getLogger(__name__)
cache = CacheManager()
comfort_service = ComfortService()
location_service = LocationService()

# 카테고리별 평균 체류 시간 (분)
STAY_MINUTES = {
    "nature": 60,
    "culture": 50,
    "food": 45,
    "activity": 70,
    "shopping": 40,
    "nightview": 40,
}
DEFAULT_STAY = 50
# 평균 도보+대중교통 이동 속도 (km/h)
TRAVEL_SPEED_KMH = 15.0


@router.get("/generate")
async def generate_course(
    duration: str = Query("half", description="반나절(half) 또는 하루(full)"),
    start_lat: Optional[float] = Query(None, ge=33.0, le=38.0),
    start_lng: Optional[float] = Query(None, ge=124.0, le=132.0),
    categories: Optional[str] = Query(None, description="선호 카테고리 (콤마 구분)"),
    max_spots: int = Query(5, ge=2, le=10),
    lang: str = Query("ko"),
):
    """코스 추천 생성 — 조건 필터 + 쾌적도 가중 선택 + Nearest Neighbor TSP"""
    # 시간 예산 (분)
    if duration == "full":
        time_budget = 420  # 7시간
    else:
        time_budget = 210  # 3.5시간

    # 출발지 기본값: 부산역
    if start_lat is None:
        start_lat = 35.1152
    if start_lng is None:
        start_lng = 129.0403

    cache_key = f"course:{duration}:{start_lat}:{start_lng}:{categories}:{max_spots}:{lang}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()
        query = sb.table("tourist_spots").select("*").eq("is_active", True)

        if categories:
            cat_list = [c.strip() for c in categories.split(",")]
            if len(cat_list) == 1:
                query = query.eq("category_id", cat_list[0])
            else:
                query = query.in_("category_id", cat_list)

        spots_result = query.execute()
        spots = spots_result.data or []

        if not spots:
            return SuccessResponse(
                data={"course": [], "total_distance": 0, "total_time": 0},
                meta=Meta(total=0),
            )

        # 쾌적도 조회
        spot_ids = [str(s.get("id")) for s in spots]
        comfort_data = await comfort_service.get_bulk_comfort(spot_ids)

        # 거리 계산 (출발지 기준)
        for s in spots:
            s["distance_km"] = location_service.haversine(
                start_lat, start_lng, s.get("lat", 0), s.get("lng", 0)
            )
            comfort = comfort_data.get(str(s.get("id")), {})
            s["comfort_score"] = comfort.get("total_score", 50)

        # 후보 필터링: 출발지에서 너무 먼 곳 제외 (20km 이내)
        candidates = [s for s in spots if s["distance_km"] <= 20.0]

        if len(candidates) < 2:
            candidates = spots[:max_spots]

        # 쾌적도 가중 선택
        selected = _weighted_select(candidates, max_spots)

        if not selected:
            return SuccessResponse(
                data={"course": [], "total_distance": 0, "total_time": 0},
                meta=Meta(total=0),
            )

        # Nearest Neighbor TSP
        ordered = _nearest_neighbor_tsp(selected, start_lat, start_lng)

        # 코스 조립 + 시간 계산
        course = []
        total_distance = 0.0
        total_time = 0
        prev_lat, prev_lng = start_lat, start_lng

        for idx, spot in enumerate(ordered):
            dist = location_service.haversine(
                prev_lat, prev_lng,
                spot.get("lat", 0), spot.get("lng", 0),
            )
            travel_min = round((dist / TRAVEL_SPEED_KMH) * 60)
            stay_min = STAY_MINUTES.get(spot.get("category_id", ""), DEFAULT_STAY)

            total_distance += dist
            total_time += travel_min + stay_min

            # 시간 예산 초과 시 더 이상 추가하지 않음
            if total_time > time_budget and idx > 0:
                total_time -= (travel_min + stay_min)
                total_distance -= dist
                break

            comfort = comfort_data.get(str(spot.get("id")), {})
            course.append({
                "order": idx + 1,
                "spot": {
                    "id": str(spot.get("id", "")),
                    "name": spot.get("name", ""),
                    "category": spot.get("category_id", ""),
                    "lat": spot.get("lat"),
                    "lng": spot.get("lng"),
                    "comfort_score": comfort.get("total_score"),
                    "comfort_grade": comfort.get("grade"),
                    "thumbnail_url": (
                        spot.get("images", [""])[0]
                        if isinstance(spot.get("images"), list) and spot.get("images")
                        else ""
                    ),
                },
                "distance_from_prev": round(dist, 2),
                "travel_time": travel_min,
                "stay_time": stay_min,
                "estimated_time": travel_min + stay_min,
            })

            prev_lat = spot.get("lat", 0)
            prev_lng = spot.get("lng", 0)

        response = SuccessResponse(
            data={
                "course": course,
                "total_distance": round(total_distance, 2),
                "total_time": total_time,
                "duration": duration,
                "start_lat": start_lat,
                "start_lng": start_lng,
            },
            meta=Meta(total=len(course)),
        )

        await cache.set(cache_key, response.model_dump(), ttl=120)
        return response

    except Exception as e:
        logger.error(f"코스 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="코스 생성 중 오류 발생")


def _weighted_select(candidates: list, max_spots: int) -> list:
    """쾌적도 점수 가중 랜덤 선택"""
    if len(candidates) <= max_spots:
        return candidates

    # 가중치: comfort_score + 거리 보정 (가까울수록 보너스)
    weights = []
    for s in candidates:
        comfort = s.get("comfort_score", 50)
        dist_bonus = max(0, 10 - s.get("distance_km", 10))
        weights.append(max(comfort + dist_bonus, 1))

    selected = []
    remaining = list(range(len(candidates)))
    remaining_weights = list(weights)

    for _ in range(max_spots):
        if not remaining:
            break
        chosen_idx = random.choices(
            range(len(remaining)), weights=remaining_weights, k=1
        )[0]
        selected.append(candidates[remaining[chosen_idx]])
        remaining.pop(chosen_idx)
        remaining_weights.pop(chosen_idx)

    return selected


def _nearest_neighbor_tsp(spots: list, start_lat: float, start_lng: float) -> list:
    """Nearest Neighbor 기반 방문 순서 최적화"""
    if len(spots) <= 1:
        return spots

    unvisited = list(spots)
    ordered = []
    current_lat, current_lng = start_lat, start_lng

    while unvisited:
        nearest = min(
            unvisited,
            key=lambda s: LocationService.haversine(
                current_lat, current_lng,
                s.get("lat", 0), s.get("lng", 0),
            ),
        )
        ordered.append(nearest)
        current_lat = nearest.get("lat", 0)
        current_lng = nearest.get("lng", 0)
        unvisited.remove(nearest)

    return ordered
