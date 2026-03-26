"""
관광지 Pydantic 모델 — API 설계서 기준
"""
from pydantic import BaseModel
from typing import Optional, List


class SpotResponse(BaseModel):
    """관광지 목록 아이템 (API-001 응답)"""
    id: str
    name: str
    category: str
    category_name: Optional[str] = ""
    lat: float
    lng: float
    distance_km: Optional[float] = None
    comfort_score: Optional[int] = None
    comfort_grade: Optional[str] = None
    recommend_score: Optional[float] = None
    thumbnail_url: Optional[str] = ""
    crowd_level: Optional[str] = None
    weather_summary: Optional[str] = None

    class Config:
        from_attributes = True


class NearbySpot(BaseModel):
    """주변 추천 관광지"""
    id: str
    name: str
    distance_km: float


class ComfortDetail(BaseModel):
    """쾌적함 상세 (상세 페이지용)"""
    score: int
    grade: str
    weather: Optional[dict] = None
    crowd: Optional[dict] = None
    transport: Optional[dict] = None


class TransportInfo(BaseModel):
    """교통 정보"""
    nearest_station: Optional[str] = None
    bus_routes: Optional[List[str]] = []
    walk_from_station_min: Optional[int] = None


class SpotDetail(BaseModel):
    """관광지 상세 (API-002 응답)"""
    id: str
    name: str
    category: str
    description: Optional[str] = ""
    images: Optional[List[str]] = []
    lat: float
    lng: float
    address: Optional[str] = ""
    operating_hours: Optional[str] = ""
    admission_fee: Optional[str] = ""
    phone: Optional[str] = ""
    comfort: Optional[ComfortDetail] = None
    transport_info: Optional[TransportInfo] = None
    nearby_spots: Optional[List[NearbySpot]] = []

    class Config:
        from_attributes = True


class CategoryItem(BaseModel):
    """카테고리 아이템 (API-003)"""
    id: str
    name: str
    icon: str
    spot_count: int = 0


class RecommendItem(BaseModel):
    """추천 아이템 (API-004 응답)"""
    rank: int
    id: str
    name: str
    category: str
    recommend_score: float
    comfort_score: Optional[int] = None
    distance_km: Optional[float] = None
    reasons: Optional[List[str]] = []
    thumbnail_url: Optional[str] = ""
