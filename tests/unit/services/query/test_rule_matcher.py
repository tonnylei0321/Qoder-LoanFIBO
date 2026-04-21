"""规则匹配器单元测试"""
import pytest
from backend.app.services.query.rule_matcher import RuleMatcher, CompiledRule


@pytest.fixture
def matcher():
    return RuleMatcher()


@pytest.fixture
def sample_rules():
    return [
        CompiledRule(
            id="r1", intent_id="query_loan_amount", table="bd_loan_contract",
            columns=["loan_amount"], conditions=[], priority=10
        ),
        CompiledRule(
            id="r2", intent_id="query_overdue_ratio", table="bd_loan_contract",
            columns=["overdue_amount", "total_amount"], conditions=[], priority=5
        ),
    ]


class TestRuleMatcher:
    def test_match_by_intent(self, matcher, sample_rules):
        rule = matcher.match("query_loan_amount", {}, sample_rules)
        assert rule is not None
        assert rule.id == "r1"

    def test_no_match_returns_none(self, matcher, sample_rules):
        rule = matcher.match("unknown_intent", {}, sample_rules)
        assert rule is None

    def test_match_highest_priority(self, matcher):
        rules = [
            CompiledRule(id="r1", intent_id="q1", table="t1", columns=[], conditions=[], priority=5),
            CompiledRule(id="r2", intent_id="q1", table="t2", columns=[], conditions=[], priority=10),
        ]
        rule = matcher.match("q1", {}, rules)
        assert rule.id == "r2"
