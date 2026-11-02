PY ?= python
SYN = data/synthea

.PHONY: all data omop cohort models extraction test clean

all: omop cohort models extraction

data:                 ## generate synthetic EHR populations with Synthea (about 30 min on 2 cores)
	bash scripts/generate_synthea.sh

omop:                 ## Synthea CSV -> OMOP CDM v5.4-shaped DuckDB databases
	$(PY) -m src.omop_etl --synthea $(SYN)/dev_ma/csv --db data/omop_dev.duckdb
	$(PY) -m src.omop_etl --synthea $(SYN)/ext_il/csv --db data/omop_ext.duckdb

cohort:               ## OMOP -> landmark cohort + baseline features
	$(PY) -m src.build_cohort --db data/omop_dev.duckdb --out data/analytic_dev.parquet
	$(PY) -m src.build_cohort --db data/omop_ext.duckdb --out data/analytic_ext.parquet

models:               ## train models, evaluate beyond AUROC, write outputs/ and figures
	$(PY) -m src.run_risk_pipeline --dev data/analytic_dev.parquet --ext data/analytic_ext.parquet

extraction:           ## clinical-note extraction harness, rule-based baseline
	$(PY) -m src.run_extraction_eval --backend rules

test:
	$(PY) -m pytest -q tests

clean:
	rm -rf data/*.duckdb data/*.parquet outputs/*
