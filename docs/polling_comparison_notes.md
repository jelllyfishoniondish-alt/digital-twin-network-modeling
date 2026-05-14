# Polling Interval Comparison Findings

## Scope

This note summarizes the final polling-interval comparison matrix produced on the VM for:

- topology: `geant_backbone_8cities_stage3`
- scenarios:
  - `recovery_scenario`
  - `observation_degradation_scenario`
- traffic profiles:
  - `none`
  - `icmp`
- polling intervals:
  - `1s`
  - `2s`
  - `4s`
- `repeat = 3`

Primary artifacts on the VM:

- `data/exports/polling_full_matrix.csv`
- `data/exports/polling_full_matrix_summary.csv`
- `data/exports/polling_full_matrix_manifest.json`
- `data/plots/polling_full_matrix_summary.png`

## Main Findings

### 1. Longer polling intervals clearly increase recovery latency

The cleanest signal in this matrix is the recovery side of `recovery_scenario`.

- `none`
  - `1s`: recovery `0.993098s`
  - `2s`: recovery `1.977366s`
  - `4s`: recovery `3.983571s`

- `icmp`
  - `1s`: recovery `0.919655s`
  - `2s`: recovery `1.622013s`
  - `4s`: recovery `3.851688s`

This is the expected polling-driven trend: when the polling period increases, twin recovery confirmation is delayed because the restored link is only visible on a later sync cycle.

### 2. Detection delay also worsens at `4s`, but `1s` vs `2s` is less clean

For `recovery_scenario`, detection delay at `4s` is clearly worse:

- `none`
  - `1s`: detection `0.612924s`
  - `2s`: detection `0.420530s`
  - `4s`: detection `2.411032s`

- `icmp`
  - `1s`: detection `0.786003s`
  - `2s`: detection `1.562542s`
  - `4s`: detection `1.263581s`

The `4s` case is consistently slower than the shorter polling configurations, but `1s` and `2s` do not order perfectly. That is consistent with earlier observations in this project: detection timing depends not only on the polling period, but also on controller convergence timing and when the topology change becomes visible to the next successful poll.

### 3. Observation degradation is a robustness test, not a pure polling-latency benchmark

`observation_degradation_scenario` measures the delay until the twin records a `SYNC_ERROR` for `/v1.0/topology/links`, while verifying that no false `LINK_DOWN` is emitted.

Results:

- `none`
  - `1s`: detection `0.917431s`
  - `2s`: detection `1.033982s`
  - `4s`: detection `1.483818s`

- `icmp`
  - `1s`: detection `1.110273s`
  - `2s`: detection `0.439695s`
  - `4s`: detection `0.509751s`

This scenario does not show a strict monotonic relationship with the configured polling interval, especially under `icmp`. That is acceptable because the scenario is primarily validating **robustness semantics**:

- the twin records observation degradation as `SYNC_ERROR`
- the twin does **not** misreport a real link failure

So this scenario should be interpreted as a correctness/robustness experiment first, and only secondarily as a timing experiment.

### 4. Background traffic still changes timing behavior

Even in the polling comparison, `icmp` background traffic still affects measured delays.

For example:

- `recovery_scenario`
  - `1s`
    - `none`: detection `0.612924s`
    - `icmp`: detection `0.786003s`
  - `2s`
    - `none`: detection `0.420530s`
    - `icmp`: detection `1.562542s`

This remains consistent with the earlier topology and controller comparisons: the twin keeps working under load, but measured reaction timing depends on the runtime condition of the network and controller.

## Figure Notes

### Figure: `polling_full_matrix_summary.png`

Recommended interpretation:

- x-axis labels combine:
  - polling interval
  - scenario
  - traffic profile
- teal bars show detection delay
- red markers show recovery delay

Recommended caption:

`Comparison of twin detection and recovery delays under three polling intervals. Recovery delay scales clearly with the polling period in recovery experiments, while observation degradation remains primarily a robustness validation showing SYNC_ERROR reporting without false link-down events.`

## Short Conclusion

The final polling comparison supports two main claims:

1. recovery timing is strongly constrained by the polling interval
2. observation degradation is handled robustly without false topology-failure reports

The strongest quantitative signal is therefore the recovery-delay trend, while the observation-degradation scenario is more useful as a correctness check than as a strict latency benchmark.
