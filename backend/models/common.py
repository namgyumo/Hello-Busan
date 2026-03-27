"""
공통 Pydantic 모델 — API 설계서 공통 응답 형식
"""
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime, timezone


class Meta(BaseModel):
    """공통 메타 정보"""
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    timestamp: str = ""
    fallback_used: bool = False
    personalized: bool = False
    experiment_bucket: Optional[str] = None

    def __init__(self, **data):
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        super().__init__(**data)


class SuccessResponse(BaseModel):
    """성공 응답 (단일/목록)"""
    success: bool = True
    data: Any = None
    meta: Meta = Meta()


class ErrorDetail(BaseModel):
    """에러 상세"""
    code: str
    message: str
    detail: Optional[str] = None
    fallback_used: bool = False
    fallback_type: Optional[str] = None


class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = False
    error: ErrorDetail
