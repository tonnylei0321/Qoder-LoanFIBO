"""DSL执行引擎单元测试"""
import pytest
from backend.app.services.rules.dsl_executor import DSLExecutor
from backend.app.services.security_error import SecurityError
from backend.app.services.rules.dsl_parser import DSLFormula


@pytest.fixture
def executor():
    return DSLExecutor()


class TestDSLExecutor:
    def test_evaluate_simple_comparison(self, executor):
        formula = DSLFormula(field_name="loan_amount", operator=">", right_value=1000000)
        result = executor.evaluate(formula, {"loan_amount": 2000000})
        assert result is True

    def test_evaluate_false_comparison(self, executor):
        formula = DSLFormula(field_name="loan_amount", operator=">", right_value=1000000)
        result = executor.evaluate(formula, {"loan_amount": 500000})
        assert result is False

    def test_evaluate_between(self, executor):
        formula = DSLFormula(
            field_name="ratio", operator="between", right_value=(0.3, 0.8)
        )
        assert executor.evaluate(formula, {"ratio": 0.5}) is True
        assert executor.evaluate(formula, {"ratio": 0.9}) is False

    def test_evaluate_compound_and(self, executor):
        formula = DSLFormula(
            field_name="_compound",
            operator="compound",
            right_value=None,
            connector="AND",
            children=[
                DSLFormula(field_name="amount", operator=">", right_value=100),
                DSLFormula(field_name="risk", operator="=", right_value="high"),
            ],
        )
        assert executor.evaluate(formula, {"amount": 200, "risk": "high"}) is True
        assert executor.evaluate(formula, {"amount": 50, "risk": "high"}) is False

    def test_missing_field_returns_false(self, executor):
        formula = DSLFormula(field_name="nonexistent", operator=">", right_value=0)
        result = executor.evaluate(formula, {})
        assert result is False
