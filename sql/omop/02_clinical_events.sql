-- OMOP CDM v5.4-shaped clinical event tables. Source vocabularies:
--   conditions / procedures: SNOMED CT    measurements / observations: LOINC    drugs: RxNorm

CREATE OR REPLACE TABLE condition_occurrence AS
SELECT
    row_number() OVER (ORDER BY c.START)                       AS condition_occurrence_id,
    pe.person_id,
    0                                                          AS condition_concept_id,
    CAST(c.START AS DATE)                                      AS condition_start_date,
    CAST(c.STOP AS DATE)                                       AS condition_end_date,
    v.visit_occurrence_id,
    CAST(c.CODE AS VARCHAR)                                    AS condition_source_value,
    c.DESCRIPTION                                              AS condition_source_description
FROM stg_conditions c
JOIN person pe ON pe.person_source_value = c.PATIENT
LEFT JOIN visit_occurrence v ON v.visit_source_id = c.ENCOUNTER;

CREATE OR REPLACE TABLE measurement AS
SELECT
    row_number() OVER (ORDER BY o.DATE)                        AS measurement_id,
    pe.person_id,
    0                                                          AS measurement_concept_id,
    CAST(o.DATE AS DATE)                                       AS measurement_date,
    TRY_CAST(o.VALUE AS DOUBLE)                                AS value_as_number,
    o.UNITS                                                    AS unit_source_value,
    v.visit_occurrence_id,
    CAST(o.CODE AS VARCHAR)                                    AS measurement_source_value,
    o.DESCRIPTION                                              AS measurement_source_description
FROM stg_observations o
JOIN person pe ON pe.person_source_value = o.PATIENT
LEFT JOIN visit_occurrence v ON v.visit_source_id = o.ENCOUNTER
WHERE o.TYPE = 'numeric';

CREATE OR REPLACE TABLE observation AS
SELECT
    row_number() OVER (ORDER BY o.DATE)                        AS observation_id,
    pe.person_id,
    0                                                          AS observation_concept_id,
    CAST(o.DATE AS DATE)                                       AS observation_date,
    CAST(o.VALUE AS VARCHAR)                                   AS value_as_string,
    v.visit_occurrence_id,
    CAST(o.CODE AS VARCHAR)                                    AS observation_source_value,
    o.DESCRIPTION                                              AS observation_source_description
FROM stg_observations o
JOIN person pe ON pe.person_source_value = o.PATIENT
LEFT JOIN visit_occurrence v ON v.visit_source_id = o.ENCOUNTER
WHERE o.TYPE <> 'numeric';

CREATE OR REPLACE TABLE drug_exposure AS
SELECT
    row_number() OVER (ORDER BY m.START)                       AS drug_exposure_id,
    pe.person_id,
    0                                                          AS drug_concept_id,
    CAST(m.START AS DATE)                                      AS drug_exposure_start_date,
    CAST(m.STOP AS DATE)                                       AS drug_exposure_end_date,
    v.visit_occurrence_id,
    CAST(m.CODE AS VARCHAR)                                    AS drug_source_value,
    m.DESCRIPTION                                              AS drug_source_description
FROM stg_medications m
JOIN person pe ON pe.person_source_value = m.PATIENT
LEFT JOIN visit_occurrence v ON v.visit_source_id = m.ENCOUNTER;

CREATE OR REPLACE TABLE procedure_occurrence AS
SELECT
    row_number() OVER (ORDER BY pr.START)                      AS procedure_occurrence_id,
    pe.person_id,
    0                                                          AS procedure_concept_id,
    CAST(pr.START AS DATE)                                     AS procedure_date,
    v.visit_occurrence_id,
    CAST(pr.CODE AS VARCHAR)                                   AS procedure_source_value,
    pr.DESCRIPTION                                             AS procedure_source_description
FROM stg_procedures pr
JOIN person pe ON pe.person_source_value = pr.PATIENT
LEFT JOIN visit_occurrence v ON v.visit_source_id = pr.ENCOUNTER;
