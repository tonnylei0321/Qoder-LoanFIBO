"""DSL解析器单元测试"""
import pytest
from backend.app.services.rules.dsl_parser import DSLParser, DSLFormula


class TestDSLParser:
    @pytest.fixture
    def parser(self):
        return DSLParser()

    def test_parse_simple_comparison(self, parser):
        formula = parser.parse("loan_amount > 1000000")
        assert formula is not None
        assert formula.operator == ">"
        assert formula.right_value == 1000000

    def test_parse_range_condition(self, parser):
        formula = parser.parse("100000 <= loan_amount <= 500000")
        assert formula is not None
        assert formula.operator == "between"

    def test_parse_compound_condition(self, parser):
        formula = parser.parse("loan_amount > 1000000 AND risk_level = 'high'")
        assert formula is not None
        assert formula.connector == "AND"

    def test_parse_invalid_formula(self, parser):
        with pytest.raises(ValueError):
            parser.parse("!!!invalid!!!")

    def test_parse_threshold_rule(self, parser):
        formula = parser.parse("ratio > 0.8")
        assert formula.operator == ">"
        assert formula.right_value == 0.8
