"""
쾌적함 지수 + 히트맵 API 라우터 — API 설계서 API-005, API-006, API-007
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from backend.models.common import SuccessResponse, Meta
from backend.models.comfort import HeatmapResponse, HeatmapConfig
from backend.services.comfort import ComfortService
from backend.cache.manager import CacheManager
from backend.db.supabase import get_supabase
import logging

router = APIRouter(prefix="/api/v1/comfort", tags=["comfort"])
logger = logging.getLogger(__name__)
comfort_service = ComfortService()
cache = CacheManager()


@router.get("/bulk")
async def get_comfort_bulk():
    """[API-006] 복수 관광지 쾌적함 지수 일괄 조회"""
    cache_key = "comfort:bulk"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()
        spots = sb.table("tourist_spots").select("id, lat, lng").eq("is_active", True).execute()

        spot_ids = [str(s["id"]) for s in (spots.data or [])]
        comfort_data = await comfort_service.get_bulk_comfort(spot_ids)

        items = []
        for s in (spots.data or []):
            sid = str(s["id"])
            c = comfort_data.get(sid, {})
            items.append({
                "spot_id": sid,
                "score": c.get("total_score", 0),
                "grade": c.get("grade", "보통"),
                "lat": s["lat"],
                "lng": s["lng"],
            })

        response = SuccessResponse(
            data=items,
            meta=Meta(total=len(items)),
        )
        await cache.set(cache_key, response.model_dump(), ttl=60)
        return response

    except Exception as e:
        logger.error(f"일괄 쾌적함 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{spot_id}")
async def get_comfort(spot_id: str, lang: str = Query("ko")):
    """[API-005] 관광지별 쾌적함 지수 조회"""
    cache_key = f"comfort:{spot_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        result = await comfort_service.get_comfort(spot_id)
        if not result:
            raise HTTPException(status_code=404, detail="쾌적함 정보를 찾을 수 없습니다")

        response = SuccessResponse(data=result.model_dump())
        await cache.set(cache_key, response.model_dump(), ttl=60)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"쾌적함 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
