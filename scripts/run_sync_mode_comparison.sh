#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_prefix="${OUTPUT_PREFIX:-$root_dir/data/exports/sync_mode_comparison}"
topology_file="${TOPOLOGY_FILE:-$root_dir/data/topologies/geant_backbone_8cities_stage3.json}"
repeat="${REPEAT:-1}"
poll_interval="${POLL_INTERVAL_SECONDS:-2}"
hybrid_poll_interval="${HYBRID_POLL_INTERVAL_SECONDS:-10}"

(
  cd "$root_dir"
  POLL_INTERVAL_SECONDS="$poll_interval" \
  HYBRID_POLL_INTERVAL_SECONDS="$hybrid_poll_interval" \
  python3 -m src.twin.sync_mode_comparison \
    --topology-file "$topology_file" \
    --repeat "$repeat" \
    --output-prefix "$output_prefix"
)
