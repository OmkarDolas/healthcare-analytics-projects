-- Average RAF score by segment, plan and payment year, with year-over-year change.
WITH plan_year AS (
    SELECT segment, plan, payment_year,
           COUNT(*)                  AS members,
           ROUND(AVG(raf_score), 4)  AS avg_raf,
           ROUND(AVG(hcc_count), 3)  AS avg_hcc_count
      FROM member_years_clean
     GROUP BY segment, plan, payment_year
)
SELECT p.*,
       ROUND(avg_raf - LAG(avg_raf) OVER (PARTITION BY segment, plan ORDER BY payment_year), 4) AS raf_yoy_change,
       ROUND(100.0 * (avg_raf / LAG(avg_raf) OVER (PARTITION BY segment, plan ORDER BY payment_year) - 1), 2) AS raf_yoy_pct
  FROM plan_year p
 ORDER BY segment, plan, payment_year;
