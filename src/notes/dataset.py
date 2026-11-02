"""Build the extraction evaluation set: Synthea clinical notes paired with reference labels
derived from the same patients' structured EHR records."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.notes.vocab import SNOMED_TO_CONDITION, classify_medication

DATE_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*$", re.M)
UUID = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.txt$")


@dataclass
class NoteRecord:
    note_id: str
    patient_id: str
    note_date: str
    text: str


def split_notes(path: Path) -> list[NoteRecord]:
    """A Synthea notes file holds every encounter note for one patient, each starting with a date."""
    raw = path.read_text()
    patient_id = UUID.search(path.name).group(1)
    starts = [(m.start(), m.group(1)) for m in DATE_LINE.finditer(raw)]
    notes = []
    for i, (pos, date) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(raw)
        notes.append(NoteRecord(f"{patient_id}_{i:03d}", patient_id, date, raw[pos:end].strip()))
    return notes


def smoking_category(value: str | None) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "unknown"
    v = value.lower()
    if "never" in v:
        return "never"
    if "ex-smoker" in v or "former" in v:
        return "former"
    if "smoker" in v or "every day" in v:
        return "current"
    return "unknown"


def reference_labels(patient_id: str, note_date: str, tables: dict) -> dict:
    """Reference labels for one note, derived from the structured record.

    Note-level reference (what the note documents). Synthea's note template lists resolved
    conditions and completed prescriptions as history, plus items recorded at the visit itself:
      conditions          = diagnosed on the visit date, or resolved on/before it
      medication_classes  = prescribed on the visit date, or stopped before it
    Problem list (what the structured EHR says is active at the visit) is kept separately to
    measure how much of the active problem list a single note leaves out.
    """
    d = pd.Timestamp(note_date)
    pat = tables["patients"].loc[patient_id]
    birth = pd.Timestamp(pat["BIRTHDATE"])
    age = d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))

    c = tables["conditions"]
    c = c[c.PATIENT == patient_id]
    note_c = c[(c.S == d) | (c.E <= d)]
    active_c = c[(c.S <= d) & (c.E.isna() | (c.E > d))]
    to_label = lambda codes: sorted({SNOMED_TO_CONDITION[x] for x in codes if x in SNOMED_TO_CONDITION})

    m = tables["medications"]
    m = m[m.PATIENT == patient_id]
    note_m = m[(m.S == d) | (m.E < d)]
    classes = sorted(set().union(*[classify_medication(x) for x in note_m.DESCRIPTION])) if len(note_m) else []

    obs = tables["smoking"]
    obs = obs[(obs.PATIENT == patient_id) & (obs.D <= d)]
    smoking = smoking_category(obs.sort_values("D").VALUE.iloc[-1] if len(obs) else None)

    return {"age": int(age), "sex": "male" if pat["GENDER"] == "M" else "female",
            "smoking_status": smoking, "conditions": to_label(note_c.CODE),
            "medication_classes": classes, "problem_list": to_label(active_c.CODE)}


def build_eval_set(notes_dir: Path, csv_dir: Path, seed: int = 0) -> pd.DataFrame:
    """Per patient: the latest note, up to two notes from visits where a cardiometabolic condition
    was diagnosed (so positive labels are represented), and one random earlier note."""
    day = lambda s: pd.to_datetime(s, utc=True).dt.tz_localize(None).dt.normalize()
    tables = {"patients": pd.read_csv(csv_dir / "patients.csv").set_index("Id")}
    cond = pd.read_csv(csv_dir / "conditions.csv", dtype={"CODE": str})
    tables["conditions"] = cond.assign(S=day(cond.START), E=day(cond.STOP))
    meds = pd.read_csv(csv_dir / "medications.csv")
    tables["medications"] = meds.assign(S=day(meds.START), E=day(meds.STOP))
    obs = pd.read_csv(csv_dir / "observations.csv", usecols=["DATE", "PATIENT", "CODE", "VALUE"])
    obs = obs[obs.CODE == "72166-2"]
    tables["smoking"] = obs.assign(D=day(obs.DATE))
    target_codes = set(SNOMED_TO_CONDITION)

    rng = np.random.default_rng(seed)
    rows = []
    for path in sorted(Path(notes_dir).glob("*.txt")):
        notes = split_notes(path)
        if not notes or notes[0].patient_id not in tables["patients"].index:
            continue
        pc = tables["conditions"]
        pc = pc[(pc.PATIENT == notes[0].patient_id) & pc.CODE.isin(target_codes)]
        dx_dates = {d.strftime("%Y-%m-%d") for d in pc.S}
        picks = [0]  # files list the most recent note first
        dx_idx = [i for i, n in enumerate(notes) if n.note_date in dx_dates and i != 0]
        if dx_idx:
            picks += list(rng.choice(dx_idx, size=min(2, len(dx_idx)), replace=False))
        rest = [i for i in range(1, len(notes)) if i not in picks]
        if rest:
            picks.append(int(rng.choice(rest)))
        for i in picks:
            n = notes[i]
            ref = reference_labels(n.patient_id, n.note_date, tables)
            rows.append({"note_id": n.note_id, "patient_id": n.patient_id, "note_date": n.note_date,
                         "text": n.text, **{f"ref_{k}": v for k, v in ref.items()}})
    return pd.DataFrame(rows)
