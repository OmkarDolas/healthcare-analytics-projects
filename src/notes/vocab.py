"""Code lists used to derive reference labels from structured EHR data.

Reference labels come from SNOMED CT condition codes and RxNorm medication descriptions in the
structured record, not from the note text, so the harness measures agreement between what an
extractor reads in the note and what the structured EHR says.
"""
from __future__ import annotations

SNOMED_TO_CONDITION = {
    "59621000": "hypertension",
    "44054006": "type_2_diabetes",
    "714628002": "prediabetes",
    "15777000": "prediabetes",
    "55822004": "hyperlipidemia",
    "431855005": "chronic_kidney_disease",
    "431856006": "chronic_kidney_disease",
    "433144002": "chronic_kidney_disease",
    "431857002": "chronic_kidney_disease",
    "46177005": "chronic_kidney_disease",
    "162864005": "obesity",
    "408512008": "obesity",
    "414545008": "ischemic_heart_disease",
    "22298006": "myocardial_infarction",
    "401303003": "myocardial_infarction",
    "401314000": "myocardial_infarction",
    "399211009": "myocardial_infarction",
    "230690007": "stroke",
    "88805009": "heart_failure",
    "84114007": "heart_failure",
    "49436004": "atrial_fibrillation",
}

# Ingredient names (lower case) used to classify RxNorm drug descriptions into classes.
MEDICATION_CLASS_INGREDIENTS = {
    "statin": ["simvastatin", "atorvastatin", "rosuvastatin", "pravastatin", "lovastatin"],
    "antihypertensive": ["lisinopril", "losartan", "amlodipine", "hydrochlorothiazide", "metoprolol",
                         "atenolol", "valsartan", "chlorthalidone", "carvedilol"],
    "glucose_lowering": ["metformin", "insulin", "glipizide", "liraglutide", "semaglutide",
                         "empagliflozin", "canagliflozin", "sitagliptin"],
    "antiplatelet": ["aspirin", "clopidogrel", "ticagrelor", "prasugrel"],
    "anticoagulant": ["warfarin", "apixaban", "rivaroxaban", "dabigatran", "heparin"],
}


def classify_medication(description: str) -> set[str]:
    d = description.lower()
    return {cls for cls, names in MEDICATION_CLASS_INGREDIENTS.items() if any(n in d for n in names)}
