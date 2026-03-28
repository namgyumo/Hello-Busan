"""
Gemini 2.5 Flash Lite 기반 AI 관광지 추천 서비스
- 대화형: 맥락을 유지하며 질문 → 요구사항 파악 → 추천
- 추천 시: 필터 추출 → DB 후보 축소 → TOP 10 선정
"""

import json
import logging
from typing import Dict, List

import google.generativeai as genai

from backend.config import settings
from backend.db.supabase import get_supabase

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ["nature", "culture", "activity", "shopping", "food", "nightview", "heritage"]

# 대화형 시스템 프롬프트
CHAT_SYSTEM_PROMPT = """\
당신은 "헬로부산 AI"입니다. 부산 관광지를 추천해주는 친절한 여행 컨설턴트입니다.

## 역할
사용자의 요구사항을 대화를 통해 파악한 뒤, 최적의 관광지를 추천합니다.

## 대화 규칙
1. 사용자의 요청이 모호하면 1~2개의 짧은 질문으로 취향을 파악하세요.
   - 예: 동행자(혼자/커플/가족/친구), 분위기(힐링/액티브/감성), 실내/실외, 지역 선호 등
2. 질문은 한 번에 최대 2개까지만 하세요. 너무 많이 묻지 마세요.
3. 충분한 정보가 모이면 (보통 1~2번의 대화 후) 추천을 제공하세요.
4. 사용자가 처음부터 구체적으로 요청하면 바로 추천하세요.
5. 답변은 짧고 친근하게, 한국어로 작성하세요.

## 응답 형식
반드시 아래 JSON 형식으로만 응답하세요. 설명이나 마크다운 없이 JSON만 출력하세요.

질문이 필요한 경우:
{"action": "ask", "message": "질문 내용"}

추천할 준비가 된 경우:
{"action": "recommend", "message": "추천 소개 멘트", "filters": {"category_ids": [], "mood": "", "indoor_outdoor": "", "area": "", "time_of_day": []}}

filters 필드 설명:
- category_ids: nature, culture, activity, shopping, food, nightview, heritage 중 선택
  * heritage(문화재)는 박물관 소장 유물/보물/무형문화재 등으로, 사용자가 "문화재", "보물", "유물", "국보" 등을 명시적으로 언급했을 때만 포함하세요.
  * "박물관", "역사", "문화" 등 일반적인 표현은 culture 카테고리를 사용하세요. heritage를 포함하지 마세요.
- mood: 분위기 키워드 (로맨틱, 가족, 힐링, 액티브, 감성, 맛집탐방 등)
- indoor_outdoor: indoor, outdoor, both 중 하나
- area: 부산 내 지역 (해운대, 광안리, 서면, 남포동, 기장 등)
- time_of_day: morning, afternoon, evening, night 중 선택
- 확실하지 않은 필터는 빈 값으로 두세요
"""

# TOP 10 선정 프롬프트
RANKING_PROMPT = """\
당신은 부산 관광 전문가입니다.
아래 대화 맥락과 관광지 후보를 분석하여, 가장 적합한 10개를 선정해주세요.

대화 맥락:
{conversation_summary}

관광지 후보 목록:
{candidates_text}

응답 규칙:
- 반드시 10개를 선정하세요. 후보가 10개 미만이면 모두 선정하세요.
- 각 관광지에 대해 사용자 요청에 맞는 구체적인 추천 이유를 2~3문장으로 작성하세요.
- 반드시 아래 JSON 형식만 출력하세요. 설명이나 마크다운 없이 JSON만 출력하세요.

JSON 형식:
[
  {{"id": "관광지ID", "reason": "추천 이유"}},
  ...
]

JSON 응답:"""


def _strip_code_block(text: str) -> str:
    """마크다운 코드블록 제거"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


class AIRecommendService:
    """Gemini 2.5 Flash Lite 기반 대화형 AI 관광지 추천 서비스"""

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def chat(self, messages: List[Dict]) -> dict:
        """
        대화형 추천 파이프라인.
        messages: [{"role": "user"|"assistant", "content": "..."}]
        반환: {"type": "message"|"recommendation", "message": "...", ...}
        """
        # Gemini 대화 컨텍스트 구성
        gemini_history = []
        for msg in messages[:-1]:  # 마지막 메시지 제외 (현재 입력)
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        current_message = messages[-1]["content"]

        # Gemini 대화 시작
        chat = self.model.start_chat(history=gemini_history)

        try:
            prompt = f"{CHAT_SYSTEM_PROMPT}\n\n사용자: {current_message}"
            response = await chat.send_message_async(prompt)
            raw_text = _strip_code_block(response.text)
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning(f"대화 JSON 파싱 실패, 원본: {response.text[:200]}")
            # 파싱 실패 시 텍스트 그대로 반환
            return {"type": "message", "message": response.text.strip()}
        except Exception as e:
            logger.error(f"Gemini 대화 실패: {e}")
            return {"type": "message", "message": "죄송합니다, 일시적인 오류가 발생했어요. 다시 말씀해 주세요!"}

        action = result.get("action", "ask")
        ai_message = result.get("message", "")

        if action == "recommend":
            # 추천 모드: 필터 추출 → DB 검색 → 랭킹
            filters = result.get("filters", {})
            if "category_ids" in filters:
                filters["category_ids"] = [
                    c for c in filters["category_ids"] if c in VALID_CATEGORIES
                ]

            # heritage는 사용자가 명시적으로 문화재를 요청한 경우만 포함
            heritage_keywords = ["문화재", "보물", "유물", "국보", "사적", "무형문화재"]
            full_conversation = " ".join(m["content"] for m in messages if m["role"] == "user")
            user_wants_heritage = any(kw in full_conversation for kw in heritage_keywords)
            if not user_wants_heritage and "category_ids" in filters:
                filters["category_ids"] = [
                    c for c in filters["category_ids"] if c != "heritage"
                ]

            logger.info(f"추천 필터: {filters}")

            candidates = await self._search_candidates(filters)

            # 대화 맥락 요약 (랭킹 프롬프트용)
            conversation_summary = "\n".join(
                f"{'사용자' if m['role'] == 'user' else 'AI'}: {m['content']}"
                for m in messages
            )

            recommendations = await self._rank_spots(conversation_summary, candidates)

            return {
                "type": "recommendation",
                "message": ai_message,
                "filters": filters,
                "recommendations": recommendations,
            }
        else:
            # 질문 모드
            return {"type": "message", "message": ai_message}

    async def _search_candidates(self, filters: dict) -> list:
        """추출된 필터로 Supabase 쿼리하여 50개 후보 축소"""
        sb = get_supabase()

        query = (
            sb.table("tourist_spots")
            .select("id, name, category_id, address, description, images, lat, lng")
            .eq("is_active", True)
        )

        category_ids = filters.get("category_ids", [])
        if category_ids:
            if len(category_ids) == 1:
                query = query.eq("category_id", category_ids[0])
            else:
                query = query.in_("category_id", category_ids)
        else:
            # 카테고리 미지정 시 heritage 제외
            query = query.neq("category_id", "heritage")

        result = query.limit(50).execute()
        candidates = result.data or []

        area = filters.get("area")
        if area and candidates:
            area_filtered = [
                c for c in candidates
                if area in (c.get("address") or "")
            ]
            if len(area_filtered) >= 5:
                candidates = area_filtered

        logger.info(f"후보 {len(candidates)}건 검색 완료")
        return candidates

    async def _rank_spots(self, conversation_summary: str, candidates: list) -> list:
        """후보 관광지 중 TOP 10 선정 + 추천 이유 생성"""
        if not candidates:
            return []

        candidates_text = "\n".join(
            f"- ID: {c['id']}, 이름: {c['name']}, "
            f"카테고리: {c.get('category_id', '')}, "
            f"주소: {c.get('address', '')}, "
            f"설명: {(c.get('description') or '')[:100]}"
            for c in candidates
        )

        prompt = RANKING_PROMPT.format(
            conversation_summary=conversation_summary,
            candidates_text=candidates_text,
        )

        try:
            response = await self.model.generate_content_async(prompt)
            raw_text = _strip_code_block(response.text)
            rankings = json.loads(raw_text)
        except json.JSONDecodeError as e:
            logger.warning(f"랭킹 JSON 파싱 실패: {e}")
            rankings = [
                {"id": c["id"], "reason": f"{c['name']} — 부산의 인기 관광지입니다."}
                for c in candidates[:10]
            ]
        except Exception as e:
            logger.error(f"Gemini 랭킹 실패: {e}")
            rankings = [
                {"id": c["id"], "reason": f"{c['name']} — 부산의 인기 관광지입니다."}
                for c in candidates[:10]
            ]

        candidates_map = {str(c["id"]): c for c in candidates}
        results = []

        for rank in rankings[:10]:
            spot_id = str(rank.get("id", ""))
            spot = candidates_map.get(spot_id)
            if not spot:
                continue

            results.append({
                "id": spot["id"],
                "name": spot["name"],
                "category_id": spot.get("category_id", ""),
                "address": spot.get("address", ""),
                "images": spot.get("images", []),
                "reason": rank.get("reason", ""),
                "lat": spot.get("lat", 0.0),
                "lng": spot.get("lng", 0.0),
            })

        logger.info(f"TOP {len(results)} 선정 완료")
        return results
