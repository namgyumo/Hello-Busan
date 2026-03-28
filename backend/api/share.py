"""
SNS 공유 메타데이터 API 라우터
OG 태그용 공유 메타데이터 반환
"""
from fastapi import APIRouter, HTTPException
from backend.models.common import SuccessResponse, Meta
from backend.db.supabase import get_supabase
from backend.cache.manager import CacheManager
import logging

router = APIRouter(prefix="/api/v1/share", tags=["share"])
logger = logging.getLogger(__name__)
cache = CacheManager()

BASE_URL = "https://hellobusan.kr"

CATEGORY_LABELS = {
    "nature": "자연/경관",
    "culture": "문화/역사",
    "food": "맛집/카페",
    "activity": "액티비티",
    "shopping": "쇼핑",
    "nightview": "야경",
}


@router.get("/{spot_id}")
async def get_share_metadata(spot_id: str):
    """공유용 메타데이터 반환 (OG 태그용)

    - title: 관광지 이름 — Hello, Busan!
    - description: 쾌적도 포함 설명
    - image_url: 대표 이미지
    - share_url: UTM 파라미터 포함 공유 URL
    - category: 카테고리 라벨
    """
    cache_key = f"share:{spot_id}"
    cached = cache.get(cache_key)
    if cached:
        return SuccessResponse(data=cached)

    try:
        sb = get_supabase()
        result = sb.table("spots").select(
            "id, name, category, address, description, images, lat, lng"
        ).eq("id", spot_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="관광지를 찾을 수 없습니다")

        spot = result.data[0]
        name = spot.get("name", "")
        category = spot.get("category", "")
        category_label = CATEGORY_LABELS.get(category, category)
        description = spot.get("description", "")
        images = spot.get("images") or []
        image_url = images[0] if images else f"{BASE_URL}/images/og-home.png"

        # 설명 텍스트 정리 (HTML 태그 제거, 최대 120자)
        clean_desc = _strip_html(description)
        if len(clean_desc) > 120:
            clean_desc = clean_desc[:117] + "..."

        share_url = (
            f"{BASE_URL}/detail.html?id={spot_id}"
            f"&utm_source=share&utm_medium=sns&utm_campaign=spot_share"
        )

        og_description = (
            f"{name} - {category_label} | {clean_desc}"
            if clean_desc
            else f"{name} - {category_label} | Hello, Busan!에서 부산 관광지를 확인하세요"
        )

        data = {
            "title": f"{name} — Hello, Busan!",
            "description": og_description,
            "image_url": image_url,
            "share_url": share_url,
            "spot_name": name,
            "category": category,
            "category_label": category_label,
            "address": spot.get("address", ""),
        }

        cache.set(cache_key, data, ttl=300)
        return SuccessResponse(data=data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"공유 메타데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="공유 메타데이터를 가져올 수 없습니다")


def _strip_html(html: str) -> str:
    """HTML 태그를 제거하고 텍스트만 추출"""
    if not html:
        return ""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    # HTML 엔티티 디코딩
    text = (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
    return text
