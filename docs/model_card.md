# Model card: 5-year incident CVD risk (synthetic EHR)

## Intended use
A teaching and portfolio model that shows how to build and evaluate a clinical risk model on OMOP-shaped
EHR data. **Not for clinical use.** It was trained on synthetic Synthea patients.

## Model details
| | |
|---|---|
| Task | Probability of a first CVD event (MI, stroke, heart failure, ischemic heart disease, cardiac arrest) within 5 years of an index date |
| Population | Adults 40–79 without prior CVD, active in care in the prior 3 years |
| Models | L2 logistic regression (C=0.5); XGBoost (depth 3, early stopping); PyTorch MLP (2×32, dropout 0.3, AdamW, early stopping) |
| Inputs | 31 features: age, sex, latest vitals and labs, 3-year trajectories, utilization, comorbidities, active medications, smoking ([full list](cohort_definition.md)) |
| Excluded inputs | Race and ethnicity, which are used only to audit subgroup performance |
| Missing data | Median imputation with missingness indicators |

## Performance (held-out persons; 95% person-level bootstrap CI)
| Model | Internal AUROC | Temporal AUROC (2018) | External AUROC | Brier (internal) | Calibration slope (internal) |
|---|---|---|---|---|---|
| Logistic regression | 0.764 (0.716–0.808) | 0.755 (0.694–0.808) | 0.747 (0.721–0.775) | 0.103 | 1.16 |
| XGBoost | 0.746 (0.694–0.789) | 0.731 (0.660–0.792) | 0.736 (0.708–0.761) | 0.108 | 1.74 |
| PyTorch MLP | 0.748 (0.702–0.790) | 0.713 (0.649–0.778) | 0.722 (0.692–0.751) | 0.106 | 1.32 |

Full metrics: [`outputs/metrics_overall.csv`](../outputs/metrics_overall.csv).

**Recommended model:** logistic regression. It was best or tied on every test set and is the most
transparent ([coefficients](../outputs/logistic_coefficients.csv)). The MLP had the lowest validation loss,
but the gap was within noise.

## Subgroup audit (PyTorch MLP, internal + temporal test)
| Group | n | Events | AUROC | Observed / expected |
|---|---|---|---|---|
| Female | 816 | 78 | 0.775 | **0.69** (over-predicts) |
| Male | 633 | 128 | 0.701 | **1.23** (under-predicts) |
| Age 40–54 | 818 | 54 | 0.698 | 0.66 |
| Age 55–64 | 447 | 98 | 0.650 | 1.12 |
| Age 65–79 | 184 | 54 | **0.577** | 1.12 |
| Black | 104 | 16 | 0.692 | 0.99 |
| Asian | 117 | 15 | 0.754 | 0.91 |
| White | 1,167 | 169 | 0.739 | 0.96 |
| Hispanic | 172 | 32 | 0.727 | 1.29 |

Groups with fewer than 10 events (Hawaiian, Native American, other) are reported in the CSV but flagged as
not assessable. **Action before any deployment:** sex-specific recalibration, and a model that adds
information beyond age for older adults.

## Robustness
See README finding 5 and [`outputs/shift_stress_tests.csv`](../outputs/shift_stress_tests.csv). The model
is most vulnerable to **outcome under-coding**, which input-drift monitoring cannot detect. Local
recalibration needs enough events: 117 events from 427 people was not enough to calibrate reliably.

## Limitations
Synthetic data with simplified disease models; competing risk of non-CVD death not modeled; source-code
concept sets instead of OMOP standard concepts; a single development site.
