"""结果组装器 - FIBO 语义格式化、列名→FIBO概念映射、计算结果嵌入"""
from typing import Any, Dict, List, Optional

from loguru import logger


class ResultAssembler:
    """查询结果组装服务

    职责：
    - 将 SQL 查询结果转换为 FIBO 语义格式
    - 列名→FIBO 概念映射
    - 嵌入计算指标结果
    - 结果摘要生成
    """

    def __init__(self, concept_mapping: Optional[Dict[str, str]] = None):
        # 列名 → FIBO 概念标签映射
        # 例如: {"total_assets" → "总资产", "debt_ratio" → "资产负债率"}
        self.concept_mapping = concept_mapping or {}

    def assemble(
        self,
        raw_result: Dict[str, Any],
        computed_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """组装查询结果

        Args:
            raw_result: SQLExecutor 返回的原始结果
            computed_values: DSLExecutor 计算的派生指标

        Returns:
            组装后的 FIBO 语义格式结果
        """
        columns = raw_result.get("columns", [])
        rows = raw_result.get("rows", [])

        # 映射列名为 FIBO 概念标签
        semantic_columns = self._map_columns(columns)

        # 转换行数据
        semantic_rows = []
        for row in rows:
            semantic_row = {}
            for col in columns:
                label = self.concept_mapping.get(col, col)
                semantic_row[label] = row.get(col)
            semantic_rows.append(semantic_row)

        # 嵌入计算结果
        computed = computed_values or {}
        result = {
            "columns": semantic_columns,
            "rows": semantic_rows,
            "total": len(semantic_rows),
            "computed_indicators": computed,
        }

        # 生成摘要
        if semantic_rows:
            result["summary"] = self._generate_summary(semantic_rows, computed)

        return result

    def register_concept_mapping(self, column_name: str, fibo_label: str):
        """注册列名→FIBO概念映射"""
        self.concept_mapping[column_name] = fibo_label

    def update_concept_mapping(self, mapping: Dict[str, str]):
        """批量更新概念映射"""
        self.concept_mapping.update(mapping)

    # ─── 私有方法 ───────────────────────────────────────────────

    def _map_columns(self, columns: List[str]) -> List[Dict[str, str]]:
        """将列名映射为 FIBO 概念"""
        result = []
        for col in columns:
            result.append({
                "name": col,
                "label": self.concept_mapping.get(col, col),
            })
        return result

    def _generate_summary(
        self,
        rows: List[Dict[str, Any]],
        computed: Dict[str, Any],
    ) -> str:
        """生成结果摘要"""
        total = len(rows)
        parts = [f"共 {total} 条记录"]

        if computed:
            indicator_names = list(computed.keys())
            parts.append(f"计算指标: {', '.join(indicator_names)}")

        return "；".join(parts)
