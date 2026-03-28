"""
XGBoost 혼잡도 예측 모델 학습 파이프라인
- Dataset/ 지하철 승하차 CSV 5개 + 전체 Dataset 추가 피처 → 학습 데이터
- 기존 피처: hour, day_of_week, is_weekend, month, station_id, alighting, boarding, population_flow
- 추가 피처: living_pop, working_pop, visiting_pop, sales_amount, sales_count,
             avg_temp, min_temp, max_temp, rainfall, gu_visitors, gu_visitor_ratio,
             daily_total_visitors, daily_tourist_ratio, dong_move_count
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
FEATURE_META_PATH = ML_DATA_DIR / "crowd_feature_meta.json"
POPULATION_CSV = DATASET_DIR / "부산광역시_시간대_행정동별_인구이동 (1).csv"

# 추가 데이터셋 경로
LIVING_POP_XLSX = DATASET_DIR / "일별 행정동 시간 생활인구 월별 일평균.xlsx"
SALES_XLSX = DATASET_DIR / "일별 행정동 시간 소비매출 월별 일평균.xlsx"
RAIN_XLS = DATASET_DIR / "강수분석.xls"
TEMP_XLS = DATASET_DIR / "기온분석.xls"
GU_VISITORS_CSV = DATASET_DIR / "20260325234913_지역별 방문자 수.csv"
VISITOR_TREND_CSV = DATASET_DIR / "20260325234913_방문자 수 추이.csv"

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

# 역명 → 가장 가까운 행정동명 매핑 (생활인구/소비매출 xlsx의 "구 동" 포맷)
# subway_stations.py 좌표 기반 + 부산 지리 지식으로 수동 매핑
STATION_TO_DONG = {
    # 1호선
    "다대포해수욕장": "사하구 다대1동", "다대포항": "사하구 다대1동",
    "낫개": "사하구 다대2동", "신장림": "사하구 장림2동",
    "장림": "사하구 장림1동", "동매": "사하구 장림1동",
    "괴정": "사하구 괴정1동", "사하": "사하구 괴정2동",
    "당리": "사하구 당리동", "하단": "사하구 하단1동",
    "신평": "사하구 신평1동", "동대신": "서구 동대신1동",
    "토성": "서구 동대신1동", "자갈치": "중구 남포동",
    "남포": "중구 남포동", "중앙": "중구 중앙동",
    "부산역": "동구 초량3동", "초량": "동구 초량1동",
    "부산진": "동구 범일2동", "좌천": "동구 좌천동",
    "범일": "동구 범일1동", "범내골": "부산진구 범천1동",
    "서면": "부산진구 부전1동", "부전": "부산진구 부전2동",
    "양정": "부산진구 양정1동", "시청": "연제구 연산1동",
    "연산": "연제구 연산1동", "교대": "연제구 거제1동",
    "동래": "동래구 복산동", "명륜": "동래구 명륜동",
    "온천장": "동래구 온천1동", "부산대": "금정구 장전1동",
    "장전": "금정구 장전1동", "구서": "금정구 구서1동",
    "두실": "금정구 남산동", "남산": "금정구 남산동",
    "노포": "금정구 청룡노포동",
    # 2호선
    "장산": "해운대구 좌1동", "중동": "해운대구 좌2동",
    "해운대": "해운대구 중1동", "동백": "해운대구 중2동",
    "벡스코": "해운대구 우1동", "센텀시티": "해운대구 우2동",
    "민락": "수영구 민락동", "수영": "수영구 수영동",
    "광안": "수영구 광안1동", "금련산": "수영구 광안3동",
    "남천": "수영구 남천1동", "경성대·부경대": "남구 대연3동",
    "대연": "남구 대연1동", "못골": "남구 대연5동",
    "지게골": "남구 문현1동", "문현": "남구 문현1동",
    "전포": "부산진구 전포1동", "사상": "사상구 괘법동",
    "덕천": "북구 덕천1동", "호포": "금정구 선두구동",
    "양산": "금정구 선두구동",
    # 3호선
    "수영(3)": "수영구 수영동", "망미": "수영구 망미1동",
    "배산": "수영구 망미2동", "물만골": "연제구 연산5동",
    "연산(3)": "연제구 연산1동", "거제": "연제구 거제1동",
    "종합운동장": "연제구 거제2동", "사직": "동래구 사직1동",
    "미남": "동래구 사직1동", "만덕": "북구 만덕1동",
    "대저": "강서구 대저1동",
    # 4호선 (동해선)
    "부전(동해)": "부산진구 부전2동", "거제해맞이": "연제구 거제3동",
    "교대(동해)": "연제구 거제1동", "동래(동해)": "동래구 복산동",
    "안락": "동래구 안락1동", "재송": "해운대구 재송1동",
    "센텀": "해운대구 우2동", "벡스코(동해)": "해운대구 우1동",
    "송정": "해운대구 송정동", "오시리아": "기장군 기장읍",
    "기장": "기장군 기장읍", "일광": "기장군 일광읍",
    # 부산김해경전철
    "사상(경전철)": "사상구 괘법동", "김해공항": "강서구 대저2동",
}

# 역명 → 구군 매핑 (STATION_TO_DONG에서 추출)
STATION_TO_GU = {
    station: dong.split()[0] for station, dong in STATION_TO_DONG.items()
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


def _read_pd_csv(filepath, **kwargs) -> Optional[pd.DataFrame]:
    """pandas용 CSV 인코딩 자동 감지"""
    for enc in ["cp949", "utf-8-sig", "utf-8", "euc-kr"]:
        try:
            return pd.read_csv(filepath, encoding=enc, **kwargs)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


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


def _parse_comma_int(val) -> int:
    """콤마가 포함된 숫자 문자열 → int (예: '1,588,985' → 1588985)"""
    if pd.isna(val):
        return 0
    return int(str(val).replace(",", "").strip() or "0")


def _load_population_data() -> Dict[str, float]:
    """행정동 인구이동 CSV → {시간대: 정규화 이동건수} 딕셔너리"""
    if not POPULATION_CSV.exists():
        logger.warning(f"인구이동 CSV 없음: {POPULATION_CSV}")
        return {}

    rows = _read_csv(str(POPULATION_CSV))
    hour_totals: Dict[str, List[int]] = defaultdict(list)
    for row in rows:
        hour_str = row.get("시간대", "").strip()
        count_str = row.get("이동건수", "0").strip()
        try:
            count = int(count_str)
        except ValueError:
            count = 0
        hour_totals[hour_str].append(count)

    hour_avg = {}
    for hour_str, values in hour_totals.items():
        hour_avg[hour_str] = sum(values) / len(values) if values else 0

    max_val = max(hour_avg.values()) if hour_avg else 1
    if max_val == 0:
        max_val = 1
    return {h: v / max_val for h, v in hour_avg.items()}


def _load_living_population() -> Dict[Tuple[str, str], Dict[str, float]]:
    """
    생활인구 xlsx → {(행정동명, 시간대): {living, working, visiting}} 딕셔너리
    전체 월 평균으로 집계 (시간대+행정동별)
    """
    if not LIVING_POP_XLSX.exists():
        logger.warning(f"생활인구 파일 없음: {LIVING_POP_XLSX}")
        return {}

    try:
        df = pd.read_excel(LIVING_POP_XLSX)
    except Exception as e:
        logger.warning(f"생활인구 읽기 실패: {e}")
        return {}

    result: Dict[Tuple[str, str], Dict[str, List[int]]] = defaultdict(
        lambda: {"living": [], "working": [], "visiting": []}
    )

    for _, row in df.iterrows():
        dong = str(row.get("행정동명", "")).strip()
        hour_str = str(row.get("시간대", "")).strip()  # "00시" ~ "23시"
        if not dong or not hour_str:
            continue

        living = _parse_comma_int(row.get("평균주거인구수", 0))
        working = _parse_comma_int(row.get("평균직장인구수", 0))
        visiting = _parse_comma_int(row.get("평균방문인구수", 0))

        key = (dong, hour_str)
        result[key]["living"].append(living)
        result[key]["working"].append(working)
        result[key]["visiting"].append(visiting)

    # 평균 계산 + 정규화
    averaged: Dict[Tuple[str, str], Dict[str, float]] = {}
    all_vals = {"living": [], "working": [], "visiting": []}
    for key, vals in result.items():
        avg = {}
        for field in ["living", "working", "visiting"]:
            v = vals[field]
            avg[field] = sum(v) / len(v) if v else 0
            all_vals[field].append(avg[field])
        averaged[key] = avg

    # 정규화 (0-1)
    maxes = {
        field: max(vals) if vals else 1 for field, vals in all_vals.items()
    }
    for field in maxes:
        if maxes[field] == 0:
            maxes[field] = 1

    for key in averaged:
        for field in ["living", "working", "visiting"]:
            averaged[key][field] /= maxes[field]

    logger.info(f"생활인구 데이터 로드: {len(averaged)}개 (행정동+시간대) 조합")
    return averaged


def _load_sales_data() -> Dict[Tuple[str, str], Dict[str, float]]:
    """
    소비매출 xlsx → {(행정동명, 시간대): {amount, count}} 딕셔너리
    전체 월 평균으로 집계
    """
    if not SALES_XLSX.exists():
        logger.warning(f"소비매출 파일 없음: {SALES_XLSX}")
        return {}

    try:
        df = pd.read_excel(SALES_XLSX)
    except Exception as e:
        logger.warning(f"소비매출 읽기 실패: {e}")
        return {}

    result: Dict[Tuple[str, str], Dict[str, List[int]]] = defaultdict(
        lambda: {"amount": [], "count": []}
    )

    for _, row in df.iterrows():
        dong = str(row.get("행정동명", "")).strip()
        hour_str = str(row.get("시간대", "")).strip()
        if not dong or not hour_str:
            continue

        amount = _parse_comma_int(row.get("평균이용금액", 0))
        count = _parse_comma_int(row.get("평균이용건수", 0))

        key = (dong, hour_str)
        result[key]["amount"].append(amount)
        result[key]["count"].append(count)

    averaged: Dict[Tuple[str, str], Dict[str, float]] = {}
    all_vals = {"amount": [], "count": []}
    for key, vals in result.items():
        avg = {}
        for field in ["amount", "count"]:
            v = vals[field]
            avg[field] = sum(v) / len(v) if v else 0
            all_vals[field].append(avg[field])
        averaged[key] = avg

    maxes = {field: max(vals) if vals else 1 for field, vals in all_vals.items()}
    for field in maxes:
        if maxes[field] == 0:
            maxes[field] = 1

    for key in averaged:
        for field in ["amount", "count"]:
            averaged[key][field] /= maxes[field]

    logger.info(f"소비매출 데이터 로드: {len(averaged)}개 (행정동+시간대) 조합")
    return averaged


def _load_weather_data() -> Dict[int, Dict[str, float]]:
    """
    강수분석.xls + 기온분석.xls → {month: {avg_temp, min_temp, max_temp, rainfall}}
    월별 평균으로 집계, 정규화
    xls 파일은 실제로는 TSV (탭 구분) 텍스트이며, 상단 7줄은 메타데이터
    """
    weather_by_month: Dict[int, Dict[str, List[float]]] = defaultdict(
        lambda: {"avg_temp": [], "min_temp": [], "max_temp": [], "rainfall": []}
    )

    # 기온분석
    if TEMP_XLS.exists():
        try:
            with open(TEMP_XLS, "r", encoding="cp949") as f:
                lines = f.readlines()
            # 헤더: "날짜\t지점\t평균기온(℃)\t최저기온(℃)\t최고기온(℃)"
            # 데이터 시작: 메타 7줄 + 헤더 1줄 = 8줄 스킵 → index 8부터
            for line in lines[8:]:
                parts = line.strip().split("\t")
                if len(parts) < 5 or not parts[0]:
                    continue
                try:
                    date_str = parts[0]  # "2020-02-01"
                    month = int(date_str.split("-")[1])
                    avg_t = float(parts[2]) if parts[2] else 0
                    min_t = float(parts[3]) if parts[3] else 0
                    max_t = float(parts[4]) if parts[4] else 0
                    weather_by_month[month]["avg_temp"].append(avg_t)
                    weather_by_month[month]["min_temp"].append(min_t)
                    weather_by_month[month]["max_temp"].append(max_t)
                except (ValueError, IndexError):
                    continue
            logger.info("기온분석 데이터 로드 완료")
        except Exception as e:
            logger.warning(f"기온분석 읽기 실패: {e}")

    # 강수분석
    if RAIN_XLS.exists():
        try:
            with open(RAIN_XLS, "r", encoding="cp949") as f:
                lines = f.readlines()
            # 헤더: "날짜,지점,강수량(mm)" 이지만 데이터는 탭 구분
            for line in lines[8:]:
                parts = line.strip().split("\t")
                if len(parts) < 3 or not parts[0]:
                    continue
                try:
                    date_str = parts[0]
                    month = int(date_str.split("-")[1])
                    rain = float(parts[2]) if parts[2] else 0
                    weather_by_month[month]["rainfall"].append(rain)
                except (ValueError, IndexError):
                    # 비가 안 온 날은 강수량이 빈 문자열
                    try:
                        month = int(parts[0].split("-")[1])
                        weather_by_month[month]["rainfall"].append(0.0)
                    except (ValueError, IndexError):
                        continue
            logger.info("강수분석 데이터 로드 완료")
        except Exception as e:
            logger.warning(f"강수분석 읽기 실패: {e}")

    # 월별 평균 계산
    result: Dict[int, Dict[str, float]] = {}
    for month, data in weather_by_month.items():
        result[month] = {}
        for field, values in data.items():
            result[month][field] = sum(values) / len(values) if values else 0

    # 정규화: 기온은 min-max, 강수량은 max 기준
    if result:
        all_avg = [v["avg_temp"] for v in result.values() if "avg_temp" in v]
        all_rain = [v["rainfall"] for v in result.values() if "rainfall" in v]
        temp_min = min(all_avg) if all_avg else 0
        temp_max = max(all_avg) if all_avg else 1
        temp_range = temp_max - temp_min if temp_max != temp_min else 1
        rain_max = max(all_rain) if all_rain else 1
        if rain_max == 0:
            rain_max = 1

        for month in result:
            result[month]["avg_temp"] = (result[month].get("avg_temp", 0) - temp_min) / temp_range
            result[month]["min_temp"] = (result[month].get("min_temp", 0) - temp_min) / temp_range
            result[month]["max_temp"] = (result[month].get("max_temp", 0) - temp_min) / temp_range
            result[month]["rainfall"] = result[month].get("rainfall", 0) / rain_max

    logger.info(f"날씨 데이터 로드: {len(result)}개 월")
    return result


def _load_gu_visitors() -> Dict[str, Dict[str, float]]:
    """
    구군별 방문자 수 CSV → {구군명: {visitors: 정규화수, ratio: 비율}}
    """
    if not GU_VISITORS_CSV.exists():
        logger.warning(f"구군별 방문자 CSV 없음: {GU_VISITORS_CSV}")
        return {}

    try:
        df = _read_pd_csv(str(GU_VISITORS_CSV))
        if df is None:
            return {}
    except Exception as e:
        logger.warning(f"구군별 방문자 읽기 실패: {e}")
        return {}

    result = {}
    max_visitors = df["기초지자체 방문자 수"].max()
    if max_visitors == 0 or pd.isna(max_visitors):
        max_visitors = 1

    for _, row in df.iterrows():
        gu = str(row.get("기초지자체명", "")).strip()
        visitors = float(row.get("기초지자체 방문자 수", 0))
        ratio = float(row.get("기초지자체 방문자 비율", 0))
        result[gu] = {
            "visitors": visitors / max_visitors,
            "ratio": ratio / 100.0,
        }

    logger.info(f"구군별 방문자 데이터 로드: {len(result)}개 구군")
    return result


def _load_visitor_trend() -> Dict[int, Dict[str, float]]:
    """
    방문자 수 추이 CSV → {day_of_week: {total_visitors, tourist_ratio}} 딕셔너리
    기준년월은 실제 일별 (YYYYMMDD) → 요일별 평균으로 집계
    """
    if not VISITOR_TREND_CSV.exists():
        logger.warning(f"방문자 추이 CSV 없음: {VISITOR_TREND_CSV}")
        return {}

    try:
        df = _read_pd_csv(str(VISITOR_TREND_CSV))
        if df is None:
            return {}
    except Exception as e:
        logger.warning(f"방문자 추이 읽기 실패: {e}")
        return {}

    # 기준년월 = YYYYMMDD → 요일 추출
    from datetime import datetime

    dow_data: Dict[int, Dict[str, List[float]]] = defaultdict(
        lambda: {"total": [], "tourist_ratio": []}
    )

    # 일자별로 전체/외지인 방문자 수 취합
    date_data: Dict[str, Dict[str, float]] = defaultdict(lambda: {"total": 0, "tourist": 0})
    for _, row in df.iterrows():
        date_str = str(int(row.get("기준년월", 0)))
        category = str(row.get("방문자 구분", "")).strip()
        visitors = float(row.get("방문자 수", 0))

        if category.startswith("전체"):
            date_data[date_str]["total"] = visitors
        elif category.startswith("외지인"):
            date_data[date_str]["tourist"] = visitors

    for date_str, data in date_data.items():
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            dow = dt.weekday()  # 0=월 ~ 6=일
            dow_data[dow]["total"].append(data["total"])
            ratio = data["tourist"] / data["total"] if data["total"] > 0 else 0
            dow_data[dow]["tourist_ratio"].append(ratio)
        except ValueError:
            continue

    # 요일별 평균 + 정규화
    result: Dict[int, Dict[str, float]] = {}
    all_totals = []
    for dow, data in dow_data.items():
        avg_total = sum(data["total"]) / len(data["total"]) if data["total"] else 0
        avg_ratio = sum(data["tourist_ratio"]) / len(data["tourist_ratio"]) if data["tourist_ratio"] else 0
        result[dow] = {"total_visitors": avg_total, "tourist_ratio": avg_ratio}
        all_totals.append(avg_total)

    max_total = max(all_totals) if all_totals else 1
    if max_total == 0:
        max_total = 1
    for dow in result:
        result[dow]["total_visitors"] /= max_total

    logger.info(f"방문자 추이 데이터 로드: {len(result)}개 요일")
    return result


def _load_dong_movement() -> Dict[Tuple[str, int], float]:
    """
    행정동별 인구이동 CSV → {(행정동명, 시간대int): 정규화 이동건수}
    인구이동 CSV의 행정동명은 "동" 이름만 (구 없음) → 생활인구 dong에서 동 이름으로 매칭
    """
    if not POPULATION_CSV.exists():
        return {}

    rows = _read_csv(str(POPULATION_CSV))
    dong_hour_totals: Dict[Tuple[str, int], List[int]] = defaultdict(list)
    for row in rows:
        dong = row.get("행정동명", "").strip()
        hour_str = row.get("시간대", "").strip()
        count_str = row.get("이동건수", "0").strip()
        try:
            hour = int(hour_str)
            count = int(count_str)
        except ValueError:
            continue
        dong_hour_totals[(dong, hour)].append(count)

    result = {}
    all_avgs = []
    for key, values in dong_hour_totals.items():
        avg = sum(values) / len(values) if values else 0
        result[key] = avg
        all_avgs.append(avg)

    max_val = max(all_avgs) if all_avgs else 1
    if max_val == 0:
        max_val = 1
    for key in result:
        result[key] /= max_val

    logger.info(f"행정동 인구이동 데이터 로드: {len(result)}개 (동+시간대) 조합")
    return result


class CrowdTrainer:
    """XGBoost 혼잡도 예측 모델 학습기"""

    def __init__(self):
        self.params = {
            "objective": "reg:squarederror",
            "max_depth": 7,
            "learning_rate": 0.08,
            "n_estimators": 300,
            "min_child_weight": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }
        self.station_encoder: Dict[str, int] = {}

    def prepare_training_data(self) -> Optional[pd.DataFrame]:
        """
        지하철 CSV 5개 + 전체 Dataset → 학습용 DataFrame 생성

        Returns:
            DataFrame with 기존 + 추가 피처 컬럼들 + crowd_score
        """
        # === 1. 보조 데이터 로드 ===
        pop_data = _load_population_data()
        logger.info(f"인구이동 데이터: {len(pop_data)}개 시간대")

        living_pop = _load_living_population()
        sales_data = _load_sales_data()
        weather_data = _load_weather_data()
        gu_visitors = _load_gu_visitors()
        visitor_trend = _load_visitor_trend()
        dong_movement = _load_dong_movement()

        # === 2. 지하철 CSV 파싱 (기존 로직 유지) ===
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
                category = row.get("구분", "").strip()

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

        # === 3. 역명 인코딩 ===
        sorted_stations = sorted(all_stations)
        self.station_encoder = {name: idx for idx, name in enumerate(sorted_stations)}

        # === 4. DataFrame 생성 (기존 + 추가 피처) ===
        rows_list = []
        for key, rec in records.items():
            station = rec["station"]
            station_id = self.station_encoder.get(station, 0)
            hour = rec["hour"]
            month = rec["month"]
            day_of_week = rec["day_of_week"]
            hour_str_padded = f"{hour:02d}"
            hour_str_si = f"{hour:02d}시"

            # 기존: 시간대별 유동인구
            pop_flow = pop_data.get(hour_str_padded, 0.0)

            # 추가 1: 생활인구 (행정동+시간대 매칭)
            dong_name = STATION_TO_DONG.get(station, "")
            pop_key = (dong_name, hour_str_si)
            living_info = living_pop.get(pop_key, {})
            living_val = living_info.get("living", 0.0)
            working_val = living_info.get("working", 0.0)
            visiting_val = living_info.get("visiting", 0.0)

            # 추가 2: 소비매출 (행정동+시간대 매칭)
            sales_info = sales_data.get(pop_key, {})
            sales_amount = sales_info.get("amount", 0.0)
            sales_count = sales_info.get("count", 0.0)

            # 추가 3: 날씨 (월별)
            weather = weather_data.get(month, {})
            avg_temp = weather.get("avg_temp", 0.5)
            min_temp = weather.get("min_temp", 0.5)
            max_temp = weather.get("max_temp", 0.5)
            rainfall = weather.get("rainfall", 0.0)

            # 추가 4: 구군별 방문자 수
            gu_name = STATION_TO_GU.get(station, "")
            gu_info = gu_visitors.get(gu_name, {})
            gu_visitor_val = gu_info.get("visitors", 0.0)
            gu_visitor_ratio = gu_info.get("ratio", 0.0)

            # 추가 5: 요일별 방문자 추이
            trend = visitor_trend.get(day_of_week, {})
            daily_total_visitors = trend.get("total_visitors", 0.5)
            daily_tourist_ratio = trend.get("tourist_ratio", 0.0)

            # 추가 6: 행정동별 인구이동 (동 이름만으로 매칭)
            dong_short = dong_name.split()[-1] if dong_name else ""
            # 동 이름에서 숫자 접미 제거하여 넓은 매칭 시도 (예: "하단1동" → "하단동" 매칭 실패 시)
            dong_move_val = dong_movement.get((dong_short, hour), 0.0)
            if dong_move_val == 0.0 and dong_short:
                # 번호 없는 동 이름으로 재시도
                import re
                base_dong = re.sub(r'\d+동$', '동', dong_short)
                if base_dong != dong_short:
                    dong_move_val = dong_movement.get((base_dong, hour), 0.0)

            rows_list.append({
                "hour": hour,
                "day_of_week": day_of_week,
                "is_weekend": rec["is_weekend"],
                "month": month,
                "station_id": station_id,
                "alighting_count": rec["alighting"],
                "boarding_count": rec["boarding"],
                "population_flow": pop_flow,
                # 추가 피처
                "living_pop": living_val,
                "working_pop": working_val,
                "visiting_pop": visiting_val,
                "sales_amount": sales_amount,
                "sales_count": sales_count,
                "avg_temp": avg_temp,
                "min_temp": min_temp,
                "max_temp": max_temp,
                "rainfall": rainfall,
                "gu_visitors": gu_visitor_val,
                "gu_visitor_ratio": gu_visitor_ratio,
                "daily_total_visitors": daily_total_visitors,
                "daily_tourist_ratio": daily_tourist_ratio,
                "dong_move_count": dong_move_val,
            })

        df = pd.DataFrame(rows_list)

        # crowd_score 계산: 승하차 합계 기반, 0-100 정규화
        df["total_traffic"] = df["alighting_count"] + df["boarding_count"]
        max_traffic = df["total_traffic"].quantile(0.99)
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
            # 추가 피처
            "living_pop", "working_pop", "visiting_pop",
            "sales_amount", "sales_count",
            "avg_temp", "min_temp", "max_temp", "rainfall",
            "gu_visitors", "gu_visitor_ratio",
            "daily_total_visitors", "daily_tourist_ratio",
            "dong_move_count",
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

        # 피처 메타 저장 (predictor에서 참조)
        feature_meta = {
            "feature_cols": feature_cols,
            "station_to_dong": STATION_TO_DONG,
            "station_to_gu": STATION_TO_GU,
        }
        with open(FEATURE_META_PATH, "w", encoding="utf-8") as f:
            json.dump(feature_meta, f, indent=2, ensure_ascii=False)
        logger.info(f"피처 메타 저장: {FEATURE_META_PATH}")

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
