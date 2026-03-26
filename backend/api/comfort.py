"""
쾌적도 API 라우터
- 관광지별 실시간 쾌적도 조회
- 전체 쾌적도 대시보드 데이터
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from backend.services.comfort import ComfortService
from backend.cache.manager import CacheManager
from backend.models.comfort import ComfortResponse, ComfortDashboard

router = APIRouter(prefix="/api/v1/comfort", tags=["comfort"])
comfort_service = ComfortService()
cache = CacheManager()


@router.get("/{spot_id}", response_model=ComfortResponse)
async def get_comfort(spot_id: str):
    """특정 관광지의 실시간 쾌적도"""
    cache_key = f"comfort:{spot_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await comfort_service.get_comfort(spot_id)
    if not result:
        raise HTTPException(status_code=404, detail="쾌적도 정보 없음")

    await cache.set(cache_key, result.dict(), ttl=60)
    return result


@router.get("", response_model=ComfortDashboard)
async def get_comfort_dashboard(
    category: Optional[str] = Query(None),
):
    """전체 쾌적도 대시보드"""
    cache_key = f"comfort_dashboard:{category}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await comfort_service.get_dashboard(category=category)
    await cache.set(cache_key, result.dict(), ttl=60)
    return result


@router.get("/{spot_id}/history")
async def get_comfort_history(
    spot_id: str,
    hours: int = Query(24, ge=1, le=168, description="조회 시간 범위"),
):
    """쾌적도 히스토리 (차트용)"""
    cache_key = f"comfort_history:{spot_id}:{hours}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await comfort_service.get_history(spot_id, hours=hours)
    await cache.set(cache_key, result, ttl=120)
    return {"spot_id": spot_id, "history": result}
