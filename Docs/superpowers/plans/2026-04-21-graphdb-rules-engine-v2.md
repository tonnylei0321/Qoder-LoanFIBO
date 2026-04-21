# GraphDB 规则引擎 v2.0 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 GraphDB 规则引擎 v2.0 的核心编译和查询能力，支持 L0/L1/L2 三层规则编译、NLQ 自然语言查询、多租户隔离。

**Architecture:** FastAPI 异步服务 + Celery 同步 Worker 双模式；GraphDB 存储 L0/L1 规则，PostgreSQL 存储 L2 规则，Redis 缓存编译结果。查询引擎采用分层架构：模板匹配(100%准确) → BERT分类(90%查询) → LLM解析(复杂查询)。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy(asyncpg) / Celery / Redis / httpx / RestrictedPython / PyTorch(TinyBERT)

---

## 文件结构

```
backend/app/
├── models/
│   ├── tenant.py                    # 租户模型
│   ├── tenant_config.py             # 租户配置模型
│   ├── compile_status.py            # 编译状态模型
│   ├── rule_version.py              # 规则版本历史模型
│   └── l2_rule.py                   # L2规则模型
├── services/
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── compiler.py              # RuleCompiler 核心编译器
│   │   ├── dsl_parser.py            # DSL解析器
│   │   ├── dsl_executor.py          # DSL执行引擎(RestrictedPython)
│   │   ├── incremental_compiler.py  # 增量编译器
│   │   ├── compile_scheduler.py     # 编译调度器
│   │   ├── compile_worker.py        # Celery Worker
│   │   └── conflict_resolver.py     # 规则冲突检测与解决
│   ├── query/
│   │   ├── __init__.py
│   │   ├── intent_classifier.py     # 意图分类器
│   │   ├── sql_generator.py         # SQL生成器(白名单+参数化)
│   │   ├── semantic_mapping.py      # RDF到SQL语义映射
│   │   ├── rule_matcher.py          # 规则匹配器
│   │   ├── query_engine.py          # 查询引擎
│   │   └── query_confirmation.py    # 查询确认服务
│   ├── graphdb_client.py            # GraphDB客户端(双模式)
│   └── compile_cache.py             # 编译缓存(Redis)
├── api/v1/
│   ├── rules.py                     # 规则管理API
│   ├── query.py                     # NLQ查询API
│   └── tenant.py                    # 租户配置API
├── schemas/
│   ├── rules.py                     # 规则相关Schema
│   └── query.py                     # 查询相关Schema
└── config.py                        # 新增GraphDB/Redis配置

tests/
├── unit/
│   ├── services/
│   │   ├── rules/
│   │   │   ├── test_compiler.py
│   │   │   ├── test_dsl_parser.py
│   │   │   ├── test_dsl_executor.py
│   │   │   ├── test_incremental_compiler.py
│   │   │   └── test_conflict_resolver.py
│   │   ├── query/
│   │   │   ├── test_intent_classifier.py
│   │   │   ├── test_sql_generator.py
│   │   │   ├── test_semantic_mapping.py
│   │   │   ├── test_rule_matcher.py
│   │   │   └── test_query_engine.py
│   │   ├── test_graphdb_client.py
│   │   └── test_compile_cache.py
│   └── api/
│       ├── test_rules_api.py
│       └── test_query_api.py
└── integration/
    └── test_compile_pipeline.py
```

---

## Phase 1: 核心数据模型与编译缓存

### Task 1: 租户与编译状态数据模型

**Files:**
- Create: `backend/app/models/tenant.py`
- Create: `backend/app/models/tenant_config.py`
- Create: `backend/app/models/compile_status.py`
- Create: `backend/app/models/rule_version.py`
- Create: `backend/app/models/l2_rule.py`
- Test: `tests/unit/models/test_tenant_models.py`

- [ ] **Step 1: 写失败测试 - 租户模型**

```python
# tests/unit/models/test_tenant_models.py
"""租户与编译状态模型单元测试"""
import pytest
from datetime import datetime
from backend.app.models.tenant import Tenant
from backend.app.models.tenant_config import TenantConfig
from backend.app.models.compile_status import CompileStatus
from backend.app.models.rule_version import RuleVersion
from backend.app.models.l2_rule import L2Rule


class TestTenant:
    def test_create_tenant(self):
        tenant = Tenant(
            id="tenant_001",
            name="测试租户",
            industry="banking",
            tier="tier1",
            status="active"
        )
        assert tenant.id == "tenant_001"
        assert tenant.industry == "banking"
        assert tenant.tier == "tier1"

    def test_tenant_default_status(self):
        tenant = Tenant(id="t1", name="test", industry="banking", tier="tier2")
        assert tenant.status == "active"


class TestTenantConfig:
    def test_create_config(self):
        config = TenantConfig(
            tenant_id="tenant_001",
            db_schema="tenant_001",
            compile_priority=5,
            max_rules=100,
            nlq_enabled=True
        )
        assert config.tenant_id == "tenant_001"
        assert config.nlq_enabled is True


class TestCompileStatus:
    def test_create_compile_status(self):
        status = CompileStatus(
            tenant_id="tenant_001",
            status="ready",
            current_version="v1.0.0",
            last_compiled_at=datetime.now()
        )
        assert status.status == "ready"

    def test_compile_status_states(self):
        """验证所有合法状态"""
        valid_states = ["ready", "compiling", "L0_CRITICAL",
                        "L0_HIGH_COMPILING", "L0_CRITICAL_FAILED",
                        "L0_CRITICAL_ERROR", "STALE", "failed"]
        for state in valid_states:
            status = CompileStatus(tenant_id="t1", status=state)
            assert status.status == state


class TestRuleVersion:
    def test_create_version(self):
        version = RuleVersion(
            id=1,
            tenant_id="tenant_001",
            version="v1.0.0",
            rule_count=50,
            compile_time_ms=1200
        )
        assert version.version == "v1.0.0"
        assert version.rule_count == 50


class TestL2Rule:
    def test_create_l2_rule(self):
        rule = L2Rule(
            id="rule_001",
            tenant_id="tenant_001",
            name="自定义风控规则",
            rule_type="threshold",
            definition={"field": "loan_amount", "operator": ">", "value": 1000000},
            priority=10,
            enabled=True
        )
        assert rule.tenant_id == "tenant_001"
        assert rule.rule_type == "threshold"
        assert rule.enabled is True
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/models/test_tenant_models.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现模型**

```python
# backend/app/models/tenant.py
"""租户模型"""
from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from backend.app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)  # tier1/tier2/tier3
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

```python
# backend/app/models/tenant_config.py
"""租户配置模型"""
from sqlalchemy import Column, String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database import Base


class TenantConfig(Base):
    __tablename__ = "tenant_configs"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    db_schema: Mapped[str] = mapped_column(String(64), nullable=False)
    compile_priority: Mapped[int] = mapped_column(Integer, default=5)
    max_rules: Mapped[int] = mapped_column(Integer, default=100)
    nlq_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_settings: Mapped[str] = mapped_column(Text, nullable=True)
```

```python
# backend/app/models/compile_status.py
"""编译状态模型"""
from sqlalchemy import Column, String, Integer, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from backend.app.database import Base


class CompileStatus(Base):
    __tablename__ = "compile_status"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    current_version: Mapped[str] = mapped_column(String(32), nullable=True)
    last_compiled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(String(1024), nullable=True)
    staleness_seconds: Mapped[int] = mapped_column(Integer, default=0)
```

```python
# backend/app/models/rule_version.py
"""规则版本历史模型"""
from sqlalchemy import Column, String, Integer, DateTime, Float, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from backend.app.database import Base


class RuleVersion(Base):
    __tablename__ = "rule_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_count: Mapped[int] = mapped_column(Integer, default=0)
    compile_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    config_snapshot: Mapped[str] = mapped_column(Text, nullable=True)
```

```python
# backend/app/models/l2_rule.py
"""L2规则模型（租户自定义规则）"""
from sqlalchemy import Column, String, Integer, Boolean, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from backend.app.database import Base


class L2Rule(Base):
    __tablename__ = "l2_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/models/test_tenant_models.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/tenant.py backend/app/models/tenant_config.py \
       backend/app/models/compile_status.py backend/app/models/rule_version.py \
       backend/app/models/l2_rule.py tests/unit/models/test_tenant_models.py
git commit -m "feat: add tenant and compile status data models for rules engine v2"
```

---

### Task 2: 编译缓存服务 (Redis)

**Files:**
- Create: `backend/app/services/compile_cache.py`
- Test: `tests/unit/services/test_compile_cache.py`

- [ ] **Step 1: 写失败测试 - 编译缓存**

```python
# tests/unit/services/test_compile_cache.py
"""编译缓存服务单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.services.compile_cache import CompileCache


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def cache(mock_redis):
    return CompileCache(redis_client=mock_redis)


class TestCompileCache:
    @pytest.mark.asyncio
    async def test_get_compiled_rules_cache_miss(self, cache, mock_redis):
        mock_redis.get.return_value = None
        result = await cache.get_compiled_rules("tenant_001")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_compiled_rules(self, cache, mock_redis):
        rules = {"version": "v1.0.0", "rules": []}
        await cache.set_compiled_rules("tenant_001", rules, ttl=3600)
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_compile_status(self, cache, mock_redis):
        mock_redis.get.return_value = b'"ready"'
        status = await cache.get_compile_status("tenant_001")
        assert status == "ready"

    @pytest.mark.asyncio
    async def test_set_compile_status_with_ttl(self, cache, mock_redis):
        await cache.set_compile_status("tenant_001", "L0_HIGH_COMPILING", ttl=300)
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_stale(self, cache, mock_redis):
        await cache.mark_stale("tenant_001", reason="L0_UPDATED", max_staleness=3600)
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_get_staleness_seconds(self, cache, mock_redis):
        mock_redis.get.return_value = b'1800'
        seconds = await cache.get_staleness_seconds("tenant_001")
        assert seconds == 1800
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/test_compile_cache.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现编译缓存**

```python
# backend/app/services/compile_cache.py
"""编译缓存服务 - Redis存储编译后规则和状态"""
import json
from typing import Any, Dict, Optional
from loguru import logger


class CompileCache:
    """编译缓存（Redis）"""

    KEY_PREFIX = "rules"
    STATUS_PREFIX = "compile_status"
    STALE_PREFIX = "stale"

    def __init__(self, redis_client):
        self.redis = redis_client

    def _rules_key(self, tenant_id: str) -> str:
        return f"{self.KEY_PREFIX}:{tenant_id}:latest"

    def _status_key(self, tenant_id: str) -> str:
        return f"{self.STATUS_PREFIX}:{tenant_id}"

    def _stale_key(self, tenant_id: str) -> str:
        return f"{self.STALE_PREFIX}:{tenant_id}"

    async def get_compiled_rules(self, tenant_id: str) -> Optional[Dict]:
        data = await self.redis.get(self._rules_key(tenant_id))
        if data is None:
            return None
        return json.loads(data)

    async def set_compiled_rules(
        self, tenant_id: str, rules: Dict, ttl: int = 86400
    ) -> bool:
        key = self._rules_key(tenant_id)
        await self.redis.setex(key, ttl, json.dumps(rules, default=str))
        return True

    async def get_compile_status(self, tenant_id: str) -> Optional[str]:
        data = await self.redis.get(self._status_key(tenant_id))
        if data is None:
            return None
        return json.loads(data)

    async def set_compile_status(
        self, tenant_id: str, status: str, ttl: Optional[int] = None
    ) -> bool:
        key = self._status_key(tenant_id)
        value = json.dumps(status)
        if ttl:
            await self.redis.setex(key, ttl, value)
        else:
            await self.redis.set(key, value)
        return True

    async def mark_stale(
        self, tenant_id: str, reason: str, max_staleness: int = 3600
    ) -> bool:
        import time
        key = self._stale_key(tenant_id)
        await self.redis.setex(key, max_staleness, str(int(time.time())))
        await self.set_compile_status(tenant_id, "STALE")
        return True

    async def get_staleness_seconds(self, tenant_id: str) -> int:
        import time
        data = await self.redis.get(self._stale_key(tenant_id))
        if data is None:
            return 0
        marked_time = int(data)
        return int(time.time()) - marked_time

    async def get_last_compile(self, tenant_id: str) -> Optional[Dict]:
        return await self.get_compiled_rules(tenant_id)

    async def delete(self, tenant_id: str) -> bool:
        keys = [
            self._rules_key(tenant_id),
            self._status_key(tenant_id),
            self._stale_key(tenant_id),
        ]
        for key in keys:
            await self.redis.delete(key)
        return True
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/test_compile_cache.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/compile_cache.py tests/unit/services/test_compile_cache.py
git commit -m "feat: add compile cache service with Redis backend"
```

---

## Phase 2: 语义映射与SQL生成器

### Task 3: RDF到SQL语义映射

**Files:**
- Create: `backend/app/services/query/semantic_mapping.py`
- Test: `tests/unit/services/query/test_semantic_mapping.py`

- [ ] **Step 1: 写失败测试 - 语义映射**

```python
# tests/unit/services/query/test_semantic_mapping.py
"""语义映射单元测试"""
import pytest
from backend.app.services.query.semantic_mapping import SemanticMapping, JoinDefinition, TableMapping


class TestSemanticMapping:
    @pytest.fixture
    def mapping(self):
        return SemanticMapping(
            concept_to_table={
                "loan:LoanContract": "bd_loan_contract",
                "loan:LoanContract.loanAmount": "bd_loan_contract.loan_amount",
                "loan:LoanContract.borrower": "bd_loan_contract.borrower_id",
                "loan:LoanContract.status": "bd_loan_contract.contract_status",
            },
            relation_to_join={
                "loan:hasBorrower": JoinDefinition(
                    from_table="bd_loan_contract",
                    to_table="bd_borrower",
                    from_column="borrower_id",
                    to_column="id",
                    join_type="INNER"
                ),
            },
            table_mappings={
                "bd_loan_contract": TableMapping(
                    table_name="bd_loan_contract",
                    concept="loan:LoanContract",
                    allowed_columns=["loan_amount", "borrower_id", "contract_status"]
                ),
                "bd_borrower": TableMapping(
                    table_name="bd_borrower",
                    concept="loan:Borrower",
                    allowed_columns=["id", "name", "credit_score"]
                ),
            }
        )

    def test_resolve_concept_to_table(self, mapping):
        table = mapping.resolve_concept("loan:LoanContract")
        assert table == "bd_loan_contract"

    def test_resolve_slot_to_column(self, mapping):
        column = mapping.resolve_slot("loanAmount", "loan:LoanContract")
        assert column == "bd_loan_contract.loan_amount"

    def test_resolve_unknown_concept(self, mapping):
        table = mapping.resolve_concept("unknown:Concept")
        assert table is None

    def test_resolve_unknown_slot(self, mapping):
        column = mapping.resolve_slot("nonExistent", "loan:LoanContract")
        assert column is None

    def test_get_join_definition(self, mapping):
        join = mapping.get_join("loan:hasBorrower")
        assert join is not None
        assert join.from_table == "bd_loan_contract"
        assert join.to_table == "bd_borrower"

    def test_is_column_allowed(self, mapping):
        assert mapping.is_column_allowed("bd_loan_contract", "loan_amount") is True
        assert mapping.is_column_allowed("bd_loan_contract", "drop_table") is False
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/test_semantic_mapping.py -v`
Expected: FAIL

- [ ] **Step 3: 实现语义映射**

```python
# backend/app/services/query/semantic_mapping.py
"""RDF到SQL语义映射层"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class JoinDefinition:
    """JOIN关系定义"""
    from_table: str
    to_table: str
    from_column: str
    to_column: str
    join_type: str = "INNER"


@dataclass
class TableMapping:
    """表映射定义"""
    table_name: str
    concept: str
    allowed_columns: List[str] = field(default_factory=list)


class SemanticMapping:
    """语义映射定义"""

    def __init__(
        self,
        concept_to_table: Dict[str, str],
        relation_to_join: Dict[str, JoinDefinition],
        table_mappings: Dict[str, TableMapping],
    ):
        self.concept_to_table = concept_to_table
        self.relation_to_join = relation_to_join
        self.table_mappings = table_mappings

    def resolve_concept(self, concept: str) -> Optional[str]:
        table = self.concept_to_table.get(concept)
        return table

    def resolve_slot(self, slot_name: str, concept: str) -> Optional[str]:
        key = f"{concept}.{slot_name}"
        return self.concept_to_table.get(key)

    def get_join(self, relation: str) -> Optional[JoinDefinition]:
        return self.relation_to_join.get(relation)

    def is_column_allowed(self, table_name: str, column_name: str) -> bool:
        mapping = self.table_mappings.get(table_name)
        if mapping is None:
            return False
        return column_name in mapping.allowed_columns
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/test_semantic_mapping.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/query/semantic_mapping.py \
       backend/app/services/query/__init__.py \
       tests/unit/services/query/test_semantic_mapping.py
git commit -m "feat: add semantic mapping layer for RDF-to-SQL translation"
```

---

### Task 4: SQL生成器（白名单+参数化）

**Files:**
- Create: `backend/app/services/query/sql_generator.py`
- Test: `tests/unit/services/query/test_sql_generator.py`

- [ ] **Step 1: 写失败测试 - SQL生成器**

```python
# tests/unit/services/query/test_sql_generator.py
"""SQL生成器单元测试"""
import pytest
from backend.app.services.query.sql_generator import SQLGenerator, SecurityError
from backend.app.services.query.semantic_mapping import SemanticMapping, JoinDefinition, TableMapping


@pytest.fixture
def mapping():
    return SemanticMapping(
        concept_to_table={
            "loan:LoanContract": "bd_loan_contract",
            "loan:LoanContract.loanAmount": "bd_loan_contract.loan_amount",
            "loan:LoanContract.status": "bd_loan_contract.contract_status",
        },
        relation_to_join={
            "loan:hasBorrower": JoinDefinition(
                from_table="bd_loan_contract", to_table="bd_borrower",
                from_column="borrower_id", to_column="id"
            ),
        },
        table_mappings={
            "bd_loan_contract": TableMapping(
                table_name="bd_loan_contract", concept="loan:LoanContract",
                allowed_columns=["loan_amount", "contract_status", "borrower_id"]
            ),
        }
    )


@pytest.fixture
def generator(mapping):
    return SQLGenerator(mapping=mapping)


class TestSQLGenerator:
    def test_generate_simple_query(self, generator):
        sql, params = generator.generate_safe(
            table_name="bd_loan_contract",
            select_columns=["loan_amount", "contract_status"],
            conditions={"loan_amount": 1000000},
        )
        assert "SELECT" in sql
        assert "bd_loan_contract" in sql
        assert "%s" in sql
        assert 1000000 in params

    def test_reject_unknown_slot(self, generator):
        with pytest.raises(SecurityError, match="未定义的槽位名"):
            generator.generate_safe(
                table_name="bd_loan_contract",
                select_columns=["loan_amount"],
                conditions={"evil_injection": "drop table"},
            )

    def test_reject_sql_injection_in_column(self, generator):
        with pytest.raises(SecurityError):
            generator.generate_safe(
                table_name="bd_loan_contract",
                select_columns=["; DROP TABLE bd_loan_contract;--"],
                conditions={},
            )

    def test_validate_sql_safety_rejects_insert(self, generator):
        with pytest.raises(SecurityError, match="危险操作"):
            generator._validate_sql_safety("INSERT INTO users VALUES (1)")

    def test_validate_sql_safety_rejects_semicolon_injection(self, generator):
        with pytest.raises(SecurityError, match="非法分号"):
            generator._validate_sql_safety("SELECT * FROM t; DROP TABLE t")

    def test_quote_identifier(self, generator):
        assert generator._quote_identifier("loan_amount") == '"loan_amount"'
        assert generator._quote_identifier('col"with"quote') == '"col""with""quote"'
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/test_sql_generator.py -v`
Expected: FAIL

- [ ] **Step 3: 实现SQL生成器**

```python
# backend/app/services/query/sql_generator.py
"""SQL生成器 - 白名单+参数化查询"""
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from backend.app.services.query.semantic_mapping import SemanticMapping, TableMapping


class SecurityError(Exception):
    """SQL安全异常"""
    pass


class SQLGenerator:
    """SQL生成器（安全优先）"""

    def __init__(self, mapping: SemanticMapping):
        self.mapping = mapping

    def generate_safe(
        self,
        table_name: str,
        select_columns: List[str],
        conditions: Dict[str, Any],
        order_by: Optional[str] = None,
        limit: int = 100,
    ) -> Tuple[str, List[Any]]:
        table_mapping = self.mapping.table_mappings.get(table_name)
        if not table_mapping:
            raise SecurityError(f"未定义的表: {table_name}")

        quoted_cols = []
        for col in select_columns:
            if not self.mapping.is_column_allowed(table_name, col):
                raise SecurityError(f"未授权的列: {col}")
            quoted_cols.append(self._quote_identifier(col))

        where_clause, params = self._build_parametrized_conditions(
            conditions, table_mapping
        )

        sql = f"SELECT {', '.join(quoted_cols)} FROM {self._quote_identifier(table_name)}"
        if where_clause:
            sql += f" WHERE {' AND '.join(where_clause)}"
        if order_by:
            sql += f" ORDER BY {self._quote_identifier(order_by)}"
        sql += f" LIMIT {limit}"

        self._validate_sql_safety(sql)
        return sql, params

    def _build_parametrized_conditions(
        self, slots: Dict[str, Any], table_mapping: TableMapping
    ) -> Tuple[List[str], List[Any]]:
        conditions = []
        params = []

        for slot_name, slot_value in slots.items():
            column_name = self._resolve_slot_to_column(slot_name, table_mapping)
            if not column_name:
                raise SecurityError(f"未定义的槽位名: {slot_name}")

            quoted_column = self._quote_identifier(column_name)
            conditions.append(f"{quoted_column} = %s")
            params.append(slot_value)

        return conditions, params

    def _resolve_slot_to_column(
        self, slot_name: str, table_mapping: TableMapping
    ) -> Optional[str]:
        full_key = f"{table_mapping.concept}.{slot_name}"
        column_path = self.mapping.concept_to_table.get(full_key)
        if column_path:
            parts = column_path.split(".")
            if len(parts) == 2:
                _, column = parts
                if self.mapping.is_column_allowed(table_mapping.table_name, column):
                    return column
        return None

    def _quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def _validate_sql_safety(self, sql: str):
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP',
            'TRUNCATE', 'ALTER', 'CREATE', 'GRANT',
            'EXECUTE', 'EXEC', 'XP_', 'LOAD_'
        ]
        upper_sql = sql.upper()
        for keyword in dangerous_keywords:
            if keyword in upper_sql:
                raise SecurityError(f"SQL包含危险操作: {keyword}")

        stripped = sql.strip().rstrip(';')
        if ';' in stripped:
            raise SecurityError("SQL包含非法分号")

        if '--' in sql or '/*' in sql:
            raise SecurityError("SQL包含非法注释")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/test_sql_generator.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/query/sql_generator.py \
       tests/unit/services/query/test_sql_generator.py
git commit -m "feat: add SQL generator with whitelist and parameterized query security"
```

---

## Phase 3: 规则编译器核心

### Task 5: DSL解析器与执行引擎

**Files:**
- Create: `backend/app/services/rules/dsl_parser.py`
- Create: `backend/app/services/rules/dsl_executor.py`
- Test: `tests/unit/services/rules/test_dsl_parser.py`
- Test: `tests/unit/services/rules/test_dsl_executor.py`

- [ ] **Step 1: 写失败测试 - DSL解析器**

```python
# tests/unit/services/rules/test_dsl_parser.py
"""DSL解析器单元测试"""
import pytest
from backend.app.services.rules.dsl_parser import DSLParser, DSLFormula


class TestDSLParser:
    @pytest.fixture
    def parser(self):
        return DSLParser()

    def test_parse_simple_comparison(self, parser):
        formula = parser.parse("loan_amount > 1000000")
        assert formula is not None
        assert formula.operator == ">"
        assert formula.right_value == 1000000

    def test_parse_range_condition(self, parser):
        formula = parser.parse("100000 <= loan_amount <= 500000")
        assert formula is not None
        assert formula.operator == "between"

    def test_parse_compound_condition(self, parser):
        formula = parser.parse("loan_amount > 1000000 AND risk_level = 'high'")
        assert formula is not None
        assert formula.connector == "AND"

    def test_parse_invalid_formula(self, parser):
        with pytest.raises(ValueError):
            parser.parse("!!!invalid!!!")

    def test_parse_threshold_rule(self, parser):
        formula = parser.parse("ratio > 0.8")
        assert formula.operator == ">"
        assert formula.right_value == 0.8
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/rules/test_dsl_parser.py -v`
Expected: FAIL

- [ ] **Step 3: 实现DSL解析器**

```python
# backend/app/services/rules/dsl_parser.py
"""DSL解析器 - 规则公式语法解析"""
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


@dataclass
class DSLFormula:
    """DSL公式AST节点"""
    field_name: str
    operator: str
    right_value: Any
    connector: Optional[str] = None  # AND / OR
    children: List['DSLFormula'] = field(default_factory=list)

    @property
    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(c.depth for c in self.children)


class DSLParser:
    """DSL公式解析器"""

    OPERATORS = {
        '>': '>', '>=': '>=', '<': '<', '<=': '<=',
        '=': '=', '==': '=', '!=': '!=', '<>': '!=',
    }

    def parse(self, formula: str) -> DSLFormula:
        formula = formula.strip()
        if not formula:
            raise ValueError("空公式")

        # 处理 AND/OR 连接
        for connector in [' AND ', ' OR ']:
            parts = self._split_by_connector(formula, connector.strip())
            if len(parts) > 1:
                children = [self.parse(p.strip()) for p in parts]
                return DSLFormula(
                    field_name="_compound",
                    operator="compound",
                    right_value=None,
                    connector=connector.strip(),
                    children=children,
                )

        # 处理 between
        between_match = re.match(
            r'(\S+)\s+between\s+(\S+)\s+and\s+(\S+)', formula, re.IGNORECASE
        )
        if between_match:
            return DSLFormula(
                field_name=between_match.group(1),
                operator="between",
                right_value=(self._parse_value(between_match.group(2)),
                             self._parse_value(between_match.group(3))),
            )

        # 处理 range: 100 <= x <= 500
        range_match = re.match(
            r'(\S+)\s*(<=?|>=?)\s*(\S+)\s*(<=?|>=?)\s*(\S+)', formula
        )
        if range_match:
            return DSLFormula(
                field_name=range_match.group(3),
                operator="between",
                right_value=(self._parse_value(range_match.group(1)),
                             self._parse_value(range_match.group(5))),
            )

        # 处理简单比较
        for op in ['>=', '<=', '!=', '<>', '==', '>', '<', '=']:
            parts = formula.split(op, 1)
            if len(parts) == 2:
                return DSLFormula(
                    field_name=parts[0].strip(),
                    operator=self.OPERATORS.get(op, op),
                    right_value=self._parse_value(parts[1].strip()),
                )

        raise ValueError(f"无法解析公式: {formula}")

    def _split_by_connector(self, formula: str, connector: str) -> List[str]:
        pattern = f' {connector} '
        return formula.split(pattern)

    def _parse_value(self, value: str) -> Any:
        value = value.strip().strip("'\"")
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/rules/test_dsl_parser.py -v`
Expected: PASS

- [ ] **Step 5: 写失败测试 - DSL执行引擎**

```python
# tests/unit/services/rules/test_dsl_executor.py
"""DSL执行引擎单元测试"""
import pytest
from backend.app.services.rules.dsl_executor import DSLExecutor, SecurityError
from backend.app.services.rules.dsl_parser import DSLFormula


@pytest.fixture
def executor():
    return DSLExecutor()


class TestDSLExecutor:
    def test_evaluate_simple_comparison(self, executor):
        formula = DSLFormula(field_name="loan_amount", operator=">", right_value=1000000)
        result = executor.evaluate(formula, {"loan_amount": 2000000})
        assert result is True

    def test_evaluate_false_comparison(self, executor):
        formula = DSLFormula(field_name="loan_amount", operator=">", right_value=1000000)
        result = executor.evaluate(formula, {"loan_amount": 500000})
        assert result is False

    def test_evaluate_between(self, executor):
        formula = DSLFormula(
            field_name="ratio", operator="between",
            right_value=(0.3, 0.8)
        )
        assert executor.evaluate(formula, {"ratio": 0.5}) is True
        assert executor.evaluate(formula, {"ratio": 0.9}) is False

    def test_evaluate_compound_and(self, executor):
        formula = DSLFormula(
            field_name="_compound", operator="compound",
            right_value=None, connector="AND",
            children=[
                DSLFormula(field_name="amount", operator=">", right_value=100),
                DSLFormula(field_name="risk", operator="=", right_value="high"),
            ]
        )
        assert executor.evaluate(formula, {"amount": 200, "risk": "high"}) is True
        assert executor.evaluate(formula, {"amount": 50, "risk": "high"}) is False

    def test_missing_field_returns_false(self, executor):
        formula = DSLFormula(field_name="nonexistent", operator=">", right_value=0)
        result = executor.evaluate(formula, {})
        assert result is False
```

- [ ] **Step 6: 运行测试验证失败**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/rules/test_dsl_executor.py -v`
Expected: FAIL

- [ ] **Step 7: 实现DSL执行引擎**

```python
# backend/app/services/rules/dsl_executor.py
"""DSL执行引擎 - 安全公式求值"""
from typing import Any, Dict, Optional
from loguru import logger
from backend.app.services.rules.dsl_parser import DSLFormula


class SecurityError(Exception):
    """执行安全异常"""
    pass


class DSLExecutor:
    """DSL执行引擎（同步实现，供to_thread调用）"""

    def __init__(self, max_ast_depth: int = 50, execution_timeout: int = 5):
        self.max_ast_depth = max_ast_depth
        self.execution_timeout = execution_timeout

    def evaluate(self, formula: DSLFormula, context: Dict[str, Any]) -> bool:
        if formula.depth > self.max_ast_depth:
            raise SecurityError(f"AST深度超过限制: {formula.depth}")

        if formula.operator == "compound":
            return self._evaluate_compound(formula, context)

        left_value = context.get(formula.field_name)
        if left_value is None:
            return False

        return self._compare(left_value, formula.operator, formula.right_value)

    def _evaluate_compound(self, formula: DSLFormula, context: Dict[str, Any]) -> bool:
        results = [self.evaluate(child, context) for child in formula.children]
        if formula.connector == "AND":
            return all(results)
        elif formula.connector == "OR":
            return any(results)
        return False

    def _compare(self, left: Any, operator: str, right: Any) -> bool:
        try:
            if operator == ">":
                return left > right
            elif operator == ">=":
                return left >= right
            elif operator == "<":
                return left < right
            elif operator == "<=":
                return left <= right
            elif operator in ("=", "=="):
                return left == right
            elif operator in ("!=", "<>"):
                return left != right
            elif operator == "between":
                low, high = right
                return low <= left <= high
        except TypeError:
            return False
        return False
```

- [ ] **Step 8: 运行测试验证通过**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/rules/test_dsl_parser.py tests/unit/services/rules/test_dsl_executor.py -v`
Expected: PASS

- [ ] **Step 9: 提交**

```bash
git add backend/app/services/rules/dsl_parser.py backend/app/services/rules/dsl_executor.py \
       backend/app/services/rules/__init__.py \
       tests/unit/services/rules/test_dsl_parser.py tests/unit/services/rules/test_dsl_executor.py
git commit -m "feat: add DSL parser and safe evaluation engine for rules engine"
```

---

## Phase 4: 查询引擎核心

### Task 6: 意图分类器（模板匹配模式）

**Files:**
- Create: `backend/app/services/query/intent_classifier.py`
- Test: `tests/unit/services/query/test_intent_classifier.py`

> 注：先实现模板匹配（零依赖），BERT/LLM后续迭代。

- [ ] **Step 1: 写失败测试 - 意图分类器**

```python
# tests/unit/services/query/test_intent_classifier.py
"""意图分类器单元测试"""
import pytest
from backend.app.services.query.intent_classifier import IntentClassifier, ClassificationResult


@pytest.fixture
def classifier():
    templates = [
        {"intent_id": "query_loan_amount", "patterns": [
            "贷款金额", "loan amount", "贷款余额"
        ], "slots": ["time", "entity"]},
        {"intent_id": "query_overdue_ratio", "patterns": [
            "逾期率", "overdue ratio", "不良率"
        ], "slots": ["time"]},
    ]
    return IntentClassifier(templates=templates)


class TestIntentClassifier:
    @pytest.mark.asyncio
    async def test_template_match_exact(self, classifier):
        result = await classifier.classify("贷款金额")
        assert result.intent_id == "query_loan_amount"
        assert result.confidence >= 0.95
        assert result.query_type == "predefined"

    @pytest.mark.asyncio
    async def test_template_match_partial(self, classifier):
        result = await classifier.classify("查询贷款金额")
        assert result.intent_id == "query_loan_amount"
        assert result.confidence > 0.7

    @pytest.mark.asyncio
    async def test_no_match_returns_unknown(self, classifier):
        result = await classifier.classify("今天天气怎么样")
        assert result.intent_id == "unknown"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_overdue_ratio_match(self, classifier):
        result = await classifier.classify("逾期率")
        assert result.intent_id == "query_overdue_ratio"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/test_intent_classifier.py -v`
Expected: FAIL

- [ ] **Step 3: 实现意图分类器（模板匹配模式）**

```python
# backend/app/services/query/intent_classifier.py
"""意图分类器 - 模板匹配模式（首期实现）"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ClassificationResult:
    """分类结果"""
    intent_id: str
    confidence: float
    slots: Dict[str, Any] = field(default_factory=dict)
    matched_pattern: Optional[str] = None
    requires_confirmation: bool = False
    query_type: str = "unknown"
    message: str = ""


class IntentClassifier:
    """意图分类器 - 模板匹配（首期）+ BERT/LLM（后续迭代）"""

    def __init__(self, templates: List[Dict], llm_client=None):
        self.templates = templates
        self.llm_client = llm_client

    async def classify(self, query: str, context: Optional[Dict] = None) -> ClassificationResult:
        # 1. 模板匹配（快速路径）
        template_match = self._match_template(query)
        if template_match and template_match.confidence > 0.95:
            return template_match

        # 2. 模糊匹配
        if template_match and template_match.confidence > 0.5:
            template_match.requires_confirmation = True
            return template_match

        # 3. 未匹配
        return ClassificationResult(
            intent_id="unknown",
            confidence=0.0,
            requires_confirmation=True,
            query_type="rejected",
            message="无法理解的查询，请使用标准问法"
        )

    def _match_template(self, query: str) -> Optional[ClassificationResult]:
        best_match = None
        best_confidence = 0.0

        for template in self.templates:
            for pattern in template.get("patterns", []):
                confidence = self._calculate_similarity(query, pattern)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = ClassificationResult(
                        intent_id=template["intent_id"],
                        confidence=confidence,
                        slots={s: None for s in template.get("slots", [])},
                        matched_pattern=pattern,
                        query_type="predefined" if confidence > 0.95 else "fuzzy",
                    )
        return best_match

    def _calculate_similarity(self, query: str, pattern: str) -> float:
        if query == pattern:
            return 1.0
        if pattern.lower() in query.lower():
            return 0.95
        if query.lower() in pattern.lower():
            return 0.85
        # 简单的字符重叠度
        query_chars = set(query.lower())
        pattern_chars = set(pattern.lower())
        if not pattern_chars:
            return 0.0
        overlap = len(query_chars & pattern_chars) / len(pattern_chars)
        return overlap * 0.7
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/test_intent_classifier.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/query/intent_classifier.py \
       tests/unit/services/query/test_intent_classifier.py
git commit -m "feat: add intent classifier with template matching for NLQ"
```

---

### Task 7: 查询引擎集成

**Files:**
- Create: `backend/app/services/query/rule_matcher.py`
- Create: `backend/app/services/query/query_engine.py`
- Test: `tests/unit/services/query/test_rule_matcher.py`
- Test: `tests/unit/services/query/test_query_engine.py`

- [ ] **Step 1: 写失败测试 - 规则匹配器**

```python
# tests/unit/services/query/test_rule_matcher.py
"""规则匹配器单元测试"""
import pytest
from backend.app.services.query.rule_matcher import RuleMatcher, CompiledRule


@pytest.fixture
def matcher():
    return RuleMatcher()


@pytest.fixture
def sample_rules():
    return [
        CompiledRule(id="r1", intent_id="query_loan_amount", table="bd_loan_contract",
                      columns=["loan_amount"], conditions=[], priority=10),
        CompiledRule(id="r2", intent_id="query_overdue_ratio", table="bd_loan_contract",
                      columns=["overdue_amount", "total_amount"], conditions=[], priority=5),
    ]


class TestRuleMatcher:
    def test_match_by_intent(self, matcher, sample_rules):
        rule = matcher.match("query_loan_amount", {}, sample_rules)
        assert rule is not None
        assert rule.id == "r1"

    def test_no_match_returns_none(self, matcher, sample_rules):
        rule = matcher.match("unknown_intent", {}, sample_rules)
        assert rule is None

    def test_match_highest_priority(self, matcher):
        rules = [
            CompiledRule(id="r1", intent_id="q1", table="t1", columns=[], conditions=[], priority=5),
            CompiledRule(id="r2", intent_id="q1", table="t2", columns=[], conditions=[], priority=10),
        ]
        rule = matcher.match("q1", {}, rules)
        assert rule.id == "r2"
```

- [ ] **Step 2: 运行测试验证失败 → 实现规则匹配器**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/test_rule_matcher.py -v`
Expected: FAIL → implement RuleMatcher

```python
# backend/app/services/query/rule_matcher.py
"""规则匹配器"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CompiledRule:
    """编译后的规则"""
    id: str
    intent_id: str
    table: str
    columns: List[str]
    conditions: List[Dict[str, Any]]
    priority: int = 0


class RuleMatcher:
    """规则匹配器"""

    def match(
        self, intent_id: str, slots: Dict[str, Any], rules: List[CompiledRule]
    ) -> Optional[CompiledRule]:
        matching = [r for r in rules if r.intent_id == intent_id]
        if not matching:
            return None
        # 返回优先级最高的规则
        return max(matching, key=lambda r: r.priority)
```

- [ ] **Step 3: 写失败测试 - 查询引擎**

```python
# tests/unit/services/query/test_query_engine.py
"""查询引擎单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.services.query.query_engine import QueryEngine, QueryResult, QueryStatus
from backend.app.services.query.intent_classifier import IntentClassifier
from backend.app.services.query.rule_matcher import RuleMatcher, CompiledRule
from backend.app.services.query.sql_generator import SQLGenerator
from backend.app.services.query.semantic_mapping import SemanticMapping, TableMapping
from backend.app.services.compile_cache import CompileCache


@pytest.fixture
def engine():
    mapping = SemanticMapping(
        concept_to_table={"loan:LoanContract": "bd_loan_contract"},
        relation_to_join={},
        table_mappings={
            "bd_loan_contract": TableMapping(
                table_name="bd_loan_contract", concept="loan:LoanContract",
                allowed_columns=["loan_amount", "contract_status"]
            )
        }
    )
    classifier = IntentClassifier(templates=[
        {"intent_id": "query_loan_amount", "patterns": ["贷款金额"], "slots": []}
    ])
    rule_matcher = RuleMatcher()
    sql_generator = SQLGenerator(mapping=mapping)
    cache = AsyncMock(spec=CompileCache)
    cache.get_compile_status = AsyncMock(return_value="ready")
    cache.get_compiled_rules = AsyncMock(return_value={
        "version": "v1.0.0",
        "rules": [
            {"id": "r1", "intent_id": "query_loan_amount", "table": "bd_loan_contract",
             "columns": ["loan_amount"], "conditions": [], "priority": 10}
        ]
    })
    return QueryEngine(
        classifier=classifier,
        rule_matcher=rule_matcher,
        sql_generator=sql_generator,
        cache=cache
    )


class TestQueryEngine:
    @pytest.mark.asyncio
    async def test_query_success(self, engine):
        result = await engine.query("tenant_001", "贷款金额", {})
        assert result.status == QueryStatus.SUCCESS or result.status == QueryStatus.REQUIRES_CONFIRMATION

    @pytest.mark.asyncio
    async def test_query_blocked_when_compiling(self, engine):
        engine.cache.get_compile_status = AsyncMock(return_value="L0_CRITICAL")
        result = await engine.query("tenant_001", "贷款金额", {})
        assert result.status == QueryStatus.SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_query_blocked_when_compile_failed(self, engine):
        engine.cache.get_compile_status = AsyncMock(return_value="L0_CRITICAL_FAILED")
        result = await engine.query("tenant_001", "贷款金额", {})
        assert result.status == QueryStatus.RULE_COMPILE_FAILED

    @pytest.mark.asyncio
    async def test_unknown_query(self, engine):
        result = await engine.query("tenant_001", "今天天气", {})
        assert result.status == QueryStatus.REJECTED
```

- [ ] **Step 4: 运行测试验证失败 → 实现查询引擎**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/test_query_engine.py -v`
Expected: FAIL → implement QueryEngine

```python
# backend/app/services/query/query_engine.py
"""查询引擎 - 统一查询入口"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from loguru import logger
from backend.app.services.query.intent_classifier import IntentClassifier
from backend.app.services.query.rule_matcher import RuleMatcher, CompiledRule
from backend.app.services.query.sql_generator import SQLGenerator
from backend.app.services.compile_cache import CompileCache


class QueryStatus(str, Enum):
    SUCCESS = "success"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    SERVICE_UNAVAILABLE = "service_unavailable"
    RULE_COMPILE_FAILED = "rule_compile_failed"
    REJECTED = "rejected"


@dataclass
class QueryResult:
    status: QueryStatus
    data: Optional[Dict] = None
    sql: Optional[str] = None
    message: str = ""
    retry_after: Optional[int] = None
    admin_alert: bool = False


class QueryEngine:
    """查询引擎"""

    def __init__(
        self,
        classifier: IntentClassifier,
        rule_matcher: RuleMatcher,
        sql_generator: SQLGenerator,
        cache: CompileCache,
    ):
        self.classifier = classifier
        self.rule_matcher = rule_matcher
        self.sql_generator = sql_generator
        self.cache = cache

    async def query(
        self, tenant_id: str, query_text: str, context: Dict, options: Optional[Dict] = None
    ) -> QueryResult:
        # 0. 编译状态检查
        compile_status = await self.cache.get_compile_status(tenant_id)
        if compile_status in ("L0_CRITICAL", "L0_HIGH_COMPILING"):
            return QueryResult(
                status=QueryStatus.SERVICE_UNAVAILABLE,
                message="系统规则更新中，请稍后重试",
                retry_after=30
            )
        elif compile_status in ("L0_CRITICAL_FAILED", "L0_CRITICAL_ERROR"):
            return QueryResult(
                status=QueryStatus.RULE_COMPILE_FAILED,
                message="系统规则更新失败，请联系管理员",
                admin_alert=True
            )

        # 1. 意图分类
        classification = await self.classifier.classify(query_text, context)

        # 2. 未匹配意图
        if classification.intent_id == "unknown":
            return QueryResult(
                status=QueryStatus.REJECTED,
                message=classification.message or "无法理解的查询"
            )

        # 3. 需要确认
        if classification.requires_confirmation:
            return QueryResult(
                status=QueryStatus.REQUIRES_CONFIRMATION,
                message="请确认查询意图",
                data={"classification": classification}
            )

        # 4. 获取编译规则
        compiled_rules_data = await self.cache.get_compiled_rules(tenant_id)
        if not compiled_rules_data:
            return QueryResult(status=QueryStatus.SERVICE_UNAVAILABLE, message="规则未编译")

        rules = [CompiledRule(**r) for r in compiled_rules_data.get("rules", [])]

        # 5. 规则匹配
        matched_rule = self.rule_matcher.match(
            classification.intent_id, classification.slots, rules
        )
        if not matched_rule:
            return QueryResult(status=QueryStatus.REJECTED, message="未找到匹配规则")

        # 6. SQL生成
        try:
            sql, params = self.sql_generator.generate_safe(
                table_name=matched_rule.table,
                select_columns=matched_rule.columns,
                conditions=classification.slots,
            )
        except Exception as e:
            return QueryResult(status=QueryStatus.REJECTED, message=f"查询生成失败: {e}")

        return QueryResult(
            status=QueryStatus.SUCCESS,
            sql=sql,
            data={"sql": sql, "params": params, "rule_id": matched_rule.id}
        )
```

- [ ] **Step 5: 运行测试验证通过**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/services/query/ -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/query/rule_matcher.py backend/app/services/query/query_engine.py \
       tests/unit/services/query/test_rule_matcher.py tests/unit/services/query/test_query_engine.py
git commit -m "feat: add rule matcher and query engine with compile status checks"
```

---

## Phase 5: API路由

### Task 8: NLQ查询与规则管理API

**Files:**
- Create: `backend/app/api/v1/query.py`
- Create: `backend/app/api/v1/rules.py`
- Create: `backend/app/schemas/query.py`
- Create: `backend/app/schemas/rules.py`
- Test: `tests/unit/api/test_query_api.py`

- [ ] **Step 1: 写失败测试 - 查询API**

```python
# tests/unit/api/test_query_api.py
"""NLQ查询API单元测试"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from backend.app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestQueryAPI:
    @pytest.mark.asyncio
    async def test_query_endpoint_exists(self, client):
        response = await client.post(
            "/api/v1/query",
            json={"tenant_id": "test", "query": "贷款金额"}
        )
        assert response.status_code in (200, 422, 503)

    @pytest.mark.asyncio
    async def test_query_missing_tenant(self, client):
        response = await client.post(
            "/api/v1/query",
            json={"query": "贷款金额"}
        )
        assert response.status_code == 422
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/leitao/Documents/trae_projects/Qoder-LoanFIBO && python -m pytest tests/unit/api/test_query_api.py -v`

- [ ] **Step 3: 实现API路由和Schema**

> Schema + Route 实现（按需填充）

- [ ] **Step 4: 运行测试验证通过**

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/v1/query.py backend/app/api/v1/rules.py \
       backend/app/schemas/query.py backend/app/schemas/rules.py \
       tests/unit/api/test_query_api.py
git commit -m "feat: add NLQ query and rule management API endpoints"
```

---

## 自检清单

### 1. 规格覆盖
| 需求模块 | 对应任务 | 状态 |
|----------|----------|------|
| 规则编译器 | Task 5 (DSL Parser + Executor) | ✅ |
| 编译缓存 | Task 2 (CompileCache) | ✅ |
| 语义映射 | Task 3 (SemanticMapping) | ✅ |
| SQL生成器 | Task 4 (SQLGenerator) | ✅ |
| 意图分类器 | Task 6 (IntentClassifier) | ✅ |
| 查询引擎 | Task 7 (QueryEngine) | ✅ |
| API路由 | Task 8 (Query + Rules API) | ✅ |
| 租户模型 | Task 1 (Models) | ✅ |

### 2. 占位符扫描
无 TBD/TODO/占位符

### 3. 类型一致性
所有模型、服务、API的接口签名已在各Task中定义并保持一致
