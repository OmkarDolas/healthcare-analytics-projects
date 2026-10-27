"""Generate synthetic daily health-plan operations data from two source systems plus a reporting extract.

claims_ops       - claims processing system (one row per day x claim type)
call_center      - telephony system (one row per day x queue)
daily_ops_summary - reporting-system extract that should reconcile to claims_ops daily totals

No real operational data is used. Realistic defects (duplicates, nulls, negatives, logical errors, a missing
day, reconciliation breaks) and two real operational events are injected so the pipeline has work to do:
  * 2025-06-09 claims system outage -> backlog and turnaround spike for about a week
  * 2025-10-15 .. 2025-12-07 Medicare open enrollment -> call volume and abandonment spike
"""
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(11)
DATA = Path(__file__).resolve().parents[1] / "data"
DATES = pd.date_range("2025-01-01", "2026-09-30", freq="D")
OUTAGE = pd.Timestamp("2025-06-09")
AEP_START, AEP_END = pd.Timestamp("2025-10-15"), pd.Timestamp("2025-12-07")

CLAIM_TYPES = {  # base daily volume, auto-adjudication rate, denial rate, turnaround days
    "Medical": (9000, 0.82, 0.075, 6.0),
    "Pharmacy": (14000, 0.95, 0.040, 1.2),
    "Behavioral": (1800, 0.71, 0.090, 8.5),
}
QUEUES = {"Member": (2600, 410), "Provider": (1500, 520), "Broker": (300, 380)}  # calls, AHT seconds


def claims_ops():
    rows = []
    for d in DATES:
        weekday = d.weekday() < 5
        days_since_outage = (d - OUTAGE).days
        outage = 0 <= days_since_outage < 7
        for ct, (vol, auto, deny, tat) in CLAIM_TYPES.items():
            received = int(vol * (1.0 if weekday else 0.35) * RNG.normal(1, 0.05))
            proc_rate = RNG.normal(0.985, 0.008)
            if outage:  # system down day 0, recovering over the week
                proc_rate = 0.25 + 0.11 * days_since_outage
            elif 7 <= days_since_outage < 12:  # backlog burn-down
                proc_rate = 1.25
            processed = int(received * proc_rate)
            turnaround = tat * RNG.normal(1, 0.04) * (2.6 - 0.15 * days_since_outage if outage else 1)
            rows.append(dict(
                date=d, claim_type=ct, received=received, processed=processed,
                pended=max(received - processed, 0) + int(received * 0.01),
                denied=int(processed * deny * RNG.normal(1, 0.06)),
                avg_turnaround_days=round(turnaround, 2),
                auto_adjudicated=int(processed * min(auto * RNG.normal(1, 0.01), 0.99) * (0.6 if outage else 1)),
            ))
    return pd.DataFrame(rows)


def call_center():
    rows = []
    for d in DATES:
        weekday = d.weekday() < 5
        aep = AEP_START <= d <= AEP_END
        for q, (vol, aht) in QUEUES.items():
            offered = int(vol * (1.0 if weekday else 0.2) * RNG.normal(1, 0.06) * (1.45 if aep and q != "Provider" else 1))
            abandon_rate = RNG.normal(0.045, 0.006) * (2.8 if aep and q != "Provider" else 1)
            abandoned = int(offered * max(abandon_rate, 0.01))
            rows.append(dict(
                date=d, queue=q, calls_offered=offered, calls_answered=offered - abandoned,
                avg_handle_time_sec=int(aht * RNG.normal(1, 0.04) * (1.12 if aep else 1)),
                avg_speed_answer_sec=int(RNG.normal(38, 6) * (3.2 if aep and q != "Provider" else 1)),
                abandoned=abandoned,
            ))
    return pd.DataFrame(rows)


def reporting_extract(claims):
    rep = claims.groupby("date", as_index=False)[["received", "processed", "denied"]].sum()
    rep.columns = ["date", "total_received", "total_processed", "total_denied"]
    # a late-arriving Behavioral file was not loaded into the reporting system on these days
    for d in ("2025-03-14", "2025-08-22", "2026-02-06"):
        beh = claims[(claims.date == d) & (claims.claim_type == "Behavioral")]
        rep.loc[rep.date == d, ["total_received", "total_processed"]] -= beh[["received", "processed"]].values
    rep.loc[rep.date == "2026-05-19", "total_denied"] += 900  # manual adjustment never posted to source
    return rep


def inject_defects(claims, calls):
    claims = claims[claims.date != "2025-11-27"]  # missing day: extract job failed (Thanksgiving)
    dup = claims.sample(6, random_state=3)
    claims = pd.concat([claims, dup], ignore_index=True)  # duplicate loads
    idx = claims.sample(12, random_state=4).index
    claims.loc[idx[:4], "avg_turnaround_days"] = np.nan
    claims.loc[idx[4:7], "denied"] = -claims.loc[idx[4:7], "denied"]
    claims.loc[idx[7:], "processed"] = (claims.loc[idx[7:], "received"] * 1.6).astype(int)  # processed > received
    cidx = calls.sample(8, random_state=5).index
    calls.loc[cidx[:4], "avg_handle_time_sec"] = np.nan
    calls.loc[cidx[4:], "calls_answered"] = calls.loc[cidx[4:], "calls_offered"] + 50  # answered > offered
    return claims.sort_values(["date", "claim_type"]), calls


def main():
    DATA.mkdir(exist_ok=True)
    claims = claims_ops()
    rep = reporting_extract(claims)
    claims, calls = inject_defects(claims, call_center())
    fmt = "%Y-%m-%d"
    claims.to_csv(DATA / "claims_ops.csv", index=False, date_format=fmt)
    calls.to_csv(DATA / "call_center.csv", index=False, date_format=fmt)
    rep.to_csv(DATA / "daily_ops_summary.csv", index=False, date_format=fmt)
    print(f"claims_ops.csv: {len(claims):,} rows | call_center.csv: {len(calls):,} rows | "
          f"daily_ops_summary.csv: {len(rep):,} rows")


if __name__ == "__main__":
    main()
