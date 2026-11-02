"""Target schema for structured information extraction from clinical notes."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

CONDITIONS = (
    "hypertension", "type_2_diabetes", "prediabetes", "hyperlipidemia", "chronic_kidney_disease",
    "obesity", "ischemic_heart_disease", "myocardial_infarction", "stroke", "heart_failure",
    "atrial_fibrillation",
)
MEDICATION_CLASSES = (
    "statin", "antihypertensive", "glucose_lowering", "antiplatelet", "anticoagulant",
)

Condition = Literal[CONDITIONS]  # type: ignore[valid-type]
MedicationClass = Literal[MEDICATION_CLASSES]  # type: ignore[valid-type]


class Evidence(BaseModel):
    field: str = Field(description="Name of the extracted field this quote supports")
    quote: str = Field(description="Verbatim span copied from the note")


class CardioExtraction(BaseModel):
    """Cardiovascular-relevant facts stated in a single clinical note."""
    age: Optional[int] = Field(None, ge=0, le=120, description="Patient age in years at the visit")
    sex: Optional[Literal["male", "female"]] = None
    smoking_status: Literal["never", "former", "current", "unknown"] = "unknown"
    conditions: list[Condition] = Field(  # type: ignore[valid-type]
        default_factory=list, description="Conditions the note says the patient has or has had")
    medication_classes: list[MedicationClass] = Field(  # type: ignore[valid-type]
        default_factory=list, description="Drug classes appearing in the note's medication list")
    evidence: list[Evidence] = Field(default_factory=list,
                                     description="Supporting verbatim quotes, one per extracted fact")
