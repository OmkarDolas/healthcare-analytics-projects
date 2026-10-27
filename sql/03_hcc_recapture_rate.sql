-- HCC recapture rate: of members with an HCC documented in the prior year who are still enrolled,
-- the share whose HCC was documented again in the current year. Low recapture = RAF under-stated.
WITH hcc_long AS (
    SELECT member_id, segment, plan, payment_year, 'HCC18'  AS hcc, HCC18  AS flag FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC19',  HCC19  FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC85',  HCC85  FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC96',  HCC96  FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC111', HCC111 FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC108', HCC108 FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC59',  HCC59  FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC138', HCC138 FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC22',  HCC22  FROM member_years_clean UNION ALL
    SELECT member_id, segment, plan, payment_year, 'HCC12',  HCC12  FROM member_years_clean
)
SELECT cur.segment, cur.plan, cur.payment_year,
       SUM(prev.flag)                                   AS prior_year_hccs,
       SUM(CASE WHEN prev.flag = 1 AND cur.flag = 1 THEN 1 ELSE 0 END) AS recaptured_hccs,
       ROUND(100.0 * SUM(CASE WHEN prev.flag = 1 AND cur.flag = 1 THEN 1 ELSE 0 END) / SUM(prev.flag), 2) AS recapture_rate_pct
  FROM hcc_long cur
  JOIN hcc_long prev
    ON prev.member_id = cur.member_id AND prev.hcc = cur.hcc AND prev.payment_year = cur.payment_year - 1
 GROUP BY cur.segment, cur.plan, cur.payment_year
 ORDER BY cur.segment, cur.plan, cur.payment_year;
