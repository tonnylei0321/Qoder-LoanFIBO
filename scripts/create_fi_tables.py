"""
创建 fi_ 前缀的信贷分析表
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import engine, Base

# 导入所有 fi_ 模型以触发元数据注册
from backend.app.models.fi_company import FiCompany
from backend.app.models.fi_dimension import FiDimension
from backend.app.models.fi_indicator import FiIndicator
from backend.app.models.fi_indicator_value import FiIndicatorValue
from backend.app.models.fi_score_record import FiScoreRecord
from backend.app.models.fi_alert_record import FiAlertRecord


async def create_tables():
    print("正在创建 fi_ 表...")
    async with engine.begin() as conn:
        # 只创建 fi_ 前缀的表，不影响现有表
        fi_tables = [
            Base.metadata.tables[t]
            for t in Base.metadata.tables
            if t.startswith("fi_")
        ]
        print(f"发现 {len(fi_tables)} 张 fi_ 表: {[t.name for t in fi_tables]}")
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=fi_tables))
    print("✅ 所有 fi_ 表创建完成！")


if __name__ == "__main__":
    asyncio.run(create_tables())
