"""
지하철 승하차 데이터 전처리기
- CSV 원본 → 역별/시간대별/요일구분별 평균 하차 인원
- 결과: ml_data/subway_crowd_avg.json (0.0~1.0 정규화)
"""
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

# 프로젝트 루트 기준 경로
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "dataset"
OUTPUT_DIR = PROJECT_ROOT / "ml_data"
OUTPUT_FILE = OUTPUT_DIR / "subway_crowd_avg.json"

# 대상 CSV 파일 목록
CSV_FILES = [
    "일별 역별 시간대별 승하차(2023년 12월).csv",
    "일별 역별 시간대별 승하차(2024년 4월).csv",
    "일별 역별 시간대별 승하차인원(2024년 9월).csv",
    "일별 역별 시간대별 승하차인원(2024년 12월).csv",
    "일별 역별 시간대별 승하차(2025년 12월).csv",
]

# 시간대 컬럼 → 시간 매핑 (01시-02시 → "01", ..., 24시-01시 → "00")
HOUR_COLUMNS = [
    ("01시-02시", "01"), ("02시-03시", "02"), ("03시-04시", "03"),
    ("04시-05시", "04"), ("05시-06시", "05"), ("06시-07시", "06"),
    ("07시-08시", "07"), ("08시-09시", "08"), ("09시-10시", "09"),
    ("10시-11시", "10"), ("11시-12시", "11"), ("12시-13시", "12"),
    ("13시-14시", "13"), ("14시-15시", "14"), ("15시-16시", "15"),
    ("16시-17시", "16"), ("17시-18시", "17"), ("18시-19시", "18"),
    ("19시-20시", "19"), ("20시-21시", "20"), ("21시-22시", "21"),
    ("22시-23시", "22"), ("23시-24시", "23"), ("24시-01시", "00"),
]

# 주말 요일
WEEKEND_DAYS = {"토", "일"}


def _read_csv(filepath: str):
    """CSV 파일을 인코딩 자동 감지하여 읽기"""
    for enc in ["cp949", "utf-8", "euc-kr", "utf-8-sig"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                return rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"인코딩 감지 실패: {filepath}")


def _normalize_station_name(name: str) -> str:
    """역명 정규화 (환승역 접두사 제거: '1서면' → '서면')"""
    if name and name[0].isdigit() and len(name) > 1:
        return name[1:]
    return name


def preprocess():
    """
    5개 CSV 파일에서 하차 데이터만 추출하여
    역별/시간대별/요일구분별 평균 하차 인원을 계산하고
    0.0~1.0으로 정규화하여 JSON 저장
    """
    # { 역명: { "weekday": { "08": [값들], ... }, "weekend": { ... } } }
    raw_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for csv_file in CSV_FILES:
        filepath = DATASET_DIR / csv_file
        if not filepath.exists():
            print(f"  [SKIP] 파일 없음: {csv_file}")
            continue

        print(f"  [READ] {csv_file}")
        rows = _read_csv(str(filepath))

        for row in rows:
            # 하차 데이터만 추출
            if row.get("구분", "").strip() != "하차":
                continue

            station = _normalize_station_name(row.get("역명", "").strip())
            if not station:
                continue

            weekday_str = row.get("요일", "").strip()
            day_type = "weekend" if weekday_str in WEEKEND_DAYS else "weekday"

            for col_name, hour_key in HOUR_COLUMNS:
                val = row.get(col_name, "0").strip()
                try:
                    count = int(val) if val else 0
                except ValueError:
                    count = 0
                raw_data[station][day_type][hour_key].append(count)

    # 평균 계산
    avg_data = {}
    for station, day_types in raw_data.items():
        avg_data[station] = {}
        for day_type, hours in day_types.items():
            avg_data[station][day_type] = {}
            for hour, values in hours.items():
                if values:
                    avg_data[station][day_type][hour] = round(
                        sum(values) / len(values), 1
                    )
                else:
                    avg_data[station][day_type][hour] = 0.0

    # 역별 0.0~1.0 정규화 (해당 역의 전체 시간대 중 최대값 대비 비율)
    normalized = {}
    for station, day_types in avg_data.items():
        # 해당 역의 모든 시간대 값에서 최대값 찾기
        all_values = []
        for day_type in day_types.values():
            all_values.extend(day_type.values())
        max_val = max(all_values) if all_values else 1.0
        if max_val == 0:
            max_val = 1.0

        normalized[station] = {}
        for day_type, hours in day_types.items():
            normalized[station][day_type] = {}
            for hour, val in sorted(hours.items()):
                normalized[station][day_type][hour] = round(val / max_val, 4)

    # JSON 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"\n  [DONE] {len(normalized)}개 역 처리 완료 → {OUTPUT_FILE}")
    return normalized


if __name__ == "__main__":
    print("=== 지하철 승하차 데이터 전처리 시작 ===")
    preprocess()
