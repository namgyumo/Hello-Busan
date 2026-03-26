"""
쾌적도 종합 점수 계산기
- crowd_data + weather_data + transport_data → comfort_scores
- 스케줄러에서 주기적 호출 (혼잡도 수집 직후)
"""
from typing import Dict, List, Optional
from backend.db.supabase import get_supabase
from backend.services.comfort import ComfortService, COMFORT_WEIGHTS, _get_grade
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ScoreCalculator:
    """쾌적도 종합 점수 계산 + comfort_scores 테이블 갱신"""

    async def calculate_all(self) -> int:
        """
        모든 활성 관광지의 comfort_scores 재계산
        Returns: 갱신된 레코드 수
        """
        sb = get_supabase()

        # 1) 활성 관광지 목록
        spots = (
            sb.table("tourist_spots")
            .select("id")
            .eq("is_active", True)
            .execute()
        )
        if not spots.data:
            logger.warning("활성 관광지 없음")
            return 0

        # 2) 최신 혼잡도 데이터 조회
        crowd_map = await self._get_latest_crowd()

        # 3) 최신 날씨 데이터 조회
        weather = await self._get_latest_weather()

        # 4) 교통 접근성 데이터 조회
        transport_map = await self._get_transport_scores()

        # 5) 각 관광지별 종합 점수 계산 + 저장
        updated = 0
        now = datetime.now().isoformat()

        for spot in spots.data:
            spot_id = str(spot["id"])

            # 혼잡도 → 쾌적도 점수 변환 (crowd_ratio 0%=여유, 100%=혼잡 → 점수 100=여유, 0=혼잡)
            crowd_ratio = crowd_map.get(spot_id, {}).get("crowd_ratio", 50.0)
            crowd_score = int(max(0, 100 - crowd_ratio))

            # 날씨 점수 (온도+습도+강수 기반)
            weather_score = self._calc_weather_score(weather)

            # 교통 점수 (transit_score: 이미 0~100)
            transport_score = transport_map.get(spot_id, {}).get("transit_score", 50)

            # 종합 쾌적도 점수
            total_score = ComfortService.calc_comfort_score(
                weather_score=weather_score,
                crowd_score=crowd_score,
                transport_score=transport_score,
            )

            grade = _get_grade(total_score)

            try:
                sb.table("comfort_scores").upsert(
                    {
                        "spot_id": spot_id,
                        "total_score": total_score,
                        "weather_score": weather_score,
                        "crowd_score": crowd_score,
                        "transport_score": transport_score,
                        "grade": grade,
                        "timestamp": now,
                    },
                    on_conflict="spot_id",
                ).execute()
                updated += 1
            except Exception as e:
                logger.error(f"comfort_scores 저장 실패 [{spot_id}]: {e}")

        logger.info(f"comfort_scores {updated}건 갱신")
        return updated

    async def _get_latest_crowd(self) -> Dict[str, Dict]:
        """최신 혼잡도 데이터 조회 (spot_id → {crowd_ratio})"""
        sb = get_supabase()
        try:
            # spot_id별 최신 1건씩 조회
            result = (
                sb.table("crowd_data")
                .select("spot_id, crowd_level, crowd_ratio")
                .order("timestamp", desc=True)
                .execute()
            )
            crowd_map = {}
            for row in (result.data or []):
                sid = str(row.get("spot_id", ""))
                if sid not in crowd_map:  # 최신 1건만
                    crowd_map[sid] = {
                        "crowd_level": row.get("crowd_level", "보통"),
                        "crowd_ratio": row.get("crowd_ratio", 50.0),
                    }
            return crowd_map
        except Exception as e:
            logger.error(f"혼잡도 조회 실패: {e}")
            return {}

    async def _get_latest_weather(self) -> Dict:
        """최신 날씨 데이터 (부산 전체 공통 1건)"""
        sb = get_supabase()
        try:
            result = (
                sb.table("weather_data")
                .select("*")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
            return {}
        except Exception as e:
            logger.error(f"날씨 조회 실패: {e}")
            return {}

    async def _get_transport_scores(self) -> Dict[str, Dict]:
        """교통 접근성 데이터 (spot_id → {transit_score})"""
        sb = get_supabase()
        try:
            result = (
                sb.table("transport_data")
                .select("spot_id, transit_score")
                .order("timestamp", desc=True)
                .execute()
            )
            transport_map = {}
            for row in (result.data or []):
                sid = str(row["spot_id"])
                if sid not in transport_map:
                    transport_map[sid] = {"transit_score": row.get("transit_score", 50)}
            return transport_map
        except Exception as e:
            logger.error(f"교통 조회 실패: {e}")
            return {}

    def _calc_weather_score(self, weather: Dict) -> int:
        """
        날씨 → 쾌적도 점수 (0~100)
        - 기온: 18~25도 최적, 극한 온도일수록 감점
        - 습도: 40~60% 최적, 높을수록 감점
        - 강수: 있으면 크게 감점
        - 하늘: 맑음 > 구름많음 > 흐림
        """
        if not weather:
            return 60  # 기본값

        temp = float(weather.get("temperature", 20))
        humidity = float(weather.get("humidity", 50))
        rain_type = str(weather.get("rain_type", "없음"))
        sky = str(weather.get("sky_code", "1"))

        # 기온 점수 (18~25 최적, 100점)
        if 18 <= temp <= 25:
            temp_score = 100
        elif 10 <= temp < 18 or 25 < temp <= 30:
            temp_score = 70
        elif 5 <= temp < 10 or 30 < temp <= 35:
            temp_score = 40
        else:
            temp_score = 20

        # 습도 점수
        if 40 <= humidity <= 60:
            humidity_score = 100
        elif 30 <= humidity < 40 or 60 < humidity <= 70:
            humidity_score = 80
        elif 70 < humidity <= 80:
            humidity_score = 50
        else:
            humidity_score = 30

        # 강수 점수
        rain_score = 100
        if rain_type not in ("없음", "0"):
            rain_score = 20  # 비/눈 시 큰 감점

        # 하늘 점수
        sky_scores = {"1": 100, "3": 70, "4": 50}
        sky_score = sky_scores.get(sky, 60)

        # 종합 날씨 점수 (기온 40%, 습도 20%, 강수 25%, 하늘 15%)
        total = (
            temp_score * 0.40
            + humidity_score * 0.20
            + rain_score * 0.25
            + sky_score * 0.15
        )
        return int(total)
