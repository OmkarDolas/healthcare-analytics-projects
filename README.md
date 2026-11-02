# Healthcare Analytics Projects

Four end-to-end healthcare data projects on **synthetic** data: three health plan analytics projects (SQL,
Python, R, SAS, Tableau, Power BI, Excel, Google Sheets) and one clinical AI project (OMOP EHR data, PyTorch,
model evaluation beyond AUROC, LLM-based clinical-note extraction). Each project lives on its own branch.

| Project | Branch | Focus | Tools |
|---|---|---|---|
| Medicare Advantage & ACA Risk Adjustment Analytics | [`medicare-aca-risk-adjustment-analytics`](https://github.com/OmkarDolas/healthcare-analytics-projects/tree/medicare-aca-risk-adjustment-analytics) | RAF trends, HCC recapture, statistical testing, stakeholder deck | SQL, Python, R, SAS, Tableau, PowerPoint |
| Membership Reporting & Forecasting Dashboard | [`membership-reporting-forecasting-dashboard`](https://github.com/OmkarDolas/healthcare-analytics-projects/tree/membership-reporting-forecasting-dashboard) | Membership reporting, Finance reconciliation, forecasting, variance analysis | SQL, Python, Power BI (DAX), Excel, Google Sheets |
| Operational Performance Reporting & Data Quality Automation | [`operational-reporting-data-quality-automation`](https://github.com/OmkarDolas/healthcare-analytics-projects/tree/operational-reporting-data-quality-automation) | Operational KPIs, automated data quality checks, reconciliation, anomaly detection | SQL, Python, Tableau, Excel |
| Cardiovascular Risk Prediction on EHR Data & Clinical-Note Extraction | [`cardiovascular-risk-ehr-evaluation`](https://github.com/OmkarDolas/healthcare-analytics-projects/tree/cardiovascular-risk-ehr-evaluation) | 5-year CVD risk on OMOP-shaped EHR data; calibration, subgroup, temporal and external validation, dataset-shift stress tests; LLM note extraction with an evaluation harness | Python, SQL (DuckDB), OMOP CDM, PyTorch, XGBoost, scikit-learn, Synthea |

All data is synthetic: the health plan projects generate it with `src/generate_data.py`, and the clinical AI project with [Synthea](https://github.com/synthetichealth/synthea). No real member, claims or patient data is used.

**Author:** Omkar Dolas · [LinkedIn](https://linkedin.com/in/omkar-dolas)
