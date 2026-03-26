"""
쾌적도 서비스
- 혼잡도 + 날씨 + 교통 -> 종합 쾌적도 계산
"""
from typing import Dict, List, Optional
from backend.db.supabase import get_supabase
from backend.models.comfort import ComfortResponse, ComfortDashboard
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ComfortService:
    """쾌적도 서비스"""

    COMFORT_WEIGHTS = {
        "crowd": 0.5,
        "weather": 0.3,
        "transport": 0.2,
    }

    async def get_comfort(self, spot_id: str) -> Optional[ComfortResponse]:
        """특정 관광지 쾌적도"""
        sb = get_supabase()

        comfort = (
            sb.table("comfort_index")
            .select("*")
            .eq("spot_id", spot_id)
            .order("measured_at", desc=True)
            .limit(1)
            .execute()
        )

        if not comfort.data:
            return None

        data = comfort.data[0]
        score = self._calc_comfort_score(data)

        return ComfortResponse(
            spot_id=spot_id,
            score=score,
            crowd_level=data.get("crowd_level", 0.5),
            label=self._get_label(score),
            measured_at=data.get("measured_at"),
        )

    async def get_bulk_comfort(
        self, spot_ids: List[str]
    ) -> Dict[str, Dict]:
        """여러 관광지 혼잡도 일괄 조회"""
        sb = get_supabase()
        result = {}

        for spot_id in spot_ids:
            comfort = (
                sb.table("comfort_index")
                .select("*")
                .eq("spot_id", spot_id)
                .order("measured_at", desc=True)
                .limit(1)
                .execute()
            )
            if comfort.data:
                result[spot_id] = comfort.data[0]

        return result

    async def get_dashboard(
        self, category: Optional[str] = None
    ) -> ComfortDashboard:
        """전체 쾌적도 대시보드"""
        sb = get_supabase()

        query = sb.table("spots").select("id, name, category, lat, lng")
        if category:
            query = query.eq("category", category)
        spots = query.execute()

        items = []
        for spot in spots.data or []:
            comfort = await self.get_comfort(spot["id"])
            items.append({
                "spot_id": spot["id"],
                "name": spot["name"],
                "category": spot["category"],
                "lat": spot["lat"],
                "lng": spot["lng"],
                "comfort": comfort.dict() if comfort else None,
            })

        return ComfortDashboard(
            items=items,
            total=len(items),
            updated_at=datetime.now().isoformat(),
        )

    async def get_history(
        self, spot_id: str, hours: int = 24
    ) -> List[Dict]:
        """쾌적도 히스토리"""
        sb = get_supabase()
        since = (datetime.now() - timedelta(hours=hours)).isoformat()

        result = (
            sb.table("comfort_index")
            .select("*")
            .eq("spot_id", spot_id)
            .gte("measured_at", since)
            .order("measured_at")
            .execute()
        )

        return result.data or []

    def _calc_comfort_score(self, data: Dict) -> float:
        """종합 쾌적도 점수 (0~100)"""
        crowd = 1 - data.get("crowd_level", 0.5)
        weather = data.get("weather_score", 0.7)
        transport = data.get("transport_score", 0.5)

        score = (
            self.COMFORT_WEIGHTS["crowd"] * crowd
            + self.COMFORT_WEIGHTS["weather"] * weather
            + self.COMFORT_WEIGHTS["transport"] * transport
        )
        return round(score * 100, 1)

    @staticmethod
    def _get_label(score: float) -> str:
        """쾌적도 라벨"""
        if score >= 80:
            return "매우 쾌적"
        elif score >= 60:
            return "쾌적"
        elif score >= 40:
            return "보통"
        elif score >= 20:
            return "혼잡"
        else:
            return "매우 혼잡"
