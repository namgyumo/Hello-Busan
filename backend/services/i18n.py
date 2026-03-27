"""
다국어 서비스
- 서버사이드 번역 지원
- 5개 언어: ko, en, ja, zh, ru
"""
from typing import Dict, Optional
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["ko", "en", "ja", "zh", "ru"]
DEFAULT_LANGUAGE = "ko"
LOCALES_DIR = Path(__file__).parent.parent.parent / "frontend" / "locales"


class I18nService:
    """다국어 서비스"""

    def __init__(self):
        self._translations: Dict[str, Dict] = {}
        self._load_translations()

    def _load_translations(self):
        """번역 파일 로드"""
        for lang in SUPPORTED_LANGUAGES:
            path = LOCALES_DIR / f"{lang}.json"
            try:
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        self._translations[lang] = json.load(f)
                    logger.info(f"번역 로드: {lang}")
                else:
                    logger.warning(f"번역 파일 없음: {path}")
            except Exception as e:
                logger.error(f"번역 로드 실패 [{lang}]: {e}")

    def translate(
        self, key: str, lang: Optional[str] = None
    ) -> str:
        """번역"""
        lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        translations = self._translations.get(lang, {})
        return translations.get(key, key)

    def get_translations(self, lang: str) -> Dict:
        """전체 번역 데이터"""
        if lang not in SUPPORTED_LANGUAGES:
            lang = DEFAULT_LANGUAGE
        return self._translations.get(lang, {})

    def get_supported_languages(self):
        """지원 언어 목록"""
        return SUPPORTED_LANGUAGES
