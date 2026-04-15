"""
端到端验证脚本：BIPV5 财务+资金域 50 张表
运行 parse_ddl_node + index_ttl_node，查询结果并打印报告。

Usage:
    python scripts/run_e2e_validation.py
"""
import asyncio
import os
import sys
from pathlib import Path

# 确保能找到 backend 包
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("DDL_DIR", "./data/ddl")
os.environ.setdefault("TTL_DIR", "./data/ttl")

from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from backend.app.services.ddl_parser import parse_ddl_node
from backend.app.services.ttl_indexer import index_ttl_node

DB_URL = "postgresql+asyncpg://loanfibo:loanfibo_secret@localhost:5434/loanfibo"


async def run():
    logger.info("=" * 60)
    logger.info("BIPV5 端到端验证：财务+资金域 50 张抽样表")
    logger.info("=" * 60)

    # Step 1: DDL 解析
    logger.info("\n[1/2] 运行 parse_ddl_node ...")
    state = {"job_id": 88888, "error": None}
    result = await parse_ddl_node(state)
    if result.get("error"):
        logger.error(f"parse_ddl_node 失败: {result['error']}")
        return
    logger.success("parse_ddl_node 完成")

    # Step 2: TTL 索引
    logger.info("\n[2/2] 运行 index_ttl_node ...")
    result2 = await index_ttl_node(result)
    if result2.get("error"):
        logger.error(f"index_ttl_node 失败: {result2['error']}")
        return
    logger.success("index_ttl_node 完成")

    # Step 3: 查询结果
    logger.info("\n[结果报告]")
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.connect() as conn:
        # table_registry 统计
        r = await conn.execute(text(
            "SELECT database_name, COUNT(*) as cnt "
            "FROM table_registry GROUP BY database_name ORDER BY cnt DESC"
        ))
        rows = r.fetchall()
        logger.info("--- table_registry（按库分组）---")
        total_tables = 0
        for db_name, cnt in rows:
            logger.info(f"  {db_name}: {cnt} 张表")
            total_tables += cnt
        logger.info(f"  合计: {total_tables} 张表")

        # 检查字段数量
        r2 = await conn.execute(text(
            "SELECT table_name, database_name, "
            "jsonb_array_length(parsed_fields::jsonb) as field_count "
            "FROM table_registry ORDER BY field_count DESC LIMIT 10"
        ))
        logger.info("\n--- 字段最多的 10 张表 ---")
        for table_name, db_name, field_count in r2.fetchall():
            logger.info(f"  {db_name}.{table_name}: {field_count} 个字段")

        # 检查 PRIMARY KEY 识别
        r3 = await conn.execute(text("""
            SELECT COUNT(*) FROM table_registry
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(parsed_fields::jsonb) AS f
                WHERE (f->>'is_primary_key')::boolean = true
            )
        """))
        pk_count = r3.scalar()
        logger.info(f"\n--- 包含主键字段的表: {pk_count}/{total_tables} ---")

        # TTL 索引统计
        r4 = await conn.execute(text("SELECT COUNT(*) FROM ontology_class_index"))
        class_cnt = r4.scalar()
        r5 = await conn.execute(text("SELECT COUNT(*) FROM ontology_property_index"))
        prop_cnt = r5.scalar()
        r6 = await conn.execute(text("SELECT COUNT(*) FROM ontology_index_meta"))
        meta_cnt = r6.scalar()
        logger.info(f"\n--- TTL 索引 ---")
        logger.info(f"  ontology_class_index:    {class_cnt} 条")
        logger.info(f"  ontology_property_index: {prop_cnt} 条")
        logger.info(f"  ontology_index_meta:     {meta_cnt} 条")

    await engine.dispose()
    logger.info("\n验证完成！")


if __name__ == "__main__":
    asyncio.run(run())
