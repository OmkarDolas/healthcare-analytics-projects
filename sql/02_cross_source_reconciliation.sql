-- Reconcile the reporting-system extract to claims_ops daily totals (deduplicated source).
-- Business rule: any measure off by more than 0.5% (or a date present in only one system) is an exception.
WITH src AS (
    SELECT date, SUM(received) AS received, SUM(processed) AS processed, SUM(denied) AS denied
      FROM claims_dedup GROUP BY date
),
joined AS (
    SELECT r.date, s.received AS source_received, r.total_received AS report_received,
           s.processed AS source_processed, r.total_processed AS report_processed,
           s.denied AS source_denied, r.total_denied AS report_denied
      FROM daily_ops_summary r LEFT JOIN src s ON s.date = r.date
)
SELECT *,
       ROUND(100.0 * (report_received  - source_received)  / source_received, 2)  AS received_var_pct,
       ROUND(100.0 * (report_processed - source_processed) / source_processed, 2) AS processed_var_pct,
       ROUND(100.0 * (report_denied    - source_denied)    / source_denied, 2)    AS denied_var_pct,
       CASE WHEN source_received IS NULL THEN 'MISSING IN SOURCE'
            WHEN ABS(1.0 * (report_received  - source_received)  / source_received)  > 0.005
              OR ABS(1.0 * (report_processed - source_processed) / source_processed) > 0.005
              OR ABS(1.0 * (report_denied    - source_denied)    / source_denied)    > 0.005 THEN 'EXCEPTION'
            ELSE 'OK' END AS status
  FROM joined
 ORDER BY status DESC, date;
