import json

import pandas as pd

from src.notes.extractors import LLMExtractor, RuleBasedExtractor
from src.notes.harness import run_extractor, score

NOTE = """2019-05-07

# Chief Complaint
No complaints.

# History of Present Illness
Maria is a 64 year-old nonhispanic white female. Patient has a history of viral sinusitis (disorder), history of myocardial infarction (situation).

# Social History
Patient is married. Patient quit smoking at age 30.

# Allergies
No Known Allergies.

# Medications
simvastatin 20 mg oral tablet; aspirin 81 mg oral tablet; lisinopril 10 mg oral tablet

# Assessment and Plan
Patient is presenting with essential hypertension (disorder), prediabetes (finding).
"""


def test_rule_extractor_reads_template_fields():
    out = RuleBasedExtractor().extract(NOTE)
    assert out.age == 64 and out.sex == "female" and out.smoking_status == "former"
    assert {"hypertension", "prediabetes", "myocardial_infarction"} <= set(out.conditions)
    assert set(out.medication_classes) == {"statin", "antiplatelet", "antihypertensive"}
    assert all(e.quote.lower() in NOTE.lower() for e in out.evidence)


class FakeClient:
    """Returns queued responses so the LLM code path is tested without a model."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete(self, system, user):
        self.prompts.append(user)
        return self.responses.pop(0)


def test_llm_extractor_repairs_invalid_output():
    bad = json.dumps({"age": 64, "sex": "F", "conditions": ["hypertension"]})  # 'F' is not allowed
    good = "```json\n" + json.dumps({"age": 64, "sex": "female", "smoking_status": "former",
                                     "conditions": ["hypertension"], "medication_classes": ["statin"],
                                     "evidence": [{"field": "age", "quote": "64 year-old"}]}) + "\n```"
    client = FakeClient([bad, good])
    ext = LLMExtractor(client, max_retries=2)
    out = ext.extract(NOTE)
    assert out.sex == "female" and out.conditions == ["hypertension"]
    assert ext.stats == {"calls": 2, "repairs": 1, "failures": 0, "seconds": ext.stats["seconds"]}
    assert "previous answer was invalid" in client.prompts[1]


def test_llm_extractor_failure_returns_empty_extraction():
    ext = LLMExtractor(FakeClient(["not json"] * 3), max_retries=2)
    out = ext.extract(NOTE)
    assert out.conditions == [] and ext.stats["failures"] == 1


def test_harness_scores_against_reference():
    eval_set = pd.DataFrame([{
        "note_id": "n1", "patient_id": "p1", "note_date": "2019-05-07", "text": NOTE,
        "ref_age": 64, "ref_sex": "female", "ref_smoking_status": "former",
        "ref_conditions": ["hypertension", "prediabetes", "myocardial_infarction", "obesity"],
        "ref_medication_classes": ["statin", "antiplatelet", "antihypertensive"],
        "ref_problem_list": ["hypertension", "type_2_diabetes"],
    }])
    res = run_extractor(RuleBasedExtractor(), eval_set)
    s = score(res, "rules")
    labels = s["labels"].set_index(["field", "label"])
    assert labels.loc[("conditions", "obesity"), "fn"] == 1          # missed: not in the note
    assert labels.loc[("conditions", "MICRO"), "precision"] == 1.0
    assert s["summary"].evidence_grounding_rate.iloc[0] == 1.0
    assert s["summary"].problem_list_conditions_missing_from_note.iloc[0] == 0.5
