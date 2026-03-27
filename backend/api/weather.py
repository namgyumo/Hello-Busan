"""
날씨 API — 현재 날씨 + 7일 예보 엔드포인트
GET /api/v1/weather/current
GET /api/v1/weather/forecast
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter
from backend.db.supabase import get_supabase
from backend.models.common import SuccessResponse, ErrorResponse, ErrorDetail, Meta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


@router.get("/current")
async def get_current_weather():
    """현재 부산 날씨 정보 반환"""
    try:
        sb = get_supabase()

        # 최근 6시간 이내 데이터 조회
        since = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        result = (
            sb.table("weather_data")
            .select("*")
            .gte("timestamp", since)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if result.data and len(result.data) > 0:
            row = result.data[0]
            sky_code = str(row.get("sky_code", "1"))
            rain_type = row.get("rain_type", "없음")
            temperature = row.get("temperature", 0)
            humidity = row.get("humidity", 0)
            wind_speed = row.get("wind_speed", 0)

            # 날씨 상태 판별
            condition = _determine_condition(sky_code, rain_type, temperature)

            return SuccessResponse(
                data={
                    "sky": sky_code,
                    "sky_text": _sky_text(sky_code),
                    "pty": rain_type,
                    "tmp": temperature,
                    "humidity": humidity,
                    "wind_speed": wind_speed,
                    "condition": condition,
                    "timestamp": row.get("timestamp"),
                }
            )

        # 데이터가 없을 경우 기본값 반환
        return SuccessResponse(
            data={
                "sky": "1",
                "sky_text": "맑음",
                "pty": "없음",
                "tmp": 20,
                "humidity": 50,
                "wind_speed": 2.0,
                "condition": "clear_cool",
                "timestamp": None,
            },
            meta=Meta(fallback_used=True),
        )

    except Exception as e:
        logger.error(f"날씨 조회 실패: {e}")
        # 에러 시에도 기본값 반환 (프론트엔드가 배너를 표시할 수 있도록)
        return SuccessResponse(
            data={
                "sky": "1",
                "sky_text": "맑음",
                "pty": "없음",
                "tmp": 20,
                "humidity": 50,
                "wind_speed": 2.0,
                "condition": "clear_cool",
                "timestamp": None,
            },
            meta=Meta(fallback_used=True),
        )


def _sky_text(code: str) -> str:
    """하늘 상태 코드 -> 텍스트"""
    return {"1": "맑음", "3": "구름많음", "4": "흐림"}.get(code, "알 수 없음")


def _determine_condition(sky: str, rain_type: str, tmp: float) -> str:
    """
    날씨 조건 판별 → 프론트엔드 배너 로직에 사용
    - rain: 비/눈
    - clear_hot: 맑음 + 더움 (28도 이상)
    - clear_cool: 맑음 + 선선
    - cloudy: 흐림
    """
    if rain_type not in ("없음", "0", "", None):
        return "rain"
    if sky == "4":
        return "cloudy"
    if sky in ("1", "3") and tmp >= 28:
        return "clear_hot"
    return "clear_cool"


# ────────────────────────────────────────────
# 7일 예보 + 여행 적합도 추천
# ────────────────────────────────────────────

@router.get("/forecast")
async def get_weekly_forecast():
    """7일간 날씨 예보 + 여행 적합도 점수 반환"""
    try:
        sb = get_supabase()

        # 최근 24시간 이내 수집된 예보 데이터 조회 (단기예보는 3일치 제공)
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        result = (
            sb.table("weather_data")
            .select("*")
            .gte("timestamp", since)
            .order("timestamp", desc=True)
            .execute()
        )

        rows = result.data or []

        # 날짜별로 데이터 그룹핑 (forecast_date 기준, 없으면 timestamp 기반)
        daily_data = _group_by_date(rows)

        # 오늘부터 7일간의 예보 생성
        today = datetime.now(timezone(timedelta(hours=9)))  # KST
        forecasts: List[Dict] = []

        for day_offset in range(7):
            target_date = today + timedelta(days=day_offset)
            date_str = target_date.strftime("%Y%m%d")
            date_display = target_date.strftime("%Y-%m-%d")
            day_of_week = target_date.weekday()  # 0=Mon

            if date_str in daily_data:
                # 실제 예보 데이터가 있는 경우
                day_rows = daily_data[date_str]
                forecast = _build_forecast_from_data(day_rows, date_display, day_of_week)
            else:
                # 데이터 없으면 기본값 기반 예보 생성
                forecast = _build_fallback_forecast(date_display, day_of_week, day_offset)

            forecast["is_today"] = (day_offset == 0)
            forecasts.append(forecast)

        # 여행 적합도 점수 기준 상위 3일 추천
        scored = sorted(forecasts, key=lambda x: x["travel_score"], reverse=True)
        recommended_dates = [d["date"] for d in scored[:3]]

        for f in forecasts:
            f["recommended"] = f["date"] in recommended_dates

        return SuccessResponse(
            data={
                "forecasts": forecasts,
                "recommended_dates": recommended_dates,
            }
        )

    except Exception as e:
        logger.error(f"7일 예보 조회 실패: {e}")
        # 에러 시 기본 예보 반환
        return SuccessResponse(
            data={
                "forecasts": _generate_fallback_forecasts(),
                "recommended_dates": [],
            },
            meta=Meta(fallback_used=True),
        )


def _group_by_date(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """DB 데이터를 날짜별로 그룹핑"""
    grouped: Dict[str, List[Dict]] = {}
    for row in rows:
        # forecast_date 필드가 있으면 사용, 없으면 timestamp에서 추출
        fd = row.get("forecast_date", "")
        if not fd and row.get("timestamp"):
            try:
                ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                kst = ts + timedelta(hours=9)
                fd = kst.strftime("%Y%m%d")
            except (ValueError, TypeError):
                continue
        if fd:
            grouped.setdefault(fd, []).append(row)
    return grouped


def _build_forecast_from_data(rows: List[Dict], date_display: str, day_of_week: int) -> Dict:
    """실제 데이터 기반 일별 예보 빌드"""
    temps = []
    humidities = []
    sky_codes = []
    rain_types = []
    rain_probs = []

    for r in rows:
        t = r.get("temperature")
        if t is not None:
            temps.append(float(t))
        h = r.get("humidity")
        if h is not None:
            humidities.append(float(h))
        sc = r.get("sky_code")
        if sc:
            sky_codes.append(str(sc))
        rt = r.get("rain_type", "없음")
        if rt:
            rain_types.append(str(rt))
        # POP(강수확률)이 있으면 수집
        pop = r.get("rain_probability") or r.get("pop")
        if pop is not None:
            try:
                rain_probs.append(float(pop))
            except (ValueError, TypeError):
                pass

    temp_max = max(temps) if temps else 22.0
    temp_min = min(temps) if temps else 15.0
    avg_humidity = sum(humidities) / len(humidities) if humidities else 50.0

    # 가장 빈번한 하늘 상태
    sky = _most_common(sky_codes) if sky_codes else "1"
    rain_type = _most_common(rain_types) if rain_types else "없음"
    rain_prob = max(rain_probs) if rain_probs else (60.0 if rain_type not in ("없음", "0") else 10.0)

    condition = _determine_condition(sky, rain_type, (temp_max + temp_min) / 2)
    travel_score = _calc_travel_score(temp_max, temp_min, avg_humidity, rain_type, rain_prob, sky)

    return {
        "date": date_display,
        "day_of_week": day_of_week,
        "temp_max": round(temp_max, 1),
        "temp_min": round(temp_min, 1),
        "humidity": round(avg_humidity),
        "sky_code": sky,
        "sky_text": _sky_text(sky),
        "rain_type": rain_type,
        "rain_probability": round(rain_prob),
        "condition": condition,
        "travel_score": travel_score,
        "has_data": True,
    }


def _build_fallback_forecast(date_display: str, day_of_week: int, day_offset: int) -> Dict:
    """데이터 없을 때 기본 예보 생성 (점진적 불확실성 증가)"""
    # 기본 봄철 날씨 기준, 먼 미래일수록 불확실
    base_max = 20.0 + (day_offset % 3) * 2
    base_min = 12.0 + (day_offset % 3)
    return {
        "date": date_display,
        "day_of_week": day_of_week,
        "temp_max": base_max,
        "temp_min": base_min,
        "humidity": 55,
        "sky_code": "1" if day_offset % 3 != 2 else "3",
        "sky_text": _sky_text("1" if day_offset % 3 != 2 else "3"),
        "rain_type": "없음",
        "rain_probability": 10 + day_offset * 5,
        "condition": "clear_cool",
        "travel_score": max(50, 85 - day_offset * 5),
        "has_data": False,
    }


def _generate_fallback_forecasts() -> List[Dict]:
    """완전 폴백 (API 에러 시)"""
    today = datetime.now(timezone(timedelta(hours=9)))
    forecasts = []
    for i in range(7):
        d = today + timedelta(days=i)
        f = _build_fallback_forecast(d.strftime("%Y-%m-%d"), d.weekday(), i)
        f["is_today"] = (i == 0)
        f["recommended"] = (i in [0, 1, 3])
        forecasts.append(f)
    return forecasts


def _most_common(items: list) -> str:
    """리스트에서 가장 빈번한 값 반환"""
    if not items:
        return ""
    counts: Dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return max(counts, key=counts.get)


def _calc_travel_score(
    temp_max: float, temp_min: float, humidity: float,
    rain_type: str, rain_prob: float, sky: str,
) -> int:
    """
    여행 적합도 점수 (0~100)
    - 기온 쾌적도 (40%)
    - 강수 (30%)
    - 하늘 상태 (15%)
    - 습도 (15%)
    """
    avg_temp = (temp_max + temp_min) / 2

    # 기온 점수
    if 15 <= avg_temp <= 25:
        temp_score = 100
    elif 10 <= avg_temp < 15 or 25 < avg_temp <= 30:
        temp_score = 70
    elif 5 <= avg_temp < 10 or 30 < avg_temp <= 35:
        temp_score = 40
    else:
        temp_score = 20

    # 강수 점수
    if rain_type not in ("없음", "0"):
        rain_score = 15
    elif rain_prob >= 70:
        rain_score = 30
    elif rain_prob >= 50:
        rain_score = 55
    elif rain_prob >= 30:
        rain_score = 75
    else:
        rain_score = 100

    # 하늘 점수
    sky_scores = {"1": 100, "3": 70, "4": 45}
    sky_score = sky_scores.get(str(sky), 60)

    # 습도 점수
    if 40 <= humidity <= 60:
        humidity_score = 100
    elif 30 <= humidity < 40 or 60 < humidity <= 70:
        humidity_score = 80
    elif 70 < humidity <= 80:
        humidity_score = 50
    else:
        humidity_score = 30

    total = (
        temp_score * 0.40
        + rain_score * 0.30
        + sky_score * 0.15
        + humidity_score * 0.15
    )
    return int(total)
