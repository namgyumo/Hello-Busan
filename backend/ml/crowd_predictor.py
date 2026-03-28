"""
XGBoost 혼잡도 예측기
- ml_data/crowd_model.joblib 로드
- 역명/시간/요일/월 → 0-100 혼잡도 점수 예측
- 모델 미로드 시 None 반환 (graceful fallback)
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ML_DATA_DIR = PROJECT_ROOT / "ml_data"
MODEL_PATH = ML_DATA_DIR / "crowd_model.joblib"
ENCODER_PATH = ML_DATA_DIR / "crowd_station_encoder.json"
POPULATION_PATH = ML_DATA_DIR / "population_by_dong.json"


class CrowdPredictor:
    """XGBoost 혼잡도 예측기"""

    def __init__(self):
        self.model = None
        self.station_encoder: Dict[str, int] = {}
        self.population_by_hour: Dict[str, float] = {}
        self.is_loaded = False
        self._load()

    def _load(self):
        """모델 + 역명 인코더 로드"""
        try:
            if MODEL_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
                logger.info(f"혼잡도 모델 로드 완료: {MODEL_PATH}")
            else:
                logger.warning(f"혼잡도 모델 파일 없음: {MODEL_PATH}")
                return

            if ENCODER_PATH.exists():
                with open(ENCODER_PATH, "r", encoding="utf-8") as f:
                    self.station_encoder = json.load(f)
                logger.info(f"역명 인코더 로드: {len(self.station_encoder)}개 역")
            else:
                logger.warning(f"역명 인코더 없음: {ENCODER_PATH}")
                return

            # 인구이동 데이터에서 시간대별 유동인구 비율 로드
            self._load_population_flow()

            self.is_loaded = True
        except Exception as e:
            logger.error(f"혼잡도 모델 로드 실패: {e}")
            self.is_loaded = False

    def _load_population_flow(self):
        """ml_data/population_by_dong.json에서 시간대별 평균 유동인구 계산"""
        if not POPULATION_PATH.exists():
            return
        try:
            with open(POPULATION_PATH, "r", encoding="utf-8") as f:
                pop_data = json.load(f)
            # population_by_dong.json 구조: {행정동명: {시간대: 이동건수, ...}, ...}
            # 전체 행정동의 시간대별 평균을 구해 정규화
            hour_sums: Dict[str, list] = {}
            for dong, hours in pop_data.items():
                if not isinstance(hours, dict):
                    continue
                for h, val in hours.items():
                    if h not in hour_sums:
                        hour_sums[h] = []
                    hour_sums[h].append(float(val))

            hour_avg = {h: sum(v) / len(v) for h, v in hour_sums.items() if v}
            max_val = max(hour_avg.values()) if hour_avg else 1
            if max_val == 0:
                max_val = 1
            self.population_by_hour = {h: v / max_val for h, v in hour_avg.items()}
        except Exception as e:
            logger.debug(f"인구이동 데이터 로드 실패 (무시): {e}")

    def predict(
        self,
        station_name: str,
        hour: int,
        day_of_week: int,
        month: int,
    ) -> Optional[float]:
        """
        혼잡도 점수 예측

        Args:
            station_name: 역 이름 (예: "해운대", "서면")
            hour: 시간 (0-23)
            day_of_week: 요일 (0=월 ~ 6=일)
            month: 월 (1-12)

        Returns:
            0-100 혼잡도 점수, 모델 미로드 시 None
        """
        if not self.is_loaded or self.model is None:
            return None

        # 역명 → station_id 인코딩
        # 환승역 접두사 제거 후 조회
        clean_name = station_name
        if clean_name and clean_name[0].isdigit() and len(clean_name) > 1:
            clean_name = clean_name[1:]

        station_id = self.station_encoder.get(clean_name)
        if station_id is None:
            # 부분 매칭 시도
            for name, sid in self.station_encoder.items():
                if name in clean_name or clean_name in name:
                    station_id = sid
                    break

        if station_id is None:
            return None

        is_weekend = 1 if day_of_week >= 5 else 0
        hour_str = f"{hour:02d}"
        pop_flow = self.population_by_hour.get(hour_str, 0.5)

        # 피처 순서: hour, day_of_week, is_weekend, month, station_id,
        #            alighting_count, boarding_count, population_flow
        # alighting/boarding은 예측 시점에는 알 수 없으므로 0 (모델이 나머지 피처로 추론)
        features = np.array([[
            hour, day_of_week, is_weekend, month,
            station_id, 0, 0, pop_flow,
        ]], dtype=np.float32)

        try:
            score = float(self.model.predict(features)[0])
            return max(0.0, min(100.0, score))
        except Exception as e:
            logger.error(f"혼잡도 예측 실패 [{station_name}]: {e}")
            return None

    def reload(self):
        """모델 리로드"""
        self.is_loaded = False
        self.model = None
        self.station_encoder = {}
        self.population_by_hour = {}
        self._load()
