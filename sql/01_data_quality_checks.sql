-- Data quality checks on both source systems. One row per check; failed_rows must be 0 to publish.
WITH RECURSIVE calendar(d) AS (
    SELECT (SELECT MIN(date) FROM claims_ops)
    UNION ALL
    SELECT DATE(d, '+1 day') FROM calendar WHERE d < (SELECT MAX(date) FROM claims_ops)
)
SELECT 'claims_ops' AS source, 'completeness' AS dimension, 'null_turnaround_days' AS check_name,
       COUNT(*) AS failed_rows FROM claims_ops WHERE avg_turnaround_days IS NULL
UNION ALL
SELECT 'claims_ops', 'uniqueness', 'duplicate_date_claim_type', COALESCE(SUM(n - 1), 0) FROM (
    SELECT COUNT(*) AS n FROM claims_ops GROUP BY date, claim_type HAVING COUNT(*) > 1)
UNION ALL
SELECT 'claims_ops', 'validity', 'negative_counts', COUNT(*) FROM claims_ops
 WHERE received < 0 OR processed < 0 OR pended < 0 OR denied < 0 OR auto_adjudicated < 0
UNION ALL
SELECT 'claims_ops', 'validity', 'turnaround_out_of_range', COUNT(*) FROM claims_ops
 WHERE avg_turnaround_days < 0 OR avg_turnaround_days > 60
UNION ALL
SELECT 'claims_ops', 'consistency', 'processed_gt_received_plus_backlog', COUNT(*) FROM claims_ops
 WHERE processed > received * 1.3
UNION ALL
SELECT 'claims_ops', 'consistency', 'denied_or_auto_gt_processed', COUNT(*) FROM claims_ops
 WHERE denied > processed OR auto_adjudicated > processed
UNION ALL
SELECT 'claims_ops', 'completeness', 'missing_dates', COUNT(*) FROM calendar
 WHERE d NOT IN (SELECT DISTINCT date FROM claims_ops)
UNION ALL
SELECT 'call_center', 'completeness', 'null_handle_time', COUNT(*) FROM call_center WHERE avg_handle_time_sec IS NULL
UNION ALL
SELECT 'call_center', 'uniqueness', 'duplicate_date_queue', COALESCE(SUM(n - 1), 0) FROM (
    SELECT COUNT(*) AS n FROM call_center GROUP BY date, queue HAVING COUNT(*) > 1)
UNION ALL
SELECT 'call_center', 'consistency', 'answered_plus_abandoned_ne_offered', COUNT(*) FROM call_center
 WHERE calls_answered + abandoned <> calls_offered
UNION ALL
SELECT 'call_center', 'validity', 'negative_or_zero_offered_weekday', COUNT(*) FROM call_center
 WHERE calls_offered <= 0;
