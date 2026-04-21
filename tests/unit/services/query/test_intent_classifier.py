"""意图分类器单元测试"""
import pytest
from backend.app.services.query.intent_classifier import IntentClassifier, ClassificationResult


@pytest.fixture
def classifier():
    templates = [
        {
            "intent_id": "query_loan_amount",
            "patterns": ["贷款金额", "loan amount", "贷款余额"],
            "slots": ["time", "entity"],
        },
        {
            "intent_id": "query_overdue_ratio",
            "patterns": ["逾期率", "overdue ratio", "不良率"],
            "slots": ["time"],
        },
    ]
    return IntentClassifier(templates=templates)


class TestIntentClassifier:
    @pytest.mark.asyncio
    async def test_template_match_exact(self, classifier):
        result = await classifier.classify("贷款金额")
        assert result.intent_id == "query_loan_amount"
        assert result.confidence >= 0.95
        assert result.query_type == "predefined"

    @pytest.mark.asyncio
    async def test_template_match_partial(self, classifier):
        result = await classifier.classify("查询贷款金额")
        assert result.intent_id == "query_loan_amount"
        assert result.confidence > 0.7

    @pytest.mark.asyncio
    async def test_no_match_returns_unknown(self, classifier):
        result = await classifier.classify("今天天气怎么样")
        assert result.intent_id == "unknown"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_overdue_ratio_match(self, classifier):
        result = await classifier.classify("逾期率")
        assert result.intent_id == "query_overdue_ratio"
