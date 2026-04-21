"""
Seed script: initialize fi_dimension and fi_indicator tables
with standard indicators for pre_loan / post_loan / scf scenarios.

Usage:
    python -m scripts.seed_indicators
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend.app.database import async_session_factory, engine, Base

# Import all fi_ models so SQLAlchemy creates the tables
from backend.app.models.fi_company import FiCompany  # noqa
from backend.app.models.fi_dimension import FiDimension
from backend.app.models.fi_indicator import FiIndicator
from backend.app.models.fi_indicator_value import FiIndicatorValue  # noqa
from backend.app.models.fi_score_record import FiScoreRecord  # noqa
from backend.app.models.fi_alert_record import FiAlertRecord  # noqa


# ─── Dimension definitions ────────────────────────────────────────────────────

PRE_LOAN_DIMENSIONS = [
    {"code": "liquidity",      "name": "流动性",     "weight": 0.25, "sort_order": 1},
    {"code": "profitability",  "name": "盈利能力",   "weight": 0.20, "sort_order": 2},
    {"code": "solvency",       "name": "偿债能力",   "weight": 0.20, "sort_order": 3},
    {"code": "operations",     "name": "运营能力",   "weight": 0.15, "sort_order": 4},
    {"code": "growth",         "name": "成长性",     "weight": 0.10, "sort_order": 5},
    {"code": "cashflow",       "name": "现金流",     "weight": 0.10, "sort_order": 6},
]

POST_LOAN_DIMENSIONS = [
    {"code": "pl_liquidity",   "name": "流动性监控", "weight": 0.30, "sort_order": 1},
    {"code": "pl_operations",  "name": "经营情况",   "weight": 0.25, "sort_order": 2},
    {"code": "pl_solvency",    "name": "偿债能力",   "weight": 0.25, "sort_order": 3},
    {"code": "pl_cashflow",    "name": "现金流监控", "weight": 0.20, "sort_order": 4},
]

SCF_DIMENSIONS = [
    {"code": "scf_ar",         "name": "应收账款质量", "weight": 0.30, "sort_order": 1},
    {"code": "scf_core",       "name": "核心企业信用", "weight": 0.25, "sort_order": 2},
    {"code": "scf_trade",      "name": "贸易真实性",   "weight": 0.25, "sort_order": 3},
    {"code": "scf_risk",       "name": "供应链风险",   "weight": 0.20, "sort_order": 4},
]


# ─── Indicator definitions ────────────────────────────────────────────────────
# Format: (code, name, fibo_path, formula, unit, dim_code, weight, threshold_warning, threshold_alert, direction)

PRE_LOAN_INDICATORS = [
    # 流动性 (liquidity)
    ("PRE_LIQ_01", "流动比率",   "fibo-fnd:CurrentRatio",
     "流动资产 / 流动负债", "倍", "liquidity", 0.25, 1.5, 1.0, "above"),
    ("PRE_LIQ_02", "速动比率",   "fibo-fnd:QuickRatio",
     "(流动资产 - 存货) / 流动负债", "倍", "liquidity", 0.20, 1.0, 0.7, "above"),
    ("PRE_LIQ_03", "现金比率",   "fibo-fnd:CashRatio",
     "货币资金 / 流动负债", "倍", "liquidity", 0.15, 0.3, 0.15, "above"),
    ("PRE_LIQ_04", "营运资金",   "fibo-fnd:WorkingCapital",
     "流动资产 - 流动负债", "万元", "liquidity", 0.20, 500, 0, "above"),
    ("PRE_LIQ_05", "存货周转天数", "fibo-fnd:InventoryDays",
     "存货 / 营业成本 × 365", "天", "liquidity", 0.10, 90, 180, "below"),
    ("PRE_LIQ_06", "应收账款周转天数", "fibo-fnd:ARDays",
     "应收账款 / 营业收入 × 365", "天", "liquidity", 0.10, 60, 120, "below"),

    # 盈利能力 (profitability)
    ("PRE_PRF_01", "净资产收益率(ROE)", "fibo-fnd:ReturnOnEquity",
     "净利润 / 平均净资产 × 100%", "%", "profitability", 0.30, 8.0, 4.0, "above"),
    ("PRE_PRF_02", "总资产收益率(ROA)", "fibo-fnd:ReturnOnAssets",
     "净利润 / 平均总资产 × 100%", "%", "profitability", 0.25, 4.0, 2.0, "above"),
    ("PRE_PRF_03", "销售净利润率",      "fibo-fnd:NetProfitMargin",
     "净利润 / 营业收入 × 100%", "%", "profitability", 0.25, 5.0, 2.0, "above"),
    ("PRE_PRF_04", "毛利率",           "fibo-fnd:GrossProfitMargin",
     "(营业收入 - 营业成本) / 营业收入 × 100%", "%", "profitability", 0.20, 20.0, 10.0, "above"),

    # 偿债能力 (solvency)
    ("PRE_SOL_01", "资产负债率",   "fibo-fnd:DebtToAssetRatio",
     "总负债 / 总资产 × 100%", "%", "solvency", 0.30, 60, 75, "below"),
    ("PRE_SOL_02", "利息保障倍数", "fibo-fnd:InterestCoverageRatio",
     "息税前利润 / 利息费用", "倍", "solvency", 0.25, 3.0, 1.5, "above"),
    ("PRE_SOL_03", "债务净额/EBITDA", "fibo-fnd:NetDebtToEBITDA",
     "(有息负债 - 现金) / EBITDA", "倍", "solvency", 0.25, 3.0, 5.0, "below"),
    ("PRE_SOL_04", "产权比率",     "fibo-fnd:EquityRatio",
     "总负债 / 所有者权益", "倍", "solvency", 0.20, 1.5, 3.0, "below"),

    # 运营能力 (operations)
    ("PRE_OPS_01", "总资产周转率", "fibo-fnd:TotalAssetTurnover",
     "营业收入 / 平均总资产", "次", "operations", 0.30, 0.8, 0.4, "above"),
    ("PRE_OPS_02", "流动资产周转率", "fibo-fnd:CurrentAssetTurnover",
     "营业收入 / 平均流动资产", "次", "operations", 0.30, 2.0, 1.0, "above"),
    ("PRE_OPS_03", "应收账款周转率", "fibo-fnd:AccountsReceivableTurnover",
     "营业收入 / 平均应收账款", "次", "operations", 0.20, 6.0, 3.0, "above"),
    ("PRE_OPS_04", "存货周转率",    "fibo-fnd:InventoryTurnover",
     "营业成本 / 平均存货", "次", "operations", 0.20, 4.0, 2.0, "above"),

    # 成长性 (growth)
    ("PRE_GRW_01", "营业收入增长率", "fibo-fnd:RevenueGrowthRate",
     "(本期营收 - 上期营收) / 上期营收 × 100%", "%", "growth", 0.40, 5.0, -5.0, "above"),
    ("PRE_GRW_02", "净利润增长率",   "fibo-fnd:NetProfitGrowthRate",
     "(本期净利润 - 上期净利润) / |上期净利润| × 100%", "%", "growth", 0.35, 5.0, -10.0, "above"),
    ("PRE_GRW_03", "总资产增长率",   "fibo-fnd:TotalAssetGrowthRate",
     "(期末总资产 - 期初总资产) / 期初总资产 × 100%", "%", "growth", 0.25, 3.0, -5.0, "above"),

    # 现金流 (cashflow)
    ("PRE_CF_01",  "经营活动现金净流量", "fibo-fnd:OperatingCashFlow",
     "经营活动产生的现金流量净额", "万元", "cashflow", 0.40, 0, -1000, "above"),
    ("PRE_CF_02",  "自由现金流",        "fibo-fnd:FreeCashFlow",
     "经营现金流 - 资本支出", "万元", "cashflow", 0.35, 0, -500, "above"),
    ("PRE_CF_03",  "现金流量比率",      "fibo-fnd:CashFlowRatio",
     "经营活动净现金流 / 流动负债", "倍", "cashflow", 0.25, 0.2, 0.05, "above"),

    # Extra
    ("PRE_LIQ_07", "净营运资本比率",  "fibo-fnd:NetWorkingCapitalRatio",
     "净营运资本 / 总资产", "%", "liquidity", 0.0, 10, 0, "above"),
    ("PRE_PRF_05", "EBITDA利润率",   "fibo-fnd:EBITDAMargin",
     "EBITDA / 营业收入 × 100%", "%", "profitability", 0.0, 10, 5, "above"),
]


POST_LOAN_INDICATORS = [
    # 流动性监控 (pl_liquidity)
    ("PL_LIQ_01", "流动比率",      "fibo-fnd:CurrentRatio",
     "流动资产 / 流动负债", "倍", "pl_liquidity", 0.30, 1.2, 0.8, "above"),
    ("PL_LIQ_02", "速动比率",      "fibo-fnd:QuickRatio",
     "(流动资产 - 存货) / 流动负债", "倍", "pl_liquidity", 0.25, 0.8, 0.5, "above"),
    ("PL_LIQ_03", "货币资金/短债",  "fibo-fnd:CashToShortDebtRatio",
     "货币资金 / 短期有息负债", "倍", "pl_liquidity", 0.25, 0.5, 0.2, "above"),
    ("PL_LIQ_04", "银行授信使用率", "fibo-fnd:CreditLineUsageRate",
     "已使用授信额度 / 授信总额度 × 100%", "%", "pl_liquidity", 0.20, 80, 90, "below"),
    ("PL_LIQ_05", "逾期次数",       "fibo-fnd:OverdueCount",
     "近12个月逾期次数", "次", "pl_liquidity", 0.0, 0, 2, "below"),

    # 经营情况 (pl_operations)
    ("PL_OPS_01", "营业收入同比增速", "fibo-fnd:RevenueYoYGrowth",
     "同比增速", "%", "pl_operations", 0.30, 0, -15, "above"),
    ("PL_OPS_02", "毛利率变化",       "fibo-fnd:GrossMarginChange",
     "本期毛利率 - 上期毛利率", "pct", "pl_operations", 0.25, -5, -10, "above"),
    ("PL_OPS_03", "前五大客户集中度", "fibo-fnd:CustomerConcentration",
     "前五大客户收入 / 总收入 × 100%", "%", "pl_operations", 0.25, 60, 80, "below"),
    ("PL_OPS_04", "对外担保比率",     "fibo-fnd:ExternalGuaranteeRatio",
     "对外担保余额 / 净资产 × 100%", "%", "pl_operations", 0.20, 30, 50, "below"),
    ("PL_OPS_05", "关联交易占比",     "fibo-fnd:RelatedPartyTransactionRatio",
     "关联交易金额 / 总收入 × 100%", "%", "pl_operations", 0.0, 20, 40, "below"),

    # 偿债能力 (pl_solvency)
    ("PL_SOL_01", "资产负债率",      "fibo-fnd:DebtToAssetRatio",
     "总负债 / 总资产 × 100%", "%", "pl_solvency", 0.30, 65, 80, "below"),
    ("PL_SOL_02", "利息保障倍数",    "fibo-fnd:InterestCoverageRatio",
     "EBIT / 利息", "倍", "pl_solvency", 0.30, 2.0, 1.0, "above"),
    ("PL_SOL_03", "短期债务/净资产", "fibo-fnd:ShortDebtToEquity",
     "短期有息负债 / 净资产", "倍", "pl_solvency", 0.25, 0.5, 1.0, "below"),
    ("PL_SOL_04", "或有负债比率",    "fibo-fnd:ContingentLiabilityRatio",
     "或有负债 / 净资产 × 100%", "%", "pl_solvency", 0.15, 50, 100, "below"),

    # 现金流监控 (pl_cashflow)
    ("PL_CF_01", "经营现金流",       "fibo-fnd:OperatingCashFlow",
     "经营活动净现金流", "万元", "pl_cashflow", 0.40, 0, -500, "above"),
    ("PL_CF_02", "现金回款率",       "fibo-fnd:CashCollectionRate",
     "当期收到货款 / 当期营收 × 100%", "%", "pl_cashflow", 0.35, 80, 60, "above"),
    ("PL_CF_03", "主营业务现金含量",  "fibo-fnd:CashContentOfRevenue",
     "经营现金流 / 净利润", "倍", "pl_cashflow", 0.25, 0.8, 0.3, "above"),
]


SCF_INDICATORS = [
    # 应收账款质量 (scf_ar)
    ("SCF_AR_01", "应收账款账龄结构（180天以上占比）", "fibo-fnd:ARAgingOver180",
     "180天以上应收账款 / 总应收账款 × 100%", "%", "scf_ar", 0.25, 15, 30, "below"),
    ("SCF_AR_02", "应收账款集中度",   "fibo-fnd:ARConcentration",
     "最大债务人应收账款 / 总应收账款 × 100%", "%", "scf_ar", 0.20, 30, 50, "below"),
    ("SCF_AR_03", "应收账款周转天数", "fibo-fnd:DaysReceivableOutstanding",
     "应收账款 / 营收 × 365", "天", "scf_ar", 0.25, 60, 120, "below"),
    ("SCF_AR_04", "坏账计提比率",     "fibo-fnd:BadDebtProvisionRate",
     "坏账准备 / 应收账款总额 × 100%", "%", "scf_ar", 0.15, 5, 15, "below"),
    ("SCF_AR_05", "应收账款质押率",   "fibo-fnd:ARPledgeRate",
     "已质押应收账款 / 总应收账款 × 100%", "%", "scf_ar", 0.15, 80, 60, "above"),
    ("SCF_AR_06", "预付账款占营收比", "fibo-fnd:PrepaymentToRevenueRatio",
     "预付账款 / 营收 × 100%", "%", "scf_ar", 0.0, 10, 25, "below"),

    # 核心企业信用 (scf_core)
    ("SCF_COR_01", "核心企业信用评级",     "fibo-fnd:CoreEnterpriseRating",
     "核心企业外部信用评级（AA=80,AA+=85,AAA=95）", "分", "scf_core", 0.35, 70, 50, "above"),
    ("SCF_COR_02", "核心企业资产负债率",   "fibo-fnd:CoreDebtToAsset",
     "核心企业总负债 / 总资产 × 100%", "%", "scf_core", 0.30, 60, 75, "below"),
    ("SCF_COR_03", "核心企业近12月逾期",   "fibo-fnd:CoreOverdueCount",
     "核心企业近12月银行逾期次数", "次", "scf_core", 0.20, 0, 1, "below"),
    ("SCF_COR_04", "核心企业营收规模",     "fibo-fnd:CoreRevenueScale",
     "核心企业年营收（万元）", "万元", "scf_core", 0.15, 50000, 10000, "above"),

    # 贸易真实性 (scf_trade)
    ("SCF_TRD_01", "合同单据完整度",     "fibo-fnd:TradeDocumentIntegrity",
     "完整贸易单据套数 / 申请融资合同数 × 100%", "%", "scf_trade", 0.30, 95, 80, "above"),
    ("SCF_TRD_02", "历史贸易背景核实率", "fibo-fnd:HistoricalTradeVerificationRate",
     "可核实交易 / 近12月申报交易 × 100%", "%", "scf_trade", 0.25, 90, 70, "above"),
    ("SCF_TRD_03", "应收账款与营收匹配度", "fibo-fnd:ARToRevenueMatchRate",
     "应收账款增量 / 营收增量（偏差率）", "%", "scf_trade", 0.25, 20, 40, "below"),
    ("SCF_TRD_04", "供应商集中度",       "fibo-fnd:SupplierConcentration",
     "前三供应商采购额 / 总采购额 × 100%", "%", "scf_trade", 0.20, 60, 80, "below"),
    ("SCF_TRD_05", "资金回流周期",       "fibo-fnd:FundReturnCycle",
     "货款回流平均天数", "天", "scf_trade", 0.0, 90, 180, "below"),

    # 供应链风险 (scf_risk)
    ("SCF_RSK_01", "存货质押率",       "fibo-fnd:InventoryPledgeRate",
     "已质押存货市值 / 融资额 × 100%", "%", "scf_risk", 0.25, 130, 110, "above"),
    ("SCF_RSK_02", "存货价格波动率",   "fibo-fnd:InventoryPriceVolatility",
     "近半年存货价格标准差 / 均价 × 100%", "%", "scf_risk", 0.20, 15, 30, "below"),
    ("SCF_RSK_03", "供应商信用等级",   "fibo-fnd:SupplierCreditScore",
     "主要供应商综合评分（0-100）", "分", "scf_risk", 0.25, 70, 50, "above"),
    ("SCF_RSK_04", "供应链账期错配",   "fibo-fnd:SCFMaturityMismatch",
     "应收账款均期 - 应付账款均期", "天", "scf_risk", 0.15, 30, 60, "below"),
    ("SCF_RSK_05", "融资担保覆盖率",   "fibo-fnd:FinancingGuaranteeCoverage",
     "担保品价值 / 融资余额 × 100%", "%", "scf_risk", 0.15, 120, 100, "above"),

    # Extra indicators for 47 total
    ("SCF_AR_07",  "回款核实率",         "fibo-fnd:PaymentVerificationRate",
     "已核实回款 / 总回款 × 100%", "%", "scf_ar", 0.0, 90, 70, "above"),
    ("SCF_AR_08",  "应收账款增速",       "fibo-fnd:ARGrowthRate",
     "应收账款同比增速", "%", "scf_ar", 0.0, 30, 60, "below"),
    ("SCF_AR_09",  "账龄90天以内占比",   "fibo-fnd:ARWithin90Days",
     "90天以内应收 / 总应收 × 100%", "%", "scf_ar", 0.0, 70, 50, "above"),
    ("SCF_COR_05", "核心企业现金流",     "fibo-fnd:CoreOperatingCashFlow",
     "核心企业经营现金流（万元）", "万元", "scf_core", 0.0, 1000, 0, "above"),
    ("SCF_TRD_06", "电商平台交叉验证",   "fibo-fnd:EcommerceCrossVerification",
     "电商平台可验证交易占比", "%", "scf_trade", 0.0, 80, 60, "above"),
    ("SCF_TRD_07", "物流单据核实率",     "fibo-fnd:LogisticsVerificationRate",
     "物流单据核实完整率", "%", "scf_trade", 0.0, 90, 75, "above"),
    ("SCF_RSK_06", "供应链系统集成度",   "fibo-fnd:SCFSystemIntegration",
     "已实现系统对接的供应商数 / 总供应商数 × 100%", "%", "scf_risk", 0.0, 50, 20, "above"),
    ("SCF_RSK_07", "历史违约率",         "fibo-fnd:HistoricalDefaultRate",
     "近3年违约次数", "次", "scf_risk", 0.0, 0, 1, "below"),
    ("SCF_RSK_08", "保险覆盖率",         "fibo-fnd:InsuranceCoverageRate",
     "有保险的应收账款 / 总应收账款 × 100%", "%", "scf_risk", 0.0, 60, 30, "above"),
    ("SCF_RSK_09", "汇率风险敞口",       "fibo-fnd:FXExposureRatio",
     "外币应收 / 总应收 × 100%", "%", "scf_risk", 0.0, 20, 40, "below"),
    ("SCF_RSK_10", "集中度风险综合评分", "fibo-fnd:ConcentrationRiskScore",
     "客户+地区+行业集中度综合评分（0-100，越高越好）", "分", "scf_risk", 0.0, 60, 40, "above"),
]


# ─── Runner ───────────────────────────────────────────────────────────────────

async def main():
    print("Creating fi_ tables if not exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        async with session.begin():
            # ── 清空已有数据（幂等重跑）──────────────────────────────
            await session.execute(text("DELETE FROM fi_indicator"))
            await session.execute(text("DELETE FROM fi_dimension"))
            print("Cleared existing dimension/indicator data.")

            # ── 插入维度 ─────────────────────────────────────────────
            all_dims = (
                [(d, "pre_loan") for d in PRE_LOAN_DIMENSIONS]
                + [(d, "post_loan") for d in POST_LOAN_DIMENSIONS]
                + [(d, "scf") for d in SCF_DIMENSIONS]
            )
            dim_map: dict[str, FiDimension] = {}

            for dim_data, scenario in all_dims:
                dim = FiDimension(
                    code=dim_data["code"],
                    name=dim_data["name"],
                    weight=dim_data["weight"],
                    scenario=scenario,
                    sort_order=dim_data["sort_order"],
                )
                session.add(dim)
                dim_map[dim_data["code"]] = dim

            await session.flush()
            print(f"Inserted {len(dim_map)} dimensions.")

            # ── 插入指标 ─────────────────────────────────────────────
            def make_indicators(rows, scenario):
                for row in rows:
                    code, name, fibo_path, formula, unit, dim_code, weight, warn, alert_thr, direction = row
                    dim = dim_map.get(dim_code)
                    ind = FiIndicator(
                        code=code,
                        name=name,
                        fibo_path=fibo_path,
                        formula=formula,
                        data_source=f"ERP系统/{scenario.replace('_', ' ').title()}模块",
                        unit=unit,
                        dimension_id=dim.id if dim else None,
                        scenario=scenario,
                        weight=weight if weight > 0 else None,
                        threshold_warning=warn,
                        threshold_alert=alert_thr,
                        threshold_direction=direction,
                    )
                    session.add(ind)

            make_indicators(PRE_LOAN_INDICATORS, "pre_loan")
            make_indicators(POST_LOAN_INDICATORS, "post_loan")
            make_indicators(SCF_INDICATORS, "scf")

            await session.flush()

    total_pre = len(PRE_LOAN_INDICATORS)
    total_post = len(POST_LOAN_INDICATORS)
    total_scf = len(SCF_INDICATORS)
    print(f"Seed complete: {total_pre} pre_loan + {total_post} post_loan + {total_scf} scf = {total_pre + total_post + total_scf} indicators")


if __name__ == "__main__":
    asyncio.run(main())
