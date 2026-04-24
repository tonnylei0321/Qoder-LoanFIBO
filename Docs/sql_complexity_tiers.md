# 71 个指标 SQL 复杂度分档

## 分档标准

| 档位 | 特征 | 预计 SQL 行数 | 交付确定性 |
|---|---|---|---|
| **A档 · 简单** | 仅 GL_BALANCE/GL_CASHFLOWCASE,科目加减比率 | 30-50 行 | 0 幻觉 |
| **B档 · 中等** | 2-4 张业务表 JOIN(含应收/应付/合同明细),单期计算 | 60-120 行 | 0 幻觉 |
| **C档 · 复杂** | 5+ 张表 JOIN / 账龄分桶 / 时序对比 / 评分模型 | 120-250 行 | 核心逻辑 0 幻觉,TODO 标注需补规则 |
| **D档 · 需补数据** | 派生组合指标、需外部数据(征信/四流合一/发票验真) | — | 需您补充规则或数据源后才可写 |

## A 档 · 简单 (GL 单表)  ·  1 个

| 指标ID | 指标名 | 字段数 | 涉及表 |
|---|---|---|---|
| `POST-D3-03` | 经营现金流同比变化 | 11 | `GL_CASHFLOWCASE` |

## B 档 · 中等 (业务表 JOIN)  ·  32 个

| 指标ID | 指标名 | 字段数 | 涉及表 |
|---|---|---|---|
| `POST-D3-01` | 营收同比增速 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `POST-D3-02` | 毛利率环比变化 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `POST-D3-05` | 在手合同金额 | 14 | `CT_SALE`, `CT_SALE_EXEC` |
| `POST-D4-01` | 非银融资占比变化 | 20 | `BATM_FINANCING`, `BOND_CONTRACT`, `CDMC_CONTRACT`, `ICDMC_CONTRACT` |
| `POST-D4-03` | 资产负债率变化 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `POST-D5-03` | 质押应收集中度 | 30 | `AR_RECITEM`, `BD_CUSTOMER`, `GPMC_GUACONTRACT`, `GPMC_GUAPLEINF` |
| `PRE-D1-01` | 速动比率 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D1-02` | 流动比率 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D1-03` | 利息覆盖倍数 ICR | 20 | `BD_ACCOUNT`, `GL_BALANCE`, `GL_DETAIL` |
| `PRE-D1-06` | 现金覆盖天数 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D2-01` | EBITDA利润率 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D2-02` | 现金流/净利润比 | 20 | `BD_ACCOUNT`, `GL_BALANCE`, `GL_CASHFLOWCASE` |
| `PRE-D2-04` | 毛利率 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D2-05` | 净利润率 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D3-03` | 资产负债率 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D3-04` | 有效净资产 | 19 | `AR_RECITEM`, `BD_ACCOUNT`, `BD_CUSTOMER`, `GL_BALANCE` |
| `PRE-D3-05` | 存货周转天数 | 21 | `BD_ACCOUNT`, `GL_BALANCE`, `IA_MONTHNAB` |
| `PRE-D4-01` | 自由现金流 FCF | 25 | `BD_ACCOUNT`, `GL_BALANCE`, `GL_CASHFLOWCASE` |
| `PRE-D4-03` | 资本支出/营收比 | 25 | `BD_ACCOUNT`, `GL_BALANCE`, `GL_CASHFLOWCASE` |
| `PRE-D4-05` | 现金比率 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D5-03` | 总资产周转率 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D5-04` | 净资产收益率 ROE | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D6-01` | 客户集中度 | 14 | `AR_RECITEM`, `BD_CUSTOMER`, `SO_SALEINVOICE` |
| `PRE-D6-02` | 供应商集中度 | 15 | `AP_PAYABLEITEM`, `BD_SUPPLIER`, `PO_INVOICE`, `PO_ORDER` |
| `PRE-D6-03` | 关联方应收占比 | 10 | `ARAP_BALANCE`, `AR_RECITEM`, `BD_CUSTOMER` |
| `SCF-D1-07` | 关联方交易占比 | 10 | `BD_CUSTOMER`, `BD_SUPPLIER`, `PO_INVOICE`, `SO_SALEINVOICE` |
| `SCF-D2-03` | 应收账款集中度 | 31 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER` |
| `SCF-D2-05` | 应收账款争议率 | 34 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER` |
| `SCF-D4-01` | 供应商关系稳定性 | 9 | `BD_SUPPLIER`, `PO_ORDER` |
| `SCF-D4-04` | 供应链库存周转天数 | 20 | `BD_ACCOUNT`, `GL_BALANCE`, `IA_MONTHNAB` |
| `SCF-D4-06` | 供应链DPO | 27 | `AP_PAYABLEBILL`, `AP_PAYABLEITEM`, `BD_ACCOUNT`, `GL_BALANCE` |
| `SCF-D4-07` | 供应链融资历史 | 15 | `CDMC_CONTRACT`, `CDMC_FINEXECUTE`, `CDMC_REPAYPRCPL`, `CDMC_REPINTEREST` |

## C 档 · 复杂 (评分/时序/大 JOIN)  ·  22 个

| 指标ID | 指标名 | 字段数 | 涉及表 |
|---|---|---|---|
| `POST-D2-01` | 应收账龄恶化速率 | 31 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER` |
| `POST-D2-02` | 关联方交易突增告警 | 18 | `AP_PAYABLEITEM`, `AR_RECITEM`, `BD_CUSTOMER`, `BD_SUPPLIER`, `PO_INVOICE`, `SO_SALEINVOICE` |
| `POST-D3-04` | EBITDA利润率趋势 | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `POST-D5-01` | 应收账款质押覆盖率 | 35 | `AR_RECITEM`, `CDMC_CONTRACT`, `CDMC_FINEXECUTE`, `GPMC_GUACONTRACT`, `GPMC_GUAPLEINF` |
| `POST-D5-02` | 质押应收质量评分 | 57 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER`, `GPMC_GUACONTRACT`, `GPMC_GUAPLEINF` |
| `PRE-D1-04` | 偿债覆盖率 DSCR | 29 | `BD_ACCOUNT`, `BOND_REPAYPLAN`, `CDMC_CONTRACT`, `CDMC_REPAYPRCPL`, `CDMC_REPINTEREST`, `GL_BALANCE` |
| `PRE-D1-05` | 净债务/EBITDA | 22 | `BATM_FINANCING`, `BD_ACCOUNT`, `BOND_CONTRACT`, `CDMC_CONTRACT`, `CDMC_FINEXECUTE`, `GL_BALANCE` |
| `PRE-D2-03` | 收入3年CAGR | 14 | `BD_ACCOUNT`, `GL_BALANCE` |
| `PRE-D3-01` | 应收账款质量评分 | 31 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER` |
| `PRE-D3-02` | 60天以上应收占比 | 31 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER` |
| `PRE-D4-02` | 经营现金流稳定性 | 11 | `GL_CASHFLOWCASE` |
| `PRE-D4-04` | 三类现金流结构 | 11 | `GL_CASHFLOWCASE` |
| `PRE-D5-02` | 应收账款周转天数 DSO | 45 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_ACCOUNT`, `BD_CUSTOMER`, `GL_BALANCE` |
| `SCF-D1-02` | 货物交付完整性 | 88 | `BD_CUSTOMER`, `BD_SUPPLIER`, `CT_PU`, `IC_PURCHASEIN_B`, `IC_PURCHASEIN_H`, `PO_ARRIVEORDER`, `PO_ARRIVEORDER_B`, `PO_INVOICE`, `PO_ORDER`, `PO_ORDER_B`, `SO_DELIVERY`, `SO_DELIVERY_B`, `SO_SALEINVOICE`, `SO_SALEINVOICE_B`, `SO_SALEORDER` |
| `SCF-D1-04` | 合同履约时间偏差 | 21 | `CT_PU`, `CT_PU_EXEC`, `CT_SALE`, `CT_SALE_EXEC`, `IC_PURCHASEIN_H`, `SO_DELIVERY`, `SO_DELIVERY_B` |
| `SCF-D1-11` | 历史交易频率稳定性 | 8 | `PO_ORDER`, `SO_SALEORDER` |
| `SCF-D2-01` | 应收账款账龄评分 | 31 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER` |
| `SCF-D2-02` | 90天以上应收占比 | 31 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER` |
| `SCF-D2-04` | 供应链DSO | 45 | `ARAP_BALANCE`, `AR_RECBILL`, `AR_RECITEM`, `BD_ACCOUNT`, `BD_CUSTOMER`, `GL_BALANCE` |
| `SCF-D2-07` | 历史坏账率 | 19 | `ARAP_BDLOSS`, `ARAP_BDLOSS_D`, `ARAP_VERIFY`, `AR_RECBILL`, `AR_RECITEM` |
| `SCF-D3-02` | 买方付款准时率 | 21 | `AR_GATHERBILL`, `AR_GATHERITEM`, `AR_RECBILL`, `AR_RECITEM`, `BD_CUSTOMER` |
| `SCF-D4-05` | 订单履行率 | 23 | `IC_PURCHASEIN_B`, `IC_PURCHASEIN_H`, `PO_ORDER`, `PO_ORDER_B`, `SO_DELIVERY`, `SO_DELIVERY_B`, `SO_SALEORDER` |

## D 档 · 需补数据  ·  16 个

| 指标ID | 指标名 | 字段数 | 涉及表 |
|---|---|---|---|
| `POST-D2-03` | 三表一致性校验 | 31 | `BD_ACCOUNT`, `GL_BALANCE`, `GL_CASHFLOWCASE`, `GL_VOUCHER` |
| `POST-D2-05` | 财报提交及时性 | 0 | — |
| `POST-D4-02` | 授信使用率 | 19 | `BATM_FINANCING`, `BGM_OPENREGISTER`, `CDMC_CONTRACT`, `CDMC_FINEXECUTE` |
| `PRE-D5-01` | 现金转换周期 CCC | 0 | — |
| `SCF-D1-01` | 发票-订单匹配率 | 88 | `BD_CUSTOMER`, `BD_SUPPLIER`, `CT_PU`, `IC_PURCHASEIN_B`, `IC_PURCHASEIN_H`, `PO_ARRIVEORDER`, `PO_ARRIVEORDER_B`, `PO_INVOICE`, `PO_ORDER`, `PO_ORDER_B`, `SO_DELIVERY`, `SO_DELIVERY_B`, `SO_SALEINVOICE`, `SO_SALEINVOICE_B`, `SO_SALEORDER` |
| `SCF-D1-03` | 交易对手一致性 | 91 | `AP_PAYABLEITEM`, `BD_CUSTOMER`, `BD_SUPPLIER`, `CT_PU`, `IC_PURCHASEIN_B`, `IC_PURCHASEIN_H`, `PO_ARRIVEORDER`, `PO_ARRIVEORDER_B`, `PO_INVOICE`, `PO_ORDER`, `PO_ORDER_B`, `SO_DELIVERY`, `SO_DELIVERY_B`, `SO_SALEINVOICE`, `SO_SALEINVOICE_B`, `SO_SALEORDER` |
| `SCF-D1-05` | 物流凭证三方验证 | 13 | `IC_PURCHASEIN_B`, `IC_PURCHASEIN_H`, `PO_ARRIVEORDER`, `PO_INVOICE` |
| `SCF-D1-08` | 四流合一验证得分 | 0 | — |
| `SCF-D2-06` | 应收账款质量分级 | 0 | — |
| `SCF-D2-09` | 应收可回收性评分 | 0 | — |
| `SCF-D2-10` | ERP应收与银行一致性 | 32 | `AR_GATHERBILL`, `AR_GATHERITEM`, `AR_RECBILL`, `FTS_ACCOUNT_DAILYDETAIL`, `FTS_ACCOUNT_DETAIL`, `FTS_GATHERING` |
| `SCF-D3-04` | 买方逾期应付占比 | 7 | `AR_RECITEM`, `BD_CUSTOMER` |
| `SCF-D3-09` | 核心企业确认意愿 | 8 | `BD_CUSTOMER`, `CT_SALE` |
| `SCF-D4-03` | ERP系统集成深度 | 0 | — |
| `SCF-D4-08` | 数字化平台评分 | 0 | — |
| `SCF-D4-09` | 供应链层级深度 | 4 | `BD_SUPPLIER`, `PO_ORDER` |

## 每档代表样例(仅结构示意,正式版见后续交付)

### A 档样例 · `POST-D3-03 经营现金流同比变化`

```sql
-- 仅查 GL_CASHFLOWCASE 两期
SELECT ((SUM(CASE WHEN YEAR=:year THEN MONEY END) -
        SUM(CASE WHEN YEAR=:year-1 THEN MONEY END)) /
        NULLIF(SUM(CASE WHEN YEAR=:year-1 THEN MONEY END), 0)) AS yoy_change
FROM GL_CASHFLOWCASE
WHERE PK_ORG = :org_id AND CASECODE LIKE '01%' -- 经营活动
  AND YEAR IN (:year, :year-1);
```

### B 档样例 · `PRE-D1-01 速动比率`

```sql
-- 约 80 行:含流动资产复杂规则(双向科目/坏账准备/存货跌价)
-- 与上一轮回复示意一致
WITH bal AS (SELECT ACCOUNTCODE, 
             SUM(LOCALDEBITAMOUNT - LOCALCREDITAMOUNT) AS net
             FROM GL_BALANCE WHERE ... GROUP BY ACCOUNTCODE)
SELECT (current_assets - inventory - prepaid) / NULLIF(current_liab, 0)
FROM (...);
```

### C 档样例 · `PRE-D3-01 应收账款质量评分`

```sql
-- 含账龄分桶(0-30/31-60/61-90/90+)+ 加权评分
WITH ar_aged AS (
  SELECT CUSTOMER, LOCAL_MONEY_DE - LOCAL_MONEY_CR AS bal,
    CASE WHEN MONTHS_BETWEEN(:asof, BILLDATE) <= 1 THEN '0-30'
         WHEN MONTHS_BETWEEN(:asof, BILLDATE) <= 2 THEN '31-60'
         WHEN MONTHS_BETWEEN(:asof, BILLDATE) <= 3 THEN '61-90'
         ELSE '90+'
    END AS age_bucket  -- 业务要点:以哪个日期起算?BILLDATE 还是发票开票日?
  FROM AR_RECITEM WHERE PK_ORG = :org_id AND ...
)
SELECT 100 * SUM(
  bal * CASE age_bucket WHEN '0-30' THEN 1.0
                        WHEN '31-60' THEN 0.8
                        WHEN '61-90' THEN 0.5
                        ELSE 0.1 END
) / NULLIF(SUM(bal), 0) AS ar_quality_score
FROM ar_aged;
-- TODO 贵司账龄分段标准?权重值?
```

### D 档样例 · `SCF-D1-01 发票-订单匹配率`

```
需澄清:
1. 匹配维度:金额一致?物料一致?数量一致?日期前后关系?
2. '不匹配'的容差(金额 5% 以内算匹配?)
3. 是否需要三方比对(PO + 发票 + 入库)
4. 如果需要,PO_INVOICE 的 CINVOICEID 和 PO_ORDER 的关联关系确认
```

## 汇总与建议交付量

| 档 | 数量 | 建议批次 | 预计单指标工作量 |
|---|---|---|---|
| A | 1 | 一次交付 | ~5 分钟 |
| B | 32 | 分 2-3 批交付 | ~20 分钟 |
| C | 22 | 分 3-4 批 + 每个需您确认业务规则 | ~40 分钟 |
| D | 16 | 暂缓,等您补规则 | N/A |

**合计:** A档 1 + B档 32 + C档 22 + D档 16 = 71

## 推荐下一步

1. **先批 A + B 档**(共 34 个),0 幻觉可交付,覆盖全部**偿债/盈利/资产/现金流/周转/集中度**等主流财务指标
2. **C 档每个单做**,每个我先给您 SQL 草稿 + 明确 TODO,您确认业务规则后我补完
3. **D 档整体搁置**,等您补:
   - 派生指标的组合逻辑(如 PRE-D5-01 现金转换周期 CCC = DSO + DIO - DPO,需指明哪 3 个作为子指标)
   - 外部数据源定义(如征信接口、四流合一规则)
