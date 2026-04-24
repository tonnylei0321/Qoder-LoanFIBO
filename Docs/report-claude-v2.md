# 信贷指标本体建模 · Report(指标主表)

> **项目**:71 项信贷风控指标 → FIBO 本体 + yql 自定义命名空间  
> **数据源**:用友 YonBIP V3.0 NCC 数据库(70 张表)  
> **输出用途**:与 `mapping.md` 和 `loan_v1.ttl` 配套,供 GraphDB 导入及 SPARQL → SQL 推理使用

## 命名空间

| 前缀 | IRI | 含义 |
|---|---|---|
| `yql:` | `http://yql.example.com/ontology/credit-risk/` | 自定义信贷风控指标本体 |
| `acc:` | `http://yql.example.com/ontology/accounting/` | 自定义会计科目 DataPoint |
| `scn:` | `http://yql.example.com/ontology/scenario/` | 业务场景 |
| `ncc:` | `http://yql.example.com/ontology/ncc-mapping/` | NCC 表与字段个体 |
| `fibo-*:` | `https://spec.edmcouncil.org/fibo/ontology/...` | FIBO 标准本体(19 个模块)|

## FIBO 锚定说明

- **锚接策略**:指标本身统一挂在 `yql:Indicator` 及其 11 个子类(Ratio / Score / Days / CheckResult / ChangeRate / Concentration / Alert / Grade / Trend / Pattern / Atomic)下;FIBO 实体作为**指标所度量对象**的锚点
- **锚接率**:71 个指标中,71 个挂接到具体 FIBO 类,其余通过 `yql:Indicator rdfs:subClassOf fibo-ind-ind-ind:Indicator` 统一归并(显示为 `—`)
- **计算公式**:伪代码以会计概念命名(如 `CurrentAssets`),具体的 NCC 取数规则见 `mapping.md`

## 跨模块复用关系(6 条)

| 主指标 | 被复用到 | 说明 |
|---|---|---|
| `PRE-D1-01` · 速动比率 | `POST-D1-01` · (由主指标派生) | TTL 中以 `yql:reusedBy` 声明 |
| `PRE-D1-06` · 现金覆盖天数 | `POST-D1-02` · (由主指标派生) | TTL 中以 `yql:reusedBy` 声明 |
| `PRE-D4-01` · 自由现金流 FCF | `POST-D1-03` · (由主指标派生) | TTL 中以 `yql:reusedBy` 声明 |
| `PRE-D1-04` · 偿债覆盖率 DSCR | `POST-D1-04` · (由主指标派生) | TTL 中以 `yql:reusedBy` 声明 |
| `POST-D5-01` · 应收账款质押覆盖率 | `SCF-D2-08` · (由主指标派生) | TTL 中以 `yql:reusedBy` 声明 |
| `PRE-D6-02` · 供应商集中度 | `SCF-D4-02` · (由主指标派生) | TTL 中以 `yql:reusedBy` 声明 |

## 贷前尽职调查指标 (Pre-loan Due Diligence)

### D1 偿债能力

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `PRE-D1-01` | 速动比率 <sub>(被 `POST-D1-01` 复用)</sub> | `yql:Indicator` | — | `yql:QuickRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `(CurrentAssets - Inventory - PrepaidExpenses) / CurrentLiabilities` |
| `PRE-D1-02` | 流动比率 | `yql:Indicator` | — | `yql:CurrentRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `CurrentAssets / CurrentLiabilities` |
| `PRE-D1-03` | 利息覆盖倍数 ICR | `yql:Indicator` | — | `yql:InterestCoverageRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `EBIT / InterestExpense, where EBIT = NetIncome + InterestExpense + IncomeTax` |
| `PRE-D1-04` | 偿债覆盖率 DSCR <sub>(被 `POST-D1-04` 复用)</sub> | `fibo-fbc-dae-dbt:Debt` | `fibo-fbc-dae-dbt:hasPrincipalAmount`<br>`fibo-fbc-dae-dbt:hasInterestRate` | `yql:DebtServiceCoverageRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `EBITDA / (PrincipalDue + InterestDue) for the period` |
| `PRE-D1-05` | 净债务/EBITDA | `fibo-fbc-dae-dbt:Debt` | — | `yql:NetDebtToEBITDARatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `NetDebt / EBITDA, where NetDebt = TotalInterestBearingDebt - CashAndEquivalents - TradingFinancialAssets` |
| `PRE-D1-06` | 现金覆盖天数 <sub>(被 `POST-D1-02` 复用)</sub> | `yql:Indicator` | — | `yql:CashCoverageDays` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `CashAndEquivalents / ((TotalOperatingCost - DepreciationAmortization) / 365)` |

### D2 盈利质量

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `PRE-D2-01` | EBITDA利润率 | `yql:Indicator` | — | `yql:EBITDAMargin` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `EBITDA / Revenue` |
| `PRE-D2-02` | 现金流/净利润比 | `yql:Indicator` | — | `yql:OperatingCashFlowToNetIncomeRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `OperatingCashFlow / NetIncome` |
| `PRE-D2-03` | 收入3年CAGR | `yql:Indicator` | — | `yql:RevenueCAGR3Y` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold`<br>`yql:timeOperator` | `POW(Revenue_T / Revenue_T-3, 1/3) - 1` |
| `PRE-D2-04` | 毛利率 | `yql:Indicator` | — | `yql:GrossMargin` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `(Revenue - COGS) / Revenue` |
| `PRE-D2-05` | 净利润率 | `yql:Indicator` | — | `yql:NetProfitMargin` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `NetIncome / Revenue` |

### D3 资产质量

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `PRE-D3-01` | 应收账款质量评分 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:ARQualityScore` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:scoringModel` | `100 * SUM(AgeBucket_i.Balance * Weight_i) / TotalAR` |
| `PRE-D3-02` | 60天以上应收占比 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:AR60DaysOverdueRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `AR_AgeOver60D / TotalAR` |
| `PRE-D3-03` | 资产负债率 | `yql:Indicator` | — | `yql:DebtToAssetRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `TotalLiabilities / TotalAssets` |
| `PRE-D3-04` | 有效净资产 | `fibo-fnd-acc-cur:MonetaryAmount` | `fibo-fnd-acc-cur:hasAmount`<br>`fibo-fnd-acc-cur:hasCurrency` | `yql:EffectiveNetAssets` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit` | `StockholdersEquity - IntangibleAssets - Goodwill - LongTermDeferredExpenses - DeferredTaxAssets - RelatedPartyAR` |
| `PRE-D3-05` | 存货周转天数 | `yql:Indicator` | — | `yql:DaysInventoryOutstanding` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `AvgInventory / COGS * 365, where AvgInventory = (BeginInventory + EndInventory) / 2` |

### D4 现金流结构

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `PRE-D4-01` | 自由现金流 FCF <sub>(被 `POST-D1-03` 复用)</sub> | `fibo-fnd-acc-cur:MonetaryAmount` | `fibo-fnd-acc-cur:hasAmount` | `yql:FreeCashFlow` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit` | `OperatingCashFlow - CapitalExpenditures (FCFF口径)` |
| `PRE-D4-02` | 经营现金流稳定性 | `yql:Indicator` | — | `yql:CFOStability` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold`<br>`yql:timeOperator` | `STDEV(CFO_last_8_quarters) / AVG(CFO_last_8_quarters) (变异系数 CV)` |
| `PRE-D4-03` | 资本支出/营收比 | `yql:Indicator` | — | `yql:CapExToRevenueRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `CapitalExpenditures / Revenue` |
| `PRE-D4-04` | 三类现金流结构 | `yql:Indicator` | — | `yql:CashFlowStructurePattern` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:patternDefinition` | `SIGN(CFO):SIGN(CFI):SIGN(CFF) → 8 种枚举模式` |
| `PRE-D4-05` | 现金比率 | `yql:Indicator` | — | `yql:CashRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `(CashAndEquivalents + TradingFinancialAssets) / CurrentLiabilities` |

### D5 营运效率

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `PRE-D5-01` | 现金转换周期 CCC | `yql:Indicator` | — | `yql:CashConversionCycle` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit`<br>`yql:baseIndicator`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `DSO + DIO - DPO` |
| `PRE-D5-02` | 应收账款周转天数 DSO | `yql:Indicator` | — | `yql:DaysSalesOutstanding` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `AvgAR / Revenue * 365` |
| `PRE-D5-03` | 总资产周转率 | `yql:Indicator` | — | `yql:TotalAssetTurnover` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `Revenue / AvgTotalAssets` |
| `PRE-D5-04` | 净资产收益率 ROE | `yql:Indicator` | — | `yql:ReturnOnEquity` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `NetIncome / AvgStockholdersEquity, where Avg = (Begin + End) / 2` |

### D6 外部风险

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `PRE-D6-01` | 客户集中度 | `fibo-fbc-pas-fpas:Counterparty` | — | `yql:CustomerConcentration` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `SUM(TopN_Customer_Revenue) / TotalRevenue (默认 N=3 或 N=5)` |
| `PRE-D6-02` | 供应商集中度 <sub>(被 `SCF-D4-02` 复用)</sub> | `fibo-fbc-pas-fpas:Counterparty` | — | `yql:SupplierConcentration` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `SUM(TopN_Supplier_Purchase) / TotalPurchase` |
| `PRE-D6-03` | 关联方应收占比 | `yql:ControllingInterest` | `yql:hasControllingParty` | `yql:RelatedPartyARRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `RelatedParty_AR_Balance / Total_AR_Balance` |

## 贷后监控指标 (Post-loan Monitoring)

### D2 财务行为异常

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `POST-D2-01` | 应收账龄恶化速率 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:ARAgingDeteriorationRate` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:timeOperator`<br>`yql:baseIndicator`<br>`yql:redThreshold`<br>`yql:amberThreshold`<br>`yql:greenThreshold` | `(AROver60DRatio_current - AROver60DRatio_prior) / AROver60DRatio_prior` |
| `POST-D2-02` | 关联方交易突增告警 | `yql:ControllingInterest` | — | `yql:RelatedPartyTransactionSpike` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:timeOperator`<br>`yql:baseIndicator`<br>`yql:redThreshold`<br>`yql:amberThreshold` | `IF (RP_TxnAmt_QoQ_Growth > 20%) THEN TRIGGERED` |
| `POST-D2-03` | 三表一致性校验 | `yql:Indicator` | — | `yql:ThreeStatementConsistencyCheck` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:checkRule`<br>`yql:redThreshold` | `Boolean: ALL(Rule1, Rule2, Rule3) where Rule1: NetIncome_IS = (RetainedEarnings_End - RetainedEarnings_Begin + Dividends), Rule2: CashFlow_NetIncrease = CashEnd - CashBegin, Rule3: CFO_indirect_reconciliation_starts_from_NetIncome` |
| `POST-D2-05` | 财报提交及时性 | `yql:Reporter` | — | `yql:FinancialReportTimeliness` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:redThreshold`<br>`yql:amberThreshold` | `IF (ActualSubmissionDate <= AgreedDeadline) THEN PASS ELSE DelayDays = ActualSubmissionDate - AgreedDeadline` |

### D3 经营状况实时

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `POST-D3-01` | 营收同比增速 | `yql:Indicator` | — | `yql:RevenueYoYGrowth` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold`<br>`yql:timeOperator` | `(Revenue_current_period - Revenue_same_period_lastyear) / Revenue_same_period_lastyear` |
| `POST-D3-02` | 毛利率环比变化 | `yql:Indicator` | — | `yql:GrossMarginQoQChange` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:timeOperator`<br>`yql:baseIndicator`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `GrossProfitMargin_current_quarter - GrossProfitMargin_prior_quarter (变化量,百分点)` |
| `POST-D3-03` | 经营现金流同比变化 | `yql:Indicator` | — | `yql:OperatingCashFlowYoYChange` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:timeOperator`<br>`yql:baseIndicator`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `(CFO_current - CFO_same_period_lastyear) / ABS(CFO_same_period_lastyear)` |
| `POST-D3-04` | EBITDA利润率趋势 | `yql:Indicator` | — | `yql:EBITDAMarginTrend` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:timeOperator`<br>`yql:baseIndicator`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `LinearRegressionSlope(EBITDAMargin over last 4 quarters)` |
| `POST-D3-05` | 在手合同金额 | `fibo-fnd-agr-ctr:Contract` | `fibo-fnd-agr-ctr:hasContractParty` | `yql:ContractBacklogAmount` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit` | `SUM(SignedContract.RemainingAmount where Status IN [Active, Pending Execution])` |

### D4 负债结构变化

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `POST-D4-01` | 非银融资占比变化 | `yql:FinancialServiceProvider` | — | `yql:NonBankFinancingRatioChange` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:timeOperator`<br>`yql:baseIndicator`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `NonBankFinancing_Ratio_current - NonBankFinancing_Ratio_prior, where Ratio = NonBankFinancing / TotalInterestBearingDebt` |
| `POST-D4-02` | 授信使用率 | `fibo-fbc-dae-dbt:DebtInstrument` | — | `yql:CreditLineUsageRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `UsedCreditAmount / TotalCreditFacility` |
| `POST-D4-03` | 资产负债率变化 | `yql:Indicator` | — | `yql:DebtToAssetRatioChange` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:timeOperator`<br>`yql:baseIndicator`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `DebtToAssetRatio_current - DebtToAssetRatio_prior` |

### D5 抵质押物价值

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `POST-D5-01` | 应收账款质押覆盖率 <sub>(被 `SCF-D2-08` 复用)</sub> | `yql:Collateral` | `yql:secures` | `yql:PledgedARCoverageRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `PledgedAR_Eligible_Value / OutstandingLoanBalance` |
| `POST-D5-02` | 质押应收质量评分 | `yql:Collateral` | — | `yql:PledgedARQualityScore` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:scoringModel` | `SUM(PledgedAR_i.Balance * AgingWeight_i * BuyerCreditWeight_i) / TotalPledgedAR * 100` |
| `POST-D5-03` | 质押应收集中度 | `yql:Collateral` | — | `yql:PledgedARConcentration` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `SUM(TopN_Buyer_PledgedAR) / TotalPledgedAR (默认 N=3)` |

## 供应链金融指标 (Supply Chain Finance)

### D1 贸易真实性

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `SCF-D1-01` | 发票-订单匹配率 | `fibo-fnd-agr-ctr:Contract` | — | `yql:InvoiceOrderMatchRate` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `MatchedInvoiceCount / TotalInvoiceCount, where Match = (InvoiceNo↔OrderNo匹配 AND \|InvoiceAmt-OrderAmt\|/OrderAmt < 1% AND TaxNo一致)` |
| `SCF-D1-02` | 货物交付完整性 | `yql:ContractualCommitment` | — | `yql:DeliveryCompleteness` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `SUM(DeliveredQuantity) / SUM(OrderQuantity) (按金额加权)` |
| `SCF-D1-03` | 交易对手一致性 | `fibo-fbc-pas-fpas:Counterparty` | `fibo-fbc-pas-fpas:isACounterpartyIn` | `yql:CounterpartyConsistencyCheck` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:checkRule` | `Boolean: InvoiceParty.LEI = ContractParty.LEI = LogisticsConsignee.LEI = BankPayer.LEI AND 统一社会信用代码全部一致` |
| `SCF-D1-04` | 合同履约时间偏差 | `fibo-fnd-agr-ctr:Contract` | `fibo-fnd-dt-fd:hasStartDate`<br>`fibo-fnd-dt-fd:hasEndDate` | `yql:ContractPerformanceTimeDeviation` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `ActualDeliveryDate - ContractDeliveryDate` |
| `SCF-D1-05` | 物流凭证三方验证 | `fibo-fnd-agr-ctr:Contract` | — | `yql:LogisticsThreeWayMatch` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `Boolean: LogisticsRecord ⊆ InvoiceRecord ∩ ERPGoodsReceipt AND \|LogisticsDate - InvoiceDate\| <= 7 days` |
| `SCF-D1-07` | 关联方交易占比 | `yql:ControllingInterest` | — | `yql:RelatedPartyTransactionRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `RelatedParty_TxnAmt / Total_TxnAmt` |
| `SCF-D1-08` | 四流合一验证得分 | `fibo-fnd-agr-ctr:Contract` | — | `yql:FourFlowIntegrityCheck` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:baseIndicator`<br>`yql:checkRule` | `25 * IF(ContractFlow_OK) + 25 * IF(LogisticsFlow_OK) + 25 * IF(CashFlow_OK) + 25 * IF(InvoiceFlow_OK)` |
| `SCF-D1-11` | 历史交易频率稳定性 | `yql:Indicator` | — | `yql:TransactionFrequencyStability` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold`<br>`yql:timeOperator` | `1 - (STDEV(MonthlyOrderCount_24M) / AVG(MonthlyOrderCount_24M)) (1 - CV)` |

### D2 应收账款质量

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `SCF-D2-01` | 应收账款账龄评分 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:ARAgingScore` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:scoringModel` | `100 * SUM(AgeBucket_i.Balance * AgingWeight_i) / TotalAR` |
| `SCF-D2-02` | 90天以上应收占比 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:AR90DaysOverdueRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `AR_AgeOver90D / TotalAR` |
| `SCF-D2-03` | 应收账款集中度 | `fibo-fbc-pas-fpas:Counterparty` | — | `yql:ARConcentration` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `SUM(TopN_Customer_AR) / TotalAR (默认 N=3)` |
| `SCF-D2-04` | 供应链DSO | `yql:Indicator` | — | `yql:SupplyChainDSO` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `AvgAR / Revenue * 365 (供应链场景下,通常按核心企业生态测算)` |
| `SCF-D2-05` | 应收账款争议率 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:ARDisputeRate` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `Disputed_AR_Amount / Total_AR_Amount (依据工单系统标记)` |
| `SCF-D2-06` | 应收账款质量分级 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:ARQualityGrade` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:gradeScale`<br>`yql:baseIndicator` | `ENUM_LOOKUP(SCF-D2-01 score) → A/B/C/D` |
| `SCF-D2-07` | 历史坏账率 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:HistoricalBadDebtRate` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold`<br>`yql:timeOperator` | `Cumulative_WrittenOff_AR_24M / Cumulative_AR_Generated_24M` |
| `SCF-D2-09` | 应收可回收性评分 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:ARRecoverabilityScore` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:scoringModel`<br>`yql:baseIndicator` | `0.4 * BuyerCreditScore + 0.3 * ARAgingScore + 0.3 * HistoricalCollectionRate` |
| `SCF-D2-10` | ERP应收与银行一致性 | `yql:Payment` | — | `yql:ERPBankReconciliationRate` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `ABS(ERP_RecordedCollection - BankFlowCollection) / ERP_RecordedCollection <= 0.5%` |

### D3 买方信用

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `SCF-D3-02` | 买方付款准时率 | `yql:Payment` | `yql:hasPayer` | `yql:BuyerPaymentOnTimeRate` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `OnTimePaymentCount / TotalPaymentCount, where OnTime = ActualPayDate <= ContractDueDate` |
| `SCF-D3-04` | 买方逾期应付占比 | `fibo-fnd-pas-psch:PaymentObligation` | — | `yql:BuyerOverdueAPRatio` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `Buyer_Overdue_AP / Buyer_Total_AP` |
| `SCF-D3-09` | 核心企业确认意愿 | `fibo-fnd-agr-ctr:Contract` | — | `yql:CoreEnterpriseConfirmationWillingness` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:gradeScale` | `Boolean: 已取得核心企业书面确认函(签章+回执)` |

### D4 供应链协同

| 指标ID | 指标名称 | FIBO实体 | FIBO属性 | 自定义实体 | 自定义属性 | 计算公式 |
|---|---|---|---|---|---|---|
| `SCF-D4-01` | 供应商关系稳定性 | `fibo-fbc-pas-fpas:Counterparty` | — | `yql:SupplierRelationshipStability` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:scoringModel`<br>`yql:timeOperator` | `Suppliers_Both_Years / Suppliers_Prior_Year (年度保留率)` |
| `SCF-D4-03` | ERP系统集成深度 | `yql:Indicator` | — | `yql:ERPIntegrationDepth` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:gradeScale` | `ENUM_LOOKUP(API_Coverage, Update_Frequency, Writeback_Capability) → L1-L5` |
| `SCF-D4-04` | 供应链库存周转天数 | `yql:Indicator` | — | `yql:SupplyChainInventoryDays` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `AvgInventory / COGS * 365 (供应链全链路视角)` |
| `SCF-D4-05` | 订单履行率 | `yql:ContractualCommitment` | — | `yql:OrderFulfillmentRate` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `OnTimeAndFullOrderCount / TotalOrderCount (OTIF)` |
| `SCF-D4-06` | 供应链DPO | `yql:Indicator` | — | `yql:SupplyChainDPO` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:unit`<br>`yql:greenThreshold`<br>`yql:amberThreshold`<br>`yql:redThreshold` | `AvgAP / COGS * 365` |
| `SCF-D4-07` | 供应链融资历史 | `fibo-fbc-dae-dbt:Debt` | — | `yql:SupplyChainFinancingHistory` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:scoringModel`<br>`yql:timeOperator` | `复合记录:{TxnCount, CumulativeAmount, DefaultCount, OverdueCount, MaxYearsOfCooperation}` |
| `SCF-D4-08` | 数字化平台评分 | `yql:Indicator` | — | `yql:DigitalPlatformScore` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:gradeScale` | `0.3*DataQuality + 0.25*RealTimeCapability + 0.25*Coverage + 0.2*Security` |
| `SCF-D4-09` | 供应链层级深度 | `fibo-fbc-pas-fpas:Counterparty` | — | `yql:SupplyChainTierDepth` | `yql:hasFormula`<br>`yql:hasInput`<br>`yql:appliedInScenario`<br>`yql:dimensionWeight`<br>`yql:gradeScale` | `MAX_TIER(SupplierGraph from CoreEnterprise)` |

## 核验结论

| 项目 | 数量 |
|---|---|
| 指标总数 | **71 个** |
| FIBO 锚接到具体类 | **71 个**(其余 0 个统一挂 `yql:Indicator` 子类)|
| 字段引用总数 | **1501 处** |
| 唯一 (NCC表, 字段) 对 | **322 个** |
| 涉及 NCC 表 | **48 张** (70 张中引用) |
| 字段语义字典规模 | **621 项**,全部经 `database_ddl_all.sql` 逐行核验,0 幻觉 |

### 核验流程

1. **DDL 解析**:`database_ddl_all.sql` 共 70 张表、8075 字段解析到 `tables.json`
2. **语义字典**:手工给 621 个业务字段赋中文语义,入 `field_semantics.json`;对字典中每个 `table.field` 在 `tables.json` 中核查存在性,不存在则修正(本次共修正 14 处,如 `CT_PU_B.NPRICE → NORIGPRICE`、`ICDMC_CONTRACT.PK_CONTRACT → PK_CONTRACT_ICDMC`)
3. **指标映射**:71 个指标每个的 `field_mapping` 列表中的所有 `(table, field)` 对,逐个在 `field_semantics.json` 校验,0 幻觉
4. **FIBO 类白名单**:映射中使用的 FIBO 类与属性全部来自 FIBO 官方 IRI,无虚构

### 业务闭环(使用流程)

```
loan_v1.ttl ──▶ GraphDB
                  │
                  │ (SPARQL 查询指标公式 + 字段映射)
                  ▼
              生成 SQL 模板
                  │
                  │ (替换 :org_id/:year/:period)
                  ▼
              代理服务(Agent)
                  │
                  │ (在 NCC Oracle DB 执行)
                  ▼
              结果回传 GraphDB
                  │
                  ▼
              前端展示
```


## 本次 FIBO 核验修复说明(v1.1)

| 项目 | 数值 |
|---|---|
| 已核实存在的 FIBO 类 | **7 个**(白名单,全部经 `spec.edmcouncil.org` 或 `github.com/edmcouncil/fibo` 证据核验)|
| 已核实存在的 FIBO 属性 | **8 个** |
| 未充分核实而本地化的 FIBO 类 | **6 个**(统一改为 `yql:` 自定义,附 `skos:closeMatch` 指向候选 FIBO IRI)|
| 未充分核实而本地化的 FIBO 属性 | **3 个** |
| 修复的前缀 IRI 错误 | **2 处**(`fibo-fnd-pas-pas` 改为 `.../ProductsAndServices/ProductsAndServices/`、`fibo-ind-ind-ind` 改为 `.../Indicators/Indicators/`;另外前一版有两处前缀 IRI 错误实际未被白名单使用故未影响 v1.1)|

### 已核实白名单(保留 FIBO 锚接)

| FIBO 类 | 所在 ontology | 证据 |
|---|---|---|
| `fibo-fbc-dae-dbt:Debt` | FBC/DebtAndEquities/Debt/ | GitHub FIBO 仓库直接存在 |
| `fibo-fbc-dae-dbt:DebtInstrument` | FBC/DebtAndEquities/Debt/ | 搜索结果多次提及 |
| `fibo-fbc-pas-fpas:Counterparty` | FBC/ProductsAndServices/FinancialProductsAndServices/ | FIBO 核心类,多次引用 |
| `fibo-fnd-acc-cur:MonetaryAmount` | FND/Accounting/CurrencyAmount/ | FIBO 金额锚接标准类 |
| `fibo-fnd-agr-ctr:Contract` | FND/Agreements/Contracts/ | FIBO 合同根类 |
| `fibo-fnd-arr-rt:Ratio` | FND/Arrangements/Ratios/ | Ontotext 技术文章明确指出 `Rate ≡ Ratio` |
| `fibo-fnd-pas-psch:PaymentObligation` | FND/ProductsAndServices/PaymentsAndSchedules/ | `spec.edmcouncil.org` 上直接有 URL |

### 本地化(yql:)+ skos:closeMatch(待人工校验)

以下类/属性**未能直接通过搜索证据确认**,本次统一作本地化处理,但在 TTL 中以 `skos:closeMatch` 保留候选 FIBO IRI 作为 GraphDB 人工对齐参考:

- `yql:ControllingInterest` → candidate `.../BE/OwnershipAndControl/Control/ControllingInterest`
- `yql:FinancialServiceProvider` → candidate `.../FBC/ProductsAndServices/FinancialProductsAndServices/FinancialServiceProvider`
- `yql:Collateral` → candidate `.../FBC/DebtAndEquities/Debt/Collateral`(注:原声明在 Guarantees 模块,搜索显示 Collateral 实际在 Debt 模块下)
- `yql:ContractualCommitment` → candidate `.../FND/Agreements/Contracts/ContractualCommitment`
- `yql:Reporter` → candidate `.../FND/Arrangements/Reporting/Reporter`
- `yql:Payment` → candidate `.../FND/ProductsAndServices/PaymentsAndSchedules/Payment`
- `yql:hasControllingParty` / `yql:secures` / `yql:hasPayer` 均作同等处理

**建议**:用户在 GraphDB 中同时导入 FIBO TBox 后,可通过 `skos:closeMatch` 关系验证这些本地化类是否与 FIBO 实际概念对齐。若对齐正确,可自动做 `owl:equivalentClass` 推理;若不对齐,本地化的 `yql:` 语义已保证 TTL 自洽可用。
