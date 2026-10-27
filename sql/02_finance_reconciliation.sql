-- Reconcile enrollment-system membership to Finance billed membership.
-- Business rule: variance above 1.0% at product x region x month must be researched and explained.
SELECT m.month, m.product, m.region,
       m.members                         AS enrollment_members,
       f.billed_members                  AS finance_members,
       m.members - f.billed_members      AS variance,
       ROUND(100.0 * (m.members - f.billed_members) / m.members, 2) AS variance_pct,
       CASE WHEN f.billed_members IS NULL THEN 'MISSING IN FINANCE'
            WHEN ABS(1.0 * (m.members - f.billed_members) / m.members) > 0.01 THEN 'RESEARCH'
            ELSE 'OK' END                AS status
  FROM membership m
  LEFT JOIN finance f
    ON f.month = m.month AND f.product = m.product AND f.region = m.region
 ORDER BY status DESC, ABS(variance_pct) DESC;
