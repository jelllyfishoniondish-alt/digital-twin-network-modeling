#!/usr/bin/env bash
set -euo pipefail

cmd=(
  python3 -m src.twin.polling_comparison
  --output-prefix "${OUTPUT_PREFIX:-data/exports/polling_comparison}"
  --repeat "${REPEAT:-1}"
)

if [[ -n "${TOPOLOGY_FILE:-}" ]]; then
  cmd+=(--topology-file "${TOPOLOGY_FILE}")
fi

if [[ -n "${TOPOLOGY_FILES:-}" ]]; then
  # shellcheck disable=SC2206
  topology_files=( ${TOPOLOGY_FILES} )
  cmd+=(--topology-files "${topology_files[@]}")
fi

if [[ -n "${BACKGROUND_PING_INTERVAL:-}" ]]; then
  cmd+=(--background-ping-interval "${BACKGROUND_PING_INTERVAL}")
fi

if [[ -n "${POLLING_INTERVALS:-}" ]]; then
  # shellcheck disable=SC2206
  polling_intervals=( ${POLLING_INTERVALS} )
  cmd+=(--polling-intervals "${polling_intervals[@]}")
fi

if [[ -n "${SCENARIOS:-}" ]]; then
  # shellcheck disable=SC2206
  scenarios=( ${SCENARIOS} )
  cmd+=(--scenarios "${scenarios[@]}")
fi

if [[ -n "${TRAFFIC_PROFILES:-}" ]]; then
  # shellcheck disable=SC2206
  traffic_profiles=( ${TRAFFIC_PROFILES} )
  cmd+=(--traffic-profiles "${traffic_profiles[@]}")
fi

"${cmd[@]}"
