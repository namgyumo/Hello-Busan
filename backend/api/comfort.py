"""
쾌적함 지수 + 히트맵 + 타임라인 API 라우터 — API 설계서 API-005, API-006, API-007
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from backend.models.common import SuccessResponse, Meta
from backend.models.comfort import HeatmapResponse, HeatmapConfig
from backend.services.comfort import ComfortService, COMFORT_WEIGHTS, _get_grade
from backend.cache.manager import CacheManager
from backend.db.supabase import get_supabase
from backend.collector.crowd import (
    HOUR_WEIGHTS, DAY_MULTIPLIER, SEASON_MULTIPLIER, CATEGORY_PEAK,
)
from backend.services.score_calculator import ScoreCalculator
from datetime import datetime
import logging

router = APIRouter(prefix="/api/v1/comfort", tags=["comfort"])
logger = logging.getLogger(__name__)
comfort_service = ComfortService()
cache = CacheManager()
_score_calc = ScoreCalculator()


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
        raise HTTPException(status_code=500, detail="일괄 쾌적함 조회 중 오류 발생")


@router.get("/{spot_id}/timeline")
async def get_comfort_timeline(spot_id: str):
    """시간대별 쾌적도 예측 타임라인 (24시간)"""
    cache_key = f"comfort:timeline:{spot_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()

        # 관광지 정보 (카테고리 + 좌표 필요)
        spot_result = (
            sb.table("tourist_spots")
            .select("id, category_id, lat, lng, region_code")
            .eq("id", spot_id)
            .limit(1)
            .execute()
        )
        if not spot_result.data:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

        spot = spot_result.data[0]
        category = spot.get("category_id", "nature")

        # 교통 점수 (시간에 무관, 고정값)
        transport_map = await _score_calc._get_transport_scores()
        transport_score = transport_map.get(spot_id, {}).get("transit_score", 50)

        # 현재 날씨 데이터 (관광지 위치 기반 가장 가까운 권역 매칭)
        weather_map = await _score_calc._get_latest_weather()
        spot_lat = float(spot.get("lat", 0))
        spot_lng = float(spot.get("lng", 0))
        spot_region = spot.get("region_code")
        region = spot_region if spot_region in weather_map else _score_calc._find_nearest_region(spot_lat, spot_lng)
        weather_score = _score_calc._calc_weather_score(weather_map.get(region, {}))

        # spot_id 기반 결정적 오프셋 (crowd.py와 동일 로직)
        spot_hash = hash(str(spot_id)) % 1000 / 1000.0
        spot_offset = (spot_hash - 0.5) * 0.3

        now = datetime.now()
        weekday = now.weekday()
        month = now.month
        current_hour = now.hour

        day_mult = DAY_MULTIPLIER.get(weekday, 1.0)
        season_mult = SEASON_MULTIPLIER.get(month, 1.0)
        cat_info = CATEGORY_PEAK.get(category, {})

        timeline = []
        for hour in range(24):
            # 혼잡도 계산 (crowd.py의 _estimate_crowd 로직 재현)
            base = HOUR_WEIGHTS.get(hour, 0.5)
            cat_mult = 1.0
            if hour in cat_info.get("peak_hours", []):
                cat_mult = cat_info.get("multiplier", 1.0)

            crowd_level = base * day_mult * season_mult * cat_mult + spot_offset
            crowd_level = max(0.0, min(1.0, crowd_level))

            # crowd_level -> crowd_score (0=혼잡, 100=여유)
            crowd_ratio = crowd_level * 100
            crowd_score = int(max(0, 100 - crowd_ratio))

            # 종합 쾌적도
            comfort_score = ComfortService.calc_comfort_score(
                weather_score=weather_score,
                crowd_score=crowd_score,
                transport_score=transport_score,
            )

            # 혼잡도 등급 텍스트
            if crowd_level < 0.3:
                level_text = "여유"
            elif crowd_level < 0.6:
                level_text = "보통"
            elif crowd_level < 0.8:
                level_text = "혼잡"
            else:
                level_text = "매우혼잡"

            timeline.append({
                "hour": hour,
                "comfort_score": comfort_score,
                "crowd_level": level_text,
                "weather_factor": weather_score,
            })

        response = SuccessResponse(data={
            "spot_id": spot_id,
            "current_hour": current_hour,
            "timeline": timeline,
        })
        await cache.set(cache_key, response.model_dump(), ttl=300)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"타임라인 조회 실패 [{spot_id}]: {e}")
        raise HTTPException(status_code=500, detail="타임라인 조회 중 오류 발생")


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
        raise HTTPException(status_code=500, detail="쾌적함 조회 중 오류 발생")
