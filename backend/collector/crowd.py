"""
혼잡도 데이터 수집기
- 부산 실시간 혼잡도 API
- 주요 관광지 방문자 수 추정
"""
from typing import Dict, List, Optional
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


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

        for spot in spots:
            data = await self._collect_crowd(spot)
            if data:
                crowd_data.append(data)

        logger.info(f"혼잡도 데이터 {len(crowd_data)}건 수집")
        return crowd_data

    async def _get_spot_list(self) -> List[Dict]:
        """모니터링 대상 관광지 목록"""
        sb = get_supabase()
        result = sb.table("spots").select("id, content_id, name, lat, lng").execute()
        return result.data or []

    async def _collect_crowd(self, spot: Dict) -> Optional[Dict]:
        """개별 관광지 혼잡도 수집"""
        params = {
            "numOfRows": "1",
            "pageNo": "1",
            "_type": "json",
        }

        body = await self.fetch(
            "/B551011/KorService1/detailCommon1",
            params=params,
        )

        # 혼잡도 계산 (방문자 수 기반 추정)
        crowd_level = self._estimate_crowd_level(body)

        return {
            "spot_id": spot["id"],
            "crowd_level": crowd_level,
            "visitor_count": self._extract_visitor_count(body),
            "measured_at": datetime.now().isoformat(),
        }

    def _estimate_crowd_level(self, data: Optional[Dict]) -> float:
        """
        혼잡도 레벨 추정 (0.0 ~ 1.0)
        - 0.0~0.3: 여유
        - 0.3~0.6: 보통
        - 0.6~0.8: 혼잡
        - 0.8~1.0: 매우 혼잡
        """
        if not data:
            return 0.5  # 기본값

        # TODO: 실제 API 데이터 기반 계산 로직
        return 0.5

    def _extract_visitor_count(self, data: Optional[Dict]) -> int:
        """방문자 수 추출"""
        if not data:
            return 0
        # TODO: 실제 데이터 파싱
        return 0

    async def save(self, data: List[Dict]) -> int:
        """혼잡도 데이터 저장"""
        sb = get_supabase()
        saved = 0

        for item in data:
            try:
                sb.table("comfort_index").insert({
                    "spot_id": item["spot_id"],
                    "crowd_level": item["crowd_level"],
                    "visitor_count": item["visitor_count"],
                    "measured_at": item["measured_at"],
                }).execute()
                saved += 1
            except Exception as e:
                logger.error(f"혼잡도 저장 실패: {e}")

        return saved
