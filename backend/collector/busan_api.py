"""
부산시 공공데이터 API 6종 수집기
- 부산테마여행 (RecommendedService)       → activity / nightview
- 모범음식점 (BusanTblFnrstrnStusService) → food
- 부산도보여행 (WalkingService)            → activity
- 갈맷길 코스 (BusanGalmaetGilService)    → activity
- 관광안내소 (InfoOfficeService)           → culture (참조)
- 문화재 현황 (BusanTblClthrtStusService)  → culture

공통: 부산시 API(6260000), DATA_API_KEY, 일일 10,000건
응답 형식이 2종류:
  - 표준형: {response: {header: {resultCode}, body: {items: {item: []}}}}
  - visitbusan형: {rootKey: {header: {code}, item: [], totalCount}}
"""
import hashlib
from typing import Dict, List, Optional
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

# 야경 키워드 (테마여행 nightview 분류용)
_NIGHT_KEYWORDS = ["야경", "밤", "야간", "선셋", "노을", "일몰", "석양"]

# 갈맷길 코스별 대표 시작점 좌표
_GALMAETGIL_COORDS = {
    "1": (35.1869, 129.2201),   # 임랑해수욕장
    "2": (35.1632, 129.1750),   # 송정해수욕장
    "3": (35.1577, 129.1600),   # 해운대
    "4": (35.1362, 129.1076),   # 오륙도
    "5": (35.0798, 129.0732),   # 남항대교
    "6": (35.0690, 129.0150),   # 감천문화마을
    "7": (35.0500, 128.9660),   # 낙동강하구
    "8": (35.0400, 128.9700),   # 을숙도
    "9": (35.0320, 128.9580),   # 가덕도
}


def _safe_float(val, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if v != 0 else default
    except (TypeError, ValueError):
        return default


def _clean_title(title: str) -> str:
    """다국어 태그 제거: '초량이바구길 (한,영,중간,중번,일)' → '초량이바구길'"""
    if " (" in title and title.endswith(")"):
        return title[:title.rfind(" (")].strip()
    return title.strip()


class BusanApiCollector(BaseCollector):
    """부산시 공공데이터 API 6종 통합 수집기"""

    PAGE_SIZE = 100

    def __init__(self):
        super().__init__(
            api_key=settings.DATA_API_KEY,
            base_url="http://apis.data.go.kr/6260000",
        )

    # ------------------------------------------------------------------
    # 응답 파싱 오버라이드
    # ------------------------------------------------------------------
    def _parse_response(self, data: Dict) -> Optional[Dict]:
        """
        부산시 API 응답 파싱 — 두 가지 형식 지원

        표준형 (모범음식점, 갈맷길, 문화재):
          {response: {header: {resultCode: "00"}, body: {items: {item: [...]}, totalCount: N}}}
        visitbusan형 (테마여행, 도보여행, 관광안내소):
          {rootKey: {header: {code: "00"}, item: [...], totalCount: N}}
        """
        if not isinstance(data, dict):
            return None

        # 표준형 시도
        if "response" in data:
            return super()._parse_response(data)

        # visitbusan 형 — 최상위 키가 API 메서드명
        try:
            root_key = next(iter(data))
            api_data = data[root_key]
            if not isinstance(api_data, dict):
                return None

            header = api_data.get("header", {})
            code = str(header.get("code", ""))
            if code and code not in ("00", "0000"):
                logger.warning(f"부산시 API 에러: {header.get('message', '')}")
                return None

            items = api_data.get("item", [])
            if not isinstance(items, list):
                items = [items] if isinstance(items, dict) else []

            total = int(api_data.get("totalCount", len(items)))
            return {
                "items": items,
                "totalCount": total,
            }
        except Exception as e:
            logger.error(f"부산시 API 응답 파싱 실패: {e}")
            return None

    # ------------------------------------------------------------------
    # 수집 메인
    # ------------------------------------------------------------------
    async def collect(self) -> List[Dict]:
        """6개 API 순차 수집"""
        all_spots = []

        collectors = [
            ("theme", self._collect_theme),
            ("food", self._collect_food),
            ("galmaetgil", self._collect_galmaetgil),
            ("info_office", self._collect_info_office),
            ("heritage", self._collect_heritage),
        ]

        for name, fn in collectors:
            try:
                spots = await fn()
                all_spots.extend(spots)
                logger.info(f"부산시 [{name}] {len(spots)}건 수집")
            except Exception as e:
                logger.error(f"부산시 [{name}] 수집 실패: {e}")

        logger.info(f"부산시 API 총 {len(all_spots)}건 수집 완료")
        return all_spots

    # ------------------------------------------------------------------
    # 1. 부산테마여행 + 부산도보여행 (동일 구조, visitbusan형)
    # ------------------------------------------------------------------
    async def _collect_theme(self) -> List[Dict]:
        """테마여행 + 도보여행 수집"""
        apis = [
            ("/RecommendedService/getRecommendedKr", "테마여행"),
            ("/WalkingService/getWalkingKr", "도보여행"),
        ]
        spots = []
        seen = set()

        for endpoint, label in apis:
            page = 1
            while True:
                body = await self.fetch(endpoint, {
                    "numOfRows": str(self.PAGE_SIZE),
                    "pageNo": str(page),
                    "resultType": "json",
                })
                if not body:
                    break

                items = body.get("items", [])
                if not items:
                    break

                for item in items:
                    seq = item.get("UC_SEQ")
                    if seq in seen:
                        continue
                    seen.add(seq)

                    lat = _safe_float(item.get("LAT"))
                    lng = _safe_float(item.get("LNG"))
                    if not lat or not lng:
                        continue

                    title = _clean_title(
                        item.get("MAIN_TITLE") or item.get("TITLE") or ""
                    )
                    if not title:
                        continue

                    # nightview 분류
                    text = (item.get("MAIN_TITLE") or "") + " " + (item.get("TITLE") or "")
                    category = "nightview" if any(kw in text for kw in _NIGHT_KEYWORDS) else "activity"

                    images = []
                    for key in ("MAIN_IMG_NORMAL", "MAIN_IMG_THUMB"):
                        img = item.get(key, "")
                        if img and img not in images:
                            images.append(img)

                    spots.append({
                        "external_id": f"busan_theme_{seq}",
                        "name": title,
                        "category_id": category,
                        "address": item.get("ADDR1", ""),
                        "lat": lat,
                        "lng": lng,
                        "images": images,
                        "phone": item.get("CNTCT_TEL", ""),
                        "description": (item.get("ITEMCNTNTS") or "")[:2000],
                        "operating_hours": item.get("USAGE_DAY_WEEK_AND_TIME", ""),
                        "admission_fee": item.get("USAGE_AMOUNT", ""),
                    })

                total = int(body.get("totalCount", 0))
                if page * self.PAGE_SIZE >= total:
                    break
                page += 1

        return spots

    # ------------------------------------------------------------------
    # 2. 모범음식점 (표준형)
    # ------------------------------------------------------------------
    async def _collect_food(self) -> List[Dict]:
        """모범음식점 수집 — 실제 필드: bsnsNm, addrRoad, lat, lng, tel, menu, bsnsCond"""
        spots = []
        page = 1

        while True:
            body = await self.fetch("/BusanTblFnrstrnStusService/getTblFnrstrnStusInfo", {
                "numOfRows": str(self.PAGE_SIZE),
                "pageNo": str(page),
                "resultType": "json",
            })
            items = self._extract_standard_items(body)
            if not items:
                break

            for item in items:
                lat = _safe_float(item.get("lat"))
                lng = _safe_float(item.get("lng"))
                if not lat or not lng:
                    continue

                name = (item.get("bsnsNm") or "").strip()
                if not name:
                    continue

                cond = item.get("bsnsCond") or ""
                menu = item.get("menu") or ""
                desc = cond + (f" / {menu}" if menu else "")
                addr = item.get("addrRoad") or item.get("addrJibun") or ""

                uid = hashlib.md5(f"{name}_{addr}".encode()).hexdigest()[:12]
                spots.append({
                    "external_id": f"busan_food_{uid}",
                    "name": name,
                    "category_id": "food",
                    "address": addr,
                    "lat": lat,
                    "lng": lng,
                    "images": [],
                    "phone": item.get("tel") or "",
                    "description": desc,
                    "operating_hours": "",
                    "admission_fee": "",
                })

            total = int(body.get("totalCount", 0)) if body else 0
            if page * self.PAGE_SIZE >= total:
                break
            page += 1

        return spots

    # ------------------------------------------------------------------
    # 3. 갈맷길 코스 (표준형, 좌표 없음 → 수동 매핑)
    # ------------------------------------------------------------------
    async def _collect_galmaetgil(self) -> List[Dict]:
        """갈맷길 코스 수집 — 좌표가 API에 없으므로 코스번호로 대표좌표 매핑"""
        body = await self.fetch("/BusanGalmaetGilService/getGalmaetGilInfo", {
            "numOfRows": "50",
            "pageNo": "1",
            "resultType": "json",
        })
        items = self._extract_standard_items(body)
        if not items:
            return []

        spots = []
        for item in items:
            kos_type = str(item.get("kosType", ""))
            kos_nm = item.get("kosNm", "")
            title = item.get("title", "")

            lat, lng = _GALMAETGIL_COORDS.get(kos_type, (0.0, 0.0))
            if not lat or not lng:
                continue

            name = f"갈맷길 {kos_nm}" + (f" - {title}" if title else "")
            route = item.get("kosTxt", "")
            detail = item.get("txt1", "")

            spots.append({
                "external_id": f"busan_galmaetgil_{kos_type}_{title}".replace(" ", "_")[:50],
                "name": name,
                "category_id": "activity",
                "address": f"부산 갈맷길 {kos_nm}",
                "lat": lat,
                "lng": lng,
                "images": [],
                "phone": "",
                "description": f"{route}\n\n{detail}"[:2000],
                "operating_hours": "",
                "admission_fee": "",
            })

        return spots

    # ------------------------------------------------------------------
    # 4. 관광안내소 (visitbusan형)
    # ------------------------------------------------------------------
    async def _collect_info_office(self) -> List[Dict]:
        """관광안내소 수집 — 실제 필드: NM, LAT, LNG, ADDR1, INQRY_TEL, OP_TIME"""
        body = await self.fetch("/InfoOfficeService/getInfoOfficeKr", {
            "numOfRows": "100",
            "pageNo": "1",
            "resultType": "json",
        })
        if not body:
            return []

        items = body.get("items", [])
        spots = []

        for item in items:
            lat = _safe_float(item.get("LAT"))
            lng = _safe_float(item.get("LNG"))
            if not lat or not lng:
                continue

            seq = item.get("UIO_SEQ", "")
            name = item.get("NM") or f"부산 관광안내소 #{seq}"

            spots.append({
                "external_id": f"busan_info_office_{seq}",
                "name": name.strip(),
                "category_id": "culture",
                "address": item.get("ADDR1") or "",
                "lat": lat,
                "lng": lng,
                "images": [],
                "phone": item.get("INQRY_TEL", ""),
                "description": item.get("INFOFC_INTRCN") or "",
                "operating_hours": item.get("OP_TIME", ""),
                "admission_fee": "",
            })

        return spots

    # ------------------------------------------------------------------
    # 5. 문화재 현황 (표준형)
    # ------------------------------------------------------------------
    async def _collect_heritage(self) -> List[Dict]:
        """문화재 수집 — 실제 필드: cultHeritNm, lat, lng, addr, kind, era, number, tel"""
        spots = []
        page = 1

        while True:
            body = await self.fetch("/BusanTblClthrtStusService/getTblClthrtStusInfo", {
                "numOfRows": str(self.PAGE_SIZE),
                "pageNo": str(page),
                "resultType": "json",
            })
            items = self._extract_standard_items(body)
            if not items:
                break

            for item in items:
                lat = _safe_float(item.get("lat"))
                lng = _safe_float(item.get("lng"))
                if not lat or not lng:
                    continue

                name = (item.get("cultHeritNm") or "").strip()
                if not name:
                    continue

                kind = item.get("kind", "")
                era = (item.get("era") or "").strip()
                contents = item.get("majorContents") or ""
                desc = f"[{kind}]" if kind else ""
                if era:
                    desc += f" {era}"
                if contents:
                    desc += f"\n{contents}"

                number = item.get("number", "")

                spots.append({
                    "external_id": f"busan_heritage_{number}_{name}".replace(" ", "_")[:50],
                    "name": name,
                    "category_id": "culture",
                    "address": item.get("roadAddr") or item.get("addr", ""),
                    "lat": lat,
                    "lng": lng,
                    "images": [],
                    "phone": item.get("tel", ""),
                    "description": desc[:2000],
                    "operating_hours": "",
                    "admission_fee": "",
                })

            total = int(body.get("totalCount", 0)) if body else 0
            if page * self.PAGE_SIZE >= total:
                break
            page += 1

        return spots

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_standard_items(body: Optional[Dict]) -> List[Dict]:
        """표준 body에서 items.item 리스트 추출"""
        if not body:
            return []
        items_wrapper = body.get("items", {})
        if not isinstance(items_wrapper, dict):
            # visitbusan형에서는 items가 이미 list
            return items_wrapper if isinstance(items_wrapper, list) else []
        items = items_wrapper.get("item", [])
        if not isinstance(items, list):
            return [items] if isinstance(items, dict) else []
        return items

    # ------------------------------------------------------------------
    # 저장
    # ------------------------------------------------------------------
    async def save(self, data: List[Dict]) -> int:
        """tourist_spots 테이블에 upsert"""
        sb = get_supabase()
        saved = 0

        for spot in data:
            try:
                sb.table("tourist_spots").upsert(
                    {
                        "external_id": spot["external_id"][:50],
                        "name": spot["name"][:200],
                        "category_id": spot["category_id"][:20],
                        "address": (spot.get("address") or "")[:300],
                        "lat": spot["lat"],
                        "lng": spot["lng"],
                        "images": spot.get("images", []),
                        "phone": (spot.get("phone") or "")[:20],
                        "description": spot.get("description") or "",
                        "operating_hours": (spot.get("operating_hours") or "")[:200],
                        "admission_fee": (spot.get("admission_fee") or "")[:100],
                        "is_active": True,
                    },
                    on_conflict="external_id",
                ).execute()
                saved += 1
            except Exception as e:
                logger.error(f"저장 실패 [{spot.get('name')}]: {e}")

        return saved
