-- HCC prevalence (% of members) by segment and year, joined to the HCC reference table.
WITH totals AS (SELECT segment, payment_year, COUNT(*) AS members FROM member_years_clean GROUP BY 1, 2)
SELECT t.segment, t.payment_year, r.hcc, r.description, r.coefficient,
       ROUND(100.0 * CASE r.hcc
            WHEN 'HCC18'  THEN SUM(m.HCC18)  WHEN 'HCC19'  THEN SUM(m.HCC19)  WHEN 'HCC85' THEN SUM(m.HCC85)
            WHEN 'HCC96'  THEN SUM(m.HCC96)  WHEN 'HCC111' THEN SUM(m.HCC111) WHEN 'HCC108' THEN SUM(m.HCC108)
            WHEN 'HCC59'  THEN SUM(m.HCC59)  WHEN 'HCC138' THEN SUM(m.HCC138) WHEN 'HCC22' THEN SUM(m.HCC22)
            WHEN 'HCC12'  THEN SUM(m.HCC12) END / t.members, 2) AS prevalence_pct
  FROM totals t
  JOIN member_years_clean m ON m.segment = t.segment AND m.payment_year = t.payment_year
 CROSS JOIN hcc_reference r
 GROUP BY t.segment, t.payment_year, r.hcc
 ORDER BY t.segment, t.payment_year, prevalence_pct DESC;
