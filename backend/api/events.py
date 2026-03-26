"""
SSE 이벤트 스트리밍 API 라우터
- 실시간 쾌적도 업데이트
- 히트맵 데이터 스트리밍
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from backend.services.comfort import ComfortService
from backend.db.supabase import get_supabase
import asyncio
import json
import logging

router = APIRouter(prefix="/api/v1/events", tags=["events"])
logger = logging.getLogger(__name__)
comfort_service = ComfortService()

# SSE 연결 관리
active_connections: list = []


async def event_generator(request: Request):
    """SSE 이벤트 생성기"""
    queue = asyncio.Queue()
    active_connections.append(queue)

    try:
        # 초기 데이터 전송
        initial_data = await comfort_service.get_dashboard()
        yield f"event: comfort_update\ndata: {json.dumps(initial_data.dict(), ensure_ascii=False)}\n\n"

        # 히트맵 초기 데이터
        heatmap_data = await _get_heatmap_data()
        yield f"event: heatmap_update\ndata: {json.dumps(heatmap_data, ensure_ascii=False)}\n\n"

        while True:
            if await request.is_disconnected():
                break

            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"event: {data['event']}\ndata: {json.dumps(data['data'], ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                # 30초마다 keep-alive
                yield f": keep-alive\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        active_connections.remove(queue)
        logger.info(f"SSE 연결 종료. 활성 연결: {len(active_connections)}")


@router.get("/stream")
async def stream_events(request: Request):
    """SSE 스트림 엔드포인트"""
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def broadcast_event(event_type: str, data: dict):
    """모든 연결에 이벤트 브로드캐스트"""
    for queue in active_connections:
        await queue.put({"event": event_type, "data": data})


async def _get_heatmap_data() -> list:
    """히트맵용 혼잡도 데이터"""
    sb = get_supabase()
    result = (
        sb.table("spots")
        .select("id, name, lat, lng")
        .execute()
    )

    comfort_data = await comfort_service.get_bulk_comfort(
        [s["id"] for s in result.data]
    )

    heatmap = []
    for spot in result.data:
        comfort = comfort_data.get(spot["id"], {})
        heatmap.append({
            "lat": spot["lat"],
            "lng": spot["lng"],
            "intensity": comfort.get("crowd_level", 0.5),
            "name": spot["name"],
        })
    return heatmap


@router.get("/status")
async def get_sse_status():
    """SSE 연결 상태"""
    return {
        "active_connections": len(active_connections),
        "status": "healthy",
    }
