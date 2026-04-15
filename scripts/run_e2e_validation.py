"""
端到端验证脚本：BIPV5 财务+资金域 50 张表
Phase 1: parse_ddl_node + index_ttl_node
Phase 2: fetch_batch_node + retrieve_candidates_node
Phase 3: 可选 — 输入 'y' 启动真实 LLM 映射（耗 token）

Usage:
    python scripts/run_e2e_validation.py            # Phase 1+2
    python scripts/run_e2e_validation.py --llm      # Phase 1+2+3
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("DDL_DIR", "./data/ddl")
os.environ.setdefault("TTL_DIR", "./data/ttl")

from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from backend.app.services.ddl_parser import parse_ddl_node
from backend.app.services.ttl_indexer import index_ttl_node
from backend.app.services.pipeline_orchestrator import fetch_batch_node
from backend.app.services.candidate_retriever import retrieve_candidates_node, search_candidates

DB_URL = "postgresql+asyncpg://loanfibo:loanfibo_secret@localhost:5434/loanfibo"
RUN_LLM = "--llm" in sys.argv


async def run():
    logger.info("=" * 60)
    logger.info("BIPV5 端到端验证：财务+资金域 50 张节样表")
    logger.info(f"LLM 映射阶段: {'\u5f00启' if RUN_LLM else '跳过（传入 --llm 开启）'}")
    logger.info("=" * 60)

    state = {"job_id": 88888, "error": None, "current_batch": [], "revision_round": 0, "phase": "parse_ddl"}

    # ------- Phase 1a: DDL 解析 -------
    logger.info("\n[1/4] parse_ddl_node ...")
    state = await parse_ddl_node(state)
    if state.get("error"):
        logger.error(f"parse_ddl_node 失败: {state['error']}"); return
    logger.success("parse_ddl_node 完成")

    # ------- Phase 1b: TTL 索引 -------
    logger.info("\n[2/4] index_ttl_node ...")
    state = await index_ttl_node(state)
    if state.get("error"):
        logger.error(f"index_ttl_node 失败: {state['error']}"); return
    logger.success("index_ttl_node 完成")

    # ------- Phase 2a: fetch_batch -------
    logger.info("\n[3/4] fetch_batch_node ...")
    state = await fetch_batch_node(state)
    batch = state.get("current_batch", [])
    logger.info(f"  载入第一批: {len(batch)} 张表 (IDs: {batch[:5]}{'...' if len(batch)>5 else ''})")

    # ------- Phase 2b: retrieve_candidates -------
    logger.info("\n[4/4] retrieve_candidates_node ...")
    state = await retrieve_candidates_node(state)
    logger.success("retrieve_candidates_node 完成")

    # ------- 内联搜索验证：抽取样本表的关键词并搜索 -------
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.connect() as conn:
        # 取第一张表做搜索验证
        if batch:
            row = (await conn.execute(
                text("SELECT table_name, database_name FROM table_registry WHERE id = :id"),
                {"id": batch[0]}
            )).fetchone()
            if row:
                keywords = row[0].replace('_', ' ')
                candidates = await search_candidates(keywords, limit=5)
                logger.info(f"\n--- 候选检索验证 (table='{row[0]}', keywords='{keywords}') ---")
                if candidates:
                    for c in candidates:
                        logger.info(f"  {c['label_zh']} ({c['class_uri']})")
                else:
                    logger.warning("  未找到候选（TTL 本体内容范围有限，属正常现象）")

        # 结果汇总
        r = await conn.execute(text(
            "SELECT database_name, COUNT(*) as cnt "
            "FROM table_registry GROUP BY database_name ORDER BY cnt DESC"
        ))
        logger.info("\n--- table_registry（按库分组）---")
        total = 0
        for db_name, cnt in r.fetchall():
            logger.info(f"  {db_name}: {cnt} 张表")
            total += cnt
        logger.info(f"  合计: {total} 张表")

        r2 = await conn.execute(text("SELECT COUNT(*) FROM ontology_class_index"))
        logger.info(f"\n--- ontology_class_index: {r2.scalar()} 条 ---")

        r3 = await conn.execute(text(
            "SELECT COUNT(*) FROM table_registry WHERE mapping_status = 'pending'"
        ))
        logger.info(f"--- pending 待映射表数: {r3.scalar()} ---")

    await engine.dispose()

    # ------- Phase 3: LLM 映射（可选） -------
    if RUN_LLM:
        logger.info("\n[LLM] 尝试对第一批表运行 LLM 映射...")
        from backend.app.services.mapping_llm import mapping_llm_node
        state = await mapping_llm_node(state)
        logger.success("LLM 映射完成")
    else:
        logger.info("\n跳过 LLM 映射阶段（传入 --llm 可开启）")

    logger.info("\n验证完成！")


if __name__ == "__main__":
    asyncio.run(run())
