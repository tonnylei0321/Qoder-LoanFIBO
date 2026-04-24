"""LLM 意图解析器 - 使用大模型解析自然语言查询意图"""
import json
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.app.services.query.intent_classifier import ClassificationResult


# LLM 解析用的 System Prompt
_LLM_INTENT_SYSTEM_PROMPT = """你是金融数据查询意图解析专家。
用户输入自然语言查询，你需要提取意图和槽位。

输出 JSON 格式：
{
  "intent_id": "query_xxx",
  "confidence": 0.0-1.0,
  "query_type": "aggregation|lookup|comparison|trend|unknown",
  "slots": { "entity": "...", "metric": "...", "time_range": "...", "filters": {} },
  "requires_confirmation": true/false,
  "message": "解析说明"
}

已知意图类型：
- query_company_info: 查询企业基本信息
- query_indicator: 查询指标值
- query_score: 查询评分
- query_alert: 查询预警
- query_comparison: 对比分析
- query_trend: 趋势分析
- unknown: 无法识别"""


class LLMIntentParser:
    """LLM 意图解析器

    当模板匹配器无法高置信度分类时，使用 LLM 进行深度意图解析。
    支持的 LLM 提供商：DashScope (qwen-max)。
    """

    def __init__(self, llm_client=None, model: str = "qwen-max"):
        self.llm_client = llm_client
        self.model = model

    async def parse(
        self,
        query: str,
        context: Optional[Dict] = None,
    ) -> ClassificationResult:
        """使用 LLM 解析查询意图

        Args:
            query: 用户自然语言查询
            context: 可选上下文信息（租户、场景等）

        Returns:
            ClassificationResult 解析结果
        """
        if self.llm_client is None:
            return ClassificationResult(
                intent_id="unknown",
                confidence=0.0,
                requires_confirmation=True,
                query_type="rejected",
                message="LLM 客户端未配置，无法解析",
            )

        try:
            user_prompt = f"查询: {query}"
            if context:
                user_prompt += f"\n上下文: {json.dumps(context, ensure_ascii=False)}"

            response = await self._call_llm(user_prompt)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"LLMIntentParser error: {e}")
            return ClassificationResult(
                intent_id="unknown",
                confidence=0.0,
                requires_confirmation=True,
                query_type="rejected",
                message=f"LLM 解析失败: {e}",
            )

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        if hasattr(self.llm_client, "chat"):
            # DashScope / OpenAI 兼容接口
            result = await self.llm_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": _LLM_INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return result
        raise NotImplementedError("不支持的 LLM 客户端类型")

    def _parse_response(self, response: str) -> ClassificationResult:
        """解析 LLM 返回的 JSON"""
        try:
            data = json.loads(response)
            return ClassificationResult(
                intent_id=data.get("intent_id", "unknown"),
                confidence=float(data.get("confidence", 0.5)),
                slots=data.get("slots", {}),
                requires_confirmation=data.get("requires_confirmation", True),
                query_type=data.get("query_type", "unknown"),
                message=data.get("message", ""),
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"LLM response parse error: {e}, raw: {response[:200]}")
            return ClassificationResult(
                intent_id="unknown",
                confidence=0.3,
                requires_confirmation=True,
                query_type="unknown",
                message="LLM 返回格式异常",
            )
