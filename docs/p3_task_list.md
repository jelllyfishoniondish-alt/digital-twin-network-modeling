# P3 Task List

## Goal

P3 focuses on scale, external data realism, and comparative evaluation.

By the time P3 starts, the project is assumed to already have:

- a data-driven topology pipeline
- a realistic 8-city backbone subset
- a loop-capable topology-aware controller
- background traffic support
- repeated experiment support
- matrix-style scenario execution

P3 should not rebuild those foundations. It should extend them.

## Scope

P3 work is grouped into four tracks:

1. stronger topology data provenance
2. larger topology variants
3. more systematic comparison studies
4. stronger exported experiment artifacts

## P3.1 Real Dataset Import

### Objective

Reduce manual curation by importing machine-readable research topology data directly.

### Tasks

- add `data/topologies/raw/` for original dataset files
- add a converter for at least one source:
  - `Topology Zoo`
  - `TopoHub`
- map raw nodes into internal fields:
  - `name`
  - `city`
  - `country`
  - `latitude`
  - `longitude`
- map raw edges into internal fields:
  - `src`
  - `dst`
  - `label`
  - `distance_km`
  - `delay_ms`
  - optional `bandwidth_mbps`
- record provenance in exported topology JSON

### Deliverables

- `src/topology/importers/`
- one imported topology JSON generated from a raw source file
- documentation of the conversion assumptions

### Acceptance Criteria

- at least one topology file is generated from raw research data, not only hand-written JSON
- imported topology can be launched by the existing Mininet builder
- twin experiments can run on the imported topology without code changes to the experiment logic

## P3.2 Medium-Scale Topology Variant

### Objective

Evaluate how the twin behaves on a larger topology than the current 8-city backbone.

### Tasks

- define a medium-scale topology target:
  - suggested size: 12 to 15 cities
- preserve the same host-per-switch modeling style initially
- keep scenario targets meaningful and stable
- verify the topology-aware controller still maintains connectivity

### Deliverables

- one new medium-scale topology file
- at least one validated scenario run on that topology

### Acceptance Criteria

- `pingAll()` succeeds on the medium-scale topology
- at least `recovery_scenario` and `link_flap_scenario` run successfully
- exported results include the new topology name

## P3.3 Comparative Experiment Matrix

### Objective

Turn the current matrix runner into a true comparison workflow across topology scale and runtime conditions.

### Tasks

- compare:
  - 8-city backbone
  - medium-scale topology
- compare:
  - `none`
  - `icmp`
- compare:
  - `recovery_scenario`
  - `link_flap_scenario`
  - `multi_fault_scenario`
- optionally compare different polling intervals:
  - `1s`
  - `2s`
  - `4s`

### Deliverables

- one combined matrix dataset for scale comparison
- one combined matrix dataset for polling comparison
- summary plots that group by topology and scenario

### Acceptance Criteria

- experiment outputs can be compared by topology name and background traffic profile
- summary CSV includes enough metadata to group by topology and scenario
- at least one plot compares multiple topologies in one figure

## P3.4 Export and Plot Improvements

### Objective

Make experiment outputs easier to interpret without manual post-processing.

### Tasks

- add grouped plotting by:
  - scenario
  - background traffic
  - topology
- add optional boxplot or error-bar plot output
- export run metadata:
  - topology file
  - repeat count
  - polling interval
  - controller app
- add a matrix manifest file describing the generated artifacts

### Deliverables

- improved plotting module
- matrix manifest JSON
- at least one multi-series figure

### Acceptance Criteria

- a repeated matrix run generates both raw records and grouped summaries
- output files are traceable without reading the console logs
- plot labels distinguish scenario, traffic profile, and topology

## P3.5 Optional Control-Plane Comparison

### Objective

Evaluate whether the twin’s results depend on the forwarding/control strategy.

### Tasks

- keep current `topology_aware_switch` as baseline
- optionally add an alternative forwarding strategy
- compare connectivity stability and measured delays under both strategies

### Deliverables

- second controller variant or a documented reason to defer it

### Acceptance Criteria

- controller choice is represented in exported metadata if comparison is implemented

## Priority Order

Recommended order:

1. `P3.1` real dataset import
2. `P3.2` medium-scale topology
3. `P3.3` comparative matrix across topology sizes
4. `P3.4` export and plot improvements
5. `P3.5` optional control-plane comparison

## Suggested First P3 Milestone

The first concrete P3 milestone should be:

- import one raw topology source
- produce one new 12-to-15 city topology
- validate `recovery_scenario` on it

This is the smallest step that materially advances realism and scale at the same time.
