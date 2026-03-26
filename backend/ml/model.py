"""
XGBoost 추천 모델
- 모델 로드 / 예측
- 관광지 점수 계산
"""
import xgboost as xgb
import numpy as np
import joblib
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

MODEL_PATH = Path("ml_data/model.joblib")


class RecommendModel:
    """XGBoost 관광지 추천 모델"""

    def __init__(self):
        self.model: Optional[xgb.XGBRegressor] = None
        self.is_loaded = False
        self._load_model()

    def _load_model(self):
        """저장된 모델 로드"""
        try:
            if MODEL_PATH.exists():
                self.model = joblib.load(MODEL_PATH)
                self.is_loaded = True
                logger.info("ML 모델 로드 완료")
            else:
                logger.warning(f"모델 파일 없음: {MODEL_PATH}")
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            self.is_loaded = False

    def predict(self, features: np.ndarray) -> np.ndarray:
        """
        관광지 추천 점수 예측
        Args:
            features: (N, D) 피처 배열
        Returns:
            (N,) 추천 점수 배열
        """
        if not self.is_loaded or self.model is None:
            raise RuntimeError("모델이 로드되지 않음")

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
