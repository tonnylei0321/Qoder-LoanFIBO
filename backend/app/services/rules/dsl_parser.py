"""DSL解析器 - 规则公式语法解析"""
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


@dataclass
class DSLFormula:
    """DSL公式AST节点"""

    field_name: str
    operator: str
    right_value: Any
    connector: Optional[str] = None  # AND / OR
    children: List["DSLFormula"] = field(default_factory=list)

    @property
    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(c.depth for c in self.children)


class DSLParser:
    """DSL公式解析器"""

    OPERATORS = {
        ">": ">",
        ">=": ">=",
        "<": "<",
        "<=": "<=",
        "=": "=",
        "==": "=",
        "!=": "!=",
        "<>": "!=",
    }

    def parse(self, formula: str) -> DSLFormula:
        formula = formula.strip()
        if not formula:
            raise ValueError("空公式")

        # 处理 AND/OR 连接
        for connector in [" AND ", " OR "]:
            parts = self._split_by_connector(formula, connector.strip())
            if len(parts) > 1:
                children = [self.parse(p.strip()) for p in parts]
                return DSLFormula(
                    field_name="_compound",
                    operator="compound",
                    right_value=None,
                    connector=connector.strip(),
                    children=children,
                )

        # 处理 between keyword
        between_match = re.match(
            r"(\S+)\s+between\s+(\S+)\s+and\s+(\S+)", formula, re.IGNORECASE
        )
        if between_match:
            return DSLFormula(
                field_name=between_match.group(1),
                operator="between",
                right_value=(
                    self._parse_value(between_match.group(2)),
                    self._parse_value(between_match.group(3)),
                ),
            )

        # 处理 range: 100 <= x <= 500
        range_match = re.match(r"(\S+)\s*(<=?|>=?)\s*(\S+)\s*(<=?|>=?)\s*(\S+)", formula)
        if range_match:
            return DSLFormula(
                field_name=range_match.group(3),
                operator="between",
                right_value=(
                    self._parse_value(range_match.group(1)),
                    self._parse_value(range_match.group(5)),
                ),
            )

        # 处理简单比较
        for op in [">=", "<=", "!=", "<>", "==", ">", "<", "="]:
            parts = formula.split(op, 1)
            if len(parts) == 2:
                return DSLFormula(
                    field_name=parts[0].strip(),
                    operator=self.OPERATORS.get(op, op),
                    right_value=self._parse_value(parts[1].strip()),
                )

        raise ValueError(f"无法解析公式: {formula}")

    def _split_by_connector(self, formula: str, connector: str) -> List[str]:
        pattern = f" {connector} "
        return formula.split(pattern)

    def _parse_value(self, value: str) -> Any:
        value = value.strip().strip("'\"")
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
