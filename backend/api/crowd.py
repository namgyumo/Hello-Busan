"""
혼잡도 트렌드 API 라우터
- GET /api/v1/crowd/{spot_id}/trend — 시간대별 혼잡도 트렌드
- GET /api/v1/crowd/{spot_id}/weekly — 요일별 혼잡도 패턴
"""
from fastapi import APIRouter, HTTPException
from backend.models.common import SuccessResponse
from backend.services.crowd_trend import CrowdTrendService
from backend.cache.manager import CacheManager
import logging

router = APIRouter(prefix="/api/v1/crowd", tags=["crowd-trend"])
logger = logging.getLogger(__name__)
trend_service = CrowdTrendService()
cache = CacheManager()


@router.get("/{spot_id}/trend")
async def get_crowd_trend(spot_id: str):
    """시간대별(0~23시) 혼잡도 트렌드"""
    cache_key = f"crowd:trend:{spot_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        result = trend_service.get_hourly_trend(spot_id)
        if not result:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

        response = SuccessResponse(data=result)
        await cache.set(cache_key, response.model_dump(), ttl=300)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"혼잡도 트렌드 조회 실패 [{spot_id}]: {e}")
        raise HTTPException(status_code=500, detail="혼잡도 트렌드 조회 중 오류 발생")


@router.get("/{spot_id}/weekly")
async def get_crowd_weekly(spot_id: str):
    """요일별(월~일) 혼잡도 패턴"""
    cache_key = f"crowd:weekly:{spot_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        result = trend_service.get_weekly_pattern(spot_id)
        if not result:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

        response = SuccessResponse(data=result)
        await cache.set(cache_key, response.model_dump(), ttl=300)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"요일별 혼잡도 조회 실패 [{spot_id}]: {e}")
        raise HTTPException(status_code=500, detail="요일별 혼잡도 조회 중 오류 발생")
