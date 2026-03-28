"""
혼잡도 트렌드 예측 서비스
- 시간대별(24시간) 혼잡도 트렌드
- 요일별(월~일) 혼잡도 패턴
- 카테고리별 기본 패턴 생성 (데이터 부족 시 폴백)
"""
from typing import Dict, List, Optional
from backend.db.supabase import get_supabase
from backend.collector.crowd import (
    HOUR_WEIGHTS, DAY_MULTIPLIER, SEASON_MULTIPLIER, CATEGORY_PEAK,
)
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)


class CrowdTrendService:
    """혼잡도 트렌드 예측 서비스"""

    def _spot_offset(self, spot_id: str) -> float:
        """spot_id 기반 결정적 오프셋 (crowd.py와 동일 로직)"""
        spot_hash = int(hashlib.md5(str(spot_id).encode()).hexdigest(), 16) % 1000 / 1000.0
        return (spot_hash - 0.5) * 0.3

    def _crowd_level_to_score(self, crowd_level: float) -> int:
        """crowd_level(0=여유, 1=혼잡) -> crowd_score(0=혼잡, 100=여유)"""
        crowd_ratio = crowd_level * 100
        return int(max(0, min(100, 100 - crowd_ratio)))

    def _get_category(self, spot_id: str) -> Optional[str]:
        """관광지 카테고리 조회"""
        try:
            sb = get_supabase()
            result = (
                sb.table("tourist_spots")
                .select("category_id")
                .eq("id", spot_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0].get("category_id", "nature")
            return None
        except Exception as e:
            logger.error(f"카테고리 조회 실패 [{spot_id}]: {e}")
            return None

    def get_hourly_trend(self, spot_id: str) -> Optional[Dict]:
        """시간대별(0~23시) 혼잡도 트렌드 반환

        Returns:
            {
                "spot_id": str,
                "hours": [{"hour": 0, "crowd_score": 95, "level": "여유"}, ...],
                "best_times": [{"hour": 5, "crowd_score": 98}, ...],  # TOP 3 한산한 시간
                "current_hour": int,
                "current_score": int,
                "current_level": str,
            }
        """
        category = self._get_category(spot_id)
        if category is None:
            return None

        now = datetime.now()
        weekday = now.weekday()
        month = now.month
        current_hour = now.hour

        offset = self._spot_offset(spot_id)
        day_mult = DAY_MULTIPLIER.get(weekday, 1.0)
        season_mult = SEASON_MULTIPLIER.get(month, 1.0)
        cat_info = CATEGORY_PEAK.get(category, {})

        hours = []
        for hour in range(24):
            base = HOUR_WEIGHTS.get(hour, 0.5)
            cat_mult = 1.0
            if hour in cat_info.get("peak_hours", []):
                cat_mult = cat_info.get("multiplier", 1.0)

            crowd_level = base * day_mult * season_mult * cat_mult + offset
            crowd_level = max(0.0, min(1.0, crowd_level))
            crowd_score = self._crowd_level_to_score(crowd_level)

            if crowd_score >= 70:
                level = "여유"
            elif crowd_score >= 40:
                level = "보통"
            elif crowd_score >= 20:
                level = "혼잡"
            else:
                level = "매우혼잡"

            hours.append({
                "hour": hour,
                "crowd_score": crowd_score,
                "level": level,
            })

        # best_times: 가장 한산한 시간대 TOP 3
        sorted_hours = sorted(hours, key=lambda h: h["crowd_score"], reverse=True)
        best_times = [{"hour": h["hour"], "crowd_score": h["crowd_score"]} for h in sorted_hours[:3]]

        current_entry = hours[current_hour]

        return {
            "spot_id": spot_id,
            "hours": hours,
            "best_times": best_times,
            "current_hour": current_hour,
            "current_score": current_entry["crowd_score"],
            "current_level": current_entry["level"],
        }

    def get_weekly_pattern(self, spot_id: str) -> Optional[Dict]:
        """요일별(월~일) 평균 혼잡도 패턴 반환

        Returns:
            {
                "spot_id": str,
                "days": [{"day": 0, "day_name": "월", "avg_score": 75}, ...],
                "best_day": {"day": 0, "day_name": "월", "avg_score": 75},
                "today": int,
            }
        """
        category = self._get_category(spot_id)
        if category is None:
            return None

        now = datetime.now()
        month = now.month
        today = now.weekday()

        offset = self._spot_offset(spot_id)
        season_mult = SEASON_MULTIPLIER.get(month, 1.0)
        cat_info = CATEGORY_PEAK.get(category, {})

        day_names = ["월", "화", "수", "목", "금", "토", "일"]
        days = []

        for weekday in range(7):
            day_mult = DAY_MULTIPLIER.get(weekday, 1.0)

            # 하루 평균: 주요 활동 시간대(8~22시) 평균 혼잡도
            total_score = 0
            count = 0
            for hour in range(8, 22):
                base = HOUR_WEIGHTS.get(hour, 0.5)
                cat_mult = 1.0
                if hour in cat_info.get("peak_hours", []):
                    cat_mult = cat_info.get("multiplier", 1.0)

                crowd_level = base * day_mult * season_mult * cat_mult + offset
                crowd_level = max(0.0, min(1.0, crowd_level))
                total_score += self._crowd_level_to_score(crowd_level)
                count += 1

            avg_score = round(total_score / count) if count > 0 else 50

            days.append({
                "day": weekday,
                "day_name": day_names[weekday],
                "avg_score": avg_score,
            })

        # best_day: 가장 한산한 요일
        best = max(days, key=lambda d: d["avg_score"])

        return {
            "spot_id": spot_id,
            "days": days,
            "best_day": {
                "day": best["day"],
                "day_name": best["day_name"],
                "avg_score": best["avg_score"],
            },
            "today": today,
        }
