"""
Hello-Busan 테스트 공통 fixture
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ── Supabase 모킹 ──

class FakeQueryBuilder:
    """Supabase 쿼리 빌더 모킹"""

    def __init__(self, data=None):
        self._data = data or []

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def in_(self, *a, **kw):
        return self

    def neq(self, *a, **kw):
        return self

    def order(self, *a, **kw):
        return self

    def range(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def single(self, *a, **kw):
        return self

    def upsert(self, *a, **kw):
        return self

    def execute(self):
        result = MagicMock()
        result.data = self._data
        return result


class FakeSupabase:
    """Supabase 클라이언트 모킹"""

    def __init__(self, table_data=None):
        self._table_data = table_data or {}

    def table(self, name):
        data = self._table_data.get(name, [])
        return FakeQueryBuilder(data)


@pytest.fixture
def fake_supabase():
    """기본 빈 Supabase 모킹"""
    return FakeSupabase()


@pytest.fixture
def sample_spots():
    """테스트용 관광지 목록"""
    return [
        {
            "id": 1,
            "name": "해운대 해수욕장",
            "category_id": "nature",
            "lat": 35.1587,
            "lng": 129.1604,
            "is_active": True,
            "images": ["https://example.com/haeundae.jpg"],
        },
        {
            "id": 2,
            "name": "감천문화마을",
            "category_id": "culture",
            "lat": 35.0975,
            "lng": 129.0108,
            "is_active": True,
            "images": [],
        },
        {
            "id": 3,
            "name": "자갈치시장",
            "category_id": "food",
            "lat": 35.0968,
            "lng": 129.0309,
            "is_active": True,
            "images": ["https://example.com/jagalchi.jpg"],
        },
    ]


@pytest.fixture
def sample_comfort_data():
    """테스트용 쾌적도 데이터"""
    return {
        "1": {
            "total_score": 85,
            "grade": "쾌적",
            "weather_score": 80,
            "crowd_score": 90,
            "transport_score": 75,
            "crowd_level": 0.1,
        },
        "2": {
            "total_score": 55,
            "grade": "혼잡",
            "weather_score": 60,
            "crowd_score": 40,
            "transport_score": 70,
            "crowd_level": 0.6,
        },
    }
