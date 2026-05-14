#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${TOPOLOGY_FILE:-}" ]]; then
  echo "TOPOLOGY_FILE is required" >&2
  exit 1
fi

venv_bin="${VENV_BIN:-$PWD/.venv/bin}"
export PATH="$venv_bin:$PATH"
python_bin="${PYTHON_BIN:-$venv_bin/python3}"
ryu_manager_bin="${RYU_MANAGER_BIN:-$venv_bin/ryu-manager}"

sudo -v

# shellcheck disable=SC2206
controller_apps=( ${CONTROLLER_APPS:-src.controller.topology_aware_switch src.controller.tree_routing_switch} )
summary_inputs=()

for controller_app in "${controller_apps[@]}"; do
  controller_slug="${controller_app##*.}"
  output_prefix="${OUTPUT_PREFIX:-data/exports/controller_compare}_${controller_slug}"
  log_path="${LOG_DIR:-/tmp}/${controller_slug}.log"

  PYTHONPATH="$PWD" "$ryu_manager_bin" --observe-links "$controller_app" ryu.app.ofctl_rest ryu.app.rest_topology > "$log_path" 2>&1 &
  ryu_pid=$!
  controller_ready=0
  for _ in $(seq 1 "${CONTROLLER_BOOT_SECONDS:-10}"); do
    if curl -fsS http://127.0.0.1:8080/v1.0/topology/switches >/dev/null 2>&1; then
      controller_ready=1
      break
    fi
    sleep 1
  done
  if [[ "$controller_ready" -ne 1 ]]; then
    echo "Controller did not become ready: $controller_app" >&2
    kill "$ryu_pid"
    wait "$ryu_pid" 2>/dev/null || true
    exit 1
  fi

  sudo env \
    PATH="$PATH" \
    PYTHONPATH="$PWD" \
    CONTROLLER_APP="$controller_app" \
    TOPOLOGY_FILE="$TOPOLOGY_FILE" \
    OUTPUT_PREFIX="$output_prefix" \
    REPEAT="${REPEAT:-1}" \
    SCENARIOS="${SCENARIOS:-recovery_scenario}" \
    TRAFFIC_PROFILES="${TRAFFIC_PROFILES:-none icmp}" \
    bash scripts/run_experiment_matrix.sh

  summary_inputs+=("${output_prefix}_summary.csv")
  kill "$ryu_pid"
  wait "$ryu_pid" 2>/dev/null || true
done

PYTHONPATH="$PWD" "$python_bin" -m src.twin.controller_comparison \
  --inputs "${summary_inputs[@]}" \
  --output-csv "${COMBINED_SUMMARY_CSV:-data/exports/controller_compare_summary.csv}" \
  --output-json "${COMBINED_SUMMARY_JSON:-data/exports/controller_compare_summary.json}"

PYTHONPATH="$PWD" "$python_bin" -m src.twin.plotting \
  --input-csv "${COMBINED_SUMMARY_CSV:-data/exports/controller_compare_summary.csv}" \
  --output "${COMBINED_PLOT:-data/plots/controller_compare_summary.png}"
