"""意图分类器 - 模板匹配模式（首期实现）"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ClassificationResult:
    """分类结果"""

    intent_id: str
    confidence: float
    slots: Dict[str, Any] = field(default_factory=dict)
    matched_pattern: Optional[str] = None
    requires_confirmation: bool = False
    query_type: str = "unknown"
    message: str = ""


class IntentClassifier:
    """意图分类器 - 模板匹配（首期）+ BERT/LLM（后续迭代）"""

    def __init__(self, templates: List[Dict], llm_client=None):
        self.templates = templates
        self.llm_client = llm_client

    async def classify(
        self, query: str, context: Optional[Dict] = None
    ) -> ClassificationResult:
        # 1. 模板匹配（快速路径）
        template_match = self._match_template(query)
        if template_match and template_match.confidence > 0.95:
            return template_match

        # 2. 模糊匹配
        if template_match and template_match.confidence > 0.5:
            template_match.requires_confirmation = True
            return template_match

        # 3. 未匹配
        return ClassificationResult(
            intent_id="unknown",
            confidence=0.0,
            requires_confirmation=True,
            query_type="rejected",
            message="无法理解的查询，请使用标准问法",
        )

    def _match_template(self, query: str) -> Optional[ClassificationResult]:
        best_match = None
        best_confidence = 0.0

        for template in self.templates:
            for pattern in template.get("patterns", []):
                confidence = self._calculate_similarity(query, pattern)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = ClassificationResult(
                        intent_id=template["intent_id"],
                        confidence=confidence,
                        slots={s: None for s in template.get("slots", [])},
                        matched_pattern=pattern,
                        query_type="predefined" if confidence > 0.95 else "fuzzy",
                    )
        return best_match

    def _calculate_similarity(self, query: str, pattern: str) -> float:
        if query == pattern:
            return 1.0
        if pattern.lower() in query.lower():
            return 0.95
        if query.lower() in pattern.lower():
            return 0.85
        # 简单的字符重叠度
        query_chars = set(query.lower())
        pattern_chars = set(pattern.lower())
        if not pattern_chars:
            return 0.0
        overlap = len(query_chars & pattern_chars) / len(pattern_chars)
        return overlap * 0.7
