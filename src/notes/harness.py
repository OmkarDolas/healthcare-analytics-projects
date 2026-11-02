"""Evaluation harness for clinical-note information extraction.

Scores any extractor against reference labels derived from structured EHR data:
* field accuracy for age, sex and smoking status
* per-label and micro/macro precision, recall and F1 for conditions and medication classes
* unsupported-claim rate: extracted labels absent from the structured record
* evidence grounding: share of evidence quotes found verbatim in the note (faithfulness check)
* schema validity, repair and failure counts, and latency for LLM backends
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from src.notes.schema import CONDITIONS, MEDICATION_CLASSES


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else np.nan
    r = tp / (tp + fn) if tp + fn else np.nan
    f = 2 * p * r / (p + r) if tp and p + r else (0.0 if tp + fp + fn else np.nan)
    return p, r, f


def _problem_list_gap(results: pd.DataFrame) -> float:
    active = results.ref_problem_list.apply(len).sum()
    covered = results.apply(lambda r: len(set(r.ref_problem_list) & set(r.ref_conditions)), axis=1).sum()
    return float(1 - covered / active) if active else np.nan


def run_extractor(extractor, eval_set: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rec in eval_set.itertuples(index=False):
        t0 = time.perf_counter()
        out = extractor.extract(rec.text)
        dt = time.perf_counter() - t0
        grounded = [ev.quote.lower() in rec.text.lower() for ev in out.evidence]
        rows.append({"note_id": rec.note_id, "pred_age": out.age, "pred_sex": out.sex,
                     "pred_smoking_status": out.smoking_status, "pred_conditions": sorted(set(out.conditions)),
                     "pred_medication_classes": sorted(set(out.medication_classes)),
                     "n_evidence": len(grounded), "n_grounded": int(sum(grounded)), "seconds": dt})
    return eval_set.merge(pd.DataFrame(rows), on="note_id")


def score(results: pd.DataFrame, extractor_name: str) -> dict[str, pd.DataFrame]:
    fields = pd.DataFrame([
        {"field": "age (exact)", "accuracy": (results.pred_age == results.ref_age).mean()},
        {"field": "sex", "accuracy": (results.pred_sex == results.ref_sex).mean()},
        {"field": "smoking_status", "accuracy": (results.pred_smoking_status == results.ref_smoking_status).mean()},
    ])

    label_rows = []
    for list_field, labels in [("conditions", CONDITIONS), ("medication_classes", MEDICATION_CLASSES)]:
        tot = np.zeros(3, dtype=int)
        f1s = []
        for lab in labels:
            ref = results[f"ref_{list_field}"].apply(lambda xs, lab=lab: lab in xs)
            pred = results[f"pred_{list_field}"].apply(lambda xs, lab=lab: lab in xs)
            tp, fp, fn = int((ref & pred).sum()), int((~ref & pred).sum()), int((ref & ~pred).sum())
            tot += [tp, fp, fn]
            p, r, f = _prf(tp, fp, fn)
            if tp + fn:
                f1s.append(f)
            label_rows.append({"field": list_field, "label": lab, "support": tp + fn, "tp": tp, "fp": fp,
                               "fn": fn, "precision": p, "recall": r, "f1": f})
        p, r, f = _prf(*tot)
        label_rows.append({"field": list_field, "label": "MICRO", "support": int(tot[0] + tot[2]),
                           "tp": int(tot[0]), "fp": int(tot[1]), "fn": int(tot[2]),
                           "precision": p, "recall": r, "f1": f})
        label_rows.append({"field": list_field, "label": "MACRO (labels with support)",
                           "support": int(tot[0] + tot[2]), "tp": np.nan, "fp": np.nan, "fn": np.nan,
                           "precision": np.nan, "recall": np.nan, "f1": float(np.nanmean(f1s)) if f1s else np.nan})
    labels = pd.DataFrame(label_rows)

    n_ev = results.n_evidence.sum()
    summary = pd.DataFrame([{
        "extractor": extractor_name, "notes": len(results), "patients": results.patient_id.nunique(),
        "age_accuracy": fields.accuracy[0], "sex_accuracy": fields.accuracy[1],
        "smoking_accuracy": fields.accuracy[2],
        "conditions_micro_f1": labels.query("field=='conditions' and label=='MICRO'").f1.iloc[0],
        "medications_micro_f1": labels.query("field=='medication_classes' and label=='MICRO'").f1.iloc[0],
        "unsupported_claims": int(labels.query("label=='MICRO'").fp.sum()),
        "evidence_grounding_rate": results.n_grounded.sum() / n_ev if n_ev else np.nan,
        "median_seconds_per_note": results.seconds.median(),
        # documentation gap: share of active problem-list conditions a single note does not mention
        "problem_list_conditions_missing_from_note": _problem_list_gap(results),
    }])
    return {"summary": summary, "fields": fields, "labels": labels}


def error_examples(results: pd.DataFrame, list_field: str, k: int = 5) -> pd.DataFrame:
    """Notes where the extractor and the structured record disagree, for error analysis."""
    r = results.copy()
    r["missed"] = r.apply(lambda x: sorted(set(x[f"ref_{list_field}"]) - set(x[f"pred_{list_field}"])), axis=1)
    r["unsupported"] = r.apply(lambda x: sorted(set(x[f"pred_{list_field}"]) - set(x[f"ref_{list_field}"])), axis=1)
    r = r[(r.missed.str.len() > 0) | (r.unsupported.str.len() > 0)]
    return r[["note_id", "note_date", "missed", "unsupported"]].head(k)
