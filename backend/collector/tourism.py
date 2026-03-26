"""
관광지 정보 수집기
- 한국관광공사 TourAPI 4.0
- 관광지 기본정보, 이미지, 카테고리 수집
"""
from typing import Dict, List, Optional
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

# 부산 지역코드
BUSAN_AREA_CODE = "6"
CONTENT_TYPE_MAP = {
    "12": "nature",     # 관광지
    "14": "culture",    # 문화시설
    "15": "activity",   # 축제/공연/행사
    "25": "activity",   # 여행코스
    "28": "activity",   # 레포츠
    "38": "shopping",   # 쇼핑
    "39": "food",       # 음식점
}


class TourismCollector(BaseCollector):
    """한국관광공사 TourAPI 수집기"""

    def __init__(self):
        super().__init__(
            api_key=settings.DATA_API_KEY,
            base_url="http://apis.data.go.kr/B551011/KorService1",
        )

    async def collect(self) -> List[Dict]:
        """부산 관광지 목록 수집 (기본정보 + 상세)"""
        all_spots = []

        for content_type_id in CONTENT_TYPE_MAP.keys():
            spots = await self._collect_by_type(content_type_id)
            if not spots:
                continue

            # 각 관광지의 상세/소개 정보도 수집
            for spot in spots:
                cid = spot.get("external_id")
                if not cid:
                    continue

                detail = await self.collect_detail(cid)
                if detail:
                    spot["description"] = detail.get("description", "")

                intro = await self.collect_intro(cid, content_type_id)
                if intro:
                    spot["operating_hours"] = intro.get("operating_hours", "")
                    spot["admission_fee"] = intro.get("admission_fee", "")

            all_spots.extend(spots)

        logger.info(f"총 {len(all_spots)}개 관광지 수집 완료")
        return all_spots

    async def _collect_by_type(
        self, content_type_id: str
    ) -> Optional[List[Dict]]:
        """콘텐츠 타입별 수집"""
        params = {
            "numOfRows": "100",
            "pageNo": "1",
            "MobileOS": "ETC",
            "MobileApp": "HelloBusan",
            "areaCode": BUSAN_AREA_CODE,
            "contentTypeId": content_type_id,
            "_type": "json",
        }

        body = await self.fetch("/areaBasedList1", params=params)
        if not body:
            return None

        items = body.get("items", {}).get("item", [])
        if not isinstance(items, list):
            items = [items]

        spots = []
        for item in items:
            images = []
            if item.get("firstimage"):
                images.append(item["firstimage"])
            if item.get("firstimage2") and item["firstimage2"] != item.get("firstimage"):
                images.append(item["firstimage2"])

            spot = {
                "external_id": item.get("contentid"),
                "name": item.get("title", "").strip(),
                "category_id": CONTENT_TYPE_MAP.get(content_type_id, "etc"),
                "address": item.get("addr1", ""),
                "lat": float(item.get("mapy", 0)),
                "lng": float(item.get("mapx", 0)),
                "images": images,
                "phone": item.get("tel", ""),
                "content_type_id": content_type_id,
            }
            if spot["lat"] and spot["lng"]:
                spots.append(spot)

        return spots

    async def collect_detail(self, content_id: str) -> Optional[Dict]:
        """관광지 상세 정보 수집"""
        params = {
            "contentId": content_id,
            "MobileOS": "ETC",
            "MobileApp": "HelloBusan",
            "defaultYN": "Y",
            "overviewYN": "Y",
            "_type": "json",
        }

        body = await self.fetch("/detailCommon1", params=params)
        if not body:
            return None

        items = body.get("items", {}).get("item", [])
        if isinstance(items, list) and items:
            item = items[0]
        elif isinstance(items, dict):
            item = items
        else:
            return None

        return {
            "description": item.get("overview", ""),
            "homepage": item.get("homepage", ""),
        }

    async def collect_intro(self, content_id: str, content_type_id: str) -> Optional[Dict]:
        """관광지 소개 정보 수집 (운영시간, 입장료 등)"""
        params = {
            "contentId": content_id,
            "contentTypeId": content_type_id,
            "MobileOS": "ETC",
            "MobileApp": "HelloBusan",
            "_type": "json",
        }

        body = await self.fetch("/detailIntro1", params=params)
        if not body:
            return None

        items = body.get("items", {}).get("item", [])
        if isinstance(items, list) and items:
            item = items[0]
        elif isinstance(items, dict):
            item = items
        else:
            return None

        # 컨텐츠 타입별 필드명이 다름
        return {
            "operating_hours": (
                item.get("usetime", "")
                or item.get("usetimeculture", "")
                or item.get("playtime", "")
                or item.get("opentimefood", "")
                or ""
            ),
            "admission_fee": (
                item.get("usefee", "")
                or item.get("usetimefestival", "")
                or ""
            ),
        }

    async def save(self, data: List[Dict]) -> int:
        """Supabase에 관광지 데이터 저장 (upsert)"""
        sb = get_supabase()
        saved = 0

        for spot in data:
            try:
                sb.table("tourist_spots").upsert(
                    {
                        "external_id": spot["external_id"],
                        "name": spot["name"],
                        "category_id": spot["category_id"],
                        "address": spot["address"],
                        "lat": spot["lat"],
                        "lng": spot["lng"],
                        "images": spot["images"],
                        "phone": spot["phone"],
                        "description": spot.get("description", ""),
                        "operating_hours": spot.get("operating_hours", ""),
                        "admission_fee": spot.get("admission_fee", ""),
                        "is_active": True,
                    },
                    on_conflict="external_id",
                ).execute()
                saved += 1
            except Exception as e:
                logger.error(f"저장 실패 [{spot.get('name')}]: {e}")

        return saved
