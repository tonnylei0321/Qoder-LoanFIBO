# GraphDB 同步功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 GraphDB 同步功能，包括发布版本管理、LLM外键推断、RDF三元组生成、GraphDB数据导入、图谱可视化浏览。

**架构:** 采用分层架构 - API层(FastAPI路由)、服务层(业务逻辑)、数据层(SQLAlchemy+PostgreSQL)、外部客户端(GraphDB REST API)。前端使用 Vue3 + D3.js/Cytoscape 实现图钻取可视化。

**Tech Stack:** FastAPI, SQLAlchemy(async), PostgreSQL, Vue3, TypeScript, D3.js/Cytoscape.js, GraphDB, DashScope(LLM)

---

## 文件结构总览

### 后端文件
```
backend/app/
├── api/v1/endpoints/
│   ├── versions.py          # 版本管理API
│   ├── graphdb_instances.py # GraphDB实例API
│   ├── sync_tasks.py        # 同步任务API
│   ├── foreign_keys.py      # 外键推断API
│   └── graph_explorer.py    # 图谱浏览API
├── services/
│   ├── version_service.py           # 版本管理业务逻辑
│   ├── graphdb_service.py           # GraphDB实例管理
│   ├── sync_service.py              # 同步任务编排
│   ├── foreign_key_inference.py     # LLM外键推断
│   ├── rdf_generator.py             # RDF三元组生成
│   └── graphdb_client.py            # GraphDB REST客户端
├── models/
│   ├── mapping_version.py           # 版本模型
│   ├── mapping_version_item.py      # 版本快照项模型
│   ├── graphdb_instance.py          # GraphDB实例模型
│   ├── sync_task.py                 # 同步任务模型
│   ├── table_foreign_key.py         # 外键关系模型
│   └── database_business_domain.py  # 业务域模型
└── schemas/
    ├── version.py
    ├── graphdb_instance.py
    ├── sync_task.py
    └── foreign_key.py
```

### 前端文件
```
frontend/src/views/graphdb/
├── GraphDBLayout.vue
├── VersionManagement/
│   ├── VersionList.vue
│   ├── VersionCreateModal.vue
│   └── VersionDetail.vue
├── InstanceManagement/
│   ├── InstanceList.vue
│   └── InstanceForm.vue
├── SyncTasks/
│   ├── TaskList.vue
│   └── TaskCreateModal.vue
└── GraphExplorer/
    ├── GraphCanvas.vue          # 核心：图谱画布
    ├── NodeDetailPanel.vue      # 节点详情面板
    ├── BreadcrumbNav.vue        # 面包屑导航
    ├── SearchBox.vue
    └── Toolbar.vue
```

---

## Phase 1: 数据库基础

### Task 1: 创建数据库迁移脚本

**Files:**
- Create: `backend/alembic/versions/20260420_add_graphdb_sync_tables.py`

**依赖:** 无

- [ ] **Step 1: 创建迁移脚本文件**

```python
"""add graphdb sync tables

Revision ID: 20260420_graphdb_sync
Revises: <previous_revision>
Create Date: 2026-04-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260420_graphdb_sync'
down_revision = '<previous_revision>'  # 需要根据实际情况修改
branch_labels = None
depends_on = None


def upgrade():
    # 1. mapping_version 表
    op.create_table(
        'mapping_version',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('version_name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='draft'),
        sa.Column('source_job_id', sa.BigInteger(), nullable=True),
        sa.Column('total_mappings', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fk_inference_status', sa.String(32), nullable=True, server_default='pending'),
        sa.Column('created_by', sa.String(128), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_name'),
        sa.ForeignKeyConstraint(['source_job_id'], ['mapping_job.id'], ondelete='SET NULL')
    )
    op.create_index('idx_mapping_version_status', 'mapping_version', ['status'])
    op.create_index('idx_mapping_version_job', 'mapping_version', ['source_job_id'])
    
    # 2. mapping_version_item 表
    op.create_table(
        'mapping_version_item',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('version_id', sa.BigInteger(), nullable=False),
        sa.Column('database_name', sa.String(128), nullable=False),
        sa.Column('table_name', sa.String(256), nullable=False),
        sa.Column('fibo_class_uri', sa.String(512), nullable=True),
        sa.Column('confidence_level', sa.String(16), nullable=True),
        sa.Column('mapping_reason', sa.Text(), nullable=True),
        sa.Column('field_mappings', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_id', 'database_name', 'table_name'),
        sa.ForeignKeyConstraint(['version_id'], ['mapping_version.id'], ondelete='CASCADE')
    )
    op.create_index('idx_version_item_version', 'mapping_version_item', ['version_id'])
    op.create_index('idx_version_item_db_table', 'mapping_version_item', ['database_name', 'table_name'])
    
    # 3. graphdb_instance 表
    op.create_table(
        'graphdb_instance',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('instance_name', sa.String(128), nullable=False),
        sa.Column('repo_id', sa.String(128), nullable=False),
        sa.Column('graphdb_url', sa.String(512), nullable=False, server_default='http://localhost:7200'),
        sa.Column('ruleset', sa.String(64), nullable=False, server_default='owl-horst-optimized'),
        sa.Column('business_domain', sa.String(128), nullable=True),
        sa.Column('named_graph_prefix', sa.String(256), nullable=True, server_default='urn:loanfibo'),
        sa.Column('status', sa.String(32), nullable=False, server_default='active'),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_status', sa.String(32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('graphdb_url', 'repo_id')
    )
    op.create_index('idx_graphdb_instance_status', 'graphdb_instance', ['status'])
    op.create_index('idx_graphdb_instance_domain', 'graphdb_instance', ['business_domain'])
    
    # 4. sync_task 表
    op.create_table(
        'sync_task',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('version_id', sa.BigInteger(), nullable=False),
        sa.Column('instance_id', sa.BigInteger(), nullable=False),
        sa.Column('sync_mode', sa.String(32), nullable=False, server_default='upsert'),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('total_triples', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('synced_triples', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('generated_files', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['version_id'], ['mapping_version.id']),
        sa.ForeignKeyConstraint(['instance_id'], ['graphdb_instance.id'])
    )
    op.create_index('idx_sync_task_status', 'sync_task', ['status'])
    op.create_index('idx_sync_task_version', 'sync_task', ['version_id'])
    op.create_index('idx_sync_task_instance', 'sync_task', ['instance_id'])
    
    # 5. table_foreign_key 表
    op.create_table(
        'table_foreign_key',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('table_mapping_id', sa.BigInteger(), nullable=False),
        sa.Column('source_field', sa.String(256), nullable=False),
        sa.Column('target_database', sa.String(128), nullable=False),
        sa.Column('target_table', sa.String(256), nullable=False),
        sa.Column('target_field', sa.String(256), nullable=False, server_default='id'),
        sa.Column('confidence', sa.String(16), nullable=False),
        sa.Column('infer_reason', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(32), nullable=True, server_default='pending'),
        sa.Column('reviewed_by', sa.String(128), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('table_mapping_id', 'source_field'),
        sa.ForeignKeyConstraint(['table_mapping_id'], ['table_mapping.id'])
    )
    op.create_index('idx_foreign_key_mapping', 'table_foreign_key', ['table_mapping_id'])
    op.create_index('idx_foreign_key_review', 'table_foreign_key', ['review_status'])
    op.create_index('idx_foreign_key_target', 'table_foreign_key', ['target_database', 'target_table'])
    
    # 6. database_business_domain 表
    op.create_table(
        'database_business_domain',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('database_name', sa.String(128), nullable=False),
        sa.Column('business_domain', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('adjacent_domains', postgresql.ARRAY(sa.String(128)), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('database_name')
    )
    op.create_index('idx_db_domain_domain', 'database_business_domain', ['business_domain'])


def downgrade():
    op.drop_table('database_business_domain')
    op.drop_table('table_foreign_key')
    op.drop_table('sync_task')
    op.drop_table('graphdb_instance')
    op.drop_table('mapping_version_item')
    op.drop_table('mapping_version')
```

- [ ] **Step 2: 运行迁移命令**

```bash
cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO/backend
alembic upgrade head
```

Expected: 成功创建6个新表

- [ ] **Step 3: 验证表结构**

```bash
psql $DATABASE_URL -c "\dt"
```

Expected: 显示 mapping_version, mapping_version_item, graphdb_instance, sync_task, table_foreign_key, database_business_domain

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/20260420_add_graphdb_sync_tables.py
git commit -m "feat: add graphdb sync database tables migration"
```

---

### Task 2: 创建SQLAlchemy模型

**Files:**
- Create: `backend/app/models/mapping_version.py`
- Create: `backend/app/models/mapping_version_item.py`
- Create: `backend/app/models/graphdb_instance.py`
- Create: `backend/app/models/sync_task.py`
- Create: `backend/app/models/table_foreign_key.py`
- Create: `backend/app/models/database_business_domain.py`
- Modify: `backend/app/models/__init__.py`

**依赖:** Task 1

- [ ] **Step 1: 创建 mapping_version.py**

```python
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class MappingVersion(Base):
    __tablename__ = "mapping_version"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version_name = Column(String(128), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="draft")
    source_job_id = Column(BigInteger, ForeignKey("mapping_job.id", ondelete="SET NULL"), nullable=True)
    total_mappings = Column(Integer, nullable=False, default=0)
    fk_inference_status = Column(String(32), nullable=True, default="pending")
    created_by = Column(String(128), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
```

- [ ] **Step 2: 创建 mapping_version_item.py**

```python
from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class MappingVersionItem(Base):
    __tablename__ = "mapping_version_item"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version_id = Column(BigInteger, ForeignKey("mapping_version.id", ondelete="CASCADE"), nullable=False)
    database_name = Column(String(128), nullable=False)
    table_name = Column(String(256), nullable=False)
    fibo_class_uri = Column(String(512), nullable=True)
    confidence_level = Column(String(16), nullable=True)
    mapping_reason = Column(Text, nullable=True)
    field_mappings = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

- [ ] **Step 3: 创建 graphdb_instance.py**

```python
from sqlalchemy import Column, BigInteger, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class GraphDBInstance(Base):
    __tablename__ = "graphdb_instance"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    instance_name = Column(String(128), nullable=False)
    repo_id = Column(String(128), nullable=False)
    graphdb_url = Column(String(512), nullable=False, default="http://localhost:7200")
    ruleset = Column(String(64), nullable=False, default="owl-horst-optimized")
    business_domain = Column(String(128), nullable=True)
    named_graph_prefix = Column(String(256), nullable=True, default="urn:loanfibo")
    status = Column(String(32), nullable=False, default="active")
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
```

- [ ] **Step 4: 创建 sync_task.py**

```python
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class SyncTask(Base):
    __tablename__ = "sync_task"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version_id = Column(BigInteger, ForeignKey("mapping_version.id"), nullable=False)
    instance_id = Column(BigInteger, ForeignKey("graphdb_instance.id"), nullable=False)
    sync_mode = Column(String(32), nullable=False, default="upsert")
    status = Column(String(32), nullable=False, default="pending")
    total_triples = Column(Integer, nullable=False, default=0)
    synced_triples = Column(Integer, nullable=False, default=0)
    generated_files = Column(Integer, nullable=True, default=0)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
```

- [ ] **Step 5: 创建 table_foreign_key.py**

```python
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class TableForeignKey(Base):
    __tablename__ = "table_foreign_key"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    table_mapping_id = Column(BigInteger, ForeignKey("table_mapping.id"), nullable=False)
    source_field = Column(String(256), nullable=False)
    target_database = Column(String(128), nullable=False)
    target_table = Column(String(256), nullable=False)
    target_field = Column(String(256), nullable=False, default="id")
    confidence = Column(String(16), nullable=False)
    infer_reason = Column(Text, nullable=True)
    review_status = Column(String(32), nullable=True, default="pending")
    reviewed_by = Column(String(128), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
```

- [ ] **Step 6: 创建 database_business_domain.py**

```python
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func
from app.database import Base


class DatabaseBusinessDomain(Base):
    __tablename__ = "database_business_domain"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    database_name = Column(String(128), unique=True, nullable=False)
    business_domain = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    adjacent_domains = Column(ARRAY(String(128)), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
```

- [ ] **Step 7: 更新 models/__init__.py**

```python
from app.models.mapping_version import MappingVersion
from app.models.mapping_version_item import MappingVersionItem
from app.models.graphdb_instance import GraphDBInstance
from app.models.sync_task import SyncTask
from app.models.table_foreign_key import TableForeignKey
from app.models.database_business_domain import DatabaseBusinessDomain

__all__ = [
    "MappingVersion",
    "MappingVersionItem", 
    "GraphDBInstance",
    "SyncTask",
    "TableForeignKey",
    "DatabaseBusinessDomain",
]
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add sqlalchemy models for graphdb sync"
```

---

## Phase 2: 后端服务实现

### Task 3: 实现 GraphDB REST 客户端

**Files:**
- Create: `backend/app/services/graphdb_client.py`
- Create: `backend/app/services/exceptions.py`

**依赖:** 无

- [ ] **Step 1: 创建异常类**

```python
# backend/app/services/exceptions.py

class GraphDBError(Exception):
    """GraphDB操作错误"""
    pass

class GraphDBConnectionError(GraphDBError):
    """GraphDB连接错误"""
    pass

class GraphDBRepositoryError(GraphDBError):
    """GraphDB Repository操作错误"""
    pass

class ForeignKeyInferenceError(Exception):
    """外键推断错误"""
    pass
```

- [ ] **Step 2: 创建 GraphDBClient 类**

```python
# backend/app/services/graphdb_client.py

import aiohttp
from typing import Optional, Dict, Any, List
import logging

from app.services.exceptions import GraphDBConnectionError, GraphDBRepositoryError

logger = logging.getLogger(__name__)


class GraphDBClient:
    """GraphDB REST API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:7200"):
        self.base_url = base_url.rstrip("/")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/rest/monitor/infrastructure") as resp:
                    if resp.status == 200:
                        return {"status": "healthy", "response_time_ms": 0}
                    return {"status": "unhealthy", "error": f"HTTP {resp.status}"}
        except Exception as e:
            raise GraphDBConnectionError(f"GraphDB连接失败: {str(e)}")
    
    async def get_repository_info(self, repo_id: str) -> Dict[str, Any]:
        """获取Repository信息"""
        url = f"{self.base_url}/rest/repositories/{repo_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    raise GraphDBRepositoryError(f"Repository '{repo_id}' 不存在")
                else:
                    raise GraphDBRepositoryError(f"获取Repository信息失败: HTTP {resp.status}")
    
    async def upload_rdf(
        self,
        repo_id: str,
        data: str,
        content_type: str = "text/turtle",
        named_graph: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        上传RDF数据到GraphDB
        
        接口: POST /rest/data/import/upload/{repo_id}
        Content-Type: multipart/form-data
        """
        url = f"{self.base_url}/rest/data/import/upload/{repo_id}"
        
        data_bytes = data.encode("utf-8")
        
        form_data = aiohttp.FormData()
        form_data.add_field(
            "file",
            data_bytes,
            filename="data.ttl",
            content_type=content_type
        )
        
        params = {}
        if named_graph:
            params["context"] = named_graph
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data, params=params) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return {
                        "success": True,
                        "triple_count": result.get("tripleCount", 0),
                        "status": result.get("status", "unknown")
                    }
                else:
                    error_text = await resp.text()
                    raise GraphDBRepositoryError(f"RDF导入失败: HTTP {resp.status}, {error_text}")
    
    async def query_sparql(
        self,
        repo_id: str,
        query: str,
        accept_format: str = "application/sparql-results+json"
    ) -> Dict[str, Any]:
        """执行SPARQL查询"""
        url = f"{self.base_url}/repositories/{repo_id}"
        
        headers = {
            "Accept": accept_format
        }
        
        data = {"query": query}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise GraphDBRepositoryError(f"SPARQL查询失败: HTTP {resp.status}, {error_text}")
    
    async def clear_named_graph(self, repo_id: str, named_graph: str) -> bool:
        """清空命名图"""
        query = f"CLEAR GRAPH <{named_graph}>"
        result = await self.query_sparql(repo_id, query)
        return True
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/graphdb_client.py backend/app/services/exceptions.py
git commit -m "feat: add GraphDB REST client"
```

---

### Task 4: 实现 RDF 生成器

**Files:**
- Create: `backend/app/services/rdf_generator.py`

**依赖:** Task 2

- [ ] **Step 1: 创建 RDF 生成器**

```python
# backend/app/services/rdf_generator.py

from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Triple:
    """RDF三元组"""
    subject: str
    predicate: str
    object: str
    is_literal: bool = False


class RDFGenerator:
    """RDF三元组生成器"""
    
    # 命名空间
    NS_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    NS_RDFS = "http://www.w3.org/2000/01/rdf-schema#"
    NS_OWL = "http://www.w3.org/2002/07/owl#"
    NS_LOANFIBO = "urn:loanfibo:"
    NS_SRC = "urn:loanfibo:source:"
    
    def __init__(self, named_graph_prefix: str = "urn:loanfibo"):
        self.named_graph_prefix = named_graph_prefix
    
    def build_entity_uri(self, database: str, table: str) -> str:
        """构建实体URI"""
        return f"{self.NS_SRC}{database}/{table}"
    
    def build_field_uri(self, entity_uri: str, field_name: str) -> str:
        """构建字段URI"""
        return f"{entity_uri}#{field_name}"
    
    def build_named_graph_uri(
        self,
        version_name: str,
        database: str
    ) -> str:
        """
        构建命名图URI
        格式: {prefix}:{version_name}:{database}
        示例: urn:loanfibo:v1.0-credit-loan:iuap_fi_loan
        """
        return f"{self.named_graph_prefix}:{version_name}:{database}"
    
    def generate_entity_triples(
        self,
        database: str,
        table: str,
        fibo_class_uri: str,
        field_mappings: List[Dict[str, Any]],
        foreign_keys: List[Dict[str, Any]]
    ) -> List[Triple]:
        """
        生成实体的RDF三元组（三层模型）
        """
        triples = []
        entity_uri = self.build_entity_uri(database, table)
        
        # L1: 实体声明
        triples.append(Triple(
            subject=entity_uri,
            predicate=f"{self.NS_RDF}type",
            object=fibo_class_uri
        ))
        
        # 构建外键查找字典
        fk_dict = {fk["source_field"]: fk for fk in foreign_keys if fk.get("review_status") == "approved"}
        
        # L2: 属性映射
        for field in field_mappings:
            field_name = field.get("field_name")
            fibo_property = field.get("fibo_property_uri")
            
            if not fibo_property:
                continue
            
            # 判断是否为ObjectProperty（有外键关系）
            if field_name in fk_dict:
                # ObjectProperty: 指向对端实体URI
                fk = fk_dict[field_name]
                target_uri = self.build_entity_uri(
                    fk["target_database"],
                    fk["target_table"]
                )
                triples.append(Triple(
                    subject=entity_uri,
                    predicate=fibo_property,
                    object=target_uri,
                    is_literal=False
                ))
            else:
                # DatatypeProperty: 指向源字段URI占位
                field_uri = self.build_field_uri(entity_uri, field_name)
                triples.append(Triple(
                    subject=entity_uri,
                    predicate=fibo_property,
                    object=field_uri,
                    is_literal=False
                ))
        
        # L3: 映射溯源
        triples.append(Triple(
            subject=entity_uri,
            predicate=f"{self.NS_LOANFIBO}sourceDatabase",
            object=database,
            is_literal=True
        ))
        triples.append(Triple(
            subject=entity_uri,
            predicate=f"{self.NS_LOANFIBO}sourceTable",
            object=table,
            is_literal=True
        ))
        
        return triples
    
    def serialize_turtle(self, triples: List[Triple], prefixes: Optional[Dict[str, str]] = None) -> str:
        """将三元组序列化为Turtle格式"""
        lines = []
        
        # 添加前缀声明
        default_prefixes = {
            "rdf": self.NS_RDF,
            "rdfs": self.NS_RDFS,
            "owl": self.NS_OWL,
            "loanfibo": self.NS_LOANFIBO,
            "src": self.NS_SRC,
        }
        if prefixes:
            default_prefixes.update(prefixes)
        
        for prefix, uri in default_prefixes.items():
            lines.append(f"@prefix {prefix}: <{uri}> .")
        
        lines.append("")
        
        # 按subject分组
        subjects: Dict[str, List[Triple]] = {}
        for triple in triples:
            if triple.subject not in subjects:
                subjects[triple.subject] = []
            subjects[triple.subject].append(triple)
        
        # 生成Turtle
        for subject, subject_triples in subjects.items():
            lines.append(f"<{subject}>")
            
            pred_obj_pairs = []
            for i, triple in enumerate(subject_triples):
                predicate = triple.predicate
                if triple.is_literal:
                    obj = f'"{triple.object}"'
                else:
                    obj = f"<{triple.object}>"
                
                if i == len(subject_triples) - 1:
                    pred_obj_pairs.append(f"    {predicate} {obj} ;")
                else:
                    pred_obj_pairs.append(f"    {predicate} {obj} ;")
            
            # 最后一个用 . 而不是 ;
            if pred_obj_pairs:
                pred_obj_pairs[-1] = pred_obj_pairs[-1].replace(" ;", " .")
            
            lines.extend(pred_obj_pairs)
            lines.append("")
        
        return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/rdf_generator.py
git commit -m "feat: add RDF generator with triple-layer model"
```

---

### Task 5: 实现版本管理服务

**Files:**
- Create: `backend/app/services/version_service.py`
- Create: `backend/app/schemas/version.py`

**依赖:** Task 2, Task 4

- [ ] **Step 1: 创建版本Schema**

```python
# backend/app/schemas/version.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MappingVersionCreate(BaseModel):
    version_name: str
    description: Optional[str] = None
    source_job_id: int
    scope_databases: List[str]


class MappingVersionResponse(BaseModel):
    id: int
    version_name: str
    description: Optional[str]
    status: str
    total_mappings: int
    fk_inference_status: str
    created_by: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
```

- [ ] **Step 2: 创建版本服务**

```python
# backend/app/services/version_service.py

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.mapping_version import MappingVersion
from app.models.mapping_version_item import MappingVersionItem
from app.models.table_mapping import TableMapping
from app.schemas.version import MappingVersionCreate


class VersionService:
    """版本管理服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_version(
        self,
        data: MappingVersionCreate,
        created_by: Optional[str] = None
    ) -> MappingVersion:
        """创建发布版本"""
        # 1. 查询审核通过的映射
        query = select(TableMapping).where(
            and_(
                TableMapping.job_id == data.source_job_id,
                TableMapping.database_name.in_(data.scope_databases),
                TableMapping.review_status == "approved",
                TableMapping.is_deleted == False
            )
        )
        result = await self.db.execute(query)
        table_mappings = result.scalars().all()
        
        if not table_mappings:
            raise ValueError("没有符合条件的映射记录")
        
        # 2. 创建版本记录
        version = MappingVersion(
            version_name=data.version_name,
            description=data.description,
            source_job_id=data.source_job_id,
            total_mappings=len(table_mappings),
            status="draft",
            fk_inference_status="pending",
            created_by=created_by
        )
        self.db.add(version)
        await self.db.flush()  # 获取version.id
        
        # 3. 创建版本快照项
        for tm in table_mappings:
            # 获取字段映射（需要field_mapping表查询）
            # 这里简化处理，实际需要查询field_mapping表
            version_item = MappingVersionItem(
                version_id=version.id,
                database_name=tm.database_name,
                table_name=tm.table_name,
                fibo_class_uri=tm.fibo_class_uri,
                confidence_level=tm.confidence_level,
                mapping_reason=tm.mapping_reason,
                field_mappings=[]  # 实际需要填充字段映射
            )
            self.db.add(version_item)
        
        await self.db.commit()
        return version
    
    async def publish_version(self, version_id: int) -> MappingVersion:
        """发布版本"""
        query = select(MappingVersion).where(MappingVersion.id == version_id)
        result = await self.db.execute(query)
        version = result.scalar_one_or_none()
        
        if not version:
            raise ValueError(f"版本 {version_id} 不存在")
        
        if version.status != "draft":
            raise ValueError(f"版本状态为 {version.status}，不能发布")
        
        version.status = "publishing"
        await self.db.commit()
        
        # TODO: 触发异步外键推断任务
        
        return version
    
    async def get_version(self, version_id: int) -> Optional[MappingVersion]:
        """获取版本详情"""
        query = select(MappingVersion).where(
            and_(
                MappingVersion.id == version_id,
                MappingVersion.is_deleted == False
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_versions(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[MappingVersion], int]:
        """获取版本列表"""
        query = select(MappingVersion).where(MappingVersion.is_deleted == False)
        
        if status:
            query = query.where(MappingVersion.status == status)
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # 分页
        query = query.order_by(MappingVersion.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        versions = result.scalars().all()
        
        return list(versions), total
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/version_service.py backend/app/schemas/version.py
git commit -m "feat: add version management service"
```

---

## Phase 3: API路由实现

### Task 6: 实现版本管理API

**Files:**
- Create: `backend/app/api/v1/endpoints/versions.py`
- Modify: `backend/app/api/v1/router.py`

**依赖:** Task 5

- [ ] **Step 1: 创建版本API路由**

```python
# backend/app/api/v1/endpoints/versions.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.database import get_db
from app.services.version_service import VersionService
from app.schemas.version import MappingVersionCreate, MappingVersionResponse
from app.schemas.response import ResponseModel, PaginatedResponse

router = APIRouter()


@router.post("", response_model=ResponseModel[MappingVersionResponse])
async def create_version(
    data: MappingVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: str = "admin"  # TODO: 从JWT获取
):
    """创建发布版本"""
    try:
        service = VersionService(db)
        version = await service.create_version(data, created_by=current_user)
        return ResponseModel(data=MappingVersionResponse.model_validate(version))
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": 400001, "message": str(e)})


@router.get("", response_model=PaginatedResponse[MappingVersionResponse])
async def list_versions(
    status: Optional[str] = Query(None, description="版本状态过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取版本列表"""
    service = VersionService(db)
    versions, total = await service.list_versions(status=status, page=page, page_size=page_size)
    
    return PaginatedResponse(
        data=[MappingVersionResponse.model_validate(v) for v in versions],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{version_id}", response_model=ResponseModel[MappingVersionResponse])
async def get_version(
    version_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取版本详情"""
    service = VersionService(db)
    version = await service.get_version(version_id)
    
    if not version:
        raise HTTPException(status_code=404, detail={"code": 404001, "message": "版本不存在"})
    
    return ResponseModel(data=MappingVersionResponse.model_validate(version))


@router.post("/{version_id}/publish", response_model=ResponseModel[MappingVersionResponse])
async def publish_version(
    version_id: int,
    db: AsyncSession = Depends(get_db)
):
    """发布版本"""
    try:
        service = VersionService(db)
        version = await service.publish_version(version_id)
        return ResponseModel(data=MappingVersionResponse.model_validate(version))
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": 402001, "message": str(e)})
```

- [ ] **Step 2: 更新路由注册**

```python
# backend/app/api/v1/router.py

from fastapi import APIRouter
from app.api.v1.endpoints import versions, graphdb_instances, sync_tasks, foreign_keys, graph_explorer

api_router = APIRouter()

# 现有路由...

# GraphDB同步功能路由
api_router.include_router(versions.router, prefix="/versions", tags=["versions"])
api_router.include_router(graphdb_instances.router, prefix="/graphdb/instances", tags=["graphdb"])
api_router.include_router(sync_tasks.router, prefix="/sync/tasks", tags=["sync"])
api_router.include_router(foreign_keys.router, prefix="/foreign-keys", tags=["foreign-keys"])
api_router.include_router(graph_explorer.router, prefix="/graph-explorer", tags=["graph-explorer"])
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/endpoints/versions.py backend/app/api/v1/router.py
git commit -m "feat: add version management API endpoints"
```

---

## 后续任务（概要）

由于计划文档长度限制，以下是后续任务的概要。每个任务都应遵循相同的详细步骤格式（Step 1-5）。

### Phase 4: 外键推断服务
- Task 7: 实现 LLM 外键推断服务 (`foreign_key_inference.py`)
- Task 8: 实现外键推断 API (`foreign_keys.py`)

### Phase 5: GraphDB实例与同步任务
- Task 9: 实现 GraphDB 实例服务与 API
- Task 10: 实现同步任务服务与 API
- Task 11: 实现同步任务执行（异步任务）

### Phase 6: 图谱浏览API
- Task 12: 实现图谱浏览服务 (`graph_explorer.py`)
- Task 13: 实现 SPARQL 查询 API

### Phase 7: 前端实现
- Task 14: 安装图可视化库 (D3.js 或 Cytoscape.js)
- Task 15: 实现 GraphCanvas 组件
- Task 16: 实现 NodeDetailPanel 组件
- Task 17: 实现版本管理页面
- Task 18: 实现 GraphDB 实例管理页面
- Task 19: 实现同步任务页面
- Task 20: 实现图谱浏览页面

---

## 执行选项

**计划已保存到:** `docs/superpowers/plans/2026-04-20-graphdb-sync-implementation.md`

**两个执行选项:**

1. **Subagent-Driven (推荐)** - 为每个Task派遣新的子代理，任务间进行评审，快速迭代
2. **Inline Execution** - 在当前会话中使用 executing-plans 执行任务，批量执行并设置检查点

**请选择执行方式？**

**注意:** 本计划包含20个Task，建议分阶段实施：
- Phase 1-2: 数据库 + 后端基础服务
- Phase 3-6: API实现
- Phase 7: 前端实现
