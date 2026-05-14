#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${TOPOLOGY_FILE:-}" ]]; then
  python3 -m src.topology.data_driven_topology \
    --topology-file "${TOPOLOGY_FILE}" \
    --controller-host "${RYU_CONTROLLER_HOST:-127.0.0.1}" \
    --controller-port "${RYU_CONTROLLER_PORT:-6633}" \
    --pingall
else
  python3 -m src.topology.minimal_topology \
    --controller-host "${RYU_CONTROLLER_HOST:-127.0.0.1}" \
    --controller-port "${RYU_CONTROLLER_PORT:-6633}" \
    --pingall
fi
