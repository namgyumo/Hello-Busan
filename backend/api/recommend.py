"""
추천 API 라우터 — API 설계서 API-004
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
from backend.models.common import SuccessResponse, Meta
from backend.ml.model import RecommendModel
from backend.ml.features import FeatureBuilder
from backend.ml.fallback import FallbackRecommender, CATEGORY_META
from backend.services.comfort import ComfortService
from backend.services.location import LocationService
from backend.cache.manager import CacheManager
from backend.db.supabase import get_supabase
from backend.services.i18n import I18nService
from backend.services.user_profile import UserProfileBuilder
from backend.api.weather import _determine_condition
import logging

router = APIRouter(prefix="/api/v1/recommend", tags=["recommend"])
logger = logging.getLogger(__name__)
cache = CacheManager()


def _sanitize_keyword(raw: str) -> str:
    """PostgREST or_ 필터에 안전하게 사용할 수 있도록 특수문자 제거"""
    kw = raw.strip()
    for ch in ("%", "\\", ",", "(", ")"):
        kw = kw.replace(ch, "")
    return kw


model = RecommendModel()
feature_builder = FeatureBuilder()
fallback = FallbackRecommender()
comfort_service = ComfortService()
location_service = LocationService()
i18n_service = I18nService()
profile_builder = UserProfileBuilder()

# 개인화 적용 최소 이벤트 수
_MIN_EVENTS_FOR_PERSONALIZATION = 10


async def _fetch_weather_context() -> Dict:
    """현재 날씨 condition + 시간/요일 정보를 컨텍스트로 반환"""
    kst = datetime.now(timezone(timedelta(hours=9)))
    context = {
        "weather": "clear_cool",
        "hour": kst.hour,
        "is_weekend": kst.weekday() >= 5,
    }
    try:
        sb = get_supabase()
        since = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        result = (
            sb.table("weather_data")
            .select("sky_code, rain_type, temperature")
            .gte("timestamp", since)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            row = result.data[0]
            sky_code = str(row.get("sky_code") or "1")
            rain_type = row.get("rain_type") or "없음"
            temperature = row.get("temperature") if row.get("temperature") is not None else 20
            context["weather"] = _determine_condition(sky_code, rain_type, temperature)
    except Exception as e:
        logger.warning(f"날씨 컨텍스트 조회 실패, 기본값 사용: {e}")
    return context


def _get_experiment_bucket(session_id: Optional[str]) -> str:
    """세션 ID의 마지막 hex digit으로 A/B 버킷 분류.
    0-7: A (기본 Fallback), 8-f: B (컨텍스트 강화 Fallback)"""
    if not session_id:
        return "A"
    last_char = session_id.strip()[-1].lower()
    try:
        return "B" if int(last_char, 16) >= 8 else "A"
    except ValueError:
        return "A"


@router.get("")
async def get_recommendations(
    lat: Optional[float] = Query(None, ge=33.0, le=38.0),
    lng: Optional[float] = Query(None, ge=124.0, le=132.0),
    categories: Optional[str] = Query(None, description="카테고리 ID (콤마 구분)"),
    search: Optional[str] = Query(None, description="검색어 (이름/주소)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    lang: str = Query("ko"),
    session_id: Optional[str] = Query(None, description="세션 ID (A/B 실험 + 개인화 추천)"),
):
    """[API-004] XGBoost 기반 관광지 추천"""
    experiment_bucket = _get_experiment_bucket(session_id)
    cache_key = f"recommend:{lat}:{lng}:{categories}:{search}:{limit}:{offset}:{lang}:{experiment_bucket}:{session_id or ''}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    fallback_used = False
    model_type = "xgboost"
    personalized = False

    # 사용자 프로필 조회 (session_id가 있을 때)
    user_profile = None
    if session_id:
        try:
            user_profile = await profile_builder.build_from_session(session_id)
            if user_profile and user_profile["session_event_count"] >= _MIN_EVENTS_FOR_PERSONALIZATION:
                personalized = True
            else:
                user_profile = None
        except Exception as e:
            logger.warning(f"사용자 프로필 조회 실패: {e}")
            user_profile = None

    try:
        sb = get_supabase()
        query = sb.table("tourist_spots").select("*").eq("is_active", True)

        if categories:
            cat_list = [c.strip() for c in categories.split(",")]
            if len(cat_list) == 1:
                query = query.eq("category_id", cat_list[0])
            else:
                query = query.in_("category_id", cat_list)

        if search and search.strip():
            keyword = _sanitize_keyword(search)
            if keyword:
                or_filter = f"(name.ilike.%{keyword}%,address.ilike.%{keyword}%,description.ilike.%{keyword}%)"
                query.params = query.params.add("or", or_filter)

        # Supabase 기본 1000행 제한 우회: 페이지네이션으로 전체 조회
        all_spots = []
        page_size = 1000
        page_offset = 0
        while True:
            page_result = query.range(page_offset, page_offset + page_size - 1).execute()
            page_data = page_result.data or []
            all_spots.extend(page_data)
            if len(page_data) < page_size:
                break
            page_offset += page_size
        spots = all_spots

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

        # 날씨/시간 컨텍스트 조회
        weather_context = await _fetch_weather_context()

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
                    context=weather_context,
                )
                scored_spots = [(s, 0.5) for s in top_list]
        else:
            fallback_used = True
            model_type = "fallback"
            top_list = fallback.recommend(
                spots=spots, user_lat=lat, user_lng=lng,
                comfort_data=comfort_data, limit=len(spots),
                context=weather_context,
            )
            scored_spots = [(s, 0.5) for s in top_list]

        # 개인화 가중치 적용
        if personalized and user_profile:
            scored_spots = _apply_personalization(scored_spots, user_profile)

        total_count = len(scored_spots)
        top_spots = scored_spots[offset:offset + limit]

        # 응답 조립
        items = []
        for rank, (s, score) in enumerate(top_spots, offset + 1):
            comfort = comfort_data.get(str(s.get("id")), {})
            reasons = _build_reasons(s, comfort, lang, weather_context)

            raw_images = s.get("images", []) if isinstance(s.get("images"), list) else []
            thumbnail = raw_images[0] if raw_images else ""

            items.append({
                "rank": rank,
                "id": str(s.get("id", "")),
                "name": s.get("name", ""),
                "category": s.get("category_id", ""),
                "address": s.get("address", ""),
                "recommend_score": round(float(score), 2),
                "comfort_score": comfort.get("total_score"),
                "comfort_grade": comfort.get("grade"),
                "lat": s.get("lat"),
                "lng": s.get("lng"),
                "distance_km": round(s.get("distance_km", 0), 1) if s.get("distance_km") else None,
                "reasons": reasons,
                "thumbnail_url": thumbnail,
                "images": raw_images,
            })

        response = SuccessResponse(
            data=items,
            meta=Meta(
                total=total_count,
                limit=limit,
                offset=offset,
                fallback_used=fallback_used,
                personalized=personalized,
                experiment_bucket=experiment_bucket,
            ),
        )

        await cache.set(cache_key, response.model_dump(), ttl=180)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"추천 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="추천 생성 중 오류 발생")


def _build_reasons(
    spot: dict, comfort: dict, lang: str = "ko",
    context: Optional[Dict] = None,
) -> list:
    """추천 이유 문자열 생성 (다국어 지원 + 컨텍스트 기반)"""
    reasons = []
    crowd_score = comfort.get("crowd_score")
    if crowd_score is not None and crowd_score >= 80:
        reasons.append(i18n_service.translate("reason_low_crowd", lang))
    if spot.get("distance_km") and spot["distance_km"] < 3:
        reasons.append(i18n_service.translate("reason_nearby", lang))

    # 컨텍스트 기반 추천 사유
    if context:
        category = spot.get("category_id", "")
        weather = context.get("weather", "")
        hour = context.get("hour", 12)
        meta = CATEGORY_META.get(category, {})
        is_indoor = meta.get("is_indoor", False)

        if weather == "rain" and is_indoor:
            reasons.append("비 오는 날 실내 관광지" if lang == "ko" else "Indoor spot for rainy weather")
        if weather == "clear_hot" and is_indoor:
            reasons.append("더운 날 시원한 실내 명소" if lang == "ko" else "Cool indoor spot for hot weather")
        if (18 <= hour or hour < 5) and category == "nightview":
            reasons.append("저녁 시간 야경 명소" if lang == "ko" else "Night view spot for evening")
        if (11 <= hour <= 13 or 17 <= hour <= 19) and category == "food":
            reasons.append("식사 시간 맛집 추천" if lang == "ko" else "Restaurant recommendation for mealtime")
        if 6 <= hour < 11 and category in ("nature", "temple"):
            reasons.append("상쾌한 오전 산책 명소" if lang == "ko" else "Refreshing morning walk spot")
        if context.get("is_weekend") and category in ("nature", "activity"):
            reasons.append("주말 나들이 추천" if lang == "ko" else "Weekend outing recommendation")

    return reasons


def _apply_personalization(
    scored_spots: list[tuple[dict, float]],
    profile: dict,
) -> list[tuple[dict, float]]:
    """사용자 프로필 기반 추천 점수 재조정

    - 카테고리 선호도에 따라 해당 카테고리 관광지 부스트
    - 이미 상세 조회한 관광지는 순위 하향 (다양성 확보)
    """
    cat_prefs = profile.get("category_preferences", {})
    viewed_ids = set(profile.get("viewed_spot_ids", []))

    adjusted = []
    for spot, score in scored_spots:
        new_score = float(score)
        spot_id = spot.get("id")
        category = spot.get("category_id", "")

        # 카테고리 선호도 부스트 (최대 +30%)
        if category in cat_prefs:
            boost = cat_prefs[category] * 0.3
            new_score *= (1.0 + boost)

        # 이미 상세 조회한 관광지 하향 (다양성 확보, -40%)
        if spot_id in viewed_ids:
            new_score *= 0.6

        adjusted.append((spot, new_score))

    adjusted.sort(key=lambda x: x[1], reverse=True)
    return adjusted
