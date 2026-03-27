"""
기상 데이터 수집기
- 기상청 단기예보 API
- 부산 5개 권역별 날씨 정보
"""
from typing import Dict, List, Optional, Tuple
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
from backend.regions import REGION_GRID
import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _safe_float(val, default: float = 0.0) -> float:
    """None이나 빈 문자열에도 안전한 float 변환"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class WeatherCollector(BaseCollector):
    """기상청 날씨 수집기 (부산 5개 권역)"""

    def __init__(self):
        super().__init__(
            api_key=settings.WEATHER_API_KEY,
            base_url="http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0",
        )

    async def collect(self) -> List[Dict]:
        """5개 권역별 단기예보 수집"""
        now = datetime.now()
        base_time = self._get_base_time(now)
        # base_time이 "2300"이고 현재 시각이 02시 이전이면 전날 발표분 사용
        if base_time == "2300" and now.hour < 2:
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        else:
            base_date = now.strftime("%Y%m%d")

        all_weather: List[Dict] = []

        for region_code, grid in REGION_GRID.items():
            params = {
                "numOfRows": "100",
                "pageNo": "1",
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": grid["nx"],
                "ny": grid["ny"],
            }

            body = await self.fetch("/getVilageFcst", params=params)
            if not body:
                logger.warning(f"날씨 수집 실패: {region_code}")
                continue

            items = body.get("items", {}).get("item", [])
            weather_data = self._parse_weather(items, region_code)
            all_weather.extend(weather_data)

        return all_weather

    def _get_base_time(self, now: datetime) -> str:
        """가장 최근 발표 시각"""
        base_times = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]
        current = now.strftime("%H%M")

        for bt in reversed(base_times):
            if current >= bt:
                return bt
        return "2300"

    def _parse_weather(self, items: list, region_code: str = "haeundae") -> List[Dict]:
        """날씨 데이터 파싱 (권역 코드 포함)"""
        grouped = {}
        for item in items:
            fcst_date = item.get("fcstDate")
            fcst_time = item.get("fcstTime")
            category = item.get("category")
            if not fcst_date or not fcst_time or not category:
                continue
            key = f"{fcst_date}_{fcst_time}"
            if key not in grouped:
                grouped[key] = {
                    "forecast_date": fcst_date,
                    "forecast_time": fcst_time,
                }
            grouped[key][category] = item.get("fcstValue")

        result = []
        for key, data in grouped.items():
            pty = data.get("PTY", "0")
            rain_type_map = {"0": "없음", "1": "비", "2": "비+눈", "3": "눈", "4": "소나기"}
            pcp = data.get("PCP") or "0"
            rain_amount = 0.0
            if pcp and pcp not in ("강수없음", "0"):
                try:
                    # "1mm미만" → 0.5, "30~50mm" → 40, "50mm이상" → 50
                    cleaned = pcp.replace("mm", "").replace("미만", "").replace("이상", "").strip()
                    range_match = re.match(r'(\d+)~(\d+)', cleaned)
                    if range_match:
                        rain_amount = (float(range_match.group(1)) + float(range_match.group(2))) / 2
                    elif cleaned:
                        rain_amount = float(cleaned)
                        if "미만" in pcp:
                            rain_amount = rain_amount * 0.5
                except (ValueError, TypeError):
                    rain_amount = 0.0

            weather = {
                "region_code": region_code,
                "temperature": _safe_float(data.get("TMP"), 0.0),
                "sky_code": data.get("SKY") or "1",
                "rain_type": rain_type_map.get(pty, "없음"),
                "rain_amount": rain_amount,
                "humidity": int(_safe_float(data.get("REH"), 0.0)),
                "wind_speed": _safe_float(data.get("WSD"), 0.0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            result.append(weather)

        return result

    async def save(self, data: List[Dict]) -> int:
        """날씨 데이터 저장"""
        sb = get_supabase()
        saved = 0

        for item in data:
            try:
                sb.table("weather_data").insert(item).execute()
                saved += 1
            except Exception as e:
                logger.error(f"날씨 저장 실패: {e}")

        return saved

    def get_sky_text(self, code: str) -> str:
        """하늘 상태 코드 -> 텍스트"""
        sky_map = {"1": "맑음", "3": "구름많음", "4": "흐림"}
        return sky_map.get(code, "알 수 없음")
