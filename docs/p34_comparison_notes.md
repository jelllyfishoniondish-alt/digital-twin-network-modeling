# P34 Cross-Topology Findings

## Scope

This note summarizes the final cross-topology matrix produced by:

- `geant_backbone_8cities_stage3`
- `geant2012_core12`

Compared dimensions:

- `recovery_scenario`
- `link_flap_scenario`
- `multi_fault_scenario`
- background traffic `none` vs `icmp`
- `repeat = 1`

Primary output files on the VM:

- `data/exports/p34_full_matrix.csv`
- `data/exports/p34_full_matrix_summary.csv`
- `data/exports/p34_full_matrix_manifest.json`
- `data/plots/p34_full_matrix_summary.png`

## Main Findings

### 1. Background traffic increases detection delay consistently

Across both topologies, `icmp` background traffic increased detection delay in all main scenarios.

Representative examples:

- `recovery_scenario`
  - `geant_backbone_8cities_stage3`
    - `none`: `0.545329s`
    - `icmp`: `1.592034s`
  - `geant2012_core12`
    - `none`: `0.893741s`
    - `icmp`: `2.104658s`

- `link_flap_scenario_down_1`
  - `geant_backbone_8cities_stage3`
    - `none`: `0.494017s`
    - `icmp`: `1.609637s`
  - `geant2012_core12`
    - `none`: `0.897431s`
    - `icmp`: `2.129881s`

This indicates the twin remains functional under load, but controller/twin reaction becomes slower when the data plane is busy.

### 2. The larger imported topology is usually slower than the curated 8-city backbone

For the same scenario and traffic profile, `geant2012_core12` generally showed higher detection delay than `geant_backbone_8cities_stage3`.

Representative examples:

- `recovery_scenario`, `none`
  - `geant_backbone_8cities_stage3`: `0.545329s`
  - `geant2012_core12`: `0.893741s`

- `multi_fault_scenario_fault_1`, `icmp`
  - `geant_backbone_8cities_stage3`: `1.603137s`
  - `geant2012_core12`: `2.126107s`

This supports the expected scaling trend: as topology size and path diversity increase, the twin tends to detect topology changes more slowly.

### 3. Recovery delay stays in the same order of magnitude across both topologies

Recovery delay is less cleanly separated by topology than detection delay.

Examples:

- `recovery_scenario`, `none`
  - `geant_backbone_8cities_stage3`: `1.643649s`
  - `geant2012_core12`: `1.992887s`

- `recovery_scenario`, `icmp`
  - `geant_backbone_8cities_stage3`: `2.021446s`
  - `geant2012_core12`: `1.700611s`

This suggests recovery timing depends not only on topology size, but also on controller convergence timing and when the next successful poll observes the restored link.

### 4. The updated exports are now easier to interpret

The final `p34` outputs improved traceability compared with earlier `p33` results:

- imported-topology target links now use readable city-pair labels such as `Bulgaria-Greece`
- summaries now include:
  - `topology_file`
  - `controller_app`
  - `configured_repeat_count`
  - `poll_interval`
- a manifest file records exactly which topology files, scenarios, and traffic profiles produced the artifacts

## Figure Notes

### Figure: `p34_full_matrix_summary.png`

Recommended interpretation:

- x-axis labels combine:
  - topology name
  - scenario name
  - traffic profile
- teal bars show detection delay
- red markers show recovery delay
- where available, summary statistics can include error bars and `P95`

Recommended caption:

`Comparison of twin detection and recovery delays across two backbone topologies and two traffic conditions. Background ICMP traffic increases detection delay in all tested scenarios, and the imported 12-node GEANT core generally reacts more slowly than the curated 8-city backbone.`

## Short Conclusion

The final cross-topology matrix shows three stable trends:

1. the twin still detects failures and recoveries under background traffic
2. added topology realism and scale tend to increase detection delay
3. the updated export format is now traceable enough for direct use in later analysis and report writing
