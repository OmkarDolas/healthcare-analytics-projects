#!/usr/bin/env bash
# Generate the three synthetic EHR populations used by this project with Synthea (requires Java 17+).
#   dev_ma : development site, Massachusetts, 2,000 living adults aged 40-85 (+ simulated deaths)
#   ext_il : external site, Chicago IL, 1,000 living adults (dataset shift)
#   notes  : Chicago IL, 120 adults with clinical notes for the extraction harness
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=data/synthea
JAR=data/synthea-with-dependencies.jar
mkdir -p "$OUT"
if [ ! -f "$JAR" ]; then
  curl -sSL -o "$JAR" \
    https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar
fi

COMMON="--exporter.years_of_history=0 --exporter.csv.export=true --exporter.fhir.export=false \
  --exporter.hospital.fhir.export=false --exporter.practitioner.fhir.export=false \
  --exporter.csv.included_files=patients.csv,conditions.csv,observations.csv,medications.csv,encounters.csv,procedures.csv"

java -jar "$JAR" -s 2024 -p 2000 -a 40-85 --exporter.baseDirectory=$OUT/dev_ma/ $COMMON Massachusetts
java -jar "$JAR" -s 7    -p 1000 -a 40-85 --exporter.baseDirectory=$OUT/ext_il/ $COMMON Illinois Chicago
java -jar "$JAR" -s 99   -p 120  -a 40-85 --exporter.baseDirectory=$OUT/notes/  $COMMON \
  --exporter.clinical_note.export=true Illinois Chicago
