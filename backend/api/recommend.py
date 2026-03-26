"""
AI 추천 API 라우터
- 개인화 추천 (위치 + 선호도 기반)
- 실시간 혼잡도 반영 추천
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from backend.ml.model import RecommendModel
from backend.ml.features import FeatureBuilder
from backend.ml.fallback import FallbackRecommender
from backend.models.spot import SpotResponse
from backend.cache.manager import CacheManager
from backend.services.comfort import ComfortService
from backend.db.supabase import get_supabase
import logging

router = APIRouter(prefix="/api/v1/recommend", tags=["recommend"])
logger = logging.getLogger(__name__)
cache = CacheManager()
model = RecommendModel()
feature_builder = FeatureBuilder()
fallback = FallbackRecommender()
comfort_service = ComfortService()


@router.get("", response_model=List[SpotResponse])
async def get_recommendations(
    lat: Optional[float] = Query(None, description="사용자 위도"),
    lng: Optional[float] = Query(None, description="사용자 경도"),
    category: Optional[str] = Query(None, description="선호 카테고리"),
    limit: int = Query(10, ge=1, le=50, description="추천 개수"),
):
    """
    AI 기반 관광지 추천
    - XGBoost 모델로 점수 예측
    - 실시간 혼잡도 반영
    - 모델 미로드 시 폴백 추천
    """
    cache_key = f"recommend:{lat}:{lng}:{category}:{limit}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()
        query = sb.table("spots").select("*")
        if category:
            query = query.eq("category", category)
        spots_result = query.execute()

        if not spots_result.data:
            return []

        spots = spots_result.data

        # 혼잡도 정보 조회
        comfort_data = await comfort_service.get_bulk_comfort(
            [s["id"] for s in spots]
        )

        # 모델이 로드되었으면 ML 추천
        if model.is_loaded:
            features = feature_builder.build_batch(
                spots=spots,
                user_lat=lat,
                user_lng=lng,
                comfort_data=comfort_data,
            )
            scores = model.predict(features)

            scored_spots = list(zip(spots, scores))
            scored_spots.sort(key=lambda x: x[1], reverse=True)
            top_spots = [s for s, _ in scored_spots[:limit]]
        else:
            logger.warning("ML 모델 미로드 - 폴백 추천 사용")
            top_spots = fallback.recommend(
                spots=spots,
                user_lat=lat,
                user_lng=lng,
                comfort_data=comfort_data,
                limit=limit,
            )

        response = [SpotResponse(**s) for s in top_spots]
        await cache.set(cache_key, [r.dict() for r in response], ttl=180)
        return response

    except Exception as e:
        logger.error(f"추천 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="추천 생성 중 오류 발생")


@router.get("/popular")
async def get_popular_spots(
    limit: int = Query(10, ge=1, le=50),
):
    """인기 관광지 (조회수 기반 폴백)"""
    cache_key = f"popular:{limit}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    sb = get_supabase()
    result = (
        sb.table("spots")
        .select("*")
        .order("view_count", desc=True)
        .limit(limit)
        .execute()
    )

    response = [SpotResponse(**s) for s in result.data]
    await cache.set(cache_key, [r.dict() for r in response], ttl=600)
    return response
