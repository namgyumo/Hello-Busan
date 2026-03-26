"""
모델 학습 파이프라인
- 학습 데이터 준비
- XGBoost 모델 학습
- 모델 평가 + 저장
"""
import xgboost as xgb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from pathlib import Path
from typing import Dict, Optional, Tuple
from backend.ml.model import RecommendModel
from backend.ml.features import FEATURE_COLUMNS
from backend.db.supabase import get_supabase
import logging
import json

logger = logging.getLogger(__name__)

TRAINING_DATA_DIR = Path("ml_data/training_data")


class ModelTrainer:
    """XGBoost 모델 학습기"""

    def __init__(self):
        self.model = RecommendModel()
        self.params = {
            "objective": "reg:squarederror",
            "max_depth": 6,
            "learning_rate": 0.1,
            "n_estimators": 100,
            "min_child_weight": 3,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }

    async def prepare_training_data(self) -> Optional[pd.DataFrame]:
        """학습 데이터 준비"""
        sb = get_supabase()

        spots = sb.table("tourist_spots").select("*").execute()
        comfort = sb.table("comfort_scores").select("*").execute()

        if not spots.data:
            logger.warning("학습 데이터 없음")
            return None

        df = pd.DataFrame(spots.data)

        comfort_df = pd.DataFrame(comfort.data) if comfort.data else pd.DataFrame()
        if not comfort_df.empty:
            avg_comfort = comfort_df.groupby("spot_id")["total_score"].mean()
            df["avg_comfort_score"] = df["id"].map(avg_comfort).fillna(50)
        else:
            df["avg_comfort_score"] = 50

        return df

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "rating",
    ) -> Dict:
        """모델 학습"""
        feature_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
        if not feature_cols:
            logger.error("사용 가능한 피처 없음")
            return {"status": "failed", "error": "no features"}

        X = df[feature_cols].values
        y = df[target_col].values if target_col in df.columns else np.random.rand(len(df))

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42,
        )

        xgb_model = xgb.XGBRegressor(**self.params)
        xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        y_pred = xgb_model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        metrics = {
            "mse": float(mse),
            "rmse": float(np.sqrt(mse)),
            "r2": float(r2),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "features": feature_cols,
        }

        logger.info(f"학습 완료: MSE={mse:.4f}, R2={r2:.4f}")

        self.model.save(xgb_model)
        self._save_metrics(metrics)

        return {"status": "success", "metrics": metrics}

    def _save_metrics(self, metrics: Dict):
        """학습 지표 저장"""
        TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = TRAINING_DATA_DIR / "metrics.json"
        with open(path, "w") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

    async def run_pipeline(self) -> Dict:
        """전체 학습 파이프라인"""
        logger.info("학습 파이프라인 시작")

        df = await self.prepare_training_data()
        if df is None or df.empty:
            return {"status": "failed", "error": "데이터 없음"}

        result = self.train(df)
        return result
