"""
행정동 인구이동 데이터 전처리
- 부산광역시_시간대_행정동별_인구이동.csv 읽기
- 행정동별/시간대별 평균 이동건수 계산
- 관광지가 속한 행정동의 혼잡도 proxy로 활용
"""
import json
import os
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "dataset" / "부산광역시_시간대_행정동별_인구이동 (1).csv"
OUTPUT_PATH = PROJECT_ROOT / "ml_data" / "population_by_dong.json"


def preprocess_population() -> dict:
    """
    행정동별/시간대별 평균 이동건수를 계산하여 JSON으로 저장

    Returns:
        {
            "행정동명": {
                "code": "행정동코드",
                "hourly_avg": {"0": 12345, "1": 11234, ...},
                "daily_avg": 56789
            },
            ...
        }
    """
    df = pd.read_csv(DATASET_PATH, encoding="cp949")

    # 컬럼명이 인코딩 문제로 깨질 수 있으므로 인덱스로 접근
    # 컬럼 순서: 기준연월, 시간대, 행정동코드, 행정동명, 이동건수
    cols = list(df.columns)
    col_month = cols[0]
    col_hour = cols[1]
    col_dong_code = cols[2]
    col_dong_name = cols[3]
    col_movement = cols[4]

    # 시간대를 정수로 변환
    df[col_hour] = df[col_hour].astype(int)
    df[col_movement] = pd.to_numeric(df[col_movement], errors="coerce").fillna(0).astype(int)

    # 행정동별 + 시간대별 평균 이동건수 (여러 월에 걸친 평균)
    grouped = df.groupby([col_dong_name, col_dong_code, col_hour])[col_movement].mean().reset_index()

    result = {}
    for dong_name in grouped[col_dong_name].unique():
        dong_data = grouped[grouped[col_dong_name] == dong_name]
        dong_code = str(dong_data[col_dong_code].iloc[0])

        hourly_avg = {}
        for _, row in dong_data.iterrows():
            hour = str(int(row[col_hour]))
            hourly_avg[hour] = int(row[col_movement])

        daily_avg = int(sum(hourly_avg.values()) / max(len(hourly_avg), 1))

        result[dong_name] = {
            "code": dong_code,
            "hourly_avg": hourly_avg,
            "daily_avg": daily_avg,
        }

    # JSON 저장
    os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"행정동 인구이동 데이터 전처리 완료: {len(result)}개 행정동 -> {OUTPUT_PATH}")
    return result


def get_dong_crowd_proxy(dong_name: str, hour: int) -> dict:
    """
    특정 행정동의 특정 시간대 혼잡도 proxy 반환

    Args:
        dong_name: 행정동명 (예: "중앙동")
        hour: 시간대 (0-23)

    Returns:
        {"movement_avg": 123456, "crowd_level": "보통", "normalized": 0.45}
    """
    if not OUTPUT_PATH.exists():
        preprocess_population()

    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    dong_info = data.get(dong_name)
    if not dong_info:
        return {"movement_avg": 0, "crowd_level": "정보없음", "normalized": 0.5}

    hourly = dong_info.get("hourly_avg", {})
    movement = hourly.get(str(hour), dong_info.get("daily_avg", 0))

    # 전체 행정동 대비 정규화 (0~1)
    all_daily = [d["daily_avg"] for d in data.values() if d["daily_avg"] > 0]
    max_daily = max(all_daily) if all_daily else 1
    min_daily = min(all_daily) if all_daily else 0
    denom = max_daily - min_daily if max_daily != min_daily else 1
    normalized = (movement - min_daily) / denom
    normalized = max(0.0, min(1.0, normalized))

    if normalized < 0.3:
        level = "여유"
    elif normalized < 0.6:
        level = "보통"
    elif normalized < 0.8:
        level = "혼잡"
    else:
        level = "매우혼잡"

    return {
        "movement_avg": movement,
        "crowd_level": level,
        "normalized": round(normalized, 3),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = preprocess_population()
    print(f"처리 완료: {len(result)}개 행정동")
