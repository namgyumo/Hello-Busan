"""
쾌적함 지수 서비스
- 혼잡도(50%) + 날씨(30%) + 교통(20%) -> 종합 쾌적함 점수
"""
from typing import Dict, List, Optional
from backend.db.supabase import get_supabase
from backend.models.comfort import ComfortResponse
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

COMFORT_WEIGHTS = {
    "weather": 0.3,
    "crowd": 0.5,
    "transport": 0.2,
}

GRADE_MAP = [
    (80, "쾌적"),
    (60, "보통"),
    (40, "혼잡"),
    (0, "매우혼잡"),
]


def _get_grade(score: int) -> str:
    for threshold, label in GRADE_MAP:
        if score >= threshold:
            return label
    return "매우혼잡"


def _get_crowd_level(crowd_score: int) -> str:
    """crowd_score(0=혼잡, 100=여유) -> 혼잡도 등급 텍스트"""
    if crowd_score is None:
        return "보통"
    if crowd_score >= 70:
        return "여유"
    if crowd_score >= 40:
        return "보통"
    if crowd_score >= 20:
        return "혼잡"
    return "매우혼잡"


class ComfortService:
    """쾌적함 지수 서비스"""

    async def get_comfort(self, spot_id: str) -> Optional[ComfortResponse]:
        """특정 관광지 쾌적함 지수"""
        try:
            sb = get_supabase()
            result = (
                sb.table("comfort_scores")
                .select("*")
                .eq("spot_id", spot_id)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if not result.data:
                return None

            data = result.data[0]
            score = data.get("total_score", 0)

            return ComfortResponse(
                spot_id=str(spot_id),
                score=score,
                grade=_get_grade(score),
                components={
                    "weather": {
                        "score": data.get("weather_score", 0),
                        "weight": COMFORT_WEIGHTS["weather"],
                    },
                    "crowd": {
                        "score": data.get("crowd_score", 0),
                        "weight": COMFORT_WEIGHTS["crowd"],
                    },
                    "transport": {
                        "score": data.get("transport_score", 0),
                        "weight": COMFORT_WEIGHTS["transport"],
                    },
                },
                updated_at=data.get("timestamp"),
            )

        except Exception as e:
            logger.error(f"쾌적함 지수 조회 실패 [{spot_id}]: {e}")
            return None

    async def get_bulk_comfort(self, spot_ids: List[str]) -> Dict[str, Dict]:
        """여러 관광지 쾌적함 지수 일괄 조회 (단일 쿼리)"""
        if not spot_ids:
            return {}

        try:
            sb = get_supabase()

            # spot_id 기준 upsert 테이블이므로 in_ 쿼리로 한 번에 조회
            comfort = (
                sb.table("comfort_scores")
                .select("*")
                .in_("spot_id", spot_ids)
                .execute()
            )

            result = {}
            for data in (comfort.data or []):
                sid = str(data.get("spot_id", ""))
                score = data.get("total_score", 0)
                crowd_score = data.get("crowd_score", 50)
                result[sid] = {
                    "total_score": score,
                    "grade": _get_grade(score),
                    "weather_score": data.get("weather_score"),
                    "crowd_score": crowd_score,
                    "transport_score": data.get("transport_score"),
                    "crowd_level": _get_crowd_level(crowd_score),
                }

            return result

        except Exception as e:
            logger.error(f"일괄 쾌적함 조회 실패: {e}")
            return {}

    @staticmethod
    def calc_comfort_score(
        weather_score: int = 50,
        crowd_score: int = 50,
        transport_score: int = 50,
    ) -> int:
        """쾌적함 지수 계산 (0~100)"""
        score = (
            COMFORT_WEIGHTS["weather"] * weather_score
            + COMFORT_WEIGHTS["crowd"] * crowd_score
            + COMFORT_WEIGHTS["transport"] * transport_score
        )
        return round(score)
