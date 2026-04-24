"""租户管理器 - 租户注册/查询/配置更新"""
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.tenant import Tenant
from backend.app.models.tenant_config import TenantConfig


class TenantManager:
    """租户管理服务

    职责：
    - 注册租户（创建 Tenant + 默认 TenantConfig）
    - 查询租户列表
    - 获取/更新租户配置
    - 租户状态管理
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_tenant(
        self,
        tenant_id: str,
        name: str,
        industry: str,
        tier: str = "tier2",
    ) -> Tenant:
        """注册新租户

        Args:
            tenant_id: 租户唯一标识
            name: 租户名称
            industry: 行业
            tier: 租户层级 (tier1/tier2/tier3)

        Raises:
            ValueError: 租户已存在
        """
        # 检查是否已存在
        existing = await self.db.get(Tenant, tenant_id)
        if existing is not None:
            raise ValueError(f"租户 {tenant_id} 已存在")

        # 创建租户
        tenant = Tenant(
            id=tenant_id,
            name=name,
            industry=industry,
            tier=tier,
            status="active",
        )
        self.db.add(tenant)

        # 创建默认配置
        config = TenantConfig(
            tenant_id=tenant_id,
            db_schema="public",
            compile_priority=5,
            max_rules=100,
            nlq_enabled=True,
            custom_settings=None,
        )
        self.db.add(config)

        await self.db.flush()
        logger.info(f"Tenant registered: {tenant_id} ({name})")
        return tenant

    async def list_tenants(
        self,
        status_filter: Optional[str] = None,
    ) -> List[Tenant]:
        """列出所有租户"""
        stmt = select(Tenant).order_by(Tenant.created_at.desc())
        if status_filter:
            stmt = stmt.where(Tenant.status == status_filter)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取租户详情"""
        return await self.db.get(Tenant, tenant_id)

    async def get_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """获取租户配置"""
        return await self.db.get(TenantConfig, tenant_id)

    async def update_tenant_config(
        self,
        tenant_id: str,
        db_schema: Optional[str] = None,
        compile_priority: Optional[int] = None,
        max_rules: Optional[int] = None,
        nlq_enabled: Optional[bool] = None,
        custom_settings: Optional[str] = None,
    ) -> TenantConfig:
        """更新租户配置

        Raises:
            ValueError: 租户或配置不存在
        """
        config = await self.db.get(TenantConfig, tenant_id)
        if config is None:
            raise ValueError(f"租户 {tenant_id} 的配置不存在")

        if db_schema is not None:
            config.db_schema = db_schema
        if compile_priority is not None:
            config.compile_priority = compile_priority
        if max_rules is not None:
            config.max_rules = max_rules
        if nlq_enabled is not None:
            config.nlq_enabled = nlq_enabled
        if custom_settings is not None:
            config.custom_settings = custom_settings

        await self.db.flush()
        return config

    async def deactivate_tenant(self, tenant_id: str) -> Tenant:
        """停用租户"""
        tenant = await self.db.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError(f"租户 {tenant_id} 不存在")
        tenant.status = "inactive"
        await self.db.flush()
        return tenant
