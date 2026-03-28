"""
SNS 공유 메타데이터 API 라우터
OG 태그용 공유 메타데이터 반환 + AI 기반 스마트 카드 생성
"""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from backend.models.common import SuccessResponse, Meta
from backend.db.supabase import get_supabase
from backend.cache.manager import CacheManager
from backend.config import settings
import logging

router = APIRouter(prefix="/api/v1/share", tags=["share"])
logger = logging.getLogger(__name__)
cache = CacheManager()


class SmartCardRequest(BaseModel):
    spot_id: str
    images: List[str]
    spot_name: str
    category: Optional[str] = ""

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


SMART_CARD_PROMPT = """\
당신은 SNS 공유 카드에 사용할 최적의 이미지를 선택하는 전문가입니다.

관광지 정보:
- 이름: {spot_name}
- 카테고리: {category}

이미지 URL 목록 ({image_count}개):
{image_list}

다음을 판단해주세요:
1. SNS 공유 카드에 가장 적합한 이미지의 인덱스 (0부터 시작)
   - 랜드마크가 잘 보이는 사진, 색감이 좋은 사진, 구도가 좋은 사진을 우선
   - 텍스트/로고가 많은 사진, 흐린 사진, 실내 간판 사진은 피하기
2. 선택한 이미지에서 가장 중요한 포인트의 위치 (focus_x, focus_y)
   - 0.0~1.0 비율값 (0.0=왼쪽/위, 1.0=오른쪽/아래)
   - 핵심 피사체(건물, 풍경, 음식 등)의 중심점
3. 카드에 표시할 짧은 캡션 (한국어, 15자 이내)
   - 관광지의 매력을 한 줄로 표현

반드시 아래 JSON 형식만 출력하세요:
{{"selected_image_index": 0, "focus_x": 0.5, "focus_y": 0.5, "caption": "캡션"}}
"""


def _strip_code_block(text: str) -> str:
    """마크다운 코드블록 제거"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


@router.post("/smart-card")
async def create_smart_card(req: SmartCardRequest):
    """AI 기반 스마트 카드 생성

    Gemini에 이미지 URL 목록과 관광지 정보를 전달하여:
    1. 카드에 가장 적합한 이미지 인덱스 선택
    2. 크롭 영역 추천 (focus_x, focus_y: 0.0~1.0)
    3. 한 줄 캡션 생성
    """
    # 이미지가 없으면 폴백
    if not req.images:
        return SuccessResponse(data={
            "selected_image_index": 0,
            "focus_x": 0.5,
            "focus_y": 0.5,
            "caption": "",
        })

    # Gemini API 키가 없으면 폴백
    if not settings.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY 미설정 — 스마트 카드 폴백")
        return SuccessResponse(data={
            "selected_image_index": 0,
            "focus_x": 0.5,
            "focus_y": 0.5,
            "caption": "",
        })

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        image_list = "\n".join(
            f"  [{i}] {url}" for i, url in enumerate(req.images)
        )
        category_label = CATEGORY_LABELS.get(req.category, req.category or "")

        prompt = SMART_CARD_PROMPT.format(
            spot_name=req.spot_name,
            category=category_label,
            image_count=len(req.images),
            image_list=image_list,
        )

        response = await model.generate_content_async(prompt)
        raw_text = _strip_code_block(response.text)
        result = json.loads(raw_text)

        # 값 검증 및 클램핑
        selected_index = result.get("selected_image_index", 0)
        if not isinstance(selected_index, int) or selected_index < 0 or selected_index >= len(req.images):
            selected_index = 0

        focus_x = result.get("focus_x", 0.5)
        focus_y = result.get("focus_y", 0.5)
        focus_x = max(0.0, min(1.0, float(focus_x)))
        focus_y = max(0.0, min(1.0, float(focus_y)))

        caption = result.get("caption", "")
        if not isinstance(caption, str):
            caption = ""
        caption = caption[:20]  # 최대 20자

        data = {
            "selected_image_index": selected_index,
            "focus_x": round(focus_x, 2),
            "focus_y": round(focus_y, 2),
            "caption": caption,
        }

        logger.info(f"스마트 카드 생성: spot={req.spot_name}, index={selected_index}, "
                     f"focus=({focus_x:.2f},{focus_y:.2f}), caption={caption}")

        return SuccessResponse(data=data)

    except json.JSONDecodeError:
        logger.warning(f"스마트 카드 JSON 파싱 실패")
        return SuccessResponse(data={
            "selected_image_index": 0,
            "focus_x": 0.5,
            "focus_y": 0.5,
            "caption": "",
        })
    except Exception as e:
        logger.error(f"스마트 카드 AI 처리 실패: {e}")
        return SuccessResponse(data={
            "selected_image_index": 0,
            "focus_x": 0.5,
            "focus_y": 0.5,
            "caption": "",
        })
