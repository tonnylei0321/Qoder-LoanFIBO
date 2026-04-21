"""SQL生成器 - 白名单+参数化查询"""
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from backend.app.services.query.semantic_mapping import SemanticMapping, TableMapping


class SecurityError(Exception):
    """SQL安全异常"""
    pass


class SQLGenerator:
    """SQL生成器（安全优先）"""

    def __init__(self, mapping: SemanticMapping):
        self.mapping = mapping

    def generate_safe(
        self,
        table_name: str,
        select_columns: List[str],
        conditions: Dict[str, Any],
        order_by: Optional[str] = None,
        limit: int = 100,
    ) -> Tuple[str, List[Any]]:
        table_mapping = self.mapping.table_mappings.get(table_name)
        if not table_mapping:
            raise SecurityError(f"未定义的表: {table_name}")

        quoted_cols = []
        for col in select_columns:
            if not self.mapping.is_column_allowed(table_name, col):
                raise SecurityError(f"未授权的列: {col}")
            quoted_cols.append(self._quote_identifier(col))

        where_clause, params = self._build_parametrized_conditions(
            conditions, table_mapping
        )

        sql = f"SELECT {', '.join(quoted_cols)} FROM {self._quote_identifier(table_name)}"
        if where_clause:
            sql += f" WHERE {' AND '.join(where_clause)}"
        if order_by:
            sql += f" ORDER BY {self._quote_identifier(order_by)}"
        sql += f" LIMIT {limit}"

        self._validate_sql_safety(sql)
        return sql, params

    def _build_parametrized_conditions(
        self, slots: Dict[str, Any], table_mapping: TableMapping
    ) -> Tuple[List[str], List[Any]]:
        conditions = []
        params = []

        for slot_name, slot_value in slots.items():
            column_name = self._resolve_slot_to_column(slot_name, table_mapping)
            if not column_name:
                raise SecurityError(f"未定义的槽位名: {slot_name}")

            quoted_column = self._quote_identifier(column_name)
            conditions.append(f"{quoted_column} = %s")
            params.append(slot_value)

        return conditions, params

    def _resolve_slot_to_column(
        self, slot_name: str, table_mapping: TableMapping
    ) -> Optional[str]:
        full_key = f"{table_mapping.concept}.{slot_name}"
        column_path = self.mapping.concept_to_table.get(full_key)
        if column_path:
            parts = column_path.split(".")
            if len(parts) == 2:
                _, column = parts
                if self.mapping.is_column_allowed(table_mapping.table_name, column):
                    return column
        return None

    def _quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def _validate_sql_safety(self, sql: str):
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP',
            'TRUNCATE', 'ALTER', 'CREATE', 'GRANT',
            'EXECUTE', 'EXEC', 'XP_', 'LOAD_'
        ]
        upper_sql = sql.upper()
        for keyword in dangerous_keywords:
            if keyword in upper_sql:
                raise SecurityError(f"SQL包含危险操作: {keyword}")

        stripped = sql.strip().rstrip(';')
        if ';' in stripped:
            raise SecurityError("SQL包含非法分号")

        if '--' in sql or '/*' in sql:
            raise SecurityError("SQL包含非法注释")
