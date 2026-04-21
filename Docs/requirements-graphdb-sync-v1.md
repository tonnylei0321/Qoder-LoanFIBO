# GraphDB 同步功能需求文档 v1.0

> 版本：v1.0  
> 日期：2026-04-20  
> 状态：需求确认中

---

## 1. 功能概述

### 1.1 目标

构建一条独立于映射 Pipeline 的同步链路，将经人工审核通过的映射结果（`table_mapping` + `field_mapping`）转化为 RDF 三元组，导入 Ontotext GraphDB，实现：

1. **映射结果版本化管理**：审核通过的映射形成发布版本快照
2. **多业务实例隔离**：支持向不同 GraphDB Repository 导入（如信贷、风控）
3. **图谱可视化浏览**：支持实体钻取，查看定义、映射关系、属性、边、事件
4. **外键关系解析**：ObjectProperty 可钻取到对端实体 URI

### 1.2 与现有 Pipeline 的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                     现有映射 Pipeline                            │
│  DDL解析 → TTL索引 → LLM映射 → 检核Agent → 映射修订 → PostgreSQL  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    人工审核通过（review_status='approved'）
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     本期新增：GraphDB同步链路                     │
│  发布版本快照 → RDF三元组生成 → 外键关系解析 → GraphDB导入 → 可视化 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心需求

### 2.1 发布版本管理（R1）

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R1.1 | 支持从审核通过的映射结果创建发布版本快照 | P0 |
| R1.2 | 版本快照包含完整的表级映射和字段级映射数据（冻结状态） | P0 |
| R1.3 | 版本支持状态管理：draft → published → synced | P0 |
| R1.4 | 支持查看版本详情，包括映射列表和统计信息 | P1 |
| R1.5 | 支持版本间的映射差异对比 | P2 |

### 2.2 GraphDB 实例管理（R2）

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R2.1 | 支持注册多个 GraphDB 实例（Repository） | P0 |
| R2.2 | 实例配置包含：名称、Server URL、Repository ID、业务域、命名图前缀 | P0 |
| R2.3 | 支持实例连通性健康检查 | P1 |
| R2.4 | 支持查看实例统计：类数、三元组数、命名图列表 | P1 |

### 2.3 同步任务管理（R3）

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R3.1 | 支持创建同步任务：选择版本 + 目标实例 + 同步模式 | P0 |
| R3.2 | 同步模式支持：Upsert（增量更新）、Replace（全量替换） | P0 |
| R3.3 | 支持异步执行同步任务，实时查看进度和日志 | P1 |
| R3.4 | 支持取消执行中的同步任务 | P2 |

### 2.4 RDF 三元组生成（R4）

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R4.1 | 支持三层三元组生成：实体声明层、属性映射层、映射溯源层 | P0 |
| R4.2 | 实体 URI 采用 `urn:loanfibo:source:{db}/{table}` 格式 | P0 |
| R4.3 | 第2层属性映射采用**源字段 URI 占位**方案 | P0 |
| R4.4 | DatatypeProperty 映射：`src:entity fibo:prop src:entity/field` | P0 |
| R4.5 | ObjectProperty 映射需解析外键关系，生成对端实体 URI | P0 |
| R4.6 | proj_ext_uri 映射使用项目自定义命名空间 | P0 |
| R4.7 | 第3层溯源包含：置信度、映射理由、版本、源表/字段信息 | P0 |

### 2.5 LLM 外键关系推断（R5）【本期重点】

> **背景**：BIPV5 DDL 文件中**不包含 FOREIGN KEY 约束**，需通过 LLM 语义分析推断外键关系。

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R5.1 | **LLM 外键推断**：根据字段名、注释、类型推断外键关系 | P0 |
| R5.2 | 外键推断输入：当前表结构 + 业务域内表名列表（用于匹配目标表） | P0 |
| R5.3 | 外键推断输出：字段名、目标数据库、目标表、目标字段、置信度 | P0 |
| R5.4 | 外键关系持久化到 `table_foreign_key` 表 | P0 |
| R5.5 | 人工审核：外键推断结果需人工确认后生效 | P1 |
| R5.6 | 三元组生成时，根据确认后的外键关系构造 ObjectProperty 对端实体 URI | P0 |

### 2.6 图谱可视化浏览（R6）【图钻取模式】

> **展示原则**：采用知识图谱图钻取（Graph Drill-Down）模式，**禁止使用表格或树形列表**。

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R6.1 | 实例选择器：选择要浏览的 GraphDB 实例 | P0 |
| R6.2 | **图谱画布**：以力导向图/环形图展示实体节点，支持缩放、拖拽、搜索高亮 | P0 |
| R6.3 | **节点交互**：点击节点展开详情面板，显示实体完整信息 | P0 |
| R6.4 | **边交互**：点击边（关系线）显示关系详情，支持沿边导航到对端实体 | P0 |
| R6.5 | **钻取浏览**：双击实体节点或点击"展开关联"，以该实体为中心重新渲染子图 | P0 |
| R6.6 | **属性展示**：点击实体节点的属性图标，以悬浮卡片形式展示 DatatypeProperty | P0 |
| R6.7 | **事件展示**：以特殊节点样式（如菱形）展示 FIBO 事件类，点击显示事件详情 | P1 |
| R6.8 | **搜索定位**：输入实体URI或关键词，图谱自动定位并高亮目标节点 | P0 |
| R6.9 | **面包屑导航**：顶部显示当前钻取路径（如：贷款合同 > 担保物 > 担保人） | P0 |
| R6.10 | 支持 SPARQL 查询编辑器（高级用户） | P2 |

---

## 3. 详细需求说明

### 3.1 LLM 外键关系推断（R5）详细设计

> **背景**：BIPV5 DDL 中**没有 FOREIGN KEY 约束**，需通过 LLM 语义分析推断。

#### 3.1.1 外键推断场景示例

以 `bd_loan_guarantee`（贷款担保表）为例：

```sql
CREATE TABLE bd_loan_guarantee (
    id varchar(36) PRIMARY KEY COMMENT '主键',
    loan_id varchar(36) COMMENT '贷款合同ID',           -- 疑似外键：指向贷款表
    guarantor_id varchar(36) COMMENT '担保人ID',        -- 疑似外键：指向企业/个人表
    guarantee_amount decimal(28,8) COMMENT '担保金额'
);
```

**LLM 推断逻辑**：
- `loan_id`：字段名含 "loan"，注释为 "贷款合同ID" → 推断指向 `bd_loan_contract.id`
- `guarantor_id`：字段名含 "guarantor"，注释为 "担保人ID" → 推断指向 `bd_corp_info.id`

#### 3.1.2 LLM Prompt 设计（遵循 9 条工程级标准）

```python
FOREIGN_KEY_INFERENCE_SYSTEM_PROMPT = """# 角色定义（原则1）
你是一位拥有 10 年经验的数据库架构专家，
专注于金融 ERP 系统（BIPV5）的数据库外键关系分析，
当前负责根据表结构和字段语义推断外键关系。

# 任务与范围（原则2）
## 任务
分析给定表的结构和字段语义，推断可能存在的外键关系，输出符合 JSON Schema 的推断结果。

## 范围外（禁止处理）
- 禁止推断没有明确语义线索的外键关系
- 禁止为技术字段（id, create_time, update_time, is_deleted, tenant_id, dr, ts）推断外键
- 禁止返回任何非 JSON 格式的文本说明

# 输入格式（原则3）
## 输入
- source_table: 源表信息（database_name, table_name, table_comment, fields）
- candidate_tables: 候选目标表列表（database_name, table_name, table_comment, primary_key）

# 输出格式（原则3）
严格返回以下 JSON，不得包含任何额外文字、markdown 代码块、解释说明：

{
  "foreign_keys": [
    {
      "source_field": "string - 源字段名",
      "target_database": "string - 目标数据库名",
      "target_table": "string - 目标表名",
      "target_field": "string - 目标字段名，通常为 'id'",
      "confidence": "enum: HIGH|MEDIUM|LOW",
      "reason": "string - 推断理由（1-2句中文）"
    }
  ],
  "uncertain_fields": ["string - 疑似外键但无法确定目标的字段名"]
}

# 执行步骤（原则4）
## 执行步骤（按序执行，不得跳过）

步骤 1 - 字段筛选：
  遍历源表所有字段，排除技术字段（id, create_time, update_time, is_deleted, tenant_id, dr, ts）
  → 识别可能为外键的字段：字段名含 "_id"、"_code" 后缀，或注释含 "ID"、"编码"、"编号"

步骤 2 - 语义匹配：
  对疑似外键字段，分析字段名和注释的语义
  → 在候选目标表中查找语义匹配的表（表名、注释与字段语义相关）
  → 示例：loan_id → 匹配含 "loan"、"合同"、"contract" 的表

步骤 3 - 置信度评估：
  根据匹配程度评估置信度
  → HIGH：字段名与目标表名直接对应（如 loan_id → bd_loan_contract）
  → MEDIUM：注释语义明确指向目标表（如 "贷款合同ID" → bd_loan_contract）
  → LOW：仅有间接语义关联

步骤 4 - 组装输出：
  按原则3定义的 JSON Schema 组装结果
  → 确保 uncertain_fields 包含疑似外键但无法确定目标的字段
  → 检查 JSON 格式合法性

# 禁止行为（原则5）
## 禁止行为
- 禁止为没有 "_id"、"_code" 后缀且注释不含 "ID"、"编码" 的字段推断外键
- 禁止将自增主键字段（如 id）作为外键源字段
- 禁止为同一源字段推断多个目标表
- 禁止返回 markdown 代码块（如 ```json）

# 不确定性处理（原则6）
## 不确定性出口
如果字段疑似外键但无法确定目标表（候选表中无匹配）：
→ 将该字段加入 uncertain_fields 列表，不加入 foreign_keys

# 置信度评分规则（原则7）
## 评分标准
- HIGH（0.8-1.0）：字段名与目标表名直接对应，或注释明确指向
- MEDIUM（0.5-0.7）：语义相关但非直接对应
- LOW（0.3-0.4）：仅有间接关联，需人工确认

# 示例（原则8）
## 示例 1：明确外键
输入：
- source_table: { "table_name": "bd_loan_guarantee", "fields": [{"name": "loan_id", "comment": "贷款合同ID"}] }
- candidate_tables: [{ "table_name": "bd_loan_contract", "comment": "贷款合同表" }]

输出：
{
  "foreign_keys": [
    {
      "source_field": "loan_id",
      "target_database": "iuap_fi_loan",
      "target_table": "bd_loan_contract",
      "target_field": "id",
      "confidence": "HIGH",
      "reason": "字段名loan_id和注释'贷款合同ID'明确指向贷款合同表"
    }
  ],
  "uncertain_fields": []
}

## 示例 2：无法确定目标
输入：
- source_table: { "table_name": "bd_loan_guarantee", "fields": [{"name": "guarantor_id", "comment": "担保人ID"}] }
- candidate_tables: [{ "table_name": "bd_corp_info", "comment": "企业信息" }, { "table_name": "bd_person_info", "comment": "个人信息" }]

输出：
{
  "foreign_keys": [],
  "uncertain_fields": ["guarantor_id"]
}

# 质量目标（原则9）
## 质量指标
- 推断准确率（经人工审核后）：> 80%
- 高置信度（HIGH）准确率：> 90%
- 漏检率（实际外键但未推断）：< 20%
"""
```

#### 3.1.3 数据模型扩展

新增 `table_foreign_key` 表（由 LLM 推断结果填充）：

```sql
CREATE TABLE table_foreign_key (
    id              BIGSERIAL PRIMARY KEY,
    table_mapping_id BIGINT NOT NULL REFERENCES table_mapping(id),
    source_field    VARCHAR(256) NOT NULL,
    target_database VARCHAR(128) NOT NULL,
    target_table    VARCHAR(256) NOT NULL,
    target_field    VARCHAR(256) NOT NULL,
    confidence      VARCHAR(16) NOT NULL,  -- HIGH/MEDIUM/LOW
    infer_reason    TEXT,                   -- LLM 推断理由
    review_status   VARCHAR(32) DEFAULT 'pending',  -- pending/approved/rejected
    is_composite    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);
```

#### 3.1.4 ObjectProperty 三元组生成

假设映射结果：
- `bd_loan_guarantee` → `LoanCollateral`
- `loan_id` → `isCollateralFor`（ObjectProperty，指向贷款）
- 外键推断：`loan_id` → `bd_loan_contract.id`

生成的三元组：

```turtle
# 有确认的外键关系时，生成指向对端实体的 ObjectProperty
src:iuap_fi_loan/bd_loan_guarantee
    fibo-loan:isCollateralFor  src:iuap_fi_loan/bd_loan_contract .
```

**关键**：用户点击 `src:iuap_fi_loan/bd_loan_contract` 时，可以钻取到贷款合同实体的详情。

#### 3.1.5 外键与映射的关联逻辑

```
field_mapping.fibo_property_uri = ObjectProperty
         ↓
查找 table_foreign_key（review_status='approved'）
WHERE source_field = field_mapping.field_name
         ↓
构造对端实体 URI: urn:loanfibo:source:{target_db}/{target_table}
         ↓
生成三元组: src:source_table fibo:prop src:target_db/target_table
```

### 3.2 三元组生成规则汇总

#### 第1层：实体声明

```turtle
src:{db}/{table} rdf:type {fibo_class_uri} .
```

#### 第2层：属性映射

| 属性类型 | 三元组模式 |
|---------|-----------|
| DatatypeProperty | `src:{db}/{table} {fibo_prop} src:{db}/{table}/{field}` |
| ObjectProperty（有外键） | `src:{db}/{table} {fibo_prop} src:{target_db}/{target_table}` |
| proj_ext_uri | `src:{db}/{table} {proj_ext} src:{db}/{table}/{field}` |

#### 第3层：映射溯源

```turtle
src:{db}/{table}
    loanfibo:confidenceLevel    "{level}" ;
    loanfibo:mappingReason      "{reason}" ;
    loanfibo:mappedByVersion    <urn:loanfibo:version:{id}> ;
    loanfibo:sourceDatabase     "{db}" ;
    loanfibo:sourceTableName    "{table}" ;
    loanfibo:sourceTableComment "{comment}" .
```

---

## 4. 前端页面规划

### 4.1 新增页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 版本管理 | `/versions` | 发布版本列表、创建版本 |
| 版本详情 | `/versions/:id` | 版本映射快照列表、差异对比 |
| GraphDB实例 | `/graphdb/instances` | 实例注册、编辑、健康检查 |
| 同步任务 | `/graphdb/sync` | 创建任务、查看进度日志 |
| **图谱浏览** | `/graphdb/explore` | **核心页面：实例选择→实体列表→钻取面板** |

### 4.2 图谱浏览页面交互（图钻取模式 - 左右结构）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [实例选择器 ▼]  [面包屑：medical_kg > Disease > COVID-19]  [搜索框 🔍]  [?]  │
├──────────────────────────┬──────────────────────────────────────────────────┤
│                          │                                                  │
│    图谱画布（左侧 70%）   │        实体详情面板（右侧 30%）                   │
│                          │                                                  │
│     ┌─────────┐          │  ┌────────────────────────────────────────────┐  │
│     │ Disease │          │  │  📋 定义    🔗 映射    📊 属性    📅 事件   │  │
│     │ (中心)  │          │  ├────────────────────────────────────────────┤  │
│     └────┬────┘          │  │  URI:    src:medical_kg/COVID-19            │  │
│          │               │  │  Label:  COVID-19                            │  │
│          │ a             │  │  Class:  medical:Disease                     │  │
│          ▼               │  │                                              │  │
│     ┌─────────┐          │  │  [查看源表] [导出TTL] [SPARQL查询]            │  │
│     │COVID-19 │◄─────────┼──┤                                              │  │
│     │(高亮选中)│          │  │  ─── 映射来源 ───                            │  │
│     └────┬────┘          │  │  源数据库: medical_kg                        │  │
│          │               │  │  源表:     disease                           │  │
│          │ hasSymptom    │  │  映射版本: v1.0                              │  │
│          ▼               │  │                                              │  │
│     ┌─────────┐          │  │  ─── 关联实体 ───                            │  │
│     │  Fever  │          │  │  ▸ hasSymptom → Fever                        │  │
│     │ (症状)  │          │  │  ▸ hasTreatment → Remdesivir                 │  │
│     └─────────┘          │  │  ▸ belongsTo → Coronaviridae                 │  │
│                          │  │                                              │  │
│  [+] [-] [重置] [展开]    │  └────────────────────────────────────────────┘  │
│                          │                                                  │
└──────────────────────────┴──────────────────────────────────────────────────┘
```

#### 图钻取层级设计

| 钻取层级 | 用户操作 | 后端查询 | 可视化表现 |
|---------|----------|----------|------------|
| **L0：Repository 入口** | 点击实例选择器选择 Repository | `SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }` | 圆形节点，带统计指标（三元组数、类数） |
| **L1：本体层** | 点击 Repository 节点 → 展开类/属性 | `SELECT ?cls ?label WHERE { ?cls a owl:Class }` | 分层布局：Classes / ObjectProperties / DatatypeProperties |
| **L2：实例层** | 点击 Class（如 `Disease`）→ 展示实例 | `SELECT ?inst ?label WHERE { ?inst a <Disease> }` | 实例节点网格 + 分页加载 |
| **L3：关系细节** | 点击实例（如 `COVID-19`）→ 查看关系 | `SELECT ?p ?o WHERE { <COVID-19> ?p ?o }` | 中心辐射图（Hub-and-Spoke），当前实例居中 |
| **L4：溯源/映射** | 点击边或属性 → 查看映射来源 | 查询 `table_foreign_key` 或 `field_mapping` | 高亮映射路径，显示置信度和推断理由 |

#### 图钻取交互说明

| 交互操作 | 效果 |
|---------|------|
| **单击节点** | 高亮该节点，右侧面板显示实体详情 |
| **双击节点** | 以该节点为中心钻取（进入下一层级） |
| **点击边** | 右侧面板显示关系详情，高亮该边 |
| **拖拽画布** | 平移视图 |
| **滚轮缩放** | 放大/缩小图谱 |
| **右键节点** | 上下文菜单：钻取、查看属性、复制URI、添加到路径 |
| **面包屑点击** | 回退到指定层级 |
| **右侧标签切换** | 定义 / 映射来源 / 属性 / 事件 四栏切换 |

---

## 5. 后端服务规划

### 5.1 新增服务模块

| 服务 | 文件 | 职责 |
|------|------|------|
| 版本服务 | `version_service.py` | 版本创建、发布、查询、快照生成 |
| GraphDB客户端 | `graphdb_client.py` | REST API封装、健康检查、SPARQL查询 |
| RDF生成器 | `rdf_generator.py` | 三元组生成、Turtle序列化 |
| 同步服务 | `sync_service.py` | 同步任务编排、进度追踪 |
| **外键推断服务** | **`foreign_key_inference.py`** | **LLM外键关系推断、结果持久化** |

### 5.2 数据库新增表

```sql
-- 1. 发布版本
CREATE TABLE mapping_version (
    id              BIGSERIAL PRIMARY KEY,
    version_name    VARCHAR(128) NOT NULL UNIQUE,
    description     TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',
    source_job_id   BIGINT REFERENCES mapping_job(id),
    total_mappings  INTEGER NOT NULL DEFAULT 0,
    created_by      VARCHAR(128),
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

-- 2. 版本映射明细（快照）
CREATE TABLE mapping_version_item (
    id              BIGSERIAL PRIMARY KEY,
    version_id      BIGINT NOT NULL REFERENCES mapping_version(id),
    database_name   VARCHAR(128) NOT NULL,
    table_name      VARCHAR(256) NOT NULL,
    fibo_class_uri  VARCHAR(512),
    confidence_level VARCHAR(16),
    mapping_reason  TEXT,
    field_mappings  JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. GraphDB 实例
CREATE TABLE graphdb_instance (
    id              BIGSERIAL PRIMARY KEY,
    instance_name   VARCHAR(128) NOT NULL,
    repo_id         VARCHAR(128) NOT NULL,
    graphdb_url     VARCHAR(512) NOT NULL DEFAULT 'http://localhost:7200',
    ruleset         VARCHAR(64) NOT NULL DEFAULT 'owl-horst-optimized',
    business_domain VARCHAR(128),
    named_graph_prefix VARCHAR(256) DEFAULT 'urn:loanfibo',
    status          VARCHAR(32) NOT NULL DEFAULT 'active',
    last_health_check TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (graphdb_url, repo_id)
);

-- 4. 同步任务
CREATE TABLE sync_task (
    id              BIGSERIAL PRIMARY KEY,
    version_id      BIGINT NOT NULL REFERENCES mapping_version(id),
    instance_id     BIGINT NOT NULL REFERENCES graphdb_instance(id),
    sync_mode       VARCHAR(32) NOT NULL DEFAULT 'upsert',
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',
    total_triples   INTEGER NOT NULL DEFAULT 0,
    synced_triples  INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

-- 5. 外键关系（由 LLM 推断结果填充）
CREATE TABLE table_foreign_key (
    id              BIGSERIAL PRIMARY KEY,
    table_mapping_id BIGINT NOT NULL REFERENCES table_mapping(id),
    source_field    VARCHAR(256) NOT NULL,
    target_database VARCHAR(128) NOT NULL,
    target_table    VARCHAR(256) NOT NULL,
    target_field    VARCHAR(256) NOT NULL,
    confidence      VARCHAR(16) NOT NULL,  -- HIGH/MEDIUM/LOW
    infer_reason    TEXT,                   -- LLM 推断理由
    review_status   VARCHAR(32) DEFAULT 'pending',  -- pending/approved/rejected
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

-- 6. 数据库业务域映射（用于外键推断时按业务域分组）
CREATE TABLE database_business_domain (
    id              BIGSERIAL PRIMARY KEY,
    database_name   VARCHAR(128) NOT NULL UNIQUE,
    business_domain VARCHAR(128) NOT NULL,  -- 如：信贷、资金、风控
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);
```

---

## 6. API 接口规划

### 6.1 版本管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/versions` | 创建发布版本 |
| GET | `/api/v1/versions` | 版本列表 |
| GET | `/api/v1/versions/{id}` | 版本详情 |
| POST | `/api/v1/versions/{id}/publish` | 发布版本 |

### 6.2 GraphDB 实例

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/graphdb/instances` | 实例列表 |
| POST | `/api/v1/graphdb/instances` | 注册实例 |
| GET | `/api/v1/graphdb/instances/{id}` | 实例详情 |
| GET | `/api/v1/graphdb/instances/{id}/status` | 健康检查 |

### 6.3 同步任务

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/sync/tasks` | 创建同步任务 |
| GET | `/api/v1/sync/tasks` | 任务列表 |
| GET | `/api/v1/sync/tasks/{id}` | 任务详情（含进度） |
| POST | `/api/v1/sync/tasks/{id}/cancel` | 取消任务 |

### 6.4 图谱浏览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/graphdb/instances/{id}/entities` | 实体列表 |
| GET | `/api/v1/graphdb/instances/{id}/entities/{uri}` | 实体详情 |
| GET | `/api/v1/graphdb/instances/{id}/search` | SPARQL搜索 |

---

## 7. 实施阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **P1** | LLM外键推断服务 + 数据库表创建 | 无 |
| **P2** | 后端核心：版本管理 + GraphDB实例管理 + RDF生成 | P1 |
| **P3** | 同步任务 + GraphDB导入（利用LLM推断的外键） | P2 |
| **P4** | 前端管理页：版本 + 实例 + 任务 + 外键审核 | P2 |
| **P5** | **图谱可视化浏览（核心）** | P3 |
| **P6** | 高级功能：版本对比、SPARQL编辑器 | P5 |

---

## 8. 待确认事项

1. [x] 第2层属性映射方案：**源字段URI占位**（方案A）
2. [x] ObjectProperty对端处理：**LLM语义推断外键关系**（DDL中无外键约束）
3. [x] 外键推断的候选目标表范围：**按业务域分组匹配（如信贷域、资金域）**
   - 业务域配置：在 `table_registry` 或新增 `database_business_domain` 表中维护数据库与业务域的映射
   - 推断时优先匹配同业务域内的表，若未找到再扩展到相邻业务域

---

## 9. 附录

### 9.1 命名空间前缀

| 前缀 | URI |
|------|-----|
| `rdf` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` |
| `rdfs` | `http://www.w3.org/2000/01/rdf-schema#` |
| `owl` | `http://www.w3.org/2002/07/owl#` |
| `xsd` | `http://www.w3.org/2001/XMLSchema#` |
| `fibo-*` | `https://spec.edmcouncil.org/fibo/ontology/...` |
| `loanfibo` | `urn:loanfibo:ontology:` |
| `src` | `urn:loanfibo:source:` |

### 9.2 相关文档

- [三元组生成逻辑设计](graphdb-sync-triple-generation-design.md)
- [FIBO本体切换方案](fibo-ontology-migration.md)
