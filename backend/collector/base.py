"""
데이터 수집기 기본 클래스 (추상)
- 공통 HTTP 요청 로직
- 재시도 / 에러 핸들링
- 수집 결과 저장 인터페이스
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """공공데이터 수집기 추상 클래스"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 (재사용)"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self):
        """클라이언트 종료"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def fetch(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        API 요청 + 재시도 로직
        - 지수 백오프 적용
        - 에러 시 None 반환
        """
        client = await self.get_client()
        if params is None:
            params = {}
        params["serviceKey"] = self.api_key

        for attempt in range(self.max_retries):
            try:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                data = response.json()
                return self._parse_response(data)
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"[{self.__class__.__name__}] HTTP {e.response.status_code} "
                    f"attempt {attempt + 1}/{self.max_retries}"
                )
            except httpx.RequestError as e:
                logger.warning(
                    f"[{self.__class__.__name__}] Request error: {e} "
                    f"attempt {attempt + 1}/{self.max_retries}"
                )
            except Exception as e:
                logger.error(
                    f"[{self.__class__.__name__}] Unexpected error: {e}"
                )
                return None

            if attempt < self.max_retries - 1:
                wait = 2 ** attempt
                await asyncio.sleep(wait)

        logger.error(f"[{self.__class__.__name__}] 최대 재시도 초과: {endpoint}")
        return None

    def _parse_response(self, data: Dict) -> Optional[Dict]:
        """공공데이터포털 공통 응답 파싱"""
        try:
            header = data.get("response", {}).get("header", {})
            result_code = header.get("resultCode", "")
            if result_code not in ("0000", "00"):
                logger.warning(f"API 응답 에러: {header.get('resultMsg')}")
                return None
            return data["response"]["body"]
        except (KeyError, TypeError) as e:
            logger.error(f"응답 파싱 실패: {e}")
            return None

    @abstractmethod
    async def collect(self) -> List[Dict]:
        """데이터 수집 (하위 클래스 구현)"""
        pass

    @abstractmethod
    async def save(self, data: List[Dict]) -> int:
        """수집 데이터 저장 (하위 클래스 구현)"""
        pass

    async def run(self) -> Dict[str, Any]:
        """수집 + 저장 파이프라인 실행"""
        start = datetime.now()
        try:
            data = await self.collect()
            saved = await self.save(data) if data else 0
            elapsed = (datetime.now() - start).total_seconds()
            result = {
                "collector": self.__class__.__name__,
                "collected": len(data) if data else 0,
                "saved": saved,
                "elapsed_seconds": elapsed,
                "status": "success",
            }
            logger.info(f"수집 완료: {result}")
            return result
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds()
            logger.error(f"수집 실패: {e}")
            return {
                "collector": self.__class__.__name__,
                "error": str(e),
                "elapsed_seconds": elapsed,
                "status": "failed",
            }
        finally:
            await self.close()
