# loan_v1.4.ttl — 信贷指标本体 v1.4 (三层建模)

## 核心变化

v1.3 把指标建模为 `Individual`,v1.4 改成**三层结构**:

```
┌──────────────────────────────────────────────────────┐
│ 层 1 概念(Class)                                      │
│   yql:CurrentRatio a owl:Class                       │
│     rdfs:subClassOf yql:RatioIndicator               │
│     skos:closeMatch fibo-fnd-arr-rt:Ratio            │
│     dcterms:subject "偿债能力"                        │
└──────────────────────────────────────────────────────┘
                      ↑ computesIndicator
┌──────────────────────────────────────────────────────┐
│ 层 2 计算规则(Individual)                             │
│   rule:Rule_PRE_SOLV_01 a yql:CalculationRule        │
│     yql:computesIndicator yql:CurrentRatio           │
│     yql:hasFormula "流动资产/流动负债"                 │
│     yql:hasSQL """..."""                             │
│     yql:usesTable ncc:GL_BALANCE                     │
│     yql:mapsToField ncc:GL_BALANCE__LOCALDEBITAMOUNT │
│     yql:appliedInScenario scn:PreLoanDD              │
│     yql:ruleVersion "1.0"                            │
│     yql:effectiveFrom "2024-01-01"                   │
└──────────────────────────────────────────────────────┘
                      ↑ ofIndicator / byRule
┌──────────────────────────────────────────────────────┐
│ 层 3 指标取值(Individual,运行时插入)                   │
│   val:Value_CurrentRatio_ORG001_202412               │
│     a yql:IndicatorValue                             │
│     yql:ofIndicator yql:CurrentRatio                 │
│     yql:byRule rule:Rule_PRE_SOLV_01                 │
│     yql:forOrg "ORG001"                              │
│     yql:forPeriod "2024-12"                          │
│     yql:numericValue 1.82                            │
│     yql:computedAt "2025-01-05T10:00:00"             │
└──────────────────────────────────────────────────────┘
```

## 为什么分三层

| 设计考虑 | 单层(v1.3)做不到 | 三层(v1.4)的解决方式 |
|---|---|---|
| **多个 SQL 版本** | 指标=规则,无法支持"口径变更后新旧规则并存" | 同一概念下挂多条 Rule,用 `effectiveFrom`/`effectiveTo` 切换 |
| **存历史计算值** | 没有 Value 这类实体 | Value 承载 `机构+期间+数值+规则` 四元组 |
| **概念和实现解耦** | "流动比率"这个名称既是定义又是 SQL | Class 是概念,Rule 是实现,以后换个计算方法不需要改概念 |
| **FIBO 对齐更自然** | Individual 做 closeMatch 语义较弱 | Class 间做 closeMatch 是标准用法 |

## 实体统计

| 类别 | 数量 | 类型 |
|---|---|---|
| 指标概念 | 76 | owl:Class(层 1) |
| 指标顶层类 | 3 | RatioIndicator / AmountIndicator / CountIndicator |
| CalculationRule | 76 | Individual(层 2,1:1 对应概念) |
| IndicatorValue 示例 | 3 | Individual(层 3,联调示范) |
| NCC 数据表 | 22 | Individual |
| NCC 字段 | 93 | Individual |
| 会计科目 | 60 | Individual |
| 应用场景 | 3 | Individual |

## 核验通过项

- ✅ 76 个指标概念,全部 `subClassOf` 顶层三类之一
- ✅ 76 条规则,全部带 `yql:hasSQL` + `yql:computesIndicator`
- ✅ 概念↔规则 1:1 双向一致(无孤立概念,无重复规则)
- ✅ 3 条 Value 示例引用的概念和规则都存在
- ✅ SQL 字段 0 幻觉(对照 tables.json 真实 DDL)
- ✅ FIBO 引用 7 种,全部在白名单
- ✅ mapsToField 引用 93 个字段,全部声明

## 代理服务调用流程(更新版)

### 原来(v1.3)

```
代理 → 查 yql:Indicator_XXX → 取 yql:hasSQL → 执行
```

### 现在(v1.4)

```
代理 → 根据意图找到 yql:CurrentRatio 这个概念
     → 查对应的生效中 Rule(按 effectiveFrom/To 过滤)
     → 取 rule:Rule_*.yql:hasSQL → 执行
     → (可选)把结果插入为一条 IndicatorValue
```

推荐用下面这个 SPARQL 模板**取当前生效的 SQL**:

```sparql
PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?rule ?sql WHERE {
  ?rule yql:computesIndicator yql:CurrentRatio ;
        yql:hasSQL ?sql ;
        yql:effectiveFrom ?from .
  OPTIONAL { ?rule yql:effectiveTo ?to }
  FILTER(?from <= "2024-12-31"^^xsd:date &&
         (!BOUND(?to) || ?to >= "2024-12-31"^^xsd:date))
}
```

## 应用如何写入计算值

代理或离线任务计算完一个值后,用 SPARQL UPDATE 把结果插入图谱:

```sparql
PREFIX val: <http://yql.example.com/ontology/indicator-value/>
PREFIX yql: <http://yql.example.com/ontology/credit-risk/>
PREFIX rule: <http://yql.example.com/ontology/calculation-rule/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

INSERT DATA {
  val:Value_CurrentRatio_ORG042_202501 a yql:IndicatorValue ;
    yql:ofIndicator yql:CurrentRatio ;
    yql:byRule rule:Rule_PRE_SOLV_01 ;
    yql:forOrg "ORG042" ;
    yql:forPeriod "2025-01" ;
    yql:numericValue "2.15"^^xsd:decimal ;
    yql:computedAt "2025-02-01T02:30:00"^^xsd:dateTime .
}
```

Value 的 IRI 命名建议:`val:Value_{IndicatorClass}_{Org}_{YYYYMM}`,保证唯一且可读。

## 常用查询(给代理/前端参考)

### 1. 查询某指标的历史趋势(12 期)

```sparql
SELECT ?period ?value WHERE {
  ?v yql:ofIndicator yql:CurrentRatio ;
     yql:forOrg "ORG001" ;
     yql:forPeriod ?period ;
     yql:numericValue ?value .
} ORDER BY ?period
```

### 2. 查询某机构某期所有指标(仪表板用)

```sparql
SELECT ?indicatorName ?value ?topic WHERE {
  ?v a yql:IndicatorValue ;
     yql:forOrg "ORG001" ;
     yql:forPeriod "2024-12" ;
     yql:ofIndicator ?i ;
     yql:numericValue ?value .
  ?i rdfs:label ?indicatorName ;
     dcterms:subject ?topic .
} ORDER BY ?topic ?indicatorName
```

### 3. 查询所有「偿债能力」主题的指标

```sparql
SELECT ?label WHERE {
  ?c dcterms:subject "偿债能力"@zh ;
     rdfs:label ?label .
}
```

### 4. 查询某指标用到哪些表和字段(溯源)

```sparql
SELECT ?table ?field WHERE {
  ?rule yql:computesIndicator yql:CurrentRatio ;
        yql:usesTable ?t ;
        yql:mapsToField ?f .
  ?t rdfs:label ?table .
  ?f rdfs:label ?field .
}
```

## 升级迁移要点

**如果您已经导入 v1.3**,不要直接覆盖。步骤:

1. **清空 GraphDB 旧仓库**(Setup → Repositories → 选仓库 → Clear)
2. **导入 v1.4**
3. **验证**:执行 `SELECT (COUNT(*) AS ?n) WHERE { ?c rdfs:subClassOf yql:Indicator }` 应返回 76+3=79

**如果应用层已有调用 v1.3 的代码**,接口需要调整:

- 原 `yql:Indicator_PRE_SOLV_01` 类型 Individual → 现 `yql:CurrentRatio` 类型 Class
- 原 `yql:Indicator_XXX yql:hasSQL ?sql` → 现需 join `rule:Rule_XXX`
- 推荐保留 `skos:notation` 作为接口稳定 ID(如 "PRE-SOLV-01")

## 前端分面改造建议(独立任务)

这个 TTL 只解决了"本体结构更合理",但"左侧列表太细"的视觉问题仍需前端分面改造。

建议您给前端同事提如下需求:

### 分面分组结构

```
实体列表
├─ 指标概念 (yql:Indicator 及其子类)(76 类)
│   ├─ 偿债能力(7)
│   ├─ 盈利能力(9)
│   ├─ 合同(7)
│   └─ ...(按 dcterms:subject 分组)
├─ 计算规则 (yql:CalculationRule)(76 条)
├─ 指标取值 (yql:IndicatorValue)(3+,运行时增长)
├─ 数据表 (yql:NCCTable)(22)
├─ 数据字段 (yql:NCCField)(93,按 yql:inTable 分组)
├─ 会计科目 (yql:AccountCode)(60,按前缀 1/2/4/6 分组)
└─ 场景 (yql:Scenario)(3)
```

### 每个分面的 SPARQL

**类型聚合查询**(进入图谱时调用一次):

```sparql
SELECT ?type (COUNT(DISTINCT ?s) AS ?cnt) WHERE {
  ?s a ?type .
  FILTER(?type IN (yql:Indicator, yql:CalculationRule, yql:IndicatorValue,
                   yql:NCCTable, yql:NCCField, yql:AccountCode, yql:Scenario))
} GROUP BY ?type
```

**指标概念按主题分组**(点开"指标概念"分面时):

```sparql
SELECT ?topic (COUNT(DISTINCT ?c) AS ?cnt) WHERE {
  ?c rdfs:subClassOf+ yql:Indicator ;
     dcterms:subject ?topic .
} GROUP BY ?topic ORDER BY DESC(?cnt)
```

**字段按归属表分组**(点开"字段"分面时):

```sparql
SELECT ?tableLabel (COUNT(DISTINCT ?f) AS ?cnt) WHERE {
  ?f a yql:NCCField ; yql:inTable ?t .
  ?t rdfs:label ?tableLabel .
} GROUP BY ?tableLabel ORDER BY DESC(?cnt)
```

## 历史版本

| 版本 | 文件 | 特点 |
|---|---|---|
| v1.1 | loan_v1.ttl | FIBO 白名单受控,71 指标全集 |
| v1.2 | loan_v1.2.ttl | 仅 A+B 档 34 指标 + 内嵌 SQL |
| v1.3 | loan_v1.3.ttl | 76 个难度=1 指标,label 带前缀 |
| **v1.4** | **loan_v1.4.ttl** | **三层建模(Class/Rule/Value)** |
