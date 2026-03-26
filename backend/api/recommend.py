"""
추천 API 라우터 — API 설계서 API-004
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from backend.models.common import SuccessResponse, Meta
from backend.ml.model import RecommendModel
from backend.ml.features import FeatureBuilder
from backend.ml.fallback import FallbackRecommender
from backend.services.comfort import ComfortService
from backend.services.location import LocationService
from backend.cache.manager import CacheManager
from backend.db.supabase import get_supabase
import logging

router = APIRouter(prefix="/api/v1/recommend", tags=["recommend"])
logger = logging.getLogger(__name__)
cache = CacheManager()
model = RecommendModel()
feature_builder = FeatureBuilder()
fallback = FallbackRecommender()
comfort_service = ComfortService()
location_service = LocationService()


@router.get("")
async def get_recommendations(
    lat: Optional[float] = Query(None, ge=33.0, le=38.0),
    lng: Optional[float] = Query(None, ge=124.0, le=132.0),
    categories: Optional[str] = Query(None, description="카테고리 ID (콤마 구분)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    lang: str = Query("ko"),
):
    """[API-004] XGBoost 기반 관광지 추천"""
    cache_key = f"recommend:{lat}:{lng}:{categories}:{limit}:{offset}:{lang}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    fallback_used = False
    model_type = "xgboost"

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
                data=[],
                meta=Meta(total=0, fallback_used=False),
            )

        # 쾌적함 지수 조회
        spot_ids = [str(s.get("id")) for s in spots]
        comfort_data = await comfort_service.get_bulk_comfort(spot_ids)

        # 거리 계산
        if lat and lng:
            for s in spots:
                s["distance_km"] = location_service.haversine(
                    lat, lng, s.get("lat", 0), s.get("lng", 0)
                )

        # ML 모델 또는 폴백 — 전체 스코어링 후 offset/limit 적용
        if model.is_loaded:
            try:
                features = feature_builder.build_batch(
                    spots=spots,
                    user_lat=lat,
                    user_lng=lng,
                    comfort_data=comfort_data,
                )
                scores = model.predict(features)
                scored_spots = list(zip(spots, scores))
                scored_spots.sort(key=lambda x: x[1], reverse=True)
            except Exception as e:
                logger.warning(f"ML 예측 실패, 폴백 사용: {e}")
                fallback_used = True
                model_type = "fallback"
                top_list = fallback.recommend(
                    spots=spots, user_lat=lat, user_lng=lng,
                    comfort_data=comfort_data, limit=len(spots),
                )
                scored_spots = [(s, 0.5) for s in top_list]
        else:
            fallback_used = True
            model_type = "fallback"
            top_list = fallback.recommend(
                spots=spots, user_lat=lat, user_lng=lng,
                comfort_data=comfort_data, limit=len(spots),
            )
            scored_spots = [(s, 0.5) for s in top_list]

        total_count = len(scored_spots)
        top_spots = scored_spots[offset:offset + limit]

        # 응답 조립
        items = []
        for rank, (s, score) in enumerate(top_spots, offset + 1):
            comfort = comfort_data.get(str(s.get("id")), {})
            reasons = _build_reasons(s, comfort)

            items.append({
                "rank": rank,
                "id": str(s.get("id", "")),
                "name": s.get("name", ""),
                "category": s.get("category_id", ""),
                "recommend_score": round(float(score), 2),
                "comfort_score": comfort.get("total_score"),
                "comfort_grade": comfort.get("grade"),
                "lat": s.get("lat"),
                "lng": s.get("lng"),
                "distance_km": round(s.get("distance_km", 0), 1) if s.get("distance_km") else None,
                "reasons": reasons,
                "thumbnail_url": s.get("images", [""])[0] if isinstance(s.get("images"), list) and s.get("images") else "",
            })

        response = SuccessResponse(
            data=items,
            meta=Meta(
                total=total_count,
                limit=limit,
                offset=offset,
                fallback_used=fallback_used,
            ),
        )

        await cache.set(cache_key, response.model_dump(), ttl=180)
        return response

    except Exception as e:
        logger.error(f"추천 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="추천 생성 중 오류 발생")


def _build_reasons(spot: dict, comfort: dict) -> list:
    """추천 이유 문자열 생성"""
    reasons = []
    grade = comfort.get("grade", "")
    if grade in ("쾌적",):
        reasons.append("혼잡도 낮음")
    if spot.get("distance_km") and spot["distance_km"] < 3:
        reasons.append("가까운 거리")
    return reasons
