"""
관광지 API 라우터 — API 설계서 API-001, API-002, API-003
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from backend.models.common import SuccessResponse, Meta
from backend.models.spot import SpotResponse, SpotDetail, CategoryItem
from backend.db.supabase import get_supabase
from backend.cache.manager import CacheManager
from backend.services.comfort import ComfortService
from backend.services.location import LocationService
from backend.collector.tourism import TourismCollector
from backend.ml.similarity import SimilarityEngine
from datetime import datetime
import logging

router = APIRouter(prefix="/api/v1/spots", tags=["spots"])
logger = logging.getLogger(__name__)
cache = CacheManager()
comfort_service = ComfortService()
location_service = LocationService()
similarity_engine = SimilarityEngine()


def _sanitize_keyword(raw: str) -> str:
    """PostgREST or_ 필터에 안전하게 사용할 수 있도록 특수문자 제거"""
    kw = raw.strip()
    # PostgREST 필터 구분자 및 와일드카드 제거
    for ch in ("%", "\\", ",", "(", ")"):
        kw = kw.replace(ch, "")
    return kw


def _search_rank(spot: dict, kw_lower: str) -> int:
    """검색 매칭 우선순위: 제목(0) > 주소(1) > 설명(2)"""
    if kw_lower in (spot.get("name") or "").lower():
        return 0
    if kw_lower in (spot.get("address") or "").lower():
        return 1
    return 2


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
    search: Optional[str] = Query(None, description="검색어 (이름/주소)"),
    lang: str = Query("ko", description="언어 코드"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """[API-001] 위치 기반 관광지 목록 조회"""
    # lat/lng 중 하나만 제공된 경우 에러 반환 (DB 쿼리 전에 검증)
    if (lat is not None) != (lng is not None):
        raise HTTPException(
            status_code=400,
            detail="lat과 lng는 함께 제공해야 합니다",
        )

    cache_key = f"spots:{lat}:{lng}:{radius}:{category}:{search}:{lang}:{limit}:{offset}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()

        # 실제 데이터 조회 (검색 시 Python 측 필터링 — Supabase .or_() 버그 회피)
        query = sb.table("tourist_spots").select("*").eq("is_active", True)

        if category:
            categories = [c.strip() for c in category.split(",")]
            if len(categories) == 1:
                query = query.eq("category_id", categories[0])
            else:
                query = query.in_("category_id", categories)

        # 검색어가 있으면 전체 조회 후 Python 필터링, 없으면 기존 로직
        keyword = ""
        if search and search.strip():
            keyword = _sanitize_keyword(search)

        if lat and lng:
            # Supabase 기본 1000행 제한 우회: 페이지네이션으로 전체 조회
            spots_data = []
            _page_size = 1000
            _page_offset = 0
            while True:
                _page_result = query.range(_page_offset, _page_offset + _page_size - 1).execute()
                _page_data = _page_result.data or []
                spots_data.extend(_page_data)
                if len(_page_data) < _page_size:
                    break
                _page_offset += _page_size

            # Python 측 검색 필터링
            if keyword:
                kw_lower = keyword.lower()
                spots_data = [
                    s for s in spots_data
                    if kw_lower in (s.get("name") or "").lower()
                    or kw_lower in (s.get("address") or "").lower()
                    or kw_lower in (s.get("description") or "").lower()
                ]
                spots_data.sort(key=lambda s: _search_rank(s, kw_lower))

            spots_data = location_service.filter_by_radius(spots_data, lat, lng, radius)
            spots_data = location_service.sort_by_distance(spots_data, lat, lng)
            total_count = len(spots_data)
            spots_data = spots_data[offset:offset + limit]
        elif keyword:
            # 검색어 있지만 위치 없음: 전체 조회 후 Python 필터링
            spots_data = []
            _page_size = 1000
            _page_offset = 0
            while True:
                _page_result = query.range(_page_offset, _page_offset + _page_size - 1).execute()
                _page_data = _page_result.data or []
                spots_data.extend(_page_data)
                if len(_page_data) < _page_size:
                    break
                _page_offset += _page_size

            kw_lower = keyword.lower()
            spots_data = [
                s for s in spots_data
                if kw_lower in (s.get("name") or "").lower()
                or kw_lower in (s.get("address") or "").lower()
                or kw_lower in (s.get("description") or "").lower()
            ]
            spots_data.sort(key=lambda s: _search_rank(s, kw_lower))
            total_count = len(spots_data)
            spots_data = spots_data[offset:offset + limit]
        else:
            # 검색어 없고 위치도 없음: 기존 페이지네이션
            count_query = sb.table("tourist_spots").select("id", count="exact").eq("is_active", True)
            if category:
                cats = [c.strip() for c in category.split(",")]
                if len(cats) == 1:
                    count_query = count_query.eq("category_id", cats[0])
                else:
                    count_query = count_query.in_("category_id", cats)
            count_result = count_query.execute()
            total_count = count_result.count if hasattr(count_result, 'count') and count_result.count is not None else len(count_result.data or [])

            result = query.range(offset, offset + limit - 1).execute()
            spots_data = result.data or []

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
                total=total_count,
                limit=limit,
                offset=offset,
                fallback_used=False,
            ),
        )

        await cache.set(cache_key, response.model_dump(), ttl=300)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"관광지 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="관광지 조회 중 오류 발생")


@router.get("/categories")
async def get_categories(lang: str = Query("ko")):
    """[API-003] 카테고리 목록 조회"""
    try:
        sb = get_supabase()

        # 카테고리별 관광지 수 집계 (개별 count 쿼리 — 1000행 제한 회피)
        count_map = {}
        for cat_id in CATEGORY_MAP:
            count_result = (
                sb.table("tourist_spots")
                .select("id", count="exact")
                .eq("is_active", True)
                .eq("category_id", cat_id)
                .execute()
            )
            count_map[cat_id] = (
                count_result.count
                if hasattr(count_result, "count") and count_result.count is not None
                else len(count_result.data or [])
            )

        # DB 카테고리 테이블 조회 시도
        result = sb.table("categories").select("*").order("sort_order").execute()

        items = []
        for cat in (result.data or []):
            name_key = f"name_{lang}" if lang != "ko" else "name_ko"
            cat_id = cat.get("id", "")
            items.append({
                "id": cat_id,
                "name": cat.get(name_key) or cat.get("name_ko", ""),
                "icon": cat.get("icon", ""),
                "spot_count": count_map.get(cat_id, 0),
            })

        # DB 카테고리가 없으면 정적 맵에서 생성
        if not items:
            items = [
                {"id": k, "name": v["name"], "icon": v["icon"], "spot_count": count_map.get(k, 0)}
                for k, v in CATEGORY_MAP.items()
            ]

        return SuccessResponse(data=items)

    except Exception as e:
        logger.error(f"카테고리 조회 실패: {e}")
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
        result = sb.table("tourist_spots").select("*").eq("id", spot_id).limit(1).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

        s = result.data[0]

        # 쾌적함 지수
        comfort = await comfort_service.get_comfort(spot_id)

        # 주변 관광지 (반경 3km)
        all_spots = sb.table("tourist_spots").select("id, name, lat, lng").eq("is_active", True).execute()
        nearby_candidates = []
        if all_spots.data:
            for ns in all_spots.data:
                if str(ns["id"]) == spot_id:
                    continue
                dist = location_service.haversine(
                    s.get("lat", 0), s.get("lng", 0),
                    ns.get("lat", 0), ns.get("lng", 0),
                )
                if dist <= 3.0:
                    nearby_candidates.append({"id": str(ns["id"]), "name": ns["name"], "distance_km": round(dist, 1)})
            nearby_candidates.sort(key=lambda x: x["distance_km"])
            nearby_candidates = nearby_candidates[:3]

        # 주변 관광지 쾌적함 지수 조회
        nearby_ids = [n["id"] for n in nearby_candidates]
        nearby_comfort = await comfort_service.get_bulk_comfort(nearby_ids) if nearby_ids else {}
        nearby = []
        for n in nearby_candidates:
            nc = nearby_comfort.get(n["id"], {})
            n["comfort_score"] = nc.get("total_score")
            n["comfort_grade"] = nc.get("grade")
            nearby.append(n)

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
        raise HTTPException(status_code=500, detail="관광지 상세 조회 중 오류 발생")


@router.get("/{spot_id}/similar")
async def get_similar_spots(
    spot_id: str,
    limit: int = Query(5, ge=1, le=20),
    lang: str = Query("ko"),
):
    """콘텐츠 기반 유사 관광지 추천"""
    cache_key = f"similar_spots:{spot_id}:{limit}:{lang}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()

        # 대상 관광지 존재 확인
        target_result = sb.table("tourist_spots").select("id").eq("id", spot_id).limit(1).execute()
        if not target_result.data:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

        # 전체 활성 관광지 조회
        all_result = sb.table("tourist_spots").select(
            "id, name, category_id, lat, lng, rating, images, address"
        ).eq("is_active", True).execute()
        all_spots = all_result.data or []

        # 유사도 계산
        similar = similarity_engine.find_similar(spot_id, all_spots, top_k=limit)

        items = []
        for s in similar:
            items.append({
                "id": str(s.get("id", "")),
                "name": s.get("name", ""),
                "category": s.get("category_id", ""),
                "category_name": CATEGORY_MAP.get(s.get("category_id", ""), {}).get("name", ""),
                "lat": s.get("lat", 0),
                "lng": s.get("lng", 0),
                "rating": s.get("rating"),
                "thumbnail_url": s.get("images", [""])[0] if isinstance(s.get("images"), list) and s.get("images") else "",
                "similarity_score": s.get("similarity_score", 0),
            })

        response = SuccessResponse(data=items)
        await cache.set(cache_key, response.model_dump(), ttl=600)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"유사 관광지 추천 실패: {e}")
        raise HTTPException(status_code=500, detail="유사 관광지 추천 중 오류 발생")


# 음식점 카테고리 ID (TourAPI contentTypeId=39)
FOOD_CATEGORIES = {"food"}

# 가격대 분류 기준 (원)
PRICE_THRESHOLDS = {"low": 10000, "mid": 25000}


def _classify_price(price: int) -> str:
    """가격대 분류: low / mid / high"""
    if price <= PRICE_THRESHOLDS["low"]:
        return "low"
    if price <= PRICE_THRESHOLDS["mid"]:
        return "mid"
    return "high"


def _parse_menu_text(raw_menu: str) -> List[dict]:
    """
    TourAPI detailIntro2의 음식점 대표메뉴(firstmenu) 및
    취급메뉴(treatmenu) 텍스트를 파싱하여 메뉴 리스트로 변환.
    형식 예시: "밀면 7,000원 / 비빔밀면 7,000원" 또는 줄바꿈 구분
    """
    if not raw_menu:
        return []

    import re
    # <br>, <br/>, 줄바꿈, / 등을 구분자로 사용
    separators = re.split(r'<br\s*/?>|\n|/|,\s*(?=[가-힣a-zA-Z])', raw_menu)
    menus = []

    for item in separators:
        item = re.sub(r'<[^>]+>', '', item).strip()
        if not item:
            continue

        # "메뉴명 가격원" 패턴 매칭
        price_match = re.search(r'(\d[\d,]*)\s*원', item)
        if price_match:
            price_str = price_match.group(1).replace(',', '')
            price = int(price_str)
            name = item[:price_match.start()].strip().rstrip('-').strip()
            if not name:
                continue
            menus.append({
                "name": name,
                "price": price,
                "price_range": _classify_price(price),
                "is_signature": len(menus) == 0,
            })
        else:
            # 가격 없이 메뉴명만 있는 경우
            if item and len(item) < 50:
                menus.append({
                    "name": item,
                    "price": None,
                    "price_range": None,
                    "is_signature": len(menus) == 0,
                })

    return menus


@router.get("/{spot_id}/menu")
async def get_spot_menu(
    spot_id: str,
    price_range: Optional[str] = Query(None, description="가격대 필터 (low/mid/high)"),
    lang: str = Query("ko"),
):
    """맛집 메뉴/가격 정보 조회"""
    cache_key = f"spot_menu:{spot_id}:{price_range}:{lang}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()
        result = sb.table("tourist_spots").select(
            "id, name, category_id, external_id"
        ).eq("id", spot_id).limit(1).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

        spot = result.data[0]

        if spot.get("category_id") not in FOOD_CATEGORIES:
            return SuccessResponse(data={
                "spot_id": str(spot["id"]),
                "is_restaurant": False,
                "menus": [],
                "summary": None,
            })

        # TourAPI detailIntro2에서 메뉴 정보 수집
        menus = []
        external_id = spot.get("external_id")
        content_type_id = "39"  # 음식점 contentTypeId

        if external_id:
            try:
                collector = TourismCollector()
                body = await collector.fetch("/detailIntro2", params={
                    "contentId": external_id,
                    "contentTypeId": content_type_id,
                    "MobileOS": "ETC",
                    "MobileApp": "HelloBusan",
                    "_type": "json",
                })
                await collector.close()

                if body:
                    items_wrapper = body.get("items", {})
                    items = items_wrapper.get("item", []) if isinstance(items_wrapper, dict) else []
                    if isinstance(items, dict):
                        items = [items]

                    if items:
                        item = items[0]
                        # firstmenu: 대표메뉴, treatmenu: 취급메뉴
                        first_menu = item.get("firstmenu", "")
                        treat_menu = item.get("treatmenu", "")

                        raw_text = first_menu
                        if treat_menu and treat_menu != first_menu:
                            raw_text = f"{first_menu} / {treat_menu}" if raw_text else treat_menu

                        menus = _parse_menu_text(raw_text)
            except Exception as e:
                logger.warning(f"메뉴 수집 실패 [{spot_id}]: {e}")

        # 가격대 필터 적용
        if price_range and price_range in ("low", "mid", "high"):
            menus = [m for m in menus if m.get("price_range") == price_range]

        # 가격 요약 정보
        prices = [m["price"] for m in menus if m.get("price")]
        summary = None
        if prices:
            avg_price = round(sum(prices) / len(prices))
            summary = {
                "avg_price": avg_price,
                "min_price": min(prices),
                "max_price": max(prices),
                "price_range": _classify_price(avg_price),
                "menu_count": len(menus),
            }

        response_data = {
            "spot_id": str(spot["id"]),
            "is_restaurant": True,
            "menus": menus,
            "summary": summary,
        }

        response = SuccessResponse(data=response_data)
        await cache.set(cache_key, response.model_dump(), ttl=3600)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"메뉴 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="메뉴 조회 중 오류 발생")
