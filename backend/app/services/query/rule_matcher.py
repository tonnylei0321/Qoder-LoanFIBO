"""规则匹配器"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CompiledRule:
    """编译后的规则"""

    id: str
    intent_id: str
    table: str
    columns: List[str]
    conditions: List[Dict[str, Any]]
    priority: int = 0


class RuleMatcher:
    """规则匹配器"""

    def match(
        self, intent_id: str, slots: Dict[str, Any], rules: List[CompiledRule]
    ) -> Optional[CompiledRule]:
        matching = [r for r in rules if r.intent_id == intent_id]
        if not matching:
            return None
        # 返回优先级最高的规则
        return max(matching, key=lambda r: r.priority)
