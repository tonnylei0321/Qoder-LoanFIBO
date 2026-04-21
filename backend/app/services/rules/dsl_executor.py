"""DSL执行引擎 - 安全公式求值"""
from typing import Any, Dict, Optional

from loguru import logger

from backend.app.services.rules.dsl_parser import DSLFormula


class SecurityError(Exception):
    """执行安全异常"""
    pass


class DSLExecutor:
    """DSL执行引擎（同步实现，供to_thread调用）"""

    def __init__(self, max_ast_depth: int = 50, execution_timeout: int = 5):
        self.max_ast_depth = max_ast_depth
        self.execution_timeout = execution_timeout

    def evaluate(self, formula: DSLFormula, context: Dict[str, Any]) -> bool:
        if formula.depth > self.max_ast_depth:
            raise SecurityError(f"AST深度超过限制: {formula.depth}")

        if formula.operator == "compound":
            return self._evaluate_compound(formula, context)

        left_value = context.get(formula.field_name)
        if left_value is None:
            return False

        return self._compare(left_value, formula.operator, formula.right_value)

    def _evaluate_compound(self, formula: DSLFormula, context: Dict[str, Any]) -> bool:
        results = [self.evaluate(child, context) for child in formula.children]
        if formula.connector == "AND":
            return all(results)
        elif formula.connector == "OR":
            return any(results)
        return False

    def _compare(self, left: Any, operator: str, right: Any) -> bool:
        try:
            if operator == ">":
                return left > right
            elif operator == ">=":
                return left >= right
            elif operator == "<":
                return left < right
            elif operator == "<=":
                return left <= right
            elif operator in ("=", "=="):
                return left == right
            elif operator in ("!=", "<>"):
                return left != right
            elif operator == "between":
                low, high = right
                return low <= left <= high
        except TypeError:
            return False
        return False
