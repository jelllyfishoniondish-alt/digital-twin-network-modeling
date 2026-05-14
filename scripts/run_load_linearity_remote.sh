#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source "$PWD/scripts/global_config.sh"

venv_bin="${VENV_BIN:-$PWD/.venv/bin}"
export PATH="$venv_bin:$PATH"
export PYTHONPATH="$PWD"

controller_app="${CONTROLLER_APP:-src.controller.topology_aware_switch}"
ryu_manager_bin="${RYU_MANAGER_BIN:-$venv_bin/ryu-manager}"
controller_log_base="${CONTROLLER_LOG_BASE:-/tmp/load_linearity_ryu}"
controller_boot_seconds="${CONTROLLER_BOOT_SECONDS:-15}"
scenario_name="${SCENARIO_NAME:-recovery_scenario}"
topology_file="${TOPOLOGY_FILE:-data/topologies/geant_backbone_8cities_stage3.json}"
output_prefix="${OUTPUT_PREFIX:-data/exports/load_linearity_recovery}"
execution_schedule_file="${output_prefix}_execution_schedule.json"

# shellcheck disable=SC2206
levels=( ${LOAD_LEVELS} )
generated_csvs=()

run_sudo() {
  if [[ -n "${SUDO_PASSWORD:-}" ]]; then
    printf '%s\n' "$SUDO_PASSWORD" | sudo -S "$@"
  else
    sudo "$@"
  fi
}

stop_controller() {
  if [[ -n "${ryu_pid:-}" ]]; then
    kill "$ryu_pid" 2>/dev/null || true
    wait "$ryu_pid" 2>/dev/null || true
    unset ryu_pid
  fi
  pkill -f ryu-manager >/dev/null 2>&1 || true
}

cleanup() {
  stop_controller
  run_sudo mn -c >/dev/null 2>&1 || true
}
trap cleanup EXIT

start_controller() {
  local run_order="$1"
  local controller_log="${controller_log_base}_run${run_order}.log"

  stop_controller
  run_sudo mn -c >/dev/null 2>&1 || true

  "$ryu_manager_bin" --observe-links "$controller_app" ryu.app.ofctl_rest ryu.app.rest_topology >"$controller_log" 2>&1 &
  ryu_pid=$!

  local controller_ready=0
  local attempt
  for attempt in $(seq 1 "$controller_boot_seconds"); do
    if curl -fsS http://127.0.0.1:8080/v1.0/topology/switches >/dev/null 2>&1; then
      controller_ready=1
      break
    fi
    sleep 1
  done

  if [[ "$controller_ready" -ne 1 ]]; then
    echo "Controller did not become ready for run ${run_order}: $controller_app" >&2
    exit 1
  fi
}

printf '[\n' >"$execution_schedule_file"
schedule_first=1
run_order=1

for repeat_index in $(seq 1 "$REPEAT"); do
  if [[ "${RANDOMIZE_LOAD_ORDER}" == "true" ]]; then
    read -r -a ordered_levels <<<"$(python3 - "$RANDOM_SEED" "$repeat_index" "${levels[@]}" <<'PY'
import random
import sys

seed = sys.argv[1]
repeat_index = int(sys.argv[2])
levels = [int(value) for value in sys.argv[3:]]
randomizer = random.Random(f"{seed}:{repeat_index}")
randomizer.shuffle(levels)
print(" ".join(str(level) for level in levels))
PY
)"
  else
    ordered_levels=("${levels[@]}")
  fi

  for load_percent in "${ordered_levels[@]}"; do
    run_output_prefix="${output_prefix}_rep$(printf '%02d' "$repeat_index")"
    output_csv="${run_output_prefix}_${load_percent}pct.csv"

    start_controller "$run_order"
    run_sudo env \
      PATH="$PATH" \
      PYTHONPATH="$PWD" \
      CONTROLLER_APP="$controller_app" \
      INITIALIZATION_TIMEOUT_SECONDS="${INITIALIZATION_TIMEOUT_SECONDS}" \
      SCENARIO_TIMEOUT_SECONDS="${SCENARIO_TIMEOUT_SECONDS}" \
      python3 -m src.twin.load_linearity_experiment \
        --topology-file "${topology_file}" \
        --scenario "${scenario_name}" \
        --repeat 1 \
        --background-ping-interval "${BACKGROUND_PING_INTERVAL}" \
        --output-prefix "${run_output_prefix}" \
        --single-load-level "${load_percent}"
    generated_csvs+=("${output_csv}")

    if [[ "$schedule_first" -eq 0 ]]; then
      printf ',\n' >>"$execution_schedule_file"
    fi
    schedule_first=0
    printf '  {"repeat_index": %s, "run_order": %s, "load_percent": %s, "output_csv": "%s", "configured_repeat_count": %s}' \
      "$repeat_index" "$run_order" "$load_percent" "$output_csv" "$REPEAT" >>"$execution_schedule_file"
    run_order=$((run_order + 1))
  done
done
printf '\n]\n' >>"$execution_schedule_file"

stop_controller
run_sudo mn -c >/dev/null 2>&1 || true

aggregate_cmd=(
  env
  PATH="$PATH"
  PYTHONPATH="$PWD"
  CONTROLLER_APP="$controller_app"
  INITIALIZATION_TIMEOUT_SECONDS="${INITIALIZATION_TIMEOUT_SECONDS}"
  SCENARIO_TIMEOUT_SECONDS="${SCENARIO_TIMEOUT_SECONDS}"
  python3 -m src.twin.load_linearity_experiment
  --topology-file "${topology_file}"
  --scenario "${scenario_name}"
  --repeat "${REPEAT}"
  --background-ping-interval "${BACKGROUND_PING_INTERVAL}"
  --output-prefix "${output_prefix}"
  --load-levels "${levels[@]}"
  --execution-schedule-file "${execution_schedule_file}"
  --aggregate-input-csvs "${generated_csvs[@]}"
)
run_sudo "${aggregate_cmd[@]}"

combined_csv="${output_prefix}.csv"

run_sudo env \
  PATH="$PATH" \
  PYTHONPATH="$PWD" \
  python3 -m src.twin.plotting \
    --input-csv "${combined_csv}" \
    --output "${output_prefix}_recovery_scatter.png" \
    --plot-type load-scatter \
    --metric recovery

run_sudo env \
  PATH="$PATH" \
  PYTHONPATH="$PWD" \
  python3 -m src.twin.plotting \
    --input-csv "${combined_csv}" \
    --output "${output_prefix}_recovery_boxplot.png" \
    --plot-type boxplot \
    --metric recovery
