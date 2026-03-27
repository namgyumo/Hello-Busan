"""
사용자 행동 로그 Pydantic 모델
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import re


class EventType(str, Enum):
    PAGE_VIEW = "page_view"
    SPOT_CLICK = "spot_click"
    CATEGORY_CLICK = "category_click"
    SEARCH = "search"
    MAP_MOVE = "map_move"
    DETAIL_VIEW = "detail_view"
    DETAIL_LEAVE = "detail_leave"
    SHARE = "share"
    FAVORITE = "favorite"
    IMPRESSION = "impression"


# 개인정보 패턴 (전화번호, 이메일)
_PII_PATTERNS = [
    re.compile(r'\b\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{4}\b'),  # 전화번호
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),  # 이메일
    re.compile(r'\b\d{6}[-]?\d{7}\b'),  # 주민등록번호
]


def strip_pii(text: str) -> str:
    """텍스트에서 개인정보 패턴을 제거"""
    for pattern in _PII_PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return text


class UserEvent(BaseModel):
    """단일 사용자 이벤트"""
    session_id: str = Field(..., min_length=1, max_length=36)
    event_type: EventType
    event_data: dict = Field(default_factory=dict)
    spot_id: Optional[int] = None
    page: str = Field(..., min_length=1, max_length=50)

    @field_validator('event_data', mode='before')
    @classmethod
    def sanitize_event_data(cls, v):
        """이벤트 데이터 내 개인정보 필터링"""
        if not isinstance(v, dict):
            return v
        sanitized = {}
        for key, val in v.items():
            if isinstance(val, str):
                sanitized[key] = strip_pii(val)
            else:
                sanitized[key] = val
        return sanitized


class EventBatchRequest(BaseModel):
    """배치 이벤트 요청"""
    events: list[UserEvent] = Field(..., min_length=1, max_length=50)


class EventBatchResponse(BaseModel):
    """배치 이벤트 응답"""
    accepted: int
    message: str = "ok"
