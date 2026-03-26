"""
관광지 CRUD API 라우터
- 관광지 목록 조회 (카테고리/키워드 필터)
- 관광지 상세 조회
- 관광지 검색
"""
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List
from backend.models.spot import SpotResponse, SpotDetail, SpotListResponse
from backend.db.supabase import get_supabase
from backend.cache.manager import CacheManager

router = APIRouter(prefix="/api/v1/spots", tags=["spots"])
cache = CacheManager()

CATEGORIES = ["nature", "culture", "food", "activity", "nightlife"]


@router.get("", response_model=SpotListResponse)
async def get_spots(
    category: Optional[str] = Query(None, description="카테고리 필터"),
    keyword: Optional[str] = Query(None, description="검색 키워드"),
    lat: Optional[float] = Query(None, description="사용자 위도"),
    lng: Optional[float] = Query(None, description="사용자 경도"),
    radius: Optional[float] = Query(5.0, description="검색 반경(km)"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """관광지 목록 조회 + 필터링"""
    cache_key = f"spots:{category}:{keyword}:{lat}:{lng}:{radius}:{page}:{size}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    sb = get_supabase()
    query = sb.table("spots").select("*")

    if category and category in CATEGORIES:
        query = query.eq("category", category)
    if keyword:
        query = query.or_(
            f"name.ilike.%{keyword}%,description.ilike.%{keyword}%"
        )

    # 위치 기반 필터링 (PostGIS 사용 시)
    if lat and lng:
        query = query.rpc(
            "nearby_spots",
            {"lat": lat, "lng": lng, "radius_km": radius},
        )

    offset = (page - 1) * size
    result = query.range(offset, offset + size - 1).execute()

    total_query = sb.table("spots").select("*", count="exact")
    if category and category in CATEGORIES:
        total_query = total_query.eq("category", category)
    total_result = total_query.execute()

    response = SpotListResponse(
        spots=[SpotResponse(**s) for s in result.data],
        total=total_result.count or len(result.data),
        page=page,
        size=size,
    )
    await cache.set(cache_key, response.dict(), ttl=300)
    return response


@router.get("/categories")
async def get_categories():
    """사용 가능한 카테고리 목록"""
    return {"categories": CATEGORIES}


@router.get("/{spot_id}", response_model=SpotDetail)
async def get_spot_detail(spot_id: str):
    """관광지 상세 정보"""
    cache_key = f"spot:{spot_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    sb = get_supabase()
    result = sb.table("spots").select("*").eq("id", spot_id).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

    # 혼잡도 정보 병합
    comfort_result = (
        sb.table("comfort_index")
        .select("*")
        .eq("spot_id", spot_id)
        .order("measured_at", desc=True)
        .limit(1)
        .execute()
    )

    spot_data = result.data
    if comfort_result.data:
        spot_data["comfort"] = comfort_result.data[0]

    response = SpotDetail(**spot_data)
    await cache.set(cache_key, response.dict(), ttl=120)
    return response


@router.get("/search/suggest")
async def search_suggest(
    q: str = Query(..., min_length=1, description="검색어"),
):
    """검색어 자동완성"""
    sb = get_supabase()
    result = (
        sb.table("spots")
        .select("id, name, category")
        .ilike("name", f"%{q}%")
        .limit(10)
        .execute()
    )
    return {"suggestions": result.data}
