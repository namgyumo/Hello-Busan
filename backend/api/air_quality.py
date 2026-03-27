"""
대기질 API — 부산 실시간 대기질 정보
GET /api/v1/air-quality
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter
from backend.db.supabase import get_supabase
from backend.models.common import SuccessResponse, Meta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/air-quality", tags=["air-quality"])

# 통합대기환경지수(CAI) 등급 텍스트
GRADE_TEXT = {1: "좋음", 2: "보통", 3: "나쁨", 4: "매우나쁨"}


@router.get("")
async def get_air_quality():
    """
    부산 현재 대기질 정보 반환

    - 측정소별 최신 데이터
    - 부산 전체 평균 요약
    """
    try:
        sb = get_supabase()

        # 최근 3시간 이내 데이터 조회
        since = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = (
            sb.table("air_quality_data")
            .select("*")
            .gte("timestamp", since)
            .order("timestamp", desc=True)
            .execute()
        )

        rows = result.data or []

        if rows:
            # 측정소별 최신 데이터만 추출
            station_latest = _get_latest_per_station(rows)
            stations = list(station_latest.values())

            # 부산 전체 평균 계산
            summary = _calc_summary(stations)

            return SuccessResponse(
                data={
                    "summary": summary,
                    "stations": stations,
                }
            )

        # 데이터 없으면 기본값 반환
        return SuccessResponse(
            data={
                "summary": _fallback_summary(),
                "stations": [],
            },
            meta=Meta(fallback_used=True),
        )

    except Exception as e:
        logger.error(f"대기질 조회 실패: {e}")
        return SuccessResponse(
            data={
                "summary": _fallback_summary(),
                "stations": [],
            },
            meta=Meta(fallback_used=True),
        )


def _get_latest_per_station(rows: List[Dict]) -> Dict[str, Dict]:
    """측정소별 최신 데이터 추출 (timestamp 내림차순 정렬 전제)"""
    latest: Dict[str, Dict] = {}
    for row in rows:
        station = row.get("station_name", "")
        if station and station not in latest:
            latest[station] = {
                "station_name": station,
                "data_time": row.get("data_time"),
                "pm10_value": row.get("pm10_value"),
                "pm10_grade": row.get("pm10_grade"),
                "pm10_grade_text": GRADE_TEXT.get(row.get("pm10_grade"), "-"),
                "pm25_value": row.get("pm25_value"),
                "pm25_grade": row.get("pm25_grade"),
                "pm25_grade_text": GRADE_TEXT.get(row.get("pm25_grade"), "-"),
                "o3_value": row.get("o3_value"),
                "o3_grade": row.get("o3_grade"),
                "no2_value": row.get("no2_value"),
                "co_value": row.get("co_value"),
                "so2_value": row.get("so2_value"),
                "khai_value": row.get("khai_value"),
                "khai_grade": row.get("khai_grade"),
                "khai_grade_text": GRADE_TEXT.get(row.get("khai_grade"), "-"),
                "timestamp": row.get("timestamp"),
            }
    return latest


def _calc_summary(stations: List[Dict]) -> Dict:
    """부산 전체 평균 대기질 요약"""
    pm10_vals = [s["pm10_value"] for s in stations if s.get("pm10_value") is not None]
    pm25_vals = [s["pm25_value"] for s in stations if s.get("pm25_value") is not None]
    khai_vals = [s["khai_value"] for s in stations if s.get("khai_value") is not None]

    avg_pm10 = round(sum(pm10_vals) / len(pm10_vals), 1) if pm10_vals else None
    avg_pm25 = round(sum(pm25_vals) / len(pm25_vals), 1) if pm25_vals else None
    avg_khai = round(sum(khai_vals) / len(khai_vals)) if khai_vals else None

    # 전체 등급: 최빈 khai_grade 또는 평균 기반
    khai_grades = [s["khai_grade"] for s in stations if s.get("khai_grade") is not None]
    overall_grade = _most_common(khai_grades) if khai_grades else 2

    return {
        "city": "부산",
        "avg_pm10": avg_pm10,
        "avg_pm25": avg_pm25,
        "avg_khai": avg_khai,
        "overall_grade": overall_grade,
        "overall_grade_text": GRADE_TEXT.get(overall_grade, "보통"),
        "station_count": len(stations),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _fallback_summary() -> Dict:
    """데이터 없을 때 기본 요약"""
    return {
        "city": "부산",
        "avg_pm10": None,
        "avg_pm25": None,
        "avg_khai": None,
        "overall_grade": None,
        "overall_grade_text": "-",
        "station_count": 0,
        "timestamp": None,
    }


def _most_common(items: list):
    """리스트에서 가장 빈번한 값"""
    if not items:
        return None
    counts: Dict = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return max(counts, key=counts.get)
