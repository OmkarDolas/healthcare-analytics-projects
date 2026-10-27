# Metric definitions, data quality rules and reporting process

## Sources
| Source | File | Grain | Owner |
|---|---|---|---|
| Claims processing system | `data/claims_ops.csv` | day x claim type (Medical, Pharmacy, Behavioral) | Claims Operations |
| Telephony system | `data/call_center.csv` | day x queue (Member, Provider, Broker) | Customer Service |
| Reporting system extract | `data/daily_ops_summary.csv` | day | BI / Reporting |

## Metric definitions
| KPI | Definition | Source |
|---|---|---|
| Processing rate % | processed / received | claims_ops |
| Auto-adjudication % | auto_adjudicated / processed (claims paid or denied with no manual touch) | claims_ops |
| Denial rate % | denied / processed | claims_ops |
| Clean claim % (proxy) | (processed - denied) / received | claims_ops |
| Avg turnaround days | Processed-weighted average of `avg_turnaround_days` | claims_ops |
| Answer rate % | calls_answered / calls_offered | call_center |
| Abandonment % | abandoned / calls_offered | call_center |
| AHT (sec) | Answered-weighted average handle time | call_center |
| ASA (sec) | Answered-weighted average speed of answer | call_center |
| 7-day rolling average | Mean of the KPI over the current and 6 prior days | derived |
| WoW change | This week's value minus last week's value | derived |

## Data quality rules (`sql/01_data_quality_checks.sql`)
| Dimension | Rule |
|---|---|
| Completeness | No null turnaround or handle time; every calendar date present in claims_ops |
| Uniqueness | One row per date x claim type and per date x queue |
| Validity | No negative counts; turnaround between 0 and 60 days; calls offered > 0 |
| Consistency | processed <= 1.3 x received (backlog burn-down allowed); denied and auto-adjudicated <= processed; answered + abandoned = offered |

Rows failing a row-level rule are **quarantined** (`outputs/quarantined_records.csv`), not deleted. A day with a
quarantined row is marked incomplete (`claim_types_reported` or `queues_reported` < 3) and excluded from charts
and anomaly detection so a missing row is not mistaken for an operational change.

## Reconciliation rule (`sql/02_cross_source_reconciliation.sql`)
Reporting-system daily totals (received, processed, denied) must match deduplicated claims_ops totals within
**0.5%**. Dates in only one system are exceptions. Each exception gets a `likely_cause`: missing source extract,
source row failed DQ, late-arriving file not loaded, or manual adjustment not posted to source.

## Anomaly rule
For each KPI, z = (today - mean of prior 28 complete days) / standard deviation of those days. |z| > 4 is flagged
(a lower threshold of 3 produced mostly single-day noise across ~3,000 daily tests). Flags within 3 days of each
other are grouped into one event (`outputs/anomaly_events.csv`) for the commentary.
Limitation: once an extreme day enters the 28-day baseline it widens the standard deviation, so the recovery days
after a large event are not flagged individually; the event grouping and 7-day averages cover that.

## Reporting process
1. Land the daily source extracts in `data/`.
2. Run `python src/run_report.py`.
3. Review `outputs/data_quality_report.html`; investigate every failed check with the source owner.
4. Work each row of `outputs/reconciliation_exceptions.csv`; confirm the likely cause and log the fix.
5. Review `outputs/anomaly_events.csv` and write commentary (cause, impact, owner, action).
6. Refresh Tableau from `outputs/tableau/`; send `outputs/Operations_KPI_Report.xlsx` to operations leaders.

## Tableau build
1. Connect to `outputs/tableau/daily_kpis.csv` and `weekly_kpis.csv` (Text file).
2. Filter `claim_types_reported = 3` for claims views and `queues_reported = 3` for call views.
3. Sheets: turnaround and processing rate (dual axis line), abandonment and ASA by week, auto-adjudication and
   denial rate, KPI cards with WoW change; reference line for the 7-day average.
4. Use `claims_by_type.csv` and `calls_by_queue.csv` for drill-down by claim type and queue.
5. Combine sheets into an Operations dashboard with a date-range filter applied to all sheets.
