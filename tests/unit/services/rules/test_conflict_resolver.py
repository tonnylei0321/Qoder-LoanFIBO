"""规则冲突检测与解决单元测试"""
import pytest
from backend.app.services.rules.conflict_resolver import ConflictResolver, Conflict, ConflictSeverity


class TestConflictResolver:
    @pytest.fixture
    def resolver(self):
        return ConflictResolver()

    @pytest.fixture
    def rules(self):
        return [
            {"id": "r1", "intent_id": "query_loan", "table": "bd_loan_contract",
             "columns": ["loan_amount"], "priority": 10},
            {"id": "r2", "intent_id": "query_loan", "table": "bd_loan_contract",
             "columns": ["loan_amount", "contract_status"], "priority": 5},
            {"id": "r3", "intent_id": "query_overdue", "table": "bd_loan_contract",
             "columns": ["overdue_amount"], "priority": 8},
        ]

    def test_detect_intent_conflict(self, resolver, rules):
        """同一intent_id的规则应产生冲突"""
        conflicts = resolver.detect(rules)
        # r1 and r2 share intent_id "query_loan"
        intent_conflicts = [c for c in conflicts if c.conflict_type == "duplicate_intent"]
        assert len(intent_conflicts) >= 1

    def test_no_conflict_different_intent(self, resolver, rules):
        """不同intent_id不应冲突"""
        conflicts = resolver.detect(rules)
        r3_conflicts = [c for c in conflicts if "r3" in c.rule_ids and c.conflict_type == "duplicate_intent"]
        assert len(r3_conflicts) == 0

    def test_resolve_keeps_higher_priority(self, resolver, rules):
        """冲突解决应保留高优先级规则"""
        resolved = resolver.resolve(rules)
        loan_rules = [r for r in resolved if r["intent_id"] == "query_loan"]
        assert len(loan_rules) == 1
        assert loan_rules[0]["priority"] == 10  # r1 has higher priority

    def test_empty_rules_no_conflict(self, resolver):
        conflicts = resolver.detect([])
        assert conflicts == []

    def test_single_rule_no_conflict(self, resolver):
        conflicts = resolver.detect([{"id": "r1", "intent_id": "q1", "priority": 1}])
        assert conflicts == []

    def test_conflict_severity(self, resolver):
        c = Conflict(
            conflict_type="duplicate_intent",
            rule_ids=["r1", "r2"],
            severity=ConflictSeverity.WARNING,
            message="Duplicate intent_id"
        )
        assert c.severity == ConflictSeverity.WARNING
        assert "r1" in c.rule_ids
