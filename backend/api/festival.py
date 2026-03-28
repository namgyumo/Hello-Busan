"""
축제·이벤트 캘린더 API 라우터 (JSON 파일 기반)
— /api/v1/festivals 엔드포인트
"""
import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from backend.models.common import SuccessResponse, Meta

router = APIRouter(prefix="/api/v1/festivals", tags=["festivals"])
logger = logging.getLogger(__name__)

# JSON 파일에서 축제 데이터 로드
_DATA_PATH = Path(__file__).parent.parent / "data" / "festivals.json"
_festivals: list[dict] = []


def _load_festivals() -> list[dict]:
    """축제 데이터 로드 (최초 1회 + 캐시)"""
    global _festivals
    if _festivals:
        return _festivals
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            _festivals = json.load(f)
        logger.info(f"축제 데이터 로드 완료: {len(_festivals)}건")
    except Exception as e:
        logger.error(f"축제 데이터 로드 실패: {e}")
        _festivals = []
    return _festivals


def _compute_status(start_date: str, end_date: str, today: str) -> str:
    """축제 상태 계산"""
    if not start_date and not end_date:
        return "unknown"
    if start_date and today < start_date:
        return "upcoming"
    if end_date and today > end_date:
        return "ended"
    return "ongoing"


def _enrich_festival(f: dict, today: str) -> dict:
    """축제 데이터에 status, d_day 추가"""
    start = f.get("start_date", "")
    end = f.get("end_date", "")
    status = _compute_status(start, end, today)

    d_day = None
    if start and status == "upcoming":
        diff = (date.fromisoformat(start) - date.fromisoformat(today)).days
        d_day = diff
    elif status == "ongoing":
        d_day = 0

    return {
        **f,
        "status": status,
        "d_day": d_day,
    }


@router.get("")
async def list_festivals(
    month: Optional[int] = Query(None, ge=1, le=12, description="월별 필터"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="연도"),
    category: Optional[str] = Query(None, description="카테고리: 축제, 공연, 전시, 체험"),
    ongoing: Optional[bool] = Query(None, description="진행 중인 축제만"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """축제 목록 조회 (필터: month, category, ongoing)"""
    today = date.today().isoformat()
    festivals = _load_festivals()

    items = []
    for f in festivals:
        enriched = _enrich_festival(f, today)

        # 월별 필터
        if month is not None:
            y = year or date.today().year
            month_start = f"{y}-{month:02d}-01"
            if month == 12:
                month_end = f"{y + 1}-01-01"
            else:
                month_end = f"{y}-{month + 1:02d}-01"
            start = f.get("start_date", "")
            end = f.get("end_date", "")
            start_ok = (not start) or (start < month_end)
            end_ok = (not end) or (end >= month_start)
            if not (start_ok and end_ok):
                continue

        # 카테고리 필터
        if category and f.get("category") != category:
            continue

        # 진행 중 필터
        if ongoing is True and enriched["status"] != "ongoing":
            continue

        items.append(enriched)

    total = len(items)
    paged = items[offset:offset + limit]

    return SuccessResponse(
        data=paged,
        meta=Meta(total=total, limit=limit, offset=offset),
    )


@router.get("/this-week")
async def this_week_festivals():
    """이번 주 진행 중인 축제"""
    today = date.today()
    today_str = today.isoformat()

    # 이번 주 월요일 ~ 일요일
    weekday = today.weekday()
    week_start = (today - timedelta(days=weekday)).isoformat()
    week_end = (today + timedelta(days=6 - weekday)).isoformat()

    festivals = _load_festivals()
    items = []
    for f in festivals:
        start = f.get("start_date", "")
        end = f.get("end_date", "")

        # 이번 주와 겹치는 축제: start <= week_end AND end >= week_start
        start_ok = (not start) or (start <= week_end)
        end_ok = (not end) or (end >= week_start)
        if start_ok and end_ok:
            items.append(_enrich_festival(f, today_str))

    # d_day 기준 정렬 (진행 중 먼저, 그 다음 가까운 순)
    items.sort(key=lambda x: (x["d_day"] if x["d_day"] is not None else 999))

    return SuccessResponse(
        data=items,
        meta=Meta(total=len(items)),
    )


@router.get("/upcoming")
async def upcoming_festivals():
    """다가오는 축제 (향후 30일)"""
    today = date.today()
    today_str = today.isoformat()
    future_str = (today + timedelta(days=30)).isoformat()

    festivals = _load_festivals()
    items = []
    for f in festivals:
        start = f.get("start_date", "")
        end = f.get("end_date", "")

        # 향후 30일 내 시작하거나 진행 중인 축제
        start_ok = (not start) or (start <= future_str)
        end_ok = (not end) or (end >= today_str)
        if start_ok and end_ok:
            items.append(_enrich_festival(f, today_str))

    items.sort(key=lambda x: x.get("start_date", ""))

    return SuccessResponse(
        data=items,
        meta=Meta(total=len(items)),
    )


@router.get("/{festival_id}")
async def get_festival(festival_id: str):
    """축제 상세 조회"""
    today = date.today().isoformat()
    festivals = _load_festivals()

    for f in festivals:
        if f.get("id") == festival_id:
            return SuccessResponse(data=_enrich_festival(f, today))

    return SuccessResponse(
        data=None,
        meta=Meta(fallback_used=True),
    )
