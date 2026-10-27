-- Weekly KPI trend with 7-day rolling averages and week-over-week change (window functions).
WITH daily AS (
    SELECT *,
           ROUND(AVG(avg_turnaround_days) OVER w7, 2) AS turnaround_7d_avg,
           ROUND(AVG(abandonment_pct)     OVER w7, 2) AS abandonment_7d_avg
      FROM daily_kpis
    WINDOW w7 AS (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
),
weekly AS (
    SELECT DATE(date, 'weekday 0', '-6 days') AS week_start,
           SUM(received) AS received, SUM(processed) AS processed,
           ROUND(100.0 * SUM(processed) / SUM(received), 2)        AS processing_rate_pct,
           ROUND(AVG(auto_adjudication_pct), 2)                    AS auto_adjudication_pct,
           ROUND(AVG(denial_rate_pct), 2)                          AS denial_rate_pct,
           ROUND(AVG(avg_turnaround_days), 2)                      AS avg_turnaround_days,
           SUM(calls_offered) AS calls_offered,
           ROUND(100.0 * SUM(calls_answered) / SUM(calls_offered), 2) AS answer_rate_pct,
           ROUND(AVG(abandonment_pct), 2)                          AS abandonment_pct,
           ROUND(AVG(aht_sec), 1)                                  AS aht_sec,
           MAX(turnaround_7d_avg)                                  AS peak_turnaround_7d_avg,
           MAX(abandonment_7d_avg)                                 AS peak_abandonment_7d_avg
      FROM daily GROUP BY 1
)
SELECT *,
       ROUND(avg_turnaround_days - LAG(avg_turnaround_days) OVER (ORDER BY week_start), 2) AS turnaround_wow_change,
       ROUND(abandonment_pct - LAG(abandonment_pct) OVER (ORDER BY week_start), 2)         AS abandonment_wow_change,
       ROUND(100.0 * (1.0 * calls_offered / LAG(calls_offered) OVER (ORDER BY week_start) - 1), 2) AS calls_wow_pct
  FROM weekly
 ORDER BY week_start;
