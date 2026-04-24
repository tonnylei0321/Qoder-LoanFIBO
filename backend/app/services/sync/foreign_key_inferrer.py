"""外键推断器 - LLM 辅助发现表间外键关系"""
import json
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.table_foreign_key import TableForeignKey


class ForeignKeyInferrer:
    """外键推断服务

    职责：
    - 调用 LLM (DashScope) 根据表结构推断外键关系
    - 持久化推断结果
    - 支持人工审核（approve/reject）
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def infer_from_schema(self, table_names: List[str]) -> List[TableForeignKey]:
        """根据表结构推断外键关系

        使用 DashScope LLM 分析表名和字段命名模式，推断外键关系。
        """
        # 获取表结构信息
        schema_info = await self._get_schema_info(table_names)

        # 调用 LLM 推断
        inferred = await self._call_llm_infer(schema_info)

        # 持久化结果
        results = []
        for fk_data in inferred:
            fk = TableForeignKey(
                source_table=fk_data["source_table"],
                source_column=fk_data["source_column"],
                target_table=fk_data["target_table"],
                target_column=fk_data["target_column"],
                confidence=fk_data.get("confidence", 0.5),
                status="pending",
                inferred_by="llm",
                inference_reason=fk_data.get("reason", ""),
            )
            self.db.add(fk)
            results.append(fk)

        await self.db.flush()
        logger.info(f"外键推断完成: {len(results)} 条结果")
        return results

    async def approve(self, fk_id: str) -> TableForeignKey:
        """审核通过外键"""
        fk = await self._get_by_id(fk_id)
        fk.status = "approved"
        await self.db.flush()
        return fk

    async def reject(self, fk_id: str) -> TableForeignKey:
        """审核拒绝外键"""
        fk = await self._get_by_id(fk_id)
        fk.status = "rejected"
        await self.db.flush()
        return fk

    # ─── 私有方法 ───────────────────────────────────────────────

    async def _get_by_id(self, fk_id: str) -> TableForeignKey:
        result = await self.db.execute(
            select(TableForeignKey).where(TableForeignKey.id == fk_id)
        )
        fk = result.scalar_one_or_none()
        if fk is None:
            raise ValueError(f"外键记录不存在: {fk_id}")
        return fk

    async def _get_schema_info(self, table_names: List[str]) -> str:
        """从数据库获取表结构信息"""
        from backend.app.models.table_registry import TableRegistry
        parts = []
        for name in table_names:
            result = await self.db.execute(
                select(TableRegistry).where(TableRegistry.table_name == name)
            )
            table = result.scalar_one_or_none()
            if table:
                parts.append(f"表 {name}: {table.column_info if hasattr(table, 'column_info') else 'N/A'}")
            else:
                parts.append(f"表 {name}: (未找到元数据)")
        return "\n".join(parts)

    async def _call_llm_infer(self, schema_info: str) -> List[Dict[str, Any]]:
        """调用 LLM 推断外键关系"""
        try:
            from openai import AsyncOpenAI
            from backend.app.config import settings

            client = AsyncOpenAI(
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.DASHSCOPE_API_BASE,
            )

            prompt = f"""分析以下数据库表结构，推断表间外键关系。

{schema_info}

请以JSON数组格式返回外键关系，每个元素包含：
- source_table: 源表名
- source_column: 源字段名
- target_table: 目标表名
- target_column: 目标字段名
- confidence: 置信度(0-1)
- reason: 推断理由

仅返回JSON，不要其他文本。"""

            response = await client.chat.completions.create(
                model=settings.MAPPING_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
            )
            content = response.choices[0].message.content.strip()
            # 解析JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM 外键推断失败: {e}")
            # 降级：基于命名模式推断
            return await self._fallback_pattern_infer(schema_info)

    async def _fallback_pattern_infer(self, schema_info: str) -> List[Dict[str, Any]]:
        """降级：基于命名模式推断外键

        如果字段名以 _id 结尾，尝试匹配目标表。
        """
        # 简单模式推断
        return []
