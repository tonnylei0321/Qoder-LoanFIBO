# GraphDB 同步 — 三元组生成逻辑设计文档

> 版本：v1.0  
> 日期：2026-04-20  
> 状态：设计评审中

---

## 1. 概述

### 1.1 目标

将 PostgreSQL 中经人工审核通过的映射结果（`table_mapping` + `field_mapping`），转化为 RDF 三元组，通过 GraphDB REST API 导入 Ontotext GraphDB，使映射关系在知识图谱中可查询、可钻取、可溯源。

### 1.2 核心定位

我们导入的**不是源系统的业务数据**（如某笔贷款的具体金额），而是**映射元数据**——即"这个表对应 FIBO 哪个类，这个字段对应 FIBO 哪个属性"的语义关联声明。

### 1.3 与现有 Pipeline 的关系

```
映射 Pipeline（已有）                    同步链路（新增）
┌─────────────────┐                  ┌──────────────────┐
│ DDL解析          │                  │ 发布版本快照      │
│ TTL索引          │                  │        ↓          │
│ LLM映射          │  →  审核通过  →   │ RDF三元组生成     │
│ 检核Agent        │                  │        ↓          │
│ 映射修订         │                  │ GraphDB导入       │
└─────────────────┘                  └──────────────────┘
     写入 PostgreSQL                     写入 GraphDB
```

同步链路与映射 Pipeline 完全解耦，不侵入已有节点。

---

## 2. 数据来源分析

### 2.1 输入数据模型

三元组的生成依赖以下 PostgreSQL 表中的数据：

| 表名 | 关键字段 | 用途 |
|------|---------|------|
| `table_mapping` | `database_name`, `table_name`, `fibo_class_uri`, `confidence_level`, `mapping_reason` | 表级映射：源表 → FIBO 类 |
| `field_mapping` | `field_name`, `field_type`, `fibo_property_uri`, `confidence_level`, `mapping_reason`, `proj_ext_uri` | 字段级映射：源字段 → FIBO 属性 |
| `table_registry` | `table_comment`, `parsed_fields`（含字段注释） | 源表注释、字段注释（溯源层需要） |
| `ontology_property_index` | `property_uri`, `property_type`（ObjectProperty / DatatypeProperty） | 判断属性类型决定三元组生成方式 |

### 2.2 数据过滤条件

仅以下状态的映射参与三元组生成：

- `table_mapping.review_status = 'approved'`（人工审核通过）
- `table_mapping.mapping_status = 'mapped'`（可映射，排除 unmappable）
- `field_mapping.confidence_level != 'UNRESOLVED'` 或字段仍生成溯源层三元组

---

## 3. 三层三元组生成模型

我们将映射结果转化为 RDF 三元组时，采用**分层递进**的设计：

```
┌─────────────────────────────────────────────────────────────┐
│ 第1层：实体声明层（表级）                                      │
│   声明：源系统表对应 FIBO 本体中的哪个类                        │
├─────────────────────────────────────────────────────────────┤
│ 第2层：属性映射层（字段级）                                    │
│   声明：源系统字段对应 FIBO 本体中的哪个属性                     │
├─────────────────────────────────────────────────────────────┤
│ 第3层：映射溯源层（元数据标注）                                │
│   标注：映射从哪来、质量如何、置信度多少                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 第1层：实体声明层

### 4.1 核心三元组

**数据来源**：`table_mapping` 表

**生成规则**：每条审核通过的 `table_mapping` 记录，生成一个实体声明三元组：

```turtle
<实体URI>  rdf:type  <fibo_class_uri>
```

### 4.2 实体 URI 的构造方案

实体 URI 是三元组中的主语（Subject），其构造方案是设计的关键决策点。

| 方案 | 实体 URI 示例 | 特点 |
|------|-------------|------|
| A. 数据库+表名直接构造 | `urn:loanfibo:iuap_apdoc_basedoc:bd_bankacct_currency` | 简单，但不区分版本 |
| B. 版本+数据库+表名 | `urn:loanfibo:v1:iuap_apdoc_basedoc:bd_bankacct_currency` | 版本隔离，但不同版本的同一表是不同实体 |
| C. 数据库+表名为主体 + 命名图区分版本 | `urn:loanfibo:iuap_apdoc_basedoc:bd_bankacct_currency` | **推荐**：同一表始终是同一实体，版本差异通过命名图隔离 |

**推荐方案 C**，理由：
- 同一源表在不同版本中语义一致，不应视为不同实体
- 版本差异通过命名图（Named Graph）隔离，支持版本间对比
- 未来版本切换时无需合并实体，只需切换查询的命名图

### 4.3 生成示例

以表 `iuap_apdoc_basedoc.bd_bankacct_currency` 为例：

```turtle
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix fibo-fbc-pas-caa: <https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/ClientsAndAccounts/> .
@prefix src:     <urn:loanfibo:source:> .

# 第1层：实体声明
src:iuap_apdoc_basedoc/bd_bankacct_currency
    rdf:type  fibo-fbc-pas-caa:BankAccountCurrency .
```

**说明**：
- `src:iuap_apdoc_basedoc/bd_bankacct_currency` 是我们系统构造的实体 URI
- `fibo-fbc-pas-caa:BankAccountCurrency` 是 FIBO 本体中已存在的类 URI
- 这条三元组声明了"这个源系统表对应 FIBO 中的 BankAccountCurrency 类"

---

## 5. 第2层：属性映射层

### 5.1 核心问题

**数据来源**：`field_mapping` 表

**生成规则**：对每条 `field_mapping`，根据 `fibo_property_uri` 的**属性类型**（ObjectProperty vs DatatypeProperty），生成不同的三元组。

属性类型需要从 `ontology_property_index` 表中查询：

```sql
SELECT property_type FROM ontology_property_index 
WHERE property_uri = 'https://spec.edmcouncil.org/fibo/.../hasCurrency'
-- 返回：'DatatypeProperty' 或 'ObjectProperty'
```

### 5.2 场景 A：DatatypeProperty（数据属性映射）

当 `fibo_property_uri` 指向一个 DatatypeProperty 时，三元组表达的是"实体的某个数据属性来源于源系统的某个字段"。

#### 方案对比

| 方案 | 三元组示例 | 特点 |
|------|-----------|------|
| A. 源字段 URI 占位 | `src:entity fibo:hasProperty src:entity/field` | 保留可导航性，未来可替换为实际值 |
| B. 字面量标注 | `src:entity fibo:hasProperty "field_name"^^loanfibo:SourceField` | 简洁，但丢失了字段级溯源能力 |

**推荐方案 A**（源字段 URI 占位）：

```turtle
src:iuap_apdoc_basedoc/bd_bankacct_currency
    fibo-fbc-pas-caa:hasCurrency      src:iuap_apdoc_basedoc/bd_bankacct_currency/currency ;
    fibo-fbc-pas-caa:hasAccountStatus src:iuap_apdoc_basedoc/bd_bankacct_currency/enable .
```

**优势**：
- 保留了对端实体的可导航性
- 前端钻取时可以知道"这个值来自哪个字段"
- 未来接入真实业务数据时，可以无缝替换占位 URI 为实际值

### 5.3 场景 B：ObjectProperty（对象属性映射）

当 `fibo_property_uri` 指向一个 ObjectProperty 时，三元组表达的是**实体间的关联关系**。

#### 示例场景

假设 `bd_loan_guarantee` 表（贷款担保表）映射到 `LoanCollateral` 类，其中 `guarantor_id` 字段映射到 `hasGuarantor` 属性：

```turtle
src:iuap_fi_loan/bd_loan_guarantee
    fibo-loan-ln-mcg:hasGuarantor  src:iuap_fi_basedoc/bd_corp_info .
```

**问题**：右侧 URI 指向的应该是另一个已映射的源表实体（因为 `guarantor_id` 是外键指向 `bd_corp_info`）。

**当前限制**：
- 映射过程中未显式记录外键关系
- LLM 仅根据字段名语义推断映射，不解析 DDL 中的外键约束

**处理策略**：
- **短期**：右侧 URI 暂用 `loanfibo:UnresolvedReference` 占位，或省略该三元组
- **长期**：增强 DDL 解析器，提取外键关系，建立实体间真实关联

### 5.4 场景 C：proj_ext_uri（项目扩展属性）

`field_mapping` 中的 `proj_ext_uri` 是 LLM 认为无法用标准 FIBO 属性映射、但可以用项目自定义扩展属性表达的字段。

```turtle
src:iuap_apdoc_basedoc/bd_bankacct_currency
    loanfibo:extFreezeControl  src:iuap_apdoc_basedoc/bd_bankacct_currency/freeze_control ;
    loanfibo:extFrozenAmount   src:iuap_apdoc_basedoc/bd_bankacct_currency/frozen_amount ;
    loanfibo:extFrozenState    src:iuap_apdoc_basedoc/bd_bankacct_currency/frozen_state .
```

---

## 6. 第3层：映射溯源层

### 6.1 目的

让 GraphDB 中的实体**可溯源**——知道映射从哪来、质量如何、置信度多少。

### 6.2 表级溯源三元组

```turtle
src:iuap_apdoc_basedoc/bd_bankacct_currency
    loanfibo:confidenceLevel     "HIGH" ;
    loanfibo:mappingReason       "该表记录企业银行账户币种信息，与FIBO BankAccountCurrency语义高度匹配" ;
    loanfibo:mappedByVersion     <urn:loanfibo:version:v1-credit-loan> ;
    loanfibo:sourceDatabase      "iuap_apdoc_basedoc" ;
    loanfibo:sourceTableName     "bd_bankacct_currency" ;
    loanfibo:sourceTableComment  "基础档案-企业银行账户币种子表" .
```

### 6.3 字段级溯源三元组

```turtle
# 字段级溯源详情
src:iuap_apdoc_basedoc/bd_bankacct_currency/currency
    rdf:type                       loanfibo:MappedField ;
    loanfibo:sourceFieldName       "currency" ;
    loanfibo:sourceFieldType       "varchar(36)" ;
    loanfibo:sourceFieldComment    "币种id" ;
    loanfibo:mappedProperty        fibo-fbc-pas-caa:hasCurrency ;
    loanfibo:confidenceLevel       "HIGH" .

src:iuap_apdoc_basedoc/bd_bankacct_currency/frozen_amount
    rdf:type                       loanfibo:MappedField ;
    loanfibo:sourceFieldName       "frozen_amount" ;
    loanfibo:sourceFieldType       "decimal(28,8)" ;
    loanfibo:sourceFieldComment    "冻结金额" ;
    loanfibo:mappedProperty        loanfibo:extFrozenAmount ;
    loanfibo:confidenceLevel       "MEDIUM" .
```

### 6.4 溯源属性定义

| 属性 URI | 值类型 | 说明 |
|----------|--------|------|
| `loanfibo:confidenceLevel` | xsd:string | 映射置信度：HIGH / MEDIUM / LOW / UNRESOLVED |
| `loanfibo:mappingReason` | xsd:string | 映射理由（LLM 生成或人工填写） |
| `loanfibo:mappedByVersion` | xsd:anyURI | 所属发布版本 |
| `loanfibo:sourceDatabase` | xsd:string | 源数据库名 |
| `loanfibo:sourceTableName` | xsd:string | 源表名 |
| `loanfibo:sourceTableComment` | xsd:string | 源表注释 |
| `loanfibo:sourceFieldName` | xsd:string | 源字段名 |
| `loanfibo:sourceFieldType` | xsd:string | 源字段类型 |
| `loanfibo:sourceFieldComment` | xsd:string | 源字段注释 |
| `loanfibo:mappedProperty` | xsd:anyURI | 映射到的 FIBO 属性 URI |

---

## 7. 完整示例：一张表生成的所有三元组

以 `bd_bankacct_currency`（企业银行账户币种子表）为例，假设映射结果如下：

| 层级 | 映射内容 |
|------|---------|
| 表级 | `fibo_class_uri` = `https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/ClientsAndAccounts/BankAccountCurrency` |
| 字段1 | `currency` → `fibo-fbc-pas-caa:hasCurrency` (DatatypeProperty) |
| 字段2 | `enable` → `fibo-fbc-pas-caa:hasAccountStatus` (DatatypeProperty) |
| 字段3 | `frozen_amount` → `loanfibo:extFrozenAmount` (项目扩展) |

生成的完整 Turtle：

```turtle
@prefix rdf:       <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:      <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:       <http://www.w3.org/2002/07/owl#> .
@prefix xsd:       <http://www.w3.org/2001/XMLSchema#> .
@prefix fibo-fbc:  <https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/ClientsAndAccounts/> .
@prefix loanfibo:  <urn:loanfibo:ontology:> .
@prefix src:       <urn:loanfibo:source:> .

# ============================================================
# 第1层：实体声明
# ============================================================
src:iuap_apdoc_basedoc/bd_bankacct_currency
    rdf:type                       fibo-fbc:BankAccountCurrency .

# ============================================================
# 第2层：属性映射
# ============================================================
src:iuap_apdoc_basedoc/bd_bankacct_currency
    fibo-fbc:hasCurrency            src:iuap_apdoc_basedoc/bd_bankacct_currency/currency ;
    fibo-fbc:hasAccountStatus       src:iuap_apdoc_basedoc/bd_bankacct_currency/enable ;
    loanfibo:extFrozenAmount        src:iuap_apdoc_basedoc/bd_bankacct_currency/frozen_amount .

# ============================================================
# 第3层：表级溯源
# ============================================================
src:iuap_apdoc_basedoc/bd_bankacct_currency
    loanfibo:confidenceLevel        "HIGH"^^xsd:string ;
    loanfibo:mappingReason          "该表记录企业银行账户币种信息，与FIBO BankAccountCurrency语义高度匹配"^^xsd:string ;
    loanfibo:mappedByVersion        <urn:loanfibo:version:v1-credit-loan> ;
    loanfibo:sourceDatabase         "iuap_apdoc_basedoc"^^xsd:string ;
    loanfibo:sourceTableName        "bd_bankacct_currency"^^xsd:string ;
    loanfibo:sourceTableComment     "基础档案-企业银行账户币种子表"^^xsd:string .

# ============================================================
# 第3层：字段级溯源
# ============================================================
src:iuap_apdoc_basedoc/bd_bankacct_currency/currency
    rdf:type                       loanfibo:MappedField ;
    loanfibo:sourceFieldName       "currency"^^xsd:string ;
    loanfibo:sourceFieldType       "varchar(36)"^^xsd:string ;
    loanfibo:sourceFieldComment    "币种id"^^xsd:string ;
    loanfibo:mappedProperty        fibo-fbc:hasCurrency ;
    loanfibo:confidenceLevel       "HIGH"^^xsd:string .

src:iuap_apdoc_basedoc/bd_bankacct_currency/enable
    rdf:type                       loanfibo:MappedField ;
    loanfibo:sourceFieldName       "enable"^^xsd:string ;
    loanfibo:sourceFieldType       "int"^^xsd:string ;
    loanfibo:sourceFieldComment    "启用状态"^^xsd:string ;
    loanfibo:mappedProperty        fibo-fbc:hasAccountStatus ;
    loanfibo:confidenceLevel       "HIGH"^^xsd:string .

src:iuap_apdoc_basedoc/bd_bankacct_currency/frozen_amount
    rdf:type                       loanfibo:MappedField ;
    loanfibo:sourceFieldName       "frozen_amount"^^xsd:string ;
    loanfibo:sourceFieldType       "decimal(28,8)"^^xsd:string ;
    loanfibo:sourceFieldComment    "冻结金额"^^xsd:string ;
    loanfibo:mappedProperty        loanfibo:extFrozenAmount ;
    loanfibo:confidenceLevel       "MEDIUM"^^xsd:string .
```

---

## 8. 命名图组织策略

### 8.1 命名图设计

所有映射三元组写入**版本对应的命名图**，与 FIBO 本体数据隔离：

| 数据类型 | 命名图 | 来源 |
|----------|--------|------|
| FIBO 本体数据 | `urn:fibo:FBC/ProductsAndServices/ClientsAndAccounts` 等 | `load_fibo_to_graphdb.sh` 加载 |
| 映射元数据 v1.0 | `urn:loanfibo:credit-loan:version:1` | 同步任务生成 |
| 映射元数据 v1.1 | `urn:loanfibo:credit-loan:version:2` | 同步任务生成 |

### 8.2 跨命名图查询示例

查询"BankAccountCurrency 类的所有实例及其映射来源"：

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX fibo-fbc: <https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/ClientsAndAccounts/>
PREFIX loanfibo: <urn:loanfibo:ontology:>

SELECT ?entity ?sourceDb ?sourceTable ?confidence
FROM NAMED <urn:loanfibo:credit-loan:version:1>
WHERE {
    GRAPH ?g {
        ?entity rdf:type fibo-fbc:BankAccountCurrency ;
                loanfibo:sourceDatabase ?sourceDb ;
                loanfibo:sourceTableName ?sourceTable ;
                loanfibo:confidenceLevel ?confidence .
    }
}
```

---

## 9. Upsert vs Replace 的三元组行为

| 操作 | SPARQL 行为 | 命名图影响 |
|------|-----------|-----------|
| **Upsert** | 对每个实体执行 `DELETE { ?s ?p ?o } INSERT { ?s ?p ?newO } WHERE { ?s ?p ?o }` | 保留其他版本数据，仅更新当前版本的命名图 |
| **Replace** | `DROP GRAPH <urn:loanfibo:xxx:version:N>` 然后重新 `INSERT DATA` | 整个版本命名图清空重建 |

### 9.1 适用场景

| 模式 | 适用场景 |
|------|---------|
| Upsert | 增量更新，只修改部分映射，保留历史版本 |
| Replace | 版本重构，重新发布整个映射版本 |

---

## 10. 边界问题处理

### 10.1 UNRESOLVED 字段

- `confidence_level = 'UNRESOLVED'` 的字段**不生成第2层三元组**
- 但仍生成第3层溯源三元组，标注为未映射

```turtle
src:iuap_apdoc_basedoc/bd_bankacct_currency/def01
    rdf:type                       loanfibo:MappedField ;
    loanfibo:sourceFieldName       "def01"^^xsd:string ;
    loanfibo:sourceFieldType       "varchar(255)"^^xsd:string ;
    loanfibo:sourceFieldComment    "备用字段1"^^xsd:string ;
    loanfibo:mappedProperty        loanfibo:Unresolved ;
    loanfibo:confidenceLevel       "UNRESOLVED"^^xsd:string .
```

### 10.2 unmappable 表

- `mapping_status = 'unmappable'` 的表**不生成任何三元组**
- 审核时已排除，不会进入发布版本

### 10.3 ObjectProperty 的对端

- 当前映射不记录外键关系
- ObjectProperty 映射的右侧 URI 暂用 `loanfibo:UnresolvedReference` 占位
- 后续可增强 DDL 解析器，提取外键关系

### 10.4 主键字段

- `is_primary_key = true` 的字段，额外生成：

```turtle
src:iuap_apdoc_basedoc/bd_bankacct_currency/id
    loanfibo:isPrimaryKey  true .
```

---

## 11. 待确认问题

1. **第2层属性映射**：DatatypeProperty 的值用"源字段 URI 占位"的方式，还是用字面量（literal）更合适？
   - 当前推荐：源字段 URI 占位

2. **ObjectProperty 的对端**：是现在就处理（需要额外推断外键关系），还是先占位后续再增强？
   - 当前推荐：先占位（`loanfibo:UnresolvedReference`），后续增强

---

## 12. 附录：命名空间前缀表

| 前缀 | URI | 说明 |
|------|-----|------|
| `rdf` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` | RDF 核心词汇 |
| `rdfs` | `http://www.w3.org/2000/01/rdf-schema#` | RDF Schema |
| `owl` | `http://www.w3.org/2002/07/owl#` | OWL 本体语言 |
| `xsd` | `http://www.w3.org/2001/XMLSchema#` | XML Schema 数据类型 |
| `fibo-*` | `https://spec.edmcouncil.org/fibo/ontology/...` | FIBO 本体命名空间（按模块） |
| `loanfibo` | `urn:loanfibo:ontology:` | LoanFIBO 项目自定义词汇 |
| `src` | `urn:loanfibo:source:` | 源系统实体 URI 前缀 |
