-- Baseline features from a 3-year lookback window before each index date.
-- Static: demographics. Latest values: vitals and labs. Longitudinal: slopes and visit counts.
-- History flags: comorbidities recorded on or before the index date. Medications active at index.

CREATE OR REPLACE TABLE lookback_measurement AS
SELECT
    c.person_id, c.landmark_year, ms.feature,
    m.measurement_date, m.value_as_number,
    row_number() OVER (PARTITION BY c.person_id, c.landmark_year, ms.feature
                       ORDER BY m.measurement_date DESC, m.value_as_number DESC) AS recency_rank
FROM cohort c
JOIN measurement m ON m.person_id = c.person_id
JOIN measurement_set ms ON ms.loinc = m.measurement_source_value
WHERE m.measurement_date <  c.index_date
  AND m.measurement_date >= c.index_date - INTERVAL 3 YEAR
  AND m.value_as_number IS NOT NULL;

CREATE OR REPLACE TABLE feat_latest AS
PIVOT (SELECT person_id, landmark_year, feature, value_as_number
       FROM lookback_measurement WHERE recency_rank = 1)
ON feature IN ('sbp', 'dbp', 'bmi', 'total_chol', 'hdl', 'ldl', 'triglycerides',
               'hba1c', 'glucose', 'egfr', 'creatinine', 'heart_rate')
USING first(value_as_number)
GROUP BY person_id, landmark_year;

-- Longitudinal trajectory features: per-year slope of SBP, BMI and HbA1c over the lookback window
CREATE OR REPLACE TABLE feat_slope AS
SELECT
    person_id, landmark_year,
    round(regr_slope(value_as_number, epoch(measurement_date) / 31557600.0)
        FILTER (WHERE feature = 'sbp'), 6)   AS sbp_slope_per_year,
    round(regr_slope(value_as_number, epoch(measurement_date) / 31557600.0)
        FILTER (WHERE feature = 'bmi'), 6)   AS bmi_slope_per_year,
    round(regr_slope(value_as_number, epoch(measurement_date) / 31557600.0)
        FILTER (WHERE feature = 'hba1c'), 6) AS hba1c_slope_per_year,
    count(*) FILTER (WHERE feature = 'sbp') AS n_bp_readings
FROM lookback_measurement
GROUP BY person_id, landmark_year;

CREATE OR REPLACE TABLE feat_utilization AS
SELECT
    c.person_id, c.landmark_year,
    count(*) FILTER (WHERE v.visit_start_date >= c.index_date - INTERVAL 1 YEAR) AS visits_prior_year,
    count(*) FILTER (WHERE v.visit_concept_id IN (9201, 9203))                   AS acute_visits_3y
FROM cohort c
JOIN visit_occurrence v ON v.person_id = c.person_id
WHERE v.visit_start_date < c.index_date
  AND v.visit_start_date >= c.index_date - INTERVAL 3 YEAR
GROUP BY c.person_id, c.landmark_year;

CREATE OR REPLACE TABLE feat_history AS
SELECT
    c.person_id, c.landmark_year,
    max(CASE WHEN cs.concept_set = 'hypertension'   THEN 1 ELSE 0 END) AS hx_hypertension,
    max(CASE WHEN cs.concept_set = 'diabetes_t2'    THEN 1 ELSE 0 END) AS hx_diabetes_t2,
    max(CASE WHEN cs.concept_set = 'prediabetes'    THEN 1 ELSE 0 END) AS hx_prediabetes,
    max(CASE WHEN cs.concept_set = 'hyperlipidemia' THEN 1 ELSE 0 END) AS hx_hyperlipidemia,
    max(CASE WHEN cs.concept_set = 'ckd'            THEN 1 ELSE 0 END) AS hx_ckd,
    max(CASE WHEN cs.concept_set = 'obesity'        THEN 1 ELSE 0 END) AS hx_obesity,
    max(CASE WHEN cs.concept_set = 'afib'           THEN 1 ELSE 0 END) AS hx_afib
FROM cohort c
JOIN condition_occurrence co ON co.person_id = c.person_id AND co.condition_start_date <= c.index_date
JOIN concept_set cs ON cs.source_code = co.condition_source_value
GROUP BY c.person_id, c.landmark_year;

CREATE OR REPLACE TABLE feat_drugs AS
SELECT
    c.person_id, c.landmark_year,
    max(CASE WHEN regexp_matches(lower(de.drug_source_description),
        'simvastatin|atorvastatin|rosuvastatin|pravastatin|lovastatin') THEN 1 ELSE 0 END) AS rx_statin,
    max(CASE WHEN regexp_matches(lower(de.drug_source_description),
        'lisinopril|losartan|amlodipine|hydrochlorothiazide|metoprolol|atenolol|valsartan|chlorthalidone')
        THEN 1 ELSE 0 END)                                                                AS rx_antihypertensive,
    max(CASE WHEN regexp_matches(lower(de.drug_source_description),
        'metformin|insulin|glipizide|liraglutide|semaglutide|empagliflozin') THEN 1 ELSE 0 END) AS rx_glucose_lowering
FROM cohort c
JOIN drug_exposure de ON de.person_id = c.person_id
WHERE de.drug_exposure_start_date <= c.index_date
  AND (de.drug_exposure_end_date IS NULL OR de.drug_exposure_end_date >= c.index_date)
GROUP BY c.person_id, c.landmark_year;

CREATE OR REPLACE TABLE smoking AS
SELECT person_id, landmark_year, value_as_string AS smoking_status FROM (
    SELECT c.person_id, c.landmark_year, o.value_as_string,
           row_number() OVER (PARTITION BY c.person_id, c.landmark_year ORDER BY o.observation_date DESC, o.value_as_string) AS rk
    FROM cohort c
    JOIN observation o ON o.person_id = c.person_id
    WHERE o.observation_source_value = '72166-2' AND o.observation_date < c.index_date
) WHERE rk = 1;

CREATE OR REPLACE TABLE analytic_dataset AS
SELECT
    c.person_id, c.landmark_year, c.index_date, c.state,
    c.age, c.sex, c.race, c.ethnicity,
    fl.* EXCLUDE (person_id, landmark_year),
    fs.* EXCLUDE (person_id, landmark_year),
    coalesce(fu.visits_prior_year, 0) AS visits_prior_year,
    coalesce(fu.acute_visits_3y, 0)   AS acute_visits_3y,
    coalesce(fh.hx_hypertension, 0)   AS hx_hypertension,
    coalesce(fh.hx_diabetes_t2, 0)    AS hx_diabetes_t2,
    coalesce(fh.hx_prediabetes, 0)    AS hx_prediabetes,
    coalesce(fh.hx_hyperlipidemia, 0) AS hx_hyperlipidemia,
    coalesce(fh.hx_ckd, 0)            AS hx_ckd,
    coalesce(fh.hx_obesity, 0)        AS hx_obesity,
    coalesce(fh.hx_afib, 0)           AS hx_afib,
    coalesce(fd.rx_statin, 0)            AS rx_statin,
    coalesce(fd.rx_antihypertensive, 0)  AS rx_antihypertensive,
    coalesce(fd.rx_glucose_lowering, 0)  AS rx_glucose_lowering,
    CASE
        WHEN sm.smoking_status ILIKE '%every day%' OR sm.smoking_status ILIKE '%current%' THEN 'current'
        WHEN sm.smoking_status ILIKE '%ex-smoker%' OR sm.smoking_status ILIKE '%former%' THEN 'former'
        WHEN sm.smoking_status ILIKE '%never%' THEN 'never'
        ELSE 'unknown' END              AS smoking,
    c.cvd_5y, c.days_to_event
FROM cohort c
LEFT JOIN feat_latest fl      USING (person_id, landmark_year)
LEFT JOIN feat_slope fs       USING (person_id, landmark_year)
LEFT JOIN feat_utilization fu USING (person_id, landmark_year)
LEFT JOIN feat_history fh     USING (person_id, landmark_year)
LEFT JOIN feat_drugs fd       USING (person_id, landmark_year)
LEFT JOIN smoking sm          USING (person_id, landmark_year)
ORDER BY c.person_id, c.landmark_year;
