"""Generate synthetic monthly membership, sales activity, finance-ledger membership and budget data.

Layouts follow a health plan membership reporting mart: one row per month x product x region.
No real enrollment data is used. Seasonality mimics Medicare AEP (January) and ACA Open Enrollment.
2026 includes two market shifts (ACA subsidy expiry, a PPO competitor exit) for the variance analysis to explain.
"""
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(7)
DATA = Path(__file__).resolve().parents[1] / "data"

MONTHS = pd.date_range("2021-01-01", "2026-09-01", freq="MS")
REGIONS = {"Philadelphia": 0.33, "Montgomery": 0.21, "Delaware": 0.16, "Bucks": 0.16, "Chester": 0.14}
# product: (line of business, starting members, monthly trend, January step-up, owner team)
PRODUCTS = {
    "MA-HMO": ("Medicare Advantage", 62000, 0.0035, 0.055, "Government Markets"),
    "MA-PPO": ("Medicare Advantage", 41000, 0.0045, 0.060, "Government Markets"),
    "PDP": ("Medicare Part D", 28000, -0.0010, 0.030, "Government Markets"),
    "ACA Individual": ("Commercial Individual", 35000, 0.0020, 0.080, "Commercial Sales"),
    "Large Group": ("Commercial Group", 210000, 0.0005, 0.020, "Commercial Sales"),
    "Small Group": ("Commercial Group", 54000, -0.0015, 0.015, "Commercial Sales"),
}


def membership():
    rows = []
    for prod, (lob, start, trend, jan, owner) in PRODUCTS.items():
        level = start
        for m in MONTHS:
            month_factor = 1 + trend + RNG.normal(0, 0.002)
            if m.month == 1:
                month_factor += jan
            if m.year == 2026:  # 2026 shifts the history cannot predict
                if prod == "ACA Individual":  # enhanced premium subsidies expired
                    month_factor -= 0.10 if m.month == 1 else 0.006
                if prod == "MA-PPO":  # competitor exited the PPO market
                    month_factor += 0.025 if m.month == 1 else 0.002
            if m.month in (2, 3) and lob != "Commercial Group":
                month_factor -= jan * 0.25  # post-enrollment-period disenrollment
            prev, level = level, level * month_factor
            for region, share in REGIONS.items():
                members = int(level * share * (1 + RNG.normal(0, 0.004)))
                gross_adds = int(max(level - prev, 0) * share + level * share * RNG.uniform(0.008, 0.012))
                rows.append((m, prod, lob, region, members, gross_adds))
    df = pd.DataFrame(rows, columns=["month", "product", "line_of_business", "region", "members", "gross_adds"])
    df = df.sort_values(["product", "region", "month"])
    df["prior_members"] = df.groupby(["product", "region"]).members.shift(1)
    df["terminations"] = (df.prior_members + df.gross_adds - df.members).fillna(0).clip(lower=0).astype(int)
    return df.drop(columns="prior_members").reset_index(drop=True)


def finance_ledger(mem):
    """Finance's billed-membership view. Usually matches, but retro terminations and a late file create
    variances that the reconciliation step must explain."""
    fin = mem[["month", "product", "region", "members"]].copy()
    fin["billed_members"] = (fin.members * (1 - RNG.uniform(0, 0.002, len(fin)))).round().astype(int)
    late = (fin["product"] == "MA-PPO") & (fin.month == "2026-03-01") & (fin.region == "Philadelphia")
    fin.loc[late, "billed_members"] = (fin.loc[late, "members"] * 0.93).round().astype(int)
    retro = (fin["product"] == "ACA Individual") & (fin.month == "2026-06-01")
    fin.loc[retro, "billed_members"] = (fin.loc[retro, "members"] * 0.97).round().astype(int)
    return fin.drop(columns="members")


def budget(mem):
    """2026 budget built from Dec-2025 actuals with planned growth (what Finance and Actuarial signed off)."""
    dec = mem[mem.month == "2025-12-01"].groupby("product").members.sum()
    plan_growth = {"MA-HMO": 0.07, "MA-PPO": 0.085, "PDP": 0.02, "ACA Individual": 0.095,
                   "Large Group": 0.025, "Small Group": 0.01}
    rows = []
    for prod, base in dec.items():
        for m in pd.date_range("2026-01-01", "2026-12-01", freq="MS"):
            jan_step = plan_growth[prod]
            rows.append((m, prod, int(base * (1 + jan_step) * (1 + 0.002 * (m.month - 1)))))
    return pd.DataFrame(rows, columns=["month", "product", "budget_members"])


def main():
    DATA.mkdir(exist_ok=True)
    mem = membership()
    mem.to_csv(DATA / "membership_monthly.csv", index=False, date_format="%Y-%m-%d")
    finance_ledger(mem).to_csv(DATA / "finance_billed_membership.csv", index=False, date_format="%Y-%m-%d")
    budget(mem).to_csv(DATA / "budget_2026.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame([(p, v[0], v[4]) for p, v in PRODUCTS.items()],
                 columns=["product", "line_of_business", "owner_team"]).to_csv(DATA / "dim_product.csv", index=False)
    print(f"membership_monthly.csv: {len(mem):,} rows, {mem.month.min():%Y-%m} to {mem.month.max():%Y-%m}")


if __name__ == "__main__":
    main()
