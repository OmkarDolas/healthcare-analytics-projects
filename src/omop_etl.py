"""Load Synthea CSV exports into an OMOP CDM v5.4-shaped DuckDB database.

Usage:
    python -m src.omop_etl --synthea data/synthea/dev_ma/csv --db data/omop_dev.duckdb
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OMOP_SQL = sorted((ROOT / "sql" / "omop").glob("*.sql"))
STAGING = ["patients", "encounters", "conditions", "observations", "medications", "procedures"]


def build_omop(synthea_csv_dir: str | Path, db_path: str | Path) -> dict[str, int]:
    """Stage Synthea CSVs, run the OMOP SQL scripts, and return table row counts."""
    synthea_csv_dir = Path(synthea_csv_dir)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))
    for name in STAGING:
        csv = synthea_csv_dir / f"{name}.csv"
        if not csv.exists():
            raise FileNotFoundError(f"Missing Synthea export: {csv}")
        con.execute(
            f"CREATE TABLE stg_{name} AS SELECT * FROM read_csv_auto(?, header=true, all_varchar=false)",
            [str(csv)],
        )
    for sql_file in OMOP_SQL:
        con.execute(sql_file.read_text())

    tables = ["person", "death", "visit_occurrence", "observation_period", "condition_occurrence",
              "measurement", "observation", "drug_exposure", "procedure_occurrence"]
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    for name in STAGING:
        con.execute(f"DROP TABLE stg_{name}")
    con.close()
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--synthea", required=True, help="Directory with Synthea CSV export")
    ap.add_argument("--db", required=True, help="Output DuckDB path")
    args = ap.parse_args()
    counts = build_omop(args.synthea, args.db)
    for table, n in counts.items():
        print(f"{table:24s} {n:>10,d}")


if __name__ == "__main__":
    main()
