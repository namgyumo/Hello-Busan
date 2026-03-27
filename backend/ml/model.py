"""
XGBoost 추천 모델
- 모델 로드 / 예측
- 관광지 점수 계산
- 학습 데이터 충분성 검증
"""
import xgboost as xgb
import numpy as np
import joblib
import json
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

MODEL_PATH = Path("ml_data/model.joblib")
METRICS_PATH = Path("ml_data/training_data/metrics.json")

# 모델 신뢰를 위한 최소 학습 데이터 수
MIN_TRAINING_SAMPLES = 30


class RecommendModel:
    """XGBoost 관광지 추천 모델"""

    def __init__(self):
        self.model: Optional[xgb.XGBRegressor] = None
        self.is_loaded = False
        self._training_samples: int = 0
        self._load_model()

    def _load_model(self):
        """저장된 모델 로드"""
        try:
            if MODEL_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
                self.is_loaded = True
                self._load_training_metadata()
                logger.info("ML 모델 로드 완료")
            else:
                logger.warning(f"모델 파일 없음: {MODEL_PATH}")
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            self.is_loaded = False

    def _load_training_metadata(self):
        """학습 메트릭에서 학습 데이터 크기 로드"""
        try:
            if METRICS_PATH.exists():
                with open(METRICS_PATH) as f:
                    metrics = json.load(f)
                self._training_samples = metrics.get("train_size", 0) + metrics.get("test_size", 0)
        except Exception:
            self._training_samples = 0

    def has_sufficient_data(self) -> bool:
        """학습 데이터가 최소 요구사항을 충족하는지 확인"""
        return self._training_samples >= MIN_TRAINING_SAMPLES

    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        관광지 추천 점수 예측
        Args:
            features: (N, D) 피처 배열
        Returns:
            (N,) 추천 점수 배열
        Raises:
            RuntimeError: 모델 미로드 또는 학습 데이터 부족 시
        """
        if not self.is_loaded or self.model is None:
            raise RuntimeError("모델이 로드되지 않음")

        if not self.has_sufficient_data():
            raise RuntimeError(
                f"학습 데이터 부족: {self._training_samples}건 "
                f"(최소 {MIN_TRAINING_SAMPLES}건 필요) — 폴백 추천 사용 권장"
            )

        try:
            scores = self.model.predict(features)
            return scores
        except Exception as e:
            logger.error(f"예측 실패: {e}")
            raise

    def reload(self):
        """모델 리로드"""
        self._load_model()

    def save(self, model: xgb.XGBRegressor):
        """모델 저장"""
        try:
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, MODEL_PATH)
            self.model = model
            self.is_loaded = True
            logger.info(f"모델 저장 완료: {MODEL_PATH}")
        except Exception as e:
            logger.error(f"모델 저장 실패: {e}")
            raise

    @property
    def feature_names(self) -> List[str]:
        """모델 피처 이름"""
        if self.model and hasattr(self.model, "feature_names_in_"):
            return list(self.model.feature_names_in_)
        return []

    @property
    def training_samples(self) -> int:
        """학습에 사용된 총 데이터 수"""
        return self._training_samples
