"""
Pydantic 모델 단위 테스트
- SuccessResponse, Meta, ErrorResponse
"""
import pytest
from backend.models.common import SuccessResponse, Meta, ErrorDetail, ErrorResponse


class TestMeta:
    def test_default_meta(self):
        meta = Meta()
        assert meta.fallback_used is False
        assert meta.total is None
        assert meta.timestamp.endswith("Z")

    def test_custom_meta(self):
        meta = Meta(total=42, limit=20, offset=0, fallback_used=True)
        assert meta.total == 42
        assert meta.limit == 20
        assert meta.fallback_used is True

    def test_timestamp_auto_generated(self):
        m1 = Meta()
        m2 = Meta()
        assert m1.timestamp  # not empty
        assert m2.timestamp


class TestSuccessResponse:
    def test_default_success(self):
        resp = SuccessResponse()
        assert resp.success is True
        assert resp.data is None

    def test_with_data(self):
        resp = SuccessResponse(data=[{"id": 1}])
        assert resp.success is True
        assert len(resp.data) == 1

    def test_with_meta(self):
        resp = SuccessResponse(
            data=[], meta=Meta(total=0, fallback_used=False)
        )
        assert resp.meta.total == 0

    def test_serialization(self):
        resp = SuccessResponse(data={"key": "value"})
        d = resp.model_dump()
        assert d["success"] is True
        assert d["data"] == {"key": "value"}
        assert "meta" in d


class TestErrorResponse:
    def test_error_response(self):
        resp = ErrorResponse(
            error=ErrorDetail(code="4001", message="Not Found")
        )
        assert resp.success is False
        assert resp.error.code == "4001"

    def test_error_with_fallback(self):
        resp = ErrorResponse(
            error=ErrorDetail(
                code="3001",
                message="API Error",
                fallback_used=True,
                fallback_type="cached_data",
            )
        )
        assert resp.error.fallback_used is True
        assert resp.error.fallback_type == "cached_data"
