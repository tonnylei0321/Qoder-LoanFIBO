"""规则冲突检测与解决"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from collections import defaultdict

from loguru import logger


class ConflictSeverity(str, Enum):
    """冲突严重程度"""
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Conflict:
    """冲突描述"""
    conflict_type: str
    rule_ids: List[str]
    severity: ConflictSeverity
    message: str


class ConflictResolver:
    """规则冲突检测与解决器"""

    def detect(self, rules: List[Dict[str, Any]]) -> List[Conflict]:
        """检测规则间的冲突"""
        if not rules:
            return []

        conflicts = []

        # 检测重复intent_id
        intent_map: Dict[str, List[Dict]] = defaultdict(list)
        for rule in rules:
            intent_id = rule.get("intent_id", "")
            if intent_id:
                intent_map[intent_id].append(rule)

        for intent_id, rule_group in intent_map.items():
            if len(rule_group) > 1:
                conflicts.append(Conflict(
                    conflict_type="duplicate_intent",
                    rule_ids=[r.get("id", "unknown") for r in rule_group],
                    severity=ConflictSeverity.WARNING,
                    message=f"Intent '{intent_id}' has {len(rule_group)} rules"
                ))

        return conflicts

    def resolve(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解决冲突：保留高优先级规则"""
        if not rules:
            return []

        # 按intent_id分组，每组保留优先级最高的
        intent_map: Dict[str, List[Dict]] = defaultdict(list)
        no_intent: List[Dict] = []

        for rule in rules:
            intent_id = rule.get("intent_id", "")
            if intent_id:
                intent_map[intent_id].append(rule)
            else:
                no_intent.append(rule)

        resolved = []
        for intent_id, rule_group in intent_map.items():
            # 保留优先级最高的规则
            best = max(rule_group, key=lambda r: r.get("priority", 0))
            resolved.append(best)

        resolved.extend(no_intent)
        return resolved
