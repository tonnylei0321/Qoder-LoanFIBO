#!/usr/bin/env python3
"""Standalone script to run the FIBO 2025Q4 indexer.

Usage:
    cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO
    python scripts/run_fibo_indexer.py [--clear]
"""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root))

from backend.app.services.fibo_indexer import run_fibo_indexer
from loguru import logger


async def main():
    clear = "--clear" in sys.argv
    fibo_root = project_root / "docs" / "fibo-master_2025Q4"

    logger.info(f"FIBO root: {fibo_root}")
    logger.info(f"Clear existing: {clear}")

    await run_fibo_indexer(fibo_root=fibo_root, clear_existing=clear)

    # Print summary
    import os
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://loanfibo:loanfibo_secret@localhost:5434/loanfibo")

    from backend.app.database import async_session_factory
    from sqlalchemy import text
    async with async_session_factory() as db:
        r = await db.execute(text(
            "SELECT "
            "(SELECT COUNT(*) FROM ontology_class_index WHERE is_deleted=false) AS classes, "
            "(SELECT COUNT(*) FROM ontology_property_index WHERE is_deleted=false) AS props, "
            "(SELECT COUNT(*) FROM ontology_relation_index WHERE is_deleted=false) AS rels"
        ))
        row = r.fetchone()
        logger.info(f"Index summary: classes={row.classes}, props={row.props}, rels={row.rels}")


if __name__ == "__main__":
    asyncio.run(main())
