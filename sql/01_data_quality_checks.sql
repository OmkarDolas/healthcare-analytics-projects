-- Data quality checks run before any reporting. Each row is one check; failed_rows must be 0 to publish.
SELECT 'missing_county' AS check_name, COUNT(*) AS failed_rows FROM member_years WHERE county IS NULL OR county = ''
UNION ALL
SELECT 'invalid_raf_score', COUNT(*) FROM member_years WHERE raf_score < 0 OR raf_score > 10
UNION ALL
SELECT 'duplicate_member_year', COUNT(*) FROM (
    SELECT member_id, payment_year FROM member_years GROUP BY member_id, payment_year HAVING COUNT(*) > 1)
UNION ALL
SELECT 'age_out_of_segment_range', COUNT(*) FROM member_years
 WHERE (segment = 'MA' AND age < 65) OR (segment = 'ACA' AND (age < 18 OR age > 64))
UNION ALL
SELECT 'hcc_count_mismatch', COUNT(*) FROM member_years
 WHERE hcc_count <> HCC18 + HCC19 + HCC85 + HCC96 + HCC111 + HCC108 + HCC59 + HCC138 + HCC22 + HCC12;
