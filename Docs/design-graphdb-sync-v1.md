# GraphDB 同步功能设计文档 v1.0

> 版本：v1.0  
> 日期：2026-04-20  
> 状态：设计中

---

## 1. 设计概述

### 1.1 设计目标

基于需求文档 [requirements-graphdb-sync-v1.md](requirements-graphdb-sync-v1.md)，完成 GraphDB 同步功能的详细技术设计。

### 1.2 设计范围

| 模块 | 设计内容 |
|------|---------|
| 架构设计 | 系统架构、数据流、模块划分 |
| 数据库设计 | 表结构、索引、约束、关系 |
| API设计 | RESTful接口、请求/响应格式 |
| 服务设计 | 核心服务类、方法、依赖关系 |
| 前端设计 | 组件结构、状态管理、路由 |
| 算法设计 | LLM外键推断、RDF生成、同步策略 |
| 安全设计 | 权限控制、数据隔离 |
| 性能设计 | 并发控制、缓存策略、批量处理 |

---

## 2. 架构设计

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              前端层 (Vue 3)                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ 版本管理页   │  │ GraphDB实例 │  │  同步任务页  │  │  图谱浏览页      │ │
│  │  /versions  │  │ /instances  │  │   /sync     │  │   /explore      │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         └─────────────────┴─────────────────┴─────────────────┘          │
│                                    │                                     │
│                         API Client (Axios)                               │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │ HTTP/REST
┌────────────────────────────────────┼────────────────────────────────────┐
│                           后端层 (FastAPI)                               │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                         API Routes                                 │  │
│  │  /api/v1/versions  /api/v1/graphdb/*  /api/v1/sync/*  /api/v1/entities │ │
│  └─────────────────────────────────┼─────────────────────────────────┘  │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                        Service Layer                               │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐  │  │
│  │  │VersionService│ │GraphDBService│ │  SyncService │ │ RDFGen   │  │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────┘  │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │  │
│  │  │ForeignKey    │ │GraphDBClient │ │PipelineState │               │  │
│  │  │InferenceSvc  │ │   (REST)     │ │   Manager    │               │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌─────────────────────────────────┼─────────────────────────────────┐  │
│  │                        Data Access Layer                           │  │
│  │              SQLAlchemy Async + PostgreSQL                         │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────┐
│                           外部依赖层                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐     │
│  │  PostgreSQL  │  │  GraphDB     │  │  LLM API     │  │  Redis   │     │
│  │  (Mapping    │  │  (RDF Store) │  │ (DashScope)  │  │ (Cache)  │     │
│  │   Data)      │  │              │  │              │  │          │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流设计

#### 2.2.1 发布版本创建流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  用户操作    │────▶│  查询审核通过 │────▶│  创建版本快照 │────▶│  保存到      │
│  创建版本    │     │  的映射结果  │     │  (深拷贝)    │     │ mapping_version│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ▼
                                                            ┌─────────────┐
                                                            │  异步触发    │
                                                            │ LLM外键推断  │
                                                            │ (如需要)     │
                                                            └─────────────┘
```

#### 2.2.2 同步任务执行流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  创建同步    │────▶│  加载版本    │────▶│  RDF三元组  │────▶│  GraphDB    │
│  任务        │     │  快照数据    │     │  生成       │     │  REST导入   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
     │                                           │                  │
     ▼                                           ▼                  ▼
┌─────────────┐                           ┌─────────────┐     ┌─────────────┐
│  更新任务    │                           │  批量生成   │     │  命名图管理  │
│  状态/进度   │◀──────────────────────────│  Turtle文件 │     │  (版本隔离)  │
└─────────────┘                           └─────────────┘     └─────────────┘
```

#### 2.2.3 图谱浏览钻取流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  选择        │────▶│  SPARQL     │────▶│  解析结果   │────▶│  力导向图   │
│  Repository │     │  查询类/实例 │     │  构建图数据  │     │  布局渲染   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                              ┌────────────────────────────────────┘
                              ▼
                       ┌─────────────┐
                       │  用户点击    │
                       │  节点/边    │
                       └──────┬──────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │ 查询详情 │    │ 钻取子图 │    │ 导航对端 │
        │ (右侧面板)│    │ (重新渲染)│    │ (高亮跳转)│
        └─────────┘    └─────────┘    └─────────┘
```

---

## 3. 数据库设计

### 3.1 ER图

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  mapping_job    │       │ mapping_version │       │mapping_version_ │
│  (已有)         │◀──────│  (新增)         │──────▶│    item         │
│                 │  1:N  │                 │  1:N  │  (新增)         │
└─────────────────┘       └─────────────────┘       └─────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  table_mapping  │◀──────│ table_foreign_  │       │ graphdb_instance│
│  (已有)         │  1:N  │    key          │       │  (新增)         │
│                 │       │  (新增)         │       │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
         │                                                    │
         │ N:1                                                │ 1:N
         ▼                                                    ▼
┌─────────────────┐                               ┌─────────────────┐
│database_business│                               │   sync_task     │
│    _domain      │                               │  (新增)         │
│  (新增)         │                               │                 │
└─────────────────┘                               └─────────────────┘
```

### 3.2 表结构设计

#### 3.2.1 mapping_version（发布版本）

```sql
CREATE TABLE mapping_version (
    id              BIGSERIAL PRIMARY KEY,
    version_name    VARCHAR(128) NOT NULL UNIQUE,
    description     TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',  -- draft/published/synced
    source_job_id   BIGINT REFERENCES mapping_job(id),
    total_mappings  INTEGER NOT NULL DEFAULT 0,
    fk_inference_status VARCHAR(32) DEFAULT 'pending',  -- pending/running/completed
    created_by      VARCHAR(128),
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

-- 索引
CREATE INDEX idx_mapping_version_status ON mapping_version(status);
CREATE INDEX idx_mapping_version_job ON mapping_version(source_job_id);
```

#### 3.2.2 mapping_version_item（版本映射快照）

```sql
CREATE TABLE mapping_version_item (
    id              BIGSERIAL PRIMARY KEY,
    version_id      BIGINT NOT NULL REFERENCES mapping_version(id) ON DELETE CASCADE,
    database_name   VARCHAR(128) NOT NULL,
    table_name      VARCHAR(256) NOT NULL,
    fibo_class_uri  VARCHAR(512),
    confidence_level VARCHAR(16),
    mapping_reason  TEXT,
    -- 冻结的字段映射快照
    field_mappings  JSONB NOT NULL DEFAULT '[]',
    -- 示例: [
    --   {
    --     "field_name": "loan_id",
    --     "field_type": "varchar(36)",
    --     "fibo_property_uri": "fibo-loan:hasLoanIdentifier",
    --     "confidence_level": "HIGH",
    --     "mapping_reason": "..."
    --   }
    -- ]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (version_id, database_name, table_name)
);

-- 索引
CREATE INDEX idx_version_item_version ON mapping_version_item(version_id);
CREATE INDEX idx_version_item_db_table ON mapping_version_item(database_name, table_name);
```

#### 3.2.3 graphdb_instance（GraphDB实例）

```sql
CREATE TABLE graphdb_instance (
    id              BIGSERIAL PRIMARY KEY,
    instance_name   VARCHAR(128) NOT NULL,
    repo_id         VARCHAR(128) NOT NULL,
    graphdb_url     VARCHAR(512) NOT NULL DEFAULT 'http://localhost:7200',
    ruleset         VARCHAR(64) NOT NULL DEFAULT 'owl-horst-optimized',
    business_domain VARCHAR(128),  -- 信贷/资金/风控
    named_graph_prefix VARCHAR(256) DEFAULT 'urn:loanfibo',
    status          VARCHAR(32) NOT NULL DEFAULT 'active',  -- active/inactive/error
    last_health_check TIMESTAMPTZ,
    health_status   VARCHAR(32),  -- healthy/unhealthy
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    
    UNIQUE (graphdb_url, repo_id)
);

-- 索引
CREATE INDEX idx_graphdb_instance_status ON graphdb_instance(status);
CREATE INDEX idx_graphdb_instance_domain ON graphdb_instance(business_domain);
```

#### 3.2.4 sync_task（同步任务）

```sql
CREATE TABLE sync_task (
    id              BIGSERIAL PRIMARY KEY,
    version_id      BIGINT NOT NULL REFERENCES mapping_version(id),
    instance_id     BIGINT NOT NULL REFERENCES graphdb_instance(id),
    sync_mode       VARCHAR(32) NOT NULL DEFAULT 'upsert',  -- upsert/replace
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',  -- pending/running/completed/failed/cancelled
    
    -- 进度统计
    total_triples   INTEGER NOT NULL DEFAULT 0,
    synced_triples  INTEGER NOT NULL DEFAULT 0,
    generated_files INTEGER DEFAULT 0,
    
    -- 错误信息
    error_message   TEXT,
    error_details   JSONB,  -- 详细的错误堆栈/上下文
    
    -- 时间戳
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

-- 索引
CREATE INDEX idx_sync_task_status ON sync_task(status);
CREATE INDEX idx_sync_task_version ON sync_task(version_id);
CREATE INDEX idx_sync_task_instance ON sync_task(instance_id);
```

#### 3.2.5 table_foreign_key（外键关系）

```sql
CREATE TABLE table_foreign_key (
    id              BIGSERIAL PRIMARY KEY,
    table_mapping_id BIGINT NOT NULL REFERENCES table_mapping(id),
    
    -- 源字段
    source_field    VARCHAR(256) NOT NULL,
    
    -- 目标位置
    target_database VARCHAR(128) NOT NULL,
    target_table    VARCHAR(256) NOT NULL,
    target_field    VARCHAR(256) NOT NULL DEFAULT 'id',
    
    -- LLM推断信息
    confidence      VARCHAR(16) NOT NULL,  -- HIGH/MEDIUM/LOW
    infer_reason    TEXT,                   -- LLM推断理由
    
    -- 审核状态
    review_status   VARCHAR(32) DEFAULT 'pending',  -- pending/approved/rejected
    reviewed_by     VARCHAR(128),
    reviewed_at     TIMESTAMPTZ,
    review_comment  TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    
    UNIQUE (table_mapping_id, source_field)
);

-- 索引
CREATE INDEX idx_foreign_key_mapping ON table_foreign_key(table_mapping_id);
CREATE INDEX idx_foreign_key_review ON table_foreign_key(review_status);
CREATE INDEX idx_foreign_key_target ON table_foreign_key(target_database, target_table);
```

#### 3.2.6 database_business_domain（数据库业务域映射）

```sql
CREATE TABLE database_business_domain (
    id              BIGSERIAL PRIMARY KEY,
    database_name   VARCHAR(128) NOT NULL UNIQUE,
    business_domain VARCHAR(128) NOT NULL,  -- 信贷: credit, 资金: treasury, 风控: risk
    description     TEXT,
    
    -- 相邻业务域（用于外键推断扩展）
    adjacent_domains VARCHAR(128)[],  -- ['credit', 'risk']
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

-- 索引
CREATE INDEX idx_db_domain_domain ON database_business_domain(business_domain);
```

---

## 4. API详细设计

### 4.1 版本管理 API

#### 4.1.1 创建发布版本

```http
POST /api/v1/versions
Content-Type: application/json

{
  "version_name": "v1.0-credit-loan",
  "description": "信贷域贷款模块首次发布",
  "source_job_id": 123,
  "scope_databases": ["iuap_fi_loan", "iuap_fi_credit"]
}
```

**响应（成功）**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "version_name": "v1.0-credit-loan",
    "description": "信贷域贷款模块首次发布",
    "status": "draft",
    "source_job_id": 123,
    "total_mappings": 156,
    "fk_inference_status": "pending",
    "created_by": "admin",
    "created_at": "2026-04-20T10:00:00Z",
    "updated_at": "2026-04-20T10:00:00Z"
  }
}
```

**响应（错误）**：
```json
{
  "code": 400001,
  "message": "版本名称已存在",
  "data": null
}
```

#### 4.1.2 获取版本列表

```http
GET /api/v1/versions?page=1&page_size=20&status=published&keyword=credit
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "version_name": "v1.0-credit-loan",
        "description": "信贷域贷款模块首次发布",
        "status": "published",
        "total_mappings": 156,
        "fk_inference_status": "completed",
        "created_by": "admin",
        "published_at": "2026-04-20T12:00:00Z",
        "created_at": "2026-04-20T10:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

#### 4.1.3 获取版本详情

```http
GET /api/v1/versions/{id}
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "version_name": "v1.0-credit-loan",
    "status": "published",
    "total_mappings": 156,
    "fk_inference_status": "completed",
    "fk_inference_progress": {
      "total_tables": 45,
      "completed_tables": 45,
      "pending_review": 12
    },
    "scope_databases": ["iuap_fi_loan", "iuap_fi_credit"],
    "created_at": "2026-04-20T10:00:00Z",
    "published_at": "2026-04-20T12:00:00Z"
  }
}
```

#### 4.1.4 发布版本

```http
POST /api/v1/versions/{id}/publish
Content-Type: application/json

{
  "trigger_fk_inference": true
}
```

**说明**：触发外键推断任务，完成后版本状态变为 published

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "status": "publishing",
    "fk_inference_task_id": "task-uuid-123"
  }
}
```

#### 4.1.5 删除版本

```http
DELETE /api/v1/versions/{id}
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

### 4.2 GraphDB实例管理 API

#### 4.2.1 创建实例

```http
POST /api/v1/graphdb/instances
Content-Type: application/json

{
  "instance_name": "信贷生产环境",
  "repo_id": "loanfibo-credit-prod",
  "graphdb_url": "http://localhost:7200",
  "ruleset": "owl-horst-optimized",
  "business_domain": "credit",
  "named_graph_prefix": "urn:loanfibo:credit"
}
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "instance_name": "信贷生产环境",
    "repo_id": "loanfibo-credit-prod",
    "graphdb_url": "http://localhost:7200",
    "status": "active",
    "health_status": "unknown",
    "created_at": "2026-04-20T10:00:00Z"
  }
}
```

#### 4.2.2 获取实例列表

```http
GET /api/v1/graphdb/instances?business_domain=credit
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "instance_name": "信贷生产环境",
        "repo_id": "loanfibo-credit-prod",
        "graphdb_url": "http://localhost:7200",
        "business_domain": "credit",
        "status": "active",
        "health_status": "healthy",
        "last_health_check": "2026-04-20T11:00:00Z",
        "statistics": {
          "total_triples": 1250000,
          "total_classes": 45,
          "total_instances": 15600
        }
      }
    ],
    "total": 1
  }
}
```

#### 4.2.3 健康检查

```http
POST /api/v1/graphdb/instances/{id}/health-check
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "health_status": "healthy",
    "response_time_ms": 45,
    "repository_info": {
      "id": "loanfibo-credit-prod",
      "title": "LoanFIBO Credit Production",
      "readable": true,
      "writable": true
    }
  }
}
```

#### 4.2.4 删除实例

```http
DELETE /api/v1/graphdb/instances/{id}
```

### 4.3 同步任务 API

#### 4.3.1 创建同步任务

```http
POST /api/v1/sync/tasks
Content-Type: application/json

{
  "version_id": 1,
  "instance_id": 1,
  "sync_mode": "upsert",
  "named_graph_suffix": "v1.0"
}
```

**参数说明**：
- `sync_mode`: `upsert`（增量更新）或 `replace`（全量替换）
- `named_graph_suffix`: 命名图后缀，完整URI为 `{prefix}:{suffix}`

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "version_id": 1,
    "instance_id": 1,
    "sync_mode": "upsert",
    "status": "pending",
    "total_triples": 0,
    "synced_triples": 0,
    "created_at": "2026-04-20T10:00:00Z"
  }
}
```

#### 4.3.2 获取任务列表

```http
GET /api/v1/sync/tasks?page=1&page_size=20&status=running
```

#### 4.3.3 获取任务详情

```http
GET /api/v1/sync/tasks/{id}
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "version_id": 1,
    "version_name": "v1.0-credit-loan",
    "instance_id": 1,
    "instance_name": "信贷生产环境",
    "sync_mode": "upsert",
    "status": "running",
    "progress": {
      "total_triples": 50000,
      "synced_triples": 25000,
      "percentage": 50,
      "current_file": "batch_3.ttl",
      "estimated_remaining_seconds": 120
    },
    "logs": [
      {
        "timestamp": "2026-04-20T10:05:00Z",
        "level": "INFO",
        "message": "开始生成RDF三元组..."
      },
      {
        "timestamp": "2026-04-20T10:10:00Z",
        "level": "INFO",
        "message": "已生成50000个三元组，开始导入GraphDB..."
      }
    ],
    "created_at": "2026-04-20T10:00:00Z",
    "started_at": "2026-04-20T10:05:00Z"
  }
}
```

#### 4.3.4 取消任务

```http
POST /api/v1/sync/tasks/{id}/cancel
```

### 4.4 外键推断 API

#### 4.4.1 获取外键推断列表

```http
GET /api/v1/foreign-keys?table_mapping_id=123&review_status=pending
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "table_mapping_id": 123,
        "source_field": "customer_id",
        "target_database": "iuap_fi_cust",
        "target_table": "bd_customer",
        "target_field": "id",
        "confidence": "HIGH",
        "infer_reason": "字段名customer_id与目标表bd_customer语义匹配，且类型一致(varchar)",
        "review_status": "pending",
        "created_at": "2026-04-20T10:00:00Z"
      }
    ],
    "total": 12,
    "pending_count": 8,
    "approved_count": 3,
    "rejected_count": 1
  }
}
```

#### 4.4.2 审核外键推断

```http
POST /api/v1/foreign-keys/{id}/review
Content-Type: application/json

{
  "status": "approved",
  "comment": "确认customer_id关联客户主表"
}
```

#### 4.4.3 批量审核

```http
POST /api/v1/foreign-keys/batch-review
Content-Type: application/json

{
  "ids": [1, 2, 3],
  "status": "approved"
}
```

### 4.5 图谱浏览 API

#### 4.5.1 获取类列表

```http
GET /api/v1/graph-explorer/classes?instance_id=1
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "uri": "https://spec.edmcouncil.org/fibo/ontology/LOAN/LoanContracts/LoanContract",
        "label": "贷款合同",
        "instance_count": 15600,
        "comment": "A contract between a lender and a borrower..."
      }
    ]
  }
}
```

#### 4.5.2 获取实例列表

```http
GET /api/v1/graph-explorer/instances?instance_id=1&class_uri=...&page=1&page_size=50
```

#### 4.5.3 获取实例详情（用于图渲染）

```http
GET /api/v1/graph-explorer/entities/{encoded_uri}?instance_id=1&depth=1
```

**响应**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "entity": {
      "uri": "src:iuap_fi_loan/bd_loan_contract#12345",
      "label": "贷款合同 #12345",
      "type": "fibo-loan:LoanContract",
      "properties": [
        {
          "predicate": "fibo-loan:hasLoanIdentifier",
          "object": "LOAN-2024-001",
          "object_type": "literal"
        }
      ]
    },
    "relations": {
      "outgoing": [
        {
          "predicate": "fibo-loan:isSecuredBy",
          "target": {
            "uri": "src:iuap_fi_loan/bd_collateral#67890",
            "label": "担保物 #67890",
            "type": "fibo-loan:Collateral"
          }
        }
      ],
      "incoming": []
    },
    "provenance": {
      "source_database": "iuap_fi_loan",
      "source_table": "bd_loan_contract",
      "mapping_version": "v1.0-credit-loan"
    }
  }
}
```

#### 4.5.4 执行SPARQL查询

```http
POST /api/v1/graph-explorer/sparql
Content-Type: application/json

{
  "instance_id": 1,
  "query": "SELECT ?s ?p ?o WHERE { ?s a <...> ; ?p ?o } LIMIT 100"
}
```

---

## 5. 服务设计

### 5.1 核心服务类图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Service Classes                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────┐                                                │
│  │  VersionService     │                                                │
│  ├─────────────────────┤                                                │
│  │ + create_version()  │                                                │
│  │ + publish_version() │◀──触发外键推断                                  │
│  │ + get_version()     │                                                │
│  │ + list_versions()   │                                                │
│  └──────────┬──────────┘                                                │
│             │                                                           │
│             ▼                                                           │
│  ┌─────────────────────┐       ┌─────────────────────┐                 │
│  │ ForeignKeyInference │       │   GraphDBService    │                 │
│  │     Service         │       ├─────────────────────┤                 │
│  ├─────────────────────┤       │ + create_instance() │                 │
│  │ + infer_foreign_keys│       │ + check_health()    │                 │
│  │  (_async)           │       │ + get_statistics()  │                 │
│  │ + review_foreign_key│       └──────────┬──────────┘                 │
│  │ + get_inference_    │                  │                            │
│  │    status()         │                  ▼                            │
│  └──────────┬──────────┘       ┌─────────────────────┐                 │
│             │                  │   GraphDBClient     │                 │
│             │                  │   (REST API封装)     │                 │
│             │                  ├─────────────────────┤                 │
│             │                  │ + upload_rdf()      │                 │
│             │                  │ + query_sparql()    │                 │
│             │                  │ + get_repository_   │                 │
│             │                  │   info()            │                 │
│             │                  └─────────────────────┘                 │
│             │                                                           │
│             ▼                                                           │
│  ┌─────────────────────┐       ┌─────────────────────┐                 │
│  │    SyncService      │◀─────▶│   RDFGenerator      │                 │
│  ├─────────────────────┤       ├─────────────────────┤                 │
│  │ + create_task()     │       │ + generate_triples()│                 │
│  │ + execute_sync()    │       │ + serialize_turtle()│                 │
│  │  (_async)           │       │ + build_named_graph_│                 │
│  │ + get_task_status() │       │    uri()            │                 │
│  │ + cancel_task()     │       └─────────────────────┘                 │
│  └─────────────────────┘                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 前端设计

### 6.1 组件结构

```
src/views/graphdb/
├── GraphDBLayout.vue           # 布局容器
├── VersionManagement/
│   ├── VersionList.vue         # 版本列表
│   ├── VersionCreateModal.vue  # 创建版本弹窗
│   └── VersionDetail.vue       # 版本详情
├── InstanceManagement/
│   ├── InstanceList.vue        # 实例列表
│   ├── InstanceForm.vue        # 实例表单
│   └── InstanceHealthCheck.vue # 健康检查
├── SyncTasks/
│   ├── TaskList.vue            # 任务列表
│   ├── TaskCreateModal.vue     # 创建任务弹窗
│   └── TaskProgress.vue        # 任务进度
└── GraphExplorer/
    ├── GraphCanvas.vue         # 图谱画布（核心）
    ├── NodeDetailPanel.vue     # 节点详情面板
    ├── EdgeDetailPopover.vue   # 边详情悬浮
    ├── BreadcrumbNav.vue       # 面包屑导航
    ├── SearchBox.vue           # 搜索框
    └── Toolbar.vue             # 工具栏（缩放/重置/展开）
```

### 6.2 状态管理 (Pinia)

```typescript
// stores/graphdb.ts
export const useGraphDBStore = defineStore('graphdb', {
  state: () => ({
    // 实例管理
    instances: [] as GraphDBInstance[],
    currentInstance: null as GraphDBInstance | null,
    
    // 版本管理
    versions: [] as MappingVersion[],
    currentVersion: null as MappingVersion | null,
    
    // 同步任务
    tasks: [] as SyncTask[],
    currentTask: null as SyncTask | null,
    
    // 图谱浏览
    graphData: null as GraphData | null,
    selectedNode: null as GraphNode | null,
    selectedEdge: null as GraphEdge | null,
    drillDownPath: [] as DrillDownLevel[],
    
    // 画布状态
    canvasZoom: 1,
    canvasCenter: { x: 0, y: 0 },
  }),
  
  actions: {
    // 版本管理
    async createVersion(payload: CreateVersionPayload) {...},
    async publishVersion(id: number) {...},
    
    // 图谱浏览
    async loadGraphData(params: GraphQueryParams) {...},
    async drillDown(nodeId: string) {...},
    async searchAndLocate(keyword: string) {...},
    
    // 画布操作
    zoomIn() {...},
    zoomOut() {...},
    resetView() {...},
  }
})
```

---

## 7. 算法设计

### 7.1 LLM外键推断算法

```python
async def infer_foreign_keys(
    table_mapping_id: int,
    business_domain: str,
    llm_client: LLMClient
) -> List[ForeignKeyInference]:
    """
    LLM外键推断主算法
    
    步骤：
    1. 获取当前表映射信息
    2. 获取同业务域候选目标表
    3. 构建LLM Prompt
    4. 调用LLM进行推断
    5. 解析并验证结果
    6. 保存到数据库
    """
    # 1. 获取源表信息
    source = await get_table_mapping(table_mapping_id)
    
    # 2. 获取候选目标表（同业务域）
    candidates = await get_candidate_tables(
        business_domain=business_domain,
        exclude_self=source.database_name
    )
    
    # 3. 构建Prompt
    prompt = build_fk_inference_prompt(
        source_table=source,
        candidate_tables=candidates
    )
    
    # 4. 调用LLM（带重试）
    response = await llm_client.chat_completion(
        messages=[
            {"role": "system", "content": FOREIGN_KEY_INFERENCE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_retries=3
    )
    
    # 5. 解析JSON结果
    inferences = parse_fk_inference_response(response.content)
    
    # 6. 验证目标表存在性
    validated = await validate_target_tables(inferences)
    
    # 7. 保存到数据库
    await save_foreign_key_inferences(table_mapping_id, validated)
    
    return validated

**外键推断批量策略说明**：
- 采用**单表推断**策略，每个表单独调用LLM
- 原因：避免Prompt过长（候选表可能很多），保证推断质量
- 并发控制：使用 Semaphore 限制同时推断的表数量（默认5个）
- 失败重试：单表失败不影响其他表，支持单独重试
```

### 7.2 命名图URI构建规则

```python
def build_named_graph_uri(
    prefix: str,
    version_name: str,
    database: str
) -> str:
    """
    构建命名图URI
    
    格式: {prefix}:{version_name}:{database}
    示例: urn:loanfibo:v1.0-credit-loan:iuap_fi_loan
    
    用途:
    - 实现版本隔离：不同版本的映射数据存储在不同命名图
    - 支持增量更新：按数据库粒度管理命名图
    - 便于清理：删除旧版本时直接删除整个命名图
    """
    return f"{prefix}:{version_name}:{database}"
```

### 7.3 RDF三元组生成算法

```python
def generate_entity_triples(
    version_item: MappingVersionItem,
    foreign_keys: List[TableForeignKey]
) -> List[Triple]:
    """
    生成实体的RDF三元组
    """
    triples = []
    entity_uri = build_entity_uri(
        version_item.database_name,
        version_item.table_name
    )
    
    # L1: 实体声明
    triples.append(Triple(
        subject=entity_uri,
        predicate="rdf:type",
        object=version_item.fibo_class_uri
    ))
    
    # L2: 属性映射
    for field in version_item.field_mappings:
        if field.fibo_property_uri:
            # 判断属性类型
            prop_type = get_property_type(field.fibo_property_uri)
            
            if prop_type == PropertyType.DATATYPE:
                # DatatypeProperty: 指向字段URI
                value_uri = build_field_uri(entity_uri, field.field_name)
                triples.append(Triple(entity_uri, field.fibo_property_uri, value_uri))
                
            elif prop_type == PropertyType.OBJECT:
                # ObjectProperty: 查找外键关系
                fk = find_foreign_key(foreign_keys, field.field_name)
                if fk and fk.review_status == 'approved':
                    target_uri = build_entity_uri(
                        fk.target_database,
                        fk.target_table
                    )
                    triples.append(Triple(entity_uri, field.fibo_property_uri, target_uri))
    
    # L3: 映射溯源
    triples.extend(build_provenance_triples(version_item, entity_uri))
    
    return triples
```

---

## 8. 安全设计

### 8.1 权限控制

| 功能 | 普通用户 | 管理员 |
|------|---------|--------|
| 查看版本 | ✅ | ✅ |
| 创建版本 | ✅ | ✅ |
| 发布版本 | ❌ | ✅ |
| 管理GraphDB实例 | ❌ | ✅ |
| 执行同步任务 | ❌ | ✅ |
| 审核外键推断 | ✅ | ✅ |
| 浏览图谱 | ✅ | ✅ |

### 8.2 数据隔离

- 版本数据：按创建者隔离，管理员可查看全部
- GraphDB实例：按业务域隔离，用户只能看到授权的业务域
- 同步任务：操作日志记录完整审计信息

---

## 9. 性能设计

### 9.1 并发控制

```python
# 外键推断并发控制（避免LLM限流）
fk_inference_semaphore = asyncio.Semaphore(5)

# 同步任务并发控制（避免GraphDB过载）
sync_task_semaphore = asyncio.Semaphore(2)
```

### 9.2 批量处理

| 场景 | 批量大小 | 说明 |
|------|---------|------|
| RDF生成 | 100条/批次 | 每100个实体生成一个Turtle文件 |
| GraphDB导入 | 10MB/批次 | 按文件大小分批上传 |
| 外键推断 | 单表 | 每个表单独推断，避免Prompt过长 |

### 9.3 缓存策略

```python
# Redis缓存键
GRAPHDB_HEALTH_STATUS = "graphdb:health:{instance_id}"
ONTOLOGY_CLASS_LABEL = "ontology:class:{class_uri}"
GRAPH_NODE_POSITION = "graph:position:{entity_uri}"
```

---

## 10. 错误码设计

### 10.1 错误码规范

错误码采用6位数字：`[模块][级别][序号]`

| 位 | 含义 | 取值 |
|----|------|------|
| 第1-2位 | 模块 | 40=版本, 41=GraphDB实例, 42=同步任务, 43=外键推断, 44=图谱浏览 |
| 第3位 | 级别 | 0=系统, 1=参数, 2=业务, 3=权限, 4=外部依赖 |
| 第4-6位 | 序号 | 001-999 |

### 10.2 错误码列表

#### 版本管理 (40)

| 错误码 | 含义 | HTTP状态 |
|--------|------|----------|
| 401001 | 版本名称不能为空 | 400 |
| 401002 | 版本名称已存在 | 400 |
| 401003 | 源Job不存在 | 400 |
| 402001 | 版本状态不允许发布（非draft） | 400 |
| 402002 | 版本已发布，不能删除 | 400 |
| 402003 | 外键推断未完成，不能发布 | 400 |
| 404001 | 版本不存在 | 404 |

#### GraphDB实例 (41)

| 错误码 | 含义 | HTTP状态 |
|--------|------|----------|
| 411001 | repo_id不能为空 | 400 |
| 411002 | graphdb_url格式错误 | 400 |
| 411003 | 实例名称已存在 | 400 |
| 412001 | 该实例下有正在运行的同步任务 | 400 |
| 413001 | 无权访问该业务域的实例 | 403 |
| 414001 | GraphDB连接失败 | 502 |
| 414002 | Repository不存在 | 502 |
| 414003 | GraphDB导入失败 | 502 |
| 414004 | SPARQL查询执行失败 | 502 |

#### 同步任务 (42)

| 错误码 | 含义 | HTTP状态 |
|--------|------|----------|
| 421001 | version_id不能为空 | 400 |
| 421002 | instance_id不能为空 | 400 |
| 421003 | 同步模式无效 | 400 |
| 422001 | 版本状态不是published | 400 |
| 422002 | 实例状态不是active | 400 |
| 422003 | 该版本正在同步中，不能创建新任务 | 400 |
| 424001 | RDF生成失败 | 500 |
| 424002 | Turtle序列化失败 | 500 |

#### 外键推断 (43)

| 错误码 | 含义 | HTTP状态 |
|--------|------|----------|
| 431001 | table_mapping_id不能为空 | 400 |
| 431002 | 审核状态无效 | 400 |
| 434001 | LLM调用失败 | 502 |
| 434002 | LLM返回格式错误 | 500 |

---

## 11. 日志规范

### 11.1 日志级别

| 级别 | 使用场景 |
|------|----------|
| DEBUG | 详细执行过程、SQL语句、SPARQL查询 |
| INFO | 业务流程节点、状态变更、用户操作 |
| WARNING | 可恢复错误、降级处理、重试 |
| ERROR | 业务失败、需要人工介入 |
| CRITICAL | 系统级错误、服务不可用 |

### 11.2 日志格式

```json
{
  "timestamp": "2026-04-20T10:00:00.000Z",
  "level": "INFO",
  "logger": "services.sync_service",
  "trace_id": "uuid-trace-123",
  "span_id": "uuid-span-456",
  "message": "开始执行同步任务",
  "context": {
    "task_id": 1,
    "version_id": 1,
    "instance_id": 1,
    "user_id": "admin"
  },
  "metrics": {
    "duration_ms": 1500,
    "triples_generated": 50000
  }
}
```

### 11.3 关键日志点

| 模块 | 日志点 | 级别 |
|------|--------|------|
| VersionService | 创建版本、发布版本、删除版本 | INFO |
| ForeignKeyInference | 开始推断、完成推断、推断失败 | INFO/ERROR |
| SyncService | 任务创建、开始执行、进度更新、完成/失败 | INFO |
| GraphDBClient | REST调用、重试、超时 | DEBUG/WARNING |
| GraphExplorer | SPARQL查询、结果缓存 | DEBUG |

---

## 12. 前端组件详细设计

### 12.1 GraphCanvas 组件（图谱画布）

**文件路径**：`src/views/graphdb/GraphExplorer/GraphCanvas.vue`

**Props**：

```typescript
interface Props {
  // 图数据
  graphData: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  
  // 布局配置
  layout: 'force' | 'circular' | 'hierarchical';
  
  // 当前选中
  selectedNodeId?: string;
  selectedEdgeId?: string;
  
  // 交互配置
  enableZoom?: boolean;      // 默认 true
  enableDrag?: boolean;      // 默认 true
  enableHover?: boolean;     // 默认 true
  
  // 样式配置
  nodeSize?: number;         // 默认 40
  edgeWidth?: number;        // 默认 2
  theme?: 'light' | 'dark';  // 默认 'light'
}
```

**Events**：

```typescript
interface Emits {
  // 节点交互
  'node-click': (node: GraphNode, event: MouseEvent) => void;
  'node-double-click': (node: GraphNode) => void;
  'node-context-menu': (node: GraphNode, event: MouseEvent) => void;
  'node-drag-end': (node: GraphNode, position: { x: number; y: number }) => void;
  
  // 边交互
  'edge-click': (edge: GraphEdge, event: MouseEvent) => void;
  'edge-hover': (edge: GraphEdge | null) => void;
  
  // 画布交互
  'canvas-click': (event: MouseEvent) => void;
  'zoom-change': (scale: number) => void;
  'viewport-change': (viewport: { x: number; y: number; zoom: number }) => void;
}
```

**实现要点**：

```vue
<template>
  <div ref="canvasRef" class="graph-canvas">
    <!-- 使用 D3.js 或 Cytoscape.js 渲染 -->
    <svg ref="svgRef" class="graph-svg">
      <g class="zoom-layer">
        <!-- 边层 -->
        <g class="edges-layer">
          <path
            v-for="edge in graphData.edges"
            :key="edge.id"
            :d="getEdgePath(edge)"
            :class="['edge', { selected: edge.id === selectedEdgeId }]"
            @click="$emit('edge-click', edge, $event)"
          />
        </g>
        
        <!-- 节点层 -->
        <g class="nodes-layer">
          <g
            v-for="node in graphData.nodes"
            :key="node.id"
            :transform="`translate(${node.x}, ${node.y})`"
            :class="['node', node.type, { selected: node.id === selectedNodeId }]"
            @click="$emit('node-click', node, $event)"
            @dblclick="$emit('node-double-click', node)"
            @contextmenu.prevent="$emit('node-context-menu', node, $event)"
          >
            <!-- 节点形状：圆形/矩形/菱形 -->
            <circle v-if="node.type === 'class'" :r="nodeSize" />
            <rect v-else-if="node.type === 'instance'" :width="nodeSize*2" :height="nodeSize*1.2" />
            <polygon v-else-if="node.type === 'event'" :points="getDiamondPoints(nodeSize)" />
            
            <!-- 节点标签 -->
            <text class="node-label" dy="5">{{ node.label }}</text>
            
            <!-- 属性图标 -->
            <g v-if="node.hasProperties" class="property-icon" @click.stop="showProperties(node)">
              <circle r="8" cx="15" cy="-15" />
              <text dy="3" dx="15">P</text>
            </g>
          </g>
        </g>
      </g>
    </svg>
    
    <!-- 工具栏 -->
    <GraphToolbar
      :zoom="currentZoom"
      @zoom-in="zoomIn"
      @zoom-out="zoomOut"
      @reset="resetView"
      @expand="expandSelected"
    />
  </div>
</template>
```

### 12.2 NodeDetailPanel 组件（节点详情面板）

**文件路径**：`src/views/graphdb/GraphExplorer/NodeDetailPanel.vue`

**Props**：

```typescript
interface Props {
  node: GraphNode | null;
  activeTab: 'definition' | 'mapping' | 'properties' | 'events';
}
```

**Events**：

```typescript
interface Emits {
  'tab-change': (tab: string) => void;
  'navigate-to-source': (source: { database: string; table: string }) => void;
  'export-ttl': (entityUri: string) => void;
  'run-sparql': (entityUri: string) => void;
  'navigate-to-entity': (entityUri: string) => void;
}
```

**模板结构**：

```vue
<template>
  <div class="node-detail-panel" v-if="node">
    <!-- 标签切换 -->
    <el-tabs v-model="activeTab" @tab-change="$emit('tab-change', $event)">
      <!-- 定义 Tab -->
      <el-tab-pane label="定义" name="definition">
        <div class="definition-section">
          <div class="field">
            <label>URI</label>
            <el-input v-model="node.uri" readonly>
              <template #append>
                <el-button @click="copyUri">复制</el-button>
              </template>
            </el-input>
          </div>
          <div class="field">
            <label>标签</label>
            <div>{{ node.label }}</div>
          </div>
          <div class="field">
            <label>类</label>
            <el-tag>{{ node.type }}</el-tag>
          </div>
          <div class="field" v-if="node.comment">
            <label>注释</label>
            <div class="comment">{{ node.comment }}</div>
          </div>
        </div>
        
        <!-- 操作按钮 -->
        <div class="actions">
          <el-button @click="$emit('export-ttl', node.uri)">导出TTL</el-button>
          <el-button @click="$emit('run-sparql', node.uri)">SPARQL查询</el-button>
        </div>
      </el-tab-pane>
      
      <!-- 映射来源 Tab -->
      <el-tab-pane label="映射来源" name="mapping">
        <div class="mapping-section">
          <div class="field">
            <label>源数据库</label>
            <div>{{ node.provenance?.source_database }}</div>
          </div>
          <div class="field">
            <label>源表</label>
            <el-link @click="navigateToSource">
              {{ node.provenance?.source_table }}
            </el-link>
          </div>
          <div class="field">
            <label>映射版本</label>
            <div>{{ node.provenance?.mapping_version }}</div>
          </div>
        </div>
      </el-tab-pane>
      
      <!-- 属性 Tab -->
      <el-tab-pane label="属性" name="properties">
        <div class="properties-list">
          <div
            v-for="prop in node.properties"
            :key="prop.predicate"
            class="property-item"
          >
            <div class="predicate">{{ prop.predicate_label }}</div>
            <div class="object">
              <template v-if="prop.object_type === 'literal'">
                {{ prop.object }}
              </template>
              <el-link v-else @click="$emit('navigate-to-entity', prop.object)">
                {{ prop.object_label }}
              </el-link>
            </div>
          </div>
        </div>
      </el-tab-pane>
      
      <!-- 事件 Tab -->
      <el-tab-pane label="事件" name="events" v-if="node.events?.length">
        <div class="events-list">
          <div
            v-for="event in node.events"
            :key="event.uri"
            class="event-item"
          >
            <el-icon><Calendar /></el-icon>
            <span>{{ event.label }}</span>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
  
  <!-- 空状态 -->
  <div v-else class="empty-panel">
    <el-empty description="点击图谱中的节点查看详情" />
  </div>
</template>
```

### 12.3 BreadcrumbNav 组件（面包屑导航）

**Props**：

```typescript
interface Props {
  path: DrillDownLevel[];  // 钻取路径
}

interface DrillDownLevel {
  level: number;           // L0-L4
  name: string;            // 显示名称
  uri?: string;            // 实体URI（可选）
}
```

**模板**：

```vue
<template>
  <div class="breadcrumb-nav">
    <el-breadcrumb separator=">">
      <el-breadcrumb-item
        v-for="(item, index) in path"
        :key="index"
        :to="{ query: { level: item.level, uri: item.uri } }"
      >
        {{ item.name }}
      </el-breadcrumb-item>
    </el-breadcrumb>
  </div>
</template>
```

---

## 13. 测试策略

### 13.1 测试分层

```
┌─────────────────────────────────────────────────────────────┐
│                      E2E 测试                                │
│  场景：完整同步流程、图谱浏览交互                             │
│  工具：Playwright                                            │
├─────────────────────────────────────────────────────────────┤
│                    集成测试                                  │
│  场景：GraphDB客户端、RDF生成、外键推断                       │
│  工具：pytest + TestContainers (GraphDB Docker)              │
├─────────────────────────────────────────────────────────────┤
│                    单元测试                                  │
│  场景：服务方法、工具函数、模型验证                           │
│  工具：pytest + pytest-asyncio + pytest-mock                 │
└─────────────────────────────────────────────────────────────┘
```

### 14.2 核心测试用例

#### 13.2.1 单元测试

```python
# tests/unit/services/test_rdf_generator.py

class TestRDFGenerator:
    """RDF生成器单元测试"""
    
    def test_build_entity_uri(self):
        """测试实体URI构建"""
        uri = build_entity_uri("iuap_fi_loan", "bd_loan_contract")
        assert uri == "urn:loanfibo:source:iuap_fi_loan/bd_loan_contract"
    
    def test_generate_datatype_property_triple(self):
        """测试DatatypeProperty三元组生成"""
        field = FieldMapping(
            field_name="loan_id",
            fibo_property_uri="fibo-loan:hasLoanIdentifier"
        )
        triples = generate_field_triples("urn:entity:1", field, [])
        
        assert len(triples) == 1
        assert triples[0].predicate == "fibo-loan:hasLoanIdentifier"
        assert "loan_id" in triples[0].object
    
    def test_generate_object_property_with_fk(self):
        """测试有外键时的ObjectProperty三元组生成"""
        field = FieldMapping(
            field_name="customer_id",
            fibo_property_uri="fibo-loan:hasBorrower"
        )
        foreign_keys = [
            ForeignKey(
                source_field="customer_id",
                target_database="iuap_fi_cust",
                target_table="bd_customer",
                review_status="approved"
            )
        ]
        triples = generate_field_triples("urn:entity:1", field, foreign_keys)
        
        assert len(triples) == 1
        assert "iuap_fi_cust/bd_customer" in triples[0].object
```

#### 13.2.2 集成测试

```python
# tests/integration/test_graphdb_client.py

class TestGraphDBClient:
    """GraphDB客户端集成测试"""
    
    @pytest.fixture
    async def graphdb_container(self):
        """启动GraphDB Docker容器"""
        with DockerContainer("ontotext/graphdb:10.5.0") as container:
            container.with_exposed_ports(7200)
            yield container
    
    async def test_create_repository(self, graphdb_container):
        """测试创建Repository"""
        client = GraphDBClient(
            base_url=f"http://localhost:{graphdb_container.get_exposed_port(7200)}"
        )
        result = await client.create_repository(
            repo_id="test-repo",
            title="Test Repository"
        )
        assert result["success"] is True
    
    async def test_upload_rdf_data(self, graphdb_container):
        """测试上传RDF数据"""
        client = GraphDBClient(...)
        turtle_data = """
        @prefix ex: <http://example.org/> .
        ex:subject ex:predicate ex:object .
        """
        result = await client.upload_rdf(
            repo_id="test-repo",
            data=turtle_data,
            content_type="text/turtle"
        )
        assert result["triple_count"] == 1
    
    async def test_sparql_query(self, graphdb_container):
        """测试SPARQL查询"""
        client = GraphDBClient(...)
        results = await client.query_sparql(
            repo_id="test-repo",
            query="SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
        )
        assert len(results["bindings"]) == 1
```

#### 13.2.3 E2E测试

```typescript
// tests/e2e/graph-explorer.spec.ts

import { test, expect } from '@playwright/test';

test.describe('图谱浏览功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/graphdb/explore');
    // 选择实例
    await page.selectOption('[data-testid="instance-selector"]', '1');
  });

  test('L0 -> L1 钻取：Repository到类', async ({ page }) => {
    // 点击Repository节点
    await page.click('[data-testid="node-repo"]');
    
    // 验证右侧面板显示Repository信息
    await expect(page.locator('[data-testid="panel-definition"]')).toContainText('三元组数');
    
    // 双击钻取到L1
    await page.dblclick('[data-testid="node-repo"]');
    
    // 验证显示类节点
    await expect(page.locator('[data-testid="node-class"]')).toHaveCount.greaterThan(0);
  });

  test('L3 关系浏览：点击边导航到对端', async ({ page }) => {
    // 钻取到L3（实例层）
    await page.dblclick('[data-testid="node-repo"]');
    await page.dblclick('[data-testid="node-class"]:first-child');
    await page.dblclick('[data-testid="node-instance"]:first-child');
    
    // 点击边
    await page.click('[data-testid="edge"]:first-child');
    
    // 验证右侧面板显示关系详情
    await expect(page.locator('[data-testid="edge-detail"]')).toBeVisible();
    
    // 点击"导航到对端"
    await page.click('[data-testid="navigate-target"]');
    
    // 验证面包屑更新
    await expect(page.locator('[data-testid="breadcrumb"]')).toContainText('>');
  });

  test('搜索定位功能', async ({ page }) => {
    // 输入搜索关键词
    await page.fill('[data-testid="search-input"]', '贷款合同');
    await page.press('[data-testid="search-input"]', 'Enter');
    
    // 验证搜索结果
    await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
    
    // 点击第一个结果
    await page.click('[data-testid="search-result"]:first-child');
    
    // 验证图谱定位到该节点
    await expect(page.locator('[data-testid="node-instance"].selected')).toBeVisible();
  });
});
```

### 13.3 测试覆盖率目标

| 模块 | 目标覆盖率 | 重点测试内容 |
|------|-----------|-------------|
| services/rdf_generator.py | 90%+ | 各种属性类型、外键场景 |
| services/foreign_key_inference.py | 85%+ | LLM调用、结果解析、重试 |
| services/graphdb_client.py | 80%+ | REST API封装、错误处理 |
| services/sync_service.py | 80%+ | 任务状态机、并发控制 |
| GraphCanvas.vue | 70%+ | 渲染、交互、事件 |

---

## 附录

### A. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 数据库表 | snake_case | `mapping_version` |
| Python类 | PascalCase | `VersionService` |
| API路径 | kebab-case | `/api/v1/sync-tasks` |
| URI | 标准URI格式 | `urn:loanfibo:source:db/table` |

### B. 相关文档

- [需求文档](requirements-graphdb-sync-v1.md)
- [三元组生成逻辑设计](graphdb-sync-triple-generation-design.md)
