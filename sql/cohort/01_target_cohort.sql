-- Landmark cohort for 5-year incident CVD risk.
-- Index dates: January 1 of each landmark year. A person enters at a landmark when they are
-- aged 40-79, alive, active in care (a visit in the prior 3 years), and free of prior CVD.
-- Outcome: first CVD event in (index, index + 5 years].
-- Persons who die without a CVD event, or whose records end, before 5 years are excluded
-- (complete-case 5-year label; competing risk of non-CVD death is a stated limitation).

CREATE OR REPLACE TABLE landmark AS
SELECT unnest([2006, 2010, 2014, 2018]) AS landmark_year;

CREATE OR REPLACE TABLE first_cvd AS
SELECT co.person_id, min(co.condition_start_date) AS first_cvd_date
FROM condition_occurrence co
JOIN concept_set cs ON cs.source_code = co.condition_source_value
WHERE cs.concept_set = 'cvd_event'
GROUP BY co.person_id;

CREATE OR REPLACE TABLE first_cvd_history AS
SELECT co.person_id, min(co.condition_start_date) AS first_history_date
FROM condition_occurrence co
JOIN concept_set cs ON cs.source_code = co.condition_source_value
WHERE cs.concept_set = 'cvd_history'
GROUP BY co.person_id;

CREATE OR REPLACE TABLE cohort AS
WITH candidates AS (
    SELECT
        p.person_id,
        l.landmark_year,
        make_date(l.landmark_year, 1, 1)                       AS index_date,
        make_date(l.landmark_year + 5, 1, 1)                   AS horizon_date,
        date_diff('day', p.birth_date, make_date(l.landmark_year, 1, 1)) / 365.25 AS age,
        p.gender_source_value                                  AS sex,
        p.race_source_value                                    AS race,
        p.ethnicity_source_value                               AS ethnicity,
        p.location_source_value                                AS state
    FROM person p
    CROSS JOIN landmark l
),
eligible AS (
    SELECT c.*
    FROM candidates c
    JOIN observation_period op USING (person_id)
    LEFT JOIN death d USING (person_id)
    LEFT JOIN first_cvd fc USING (person_id)
    LEFT JOIN first_cvd_history fh USING (person_id)
    WHERE c.age >= 40 AND c.age < 80
      AND (d.death_date IS NULL OR d.death_date > c.index_date)
      AND (fc.first_cvd_date IS NULL OR fc.first_cvd_date > c.index_date)
      AND (fh.first_history_date IS NULL OR fh.first_history_date > c.index_date)
      AND EXISTS (
          SELECT 1 FROM visit_occurrence v
          WHERE v.person_id = c.person_id
            AND v.visit_start_date >= c.index_date - INTERVAL 3 YEAR
            AND v.visit_start_date <  c.index_date)
)
SELECT
    e.*,
    CASE WHEN fc.first_cvd_date <= e.horizon_date THEN 1 ELSE 0 END AS cvd_5y,
    CASE WHEN fc.first_cvd_date <= e.horizon_date
         THEN date_diff('day', e.index_date, fc.first_cvd_date) END AS days_to_event
FROM eligible e
JOIN observation_period op USING (person_id)
LEFT JOIN death d USING (person_id)
LEFT JOIN first_cvd fc USING (person_id)
-- keep: event within horizon, or event-free and followed through the full horizon
WHERE fc.first_cvd_date <= e.horizon_date
   OR (op.observation_period_end_date >= e.horizon_date
       AND (d.death_date IS NULL OR d.death_date > e.horizon_date));
