-- Validation checks on the membership feed; failed_rows must be 0 before the report is published.
SELECT 'negative_or_null_members' AS check_name, COUNT(*) AS failed_rows
  FROM membership WHERE members IS NULL OR members < 0
UNION ALL
SELECT 'duplicate_month_product_region', COUNT(*) FROM (
    SELECT month, product, region FROM membership GROUP BY 1, 2, 3 HAVING COUNT(*) > 1)
UNION ALL
SELECT 'missing_months', (SELECT COUNT(DISTINCT product || region) * COUNT(DISTINCT month) FROM membership)
                         - (SELECT COUNT(*) FROM membership)
UNION ALL
SELECT 'product_not_in_dimension', COUNT(*) FROM membership m
  LEFT JOIN dim_product d ON d.product = m.product WHERE d.product IS NULL
UNION ALL
SELECT 'mom_swing_over_15pct', COUNT(*) FROM (
    SELECT members, LAG(members) OVER (PARTITION BY product, region ORDER BY month) AS prev FROM membership)
 WHERE prev IS NOT NULL AND ABS(1.0 * members / prev - 1) > 0.15;
