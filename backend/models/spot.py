"""
관광지 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SpotResponse(BaseModel):
    """관광지 응답 모델"""
    id: str
    content_id: Optional[str] = None
    name: str
    category: str
    address: Optional[str] = ""
    lat: float
    lng: float
    image_url: Optional[str] = ""
    thumbnail_url: Optional[str] = ""
    tel: Optional[str] = ""
    rating: Optional[float] = 0.0
    view_count: Optional[int] = 0
    description: Optional[str] = ""

    class Config:
        from_attributes = True


class SpotDetail(SpotResponse):
    """관광지 상세 모델"""
    overview: Optional[str] = ""
    homepage: Optional[str] = ""
    open_time: Optional[str] = ""
    rest_date: Optional[str] = ""
    parking: Optional[str] = ""
    comfort: Optional[dict] = None
    nearby_spots: Optional[List[dict]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SpotListResponse(BaseModel):
    """관광지 목록 응답"""
    spots: List[SpotResponse]
    total: int
    page: int = 1
    size: int = 20
