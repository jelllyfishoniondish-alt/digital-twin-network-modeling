#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
source "$script_dir/global_config.sh"

scenario_name="${SCENARIO_NAME:-recovery_scenario}"
topology_file="${TOPOLOGY_FILE:-data/topologies/geant_backbone_8cities_stage3.json}"
repeat_count="${REPEAT:-10}"
output_prefix="${OUTPUT_PREFIX:-data/exports/load_linearity_${scenario_name}}"
background_ping_interval="${BACKGROUND_PING_INTERVAL}"
load_levels="${LOAD_LEVELS:-10 30 50 80}"

cmd=(
  python3 -m src.twin.load_linearity_experiment
  --topology-file "${topology_file}"
  --scenario "${scenario_name}"
  --repeat "${repeat_count}"
  --background-ping-interval "${background_ping_interval}"
  --output-prefix "${output_prefix}"
)

# shellcheck disable=SC2206
levels=( ${load_levels} )
cmd+=(--load-levels "${levels[@]}")

"${cmd[@]}"

combined_csv="${output_prefix}.csv"

python3 -m src.twin.plotting \
  --input-csv "${combined_csv}" \
  --output "${output_prefix}_recovery_scatter.png" \
  --plot-type load-scatter \
  --metric recovery

python3 -m src.twin.plotting \
  --input-csv "${combined_csv}" \
  --output "${output_prefix}_recovery_boxplot.png" \
  --plot-type boxplot \
  --metric recovery
