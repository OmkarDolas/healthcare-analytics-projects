"""Controlled dataset-shift stress tests.

Synthea simulates every state with the same clinical modules, so the Illinois population differs
from Massachusetts mainly in demographics, not in the model's features (see outputs/shift_summary.csv).
To study how the model behaves under realistic site-to-site differences, each scenario below applies
one documented, controlled shift to the external cohort.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LIPIDS = ["total_chol", "hdl", "ldl", "triglycerides"]


def case_mix_shift(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Older, more diabetic population (e.g. a referral centre): resample persons with weights
    proportional to exp(0.05 * (age - 60)) * (2 if type 2 diabetes else 1)."""
    rng = np.random.default_rng(seed)
    w = np.exp(0.05 * (df["age"] - 60)) * np.where(df["hx_diabetes_t2"] == 1, 2.0, 1.0)
    idx = rng.choice(len(df), size=len(df), replace=True, p=w / w.sum())
    out = df.iloc[idx].copy()
    out["person_id"] = out["person_id"].astype(str) + "_" + pd.Series(range(len(out)), index=out.index).astype(str)
    return out


def measurement_shift(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Different measurement practice: BP device reads 10 mmHg high, and lipid panels are ordered
    for only 40% of patients (missing for the rest)."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    out["sbp"] = out["sbp"] + 10
    drop = rng.random(len(out)) < 0.6
    out.loc[drop, LIPIDS] = np.nan
    return out


def outcome_undercoding(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Incomplete outcome capture (events treated at outside hospitals never coded): 30% of true
    5-year events are missing from the record."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    pos = out.index[out["cvd_5y"] == 1]
    lost = rng.choice(pos, size=int(round(0.3 * len(pos))), replace=False)
    out.loc[lost, "cvd_5y"] = 0
    return out


SCENARIOS = {
    "none (external site as simulated)": lambda df, seed: df.copy(),
    "case-mix shift (older, more diabetes)": case_mix_shift,
    "measurement shift (SBP +10 mmHg, 60% lipids missing)": measurement_shift,
    "outcome under-coding (30% of events missed)": outcome_undercoding,
}
