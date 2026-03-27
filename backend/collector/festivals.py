"""
부산 축제/이벤트 수집기
- 한국관광공사 TourAPI 4.0 행사/이벤트 (contentTypeId=15)
- 부산 지역 축제 정보 수집 및 Supabase 저장
"""
from typing import Dict, List, Optional
from datetime import datetime
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

BUSAN_AREA_CODE = "6"
CONTENT_TYPE_FESTIVAL = "15"


class FestivalCollector(BaseCollector):
    """부산 축제/이벤트 TourAPI 수집기"""

    def __init__(self):
        super().__init__(
            api_key=settings.DATA_API_KEY,
            base_url="http://apis.data.go.kr/B551011/KorService2",
        )

    async def collect(self) -> List[Dict]:
        """부산 축제/이벤트 목록 수집"""
        all_festivals = []
        page = 1

        while True:
            params = {
                "numOfRows": "50",
                "pageNo": str(page),
                "MobileOS": "ETC",
                "MobileApp": "HelloBusan",
                "areaCode": BUSAN_AREA_CODE,
                "contentTypeId": CONTENT_TYPE_FESTIVAL,
                "_type": "json",
                "listYN": "Y",
                "arrange": "D",
            }

            body = await self.fetch("/areaBasedList2", params=params)
            if not body:
                break

            items_wrapper = body.get("items", {})
            if not isinstance(items_wrapper, dict):
                break
            items = items_wrapper.get("item", [])
            if not isinstance(items, list):
                items = [items] if isinstance(items, dict) else []

            if not items:
                break

            for item in items:
                lat = float(item.get("mapy", 0))
                lng = float(item.get("mapx", 0))
                if not lat or not lng:
                    continue

                content_id = item.get("contentid", "")
                title = (item.get("title") or "").strip()
                if not title:
                    continue

                images = []
                if item.get("firstimage"):
                    images.append(item["firstimage"])
                if item.get("firstimage2") and item["firstimage2"] != item.get("firstimage"):
                    images.append(item["firstimage2"])

                festival = {
                    "content_id": content_id,
                    "title": title,
                    "address": item.get("addr1", ""),
                    "lat": lat,
                    "lng": lng,
                    "images": images,
                    "phone": item.get("tel", ""),
                }

                # 상세 + 소개 정보 수집
                try:
                    detail = await self._collect_detail(content_id)
                    if detail:
                        festival["description"] = detail.get("description", "")
                        festival["homepage"] = detail.get("homepage", "")

                    intro = await self._collect_intro(content_id)
                    if intro:
                        festival["event_start_date"] = intro.get("event_start_date")
                        festival["event_end_date"] = intro.get("event_end_date")
                        festival["event_place"] = intro.get("event_place", "")
                        festival["sponsor"] = intro.get("sponsor", "")
                        festival["use_time"] = intro.get("use_time", "")
                except Exception as e:
                    logger.warning(f"축제 상세 수집 실패 [{content_id}]: {e}")

                all_festivals.append(festival)

            total_count = int(body.get("totalCount", 0))
            if page * 50 >= total_count:
                break
            page += 1

        logger.info(f"축제/이벤트 총 {len(all_festivals)}건 수집 완료")
        return all_festivals

    async def _collect_detail(self, content_id: str) -> Optional[Dict]:
        """축제 상세 정보 (overview)"""
        params = {
            "contentId": content_id,
            "MobileOS": "ETC",
            "MobileApp": "HelloBusan",
            "defaultYN": "Y",
            "overviewYN": "Y",
            "_type": "json",
        }
        body = await self.fetch("/detailCommon2", params=params)
        if not body:
            return None

        items_wrapper = body.get("items", {})
        if not isinstance(items_wrapper, dict):
            return None
        items = items_wrapper.get("item", [])
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

    async def _collect_intro(self, content_id: str) -> Optional[Dict]:
        """축제 소개 정보 (기간, 장소 등)"""
        params = {
            "contentId": content_id,
            "contentTypeId": CONTENT_TYPE_FESTIVAL,
            "MobileOS": "ETC",
            "MobileApp": "HelloBusan",
            "_type": "json",
        }
        body = await self.fetch("/detailIntro2", params=params)
        if not body:
            return None

        items_wrapper = body.get("items", {})
        if not isinstance(items_wrapper, dict):
            return None
        items = items_wrapper.get("item", [])
        if isinstance(items, list) and items:
            item = items[0]
        elif isinstance(items, dict):
            item = items
        else:
            return None

        return {
            "event_start_date": _parse_date(item.get("eventstartdate")),
            "event_end_date": _parse_date(item.get("eventenddate")),
            "event_place": item.get("eventplace", ""),
            "sponsor": item.get("sponsor1", "") or item.get("sponsor2", ""),
            "use_time": item.get("usetimefestival", ""),
        }

    async def save(self, data: List[Dict]) -> int:
        """festivals 테이블에 upsert"""
        sb = get_supabase()
        saved = 0

        for f in data:
            try:
                row = {
                    "content_id": str(f["content_id"])[:50],
                    "title": f["title"][:200],
                    "address": (f.get("address") or "")[:300],
                    "lat": f["lat"],
                    "lng": f["lng"],
                    "images": f.get("images", []),
                    "phone": (f.get("phone") or "")[:50],
                    "description": f.get("description") or "",
                    "homepage": (f.get("homepage") or "")[:500],
                    "event_start_date": f.get("event_start_date"),
                    "event_end_date": f.get("event_end_date"),
                    "event_place": (f.get("event_place") or "")[:200],
                    "sponsor": (f.get("sponsor") or "")[:200],
                    "use_time": (f.get("use_time") or "")[:200],
                    "is_active": True,
                }
                sb.table("festivals").upsert(
                    row, on_conflict="content_id"
                ).execute()
                saved += 1
            except Exception as e:
                logger.error(f"축제 저장 실패 [{f.get('title')}]: {e}")

        return saved


def _parse_date(val) -> Optional[str]:
    """TourAPI 날짜 문자열 (YYYYMMDD) → ISO date (YYYY-MM-DD)"""
    if not val:
        return None
    val = str(val).strip()
    if len(val) == 8 and val.isdigit():
        return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
    return val[:10] if len(val) >= 10 else None
