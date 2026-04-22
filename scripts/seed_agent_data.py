#!/usr/bin/env python3
"""Agent 种子数据 — 创建测试企业 + 生成凭证 + 插入版本记录。

用法:
    python scripts/seed_agent_data.py
"""

import asyncio
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from backend.app.database import async_session_factory
from backend.app.models.fi_applicant_org import FiApplicantOrg
from backend.app.models.agent_version import AgentVersion
from backend.app.services.agent.credential import CredentialService


SEED_ORGS = [
    {"name": "中天科技", "industry": "制造业", "datasource": "NCC"},
    {"name": "华为技术", "industry": "通信", "datasource": "SAP"},
    {"name": "阿里巴巴", "industry": "互联网", "datasource": "U8"},
]

SEED_VERSIONS = [
    {"version": "1.0.0", "platform": "linux", "download_url": "https://releases.loanfibo.com/agent/1.0.0/agent-linux-amd64", "min_version": "1.0.0"},
    {"version": "1.0.0", "platform": "windows", "download_url": "https://releases.loanfibo.com/agent/1.0.0/agent-windows-amd64.exe", "min_version": "1.0.0"},
]


async def seed():
    cred_service = CredentialService()

    async with async_session_factory() as db:
        # 1. 创建测试企业 + 凭证
        for org_data in SEED_ORGS:
            # 检查是否已存在
            stmt = select(FiApplicantOrg).where(FiApplicantOrg.name == org_data["name"])
            result = await db.execute(stmt)
            org = result.scalar_one_or_none()

            if org:
                org_id = str(org.id)
                print(f"  企业已存在: {org_data['name']} ({org_id})")
            else:
                # 创建企业
                org = FiApplicantOrg(name=org_data["name"], industry=org_data["industry"])
                db.add(org)
                await db.flush()
                org_id = str(org.id)
                print(f"  创建企业: {org_data['name']} ({org_id})")

            # 生成凭证
            cred_result = await cred_service.generate(db, org_id, org_data["datasource"])
            print(f"    凭证已生成: client_id={cred_result['client_id']}")
            print(f"    client_secret={cred_result['client_secret']}")

        # 2. 插入版本记录
        for ver_data in SEED_VERSIONS:
            stmt = select(AgentVersion).where(
                AgentVersion.version == ver_data["version"],
                AgentVersion.platform == ver_data["platform"],
            )
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                print(f"  版本已存在: {ver_data['version']} ({ver_data['platform']})")
                continue

            version = AgentVersion(**ver_data)
            db.add(version)
            print(f"  版本已创建: {ver_data['version']} ({ver_data['platform']})")

        await db.commit()
        print("\n种子数据写入完成！")


if __name__ == "__main__":
    print("=== Agent 种子数据 ===\n")
    asyncio.run(seed())
