# NCC 数据源映射范围

> 映射定义文件：`loan_claude-v8.ttl`  
> 命名空间前缀：`ncc:` → `http://yql.example.com/ontology/ncc-mapping/`  
> 统计：**22 张业务表**，**93 个字段映射**，**9 大业务域**

## 应付(AP)

### AP_PAYABLEBILL
**表描述**: 应付单主表

| 字段名 | 字段描述 |
|--------|---------|
| BILLPERIOD | 单据期间 |
| BILLYEAR | 单据年度 |
| LOCAL_MONEY | 本币金额 |
| PK_ORG | 组织 |

### AP_PAYABLEITEM
**表描述**: 应付单明细表

| 字段名 | 字段描述 |
|--------|---------|
| BILLDATE | 日期 |
| PK_ORG | 组织 |
| SUPPLIER | 供应商主键 |

## 应收(AR)

### AR_RECBILL
**表描述**: 应收单主表

| 字段名 | 字段描述 |
|--------|---------|
| BILLPERIOD | 单据期间 |
| BILLYEAR | 单据年度 |
| LOCAL_MONEY | 本币金额 |
| PK_ORG | 组织主键 |

### AR_RECITEM
**表描述**: 应收单明细表

| 字段名 | 字段描述 |
|--------|---------|
| BILLDATE | 单据日期 |
| CUSTOMER | 客户主键(外键→BD_CUSTOMER.PK_CUSTOMER) |
| PK_ORG | 组织 |

## 往来(ARAP)

### ARAP_BALANCE
**表描述**: 往来余额表

| 字段名 | 字段描述 |
|--------|---------|
| ACCPERIOD | 会计期间 |
| ACCYEAR | 会计年度 |
| BILLCLASS | 单据类别(AR/AP) |
| LOCAL_MONEY_CR | 本币贷方 |
| LOCAL_MONEY_DE | 本币借方 |
| PK_ORG | 组织 |

### ARAP_BDLOSS
**表描述**: 坏账损失主表

| 字段名 | 字段描述 |
|--------|---------|
| APPROVESTATUS | 审批状态 |
| BILLDATE | 单据日期 |
| LOSSLOCALMONEY | 本币损失金额 |
| PK_ORG | 组织 |

## 融资(BATM)

### BATM_FINANCING
**表描述**: 融资台账表

| 字段名 | 字段描述 |
|--------|---------|
| BALANCE | 原币余额 |
| BEGINDATE | 起始日期 |
| DR | 删除标志 |
| ENDDATE | 到期日期 |
| FINANCING_ORG | 融资机构 |
| PK_ORG | 组织 |

## 债券/担保

### BOND_CONTRACT
**表描述**: 债券合同表

| 字段名 | 字段描述 |
|--------|---------|
| DR | 删除标志 |
| ISSUERID | 债券发行机构 |
| ISSUESTARTDATE | 发行开始日期 |
| PK_ORG | 发行组织 |
| REGISTMNY | 债券发行金额 |

### GPMC_GUACONTRACT
**表描述**: 担保合同主表

| 字段名 | 字段描述 |
|--------|---------|
| AVAAMOUNT | 可用金额 |
| BILLMAKEDATE | 制单日期 |
| BUSISTATUS | 业务状态 |
| DEBTAMOUNT | 债权金额 |
| GUAAMOUNT | 担保总金额 |
| PK_ORG | 组织 |
| USEDAMOUNT | 已用金额 |

### GPMC_GUAPLEINF
**表描述**: 质押信息表

| 字段名 | 字段描述 |
|--------|---------|
| PK_ORG | 组织 |
| TOTALPLEDGE | 质押总金额 |

## 信贷合同(CDMC)

### CDMC_CONTRACT
**表描述**: 融资合同主表

| 字段名 | 字段描述 |
|--------|---------|
| AVAILABLEMNY | 可用金额(授信额度) |
| BEGINDATE | 起始日期 |
| BUSISTATUS | 业务状态 |
| CCMNY | 合同信用金额 |
| DR | 删除标志 |
| ENDDATE | 到期日期 |
| PK_FINANCORG | 金融机构主键 |
| PK_ORG | 组织 |

### CDMC_REPAYPRCPL
**表描述**: 还本计划表

| 字段名 | 字段描述 |
|--------|---------|
| EXREPAYMNY | 实际还本金额 |
| MAKEVDATE | 生效日期 |
| PK_ORG | 组织 |
| REPAYDATE | 还款日期 |
| REPAYMNY | 还本金额 |

### CDMC_REPINTEREST
**表描述**: 还息计划表

| 字段名 | 字段描述 |
|--------|---------|
| LOANDATE | 放款日期 |
| PAYINTMONEY | 还息金额 |
| PK_ORG | 组织 |

## 主数据(BD)

### BD_CUSTOMER
**表描述**: 客户基础档案

| 字段名 | 字段描述 |
|--------|---------|
| BEGINDATE | 客户启用日期 |
| ENABLESTATE | 启用状态 |
| PK_ORG | 所属组织 |

### BD_SUPPLIER
**表描述**: 供应商基础档案

| 字段名 | 字段描述 |
|--------|---------|
| BEGINDATE | 启用日期 |
| BLACKLIST | 黑名单标志 |
| ENABLESTATE | 启用状态 |
| PK_ORG | 所属组织 |

## 采购(PO)

### CT_PU
**表描述**: 采购合同主表

| 字段名 | 字段描述 |
|--------|---------|
| ACTUALINVALIDATE | 实际失效日期 |
| FSTATUSFLAG | 合同状态 |
| NTOTALORIGMNY | 合同总金额 |
| PK_ORG | 组织 |

### PO_INVOICE
**表描述**: 采购发票表

| 字段名 | 字段描述 |
|--------|---------|
| DBILLDATE | 单据日期 |
| NTOTALORIGMNY | 总原币金额 |
| PK_ORG | 组织 |

### PO_ORDER
**表描述**: 采购订单主表

| 字段名 | 字段描述 |
|--------|---------|
| DBILLDATE | 单据日期 |
| NTOTALORIGMNY | 订单总原币金额 |
| PK_ORG | 采购组织 |

## 销售(SO)

### CT_SALE
**表描述**: 销售合同主表

| 字段名 | 字段描述 |
|--------|---------|
| ACTUALINVALIDATE | 实际失效日期 |
| FSTATUSFLAG | 合同状态 |
| NTOTALORIGMNY | 合同总金额 |
| PK_ORG | 组织 |

### SO_SALEINVOICE
**表描述**: 销售发票主表

| 字段名 | 字段描述 |
|--------|---------|
| DBILLDATE | 单据日期 |
| NTOTALORIGMNY | 总原币金额 |
| PK_ORG | 组织 |

## 总账(GL)

### GL_BALANCE
**表描述**: 总账余额表

| 字段名 | 字段描述 |
|--------|---------|
| ACCOUNTCODE | 会计科目编码(冗余) |
| LOCALCREDITAMOUNT | 本币贷方发生额 |
| LOCALDEBITAMOUNT | 本币借方发生额 |
| PERIOD | 会计期间(月) |
| PK_ACCOUNTINGBOOK | 账簿主键 |
| PK_ORG | 组织主键(外键→ORG_ORGS.PK_ORG) |

## 存货(IA)

### IA_MONTHNAB
**表描述**: 存货月末余额表

| 字段名 | 字段描述 |
|--------|---------|
| CACCOUNTPERIOD | 会计期间(YYYY-MM) |
| NABMNY | 月末原币金额 |
| PK_ORG | 组织 |
