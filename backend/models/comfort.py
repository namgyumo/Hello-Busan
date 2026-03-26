"""
쾌적도 Pydantic 모델
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ComfortResponse(BaseModel):
    """쾌적도 응답"""
    spot_id: str
    score: float
    crowd_level: float
    label: str
    measured_at: Optional[str] = None


class ComfortDashboard(BaseModel):
    """쾌적도 대시보드"""
    items: List[dict]
    total: int
    updated_at: str
