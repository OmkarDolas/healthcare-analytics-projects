"""End-to-end check of the OMOP ETL and cohort SQL on a tiny hand-built Synthea-format extract."""
from pathlib import Path

import pandas as pd

from src.build_cohort import build_cohort
from src.omop_etl import build_omop

P1, P2, P3 = "aaaaaaaa-0000-0000-0000-000000000001", "aaaaaaaa-0000-0000-0000-000000000002", \
    "aaaaaaaa-0000-0000-0000-000000000003"


def _write(tmp: Path) -> Path:
    d = tmp / "csv"
    d.mkdir()
    pd.DataFrame([
        {"Id": P1, "BIRTHDATE": "1950-03-01", "DEATHDATE": None, "RACE": "white", "ETHNICITY": "nonhispanic",
         "GENDER": "M", "STATE": "Massachusetts"},
        {"Id": P2, "BIRTHDATE": "1955-06-01", "DEATHDATE": None, "RACE": "black", "ETHNICITY": "nonhispanic",
         "GENDER": "F", "STATE": "Massachusetts"},
        {"Id": P3, "BIRTHDATE": "1952-01-01", "DEATHDATE": "2012-06-01", "RACE": "asian", "ETHNICITY": "hispanic",
         "GENDER": "F", "STATE": "Massachusetts"},
    ]).to_csv(d / "patients.csv", index=False)
    enc = []
    for pid in (P1, P2, P3):
        for year in range(2003, 2026):
            if pid == P3 and year > 2012:
                break
            enc.append({"Id": f"{pid[-1]}-{year}", "START": f"{year}-06-01T09:00:00Z",
                        "STOP": f"{year}-06-01T09:30:00Z", "PATIENT": pid, "ENCOUNTERCLASS": "wellness"})
    pd.DataFrame(enc).to_csv(d / "encounters.csv", index=False)
    pd.DataFrame([
        {"START": "2008-06-01", "STOP": None, "PATIENT": P1, "ENCOUNTER": "1-2008", "SYSTEM": "SNOMED-CT",
         "CODE": "59621000", "DESCRIPTION": "Essential hypertension (disorder)"},
        {"START": "2012-06-01", "STOP": None, "PATIENT": P1, "ENCOUNTER": "1-2012", "SYSTEM": "SNOMED-CT",
         "CODE": "22298006", "DESCRIPTION": "Myocardial infarction (disorder)"},
    ]).to_csv(d / "conditions.csv", index=False)
    obs = []
    for pid in (P1, P2):
        for year in range(2003, 2026):
            obs.append({"DATE": f"{year}-06-01T09:00:00Z", "PATIENT": pid, "ENCOUNTER": f"{pid[-1]}-{year}",
                        "CATEGORY": "vital-signs", "CODE": "8480-6", "DESCRIPTION": "Systolic Blood Pressure",
                        "VALUE": 120 + (year - 2003) * (2 if pid == P1 else 0), "UNITS": "mm[Hg]",
                        "TYPE": "numeric"})
    obs.append({"DATE": "2009-06-01T09:00:00Z", "PATIENT": P1, "ENCOUNTER": "1-2009", "CATEGORY": "survey",
                "CODE": "72166-2", "DESCRIPTION": "Tobacco smoking status",
                "VALUE": "Current every day smoker (finding)", "UNITS": None, "TYPE": "text"})
    pd.DataFrame(obs).to_csv(d / "observations.csv", index=False)
    pd.DataFrame([{"START": "2008-06-01T09:00:00Z", "STOP": None, "PATIENT": P1, "ENCOUNTER": "1-2008",
                   "CODE": "314076", "DESCRIPTION": "lisinopril 10 MG Oral Tablet"}]).to_csv(
        d / "medications.csv", index=False)
    pd.DataFrame(columns=["START", "STOP", "PATIENT", "ENCOUNTER", "SYSTEM", "CODE", "DESCRIPTION"]).to_csv(
        d / "procedures.csv", index=False)
    return d


def test_omop_and_cohort(tmp_path):
    counts = build_omop(_write(tmp_path), tmp_path / "omop.duckdb")
    assert counts["person"] == 3 and counts["death"] == 1
    df, _ = build_cohort(tmp_path / "omop.duckdb")
    by = df.set_index(["person_source_value" if "person_source_value" in df else "person_id", "landmark_year"])
    # person 1: MI in 2012 -> event at the 2010 landmark; excluded after the event (prior CVD)
    p1 = df[df.sex == "M"].set_index("landmark_year")
    assert p1.loc[2010, "cvd_5y"] == 1 and p1.loc[2006, "cvd_5y"] == 0
    assert 2014 not in p1.index and 2018 not in p1.index
    assert p1.loc[2010, "hx_hypertension"] == 1 and p1.loc[2010, "rx_antihypertensive"] == 1
    assert p1.loc[2010, "smoking"] == "current"
    assert abs(p1.loc[2010, "sbp_slope_per_year"] - 2.0) < 0.05
    # person 3 died in 2012 without CVD -> no complete 5-year follow-up from 2010
    p3 = df[(df.sex == "F") & (df.race == "asian")]
    assert 2010 not in set(p3.landmark_year)
    # person 2 is event-free and fully followed
    p2 = df[(df.sex == "F") & (df.race == "black")]
    assert set(p2.landmark_year) == {2006, 2010, 2014, 2018} and p2.cvd_5y.sum() == 0
    assert len(by) == len(df)
