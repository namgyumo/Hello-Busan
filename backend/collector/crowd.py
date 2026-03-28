"""
혼잡도 데이터 수집기
- 부산 관광지 실시간 혼잡도 추정
- 지하철 승하차 실데이터 기반 + 시간/요일/시즌 보정
- XGBoost 혼잡도 예측 모델 블렌딩 (모델 있을 때 60%, 기존 룰 40%)
"""
from typing import Dict, List, Optional
from backend.collector.base import BaseCollector
from backend.db.supabase import get_supabase
from backend.config import settings
import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# XGBoost 혼잡도 예측기 (lazy 로드)
_crowd_predictor = None


def _get_crowd_predictor():
    """CrowdPredictor 싱글턴 (모델 없으면 None)"""
    global _crowd_predictor
    if _crowd_predictor is None:
        try:
            from backend.ml.crowd_predictor import CrowdPredictor
            _crowd_predictor = CrowdPredictor()
            if not _crowd_predictor.is_loaded:
                logger.info("혼잡도 XGBoost 모델 미로드 — 룰 기반 폴백")
                _crowd_predictor = False  # 로드 실패 마커
        except Exception as e:
            logger.warning(f"CrowdPredictor 초기화 실패: {e}")
            _crowd_predictor = False
    return _crowd_predictor if _crowd_predictor is not False else None

# 지하철 승하차 데이터 (전처리 결과)
_SUBWAY_DATA: Optional[Dict] = None
_SUBWAY_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "ml_data" / "subway_crowd_avg.json"

# 관광지명 → 가장 가까운 역 매핑 (부산 주요 관광지)
SPOT_STATION_MAP = {
    "해운대해수욕장": "해운대", "해운대": "해운대",
    "광안리해수욕장": "광안", "광안리": "광안",
    "태종대": "남포",
    "감천문화마을": "괴정",
    "자갈치시장": "자갈치", "자갈치": "자갈치",
    "남포동": "남포", "남포": "남포",
    "BIFF광장": "남포", "국제시장": "자갈치",
    "용두산공원": "남포", "부산타워": "남포",
    "벡스코": "벡스코", "BEXCO": "벡스코",
    "센텀시티": "센텀시티", "신세계백화점": "센텀시티",
    "서면": "서면", "서면시장": "서면",
    "부산역": "부산역", "부산진시장": "부산진",
    "동백섬": "동백", "동백": "동백",
    "민락수변공원": "민락", "민락": "민락",
    "송도해수욕장": "사하", "송도": "사하",
    "다대포해수욕장": "다대포해수욕장", "다대포": "다대포해수욕장",
    "기장": "장산",
    "금련산": "금련산",
    "온천장": "온천장", "동래온천": "동래", "동래": "동래",
    "충렬사": "충렬사",
    "경성대": "경성대부경대", "부경대": "경성대부경대",
    "수영": "수영",
    "이기대": "경성대부경대",
    "오륙도": "경성대부경대",
    "범어사": "범어사",
    "금정산": "범어사",
    "부산대": "부산대",
    "사직야구장": "사직", "사직": "사직",
    "연산": "연산",
    "구포": "구포", "구포시장": "구포",
    "초량": "초량",
    "중앙동": "중앙", "중앙": "중앙",
    "영도": "남포",
    "송정해수욕장": "해운대",
    "달맞이고개": "해운대",
    "장산": "장산",
    "부전시장": "부전", "부전": "부전",
    "전포카페거리": "전포", "전포": "전포",
}


def _load_subway_data() -> Dict:
    """지하철 승하차 평균 데이터 로드 (lazy, 1회만)"""
    global _SUBWAY_DATA
    if _SUBWAY_DATA is not None:
        return _SUBWAY_DATA
    try:
        with open(_SUBWAY_DATA_PATH, "r", encoding="utf-8") as f:
            _SUBWAY_DATA = json.load(f)
        logger.info(f"지하철 데이터 로드: {len(_SUBWAY_DATA)}개 역")
    except FileNotFoundError:
        logger.warning(f"지하철 데이터 파일 없음: {_SUBWAY_DATA_PATH} (규칙 기반 폴백)")
        _SUBWAY_DATA = {}
    except Exception as e:
        logger.error(f"지하철 데이터 로드 실패: {e}")
        _SUBWAY_DATA = {}
    return _SUBWAY_DATA


# 시간대별 혼잡도 가중치 (폴백용: 지하철 데이터 없는 관광지)
HOUR_WEIGHTS = {
    0: 0.05, 1: 0.03, 2: 0.02, 3: 0.02, 4: 0.02, 5: 0.05,
    6: 0.10, 7: 0.15, 8: 0.25, 9: 0.40, 10: 0.60, 11: 0.75,
    12: 0.80, 13: 0.75, 14: 0.70, 15: 0.65, 16: 0.60, 17: 0.55,
    18: 0.50, 19: 0.45, 20: 0.35, 21: 0.25, 22: 0.15, 23: 0.08,
}

# 요일별 보정 (월=0 ~ 일=6)
DAY_MULTIPLIER = {
    0: 0.7, 1: 0.7, 2: 0.7, 3: 0.75, 4: 0.85,  # 월~금
    5: 1.2, 6: 1.3,  # 토, 일
}

# 카테고리별 피크 시간대 보정
CATEGORY_PEAK = {
    "nature": {"peak_hours": range(9, 17), "multiplier": 1.2},
    "culture": {"peak_hours": range(10, 18), "multiplier": 1.1},
    "food": {"peak_hours": [11, 12, 13, 17, 18, 19, 20], "multiplier": 1.3},
    "activity": {"peak_hours": range(10, 17), "multiplier": 1.2},
    "shopping": {"peak_hours": range(13, 21), "multiplier": 1.1},
    "nightview": {"peak_hours": range(18, 24), "multiplier": 1.4},
}

# 월별 시즌 보정 (부산 관광 시즌)
SEASON_MULTIPLIER = {
    1: 0.6, 2: 0.6, 3: 0.8, 4: 0.9, 5: 1.0, 6: 1.1,
    7: 1.4, 8: 1.5, 9: 1.0, 10: 1.1, 11: 0.8, 12: 0.7,
}


class CrowdCollector(BaseCollector):
    """실시간 혼잡도 수집기"""

    def __init__(self):
        super().__init__(
            api_key=settings.DATA_API_KEY,
            base_url="http://apis.data.go.kr",
        )

    async def collect(self) -> List[Dict]:
        """혼잡도 데이터 수집"""
        spots = await self._get_spot_list()
        crowd_data = []

        now = datetime.now()

        for spot in spots:
            data = self._estimate_crowd(spot, now)
            crowd_data.append(data)

        # 공공 API 데이터가 있으면 보정
        api_data = await self._fetch_visitor_api()
        if api_data:
            self._apply_api_correction(crowd_data, api_data)

        logger.info(f"혼잡도 데이터 {len(crowd_data)}건 수집")
        return crowd_data

    async def _get_spot_list(self) -> List[Dict]:
        """모니터링 대상 관광지 목록"""
        sb = get_supabase()
        result = (
            sb.table("tourist_spots")
            .select("id, external_id, name, lat, lng, category_id")
            .eq("is_active", True)
            .execute()
        )
        return result.data or []

    def _find_station_for_spot(self, spot_name: str) -> Optional[str]:
        """관광지명으로 가장 가까운 지하철 역명 찾기"""
        if not spot_name:
            return None

        # 1) 직접 매핑 (정확히 일치)
        if spot_name in SPOT_STATION_MAP:
            return SPOT_STATION_MAP[spot_name]

        # 2) 부분 매칭 (관광지명에 역명이 포함된 경우)
        subway_data = _load_subway_data()
        for station in subway_data:
            if station in spot_name or spot_name in station:
                return station

        return None

    def _estimate_crowd(self, spot: Dict, now: datetime) -> Dict:
        """
        혼잡도 추정 (XGBoost 예측 + 지하철 실데이터 + 시간/요일/시즌/카테고리 보정)
        crowd_level: 0.0(여유) ~ 1.0(매우혼잡)

        블렌딩 우선순위:
        1) XGBoost 모델 있음 → XGBoost(60%) + 룰 기반(40%)
        2) 모델 없음, 지하철 데이터 있음 → 지하철(70%) + 규칙(30%)
        3) 둘 다 없음 → 규칙 기반 100%
        """
        hour = now.hour
        weekday = now.weekday()
        month = now.month
        category = spot.get("category_id", "nature")
        spot_name = spot.get("name", "")

        # XGBoost 혼잡도 예측 시도
        xgb_score = self._get_xgboost_crowd(spot_name, hour, weekday, month)

        # 지하철 실데이터 기반 시간대 혼잡도 조회
        subway_base = self._get_subway_crowd(spot_name, hour, weekday)

        if xgb_score is not None:
            # XGBoost 모델 예측 성공: XGBoost(60%) + 룰 기반(40%)
            rule_base = HOUR_WEIGHTS.get(hour, 0.5)
            xgb_normalized = xgb_score / 100.0  # 0-100 → 0-1
            base = xgb_normalized * 0.6 + rule_base * 0.4
            source_type = "xgboost"
        elif subway_base is not None:
            # 실데이터 있음: 지하철 데이터(70%) + 규칙 기반(30%) 블렌딩
            rule_base = HOUR_WEIGHTS.get(hour, 0.5)
            base = subway_base * 0.7 + rule_base * 0.3
            source_type = "subway_data"
        else:
            # 실데이터 없음: 기존 규칙 기반 폴백
            base = HOUR_WEIGHTS.get(hour, 0.5)
            source_type = "estimation"

        # 요일 보정 (XGBoost/지하철 데이터는 이미 요일 반영됨)
        if xgb_score is not None or subway_base is not None:
            day_mult = 1.0  # 이미 요일 반영됨
        else:
            day_mult = DAY_MULTIPLIER.get(weekday, 1.0)

        # 시즌 보정
        season_mult = SEASON_MULTIPLIER.get(month, 1.0)

        # 카테고리 피크 보정
        cat_info = CATEGORY_PEAK.get(category, {})
        cat_mult = 1.0
        if hour in cat_info.get("peak_hours", []):
            cat_mult = cat_info.get("multiplier", 1.0)

        # 종합 계산
        crowd_level = base * day_mult * season_mult * cat_mult

        # 장소별 고유 변동 (spot_id 기반 결정적 오프셋으로 다양성 확보)
        spot_id = spot.get("id", 0)
        spot_hash = int(hashlib.md5(str(spot_id).encode()).hexdigest(), 16) % 1000 / 1000.0  # 0.0~0.999
        spot_offset = (spot_hash - 0.5) * 0.3  # -0.15 ~ +0.15
        crowd_level += spot_offset

        # 0~1 범위로 클램핑
        crowd_level = max(0.0, min(1.0, crowd_level))

        # 방문자 수 추정 (혼잡도 기반)
        visitor_count = self._estimate_visitor_count(crowd_level, category)

        # crowd_level을 등급 문자열로 변환
        if crowd_level < 0.3:
            level_text = "여유"
        elif crowd_level < 0.6:
            level_text = "보통"
        elif crowd_level < 0.8:
            level_text = "혼잡"
        else:
            level_text = "매우혼잡"

        # crowd_ratio = crowd_level * 100 (%)
        crowd_ratio = round(crowd_level * 100, 1)

        return {
            "spot_id": spot["id"],
            "crowd_level": level_text,
            "crowd_count": visitor_count,
            "crowd_ratio": crowd_ratio,
            "source": source_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _get_xgboost_crowd(
        self, spot_name: str, hour: int, weekday: int, month: int,
    ) -> Optional[float]:
        """
        XGBoost 모델로 혼잡도 예측
        Returns: 0-100 점수, 모델 없거나 예측 불가 시 None
        """
        predictor = _get_crowd_predictor()
        if predictor is None:
            return None

        station = self._find_station_for_spot(spot_name)
        if not station:
            return None

        return predictor.predict(station, hour, weekday, month)

    def _get_subway_crowd(self, spot_name: str, hour: int, weekday: int) -> Optional[float]:
        """
        지하철 승하차 데이터에서 해당 관광지/시간대/요일의 혼잡도 조회
        Returns: 0.0~1.0 정규화 값, 데이터 없으면 None
        """
        station = self._find_station_for_spot(spot_name)
        if not station:
            return None

        subway_data = _load_subway_data()
        station_data = subway_data.get(station)
        if not station_data:
            return None

        day_type = "weekend" if weekday >= 5 else "weekday"
        hour_key = f"{hour:02d}"

        hour_data = station_data.get(day_type, {})
        value = hour_data.get(hour_key)
        if value is None:
            return None

        return float(value)

    def _estimate_visitor_count(self, crowd_level: float, category: str) -> int:
        """혼잡도 레벨로부터 방문자 수 추정"""
        # 카테고리별 최대 수용 인원 기준
        capacity = {
            "nature": 5000,
            "culture": 2000,
            "food": 500,
            "activity": 3000,
            "shopping": 4000,
            "nightview": 3000,
        }
        max_cap = capacity.get(category, 2000)
        return int(crowd_level * max_cap)

    async def _fetch_visitor_api(self) -> Optional[List[Dict]]:
        """
        부산 관광지 방문자 통계 API 조회
        (부산관광공사 실시간 방문자 수 데이터)
        """
        try:
            params = {
                "numOfRows": "100",
                "pageNo": "1",
                "_type": "json",
            }
            body = await self.fetch(
                "/B551011/KorService2/areaBasedList2",
                params=params,
            )
            if not body:
                return None

            items_wrapper = body.get("items", {})
            if not isinstance(items_wrapper, dict):
                return None
            items = items_wrapper.get("item", [])
            if not isinstance(items, list):
                items = [items] if isinstance(items, dict) else []

            return items
        except Exception as e:
            logger.debug(f"방문자 API 조회 실패 (추정치 사용): {e}")
            return None

    def _apply_api_correction(
        self, crowd_data: List[Dict], api_items: List[Dict]
    ):
        """API 실데이터로 추정치 보정"""
        # content_id 기반 매핑
        api_map = {}
        for item in api_items:
            cid = item.get("contentid")
            if cid:
                api_map[cid] = item

        # 현재는 API 데이터가 직접적인 혼잡도를 제공하지 않으므로
        # 향후 실시간 데이터 API 연동 시 여기서 보정
        pass

    async def save(self, data: List[Dict]) -> int:
        """혼잡도 데이터 저장"""
        sb = get_supabase()
        saved = 0

        for item in data:
            try:
                sb.table("crowd_data").insert({
                    "spot_id": item["spot_id"],
                    "crowd_level": item["crowd_level"],
                    "crowd_count": item["crowd_count"],
                    "crowd_ratio": item["crowd_ratio"],
                    "source": item.get("source", "estimation"),
                    "timestamp": item["timestamp"],
                }).execute()
                saved += 1
            except Exception as e:
                logger.error(f"혼잡도 저장 실패: {e}")

        return saved
