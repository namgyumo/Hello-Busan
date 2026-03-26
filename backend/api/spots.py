"""
관광지 API 라우터 — API 설계서 API-001, API-002, API-003
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from backend.models.common import SuccessResponse, Meta
from backend.models.spot import SpotResponse, SpotDetail, CategoryItem
from backend.db.supabase import get_supabase
from backend.cache.manager import CacheManager
from backend.services.comfort import ComfortService
from backend.services.location import LocationService
from datetime import datetime
import logging

router = APIRouter(prefix="/api/v1/spots", tags=["spots"])
logger = logging.getLogger(__name__)
cache = CacheManager()
comfort_service = ComfortService()
location_service = LocationService()

CATEGORY_MAP = {
    "nature": {"name": "자연/경관", "icon": "mountain"},
    "culture": {"name": "문화/역사", "icon": "temple"},
    "food": {"name": "맛집/카페", "icon": "restaurant"},
    "activity": {"name": "액티비티", "icon": "sports"},
    "shopping": {"name": "쇼핑", "icon": "bag"},
    "nightview": {"name": "야경", "icon": "moon"},
}


@router.get("")
async def get_spots(
    lat: Optional[float] = Query(None, ge=33.0, le=38.0, description="위도"),
    lng: Optional[float] = Query(None, ge=124.0, le=132.0, description="경도"),
    radius: int = Query(10, ge=1, le=50, description="반경(km)"),
    category: Optional[str] = Query(None, description="카테고리 ID (콤마 구분 복수)"),
    lang: str = Query("ko", description="언어 코드"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """[API-001] 위치 기반 관광지 목록 조회"""
    cache_key = f"spots:{lat}:{lng}:{radius}:{category}:{lang}:{limit}:{offset}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()
        query = sb.table("tourist_spots").select("*").eq("is_active", True)

        if category:
            categories = [c.strip() for c in category.split(",")]
            if len(categories) == 1:
                query = query.eq("category_id", categories[0])
            else:
                query = query.in_("category_id", categories)

        result = query.range(offset, offset + limit - 1).execute()
        spots_data = result.data or []

        # 위치 기반 필터링 + 거리 계산
        if lat and lng:
            spots_data = location_service.filter_by_radius(spots_data, lat, lng, radius)
            spots_data = location_service.sort_by_distance(spots_data, lat, lng)

        # 쾌적함 지수 병합
        spot_ids = [s.get("id") for s in spots_data if s.get("id")]
        comfort_data = await comfort_service.get_bulk_comfort(spot_ids) if spot_ids else {}

        items = []
        for s in spots_data:
            comfort = comfort_data.get(str(s.get("id")), {})
            items.append({
                "id": str(s.get("id", "")),
                "name": s.get("name", ""),
                "category": s.get("category_id", ""),
                "category_name": CATEGORY_MAP.get(s.get("category_id", ""), {}).get("name", ""),
                "lat": s.get("lat", 0),
                "lng": s.get("lng", 0),
                "distance_km": round(s.get("distance_km", 0), 1) if s.get("distance_km") else None,
                "comfort_score": comfort.get("total_score"),
                "comfort_grade": comfort.get("grade"),
                "thumbnail_url": s.get("images", [""])[0] if isinstance(s.get("images"), list) and s.get("images") else "",
                "crowd_level": comfort.get("crowd_level"),
            })

        response = SuccessResponse(
            data=items,
            meta=Meta(
                total=len(items),
                limit=limit,
                offset=offset,
                fallback_used=False,
            ),
        )

        await cache.set(cache_key, response.model_dump(), ttl=300)
        return response

    except Exception as e:
        logger.error(f"관광지 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories(lang: str = Query("ko")):
    """[API-003] 카테고리 목록 조회"""
    try:
        sb = get_supabase()
        result = sb.table("categories").select("*").order("sort_order").execute()

        items = []
        for cat in (result.data or []):
            name_key = f"name_{lang}" if lang != "ko" else "name_ko"
            items.append({
                "id": cat.get("id"),
                "name": cat.get(name_key) or cat.get("name_ko", ""),
                "icon": cat.get("icon", ""),
                "spot_count": 0,
            })

        # spot_count 빈 경우 카테고리 맵에서 폴백
        if not items:
            items = [
                {"id": k, "name": v["name"], "icon": v["icon"], "spot_count": 0}
                for k, v in CATEGORY_MAP.items()
            ]

        return SuccessResponse(data=items)

    except Exception as e:
        logger.error(f"카테고리 조회 실패: {e}")
        # DB 미연결 시 정적 카테고리 반환
        items = [
            {"id": k, "name": v["name"], "icon": v["icon"], "spot_count": 0}
            for k, v in CATEGORY_MAP.items()
        ]
        return SuccessResponse(data=items, meta=Meta(fallback_used=True))


@router.get("/{spot_id}")
async def get_spot_detail(
    spot_id: str,
    lang: str = Query("ko"),
):
    """[API-002] 관광지 상세 정보 조회"""
    cache_key = f"spot_detail:{spot_id}:{lang}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()
        result = sb.table("tourist_spots").select("*").eq("id", spot_id).single().execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

        s = result.data

        # 쾌적함 지수
        comfort = await comfort_service.get_comfort(spot_id)

        # 주변 관광지 (반경 3km)
        all_spots = sb.table("tourist_spots").select("id, name, lat, lng").eq("is_active", True).execute()
        nearby = []
        if all_spots.data:
            for ns in all_spots.data:
                if str(ns["id"]) == spot_id:
                    continue
                dist = location_service.haversine(
                    s.get("lat", 0), s.get("lng", 0),
                    ns.get("lat", 0), ns.get("lng", 0),
                )
                if dist <= 3.0:
                    nearby.append({"id": str(ns["id"]), "name": ns["name"], "distance_km": round(dist, 1)})
            nearby.sort(key=lambda x: x["distance_km"])
            nearby = nearby[:3]

        detail = {
            "id": str(s.get("id", "")),
            "name": s.get("name", ""),
            "category": s.get("category_id", ""),
            "description": s.get("description", ""),
            "images": s.get("images", []) or [],
            "lat": s.get("lat", 0),
            "lng": s.get("lng", 0),
            "address": s.get("address", ""),
            "operating_hours": s.get("operating_hours", ""),
            "admission_fee": s.get("admission_fee", ""),
            "phone": s.get("phone", ""),
            "comfort": comfort.model_dump() if comfort else None,
            "nearby_spots": nearby,
        }

        response = SuccessResponse(data=detail)
        await cache.set(cache_key, response.model_dump(), ttl=120)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관광지 상세 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
