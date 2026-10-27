"""Generate synthetic, CMS-structured member-year data for Medicare Advantage (MA) and ACA populations.

No real member data is used. Field layouts mirror the kind of tables a health plan uses for
Risk Adjustment analytics (member demographics, HCC flags, plan, county, payment year).
HCC coefficients are illustrative values in the range of the CMS-HCC model, not official rates.
"""
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
DATA = Path(__file__).resolve().parents[1] / "data"

YEARS = [2023, 2024, 2025]
COUNTIES = ["Philadelphia", "Bucks", "Chester", "Delaware", "Montgomery"]
MA_PLANS = ["MA-HMO Gold", "MA-PPO Silver", "MA-HMO Value", "D-SNP"]
ACA_PLANS = ["ACA Bronze", "ACA Silver", "ACA Gold"]

# Illustrative HCC catalogue: code, description, coefficient, base prevalence
HCCS = pd.DataFrame(
    [
        ("HCC18", "Diabetes with Chronic Complications", 0.302, 0.14),
        ("HCC19", "Diabetes without Complication", 0.105, 0.18),
        ("HCC85", "Congestive Heart Failure", 0.331, 0.09),
        ("HCC96", "Specified Heart Arrhythmias", 0.268, 0.10),
        ("HCC111", "Chronic Obstructive Pulmonary Disease", 0.335, 0.11),
        ("HCC108", "Vascular Disease", 0.288, 0.08),
        ("HCC59", "Major Depressive / Bipolar Disorders", 0.309, 0.07),
        ("HCC138", "Chronic Kidney Disease, Moderate (Stage 3)", 0.069, 0.12),
        ("HCC22", "Morbid Obesity", 0.250, 0.06),
        ("HCC12", "Breast, Prostate and Other Cancers", 0.150, 0.05),
    ],
    columns=["hcc", "description", "coefficient", "base_prevalence"],
)


def demographic_factor(age, female, dual, segment):
    base = np.where(segment == "MA", 0.30 + (age - 65).clip(0) * 0.012, 0.18 + (age - 21).clip(0) * 0.006)
    return base + female * 0.03 + dual * 0.12


def build_members(n_ma=12000, n_aca=8000):
    rows = []
    for seg, n, plans in (("MA", n_ma, MA_PLANS), ("ACA", n_aca, ACA_PLANS)):
        age = RNG.integers(65, 95, n) if seg == "MA" else RNG.integers(21, 62, n)
        rows.append(
            pd.DataFrame(
                {
                    "member_id": [f"{seg[0]}{i:06d}" for i in range(n)],
                    "segment": seg,
                    "age": age,
                    "female": RNG.random(n) < 0.54,
                    "dual_eligible": (RNG.random(n) < (0.18 if seg == "MA" else 0.0)),
                    "plan": RNG.choice(plans, n),
                    "county": RNG.choice(COUNTIES, n, p=[0.34, 0.15, 0.14, 0.16, 0.21]),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def build_member_years(members):
    """Each member gets HCC flags per year. Chronic conditions persist, but a share are
    not re-documented (not 'recaptured') in later years, which is what drives RAF accuracy work."""
    out, flags_prev = [], None
    for y_idx, year in enumerate(YEARS):
        df = members.copy()
        df["payment_year"] = year
        df["age"] = df["age"] + y_idx
        older = ((df["age"] - 20) / 60).clip(0.2, 1.4).to_numpy()
        flags = {}
        for _, h in HCCS.iterrows():
            p = h.base_prevalence * older * np.where(df.segment == "ACA", 0.55, 1.0)
            new = RNG.random(len(df)) < p * (0.35 if flags_prev is not None else 1.0)
            if flags_prev is not None:
                # recapture improves each year as documentation programs mature
                recapture = 0.74 + 0.06 * y_idx + np.where(df.plan == "D-SNP", 0.04, 0.0)
                carried = flags_prev[h.hcc] & (RNG.random(len(df)) < recapture)
                new = new | carried
            flags[h.hcc] = new
        flag_df = pd.DataFrame(flags)
        coef = HCCS.set_index("hcc")["coefficient"]
        df["demographic_score"] = demographic_factor(df.age, df.female, df.dual_eligible, df.segment)
        df["disease_score"] = flag_df.astype(float).mul(coef, axis=1).sum(axis=1)
        df["hcc_count"] = flag_df.sum(axis=1)
        df["raf_score"] = (df.demographic_score + df.disease_score).round(4)
        out.append(pd.concat([df, flag_df.astype(int)], axis=1))
        flags_prev = flag_df
    return pd.concat(out, ignore_index=True)


def main():
    DATA.mkdir(exist_ok=True)
    members = build_members()
    my = build_member_years(members)
    # a few raw-data issues for the validation step to catch
    bad = my.sample(25, random_state=1).index
    my.loc[bad[:10], "county"] = None
    my.loc[bad[10:], "raf_score"] = -1.0
    my.to_csv(DATA / "member_years.csv", index=False)
    HCCS.to_csv(DATA / "hcc_reference.csv", index=False)
    print(f"member_years.csv: {len(my):,} rows | hcc_reference.csv: {len(HCCS)} rows")


if __name__ == "__main__":
    main()
