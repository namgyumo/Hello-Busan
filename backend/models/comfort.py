"""
쾌적함 지수 Pydantic 모델 — API 설계서 기준
"""
from pydantic import BaseModel
from typing import Optional


class ComfortComponent(BaseModel):
    """쾌적함 구성 요소"""
    score: int
    weight: float
    detail: Optional[dict] = None


class ComfortResponse(BaseModel):
    """쾌적함 지수 응답 (API-005)"""
    spot_id: str
    score: int
    grade: str
    components: Optional[dict] = None
    updated_at: Optional[str] = None


class ComfortBulkItem(BaseModel):
    """일괄 조회 아이템 (API-006)"""
    spot_id: str
    score: int
    grade: str
    lat: float
    lng: float


class HeatmapConfig(BaseModel):
    """히트맵 설정"""
    radius: int = 25
    blur: int = 15
    max_zoom: int = 17
    gradient: dict = {
        "0.4": "green",
        "0.6": "yellow",
        "0.8": "orange",
        "1.0": "red",
    }


class HeatmapResponse(BaseModel):
    """히트맵 데이터 응답 (API-007)"""
    points: list  # [[lat, lng, intensity], ...]
    config: HeatmapConfig = HeatmapConfig()
