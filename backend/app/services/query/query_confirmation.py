"""查询确认服务 - 低置信度查询的确认流程"""
from typing import Optional

from loguru import logger


class QueryConfirmationService:
    """查询确认服务

    当意图分类器返回低置信度结果时，需要用户确认。
    """

    # 确认阈值
    CONFIRMATION_THRESHOLD = 0.95
    REJECTION_THRESHOLD = 0.5

    def needs_confirmation(self, confidence: float) -> bool:
        """判断是否需要用户确认"""
        return confidence < self.CONFIRMATION_THRESHOLD

    def build_confirmation_message(
        self, intent_id: str, confidence: float, matched_pattern: str
    ) -> str:
        """构建确认消息"""
        return (
            f"您的查询可能匹配意图 '{intent_id}'"
            f"（匹配模式: '{matched_pattern}'，"
            f"置信度: {confidence:.1%}），请确认是否正确？"
        )

    def build_rejection_message(self, query: str) -> str:
        """构建拒绝消息"""
        return (
            f"无法理解查询 '{query}'，"
            f"请使用标准问法（如：贷款金额、逾期率等）。"
        )
