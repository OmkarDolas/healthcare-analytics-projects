"""Run the cohort and feature SQL against an OMOP DuckDB database and export the analytic dataset.

Usage:
    python -m src.build_cohort --db data/omop_dev.duckdb --out data/analytic_dev.parquet
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COHORT_SQL = sorted((ROOT / "sql" / "cohort").glob("*.sql"))


def build_cohort(db_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (analytic dataset, attrition by landmark year)."""
    con = duckdb.connect(str(db_path))
    for sql_file in COHORT_SQL:
        con.execute(sql_file.read_text())
    df = con.execute("SELECT * FROM analytic_dataset").df()
    attrition = con.execute("""
        SELECT landmark_year, count(*) AS n, sum(cvd_5y) AS events
        FROM cohort GROUP BY 1 ORDER BY 1""").df()
    con.close()
    return df, attrition


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    df, attrition = build_cohort(args.db)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(attrition.to_string(index=False))
    print(f"rows={len(df):,} persons={df.person_id.nunique():,} event_rate={df.cvd_5y.mean():.3f}")


if __name__ == "__main__":
    main()
