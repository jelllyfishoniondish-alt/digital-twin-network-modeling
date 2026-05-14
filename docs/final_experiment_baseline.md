# Final Experiment Baseline

## 1. Purpose

This document fixes the default experiment baseline for the current project state.

Its purpose is to avoid ambiguity in later analysis by defining:

- which topology is the primary reference topology
- which controller is the default controller
- which scenarios are the primary scenarios
- which result sets should be treated as the main artifacts
- which result sets are considered extension studies rather than the main baseline

## 2. Primary Baseline

### 2.1 Default topology

The primary baseline topology is:

- `geant_backbone_8cities_stage3`

Reason:

- it is the most mature and repeatedly validated topology in the project
- it represents a complete 8-city backbone subnetwork with 10 modeled backbone links
- it has already been used in the main traffic, polling, robustness, and controller-comparison experiments
- it is easier to interpret than the imported 12-node topology while still being significantly more realistic than the original toy topology

### 2.2 Default controller

The default controller is:

- `src.controller.topology_aware_switch`

Reason:

- it is the main control-plane implementation used across the project's core experiments
- it supports the full stage-3 backbone topology reliably
- it is the most appropriate baseline for comparing against alternative controller strategies

The following controller is treated as an extension/comparison controller, not the default baseline:

- `src.controller.tree_routing_switch`

### 2.3 Default polling interval

The default polling interval is:

- `2.0s`

Reason:

- it is the most frequently used configuration across the main experiments
- it provides a middle ground between responsiveness and experimental stability
- the `1s / 2s / 4s` comparison is retained as a dedicated sensitivity study, not as the main baseline

## 3. Primary Scenarios

The primary scenario set is:

- `recovery_scenario`
- `link_flap_scenario`
- `multi_fault_scenario`

Reason:

- together they cover single-fault detection, recovery behavior, repeated topology transitions, and multi-event ordering
- they are the most representative scenarios for the project's digital-twin claims

The following scenario is retained as a dedicated robustness check rather than a main scenario:

- `observation_degradation_scenario`

Reason:

- it validates `SYNC_ERROR` handling and false-positive suppression
- it is important for correctness, but it is not the main latency-oriented scenario

## 4. Primary Result Sets

The following result sets should be treated as the main artifacts for later use.

### 4.1 Main scenario matrix

Primary matrix:

- VM artifact prefix: `traffic_profile_full_matrix`

Scope:

- topology: `geant_backbone_8cities_stage3`
- controller: `src.controller.topology_aware_switch`
- scenarios:
  - `recovery_scenario`
  - `link_flap_scenario`
  - `multi_fault_scenario`
- traffic profiles:
  - `none`
  - `icmp`
  - `iperf_tcp`
- `repeat = 3`

Primary VM artifacts:

- `data/exports/traffic_profile_full_matrix.csv`
- `data/exports/traffic_profile_full_matrix_summary.csv`
- `data/exports/traffic_profile_full_matrix_manifest.json`
- `data/plots/traffic_profile_full_matrix_summary.png`

This matrix is the best default reference for:

- how load changes twin timing behavior
- how the twin behaves across the main fault scenarios
- how `none`, `icmp`, and `iperf_tcp` compare under the same topology and controller

### 4.2 Main robustness result

Primary robustness artifact:

- VM artifact prefix: `observation_degradation_stage3`

Scope:

- topology: `geant_backbone_8cities_stage3`
- controller: `src.controller.topology_aware_switch`
- validates `SYNC_ERROR` emission without false `LINK_DOWN`

Primary VM artifacts:

- `data/exports/observation_degradation_stage3.csv`
- `data/exports/observation_degradation_stage3_summary.csv`

This result should be used when the project needs to demonstrate:

- observation degradation handling
- robustness against partial controller REST failures

## 5. Secondary Result Sets

The following result sets are still important, but they should be treated as extension studies.

### 5.1 Cross-topology comparison

Artifact prefix:

- `p34_full_matrix`

Role:

- topology realism and scaling comparison
- compares `geant_backbone_8cities_stage3` against `geant2012_core12`

Local interpretation note:

- [p34_comparison_notes.md](/Users/chenyumeng/Downloads/twin/docs/p34_comparison_notes.md)

### 5.2 Polling sensitivity comparison

Artifact prefix:

- `polling_full_matrix`

Role:

- compares `1s / 2s / 4s` polling intervals
- mainly supports the claim that recovery delay scales with the polling interval

Local interpretation note:

- [polling_comparison_notes.md](/Users/chenyumeng/Downloads/twin/docs/polling_comparison_notes.md)

### 5.3 Control-plane comparison

Artifact prefix:

- `controller_compare_summary`

Role:

- compares `topology_aware_switch` and `tree_routing_switch`
- should be used as an additional architecture/comparison study rather than the main baseline

### 5.4 Traffic-profile interpretation note

Local interpretation note:

- [traffic_profile_comparison_notes.md](/Users/chenyumeng/Downloads/twin/docs/traffic_profile_comparison_notes.md)

## 6. Baseline Claims Supported by the Current Artifacts

Using the primary baseline above, the project can now support these claims:

1. The twin detects link failures and recoveries on a realistic data-driven backbone subnetwork rather than only on a toy topology.
2. The twin remains functional under multiple background-traffic conditions, including no traffic, ICMP probing, and continuous TCP load.
3. The twin can distinguish controller observation degradation from real topology failure by emitting `SYNC_ERROR` without false `LINK_DOWN`.
4. The project can compare timing behavior across scenarios, traffic conditions, polling intervals, topology size, and controller strategies.

## 7. Recommended Reproduction Commands

These commands represent the default way to reproduce the primary baseline on the VM.

Start controller:

```bash
cd /home/yumeng/twin
source .venv/bin/activate
PYTHONPATH=/home/yumeng/twin ryu-manager --observe-links src.controller.topology_aware_switch ryu.app.ofctl_rest ryu.app.rest_topology
```

Run the primary traffic-profile matrix:

```bash
cd /home/yumeng/twin
source .venv/bin/activate
sudo env "PATH=$PATH" PYTHONPATH=/home/yumeng/twin TOPOLOGY_FILE=/home/yumeng/twin/data/topologies/geant_backbone_8cities_stage3.json SCENARIOS="recovery_scenario link_flap_scenario multi_fault_scenario" TRAFFIC_PROFILES="none icmp iperf_tcp" OUTPUT_PREFIX=/home/yumeng/twin/data/exports/traffic_profile_full_matrix REPEAT=3 bash scripts/run_experiment_matrix.sh
```

Run the robustness scenario:

```bash
cd /home/yumeng/twin
source .venv/bin/activate
sudo env "PATH=$PATH" PYTHONPATH=/home/yumeng/twin SCENARIO_NAME=observation_degradation_scenario TOPOLOGY_FILE=/home/yumeng/twin/data/topologies/geant_backbone_8cities_stage3.json OUTPUT_CSV=/home/yumeng/twin/data/exports/observation_degradation_stage3.csv bash scripts/run_experiment.sh
```

Generate the primary matrix figure:

```bash
cd /home/yumeng/twin
source .venv/bin/activate
PYTHONPATH=/home/yumeng/twin .venv/bin/python -m src.twin.plotting --input-csv /home/yumeng/twin/data/exports/traffic_profile_full_matrix_summary.csv --output /home/yumeng/twin/data/plots/traffic_profile_full_matrix_summary.png
```

## 8. Practical Rule for Later Use

Unless a later section explicitly discusses polling sensitivity, topology scaling, or controller comparison:

- use `geant_backbone_8cities_stage3`
- use `src.controller.topology_aware_switch`
- use `2.0s` polling
- cite `traffic_profile_full_matrix` as the main experiment set
- cite `observation_degradation_stage3` as the main robustness check
