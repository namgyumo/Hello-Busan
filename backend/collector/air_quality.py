"""
대기질 데이터 수집기
- 에어코리아 실시간 측정정보 API (getMsrstnAcctoRltmMesureDnsty)
- 부산 주요 측정소별 PM10, PM2.5, O3, NO2, CO, SO2, 통합대기환경지수(CAI)
"""
from typing import Dict, List, Optional
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 부산 주요 대기질 측정소 (에어코리아 측정소명)
BUSAN_STATIONS = [
    "연산동",    # 연제구
    "좌동",      # 해운대구
    "덕천동",    # 북구
    "대연동",    # 남구
    "광복동",    # 중구
    "대저동",    # 강서구
    "학장동",    # 사상구
    "장림동",    # 사하구
    "전포동",    # 부산진구
    "수영동",    # 수영구
]


class AirQualityCollector(BaseCollector):
    """에어코리아 대기질 수집기 (부산 측정소)"""

    def __init__(self):
        super().__init__(
            api_key=settings.DATA_API_KEY,
            base_url="http://apis.data.go.kr/B552584/ArpltnInforInqireSvc",
        )

    async def collect(self) -> List[Dict]:
        """부산 측정소별 실시간 대기질 수집"""
        all_data: List[Dict] = []

        for station in BUSAN_STATIONS:
            params = {
                "stationName": station,
                "dataTerm": "DAILY",
                "pageNo": "1",
                "numOfRows": "1",
                "returnType": "json",
                "ver": "1.3",
            }

            body = await self.fetch(
                "/getMsrstnAcctoRltmMesureDnsty", params=params
            )
            if not body:
                logger.warning(f"대기질 수집 실패: {station}")
                continue

            items = body.get("items", [])
            if not items:
                logger.warning(f"대기질 데이터 없음: {station}")
                continue

            item = items[0] if isinstance(items, list) else items
            parsed = self._parse_air_quality(item, station)
            if parsed:
                all_data.append(parsed)

        return all_data

    def _parse_air_quality(self, item: Dict, station: str) -> Optional[Dict]:
        """측정 데이터 파싱"""
        try:
            return {
                "station_name": station,
                "data_time": item.get("dataTime", ""),
                "pm10_value": _safe_float(item.get("pm10Value")),
                "pm10_grade": _safe_int(item.get("pm10Grade")),
                "pm25_value": _safe_float(item.get("pm25Value")),
                "pm25_grade": _safe_int(item.get("pm25Grade")),
                "o3_value": _safe_float(item.get("o3Value")),
                "o3_grade": _safe_int(item.get("o3Grade")),
                "no2_value": _safe_float(item.get("no2Value")),
                "no2_grade": _safe_int(item.get("no2Grade")),
                "co_value": _safe_float(item.get("coValue")),
                "co_grade": _safe_int(item.get("coGrade")),
                "so2_value": _safe_float(item.get("so2Value")),
                "so2_grade": _safe_int(item.get("so2Grade")),
                "khai_value": _safe_float(item.get("khaiValue")),
                "khai_grade": _safe_int(item.get("khaiGrade")),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"대기질 파싱 실패 ({station}): {e}")
            return None

    async def save(self, data: List[Dict]) -> int:
        """대기질 데이터 저장"""
        sb = get_supabase()
        saved = 0

        for item in data:
            try:
                sb.table("air_quality_data").insert(item).execute()
                saved += 1
            except Exception as e:
                logger.error(f"대기질 저장 실패 ({item.get('station_name')}): {e}")

        return saved


def _safe_float(value) -> Optional[float]:
    """안전한 float 변환 (측정불가 '-' 처리)"""
    if value is None or value == "-" or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value) -> Optional[int]:
    """안전한 int 변환"""
    if value is None or value == "-" or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
