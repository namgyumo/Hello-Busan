"""
계절·테마 큐레이션 API 라우터
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from backend.models.common import SuccessResponse, Meta
from backend.db.supabase import get_supabase
from backend.cache.manager import CacheManager

router = APIRouter(prefix="/api/v1/themes", tags=["themes"])
logger = logging.getLogger(__name__)
cache = CacheManager()

# 테마 데이터 로드
_THEMES_PATH = Path(__file__).parent.parent / "data" / "themes.json"
_themes_data = None


def _load_themes():
    global _themes_data
    if _themes_data is None:
        with open(_THEMES_PATH, "r", encoding="utf-8") as f:
            _themes_data = json.load(f)
    return _themes_data


def _current_season() -> str:
    month = datetime.now().month
    data = _load_themes()
    for season_id, info in data["seasons"].items():
        if month in info["months"]:
            return season_id
    return "spring"


@router.get("")
async def list_themes(lang: str = Query("ko")):
    """전체 테마 목록 (현재 계절 테마 우선 정렬)"""
    cache_key = f"themes:list:{lang}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    data = _load_themes()
    current = _current_season()
    season_info = data["seasons"].get(current, {})

    themes = []
    for t in data["themes"]:
        themes.append({
            "id": t["id"],
            "name": t.get(f"name_{lang}", t["name"]) if lang != "ko" else t["name"],
            "description": t.get(f"description_{lang}", t["description"]) if lang != "ko" else t["description"],
            "season": t["season"],
            "icon": t["icon"],
            "gradient": t["gradient"],
            "tags": t["tags"],
            "categories": t["categories"],
        })

    # 정렬: 현재 계절 → 상시(all) → 나머지 계절
    def sort_key(theme):
        if theme["season"] == current:
            return 0
        if theme["season"] == "all":
            return 1
        return 2

    themes.sort(key=sort_key)

    result = SuccessResponse(
        data={
            "current_season": current,
            "season_info": season_info,
            "themes": themes,
        },
        meta=Meta(total=len(themes)),
    )

    await cache.set(cache_key, result.model_dump(), ttl=600)
    return result


@router.get("/current")
async def current_season_themes(lang: str = Query("ko")):
    """현재 계절에 맞는 테마만 반환"""
    cache_key = f"themes:current:{lang}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    data = _load_themes()
    current = _current_season()
    season_info = data["seasons"].get(current, {})

    themes = []
    for t in data["themes"]:
        if t["season"] == current:
            themes.append({
                "id": t["id"],
                "name": t.get(f"name_{lang}", t["name"]) if lang != "ko" else t["name"],
                "description": t.get(f"description_{lang}", t["description"]) if lang != "ko" else t["description"],
                "season": t["season"],
                "icon": t["icon"],
                "gradient": t["gradient"],
                "tags": t["tags"],
                "categories": t["categories"],
            })

    result = SuccessResponse(
        data={
            "current_season": current,
            "season_info": season_info,
            "themes": themes,
        },
        meta=Meta(total=len(themes)),
    )

    await cache.set(cache_key, result.model_dump(), ttl=600)
    return result


@router.get("/{theme_id}")
async def theme_detail(
    theme_id: str,
    lang: str = Query("ko"),
    limit: int = Query(12, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """테마 상세 + 해당 관광지 목록 (keywords/categories 기반 동적 검색)"""
    cache_key = f"themes:detail:{theme_id}:{lang}:{limit}:{offset}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    data = _load_themes()
    theme = None
    for t in data["themes"]:
        if t["id"] == theme_id:
            theme = t
            break

    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    current = _current_season()
    season_info = data["seasons"].get(theme["season"], data["seasons"].get(current, {}))

    theme_info = {
        "id": theme["id"],
        "name": theme.get(f"name_{lang}", theme["name"]) if lang != "ko" else theme["name"],
        "description": theme.get(f"description_{lang}", theme["description"]) if lang != "ko" else theme["description"],
        "season": theme["season"],
        "icon": theme["icon"],
        "gradient": theme["gradient"],
        "tags": theme["tags"],
        "categories": theme["categories"],
        "keywords": theme["keywords"],
    }

    # tourist_spots에서 동적 검색
    spots = []
    try:
        sb = get_supabase()

        # 카테고리 기반 검색
        categories = theme.get("categories", [])
        if categories:
            query = sb.table("tourist_spots").select("*").eq("is_active", True)
            if len(categories) == 1:
                query = query.eq("category_id", categories[0])
            else:
                query = query.in_("category_id", categories)

            result = query.limit(100).execute()
            all_spots = result.data or []

            # 키워드 매칭으로 관련성 점수 부여
            keywords = [kw.lower() for kw in theme.get("keywords", [])]
            scored = []
            for s in all_spots:
                score = 0
                name = (s.get("name") or "").lower()
                desc = (s.get("description") or "").lower()
                address = (s.get("address") or "").lower()
                tags_str = " ".join(s.get("tags") or []).lower() if isinstance(s.get("tags"), list) else ""
                searchable = f"{name} {desc} {address} {tags_str}"

                for kw in keywords:
                    if kw in searchable:
                        score += 1

                scored.append((score, s))

            # 관련성 높은 순 정렬, 같으면 이름순
            scored.sort(key=lambda x: (-x[0], x[1].get("name", "")))

            # 페이징
            paged = scored[offset:offset + limit]

            for _, s in paged:
                thumbnail = ""
                images = s.get("images")
                if isinstance(images, list) and images:
                    thumbnail = images[0]

                spots.append({
                    "id": str(s.get("id", "")),
                    "name": s.get("name", ""),
                    "category": s.get("category_id", ""),
                    "address": s.get("address", ""),
                    "lat": s.get("lat"),
                    "lng": s.get("lng"),
                    "thumbnail_url": thumbnail,
                    "description": (s.get("description") or "")[:100],
                })

            total_spots = len(scored)
        else:
            total_spots = 0

    except Exception as e:
        logger.error(f"테마 관광지 검색 실패: {e}")
        total_spots = 0

    response = SuccessResponse(
        data={
            "theme": theme_info,
            "season_info": season_info,
            "spots": spots,
        },
        meta=Meta(total=total_spots, limit=limit, offset=offset),
    )

    await cache.set(cache_key, response.model_dump(), ttl=300)
    return response
