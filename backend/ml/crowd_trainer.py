"""
XGBoost 혼잡도 예측 모델 학습 파이프라인
- Dataset/ 지하철 승하차 CSV 5개 + 행정동 인구이동 CSV → 학습 데이터
- 피처: hour, day_of_week, is_weekend, month, station_id, alighting, boarding, population_flow
- 타겟: crowd_score (0-100, 승하차 인원 기반 정규화 혼잡도)
- XGBoost 학습 후 ml_data/crowd_model.joblib 저장
"""
import csv
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "Dataset"
ML_DATA_DIR = PROJECT_ROOT / "ml_data"
MODEL_PATH = ML_DATA_DIR / "crowd_model.joblib"
METRICS_PATH = ML_DATA_DIR / "crowd_metrics.json"
ENCODER_PATH = ML_DATA_DIR / "crowd_station_encoder.json"
POPULATION_CSV = DATASET_DIR / "부산광역시_시간대_행정동별_인구이동 (1).csv"

SUBWAY_CSV_FILES = [
    "일별 역별 시간대별 승하차(2023년 12월).csv",
    "일별 역별 시간대별 승하차(2024년 4월).csv",
    "일별 역별 시간대별 승하차인원(2024년 9월).csv",
    "일별 역별 시간대별 승하차인원(2024년 12월).csv",
    "일별 역별 시간대별 승하차(2025년 12월).csv",
]

# 시간대 컬럼 → 시간(int) 매핑
HOUR_COLUMNS = [
    ("01시-02시", 1), ("02시-03시", 2), ("03시-04시", 3),
    ("04시-05시", 4), ("05시-06시", 5), ("06시-07시", 6),
    ("07시-08시", 7), ("08시-09시", 8), ("09시-10시", 9),
    ("10시-11시", 10), ("11시-12시", 11), ("12시-13시", 12),
    ("13시-14시", 13), ("14시-15시", 14), ("15시-16시", 15),
    ("16시-17시", 16), ("17시-18시", 17), ("18시-19시", 18),
    ("19시-20시", 19), ("20시-21시", 20), ("21시-22시", 21),
    ("22시-23시", 22), ("23시-24시", 23), ("24시-01시", 0),
]

DAY_NAME_TO_INT = {
    "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
}


def _read_csv(filepath: str) -> List[Dict]:
    """CSV 파일을 인코딩 자동 감지하여 읽기"""
    for enc in ["cp949", "utf-8-sig", "utf-8", "euc-kr"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                reader = csv.DictReader(f)
                return list(reader)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"인코딩 감지 실패: {filepath}")


def _normalize_station_name(name: str) -> str:
    """역명 정규화 (환승역 접두사 숫자 제거: '1서면' → '서면')"""
    if name and name[0].isdigit() and len(name) > 1:
        return name[1:]
    return name


def _extract_month_from_date(date_str: str) -> int:
    """년월일 문자열에서 월 추출 (예: '2023-01-15' → 1)"""
    try:
        parts = date_str.split("-")
        return int(parts[1])
    except (IndexError, ValueError):
        return 1


def _load_population_data() -> Dict[str, Dict[str, float]]:
    """
    행정동 인구이동 CSV → {시간대: 평균 이동건수} 딕셔너리
    시간대별 전체 부산 평균 유동인구로 사용
    """
    if not POPULATION_CSV.exists():
        logger.warning(f"인구이동 CSV 없음: {POPULATION_CSV}")
        return {}

    rows = _read_csv(str(POPULATION_CSV))
    # 시간대별 이동건수 합산
    hour_totals: Dict[str, List[int]] = defaultdict(list)
    for row in rows:
        hour_str = row.get("시간대", "").strip()
        count_str = row.get("이동건수", "0").strip()
        try:
            count = int(count_str)
        except ValueError:
            count = 0
        hour_totals[hour_str].append(count)

    # 시간대별 평균
    hour_avg = {}
    for hour_str, values in hour_totals.items():
        hour_avg[hour_str] = sum(values) / len(values) if values else 0

    # 정규화 (0-1)
    max_val = max(hour_avg.values()) if hour_avg else 1
    if max_val == 0:
        max_val = 1
    return {h: v / max_val for h, v in hour_avg.items()}


class CrowdTrainer:
    """XGBoost 혼잡도 예측 모델 학습기"""

    def __init__(self):
        self.params = {
            "objective": "reg:squarederror",
            "max_depth": 6,
            "learning_rate": 0.1,
            "n_estimators": 200,
            "min_child_weight": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }
        self.station_encoder: Dict[str, int] = {}

    def prepare_training_data(self) -> Optional[pd.DataFrame]:
        """
        지하철 CSV 5개 + 인구이동 CSV → 학습용 DataFrame 생성

        Returns:
            DataFrame with columns:
                hour, day_of_week, is_weekend, month, station_id,
                alighting_count, boarding_count, population_flow, crowd_score
        """
        # 인구이동 데이터 로드
        pop_data = _load_population_data()
        logger.info(f"인구이동 데이터: {len(pop_data)}개 시간대")

        # 지하철 CSV에서 승차/하차 데이터 파싱
        # 한 행 = 한 역의 하루치 승차 or 하차, 시간대별 24컬럼
        # 승차/하차를 날짜+역+시간대 기준으로 묶어야 함
        # key: (역명, 날짜, 시간대) → {boarding: int, alighting: int}
        records: Dict[Tuple, Dict] = {}
        all_stations = set()

        for csv_file in SUBWAY_CSV_FILES:
            filepath = DATASET_DIR / csv_file
            if not filepath.exists():
                logger.warning(f"CSV 없음: {csv_file}")
                continue

            logger.info(f"CSV 읽는 중: {csv_file}")
            rows = _read_csv(str(filepath))

            for row in rows:
                station = _normalize_station_name(row.get("역명", "").strip())
                if not station:
                    continue
                all_stations.add(station)

                date_str = row.get("년월일", "").strip()
                day_name = row.get("요일", "").strip()
                category = row.get("구분", "").strip()  # 승차 or 하차

                month = _extract_month_from_date(date_str)
                day_of_week = DAY_NAME_TO_INT.get(day_name, 0)
                is_weekend = 1 if day_of_week >= 5 else 0

                for col_name, hour in HOUR_COLUMNS:
                    val_str = row.get(col_name, "0").strip()
                    try:
                        val = int(val_str) if val_str else 0
                    except ValueError:
                        val = 0

                    key = (station, date_str, hour)
                    if key not in records:
                        records[key] = {
                            "station": station,
                            "date": date_str,
                            "hour": hour,
                            "day_of_week": day_of_week,
                            "is_weekend": is_weekend,
                            "month": month,
                            "boarding": 0,
                            "alighting": 0,
                        }

                    if category == "승차":
                        records[key]["boarding"] += val
                    elif category == "하차":
                        records[key]["alighting"] += val

        if not records:
            logger.error("학습 데이터 없음: 지하철 CSV 파싱 결과가 비어있음")
            return None

        # 역명 → 숫자 인코딩
        sorted_stations = sorted(all_stations)
        self.station_encoder = {name: idx for idx, name in enumerate(sorted_stations)}

        # DataFrame 생성
        rows_list = []
        for key, rec in records.items():
            station_id = self.station_encoder.get(rec["station"], 0)
            hour = rec["hour"]
            hour_str = f"{hour:02d}"
            pop_flow = pop_data.get(hour_str, 0.0)

            rows_list.append({
                "hour": hour,
                "day_of_week": rec["day_of_week"],
                "is_weekend": rec["is_weekend"],
                "month": rec["month"],
                "station_id": station_id,
                "alighting_count": rec["alighting"],
                "boarding_count": rec["boarding"],
                "population_flow": pop_flow,
            })

        df = pd.DataFrame(rows_list)

        # crowd_score 계산: 승하차 합계 기반, 0-100 정규화
        df["total_traffic"] = df["alighting_count"] + df["boarding_count"]
        max_traffic = df["total_traffic"].quantile(0.99)  # 상위 1% 기준 정규화 (이상치 완화)
        if max_traffic == 0:
            max_traffic = 1
        df["crowd_score"] = (df["total_traffic"] / max_traffic * 100).clip(0, 100)
        df.drop(columns=["total_traffic"], inplace=True)

        logger.info(f"학습 데이터 준비 완료: {len(df)}행, 역 {len(self.station_encoder)}개")
        return df

    def train(self, df: pd.DataFrame) -> Dict:
        """
        XGBoost 모델 학습 + 저장

        Returns:
            {"status": "success"|"failed", "metrics": {...}}
        """
        feature_cols = [
            "hour", "day_of_week", "is_weekend", "month",
            "station_id", "alighting_count", "boarding_count", "population_flow",
        ]
        target_col = "crowd_score"

        X = df[feature_cols].values
        y = df[target_col].values

        if len(X) < 100:
            logger.error(f"학습 데이터 부족: {len(X)}행")
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
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        metrics = {
            "mae": round(float(mae), 4),
            "r2": round(float(r2), 4),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "features": feature_cols,
            "total_stations": len(self.station_encoder),
        }

        logger.info(f"혼잡도 모델 학습 완료: MAE={mae:.4f}, R2={r2:.4f}")

        # 모델 저장
        ML_DATA_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(xgb_model, MODEL_PATH)
        logger.info(f"모델 저장: {MODEL_PATH}")

        # 메트릭 저장
        with open(METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        logger.info(f"메트릭 저장: {METRICS_PATH}")

        # 역명 인코더 저장
        with open(ENCODER_PATH, "w", encoding="utf-8") as f:
            json.dump(self.station_encoder, f, indent=2, ensure_ascii=False)
        logger.info(f"역명 인코더 저장: {ENCODER_PATH}")

        return {"status": "success", "metrics": metrics}

    def run_pipeline(self) -> Dict:
        """전체 학습 파이프라인 (동기)"""
        logger.info("혼잡도 모델 학습 파이프라인 시작")

        df = self.prepare_training_data()
        if df is None or df.empty:
            return {"status": "failed", "error": "학습 데이터 없음"}

        result = self.train(df)
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    trainer = CrowdTrainer()
    result = trainer.run_pipeline()
    print(json.dumps(result, indent=2, ensure_ascii=False))
