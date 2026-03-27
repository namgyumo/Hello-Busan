"""
구군별 방문자 데이터 전처리
- 지역별 방문자 수 CSV 읽기
- 구군별 방문자 비율 정규화
- fallback.py의 popularity_score 보정에 활용
"""
import json
import os
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "dataset" / "20260325234913_지역별 방문자 수.csv"
OUTPUT_PATH = PROJECT_ROOT / "ml_data" / "district_popularity.json"


def preprocess_district_visitors() -> dict:
    """
    구군별 방문자 수를 정규화하여 JSON으로 저장

    Returns:
        {
            "해운대구": {"visitor_count": 6255473, "ratio_pct": 11.3, "normalized": 1.0},
            "부산진구": {"visitor_count": 6943573, "ratio_pct": 12.6, "normalized": 1.0},
            ...
        }
    """
    df = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")

    # 컬럼 순서: 기초자치단체명, 기초자치단체 방문자 수, 기초자치단체 방문자 비율
    cols = list(df.columns)
    col_district = cols[0]
    col_count = cols[1]
    col_ratio = cols[2]

    df[col_count] = pd.to_numeric(df[col_count], errors="coerce").fillna(0)
    df[col_ratio] = pd.to_numeric(df[col_ratio], errors="coerce").fillna(0)

    # min-max 정규화 (0~1)
    max_count = df[col_count].max()
    min_count = df[col_count].min()
    denom = max_count - min_count if max_count != min_count else 1

    result = {}
    for _, row in df.iterrows():
        district = row[col_district]
        count = int(row[col_count])
        ratio = float(row[col_ratio])
        normalized = round((count - min_count) / denom, 4)

        result[district] = {
            "visitor_count": count,
            "ratio_pct": ratio,
            "normalized": normalized,
        }

    # JSON 저장
    os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"구군별 방문자 데이터 전처리 완료: {len(result)}개 구군 -> {OUTPUT_PATH}")
    return result


def get_district_popularity(district_name: str) -> float:
    """
    구군명으로 정규화된 인기도 점수 반환 (0~1)
    fallback.py의 popularity_score 보정에 사용

    Args:
        district_name: 구군명 (예: "해운대구")

    Returns:
        정규화된 인기도 (0.0~1.0), 매칭 실패 시 0.5
    """
    if not OUTPUT_PATH.exists():
        preprocess_district_visitors()

    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    info = data.get(district_name)
    if info:
        return info["normalized"]

    # 부분 매칭 시도 (예: "해운대" -> "해운대구")
    for key, val in data.items():
        if district_name in key or key in district_name:
            return val["normalized"]

    return 0.5


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = preprocess_district_visitors()
    print(f"처리 완료: {len(result)}개 구군")
    for district, info in sorted(result.items(), key=lambda x: x[1]["normalized"], reverse=True):
        print(f"  {district}: {info['visitor_count']:,}명 ({info['ratio_pct']}%) -> {info['normalized']}")
