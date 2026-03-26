"""
공통 Pydantic 모델
"""
from pydantic import BaseModel
from typing import Optional, List, Any


class PaginatedResponse(BaseModel):
    """페이지네이션 응답"""
    items: List[Any]
    total: int
    page: int = 1
    size: int = 20
    has_next: bool = False


class ErrorResponse(BaseModel):
    """에러 응답"""
    detail: str
    status_code: int = 500


class HealthResponse(BaseModel):
    """헬스체크 응답"""
    status: str = "healthy"
    version: str = "1.0.0"
    services: Optional[dict] = None
