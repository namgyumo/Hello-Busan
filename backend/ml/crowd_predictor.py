"""
XGBoost 혼잡도 예측기
- ml_data/crowd_model.joblib 로드
- 역명/시간/요일/월 → 0-100 혼잡도 점수 예측
- 추가 피처 (생활인구, 소비매출, 날씨, 방문자 등) 반영
- 모델 미로드 시 None 반환 (graceful fallback)
"""
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Tuple

import joblib
import numpy as np

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ML_DATA_DIR = PROJECT_ROOT / "ml_data"
MODEL_PATH = ML_DATA_DIR / "crowd_model.joblib"
ENCODER_PATH = ML_DATA_DIR / "crowd_station_encoder.json"
POPULATION_PATH = ML_DATA_DIR / "population_by_dong.json"
FEATURE_META_PATH = ML_DATA_DIR / "crowd_feature_meta.json"


class CrowdPredictor:
    """XGBoost 혼잡도 예측기"""

    def __init__(self):
        self.model = None
        self.station_encoder: Dict[str, int] = {}
        self.population_by_hour: Dict[str, float] = {}
        self.feature_cols = []
        self.station_to_dong: Dict[str, str] = {}
        self.station_to_gu: Dict[str, str] = {}
        self.living_pop_cache: Dict[Tuple[str, str], Dict[str, float]] = {}
        self.sales_cache: Dict[Tuple[str, str], Dict[str, float]] = {}
        self.weather_cache: Dict[int, Dict[str, float]] = {}
        self.gu_visitors_cache: Dict[str, Dict[str, float]] = {}
        self.visitor_trend_cache: Dict[int, Dict[str, float]] = {}
        self.dong_movement_cache: Dict[Tuple[str, int], float] = {}
        self.is_loaded = False
        self._load()

    def _load(self):
        """모델 + 역명 인코더 + 피처 메타 + 보조 데이터 로드"""
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

            # 피처 메타 로드
            if FEATURE_META_PATH.exists():
                with open(FEATURE_META_PATH, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.feature_cols = meta.get("feature_cols", [])
                self.station_to_dong = meta.get("station_to_dong", {})
                self.station_to_gu = meta.get("station_to_gu", {})
                logger.info(f"피처 메타 로드: {len(self.feature_cols)}개 피처")

            # 인구이동 데이터 로드
            self._load_population_flow()

            # 보조 데이터 캐시 구축
            self._build_auxiliary_caches()

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

    def _build_auxiliary_caches(self):
        """
        예측 시 사용할 보조 데이터 캐시 구축
        학습 시 사용한 Dataset 파일에서 요약 통계를 로드
        파일이 없으면 기본값(0 또는 0.5)으로 폴백
        """
        import pandas as pd
        dataset_dir = PROJECT_ROOT / "Dataset"

        # 생활인구 캐시
        living_pop_path = dataset_dir / "일별 행정동 시간 생활인구 월별 일평균.xlsx"
        if living_pop_path.exists():
            try:
                self._cache_living_pop(living_pop_path)
            except Exception as e:
                logger.debug(f"생활인구 캐시 구축 실패: {e}")

        # 소비매출 캐시
        sales_path = dataset_dir / "일별 행정동 시간 소비매출 월별 일평균.xlsx"
        if sales_path.exists():
            try:
                self._cache_sales(sales_path)
            except Exception as e:
                logger.debug(f"소비매출 캐시 구축 실패: {e}")

        # 날씨 캐시
        self._cache_weather(dataset_dir)

        # 구군 방문자 캐시
        gu_path = dataset_dir / "20260325234913_지역별 방문자 수.csv"
        if gu_path.exists():
            try:
                self._cache_gu_visitors(gu_path)
            except Exception as e:
                logger.debug(f"구군 방문자 캐시 구축 실패: {e}")

        # 방문자 추이 캐시
        trend_path = dataset_dir / "20260325234913_방문자 수 추이.csv"
        if trend_path.exists():
            try:
                self._cache_visitor_trend(trend_path)
            except Exception as e:
                logger.debug(f"방문자 추이 캐시 구축 실패: {e}")

        # 행정동 인구이동 캐시
        move_path = dataset_dir / "부산광역시_시간대_행정동별_인구이동 (1).csv"
        if move_path.exists():
            try:
                self._cache_dong_movement(move_path)
            except Exception as e:
                logger.debug(f"행정동 인구이동 캐시 구축 실패: {e}")

    def _parse_comma_int(self, val) -> int:
        import pandas as pd
        if pd.isna(val):
            return 0
        return int(str(val).replace(",", "").strip() or "0")

    def _cache_living_pop(self, path):
        import pandas as pd
        df = pd.read_excel(path)
        temp: Dict[Tuple[str, str], Dict[str, list]] = defaultdict(
            lambda: {"living": [], "working": [], "visiting": []}
        )
        for _, row in df.iterrows():
            dong = str(row.get("행정동명", "")).strip()
            hour_str = str(row.get("시간대", "")).strip()
            if not dong or not hour_str:
                continue
            key = (dong, hour_str)
            temp[key]["living"].append(self._parse_comma_int(row.get("평균주거인구수", 0)))
            temp[key]["working"].append(self._parse_comma_int(row.get("평균직장인구수", 0)))
            temp[key]["visiting"].append(self._parse_comma_int(row.get("평균방문인구수", 0)))

        all_vals = {"living": [], "working": [], "visiting": []}
        averaged = {}
        for key, vals in temp.items():
            avg = {}
            for field in ["living", "working", "visiting"]:
                v = vals[field]
                avg[field] = sum(v) / len(v) if v else 0
                all_vals[field].append(avg[field])
            averaged[key] = avg

        maxes = {f: max(v) if v else 1 for f, v in all_vals.items()}
        for f in maxes:
            if maxes[f] == 0:
                maxes[f] = 1
        for key in averaged:
            for f in ["living", "working", "visiting"]:
                averaged[key][f] /= maxes[f]

        self.living_pop_cache = averaged
        logger.info(f"생활인구 캐시: {len(averaged)}개 조합")

    def _cache_sales(self, path):
        import pandas as pd
        df = pd.read_excel(path)
        temp: Dict[Tuple[str, str], Dict[str, list]] = defaultdict(
            lambda: {"amount": [], "count": []}
        )
        for _, row in df.iterrows():
            dong = str(row.get("행정동명", "")).strip()
            hour_str = str(row.get("시간대", "")).strip()
            if not dong or not hour_str:
                continue
            key = (dong, hour_str)
            temp[key]["amount"].append(self._parse_comma_int(row.get("평균이용금액", 0)))
            temp[key]["count"].append(self._parse_comma_int(row.get("평균이용건수", 0)))

        all_vals = {"amount": [], "count": []}
        averaged = {}
        for key, vals in temp.items():
            avg = {}
            for field in ["amount", "count"]:
                v = vals[field]
                avg[field] = sum(v) / len(v) if v else 0
                all_vals[field].append(avg[field])
            averaged[key] = avg

        maxes = {f: max(v) if v else 1 for f, v in all_vals.items()}
        for f in maxes:
            if maxes[f] == 0:
                maxes[f] = 1
        for key in averaged:
            for f in ["amount", "count"]:
                averaged[key][f] /= maxes[f]

        self.sales_cache = averaged
        logger.info(f"소비매출 캐시: {len(averaged)}개 조합")

    def _cache_weather(self, dataset_dir):
        weather: Dict[int, Dict[str, list]] = defaultdict(
            lambda: {"avg_temp": [], "min_temp": [], "max_temp": [], "rainfall": []}
        )

        temp_path = dataset_dir / "기온분석.xls"
        if temp_path.exists():
            try:
                with open(temp_path, "r", encoding="cp949") as f:
                    lines = f.readlines()
                for line in lines[8:]:
                    parts = line.strip().split("\t")
                    if len(parts) < 5 or not parts[0]:
                        continue
                    try:
                        month = int(parts[0].split("-")[1])
                        weather[month]["avg_temp"].append(float(parts[2]) if parts[2] else 0)
                        weather[month]["min_temp"].append(float(parts[3]) if parts[3] else 0)
                        weather[month]["max_temp"].append(float(parts[4]) if parts[4] else 0)
                    except (ValueError, IndexError):
                        continue
            except Exception as e:
                logger.debug(f"기온분석 캐시 실패: {e}")

        rain_path = dataset_dir / "강수분석.xls"
        if rain_path.exists():
            try:
                with open(rain_path, "r", encoding="cp949") as f:
                    lines = f.readlines()
                for line in lines[8:]:
                    parts = line.strip().split("\t")
                    if len(parts) < 3 or not parts[0]:
                        continue
                    try:
                        month = int(parts[0].split("-")[1])
                        rain = float(parts[2]) if parts[2] else 0
                        weather[month]["rainfall"].append(rain)
                    except (ValueError, IndexError):
                        try:
                            month = int(parts[0].split("-")[1])
                            weather[month]["rainfall"].append(0.0)
                        except (ValueError, IndexError):
                            continue
            except Exception as e:
                logger.debug(f"강수분석 캐시 실패: {e}")

        result = {}
        for month, data in weather.items():
            result[month] = {f: sum(v) / len(v) if v else 0 for f, v in data.items()}

        if result:
            all_avg = [v["avg_temp"] for v in result.values()]
            all_rain = [v["rainfall"] for v in result.values()]
            t_min = min(all_avg) if all_avg else 0
            t_max = max(all_avg) if all_avg else 1
            t_range = t_max - t_min if t_max != t_min else 1
            r_max = max(all_rain) if all_rain else 1
            if r_max == 0:
                r_max = 1
            for m in result:
                result[m]["avg_temp"] = (result[m].get("avg_temp", 0) - t_min) / t_range
                result[m]["min_temp"] = (result[m].get("min_temp", 0) - t_min) / t_range
                result[m]["max_temp"] = (result[m].get("max_temp", 0) - t_min) / t_range
                result[m]["rainfall"] = result[m].get("rainfall", 0) / r_max

        self.weather_cache = result
        logger.info(f"날씨 캐시: {len(result)}개 월")

    def _cache_gu_visitors(self, path):
        import pandas as pd
        for enc in ["cp949", "utf-8-sig", "utf-8", "euc-kr"]:
            try:
                df = pd.read_csv(path, encoding=enc)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            return

        max_v = df["기초지자체 방문자 수"].max()
        if max_v == 0 or pd.isna(max_v):
            max_v = 1

        for _, row in df.iterrows():
            gu = str(row.get("기초지자체명", "")).strip()
            visitors = float(row.get("기초지자체 방문자 수", 0))
            ratio = float(row.get("기초지자체 방문자 비율", 0))
            self.gu_visitors_cache[gu] = {
                "visitors": visitors / max_v,
                "ratio": ratio / 100.0,
            }
        logger.info(f"구군 방문자 캐시: {len(self.gu_visitors_cache)}개 구군")

    def _cache_visitor_trend(self, path):
        import pandas as pd
        from datetime import datetime

        for enc in ["cp949", "utf-8-sig", "utf-8", "euc-kr"]:
            try:
                df = pd.read_csv(path, encoding=enc)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            return

        date_data: Dict[str, Dict[str, float]] = defaultdict(lambda: {"total": 0, "tourist": 0})
        for _, row in df.iterrows():
            date_str = str(int(row.get("기준년월", 0)))
            category = str(row.get("방문자 구분", "")).strip()
            visitors = float(row.get("방문자 수", 0))
            if category.startswith("전체"):
                date_data[date_str]["total"] = visitors
            elif category.startswith("외지인"):
                date_data[date_str]["tourist"] = visitors

        dow_data: Dict[int, Dict[str, list]] = defaultdict(
            lambda: {"total": [], "tourist_ratio": []}
        )
        for ds, data in date_data.items():
            try:
                dt = datetime.strptime(ds, "%Y%m%d")
                dow = dt.weekday()
                dow_data[dow]["total"].append(data["total"])
                ratio = data["tourist"] / data["total"] if data["total"] > 0 else 0
                dow_data[dow]["tourist_ratio"].append(ratio)
            except ValueError:
                continue

        all_totals = []
        for dow, data in dow_data.items():
            avg_t = sum(data["total"]) / len(data["total"]) if data["total"] else 0
            avg_r = sum(data["tourist_ratio"]) / len(data["tourist_ratio"]) if data["tourist_ratio"] else 0
            self.visitor_trend_cache[dow] = {"total_visitors": avg_t, "tourist_ratio": avg_r}
            all_totals.append(avg_t)

        max_t = max(all_totals) if all_totals else 1
        if max_t == 0:
            max_t = 1
        for dow in self.visitor_trend_cache:
            self.visitor_trend_cache[dow]["total_visitors"] /= max_t

        logger.info(f"방문자 추이 캐시: {len(self.visitor_trend_cache)}개 요일")

    def _cache_dong_movement(self, path):
        import csv as csv_mod

        for enc in ["cp949", "utf-8-sig", "utf-8", "euc-kr"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    reader = csv_mod.DictReader(f)
                    rows = list(reader)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            return

        temp: Dict[Tuple[str, int], list] = defaultdict(list)
        for row in rows:
            dong = row.get("행정동명", "").strip()
            hour_str = row.get("시간대", "").strip()
            count_str = row.get("이동건수", "0").strip()
            try:
                hour = int(hour_str)
                count = int(count_str)
            except ValueError:
                continue
            temp[(dong, hour)].append(count)

        all_avgs = []
        for key, values in temp.items():
            avg = sum(values) / len(values) if values else 0
            self.dong_movement_cache[key] = avg
            all_avgs.append(avg)

        max_v = max(all_avgs) if all_avgs else 1
        if max_v == 0:
            max_v = 1
        for key in self.dong_movement_cache:
            self.dong_movement_cache[key] /= max_v

        logger.info(f"행정동 인구이동 캐시: {len(self.dong_movement_cache)}개 조합")

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
        clean_name = station_name
        if clean_name and clean_name[0].isdigit() and len(clean_name) > 1:
            clean_name = clean_name[1:]

        station_id = self.station_encoder.get(clean_name)
        if station_id is None:
            for name, sid in self.station_encoder.items():
                if name in clean_name or clean_name in name:
                    station_id = sid
                    break

        if station_id is None:
            return None

        is_weekend = 1 if day_of_week >= 5 else 0
        hour_str = f"{hour:02d}"
        hour_str_si = f"{hour:02d}시"
        pop_flow = self.population_by_hour.get(hour_str, 0.5)

        # 추가 피처 조회
        dong_name = self.station_to_dong.get(clean_name, "")
        pop_key = (dong_name, hour_str_si)

        # 생활인구
        living_info = self.living_pop_cache.get(pop_key, {})
        living_val = living_info.get("living", 0.0)
        working_val = living_info.get("working", 0.0)
        visiting_val = living_info.get("visiting", 0.0)

        # 소비매출
        sales_info = self.sales_cache.get(pop_key, {})
        sales_amount = sales_info.get("amount", 0.0)
        sales_count = sales_info.get("count", 0.0)

        # 날씨
        weather = self.weather_cache.get(month, {})
        avg_temp = weather.get("avg_temp", 0.5)
        min_temp = weather.get("min_temp", 0.5)
        max_temp = weather.get("max_temp", 0.5)
        rainfall = weather.get("rainfall", 0.0)

        # 구군 방문자
        gu_name = self.station_to_gu.get(clean_name, "")
        gu_info = self.gu_visitors_cache.get(gu_name, {})
        gu_visitor_val = gu_info.get("visitors", 0.0)
        gu_visitor_ratio = gu_info.get("ratio", 0.0)

        # 요일별 방문자 추이
        trend = self.visitor_trend_cache.get(day_of_week, {})
        daily_total_visitors = trend.get("total_visitors", 0.5)
        daily_tourist_ratio = trend.get("tourist_ratio", 0.0)

        # 행정동 인구이동
        dong_short = dong_name.split()[-1] if dong_name else ""
        dong_move_val = self.dong_movement_cache.get((dong_short, hour), 0.0)
        if dong_move_val == 0.0 and dong_short:
            base_dong = re.sub(r'\d+동$', '동', dong_short)
            if base_dong != dong_short:
                dong_move_val = self.dong_movement_cache.get((base_dong, hour), 0.0)

        # 피처 벡터 구성 (학습 시와 동일한 순서 — 22개 피처)
        features = np.array([[
            hour, day_of_week, is_weekend, month,
            station_id, 0, 0, pop_flow,
            living_val, working_val, visiting_val,
            sales_amount, sales_count,
            avg_temp, min_temp, max_temp, rainfall,
            gu_visitor_val, gu_visitor_ratio,
            daily_total_visitors, daily_tourist_ratio, dong_move_val,
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
        self.feature_cols = []
        self.station_to_dong = {}
        self.station_to_gu = {}
        self.living_pop_cache = {}
        self.sales_cache = {}
        self.weather_cache = {}
        self.gu_visitors_cache = {}
        self.visitor_trend_cache = {}
        self.dong_movement_cache = {}
        self._load()
