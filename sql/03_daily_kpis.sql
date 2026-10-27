-- Daily operational KPIs from the validated (clean) tables.
-- claim_types_reported / queues_reported < 3 means a source row was quarantined: the day is incomplete.
WITH claims AS (
    SELECT date, COUNT(DISTINCT claim_type) AS claim_types_reported,
           SUM(received) AS received, SUM(processed) AS processed, SUM(pended) AS pended,
           SUM(denied) AS denied, SUM(auto_adjudicated) AS auto_adjudicated,
           ROUND(SUM(avg_turnaround_days * processed) / SUM(processed), 2) AS avg_turnaround_days
      FROM claims_clean GROUP BY date
),
calls AS (
    SELECT date, COUNT(DISTINCT queue) AS queues_reported,
           SUM(calls_offered) AS calls_offered, SUM(calls_answered) AS calls_answered, SUM(abandoned) AS abandoned,
           ROUND(1.0 * SUM(avg_handle_time_sec * calls_answered) / SUM(calls_answered), 1) AS aht_sec,
           ROUND(1.0 * SUM(avg_speed_answer_sec * calls_answered) / SUM(calls_answered), 1) AS asa_sec
      FROM calls_clean GROUP BY date
)
SELECT c.date, c.claim_types_reported, k.queues_reported, c.received, c.processed, c.pended, c.denied, c.avg_turnaround_days,
       ROUND(100.0 * c.processed / c.received, 2)               AS processing_rate_pct,
       ROUND(100.0 * c.auto_adjudicated / c.processed, 2)       AS auto_adjudication_pct,
       ROUND(100.0 * c.denied / c.processed, 2)                 AS denial_rate_pct,
       ROUND(100.0 * (c.processed - c.denied) / c.received, 2)  AS clean_claim_pct,
       k.calls_offered, k.calls_answered,
       ROUND(100.0 * k.calls_answered / k.calls_offered, 2)     AS answer_rate_pct,
       ROUND(100.0 * k.abandoned / k.calls_offered, 2)          AS abandonment_pct,
       k.aht_sec, k.asa_sec
  FROM claims c
  LEFT JOIN calls k ON k.date = c.date
 ORDER BY c.date;
