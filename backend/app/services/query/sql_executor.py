"""SQL 执行引擎 - 参数化 SQL 执行、连接池、超时控制"""
import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.security_error import SecurityError


class SQLExecutor:
    """SQL 执行引擎

    职责：
    - 参数化 SQL 执行
    - 连接池复用 database.py 的 engine
    - 超时控制
    - 行数限制
    - 只允许 SELECT 语句
    """

    def __init__(
        self,
        db_session_factory,
        default_limit: int = 1000,
        max_limit: int = 10000,
        timeout_seconds: float = 30.0,
    ):
        self.db_session_factory = db_session_factory
        self.default_limit = default_limit
        self.max_limit = max_limit
        self.timeout_seconds = timeout_seconds

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """执行参数化 SQL 查询

        Args:
            sql: SQL 查询语句
            params: 参数化查询参数
            limit: 结果行数限制

        Returns:
            {"columns": [...], "rows": [...], "total": N}
        """
        # 安全检查：只允许 SELECT
        self._validate_select_only(sql)

        # 行数限制
        effective_limit = min(limit or self.default_limit, self.max_limit)

        # 添加 LIMIT 子句（如果 SQL 中没有）
        if "LIMIT" not in sql.upper():
            sql = f"{sql.rstrip(';')} LIMIT {effective_limit}"

        params = params or {}

        try:
            async with self.db_session_factory() as session:
                result = await asyncio.wait_for(
                    session.execute(text(sql), params),
                    timeout=self.timeout_seconds,
                )
                columns = list(result.keys())
                rows = [dict(zip(columns, row)) for row in result.fetchall()]

            logger.info(f"SQL 执行成功: {len(rows)} 行, {len(columns)} 列")
            return {
                "columns": columns,
                "rows": rows,
                "total": len(rows),
            }

        except asyncio.TimeoutError:
            logger.error(f"SQL 执行超时: {sql[:100]}")
            raise TimeoutError(f"SQL 执行超时 ({self.timeout_seconds}s)")
        except Exception as e:
            logger.error(f"SQL 执行失败: {e}")
            raise

    def _validate_select_only(self, sql: str):
        """校验只允许 SELECT 语句"""
        stripped = sql.strip().upper()
        if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
            raise SecurityError(f"仅允许 SELECT 查询，当前语句以 {stripped[:10]} 开头")
