"""
교통 데이터 수집기
- 부산 대중교통 정보 API
- 관광지 접근성 데이터
"""
from typing import Dict, List, Optional
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TransportCollector(BaseCollector):
    """부산 교통 정보 수집기"""

    def __init__(self):
        super().__init__(
            api_key=settings.DATA_API_KEY,
            base_url="http://apis.data.go.kr",
        )

    # 1회 수집 시 최대 API 호출 수 (일일 1000건 예산 내 관리)
    MAX_SPOTS_PER_RUN = 50

    async def collect(self) -> List[Dict]:
        """교통 데이터 수집 (API 호출 예산 관리 위해 배치 제한)"""
        spots = await self._get_spot_list()
        # 전체 spots 중 MAX_SPOTS_PER_RUN만큼만 처리 (라운드 로빈)
        batch = spots[:self.MAX_SPOTS_PER_RUN]
        transport_data = []

        for spot in batch:
            data = await self._collect_nearby_transport(spot)
            if data:
                transport_data.append(data)

        logger.info(f"교통 데이터 {len(transport_data)}/{len(spots)}건 수집 (배치 {len(batch)})")
        return transport_data

    async def _get_spot_list(self) -> List[Dict]:
        """관광지 목록 조회"""
        sb = get_supabase()
        result = sb.table("tourist_spots").select("id, name, lat, lng").eq("is_active", True).execute()
        return result.data or []

    async def _collect_nearby_transport(
        self, spot: Dict
    ) -> Optional[Dict]:
        """관광지 주변 교통 정보 수집"""
        params = {
            "numOfRows": "10",
            "pageNo": "1",
            "_type": "json",
            "gpsLati": str(spot.get("lat", 0)),
            "gpsLong": str(spot.get("lng", 0)),
        }

        body = await self.fetch(
            "/1613000/BusSttnInfoInqireService/getCrdntPrxmtSttnList",
            params=params,
        )

        # API 응답이 없으면 (403 등) 해당 spot은 건너뛰기
        if not body:
            return None

        items_wrapper = body.get("items", {})
        items = items_wrapper.get("item", []) if isinstance(items_wrapper, dict) else []
        if not isinstance(items, list):
            items = [items] if isinstance(items, dict) else []

        stations = []
        nearest_station = None
        for item in items:
            stations.append({
                "name": item.get("nodenm", ""),
                "id": item.get("nodeid", ""),
                "distance": item.get("dist", 0),
            })

        if stations:
            nearest_station = stations[0].get("name", "")

        transit_score = self._calc_accessibility(stations)

        return {
            "spot_id": spot["id"],
            "nearest_station": nearest_station,
            "bus_routes": [s.get("name", "") for s in stations],
            "transit_score": transit_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _calc_accessibility(self, stations: List[Dict]) -> int:
        """
        접근성 점수 계산 (0~100)
        - 가까운 정류장이 많을수록 높음
        """
        if not stations:
            return 0

        count_score = min(len(stations) / 5, 1.0)
        return int(count_score * 100)

    async def save(self, data: List[Dict]) -> int:
        """교통 데이터 저장"""
        sb = get_supabase()
        saved = 0

        for item in data:
            try:
                sb.table("transport_data").insert(
                    {
                        "spot_id": item["spot_id"],
                        "nearest_station": item["nearest_station"],
                        "bus_routes": item["bus_routes"],
                        "transit_score": item["transit_score"],
                        "timestamp": item["timestamp"],
                    },
                ).execute()
                saved += 1
            except Exception as e:
                logger.error(f"교통 데이터 저장 실패: {e}")

        return saved
