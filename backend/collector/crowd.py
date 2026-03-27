"""
혼잡도 데이터 수집기
- 부산 관광지 실시간 혼잡도 추정
- 방문자 수 데이터 기반 + 시간/요일/시즌 보정
"""
from typing import Dict, List, Optional
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 시간대별 혼잡도 가중치 (0~23시)
HOUR_WEIGHTS = {
    0: 0.05, 1: 0.03, 2: 0.02, 3: 0.02, 4: 0.02, 5: 0.05,
    6: 0.10, 7: 0.15, 8: 0.25, 9: 0.40, 10: 0.60, 11: 0.75,
    12: 0.80, 13: 0.75, 14: 0.70, 15: 0.65, 16: 0.60, 17: 0.55,
    18: 0.50, 19: 0.45, 20: 0.35, 21: 0.25, 22: 0.15, 23: 0.08,
}

# 요일별 보정 (월=0 ~ 일=6)
DAY_MULTIPLIER = {
    0: 0.7, 1: 0.7, 2: 0.7, 3: 0.75, 4: 0.85,  # 월~금
    5: 1.2, 6: 1.3,  # 토, 일
}

# 카테고리별 피크 시간대 보정
CATEGORY_PEAK = {
    "nature": {"peak_hours": range(9, 17), "multiplier": 1.2},
    "culture": {"peak_hours": range(10, 18), "multiplier": 1.1},
    "food": {"peak_hours": [11, 12, 13, 17, 18, 19, 20], "multiplier": 1.3},
    "activity": {"peak_hours": range(10, 17), "multiplier": 1.2},
    "shopping": {"peak_hours": range(13, 21), "multiplier": 1.1},
    "nightview": {"peak_hours": range(18, 24), "multiplier": 1.4},
}

# 월별 시즌 보정 (부산 관광 시즌)
SEASON_MULTIPLIER = {
    1: 0.6, 2: 0.6, 3: 0.8, 4: 0.9, 5: 1.0, 6: 1.1,
    7: 1.4, 8: 1.5, 9: 1.0, 10: 1.1, 11: 0.8, 12: 0.7,
}


class CrowdCollector(BaseCollector):
    """실시간 혼잡도 수집기"""

    def __init__(self):
        super().__init__(
            api_key=settings.DATA_API_KEY,
            base_url="http://apis.data.go.kr",
        )

    async def collect(self) -> List[Dict]:
        """혼잡도 데이터 수집"""
        spots = await self._get_spot_list()
        crowd_data = []

        now = datetime.now()

        for spot in spots:
            data = self._estimate_crowd(spot, now)
            crowd_data.append(data)

        # 공공 API 데이터가 있으면 보정
        api_data = await self._fetch_visitor_api()
        if api_data:
            self._apply_api_correction(crowd_data, api_data)

        logger.info(f"혼잡도 데이터 {len(crowd_data)}건 수집")
        return crowd_data

    async def _get_spot_list(self) -> List[Dict]:
        """모니터링 대상 관광지 목록"""
        sb = get_supabase()
        result = (
            sb.table("tourist_spots")
            .select("id, external_id, name, lat, lng, category_id")
            .eq("is_active", True)
            .execute()
        )
        return result.data or []

    def _estimate_crowd(self, spot: Dict, now: datetime) -> Dict:
        """
        혼잡도 추정 (시간 + 요일 + 시즌 + 카테고리 + 장소 특성 종합)
        crowd_level: 0.0(여유) ~ 1.0(매우혼잡)
        """
        hour = now.hour
        weekday = now.weekday()
        month = now.month
        category = spot.get("category_id", "nature")

        # 기본 시간대 혼잡도
        base = HOUR_WEIGHTS.get(hour, 0.5)

        # 요일 보정
        day_mult = DAY_MULTIPLIER.get(weekday, 1.0)

        # 시즌 보정
        season_mult = SEASON_MULTIPLIER.get(month, 1.0)

        # 카테고리 피크 보정
        cat_info = CATEGORY_PEAK.get(category, {})
        cat_mult = 1.0
        if hour in cat_info.get("peak_hours", []):
            cat_mult = cat_info.get("multiplier", 1.0)

        # 종합 계산
        crowd_level = base * day_mult * season_mult * cat_mult

        # 장소별 고유 변동 (spot_id 기반 결정적 오프셋으로 다양성 확보)
        spot_id = spot.get("id", 0)
        spot_hash = hash(str(spot_id)) % 1000 / 1000.0  # 0.0~0.999
        spot_offset = (spot_hash - 0.5) * 0.3  # -0.15 ~ +0.15
        crowd_level += spot_offset

        # 0~1 범위로 클램핑
        crowd_level = max(0.0, min(1.0, crowd_level))

        # 방문자 수 추정 (혼잡도 기반)
        visitor_count = self._estimate_visitor_count(crowd_level, category)

        # crowd_level을 등급 문자열로 변환
        if crowd_level < 0.3:
            level_text = "여유"
        elif crowd_level < 0.6:
            level_text = "보통"
        elif crowd_level < 0.8:
            level_text = "혼잡"
        else:
            level_text = "매우혼잡"

        # crowd_ratio = crowd_level * 100 (%)
        crowd_ratio = round(crowd_level * 100, 1)

        return {
            "spot_id": spot["id"],
            "crowd_level": level_text,
            "crowd_count": visitor_count,
            "crowd_ratio": crowd_ratio,
            "source": "estimation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _estimate_visitor_count(self, crowd_level: float, category: str) -> int:
        """혼잡도 레벨로부터 방문자 수 추정"""
        # 카테고리별 최대 수용 인원 기준
        capacity = {
            "nature": 5000,
            "culture": 2000,
            "food": 500,
            "activity": 3000,
            "shopping": 4000,
            "nightview": 3000,
        }
        max_cap = capacity.get(category, 2000)
        return int(crowd_level * max_cap)

    async def _fetch_visitor_api(self) -> Optional[List[Dict]]:
        """
        부산 관광지 방문자 통계 API 조회
        (부산관광공사 실시간 방문자 수 데이터)
        """
        try:
            params = {
                "numOfRows": "100",
                "pageNo": "1",
                "_type": "json",
            }
            body = await self.fetch(
                "/B551011/KorService2/areaBasedList2",
                params=params,
            )
            if not body:
                return None

            items_wrapper = body.get("items", {})
            if not isinstance(items_wrapper, dict):
                return None
            items = items_wrapper.get("item", [])
            if not isinstance(items, list):
                items = [items] if isinstance(items, dict) else []

            return items
        except Exception as e:
            logger.debug(f"방문자 API 조회 실패 (추정치 사용): {e}")
            return None

    def _apply_api_correction(
        self, crowd_data: List[Dict], api_items: List[Dict]
    ):
        """API 실데이터로 추정치 보정"""
        # content_id 기반 매핑
        api_map = {}
        for item in api_items:
            cid = item.get("contentid")
            if cid:
                api_map[cid] = item

        # 현재는 API 데이터가 직접적인 혼잡도를 제공하지 않으므로
        # 향후 실시간 데이터 API 연동 시 여기서 보정
        pass

    async def save(self, data: List[Dict]) -> int:
        """혼잡도 데이터 저장"""
        sb = get_supabase()
        saved = 0

        for item in data:
            try:
                sb.table("crowd_data").insert({
                    "spot_id": item["spot_id"],
                    "crowd_level": item["crowd_level"],
                    "crowd_count": item["crowd_count"],
                    "crowd_ratio": item["crowd_ratio"],
                    "source": item.get("source", "estimation"),
                    "timestamp": item["timestamp"],
                }).execute()
                saved += 1
            except Exception as e:
                logger.error(f"혼잡도 저장 실패: {e}")

        return saved
