"""
모델 학습 파이프라인
- engagement_score 기반 학습 (rating 순환 논리 제거)
- user_events 행동 데이터 → engagement score 계산
- 행동 데이터 부족 시 proxy label 폴백
- XGBoost 모델 학습 + 평가 + 저장
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

# engagement score 관광지당 최소 세션 수 (이 이하면 proxy 사용)
MIN_SESSIONS_PER_SPOT = 20


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

    def _compute_engagement_score(self, spot_id: int, events_df: pd.DataFrame) -> Optional[float]:
        """사용자 행동 기반 engagement score 계산

        Args:
            spot_id: 관광지 ID
            events_df: user_events 테이블 DataFrame

        Returns:
            0~1 정규화된 engagement score, 데이터 부족 시 None
        """
        spot_events = events_df[events_df["spot_id"] == spot_id]

        # 세션 수 확인 — 최소 기준 미달 시 None 반환
        unique_sessions = spot_events["session_id"].nunique()
        if unique_sessions < MIN_SESSIONS_PER_SPOT:
            return None

        click_count = len(spot_events[spot_events["event_type"] == "spot_click"])

        # detail_leave 이벤트에서 dwell_seconds > 60인 경우
        long_dwells = 0
        detail_leave = spot_events[spot_events["event_type"] == "detail_leave"]
        for _, row in detail_leave.iterrows():
            event_data = row.get("event_data")
            if isinstance(event_data, dict) and event_data.get("dwell_seconds", 0) > 60:
                long_dwells += 1

        favorites = len(spot_events[spot_events["event_type"] == "favorite"])
        shares = len(spot_events[spot_events["event_type"] == "share"])

        raw_score = (
            click_count * 0.15
            + long_dwells * 0.35
            + favorites * 0.30
            + shares * 0.20
        )

        # 정규화: 최대값 기준
        max_score = max(unique_sessions * 1.0, 1.0)
        return min(raw_score / max_score, 1.0)

    def _compute_proxy_score(self, spot: pd.Series) -> float:
        """user_events 부족 시 proxy label 계산

        readcount_norm * 0.35 + district_visitor_ratio * 0.25 +
        transit_score * 0.20 + consumption_norm * 0.20
        """
        # readcount 정규화 (0~1)
        readcount = spot.get("readcount", 0) or 0
        readcount_norm = min(readcount / 50000, 1.0)

        # view_count로 transit_score 대용
        view_count = spot.get("view_count", 0) or 0
        transit_score = min(view_count / 10000, 1.0)

        # avg_comfort_score를 district_visitor_ratio 대용 (정규화)
        comfort = spot.get("avg_comfort_score", 50) or 50
        district_visitor_ratio = comfort / 100.0

        # accessibility_score를 consumption_norm 대용
        consumption_norm = spot.get("accessibility_score", 0.5) or 0.5

        proxy_score = (
            readcount_norm * 0.35
            + district_visitor_ratio * 0.25
            + transit_score * 0.20
            + consumption_norm * 0.20
        )
        return min(proxy_score, 1.0)

    async def prepare_training_data(self) -> Optional[pd.DataFrame]:
        """학습 데이터 준비 — tourist_spots + comfort_scores + user_events"""
        sb = get_supabase()

        spots = sb.table("tourist_spots").select("*").execute()
        comfort = sb.table("comfort_scores").select("*").execute()

        if not spots.data:
            logger.warning("학습 데이터 없음")
            return None

        df = pd.DataFrame(spots.data)

        # comfort 점수 병합
        comfort_df = pd.DataFrame(comfort.data) if comfort.data else pd.DataFrame()
        if not comfort_df.empty:
            avg_comfort = comfort_df.groupby("spot_id")["total_score"].mean()
            df["avg_comfort_score"] = df["id"].map(avg_comfort).fillna(50)
        else:
            df["avg_comfort_score"] = 50

        # user_events 조회
        events_result = sb.table("user_events").select("*").execute()
        events_df = pd.DataFrame(events_result.data) if events_result.data else pd.DataFrame()

        # engagement_score 계산
        engagement_scores = []
        proxy_count = 0
        event_count = 0

        for _, row in df.iterrows():
            spot_id = row["id"]

            if not events_df.empty:
                score = self._compute_engagement_score(spot_id, events_df)
            else:
                score = None

            if score is not None:
                engagement_scores.append(score)
                event_count += 1
            else:
                # proxy 폴백
                proxy = self._compute_proxy_score(row)
                engagement_scores.append(proxy)
                proxy_count += 1

        df["engagement_score"] = engagement_scores

        logger.info(
            f"학습 데이터 준비 완료: {len(df)}건 "
            f"(이벤트 기반: {event_count}, proxy 폴백: {proxy_count})"
        )
        return df

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "engagement_score",
    ) -> Dict:
        """모델 학습"""
        feature_cols = [c for c in FEATURE_COLUMNS if c in df.columns]
        if not feature_cols:
            logger.error("사용 가능한 피처 없음")
            return {"status": "failed", "error": "no features"}

        X = df[feature_cols].values
        if target_col not in df.columns:
            logger.error(f"타겟 컬럼 '{target_col}'이 데이터에 없음 — 학습 중단")
            return {"status": "failed", "error": f"target column '{target_col}' not found"}
        y = df[target_col].values

        if len(X) < 10:
            logger.error(f"학습 데이터 부족: {len(X)}건 (최소 10건 필요)")
            return {"status": "failed", "error": f"insufficient data: {len(X)} rows"}

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
            "target": target_col,
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
