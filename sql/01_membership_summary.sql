-- Monthly membership by product: members, gross adds, terminations, net change, MoM and YoY growth.
WITH m AS (
    SELECT month, product, line_of_business,
           SUM(members) AS members, SUM(gross_adds) AS gross_adds, SUM(terminations) AS terminations
      FROM membership
     GROUP BY month, product, line_of_business
)
SELECT month, product, line_of_business, members, gross_adds, terminations,
       members - LAG(members) OVER w AS net_change,
       ROUND(100.0 * (1.0 * members / LAG(members) OVER w - 1), 2)      AS mom_pct,
       ROUND(100.0 * (1.0 * members / LAG(members, 12) OVER w - 1), 2)  AS yoy_pct
  FROM m
WINDOW w AS (PARTITION BY product ORDER BY month)
 ORDER BY product, month;
