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
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


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
        base_date = now.strftime("%Y%m%d")
        base_time = self._get_base_time(now)

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
            key = f"{item['fcstDate']}_{item['fcstTime']}"
            if key not in grouped:
                grouped[key] = {
                    "forecast_date": item["fcstDate"],
                    "forecast_time": item["fcstTime"],
                }
            grouped[key][item["category"]] = item["fcstValue"]

        result = []
        for key, data in grouped.items():
            pty = data.get("PTY", "0")
            rain_type_map = {"0": "없음", "1": "비", "2": "비+눈", "3": "눈", "4": "소나기"}
            pcp = data.get("PCP", "0")
            rain_amount = 0.0
            if pcp and pcp not in ("강수없음", "0"):
                try:
                    rain_amount = float(pcp.replace("mm", "").strip())
                except ValueError:
                    rain_amount = 0.0

            weather = {
                "region_code": region_code,
                "temperature": float(data.get("TMP", 0)),
                "sky_code": data.get("SKY", "1"),
                "rain_type": rain_type_map.get(pty, "없음"),
                "rain_amount": rain_amount,
                "humidity": int(float(data.get("REH", 0))),
                "wind_speed": float(data.get("WSD", 0)),
                "timestamp": datetime.now().isoformat(),
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
