# Power BI build

1. **Get data > Text/CSV**: load every file in `outputs/powerbi/`.
2. **Model view** relationships (single direction, many-to-one):
   - `fact_membership[product]`, `fact_budget[product]`, `fact_forecast[product]` -> `dim_product[product]`
   - `fact_membership[region]` -> `dim_region[region]`
   - `fact_membership[month]`, `fact_budget[month]`, `fact_forecast[month]` -> `dim_date[month]`
   - Mark `dim_date` as the date table.
3. **Measures**: paste each measure from `measures.dax` (New measure).
4. **Report pages**
   - *Membership overview*: cards (Members Latest Month, YoY %), line chart Members by month and line of business,
     slicers for product, region, line of business.
   - *Budget & forecast*: clustered column Members vs Budget Members by month, table with Variance to Budget %
     and Variance Flag (conditional formatting red above 2%), line chart actual vs Forecast Members.
   - *Reconciliation*: table from `outputs/reconciliation_exceptions.csv`.
