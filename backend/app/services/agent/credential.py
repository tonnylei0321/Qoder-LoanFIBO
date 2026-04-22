"""凭证服务 — 生成/校验/吊销 ERP Agent 的 client_id + client_secret。"""

import secrets
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.agent_credential import AgentCredential


class CredentialService:
    """管理 ERP 代理凭证的生成、验证和吊销。"""

    @staticmethod
    def _generate_client_id() -> str:
        """生成 client_id：前缀 cid_ + 32 字符随机十六进制。"""
        return f"cid_{secrets.token_hex(16)}"

    @staticmethod
    def _generate_client_secret() -> str:
        """生成 client_secret：前缀 sk_ + 32 字符随机十六进制。"""
        return f"sk_{secrets.token_hex(32)}"

    @staticmethod
    def _hash_secret(plain: str) -> str:
        """对明文 secret 做 bcrypt 哈希。"""
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_secret(plain: str, hashed: str) -> bool:
        """校验明文 secret 与 bcrypt 哈希是否匹配。"""
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

    async def generate(
        self, db: AsyncSession, org_id: str, datasource: str
    ) -> dict:
        """为一组 (org_id, datasource) 生成凭证。

        Returns:
            dict: {"client_id": "...", "client_secret": "...", "org_id": ..., "datasource": ...}
                  client_secret 明文仅此一次返回，数据库仅存哈希。
        """
        client_id = self._generate_client_id()
        client_secret = self._generate_client_secret()
        secret_hash = self._hash_secret(client_secret)

        cred = AgentCredential(
            client_id=client_id,
            client_secret_hash=secret_hash,
            org_id=org_id,
            datasource=datasource,
        )
        db.add(cred)
        await db.flush()

        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "org_id": str(org_id),
            "datasource": datasource,
        }

    async def verify(self, db: AsyncSession, client_id: str, client_secret: str) -> AgentCredential | None:
        """校验凭证。

        安全设计：
        1. 先查 client_id 是否存在，不存在则直接返回 None（不执行 bcrypt，防 CPU 消耗）
        2. 再校验 bcrypt
        3. 最后检查 revoked_at 是否为空
        """
        stmt = select(AgentCredential).where(AgentCredential.client_id == client_id)
        result = await db.execute(stmt)
        cred = result.scalar_one_or_none()

        if cred is None:
            return None

        if not self._verify_secret(client_secret, cred.client_secret_hash):
            return None

        if cred.revoked_at is not None:
            return None

        return cred

    async def revoke(self, db: AsyncSession, client_id: str) -> AgentCredential | None:
        """吊销凭证 — 设置 revoked_at 时间戳。"""
        stmt = select(AgentCredential).where(AgentCredential.client_id == client_id)
        result = await db.execute(stmt)
        cred = result.scalar_one_or_none()

        if cred is None:
            return None

        cred.revoked_at = datetime.now(timezone.utc)
        await db.flush()
        return cred

    async def get_by_org(self, db: AsyncSession, org_id: str) -> list[AgentCredential]:
        """查询某企业下所有凭证。"""
        stmt = (
            select(AgentCredential)
            .where(AgentCredential.org_id == org_id)
            .order_by(AgentCredential.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# 全局单例
credential_service = CredentialService()
