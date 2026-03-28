"""
AI 추천 API 라우터 — 대화형 관광지 추천
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.config import settings
import logging

router = APIRouter(prefix="/api/v1", tags=["ai"])
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str = Field(..., description="user 또는 assistant")
    content: str = Field(..., description="메시지 내용")


class AIChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, description="대화 히스토리")


class AIChatResponse(BaseModel):
    type: str  # "message" 또는 "recommendation"
    message: str
    filters: Optional[dict] = None
    recommendations: Optional[list] = None


@router.post("/ai/chat", response_model=AIChatResponse)
async def ai_chat(req: AIChatRequest):
    """대화형 AI 관광지 추천"""
    if not getattr(settings, "GEMINI_API_KEY", ""):
        raise HTTPException(status_code=503, detail="AI 추천 서비스가 현재 사용 불가합니다")

    last_msg = req.messages[-1]
    if last_msg.role != "user" or len(last_msg.content.strip()) < 2:
        raise HTTPException(status_code=400, detail="메시지를 2자 이상 입력해주세요")

    try:
        from backend.services.ai_recommend import AIRecommendService
        service = AIRecommendService()
        messages = [{"role": m.role, "content": m.content} for m in req.messages]
        result = await service.chat(messages)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI 대화 실패: {e}")
        raise HTTPException(status_code=500, detail="AI 추천 생성 중 오류 발생")
