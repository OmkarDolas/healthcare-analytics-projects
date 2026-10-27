# Data dictionary and metric definitions

## `data/member_years.csv` (one row per member per payment year)

| Field | Type | Definition |
|---|---|---|
| member_id | text | Synthetic member identifier (`M` = Medicare Advantage, `A` = ACA) |
| segment | text | `MA` or `ACA` |
| age | int | Member age in the payment year |
| female | bool | Sex used in the demographic factor |
| dual_eligible | bool | Eligible for both Medicare and Medicaid (MA only) |
| plan | text | Benefit plan (MA-HMO Gold, MA-PPO Silver, MA-HMO Value, D-SNP, ACA Bronze/Silver/Gold) |
| county | text | Southeastern PA county of residence |
| payment_year | int | CMS payment year (2023-2025) |
| demographic_score | float | Demographic component of the risk score |
| disease_score | float | Sum of coefficients for documented HCCs |
| hcc_count | int | Number of HCCs documented in the year |
| raf_score | float | Risk Adjustment Factor = demographic_score + disease_score |
| HCC18 ... HCC12 | 0/1 | Flag: HCC documented for the member in that year |

## `data/hcc_reference.csv`
HCC code, description, illustrative coefficient and base prevalence. Coefficients are in the range of the
CMS-HCC model but are **not** official CMS rates.

## Metric definitions

| Metric | Definition | Business rule |
|---|---|---|
| Average RAF | Mean `raf_score` across members in the group | Excludes quarantined records |
| RAF YoY % | (avg RAF this year / avg RAF prior year) - 1 | Same plan and segment |
| HCC recapture rate | HCCs documented in prior year **and** current year / HCCs documented in prior year | Member must be present in both years; computed per member x HCC |
| HCC prevalence | Members with the HCC / total members | By segment and year |
| Dual % | Share of members who are dual eligible | Latest payment year |

## Data quality checks (`sql/01_data_quality_checks.sql`)
missing county, RAF outside 0-10, duplicate member-year, age outside segment range, and `hcc_count` not
matching the HCC flags. Failing records are quarantined and reported, not silently dropped.
