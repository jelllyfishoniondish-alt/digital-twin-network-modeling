#!/usr/bin/env bash
set -euo pipefail

python3 -m src.twin.scalability_experiment \
  --output-csv "${OUTPUT_CSV:-data/exports/scalability.csv}" \
  --output-plot "${OUTPUT_PLOT:-data/plots/scalability.png}" \
  --repeat "${REPEAT:-3}"
