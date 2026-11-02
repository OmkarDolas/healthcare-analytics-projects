-- OMOP CDM v5.4-shaped PERSON, DEATH and OBSERVATION_PERIOD tables built from Synthea staging tables.
-- Gender, race, ethnicity and visit concept IDs use standard OMOP concepts.
-- Clinical concept IDs are left as 0 with source codes preserved (see docs/omop_mapping.md).

CREATE OR REPLACE TABLE person AS
SELECT
    row_number() OVER (ORDER BY p.Id)                          AS person_id,
    CASE p.GENDER WHEN 'M' THEN 8507 WHEN 'F' THEN 8532 ELSE 0 END AS gender_concept_id,
    year(p.BIRTHDATE)                                          AS year_of_birth,
    month(p.BIRTHDATE)                                         AS month_of_birth,
    day(p.BIRTHDATE)                                           AS day_of_birth,
    CAST(p.BIRTHDATE AS DATE)                                  AS birth_date,
    CASE p.RACE WHEN 'white' THEN 8527 WHEN 'black' THEN 8516 WHEN 'asian' THEN 8515 ELSE 0 END
                                                               AS race_concept_id,
    CASE p.ETHNICITY WHEN 'hispanic' THEN 38003563 WHEN 'nonhispanic' THEN 38003564 ELSE 0 END
                                                               AS ethnicity_concept_id,
    p.Id                                                       AS person_source_value,
    p.GENDER                                                   AS gender_source_value,
    p.RACE                                                     AS race_source_value,
    p.ETHNICITY                                                AS ethnicity_source_value,
    p.STATE                                                    AS location_source_value
FROM stg_patients p;

CREATE OR REPLACE TABLE death AS
SELECT pe.person_id, CAST(p.DEATHDATE AS DATE) AS death_date
FROM stg_patients p
JOIN person pe ON pe.person_source_value = p.Id
WHERE p.DEATHDATE IS NOT NULL;

CREATE OR REPLACE TABLE visit_occurrence AS
SELECT
    row_number() OVER (ORDER BY e.START, e.Id)                 AS visit_occurrence_id,
    pe.person_id,
    CASE e.ENCOUNTERCLASS
        WHEN 'inpatient' THEN 9201
        WHEN 'emergency' THEN 9203
        ELSE 9202 END                                          AS visit_concept_id,
    CAST(e.START AS DATE)                                      AS visit_start_date,
    CAST(e.STOP AS DATE)                                       AS visit_end_date,
    e.ENCOUNTERCLASS                                           AS visit_source_value,
    e.Id                                                       AS visit_source_id
FROM stg_encounters e
JOIN person pe ON pe.person_source_value = e.PATIENT;

CREATE OR REPLACE TABLE observation_period AS
SELECT
    row_number() OVER (ORDER BY v.person_id)                   AS observation_period_id,
    v.person_id,
    min(v.visit_start_date)                                    AS observation_period_start_date,
    coalesce(max(d.death_date), max(v.visit_end_date))         AS observation_period_end_date
FROM visit_occurrence v
LEFT JOIN death d USING (person_id)
GROUP BY v.person_id;
