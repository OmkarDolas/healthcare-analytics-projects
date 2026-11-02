-- Concept sets (source codes) used by the cohort and feature definitions.
-- SNOMED CT for conditions, LOINC for measurements/observations. See docs/cohort_definition.md.

CREATE OR REPLACE TABLE concept_set AS
SELECT * FROM (VALUES
    -- Outcome: incident cardiovascular disease (CVD) event
    ('cvd_event', '22298006',   'Myocardial infarction'),
    ('cvd_event', '401303003',  'Acute ST segment elevation myocardial infarction'),
    ('cvd_event', '401314000',  'Acute non-ST segment elevation myocardial infarction'),
    ('cvd_event', '230690007',  'Cerebrovascular accident'),
    ('cvd_event', '88805009',   'Chronic congestive heart failure'),
    ('cvd_event', '84114007',   'Heart failure'),
    ('cvd_event', '414545008',  'Ischemic heart disease'),
    ('cvd_event', '410429000',  'Cardiac arrest'),
    -- Prior CVD history (exclusion only)
    ('cvd_history', '399211009', 'History of myocardial infarction'),
    ('cvd_history', '399261000', 'History of coronary artery bypass grafting'),
    ('cvd_history', '429007001', 'History of cardiac arrest'),
    -- Comorbidity predictors
    ('hypertension', '59621000',  'Essential hypertension'),
    ('diabetes_t2',  '44054006',  'Diabetes mellitus type 2'),
    ('prediabetes',  '714628002', 'Prediabetes'),
    ('prediabetes',  '15777000',  'Prediabetes'),
    ('hyperlipidemia','55822004', 'Hyperlipidemia'),
    ('ckd',          '431855005', 'Chronic kidney disease stage 1'),
    ('ckd',          '431856006', 'Chronic kidney disease stage 2'),
    ('ckd',          '433144002', 'Chronic kidney disease stage 3'),
    ('ckd',          '431857002', 'Chronic kidney disease stage 4'),
    ('ckd',          '46177005',  'End-stage renal disease'),
    ('obesity',      '162864005', 'Body mass index 30+ - obesity'),
    ('obesity',      '408512008', 'Body mass index 40+ - severely obese'),
    ('afib',         '49436004',  'Atrial fibrillation')
) AS t(concept_set, source_code, description);

CREATE OR REPLACE TABLE measurement_set AS
SELECT * FROM (VALUES
    ('sbp',          '8480-6'),
    ('dbp',          '8462-4'),
    ('bmi',          '39156-5'),
    ('total_chol',   '2093-3'),
    ('hdl',          '2085-9'),
    ('ldl',          '18262-6'),
    ('triglycerides','2571-8'),
    ('hba1c',        '4548-4'),
    ('glucose',      '2339-0'),
    ('egfr',         '33914-3'),
    ('creatinine',   '38483-4'),
    ('heart_rate',   '8867-4')
) AS t(feature, loinc);
