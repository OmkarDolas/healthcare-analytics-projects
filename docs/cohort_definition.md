# Cohort and outcome definition

All definitions are SQL against OMOP CDM v5.4-shaped tables (`sql/cohort/`).

## Target cohort (landmark design)

| Element | Definition |
|---|---|
| Index dates | January 1 of 2006, 2010, 2014 and 2018 (a person can enter at several landmarks) |
| Age | 40 to 79 years at the index date |
| Active in care | At least one visit (`visit_occurrence`) in the 3 years before the index date |
| Prior CVD | Excluded if any CVD event or CVD history code is recorded on or before the index date |
| Alive | Death date, if any, after the index date |

## Outcome: incident cardiovascular disease within 5 years

First `condition_occurrence` in (index date, index date + 5 years] with a source code in the `cvd_event`
concept set: myocardial infarction (22298006, 401303003, 401314000), cerebrovascular accident (230690007),
heart failure (88805009, 84114007), ischemic heart disease (414545008) or cardiac arrest (410429000).

**Follow-up rule.** A row is kept if the person has the event within 5 years, or is event-free and both
observed and alive through the full 5 years. People who die of other causes or whose records end before
5 years are excluded. This complete-case 5-year label is simple and transparent. It ignores the competing
risk of non-CVD death, which would need a survival model (Fine-Gray or cause-specific hazards) to handle
properly. That is listed as a limitation and a next step.

## Baseline features (3-year lookback)

| Group | Features |
|---|---|
| Demographics | age, sex (race and ethnicity are **not** predictors; they are used only for subgroup audits) |
| Latest vitals/labs (LOINC) | systolic and diastolic BP, BMI, total, HDL and LDL cholesterol, triglycerides, HbA1c, glucose, eGFR, creatinine, heart rate |
| Longitudinal trajectories | per-year slope of SBP, BMI and HbA1c across the lookback; number of BP readings |
| Utilization | visits in the prior year; inpatient + emergency visits in 3 years |
| History (SNOMED) | hypertension, type 2 diabetes, prediabetes, hyperlipidemia, CKD, obesity, atrial fibrillation |
| Medications active at index (RxNorm descriptions) | statin, antihypertensive, glucose-lowering |
| Smoking (LOINC 72166-2) | never / former / current / unknown |

Missing labs are median-imputed with missingness indicators. Whether a lab was ordered carries information
in real EHR data, so the indicators are kept as features.

## Validation splits

Persons, not rows, are split, so a person's landmarks never appear in both training and test data.

| Split | Persons | Landmarks | Purpose |
|---|---|---|---|
| train | 56% of development-site persons | 2006-2014 | model fitting |
| validation | 14% | 2006-2014 | early stopping, model selection |
| internal test | 30% | 2006-2014 | same time and place |
| temporal test | same 30% | 2018 | later period (temporal validation) |
| external test | all Chicago, IL persons | all | different population (dataset shift) |
