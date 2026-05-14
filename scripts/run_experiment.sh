#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
source "$script_dir/global_config.sh"

cmd=(
  python3 -m src.twin.experiment_runner
  --scenario "${SCENARIO_NAME:-recovery_scenario}"
  --output-csv "${OUTPUT_CSV:-data/exports/${SCENARIO_NAME:-recovery_scenario}.csv}"
)

if [[ -n "${TOPOLOGY_FILE:-}" ]]; then
  cmd+=(--topology-file "${TOPOLOGY_FILE}")
fi

if [[ -n "${BACKGROUND_TRAFFIC:-}" ]]; then
  cmd+=(--background-traffic "${BACKGROUND_TRAFFIC}")
fi

if [[ -n "${BACKGROUND_PING_INTERVAL:-}" ]]; then
  cmd+=(--background-ping-interval "${BACKGROUND_PING_INTERVAL}")
fi

if [[ -n "${REPEAT:-}" ]]; then
  cmd+=(--repeat "${REPEAT}")
fi

"${cmd[@]}"
