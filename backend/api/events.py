"""
SSE 이벤트 + 히트맵 + 축제/이벤트 캘린더 API 라우터
— API 설계서 API-007, API-008, 축제 캘린더
"""
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import date, datetime
from backend.models.common import SuccessResponse, Meta
from backend.models.comfort import HeatmapConfig
from backend.services.comfort import ComfortService
from backend.cache.manager import CacheManager
from backend.db.supabase import get_supabase
import asyncio
import json
import logging

router = APIRouter(prefix="/api/v1", tags=["events"])
logger = logging.getLogger(__name__)
comfort_service = ComfortService()
cache = CacheManager()

# SSE 연결 관리
active_connections: list = []


@router.get("/heatmap")
async def get_heatmap():
    """[API-007] 히트맵 데이터 조회"""
    cache_key = "heatmap:all"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()
        spots = sb.table("tourist_spots").select("id, lat, lng").eq("is_active", True).execute()

        spot_ids = [str(s["id"]) for s in (spots.data or [])]
        comfort_data = await comfort_service.get_bulk_comfort(spot_ids)

        points = []
        for s in (spots.data or []):
            sid = str(s["id"])
            c = comfort_data.get(sid, {})
            crowd_score = c.get("crowd_score", 50)
            if crowd_score is None:
                crowd_score = 50
            # intensity: 0(쾌적) ~ 1(매우혼잡)
            intensity = round(1 - (crowd_score / 100), 2)
            points.append([s["lat"], s["lng"], intensity])

        response = SuccessResponse(
            data={
                "points": points,
                "config": HeatmapConfig().model_dump(),
            },
            meta=Meta(total=len(points)),
        )

        await cache.set(cache_key, response.model_dump(), ttl=60)
        return response

    except Exception as e:
        logger.error(f"히트맵 데이터 조회 실패: {e}")
        return SuccessResponse(
            data={"points": [], "config": HeatmapConfig().model_dump()},
            meta=Meta(fallback_used=True),
        )


@router.get("/events")
async def stream_events(request: Request):
    """[API-008] SSE 실시간 갱신 스트림"""
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _event_generator(request: Request):
    """SSE 이벤트 생성기"""
    queue = asyncio.Queue()
    active_connections.append(queue)

    try:
        # 하트비트 먼저
        yield f"event: heartbeat\ndata: {{}}\n\n"

        while True:
            if await request.is_disconnected():
                break

            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"event: {data['event']}\ndata: {json.dumps(data['data'], ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield f"event: heartbeat\ndata: {{}}\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        if queue in active_connections:
            active_connections.remove(queue)
        logger.debug(f"SSE 연결 종료. 활성: {len(active_connections)}")


async def broadcast_update(event_type: str, data: dict):
    """모든 SSE 연결에 이벤트 브로드캐스트"""
    for queue in list(active_connections):
        try:
            await queue.put({"event": event_type, "data": data})
        except Exception:
            pass


# ─── 축제/이벤트 캘린더 API ───

@router.get("/events/festivals")
async def get_festivals(
    year: Optional[int] = Query(None, ge=2020, le=2030, description="연도"),
    month: Optional[int] = Query(None, ge=1, le=12, description="월"),
    status: Optional[str] = Query(None, description="상태 필터: ongoing, upcoming, ended"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """축제/이벤트 캘린더 목록 조회"""
    today = date.today().isoformat()
    cache_key = f"festivals:{year}:{month}:{status}:{limit}:{offset}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        sb = get_supabase()
        query = sb.table("festivals").select("*").eq("is_active", True)

        # 월별 필터: 해당 월에 진행 중인 축제 (시작일 <= 월말 AND 종료일 >= 월초)
        if year and month:
            month_start = f"{year}-{month:02d}-01"
            if month == 12:
                month_end = f"{year + 1}-01-01"
            else:
                month_end = f"{year}-{month + 1:02d}-01"
            query = query.or_(
                f"event_start_date.is.null,"
                f"event_start_date.lt.{month_end}"
            )
            query = query.or_(
                f"event_end_date.is.null,"
                f"event_end_date.gte.{month_start}"
            )

        result = query.order("event_start_date", desc=False).execute()
        festivals = result.data or []

        # 상태 계산 및 필터
        items = []
        for f in festivals:
            start = f.get("event_start_date")
            end = f.get("event_end_date")
            f_status = _compute_status(start, end, today)
            f["status"] = f_status

            if status and f_status != status:
                continue
            items.append(f)

        total = len(items)
        paged = items[offset:offset + limit]

        # 응답 형식 정리
        data = []
        for f in paged:
            images = f.get("images", []) if isinstance(f.get("images"), list) else []
            data.append({
                "id": f.get("id"),
                "content_id": f.get("content_id", ""),
                "title": f.get("title", ""),
                "address": f.get("address", ""),
                "lat": f.get("lat"),
                "lng": f.get("lng"),
                "thumbnail": images[0] if images else "",
                "images": images,
                "phone": f.get("phone", ""),
                "description": f.get("description", ""),
                "homepage": f.get("homepage", ""),
                "event_start_date": f.get("event_start_date"),
                "event_end_date": f.get("event_end_date"),
                "event_place": f.get("event_place", ""),
                "sponsor": f.get("sponsor", ""),
                "use_time": f.get("use_time", ""),
                "status": f.get("status", "unknown"),
            })

        response = SuccessResponse(
            data=data,
            meta=Meta(total=total, limit=limit, offset=offset),
        )

        await cache.set(cache_key, response.model_dump(), ttl=300)
        return response

    except Exception as e:
        logger.error(f"축제 목록 조회 실패: {e}")
        return SuccessResponse(
            data=[],
            meta=Meta(total=0, fallback_used=True),
        )


def _compute_status(start: Optional[str], end: Optional[str], today: str) -> str:
    """축제 상태 계산: ongoing, upcoming, ended"""
    if not start and not end:
        return "unknown"
    if start and today < start:
        return "upcoming"
    if end and today > end:
        return "ended"
    return "ongoing"
