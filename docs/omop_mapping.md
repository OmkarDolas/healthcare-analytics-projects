# Synthea to OMOP CDM mapping

`src/omop_etl.py` stages the Synthea CSV export in DuckDB and runs `sql/omop/*.sql` to build these
OMOP CDM v5.4-shaped tables:

| OMOP table | Synthea source | Notes |
|---|---|---|
| `person` | patients.csv | gender 8507/8532, race 8527/8516/8515, ethnicity 38003563/38003564 |
| `death` | patients.csv (`DEATHDATE`) | |
| `visit_occurrence` | encounters.csv | inpatient 9201, emergency 9203, all other classes 9202 (outpatient) |
| `observation_period` | encounters + death | first visit to last visit or death |
| `condition_occurrence` | conditions.csv | SNOMED CT code in `condition_source_value` |
| `measurement` | observations.csv (numeric) | LOINC code in `measurement_source_value` |
| `observation` | observations.csv (text) | e.g. smoking status 72166-2 |
| `drug_exposure` | medications.csv | RxNorm code in `drug_source_value` |
| `procedure_occurrence` | procedures.csv | SNOMED CT code in `procedure_source_value` |

## What is simplified

* **Standard concept IDs for clinical codes are left as 0.** Mapping SNOMED, LOINC and RxNorm source codes
  to OMOP standard concepts needs the OHDSI vocabulary tables from [Athena](https://athena.ohdsi.org),
  which require a free account and are not redistributed here. Cohort definitions therefore use source
  codes. With the vocabulary loaded, the same SQL would join through `concept_relationship` ("Maps to")
  and use descendant concepts from `concept_ancestor` instead of hand-listed codes.
* Only the tables and columns this project needs are populated.
* The production-grade route is [OHDSI ETL-Synthea](https://github.com/OHDSI/ETL-Synthea). This ETL is a
  small, readable version of the same idea.
