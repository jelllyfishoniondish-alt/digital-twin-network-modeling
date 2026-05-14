#!/usr/bin/env bash
set -euo pipefail

python3 -m src.twin.plotting \
  --input-csv "${INPUT_CSV:-data/exports/recovery_scenario_summary.csv}" \
  --output "${OUTPUT_PLOT:-data/plots/detection_delay.png}"
