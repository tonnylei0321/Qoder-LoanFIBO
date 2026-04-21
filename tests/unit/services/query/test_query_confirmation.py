"""查询确认服务单元测试"""
import pytest
from backend.app.services.query.query_confirmation import QueryConfirmationService


class TestQueryConfirmationService:
    @pytest.fixture
    def service(self):
        return QueryConfirmationService()

    def test_needs_confirmation_high_confidence(self, service):
        """高置信度不需要确认"""
        assert service.needs_confirmation(confidence=0.99) is False

    def test_needs_confirmation_medium_confidence(self, service):
        """中等置信度需要确认"""
        assert service.needs_confirmation(confidence=0.75) is True

    def test_needs_confirmation_low_confidence(self, service):
        """低置信度需要确认"""
        assert service.needs_confirmation(confidence=0.3) is True

    def test_build_confirmation_message(self, service):
        msg = service.build_confirmation_message(
            intent_id="query_loan_amount",
            confidence=0.8,
            matched_pattern="贷款金额"
        )
        assert "query_loan_amount" in msg
        assert "贷款金额" in msg

    def test_build_rejection_message(self, service):
        msg = service.build_rejection_message(query="今天天气")
        assert "今天天气" in msg
