-- 2026 actual membership vs budget by product and month.
SELECT b.month, b.product,
       a.members                              AS actual_members,
       b.budget_members,
       a.members - b.budget_members           AS variance,
       ROUND(100.0 * (a.members - b.budget_members) / b.budget_members, 2) AS variance_pct
  FROM budget b
  JOIN (SELECT month, product, SUM(members) AS members FROM membership GROUP BY month, product) a
    ON a.month = b.month AND a.product = b.product
 ORDER BY b.product, b.month;
