# GraphDB 规则引擎需求文档 v2.0

> 版本：v2.0  
> 日期：2026-04-20  
> 状态：需求确认中  
> 架构目标：支撑10万租户、高性能、规则即代码

---

## 1. 架构理念转变

### 1.1 核心原则："只存规则，不存数据"

| 维度 | v1.0 架构（旧） | v2.0 架构（新） |
|------|----------------|----------------|
| **GraphDB角色** | 存储映射结果 + 业务数据 | 只存规则（本体+映射+公式） |
| **查询方式** | 实时SPARQL查询 | 预编译规则，执行SQL |
| **性能** | 低（图遍历开销大） | 高（数据库水平扩展） |
| **数据一致性** | 同步延迟 | 实时计算 |

### 1.2 三层本体架构

```
┌─────────────────────────────────────────────────────────────────┐
│  L0 - 基础财务本体 (Foundation Layer)                            │
│  来源: FIBO (Financial Industry Business Ontology)              │
│  内容: 借贷必相等、资产/负债/权益、期初期末                       │
│  存储: GraphDB (RDF三元组)                                       │
│  特点: 行业标准，不可修改，全局共享                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 继承
┌─────────────────────────────────────────────────────────────────┐
│  L1 - 行业领域本体 (Industry Layer)                              │
│  来源: 现有Pipeline映射结果 (table_mapping + field_mapping)      │
│  内容: BIPV5表→FIBO类映射、外键关系、计算公式                     │
│  存储: GraphDB (RDF三元组)                                       │
│  特点: 同行业租户共享，系统生成                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 重载
┌─────────────────────────────────────────────────────────────────┐
│  L2 - 租户私有规则 (Tenant Layer)                                │
│  来源: 租户自定义配置                                             │
│  内容: 字段别名、特殊公式、个性化规则                             │
│  存储: PostgreSQL (tenant_rules表)                              │
│  特点: 租户隔离，支持Override，高频修改                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心需求

### 2.1 规则管理（R1）

#### R1.1 规则编译系统

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R1.1.1 | **规则编译器**：将GraphDB中的L0+L1规则与PostgreSQL中的L2规则合并编译为可执行配置 | P0 |
| R1.1.2 | **编译触发**：支持定时编译（每日凌晨）和手动触发 | P0 |
| R1.1.3 | **编译输出**：生成JSON规则配置 + SQL算子模板 | P0 |
| R1.1.4 | **版本管理**：规则配置版本化，支持回滚 | P1 |
| R1.1.5 | **编译验证**：编译时验证规则一致性（如外键目标表存在性） | P1 |

#### R1.2 规则分发

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R1.2.1 | **规则缓存**：编译后的规则缓存到Redis，支持快速读取 | P0 |
| R1.2.2 | **租户隔离**：每个租户读取自己的L1+L2规则组合 | P0 |
| R1.2.3 | **热更新**：规则更新时，运行时引擎无感知切换 | P1 |
| R1.2.4 | **规则同步**：支持多节点规则同步 | P1 |

### 2.2 规则引擎（R2）

#### R2.1 查询引擎

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R2.1.1 | **语义解析**：分层解析架构，90%预定义意图+10%LLM解析 | P0 |
| R2.1.2 | **规则匹配**：根据意图匹配对应的规则配置 | P0 |
| R2.1.3 | **SQL生成**：确定性SQL生成（非LLM直接生成） | P0 |
| R2.1.4 | **数据查询**：执行SQL从业务数据库获取数据 | P0 |
| R2.1.5 | **结果组装**：将查询结果按FIBO语义组装返回 | P0 |
| R2.1.6 | **查询确认**：复杂查询展示解析结果，用户确认后执行 | P1 |
| R2.1.7 | **意图分类器**：轻量级BERT模型，5ms内完成分类 | P1 |

#### R2.2 计算引擎

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R2.2.1 | **公式计算**：支持预定义公式（如可用余额=总资产-冻结-应付） | P0 |
| R2.2.2 | **实时计算**：查询时实时计算派生指标 | P0 |
| R2.2.3 | **计算缓存**：支持计算结果缓存（TTL可配置） | P1 |
| R2.2.4 | **计算溯源**：返回计算过程和依据 | P1 |

### 2.3 本体与映射（R3）

#### R3.1 FIBO本体管理

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R3.1.1 | **本体加载**：支持加载FIBO标准本体到GraphDB | P0 |
| R3.1.2 | **本体索引**：建立类、属性、关系的快速索引 | P0 |
| R3.1.3 | **本体浏览**：可视化浏览FIBO本体结构 | P1 |
| R3.1.4 | **本体搜索**：支持按名称、注释搜索本体元素 | P1 |

#### R3.2 映射规则生成

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R3.2.1 | **表级映射**：DDL表→FIBO类的映射规则 | P0 |
| R3.2.2 | **字段级映射**：字段→FIBO属性的映射规则 | P0 |
| R3.2.3 | **外键映射**：LLM推断外键关系，生成关联规则 | P0 |
| R3.2.4 | **公式映射**：定义派生指标的计算公式 | P0 |
| R3.2.5 | **映射审核**：映射规则需人工审核后生效 | P1 |

### 2.4 租户管理（R4）

#### R4.1 租户配置

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R4.1.1 | **租户注册**：支持新租户注册，分配默认L1规则 | P0 |
| R4.1.2 | **字段别名**：租户可配置字段别名（L2层Override） | P0 |
| R4.1.3 | **自定义公式**：租户可配置私有计算公式 | P1 |
| R4.1.4 | **规则继承**：租户自动继承行业L1规则 | P0 |

#### R4.2 租户隔离

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R4.2.1 | **数据隔离**：租户只能访问自己的数据 | P0 |
| R4.2.2 | **规则隔离**：租户只能看到自己的L2规则 | P0 |
| R4.2.3 | **资源隔离**：支持租户级资源限制（QPS、存储） | P2 |

### 2.5 可视化与诊断（R5）

#### R5.1 规则可视化

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R5.1.1 | **规则图谱**：可视化展示L0+L1+L2规则层次 | P1 |
| R5.1.2 | **映射关系图**：展示表→类→属性的映射关系 | P1 |
| R5.1.3 | **血缘分析**：展示数据血缘（从字段到指标） | P1 |

#### R5.2 诊断与调试

| 需求编号 | 需求描述 | 优先级 |
|---------|---------|--------|
| R5.2.1 | **查询解析**：展示自然语言→SQL的转换过程 | P1 |
| R5.2.2 | **计算过程**：展示指标计算的分步过程 | P1 |
| R5.2.3 | **异常诊断**：查询失败时，LLM+GraphDB诊断原因 | P2 |

---

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              应用层 (API Gateway)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  查询API    │  │  规则管理API │  │  租户管理API │  │  可视化API      │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                              规则引擎层                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         查询引擎                                 │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │   │
│  │  │ 语义解析器   │ │ 规则匹配器   │ │ SQL生成器    │            │   │
│  │  │ (LLM/NLP)    │ │ (规则缓存)   │ │ (模板引擎)   │            │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         计算引擎                                 │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │   │
│  │  │ 公式解析器   │ │ 实时计算器   │ │ 结果缓存     │            │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                              规则存储层                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  GraphDB        │  │  Redis          │  │  PostgreSQL             │  │
│  │  (L0+L1规则)   │  │  (编译后规则缓存)│  │  (L2规则+租户配置)       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                              数据源层                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  BIPV5业务库    │  │  租户私有库     │  │  其他数据源             │  │
│  │  (PostgreSQL)   │  │  (可选)         │  │  (API/文件等)           │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

#### 3.2.1 规则编译流

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  FIBO本体   │     │  映射规则   │     │  规则编译器 │────▶│  编译后规则 │
│  (L0)       │────▶│  (L1)       │────▶│             │     │  (JSON/SQL) │
└─────────────┘     └─────────────┘     └──────┬──────┘     └─────────────┘
                                               │
                                               │     ┌─────────────┐
                                               └────▶│  L2租户规则 │
                                                     │ (PostgreSQL)│
                                                     └─────────────┘
                                                                   │
                                                                   ▼
                                                            ┌─────────────┐
                                                            │  Redis缓存  │
                                                            └─────────────┘
```

#### 3.2.2 查询执行流

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  用户查询   │────▶│  语义解析   │────▶│  规则匹配   │────▶│  SQL生成    │
│  (自然语言) │     │  (意图识别) │     │  (Redis)    │     │  (模板填充) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  结果返回   │◀────│  结果组装   │◀────│  数据查询   │◀────│  SQL执行    │
│  (FIBO语义) │     │  (格式化)   │     │  (业务库)   │     │  (PostgreSQL)│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

---

## 4. 关键概念定义

### 4.1 规则类型

| 规则类型 | 说明 | 示例 |
|---------|------|------|
| **MappingRule** | 表/字段到FIBO的映射 | bd_loan_contract → LoanContract |
| **ForeignKeyRule** | 外键关联规则 | customer_id → bd_customer.id |
| **FormulaRule** | 计算公式规则 | AvailableBalance = Assets - Frozen |
| **AliasRule** | 字段别名规则 | "运费" → "物流调剂费" |

### 4.2 规则存储格式

#### GraphDB中的规则（Turtle）

```turtle
# L0: FIBO标准
fibo-loan:LoanContract a owl:Class .

# L1: 映射规则
loanfibo:Rule_001 a loanfibo:MappingRule ;
    loanfibo:ruleType "TABLE_CLASS" ;
    loanfibo:sourceTable "bd_loan_contract" ;
    loanfibo:targetClass fibo-loan:LoanContract ;
    loanfibo:industry "credit" ;
    loanfibo:confidence "HIGH" .

# L2: 租户私有规则（存储于PostgreSQL）
# 注意：L2规则实际存储在PostgreSQL的tenant_rules表中，而非GraphDB
# 此处仅作概念示例
loanfibo:Rule_T001 a loanfibo:AliasRule ;
    loanfibo:ruleType "FIELD_ALIAS" ;
    loanfibo:tenantId "T_10086" ;
    loanfibo:sourceField "运费" ;
    loanfibo:alias "物流调剂费" .
```

#### L2 规则表结构（PostgreSQL）

```sql
-- 租户规则主表
CREATE TABLE tenant_rules (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    rule_type VARCHAR(32) NOT NULL,  -- FIELD_ALIAS, FORMULA_OVERRIDE, CUSTOM_RULE
    rule_name VARCHAR(128) NOT NULL,
    rule_definition JSONB NOT NULL,  -- 规则定义JSON
    priority INT DEFAULT 100,        -- 规则优先级，数值越小优先级越高
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(64),
    updated_by VARCHAR(64),
    UNIQUE(tenant_id, rule_name)
);

-- 字段别名规则示例
INSERT INTO tenant_rules (tenant_id, rule_type, rule_name, rule_definition) VALUES
('T_10086', 'FIELD_ALIAS', '运费别名', '{
    "source_field": "运费",
    "alias": "物流调剂费",
    "scope": "bd_loan_contract"
}');

-- 公式覆盖规则示例
INSERT INTO tenant_rules (tenant_id, rule_type, rule_name, rule_definition) VALUES
('T_10086', 'FORMULA_OVERRIDE', '可用余额计算', '{
    "target_field": "available_balance",
    "formula": "SUBTRACT(ADD(total_assets, frozen_amount), payable_amount)",
    "override_l1": true
}');

-- 创建索引
CREATE INDEX idx_tenant_rules_tenant_id ON tenant_rules(tenant_id);
CREATE INDEX idx_tenant_rules_type ON tenant_rules(tenant_id, rule_type);
CREATE INDEX idx_tenant_rules_active ON tenant_rules(tenant_id, is_active);
```

#### 编译后的规则（JSON）

```json
{
  "version": "2026-04-20-v1",
  "tenant_id": "T_10086",
  "industry": "credit",
  "mappings": {
    "tables": {
      "bd_loan_contract": {
        "fibo_class": "fibo-loan:LoanContract",
        "fields": {
          "loan_id": {"property": "fibo-loan:hasLoanIdentifier", "type": "DatatypeProperty"},
          "customer_id": {"property": "fibo-loan:hasBorrower", "type": "ObjectProperty", "fk": "bd_customer.id"}
        }
      }
    },
    "formulas": {
      "AvailableBalance": {
        "expression": "account_balance - frozen_amount - payable_amount",
        "variables": ["account_balance", "frozen_amount", "payable_amount"]
      }
    },
    "aliases": {
      "运费": "物流调剂费"
    }
  },
  "sql_templates": {
    "query_loan_contract": "SELECT loan_id, customer_id, ... FROM bd_loan_contract WHERE ..."
  }
}
```

---

## 5. API设计

### 5.1 查询API

#### 自然语言查询（NLQ）分层架构

##### 架构设计

```
用户输入自然语言查询
         ↓
┌─────────────────────┐
│  意图分类器          │  ← BERT-base模型，5ms，本地部署
│  (Intent Classifier) │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ↓           ↓
┌─────────┐  ┌──────────────┐
│预定义意图│  │ 复杂查询      │
│(90%查询) │  │ (10%查询)     │
│P99<20ms │  │ P99<500ms     │
│100%准确 │  │ 需用户确认    │
└────┬────┘  └───────┬──────┘
     │               │
     ↓               ↓
┌─────────┐  ┌──────────────┐
│模板匹配 │  │ LLM语义解析   │
│槽位填充 │  │ → 中间表示(IR)│
│确定性SQL│  │ → SQL生成     │
└─────────┘  └──────────────┘
```

##### 查询分类标准

| 查询类型 | 占比 | 处理方式 | 准确性 | 延迟 | 示例 |
|----------|------|----------|--------|------|------|
| **预定义意图** | 90% | 模板匹配 | 100% | <20ms | "昨天可用余额"、"本月总收入" |
| **结构化输入** | 5% | 直接执行 | 100% | <10ms | 表单选择维度+指标 |
| **LLM解析** | 4% | 展示确认 | 95%+ | <500ms | "对比去年同期的应收账款变化趋势" |
| **拒绝执行** | 1% | 提示重新表述 | - | <5ms | 无法理解或超出范围 |

##### 预定义意图模板

```json
{
  "intents": [
    {
      "id": "query_balance",
      "name": "查询余额",
      "patterns": [
        "{time}的可用余额",
        "{time}账户余额多少",
        "查询{time}余额"
      ],
      "slots": ["time"],
      "sql_template": "SELECT available_balance FROM balance_view WHERE date = {time}",
      "confirmation_required": false
    },
    {
      "id": "query_profit",
      "name": "查询利润",
      "patterns": [
        "{time}的净利润",
        "{time}利润是多少",
        "查询{time}利润"
      ],
      "slots": ["time"],
      "sql_template": "SELECT net_profit FROM profit_view WHERE date = {time}",
      "confirmation_required": false
    }
  ]
}
```

##### 查询确认机制

| 场景 | 确认方式 | 说明 |
|------|----------|------|
| **预定义意图** | 无需确认 | 直接执行，结果可信 |
| **结构化输入** | 无需确认 | 用户已明确选择 |
| **LLM解析高置信度** | 可选确认 | 置信度>0.9，可配置跳过确认 |
| **LLM解析低置信度** | 必须确认 | 展示解析的SQL/意图，用户确认后执行 |
| **关键财务指标** | 必须确认 | 余额、利润等，无论置信度都需确认 |

##### API设计

```http
POST /api/v2/query
Content-Type: application/json

{
  "tenant_id": "T_10086",
  "query": "昨天我公司的可用余额是多少",
  "context": {
    "date_range": "2026-04-19",
    "company_id": "C_001"
  },
  "options": {
    "skip_confirmation": false,  // 是否跳过确认（仅对高置信度有效）
    "require_sql_preview": true   // 是否返回SQL预览
  }
}
```

**响应（预定义意图-直接执行）**：

```json
{
  "code": 0,
  "data": {
    "query_type": "predefined_intent",
    "intent": {
      "id": "query_balance",
      "confidence": 1.0,
      "concept": "AvailableBalance",
      "slots": {
        "time": "2026-04-19"
      }
    },
    "result": {
      "value": 1234567.89,
      "currency": "CNY",
      "formula": "account_balance - frozen_amount - payable_amount",
      "components": {
        "account_balance": 1500000.00,
        "frozen_amount": 200000.00,
        "payable_amount": 65432.11
      }
    },
    "execution_time_ms": 15
  }
}
```

**响应（LLM解析-需要确认）**：

```json
{
  "code": 100,  // 需要用户确认
  "data": {
    "query_type": "llm_parsed",
    "intent": {
      "confidence": 0.85,
      "parsed_query": "查询2026年Q1与2025年Q1的应收账款对比",
      "sql_preview": "SELECT ... FROM ... WHERE ...",
      "explanation": "系统将查询2026年第一季度应收账款，并与2025年同期对比"
    },
    "confirmation": {
      "required": true,
      "token": "confirm_token_xxx",
      "expires_in": 300
    }
  }
}
```

##### 准确性保障机制

| 机制 | 说明 | 实施方式 |
|------|------|----------|
| **意图分类器** | 轻量级BERT模型 | 本地部署，5ms延迟，准确率>95% |
| **预定义模板** | 覆盖90%常见查询 | 基于历史数据分析，持续优化 |
| **槽位验证** | 验证提取的参数 | 时间格式、实体存在性校验 |
| **SQL预览** | 展示生成的SQL | 用户可查看即将执行的SQL |
| **执行限制** | 限制查询范围 | 只能查询，禁止INSERT/UPDATE/DELETE |
| **审计日志** | 记录所有查询 | 支持事后追溯和分析 |

##### 降级策略

| 场景 | 降级方式 | 用户体验 |
|------|----------|----------|
| **意图分类器故障** | 全部走LLM解析+强制确认 | 延迟增加，但功能可用 |
| **LLM服务不可用** | 仅支持预定义意图 | 提示用户使用标准问法 |
| **高并发** | 优先保障预定义意图 | LLM解析排队或限流 |
| **关键指标查询** | 强制结构化输入 | 禁用自然语言，确保准确 |

### 5.2 规则管理API

#### 触发规则编译

```http
POST /api/v2/rules/compile
Content-Type: application/json

{
  "industry": "credit",
  "tenant_id": "T_10086",
  "trigger": "manual"
}
```

#### 获取编译后规则

```http
GET /api/v2/rules/compiled?tenant_id=T_10086&version=latest
```

---

## 6. 实施阶段

### Phase 1: 核心规则引擎（4周）
- 规则编译器开发
- Redis规则缓存
- 基础查询引擎（语义解析+SQL生成）

### Phase 2: 本体与映射（3周）
- FIBO本体加载
- 现有Pipeline映射结果转化
- LLM外键推断

### Phase 3: 租户与可视化（3周）
- 租户配置系统
- 规则可视化
- 诊断与调试工具

### Phase 4: 性能优化（2周）
- 计算缓存
- SQL优化
- 压测与调优

---

## 7. 与现有系统的关系

### 7.1 与现有Pipeline的关系

```
现有Pipeline:
DDL解析 → TTL索引 → LLM映射 → 检核Agent → 映射修订 → PostgreSQL
                                                    ↓
                                              映射结果
                                                    ↓
新规则引擎:
映射结果读取 → 规则生成 → 规则编译 → Redis缓存 → 查询引擎
```

### 7.2 数据流整合

| 系统 | 职责 | 数据流向 |
|------|------|---------|
| **现有Pipeline** | 生成映射规则 | 输出到PostgreSQL |
| **新规则引擎** | 编译规则、执行查询 | 读取PostgreSQL，编译到Redis |
| **GraphDB** | 存储L0+L1规则 | 编译源，不直接参与查询 |
| **PostgreSQL** | 存储L2租户规则 | 编译源，支持高频修改 |

---

## 8. 关键决策确认

| 决策项 | 选择 | 说明 |
|--------|------|------|
| **公式规则语法** | **C - 自定义DSL** | 类似Excel公式，支持常用财务函数，用户友好 |
| **租户规则优先级** | **A - 完全Override** | L2完全替换L1，实现简单，逻辑清晰 |
| **规则编译触发** | **C - 混合模式** | 人工审核后实时编译，日常变更定时编译 |
| **多租户数据隔离** | **A - 行级权限** | 单表 + tenant_id字段，资源利用率高 |
| **计算缓存策略** | **C - 智能缓存** | 基于数据变更事件失效，性能与一致性平衡 |

---

## 9. 详细规范

### 9.1 公式规则DSL规范

#### 语法定义

```ebnf
formula           ::= scalar_expression | aggregate_expression
scalar_expression ::= term (('+' | '-') term)*
term              ::= factor (('*' | '/') factor)*
factor            ::= number | variable | scalar_function | '(' scalar_expression ')'

aggregate_expression ::= aggregate_function '(' aggregate_arg ')'
aggregate_function   ::= 'AGG_SUM' | 'AGG_AVG' | 'AGG_MAX' | 'AGG_MIN' | 'AGG_COUNT'
aggregate_arg        ::= column_ref ('WHERE' filter_expr)?
column_ref           ::= table_name '.' column_name | column_name
filter_expr          ::= scalar_expression

scalar_function   ::= func_name '(' arg_list? ')'
func_name         ::= 'DIVIDE' | 'ABS' | 'ROUND' | 'SUM' | 'AVG' | 'MAX' | 'MIN' | 'COALESCE' | 'IF'
arg_list          ::= scalar_expression (',' scalar_expression)*
variable          ::= [a-zA-Z_][a-zA-Z0-9_]*
number            ::= [0-9]+ ('.' [0-9]+)?
table_name        ::= [a-zA-Z_][a-zA-Z0-9_]*
column_name       ::= [a-zA-Z_][a-zA-Z0-9_]*
```

#### 计算模式

| 模式 | 说明 | 示例 | 生成SQL |
|------|------|------|---------|
| **标量计算** | 单行字段计算 | `amount * price` | `SELECT amount * price` |
| **聚合计算** | 多行聚合 | `AGG_SUM(amount)` | `SELECT SUM(amount)` |
| **分组聚合** | 按维度聚合 | `AGG_SUM(amount WHERE status='active')` | `SELECT SUM(CASE WHEN status='active' THEN amount END)` |
| **混合计算** | 标量+聚合 | `DIVIDE(AGG_SUM(amount), AGG_COUNT(*), 0)` | `SELECT SUM(amount) / COUNT(*)` |

#### 内置函数

| 函数 | 语法 | 说明 | 示例 |
|------|------|------|------|
| **DIVIDE** | `DIVIDE(a, b, default)` | 安全除法，除数为0时返回default | `DIVIDE(profit, cost, 0)` |
| **ABS** | `ABS(x)` | 绝对值 | `ABS(amount)` |
| **ROUND** | `ROUND(x, n)` | 四舍五入到n位小数 | `ROUND(ratio, 2)` |
| **SUM** | `SUM(a, b, c, ...)` | 标量求和 | `SUM(a, b, c)` |
| **AVG** | `AVG(a, b, c, ...)` | 标量平均值 | `AVG(q1, q2, q3, q4)` |
| **AGG_SUM** | `AGG_SUM(column)` | 聚合求和 | `AGG_SUM(amount)` |
| **AGG_AVG** | `AGG_AVG(column)` | 聚合平均值 | `AGG_AVG(price)` |
| **AGG_MAX** | `AGG_MAX(column)` | 聚合最大值 | `AGG_MAX(balance)` |
| **AGG_MIN** | `AGG_MIN(column)` | 聚合最小值 | `AGG_MIN(fee)` |
| **AGG_COUNT** | `AGG_COUNT(* \| column)` | 聚合计数 | `AGG_COUNT(*)` |
| **MAX** | `MAX(a, b, ...)` | 最大值 | `MAX(balance, 0)` |
| **MIN** | `MIN(a, b, ...)` | 最小值 | `MIN(available, limit)` |
| **COALESCE** | `COALESCE(a, b, ...)` | 返回第一个非NULL值 | `COALESCE(fee, 0)` |
| **IF** | `IF(condition, true_val, false_val)` | 条件判断 | `IF(status='active', amount, 0)` |

#### DSL 执行安全规范

| 安全限制 | 默认值 | 说明 |
|----------|--------|------|
| **AST最大深度** | 50 | 防止极深嵌套导致栈溢出 |
| **最大操作步数** | 1000 | 限制单公式执行的操作数 |
| **执行超时** | 5秒 | 单公式执行超时时间 |
| **内存限制** | 10MB | 单公式执行内存上限 |
| **禁用函数** | - | 禁止系统调用、文件操作、网络请求 |
| **沙箱环境** | WASM | DSL执行在WASM沙箱中，隔离系统资源 |

#### 安全执行流程

```
1. 公式解析
   ├── 语法检查
   ├── AST深度检查（<=50）
   └── 禁用函数检查
2. 编译阶段
   ├── 操作步数预估（<=1000）
   └── 资源使用预估
3. 执行阶段
   ├── WASM沙箱启动
   ├── 超时监控（5秒）
   ├── 内存监控（10MB）
   └── 结果返回
4. 异常处理
   ├── 超时：返回错误，记录日志
   ├── 内存超限：强制终止，返回错误
   └── 异常终止：清理资源，返回错误
```

#### 公式示例

```json
{
  "formulas": {
    "AvailableBalance": {
      "expression": "account_balance - frozen_amount - payable_amount",
      "description": "可用余额 = 账户余额 - 冻结金额 - 应付金额",
      "mode": "scalar"
    },
    "NetProfitMargin": {
      "expression": "DIVIDE(net_profit, revenue, 0) * 100",
      "description": "净利润率(%) = 净利润 / 营业收入 * 100",
      "mode": "scalar"
    },
    "WeightedAverage": {
      "expression": "DIVIDE(SUM(amount * weight), SUM(weight), 0)",
      "description": "加权平均值",
      "mode": "scalar"
    },
    "SafeAmount": {
      "expression": "IF(ABS(variance) > threshold, 0, amount)",
      "description": "如果方差超过阈值，金额为0",
      "mode": "scalar"
    },
    "TotalBranchBalance": {
      "expression": "AGG_SUM(balance)",
      "description": "所有分支机构总余额",
      "mode": "aggregate",
      "group_by": ["branch_id"]
    },
    "ActiveLoanAmount": {
      "expression": "AGG_SUM(amount WHERE status='active')",
      "description": "活跃贷款总金额",
      "mode": "aggregate"
    },
    "AverageTransactionPerAccount": {
      "expression": "DIVIDE(AGG_SUM(transaction_amount), AGG_COUNT(DISTINCT account_id), 0)",
      "description": "平均每账户交易金额",
      "mode": "aggregate"
    }
  }
}
```

### 9.2 租户规则Override规范

#### 规则继承与覆盖

```
L0 (FIBO标准)
    ↓ 继承
L1 (行业规则 - credit行业)
    ↓ Override
L2 (租户规则 - T_10086)
```

#### Override规则

1. **完全替换**: 租户规则完全替换行业规则
2. **显式声明**: 租户必须声明规则类型（新增/修改/删除）
3. **版本锁定**: 租户可锁定使用特定版本的L1规则

#### 冲突解决策略

| 冲突类型 | 场景 | 解决策略 | 说明 |
|----------|------|----------|------|
| **字段映射冲突** | L2字段映射与L1外键依赖冲突 | **拒绝冲突** | 编译失败，提示租户修改 |
| **公式覆盖冲突** | L2公式引用了L1不存在的字段 | **警告通过** | 编译通过，但标记警告 |
| **规则删除冲突** | L2删除L1被依赖的规则 | **级联检查** | 检查是否有其他规则依赖，有则拒绝 |
| **命名空间冲突** | L2新增规则与L1规则同名 | **L2优先** | 默认L2覆盖，可配置为拒绝 |

#### 冲突解决配置

```json
{
  "tenant_id": "T_10086",
  "conflict_resolution": {
    "default_policy": "REJECT",  // REJECT | WARN | OVERRIDE
    "field_mapping_conflict": "REJECT",
    "formula_reference_conflict": "WARN",
    "rule_deletion_conflict": "CASCADE_CHECK",
    "namespace_conflict": "OVERRIDE"
  }
}
```

#### 编译验证流程

```
1. 读取L0+L1规则（GraphDB）
2. 读取L2规则（PostgreSQL）
3. 规则合并
   ├── 字段映射合并
   ├── 公式合并
   └── 外键关系合并
4. 冲突检测
   ├── 字段依赖检查
   ├── 公式语法检查
   ├── 外键完整性检查
   └── 循环依赖检查
5. 冲突解决（根据配置策略）
6. 生成编译报告
   ├── 成功：生成编译后配置
   └── 失败：返回错误列表
```

#### 规则配置示例

```json
{
  "tenant_id": "T_10086",
  "industry": "credit",
  "l1_version": "2026-04-20-v1",
  "overrides": {
    "type": "complete",
    "rules": {
      "aliases": {
        "运费": "物流调剂费",
        "手续费": "服务佣金"
      },
      "formulas": {
        "CustomProfit": "revenue - cost - special_fee"
      },
      "mappings": {
        "bd_custom_table": {
          "fibo_class": "fibo-loan:CustomContract",
          "fields": {
            "custom_field": {"property": "fibo-loan:hasCustomAttribute"}
          }
        }
      }
    }
  }
}
```

### 9.3 规则编译触发规范

#### 编译架构（支持10万租户渐进扩展）

```
┌─────────────────────────────────────────────────────────────────┐
│                     规则编译服务集群                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ 编译节点-1   │  │ 编译节点-2   │  │ 编译节点-N   │  ← 水平扩展 │
│  │ (8核/32GB)  │  │ (8核/32GB)  │  │ (8核/32GB)  │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         └─────────────────┼─────────────────┘                    │
│                           ▼                                      │
│                    ┌─────────────┐                               │
│                    │  任务队列    │  ← Redis/RabbitMQ             │
│                    │ (编译任务)   │                               │
│                    └─────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

#### 渐进式租户支持策略

| 阶段 | 租户规模 | 编译策略 | 并发能力 | 全量编译时间 |
|------|----------|----------|----------|--------------|
| **初期** | 10-100租户 | 单节点编译 | 10并发 | < 1分钟 |
| **成长期** | 100-10,000租户 | 多节点编译 | 100并发 | < 10分钟 |
| **成熟期** | 10,000-100,000租户 | 分布式编译集群 | 1000并发 | < 2小时 |

#### 增量编译策略

| 变更类型 | 影响范围 | 编译策略 | 性能目标 |
|----------|----------|----------|----------|
| **L0变更** (FIBO标准) | 所有租户 | 全量编译，分布式并行 | 1000并发，< 2小时 |
| **L1变更** (行业规则) | 同行业租户 | 仅编译受影响行业 | 100并发，< 10分钟 |
| **L2变更** (租户规则) | 单个租户 | 仅编译该租户 | < 5秒 |
| **热修复** (安全补丁) | 紧急租户 | 懒加载编译（首次访问时） | 无感知 |

#### 编译性能优化

| 优化手段 | 说明 | 效果 |
|----------|------|------|
| **编译缓存** | 缓存L0+L1编译中间结果 | 减少70%编译时间 |
| **并行解析** | 多线程并行解析DSL公式 | 减少50%编译时间 |
| **增量检测** | 仅编译变更的规则片段 | 减少90%编译时间 |
| **预编译** | 非高峰时段预编译热门租户 | 用户无感知 |

#### 触发条件

| 触发类型 | 条件 | 处理方式 | 延迟 | 并发 |
|----------|------|----------|------|------|
| **人工审核通过** | 映射规则审核状态变为`approved` | 立即触发该租户编译 | < 5秒 | 单租户 |
| **定时任务** | 每日凌晨 02:00 | 批量编译所有待更新租户 | 异步 | 100并发 |
| **手动触发** | 管理员调用API | 立即触发指定租户编译 | < 5秒 | 单租户 |
| **紧急回滚** | 规则版本回滚 | 立即触发该租户编译 | < 5秒 | 单租户 |
| **L1全局变更** | 行业规则更新 | 批量编译该行业所有租户 | 异步 | 100并发 |

#### 编译状态机

```
┌─────────┐    触发     ┌─────────┐    成功    ┌─────────┐
│  PENDING │ ─────────▶ │ COMPILING│ ────────▶ │ SUCCESS │
└─────────┘            └─────────┘            └─────────┘
     │                      │
     │ 批量任务              │ 失败
     ▼                      ▼
┌─────────┐           ┌─────────┐    重试    ┌─────────┐
│  QUEUED │           │  FAILED │ ─────────▶ │  RETRY  │
└─────────┘           └─────────┘            └─────────┘
```

#### 编译任务队列配置

```json
{
  "compiler_cluster": {
    "min_nodes": 2,
    "max_nodes": 100,
    "scale_policy": "cpu_usage > 70%",
    "queue_config": {
      "high_priority": "L2变更、紧急回滚",
      "normal_priority": "定时任务、L1变更",
      "low_priority": "预编译任务"
    }
  }
}
```

### 9.4 行级权限数据隔离规范

#### 数据隔离策略对比

| 策略 | 适用场景 | 优点 | 缺点 | 推荐度 |
|------|----------|------|------|--------|
| **单表+RLS** | <1000租户，低频查询 | 资源利用率高 | RLS开销大，难扩展 | ⭐⭐ |
| **分表（按tenant_id哈希）** | 1万-10万租户 | 无RLS开销，易扩展 | 跨租户查询复杂 | ⭐⭐⭐⭐ |
| **分库（按tenant_id范围）** | >10万租户 | 完全隔离，性能最好 | 资源成本高 | ⭐⭐⭐ |
| **混合策略（推荐）** | 10万租户 | 高频租户分库，低频租户分表 | 复杂度中等 | ⭐⭐⭐⭐⭐ |

#### 推荐方案：混合策略

```
租户分层：
┌─────────────────────────────────────────────────────────┐
│  Tier 1: 高频租户（Top 100）                              │
│  └── 独立数据库实例，物理隔离                              │
├─────────────────────────────────────────────────────────┤
│  Tier 2: 中频租户（101-10000）                            │
│  └── 分库（32个库），按tenant_id % 32分布                 │
├─────────────────────────────────────────────────────────┤
│  Tier 3: 低频租户（10001-100000）                         │
│  └── 分表（256张表），按tenant_id % 256分布               │
└─────────────────────────────────────────────────────────┘
```

#### 数据库设计（分表模式）

```sql
-- 创建256张分表（示例）
-- 表名: bd_loan_contract_000 ~ bd_loan_contract_255

CREATE TABLE bd_loan_contract_{shard_id} (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    loan_id VARCHAR(128) NOT NULL,
    customer_id VARCHAR(128),
    amount DECIMAL(18, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引（无需tenant_id索引，按tenant_id分表已天然隔离）
    INDEX idx_loan_id (loan_id),
    INDEX idx_customer (customer_id),
    INDEX idx_created (created_at)
);

-- 分表路由函数
CREATE OR REPLACE FUNCTION get_shard_id(tenant_id VARCHAR) 
RETURNS INTEGER AS $$
BEGIN
    RETURN abs(hashtext(tenant_id)) % 256;
END;
$$ LANGUAGE plpgsql;
```

#### 应用层路由

```python
class TenantRouter:
    """租户数据路由"""
    
    def __init__(self):
        self.tier_config = {
            'tier1': {'tenants': 100, 'type': 'dedicated'},    # 独立实例
            'tier2': {'shards': 32, 'type': 'shard_db'},       # 32个库
            'tier3': {'shards': 256, 'type': 'shard_table'}    # 256张表
        }
    
    def get_connection(self, tenant_id: str) -> Connection:
        """获取租户数据库连接"""
        tier = self._get_tier(tenant_id)
        
        if tier == 'tier1':
            # 独立实例
            return self._get_dedicated_connection(tenant_id)
        elif tier == 'tier2':
            # 分库
            shard_id = hash(tenant_id) % 32
            return self._get_shard_db_connection(shard_id)
        else:
            # 分表
            shard_id = hash(tenant_id) % 256
            return self._get_default_connection(shard_id)
    
    def get_table_name(self, tenant_id: str, base_table: str) -> str:
        """获取租户分表名"""
        tier = self._get_tier(tenant_id)
        
        if tier in ['tier1', 'tier2']:
            return base_table  # 独立实例/分库，无需分表
        else:
            shard_id = hash(tenant_id) % 256
            return f"{base_table}_{shard_id:03d}"
```

#### 查询引擎处理

```python
def generate_sql(intent, tenant_id, rule_config):
    """生成SQL（自动处理分表路由）"""
    router = TenantRouter()
    
    # 获取分表名
    base_table = rule_config['source_table']
    actual_table = router.get_table_name(tenant_id, base_table)
    
    # 生成SQL（分表模式下无需tenant_id过滤）
    base_sql = rule_config['sql_template'].replace(base_table, actual_table)
    
    # Tier3分表模式：表已按tenant_id分，无需额外过滤
    # Tier1/Tier2：仍需tenant_id过滤（多租户共享实例/库）
    tier = router._get_tier(tenant_id)
    if tier in ['tier1', 'tier2']:
        where_clause = f"tenant_id = '{tenant_id}'"
        final_sql = f"{base_sql} WHERE {where_clause} AND ..."
    else:
        final_sql = f"{base_sql} WHERE ..."
    
    return final_sql
```

#### 性能优化建议

| 优化项 | 说明 | 预期效果 |
|--------|------|----------|
| **连接池隔离** | Tier1独立连接池，Tier2/Tier3共享连接池 | 避免高频租户影响低频租户 |
| **读写分离** | 查询走只读副本，写入走主库 | 提升查询性能 |
| **热点检测** | 监控各分片QPS，自动迁移热点租户 | 动态负载均衡 |
| **预编译SQL** | 常用查询使用预编译语句 | 减少解析开销 |

### 9.5 智能缓存规范

#### 缓存架构

```
┌─────────────────────────────────────────────────────────────┐
│                        计算缓存层                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  L1 - 本地  │  │  L2 - Redis │  │  L3 - 持久化        │ │
│  │  (Caffeine) │  │  (分布式)   │  │  (PostgreSQL)       │ │
│  │  TTL: 1min  │  │  TTL: 5min  │  │  长期存储           │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### 缓存Key设计

```
key = "calc:{tenant_id}:{formula_name}:{entity_id}:{date}:{params_hash}"

示例: "calc:T_10086:AvailableBalance:C_001:2026-04-19:a1b2c3d4"
```

#### 失效策略

| 失效类型 | 触发条件 | 处理方式 | 适用场景 |
|----------|----------|----------|----------|
| **主动失效** | 源数据变更 | 发布失效事件，清除相关缓存 | 所有计算类型 |
| **被动失效** | TTL到期 | 自动过期，下次查询重新计算 | 非关键指标（TTL兜底） |
| **手动失效** | 管理员操作 | 清除指定租户/公式的所有缓存 | 紧急情况 |
| **强制穿透** | 关键财务查询 | 直接查询数据库，绕过缓存 | 关键财务指标 |

#### 财务数据一致性保障

| 数据类型 | 缓存策略 | 一致性级别 | 说明 |
|----------|----------|------------|------|
| **关键财务指标** | 禁用缓存或TTL=0 | 强一致性 | 可用余额、账户余额等，实时计算 |
| **派生指标** | 主动失效+短TTL | 最终一致性 | 利润率、比率等，TTL=30s |
| **统计指标** | 主动失效+长TTL | 最终一致性 | 日汇总、月汇总等，TTL=5min |
| **历史数据** | 长TTL+版本控制 | 最终一致性 | 历史快照，TTL=1hour |

#### 缓存穿透策略

```json
{
  "formula_config": {
    "AvailableBalance": {
      "cache_policy": "NO_CACHE",
      "description": "关键财务指标，禁用缓存"
    },
    "NetProfitMargin": {
      "cache_policy": "EVENT_INVALIDATE",
      "ttl_seconds": 30,
      "description": "派生指标，事件失效+短TTL"
    },
    "DailySummary": {
      "cache_policy": "EVENT_INVALIDATE",
      "ttl_seconds": 300,
      "description": "统计指标，事件失效+长TTL"
    }
  }
}
```

#### 数据一致性校验

| 校验机制 | 说明 | 触发时机 |
|----------|------|----------|
| **版本号校验** | 查询时比对数据版本号 | 每次查询 |
| **Hash校验** | 计算结果Hash与缓存Key比对 | 缓存写入时 |
| **时间戳校验** | 检查数据时间戳是否最新 | 关键查询时 |

#### 数据变更事件

```json
{
  "event_type": "DATA_CHANGE",
  "tenant_id": "T_10086",
  "table": "bd_loan_contract",
  "operation": "UPDATE",
  "affected_fields": ["account_balance", "frozen_amount"],
  "timestamp": "2026-04-20T10:30:00Z"
}
```

缓存监听器根据`affected_fields`自动失效相关公式缓存。

---

## 附录

## 10. 非功能性需求

### 10.1 性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| **查询响应时间** | P99 < 50ms | 简单查询（单表） |
| **复杂查询响应时间** | P99 < 200ms | 多表关联+计算 |
| **规则编译时间** | < 5秒/租户（单租户）<br>< 1秒/租户（批量并发） | 完整L1+L2规则编译 |
| **并发查询** | 10,000 QPS | 单节点 |
| **支持的租户数** | 100,000+ | 水平扩展 |
| **缓存命中率** | > 80% | L1+L2缓存综合 |

### 10.2 可用性要求

| 指标 | 目标值 |
|------|--------|
| **系统可用性** | 99.9% (年停机时间 < 8.76小时) |
| **规则编译可用性** | 99.5% (允许定时任务失败重试) |
| **数据一致性** | 最终一致性（缓存场景） |
| **故障恢复时间** | RTO < 5分钟，RPO < 1分钟 |

### 10.3 安全规范

#### 10.3.1 数据安全

- **传输加密**: 所有API使用HTTPS/TLS 1.3
- **存储加密**: 敏感字段（如金额）加密存储
- **密钥管理**: 使用HashiCorp Vault或AWS KMS

#### 10.3.2 访问控制

| 角色 | 权限 |
|------|------|
| **系统管理员** | 规则管理、租户管理、系统配置 |
| **行业管理员** | L1规则管理、映射审核 |
| **租户管理员** | L2规则配置、数据查询 |
| **普通用户** | 数据查询（只读） |

#### 10.3.3 SQL注入防护

```python
# 禁止字符串拼接SQL
# 错误
def query_bad(tenant_id, table):
    return f"SELECT * FROM {table} WHERE tenant_id = '{tenant_id}'"

# 正确
def query_good(tenant_id, table):
    # 使用参数化查询
    return "SELECT * FROM {} WHERE tenant_id = %s".format(ALLOWED_TABLES[table]), (tenant_id,)
```

### 10.4 错误处理

#### 10.4.1 错误码定义

| 错误码 | 说明 | HTTP状态码 |
|--------|------|-----------|
| `0` | 成功 | 200 |
| `1001` | 租户不存在 | 404 |
| `1002` | 规则未编译 | 400 |
| `1003` | 公式语法错误 | 400 |
| `1004` | 查询超时 | 504 |
| `1005` | 数据源连接失败 | 503 |
| `2001` | 权限不足 | 403 |
| `2002` | 速率限制 | 429 |
| `5000` | 内部错误 | 500 |

#### 10.4.2 错误响应格式

```json
{
  "code": 1003,
  "message": "Formula syntax error",
  "details": {
    "formula": "DIVIDE(a, b)",
    "error": "DIVIDE function requires 3 arguments, got 2",
    "position": 0
  },
  "request_id": "req_abc123",
  "timestamp": "2026-04-20T10:30:00Z"
}
```

### 10.5 监控与告警

#### 10.5.1 关键指标监控

| 指标类型 | 指标名 | 告警阈值 |
|----------|--------|----------|
| **性能** | 查询P99延迟 | > 100ms |
| **性能** | 缓存命中率 | < 70% |
| **可用性** | 错误率 | > 1% |
| **资源** | CPU使用率 | > 80% |
| **资源** | 内存使用率 | > 85% |
| **业务** | 规则编译失败 | > 0 |

#### 10.5.2 日志规范

```json
{
  "timestamp": "2026-04-20T10:30:00.123Z",
  "level": "INFO",
  "service": "rules-engine",
  "trace_id": "trace_abc123",
  "span_id": "span_def456",
  "tenant_id": "T_10086",
  "event": "QUERY_EXECUTED",
  "duration_ms": 15,
  "sql_hash": "a1b2c3d4",
  "cache_hit": true
}
```

---

## 附录

### A. 与v1.0的差异对比

| 维度 | v1.0 | v2.0 |
|------|------|------|
| GraphDB用途 | 存储映射结果，实时查询 | 存储规则，编译期使用 |
| 查询性能 | 依赖GraphDB | 依赖PostgreSQL+Redis |
| 数据一致性 | 同步延迟 | 实时计算 |
| 架构复杂度 | 中等 | 较高（需规则编译器）|
| 适用场景 | 可视化浏览 | 高性能规则引擎 |
| 公式支持 | 无 | 自定义DSL |
| 租户隔离 | Repository级别 | 行级权限 |
| 缓存策略 | 无 | 三级智能缓存 |

### B. 相关文档

- [v1.0需求文档](requirements-graphdb-sync-v1.md)
- [v1.0设计文档](design-graphdb-sync-v1.md)
- [参考文章：10万租户图数据库架构](https://github.com/...)

### C. 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 本体 | Ontology | 领域概念的形式化定义 |
| 规则引擎 | Rules Engine | 解析、匹配、执行规则的系统 |
| 规则编译器 | Rule Compiler | 将GraphDB规则编译为可执行配置 |
| DSL | Domain Specific Language | 领域特定语言（如公式语法）|
| RLS | Row Level Security | 行级安全策略 |
| TTL | Time To Live | 缓存生存时间 |
| FIBO | Financial Industry Business Ontology | 金融行业业务本体标准 |

### D. 参考实现

#### D.1 公式解析器伪代码

```python
class FormulaParser:
    def __init__(self, formula_str):
        self.formula = formula_str
        self.tokens = self.tokenize(formula_str)
    
    def parse(self):
        """解析公式为AST"""
        return self.parse_expression()
    
    def parse_expression(self):
        """解析表达式：term (('+'|'-') term)*"""
        left = self.parse_term()
        while self.peek() in ('+', '-'):
            op = self.consume()
            right = self.parse_term()
            left = {'type': 'binary', 'op': op, 'left': left, 'right': right}
        return left
    
    def evaluate(self, context):
        """执行公式计算"""
        ast = self.parse()
        return self._eval_node(ast, context)
    
    def _eval_node(self, node, context):
        if node['type'] == 'variable':
            return context.get(node['name'], 0)
        elif node['type'] == 'number':
            return node['value']
        elif node['type'] == 'function':
            return self._call_function(node, context)
        elif node['type'] == 'binary':
            left = self._eval_node(node['left'], context)
            right = self._eval_node(node['right'], context)
            return self._apply_op(node['op'], left, right)
```

#### D.2 规则编译流程

```python
async def compile_rules(tenant_id: str, industry: str) -> CompileResult:
    """编译租户规则"""
    
    # 1. 读取L0规则（FIBO本体）
    l0_rules = await graphdb.query("""
        SELECT * WHERE {
            ?rule a loanfibo:FIBORule .
            # ...
        }
    """)
    
    # 2. 读取L1规则（行业规则）
    l1_rules = await graphdb.query(f"""
        SELECT * WHERE {{
            ?rule a loanfibo:MappingRule ;
                  loanfibo:industry "{industry}" .
            # ...
        }}
    """)
    
    # 3. 读取L2规则（租户私有）
    l2_rules = await postgres.query("""
        SELECT * FROM tenant_rules WHERE tenant_id = %s
    """, (tenant_id,))
    
    # 4. 合并规则（L2 Override L1）
    merged_rules = merge_rules(l0_rules, l1_rules, l2_rules)
    
    # 5. 验证规则一致性
    validation = validate_rules(merged_rules)
    if not validation.valid:
        return CompileResult(success=False, errors=validation.errors)
    
    # 6. 生成SQL模板
    sql_templates = generate_sql_templates(merged_rules)
    
    # 7. 生成编译后配置
    compiled_config = {
        "version": generate_version(),
        "tenant_id": tenant_id,
        "industry": industry,
        "rules": merged_rules,
        "sql_templates": sql_templates,
        "compiled_at": datetime.now().isoformat()
    }
    
    # 8. 写入Redis
    await redis.setex(
        f"rules:{tenant_id}:latest",
        ttl=86400 * 7,  # 7天
        value=json.dumps(compiled_config)
    )
    
    # 9. 更新编译状态
    await postgres.execute("""
        UPDATE tenant_compile_status 
        SET status = 'SUCCESS', version = %s, updated_at = NOW()
        WHERE tenant_id = %s
    """, (compiled_config['version'], tenant_id))
    
    return CompileResult(success=True, version=compiled_config['version'])
```
