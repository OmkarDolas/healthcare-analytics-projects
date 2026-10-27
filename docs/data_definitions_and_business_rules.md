# Data definitions, business rules and reporting procedure

## Sources
| Source | File | Grain | Owner |
|---|---|---|---|
| Enrollment system | `data/membership_monthly.csv` | month x product x region | Informatics |
| Finance billed membership | `data/finance_billed_membership.csv` | month x product x region | Finance |
| 2026 budget | `data/budget_2026.csv` | month x product | Finance / Actuarial |
| Product dimension | `data/dim_product.csv` | product | Sales Analytics |

## Data definitions
| Field | Definition |
|---|---|
| members | Members enrolled on the first of the month (point-in-time count) |
| gross_adds | New enrollments effective in the month |
| terminations | Disenrollments effective in the month (prior members + adds - current members) |
| net_change | members - prior month members |
| mom_pct / yoy_pct | Change vs prior month / same month prior year |
| billed_members | Members Finance billed premium for in the month |
| budget_members | Approved 2026 plan membership |

## Business rules
1. Membership is reported on the enrollment-system count; Finance billed membership is the control total.
2. Enrollment vs Finance variance above **1.0%** at product x region x month is researched before publishing.
3. Actual vs budget and actual vs forecast variance above **2.0%** is flagged and explained in the commentary.
4. The report is not published if any validation check in `sql/04_data_validation.sql` fails.

## Forecast method
Holt-Winters exponential smoothing (additive trend and 12-month seasonality) per product. Accuracy is measured
by back-test: train through Dec 2025, forecast Jan-Sep 2026, compare to actuals (MAPE). The production forecast
is refit on all actuals and projects to Dec 2027.

## Monthly reporting procedure
1. Refresh source extracts into `data/`.
2. `python src/run_reporting.py` (runs validation, reporting SQL, reconciliation, forecast).
3. Review `outputs/data_validation_report.csv`: all checks must show 0 failed rows.
4. Research every row in `outputs/reconciliation_exceptions.csv` with Finance; document the cause.
5. Review forecast and budget variances flagged RESEARCH and write commentary.
6. Refresh the Power BI report, Excel workbook and Google Sheet; distribute to Sales, Finance and Actuarial.
