# Traffic Profile Comparison Findings

## Scope

This note summarizes the final traffic-profile comparison matrix produced on the VM for:

- topology: `geant_backbone_8cities_stage3`
- scenarios:
  - `recovery_scenario`
  - `link_flap_scenario`
  - `multi_fault_scenario`
- traffic profiles:
  - `none`
  - `icmp`
  - `iperf_tcp`
- `repeat = 3`

Primary artifacts on the VM:

- `data/exports/traffic_profile_full_matrix.csv`
- `data/exports/traffic_profile_full_matrix_summary.csv`
- `data/exports/traffic_profile_full_matrix_manifest.json`
- `data/plots/traffic_profile_full_matrix_summary.png`

## Main Findings

### 1. Additional background traffic increases fault-detection delay

The cleanest signal is the first failure-detection phase in each scenario.

- `recovery_scenario`
  - `none`: detection `0.448443s`
  - `iperf_tcp`: detection `0.752905s`
  - `icmp`: detection `1.567610s`

- `link_flap_scenario_down_1`
  - `none`: detection `0.477773s`
  - `iperf_tcp`: detection `0.684838s`
  - `icmp`: detection `1.561406s`

- `multi_fault_scenario_fault_1`
  - `none`: detection `0.233982s`
  - `iperf_tcp`: detection `0.917180s`
  - `icmp`: detection `1.381603s`

Across these first-stage detections, `none` is consistently fastest, `iperf_tcp` is slower, and `icmp` is slowest.

### 2. `iperf_tcp` degrades timing, but not always in the same way as `icmp`

`iperf_tcp` does not simply behave like a heavier version of `icmp`.

Examples:

- `recovery_scenario`
  - `iperf_tcp`: detection `0.752905s`, recovery `1.858643s`
  - `icmp`: detection `1.567610s`, recovery `1.624801s`

- `link_flap_scenario_up_1`
  - `iperf_tcp`: recovery `1.790404s`
  - `icmp`: recovery `1.615536s`
  - `none`: recovery `1.877897s`

- `multi_fault_scenario_fault_2`
  - `iperf_tcp`: detection `2.047046s`
  - `icmp`: detection `1.951762s`
  - `none`: detection `1.810653s`

This suggests traffic type matters, not just traffic presence. The controller and twin are reacting to different runtime conditions under periodic ICMP probing versus continuous TCP load.

### 3. Later-stage events remain slower than the first detected fault

In the multi-stage scenarios, the first event is usually detected faster than later transitions.

Examples:

- `link_flap_scenario`
  - `down_1`
    - `none`: `0.477773s`
    - `icmp`: `1.561406s`
    - `iperf_tcp`: `0.684838s`
  - `down_2`
    - `none`: `1.776092s`
    - `icmp`: `1.666561s`
    - `iperf_tcp`: `1.867777s`

- `multi_fault_scenario`
  - `fault_1`
    - `none`: `0.233982s`
    - `icmp`: `1.381603s`
    - `iperf_tcp`: `0.917180s`
  - `fault_2`
    - `none`: `1.810653s`
    - `icmp`: `1.951762s`
    - `iperf_tcp`: `2.047046s`

This is consistent with the rest of the project: later transitions depend on both polling cadence and controller convergence after the earlier topology change.

### 4. Counter export confirms that `iperf_tcp` produces a materially different load level

The updated experiment export now includes target-link aggregate counters:

- `pre_fault_total_packets`
- `pre_fault_total_bytes`
- `post_detection_total_packets`
- `post_detection_total_bytes`
- `post_recovery_total_packets`
- `post_recovery_total_bytes`

In the VM smoke run for `recovery_scenario` with `iperf_tcp`, the target-link byte counts rose from:

- pre-fault: `34500`
- post-detection: `19679780`
- post-recovery: `56426416`

This confirms the `iperf_tcp` profile is not just a label change. It creates a higher-throughput operating condition that is visible in the twin's exported state.

## Figure Notes

### Figure: `traffic_profile_full_matrix_summary.png`

Recommended interpretation:

- x-axis labels combine:
  - scenario name
  - traffic profile
- teal bars show detection delay
- red markers show recovery delay

Recommended caption:

`Comparison of twin detection and recovery delays under three background-traffic profiles. Added traffic increases detection delay in the first fault stage across all scenarios, while continuous TCP load and ICMP probing affect later transitions differently.`

## Short Conclusion

The final traffic-profile matrix supports three main claims:

1. background traffic makes twin detection slower than the no-traffic baseline
2. `iperf_tcp` and `icmp` affect timing differently, so traffic type matters
3. exported counters now provide direct evidence that the high-load profile changes the observed operating condition on the target link
