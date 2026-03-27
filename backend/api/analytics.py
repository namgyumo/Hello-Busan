"""
사용자 행동 로그 수집 API — POST /api/v1/analytics/events
배치 전송 지원 + IP 기반 간단한 rate limiting
"""
import time
import logging

from fastapi import APIRouter, Request, HTTPException

from backend.models.analytics import EventBatchRequest, EventBatchResponse
from backend.models.common import SuccessResponse
from backend.db.supabase import get_supabase

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)

# IP 기반 간단한 rate limiting (메모리 기반)
# {ip: [timestamp, timestamp, ...]}
_rate_limit_store: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW = 60  # 60초
RATE_LIMIT_MAX = 30     # 윈도우당 최대 요청 수


_last_cleanup = time.time()
_CLEANUP_INTERVAL = 300  # 5분마다 전체 정리


def _check_rate_limit(client_ip: str) -> bool:
    """IP 기반 rate limit 확인. True = 허용, False = 차단"""
    global _last_cleanup
    now = time.time()

    # 주기적으로 오래된 IP 엔트리 전체 정리 (메모리 누수 방지)
    if now - _last_cleanup > _CLEANUP_INTERVAL:
        stale_ips = [
            ip for ip, ts_list in _rate_limit_store.items()
            if not ts_list or now - max(ts_list) > RATE_LIMIT_WINDOW
        ]
        for ip in stale_ips:
            del _rate_limit_store[ip]
        _last_cleanup = now

    # defaultdict 접근 전에 존재 여부 확인하여 빈 리스트 자동생성 방지
    timestamps = _rate_limit_store.get(client_ip, [])

    # 윈도우 밖의 오래된 타임스탬프 제거
    timestamps = [ts for ts in timestamps if now - ts < RATE_LIMIT_WINDOW]

    if len(timestamps) >= RATE_LIMIT_MAX:
        _rate_limit_store[client_ip] = timestamps
        return False

    timestamps.append(now)
    _rate_limit_store[client_ip] = timestamps
    return True


@router.post("/events")
async def collect_events(request: Request, body: EventBatchRequest):
    """사용자 행동 이벤트 배치 수집

    - 최대 50개 이벤트를 한번에 전송
    - IP 기반 rate limiting (60초당 30회)
    - 개인정보 패턴 자동 필터링 (모델 레벨)
    - IP 주소는 저장하지 않음
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )

    try:
        sb = get_supabase()

        # 배치 삽입용 데이터 변환
        rows = []
        for event in body.events:
            row = {
                "session_id": event.session_id,
                "event_type": event.event_type.value,
                "event_data": event.event_data,
                "page": event.page,
            }
            if event.spot_id is not None:
                row["spot_id"] = event.spot_id
            rows.append(row)

        # Supabase 배치 삽입
        sb.table("user_events").insert(rows).execute()

        session_preview = body.events[0].session_id[:8] if body.events else "unknown"
        logger.debug(f"이벤트 {len(rows)}건 수집 완료 (session: {session_preview}...)")

        return SuccessResponse(
            data=EventBatchResponse(accepted=len(rows)).model_dump()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이벤트 수집 실패: {e}")
        # 이벤트 수집 실패는 사용자 경험에 영향을 주면 안 되므로 200 반환
        return SuccessResponse(
            data=EventBatchResponse(accepted=0, message="failed").model_dump()
        )
