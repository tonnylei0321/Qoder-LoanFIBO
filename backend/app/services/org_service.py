"""融资企业 & 授权项 — CRUD Service + GraphDB 同步"""

import logging
import secrets
import uuid
from typing import List, Optional

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.fi_applicant_org import FiApplicantOrg
from backend.app.models.fi_authorization_scope import FiAuthorizationScope
from backend.app.models.graphdb_instance import GraphDBInstance
from backend.app.schemas.org import (
    ApplicantOrgCreate, ApplicantOrgUpdate,
    AuthorizationScopeCreate, AuthorizationScopeUpdate,
)

logger = logging.getLogger(__name__)

YQL = "http://yql.example.com/ontology/credit-risk/"
ORG_NS = "http://yql.example.com/ontology/applicant-org/"
AUTH_NS = "http://yql.example.com/ontology/auth-scope/"
INST_NS = "http://yql.example.com/ontology/erp-instance/"

# 默认 NCC 实例 URI，融资企业新增时自动关联
DEFAULT_NCC_INSTANCE_URI = f"{INST_NS}NCC_Instance"


class OrgService:
    """融资企业与授权项的 CRUD 服务，写 PG 后同步到 GraphDB。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── 融资企业 CRUD ────────────────────────────────────

    async def list_orgs(self, active_only: bool = False) -> List[FiApplicantOrg]:
        stmt = select(FiApplicantOrg).order_by(FiApplicantOrg.name)
        if active_only:
            stmt = stmt.where(FiApplicantOrg.is_active == True)  # noqa: E712
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_org(self, org_id: uuid.UUID) -> Optional[FiApplicantOrg]:
        result = await self.db.execute(select(FiApplicantOrg).where(FiApplicantOrg.id == org_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _generate_security_id() -> str:
        """生成安全ID：前缀 sid_ + 32字符随机hex。"""
        return f"sid_{secrets.token_hex(16)}"

    @staticmethod
    def mask_security_id(sid: str) -> str:
        """掩码展示安全ID：保留前8位+后4位，中间用****替换。

        例：sid_a1b2c3d4e5f6g7h8 -> sid_a1b2****g7h8
        """
        if not sid or len(sid) <= 12:
            return sid or ''
        return sid[:8] + '****' + sid[-4:]

    async def create_org(self, data: ApplicantOrgCreate) -> FiApplicantOrg:
        org = FiApplicantOrg(**data.model_dump())
        # 自动生成安全ID
        org.security_id = self._generate_security_id()
        self.db.add(org)
        await self.db.flush()

        # 构建 GraphDB URI
        code_part = org.unified_code or str(org.id)[:8]
        graph_uri = f"{ORG_NS}Org_{code_part}"
        org.graph_uri = graph_uri
        await self.db.flush()

        # 同步到 GraphDB
        try:
            await self._sync_org_to_graphdb(org)
        except Exception as e:
            logger.warning(f"GraphDB sync failed for org {org.id}: {e}")

        return org

    async def update_org(self, org_id: uuid.UUID, data: ApplicantOrgUpdate) -> Optional[FiApplicantOrg]:
        org = await self.get_org(org_id)
        if not org:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(org, k, v)
        await self.db.flush()

        # 同步到 GraphDB
        try:
            await self._sync_org_to_graphdb(org, is_update=True)
        except Exception as e:
            logger.warning(f"GraphDB sync failed for org {org.id}: {e}")

        return org

    async def delete_org(self, org_id: uuid.UUID) -> bool:
        org = await self.get_org(org_id)
        if not org:
            return False
        org.is_active = False
        await self.db.flush()

        # 从 GraphDB 删除
        if org.graph_uri:
            try:
                await self._delete_from_graphdb(org.graph_uri)
            except Exception as e:
                logger.warning(f"GraphDB delete failed for org {org.id}: {e}")
        return True

    async def regenerate_security_id(self, org_id: uuid.UUID) -> Optional[FiApplicantOrg]:
        """重新生成安全ID。"""
        org = await self.get_org(org_id)
        if not org:
            return None
        org.security_id = self._generate_security_id()
        await self.db.flush()
        return org

    # ─── 授权项 CRUD ──────────────────────────────────────

    async def list_auth_scopes(self, active_only: bool = False) -> List[FiAuthorizationScope]:
        stmt = select(FiAuthorizationScope).order_by(FiAuthorizationScope.code)
        if active_only:
            stmt = stmt.where(FiAuthorizationScope.is_active == True)  # noqa: E712
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_auth_scope(self, scope_id: uuid.UUID) -> Optional[FiAuthorizationScope]:
        result = await self.db.execute(
            select(FiAuthorizationScope).where(FiAuthorizationScope.id == scope_id)
        )
        return result.scalar_one_or_none()

    async def create_auth_scope(self, data: AuthorizationScopeCreate) -> FiAuthorizationScope:
        scope = FiAuthorizationScope(**data.model_dump())
        self.db.add(scope)
        await self.db.flush()

        # 构建 GraphDB URI
        graph_uri = f"{AUTH_NS}AuthScope_{scope.code}"
        scope.graph_uri = graph_uri
        await self.db.flush()

        # 同步到 GraphDB
        try:
            await self._sync_auth_scope_to_graphdb(scope)
        except Exception as e:
            logger.warning(f"GraphDB sync failed for auth scope {scope.id}: {e}")

        return scope

    async def update_auth_scope(self, scope_id: uuid.UUID, data: AuthorizationScopeUpdate) -> Optional[FiAuthorizationScope]:
        scope = await self.get_auth_scope(scope_id)
        if not scope:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(scope, k, v)
        await self.db.flush()

        try:
            await self._sync_auth_scope_to_graphdb(scope, is_update=True)
        except Exception as e:
            logger.warning(f"GraphDB sync failed for auth scope {scope.id}: {e}")

        return scope

    async def delete_auth_scope(self, scope_id: uuid.UUID) -> bool:
        scope = await self.get_auth_scope(scope_id)
        if not scope:
            return False
        scope.is_active = False
        await self.db.flush()

        if scope.graph_uri:
            try:
                await self._delete_from_graphdb(scope.graph_uri)
            except Exception as e:
                logger.warning(f"GraphDB delete failed for auth scope {scope.id}: {e}")
        return True

    # ─── GraphDB 同步 ─────────────────────────────────────

    async def _get_active_instance(self) -> Optional[GraphDBInstance]:
        """获取当前活跃的 GraphDB 实例"""
        result = await self.db.execute(
            select(GraphDBInstance).where(GraphDBInstance.is_active == True).limit(1)  # noqa: E712
        )
        return result.scalar_one_or_none()

    async def _sparql_update(self, sparql: str) -> None:
        """执行 SPARQL UPDATE"""
        instance = await self._get_active_instance()
        if not instance:
            logger.warning("No active GraphDB instance, skip sync")
            return
        import httpx
        url = f"{instance.server_url.rstrip('/')}/repositories/{instance.repo_id}/statements"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                content=sparql,
                headers={"Content-Type": "application/sparql-update"},
            )
            resp.raise_for_status()

    def _escape_sparql(self, text: str) -> str:
        """SPARQL 字面量安全转义"""
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")

    async def _sync_org_to_graphdb(self, org: FiApplicantOrg, is_update: bool = False) -> None:
        """将融资企业同步到 GraphDB，包括 linkedToInstance 关联。"""
        uri = org.graph_uri
        if not uri:
            return
        name = self._escape_sparql(org.name)
        short = self._escape_sparql(org.short_name) if org.short_name else ""

        if is_update:
            # 先删旧三元组再插新的（保留 linkedToInstance 不删，因为可能手动调整过）
            delete_sparql = f"""
            PREFIX yql: <{YQL}>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            DELETE WHERE {{
                <{uri}> ?p ?o .
                FILTER(?p IN (rdfs:label, yql:shortName, yql:unifiedCode, yql:industry, yql:region))
            }}"""
            await self._sparql_update(delete_sparql)

        # 检查是否已存在 linkedToInstance，避免重复关联
        existing_instance = await self._query_org_linked_instance(uri)

        insert_parts = [
            f'<{uri}> a yql:ApplicantOrg ;',
            f'        rdfs:label "{name}" .',
        ]
        if short:
            insert_parts.append(f'<{uri}> yql:shortName "{short}" .')
        if org.unified_code:
            insert_parts.append(f'<{uri}> yql:unifiedCode "{self._escape_sparql(org.unified_code)}" .')
        if org.industry:
            insert_parts.append(f'<{uri}> yql:industry "{self._escape_sparql(org.industry)}" .')
        if org.region:
            insert_parts.append(f'<{uri}> yql:region "{self._escape_sparql(org.region)}" .')

        # 如果尚未关联 ERPInstance，自动关联默认 NCC 实例
        if not existing_instance:
            insert_parts.append(
                f'<{uri}> yql:linkedToInstance <{DEFAULT_NCC_INSTANCE_URI}> .'
            )
            logger.info(f"企业 {name} 自动关联 NCC 实例: {DEFAULT_NCC_INSTANCE_URI}")

        insert_body = "\n            ".join(insert_parts)
        insert_sparql = f"""
        PREFIX yql: <{YQL}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
            {insert_body}
        }}"""
        await self._sparql_update(insert_sparql)

    async def _query_org_linked_instance(self, org_uri: str) -> str | None:
        """查询企业已关联的 ERPInstance URI。"""
        instance = await self._get_active_instance()
        if not instance:
            return None
        sparql = f"""
        PREFIX yql: <{YQL}>
        SELECT ?instance WHERE {{
            <{org_uri}> yql:linkedToInstance ?instance .
        }} LIMIT 1
        """
        import httpx
        url = f"{instance.server_url.rstrip('/')}/repositories/{instance.repo_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                data={"query": sparql},
                headers={"Accept": "application/sparql-results+json"},
            )
            if resp.status_code == 200:
                bindings = resp.json().get("results", {}).get("bindings", [])
                if bindings:
                    return bindings[0]["instance"]["value"]
        return None

    async def _sync_auth_scope_to_graphdb(self, scope: FiAuthorizationScope, is_update: bool = False) -> None:
        """将授权项同步到 GraphDB"""
        uri = scope.graph_uri
        if not uri:
            return
        label = self._escape_sparql(scope.label)
        code = self._escape_sparql(scope.code)

        if is_update:
            delete_sparql = f"""
            PREFIX yql: <{YQL}>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            DELETE WHERE {{
                <{uri}> ?p ?o .
                FILTER(?p IN (rdfs:label, yql:authCode, yql:authCategory, yql:authDescription))
            }}"""
            await self._sparql_update(delete_sparql)

        insert_sparql = f"""
        PREFIX yql: <{YQL}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
            <{uri}> a yql:AuthorizationScope ;
                    rdfs:label "{label}" ;
                    yql:authCode "{code}" .
            {"<" + uri + "> yql:authCategory \"" + self._escape_sparql(scope.category) + "\" ." if scope.category else ""}
            {"<" + uri + "> yql:authDescription \"" + self._escape_sparql(scope.description) + "\" ." if scope.description else ""}
        }}"""
        await self._sparql_update(insert_sparql)

    async def _delete_from_graphdb(self, uri: str) -> None:
        """从 GraphDB 删除实体的所有三元组"""
        sparql = f"""
        DELETE WHERE {{
            <{uri}> ?p ?o .
        }}
        DELETE WHERE {{
            ?s ?p <{uri}> .
        }}"""
        await self._sparql_update(sparql)

    # ─── 初始化种子数据 ───────────────────────────────────

    async def seed_default_auth_scopes(self) -> int:
        """从 v8 TTL 中的 8 个标准授权项初始化到 PG"""
        DEFAULT_SCOPES = [
            {"code": "ERP_AR", "label": "授权-ERP应收账款数据", "category": "ERP"},
            {"code": "ERP_AP", "label": "授权-ERP应付账款数据", "category": "ERP"},
            {"code": "ERP_INVENTORY", "label": "授权-ERP存货数据", "category": "ERP"},
            {"code": "ERP_GL", "label": "授权-ERP总账数据", "category": "ERP"},
            {"code": "FINANCIAL_STMT", "label": "授权-财务报表", "category": "财务"},
            {"code": "CREDIT_REPORT", "label": "授权-央行征信报告", "category": "征信"},
            {"code": "TAX_DATA", "label": "授权-税务数据", "category": "税务"},
            {"code": "BANK_FLOW", "label": "授权-银行流水", "category": "银行"},
        ]
        count = 0
        for item in DEFAULT_SCOPES:
            existing = await self.db.execute(
                select(FiAuthorizationScope).where(FiAuthorizationScope.code == item["code"])
            )
            if existing.scalar_one_or_none():
                continue
            scope = FiAuthorizationScope(
                code=item["code"],
                label=item["label"],
                category=item["category"],
                graph_uri=f"{AUTH_NS}AuthScope_{item['code']}",
            )
            self.db.add(scope)
            count += 1
        await self.db.flush()
        return count
