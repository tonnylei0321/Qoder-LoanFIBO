"""
Seed script: generate test companies and indicator values for development/demo.
Run AFTER seed_indicators.py.

Usage:
    python -m scripts.seed_test_data
"""

import asyncio
import sys
import os
import random
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from backend.app.database import async_session_factory

from backend.app.models.fi_company import FiCompany
from backend.app.models.fi_indicator import FiIndicator
from backend.app.models.fi_indicator_value import FiIndicatorValue
from backend.app.services.alert_engine import AlertEngine
from backend.app.services.scoring_engine import ScoringEngine


# ─── Test companies ────────────────────────────────────────────────────────────

TEST_COMPANIES = [
    {
        "name": "远大制造集团有限公司",
        "unified_code": "91110000123456789A",
        "industry": "装备制造",
        "region": "北京",
        "reg_tags": {
            "tech_finance": True,
            "green_finance": False,
            "inclusive_finance": False,
            "pension_finance": False,
            "digital_finance": True,
            "implicit_debt": False,
        },
        "risk_profile": "good",   # mostly normal indicators
    },
    {
        "name": "华南能源供应链有限公司",
        "unified_code": "91440000987654321B",
        "industry": "新能源",
        "region": "广州",
        "reg_tags": {
            "tech_finance": False,
            "green_finance": True,
            "inclusive_finance": False,
            "pension_finance": False,
            "digital_finance": False,
            "implicit_debt": False,
        },
        "risk_profile": "medium",  # some warnings
    },
    {
        "name": "中西部农业发展股份公司",
        "unified_code": "91500000112233445C",
        "industry": "农业",
        "region": "重庆",
        "reg_tags": {
            "tech_finance": False,
            "green_finance": True,
            "inclusive_finance": True,
            "pension_finance": False,
            "digital_finance": False,
            "implicit_debt": False,
        },
        "risk_profile": "poor",    # several alerts
    },
    {
        "name": "星海数字科技有限公司",
        "unified_code": "91310000556677889D",
        "industry": "信息技术",
        "region": "上海",
        "reg_tags": {
            "tech_finance": True,
            "green_finance": False,
            "inclusive_finance": False,
            "pension_finance": False,
            "digital_finance": True,
            "implicit_debt": False,
        },
        "risk_profile": "good",
    },
    {
        "name": "通汇贸易物流有限公司",
        "unified_code": "91330000998877665E",
        "industry": "批发零售",
        "region": "杭州",
        "reg_tags": {
            "tech_finance": False,
            "green_finance": False,
            "inclusive_finance": True,
            "pension_finance": False,
            "digital_finance": False,
            "implicit_debt": False,
        },
        "risk_profile": "medium",
    },
]


def _gen_value(
    indicator: FiIndicator,
    risk_profile: str,
) -> tuple[float, float]:
    """Generate a plausible (value, value_prev) pair based on risk profile."""
    warn = float(indicator.threshold_warning) if indicator.threshold_warning else None
    alert = float(indicator.threshold_alert) if indicator.threshold_alert else None
    direction = indicator.threshold_direction or "above"

    rng = random.Random()

    def rand_good():
        if direction == "above":
            base = warn if warn is not None else 1.0
            return base * rng.uniform(1.05, 1.6)
        else:
            base = warn if warn is not None else 1.0
            return base * rng.uniform(0.5, 0.85)

    def rand_warn():
        if warn is None or alert is None:
            return rand_good()
        if direction == "above":
            return rng.uniform(float(alert), float(warn))
        else:
            return rng.uniform(float(warn), float(alert))

    def rand_alert():
        if alert is None:
            return rand_warn()
        if direction == "above":
            return float(alert) * rng.uniform(0.4, 0.85)
        else:
            return float(alert) * rng.uniform(1.1, 1.8)

    if risk_profile == "good":
        weights = [0.85, 0.12, 0.03]
    elif risk_profile == "medium":
        weights = [0.55, 0.35, 0.10]
    else:  # poor
        weights = [0.30, 0.35, 0.35]

    choice = rng.choices(["good", "warn", "alert"], weights=weights)[0]
    gen_fn = {"good": rand_good, "warn": rand_warn, "alert": rand_alert}[choice]

    value = gen_fn()
    value_prev = value * rng.uniform(0.85, 1.15)

    return round(value, 4), round(value_prev, 4)


async def main():
    calc_date = date.today().replace(day=1)  # First of current month

    async with async_session_factory() as session:
        async with session.begin():
            # Remove existing test data
            await session.execute(text("DELETE FROM fi_alert_record"))
            await session.execute(text("DELETE FROM fi_score_record"))
            await session.execute(text("DELETE FROM fi_indicator_value"))
            await session.execute(text("DELETE FROM fi_company"))
            print("Cleared existing company/value data.")

            # Create companies
            company_objs = []
            for c in TEST_COMPANIES:
                profile = c.pop("risk_profile")
                company = FiCompany(**c)
                session.add(company)
                company_objs.append((company, profile))

            await session.flush()
            print(f"Created {len(company_objs)} test companies.")

            # Load all indicators
            all_indicators = (await session.execute(select(FiIndicator))).scalars().all()
            print(f"Found {len(all_indicators)} indicators.")

            # Generate indicator values for all companies × all scenarios
            scenarios = ["pre_loan", "post_loan", "scf"]
            for company, risk_profile in company_objs:
                for scenario in scenarios:
                    inds = [i for i in all_indicators if i.scenario == scenario]
                    for ind in inds:
                        value, value_prev = _gen_value(ind, risk_profile)
                        change_pct = None
                        if value_prev != 0:
                            change_pct = round((value - value_prev) / abs(value_prev) * 100, 4)

                        iv = FiIndicatorValue(
                            company_id=company.id,
                            indicator_id=ind.id,
                            value=value,
                            value_prev=value_prev,
                            change_pct=change_pct,
                            alert_level="normal",
                            data_quality="P0",
                            calc_date=calc_date,
                        )
                        session.add(iv)

            await session.flush()
            print("Inserted indicator values. Running alert evaluation...")

            # Run alert + scoring for each company × scenario
            for company, _ in company_objs:
                for scenario in scenarios:
                    alert_engine = AlertEngine(session)
                    await alert_engine.batch_evaluate(company.id, calc_date, scenario)

                    scoring_engine = ScoringEngine(session)
                    score = await scoring_engine.score(company.id, scenario, calc_date)
                    print(f"  {company.name} / {scenario}: score={score.total_score}, level={score.risk_level}")

    print("\nTest data seeded successfully!")
    print(f"Calc date: {calc_date}")
    print(f"Companies: {[c['name'] for c in TEST_COMPANIES[:5]]}")


if __name__ == "__main__":
    asyncio.run(main())
