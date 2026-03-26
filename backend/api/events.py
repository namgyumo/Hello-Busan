"""
SSE 이벤트 + 히트맵 API 라우터 — API 설계서 API-007, API-008
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
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
            # intensity: 0(쾌적) ~ 1(매우혼잡)
            intensity = round(1 - (crowd_score / 100), 2) if crowd_score else 0.5
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
    for queue in active_connections:
        try:
            await queue.put({"event": event_type, "data": data})
        except Exception:
            pass
