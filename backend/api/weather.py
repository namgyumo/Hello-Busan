"""
날씨 API — 현재 날씨 조회 엔드포인트
GET /api/v1/weather/current
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter
from backend.db.supabase import get_supabase
from backend.models.common import SuccessResponse, ErrorResponse, ErrorDetail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


@router.get("/current")
async def get_current_weather():
    """현재 부산 날씨 정보 반환"""
    try:
        sb = get_supabase()

        # 최근 6시간 이내 데이터 조회
        since = (datetime.now() - timedelta(hours=6)).isoformat()
        result = (
            sb.table("weather_data")
            .select("*")
            .gte("timestamp", since)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if result.data and len(result.data) > 0:
            row = result.data[0]
            sky_code = str(row.get("sky_code", "1"))
            rain_type = row.get("rain_type", "없음")
            temperature = row.get("temperature", 0)
            humidity = row.get("humidity", 0)
            wind_speed = row.get("wind_speed", 0)

            # 날씨 상태 판별
            condition = _determine_condition(sky_code, rain_type, temperature)

            return SuccessResponse(
                data={
                    "sky": sky_code,
                    "sky_text": _sky_text(sky_code),
                    "pty": rain_type,
                    "tmp": temperature,
                    "humidity": humidity,
                    "wind_speed": wind_speed,
                    "condition": condition,
                    "timestamp": row.get("timestamp"),
                }
            )

        # 데이터가 없을 경우 기본값 반환
        return SuccessResponse(
            data={
                "sky": "1",
                "sky_text": "맑음",
                "pty": "없음",
                "tmp": 20,
                "humidity": 50,
                "wind_speed": 2.0,
                "condition": "clear_cool",
                "timestamp": None,
            },
            meta={"fallback_used": True},
        )

    except Exception as e:
        logger.error(f"날씨 조회 실패: {e}")
        # 에러 시에도 기본값 반환 (프론트엔드가 배너를 표시할 수 있도록)
        return SuccessResponse(
            data={
                "sky": "1",
                "sky_text": "맑음",
                "pty": "없음",
                "tmp": 20,
                "humidity": 50,
                "wind_speed": 2.0,
                "condition": "clear_cool",
                "timestamp": None,
            },
            meta={"fallback_used": True},
        )


def _sky_text(code: str) -> str:
    """하늘 상태 코드 -> 텍스트"""
    return {"1": "맑음", "3": "구름많음", "4": "흐림"}.get(code, "알 수 없음")


def _determine_condition(sky: str, rain_type: str, tmp: float) -> str:
    """
    날씨 조건 판별 → 프론트엔드 배너 로직에 사용
    - rain: 비/눈
    - clear_hot: 맑음 + 더움 (28도 이상)
    - clear_cool: 맑음 + 선선
    - cloudy: 흐림
    """
    if rain_type not in ("없음", "0", "", None):
        return "rain"
    if sky == "4":
        return "cloudy"
    if sky in ("1", "3") and tmp >= 28:
        return "clear_hot"
    return "clear_cool"
