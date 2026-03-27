"""
사용자 프로필 빌더 — 세션 이벤트 기반 선호도 분석

- 카테고리 선호도: 클릭/상세조회 관광지의 카테고리 분포 (시간 감쇠 적용)
- 위치 선호도: 관심 관광지들의 평균 좌표
- 시간 선호도: 활동 시간대 패턴
- 즐겨찾기 관광지 ID 목록
"""
import math
import logging
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

from backend.db.supabase import get_supabase

logger = logging.getLogger(__name__)


def time_decay_weight(event_time: datetime, half_life_days: int = 14) -> float:
    """이벤트의 시간 감쇠 가중치 (최근 이벤트일수록 높은 가중치)

    반감기(half_life_days) 경과 시 가중치가 0.5로 감소.
    """
    now = datetime.now(timezone.utc)
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    days_ago = (now - event_time).total_seconds() / 86400
    if days_ago < 0:
        days_ago = 0
    return math.exp(-0.693 * days_ago / half_life_days)


# 관광지 상호작용으로 간주할 이벤트 타입
_INTERACTION_EVENTS = {"spot_click", "detail_view", "detail_leave", "favorite", "share"}


class UserProfileBuilder:
    """세션 기반 사용자 선호도 프로필 생성"""

    async def build_from_session(self, session_id: str) -> Optional[dict]:
        """세션의 이벤트 기록에서 사용자 선호도 추출

        Returns:
            dict — 프로필 정보, 이벤트가 부족하면 None
        """
        sb = get_supabase()

        # 해당 세션의 모든 이벤트 조회
        result = (
            sb.table("user_events")
            .select("event_type, event_data, spot_id, created_at")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        events = result.data or []

        if not events:
            return None

        profile = {
            "category_preferences": {},
            "location_center": None,
            "active_hours": [],
            "favorite_spot_ids": [],
            "viewed_spot_ids": [],
            "session_event_count": len(events),
        }

        # spot_id가 있는 이벤트에서 관광지 정보 조회
        spot_ids = list({
            e["spot_id"] for e in events
            if e.get("spot_id") is not None
        })

        spot_map = {}
        if spot_ids:
            spots_result = (
                sb.table("tourist_spots")
                .select("id, category_id, lat, lng")
                .in_("id", spot_ids)
                .execute()
            )
            spot_map = {s["id"]: s for s in (spots_result.data or [])}

        # 카테고리 선호도 (시간 감쇠 적용)
        category_weights = defaultdict(float)
        lats, lngs, loc_weights = [], [], []
        hour_counts = defaultdict(int)
        favorite_ids = set()
        viewed_ids = set()

        for event in events:
            event_type = event.get("event_type", "")
            spot_id = event.get("spot_id")
            created_at_str = event.get("created_at", "")

            # 이벤트 시간 파싱
            event_time = _parse_timestamp(created_at_str)

            # 활동 시간대 수집
            if event_time:
                hour_counts[event_time.hour] += 1

            # 관광지 관련 이벤트 처리
            if spot_id and event_type in _INTERACTION_EVENTS:
                spot_info = spot_map.get(spot_id)
                if not spot_info:
                    continue

                weight = time_decay_weight(event_time) if event_time else 0.5

                # 이벤트 타입별 가중치
                type_weight = _event_type_weight(event_type)
                combined_weight = weight * type_weight

                # 카테고리 집계
                category = spot_info.get("category_id")
                if category:
                    category_weights[category] += combined_weight

                # 위치 집계
                lat = spot_info.get("lat")
                lng = spot_info.get("lng")
                if lat and lng:
                    lats.append(lat)
                    lngs.append(lng)
                    loc_weights.append(combined_weight)

                # 상세 조회한 관광지 추적
                if event_type in ("detail_view", "detail_leave"):
                    viewed_ids.add(spot_id)

                # 즐겨찾기 추적
                if event_type == "favorite":
                    action = (event.get("event_data") or {}).get("action")
                    if action == "add":
                        favorite_ids.add(spot_id)
                    elif action == "remove":
                        favorite_ids.discard(spot_id)

        # 카테고리 선호도 정규화
        total_cat_weight = sum(category_weights.values())
        if total_cat_weight > 0:
            profile["category_preferences"] = {
                cat: round(w / total_cat_weight, 3)
                for cat, w in sorted(
                    category_weights.items(), key=lambda x: x[1], reverse=True
                )
            }

        # 위치 중심점 (가중 평균)
        if lats and lngs:
            total_loc_weight = sum(loc_weights)
            if total_loc_weight > 0:
                avg_lat = sum(la * w for la, w in zip(lats, loc_weights)) / total_loc_weight
                avg_lng = sum(ln * w for ln, w in zip(lngs, loc_weights)) / total_loc_weight
                profile["location_center"] = {
                    "lat": round(avg_lat, 4),
                    "lng": round(avg_lng, 4),
                }

        # 활동 시간대 (상위 3개)
        if hour_counts:
            top_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            profile["active_hours"] = [h for h, _ in top_hours]

        profile["favorite_spot_ids"] = list(favorite_ids)
        profile["viewed_spot_ids"] = list(viewed_ids)

        return profile


def _event_type_weight(event_type: str) -> float:
    """이벤트 타입별 상호작용 강도 가중치"""
    weights = {
        "favorite": 3.0,
        "share": 2.5,
        "detail_view": 2.0,
        "detail_leave": 1.5,
        "spot_click": 1.0,
    }
    return weights.get(event_type, 1.0)


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    """ISO 8601 타임스탬프 문자열 파싱"""
    if not ts_str:
        return None
    try:
        # Supabase의 ISO 형식 처리
        ts_str = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None
