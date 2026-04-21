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
        """引号感知的连接词拆分

        不会拆分引号内包含 AND/OR 的内容，
        如 name = "AND VALUE" 不会被错误拆分。
        """
        pattern = f" {connector} "
        parts = []
        current = []
        in_quote = False
        quote_char = None
        i = 0
        while i < len(formula):
            # 检查是否进入/退出引号
            if formula[i] in ('"', "'") and (
                not in_quote or formula[i] == quote_char
            ):
                if in_quote:
                    in_quote = False
                    quote_char = None
                else:
                    in_quote = True
                    quote_char = formula[i]
                current.append(formula[i])
                i += 1
                continue
            # 只在引号外检查连接词
            if not in_quote and formula[i:i + len(pattern)] == pattern:
                parts.append("".join(current))
                current = []
                i += len(pattern)
                continue
            current.append(formula[i])
            i += 1
        if current:
            parts.append("".join(current))
        return parts

    def _parse_value(self, value: str) -> Any:
        value = value.strip().strip("'\"")
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
