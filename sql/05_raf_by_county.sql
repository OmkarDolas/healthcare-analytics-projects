-- Average RAF and dual-eligible share by county for the latest payment year (Tableau map / bar input).
SELECT segment, county, payment_year,
       COUNT(*) AS members,
       ROUND(AVG(raf_score), 4) AS avg_raf,
       ROUND(100.0 * AVG(dual_eligible), 2) AS dual_pct
  FROM member_years_clean
 WHERE payment_year = (SELECT MAX(payment_year) FROM member_years_clean)
 GROUP BY segment, county, payment_year
 ORDER BY segment, avg_raf DESC;
