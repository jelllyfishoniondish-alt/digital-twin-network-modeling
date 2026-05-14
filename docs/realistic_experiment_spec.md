# Realistic Experiment Enhancement Spec

## 1. Background

The current project validates the digital twin pipeline on a minimal three-switch line topology:

- `s1 - s2 - s3`
- one host per switch
- failure injection through `configLinkStatus`
- event export through CSV / JSON / PNG

This is sufficient for a proof of concept, but it is too small and too synthetic to support a stronger experimental study on network digital twins.

The next stage should move from a hand-written toy topology to a data-driven and more realistic backbone-style topology, while preserving the current twin pipeline:

- Mininet / OVS for emulation
- Ryu REST for observation
- polling-based twin synchronization
- event-based fault detection
- experiment export and plotting

## 2. Objectives

### 2.1 Primary Objective

Upgrade the experiment pipeline so that the twin is evaluated on a realistic research/backbone-style network topology instead of a fixed three-node demo topology.

### 2.2 Secondary Objectives

- Introduce topology data from open research-grade datasets
- Attach geographic and link-level realism to the emulated topology
- Extend experiments beyond single link down/up detection
- Produce repeatable experimental outputs suitable for comparative analysis

## 3. Non-Goals

- Full reproduction of the operational GÉANT production network
- Real-time integration with live GÉANT telemetry
- Large-scale emulation of the full European backbone on the current VM
- Traffic engineering optimization or routing protocol emulation beyond the current SDN/Ryu setup

## 4. Data Source Strategy

### 4.1 Priority Order

1. `Topology Zoo` / `TopoHub` machine-readable topology data
2. `GÉANT` official topology material for sanity-checking and naming consistency
3. `SNDlib Geant` or similar datasets for later capacity/demand extensions

### 4.2 Rationale

`Topology Zoo` and `TopoHub` are the most practical starting points because they provide graph-oriented formats that can be transformed into Mininet topologies with limited preprocessing.

`GÉANT` official material is useful as a reference for the real network context, but not sufficient alone as the primary machine-readable input.

`SNDlib` should be treated as a later-stage extension when the project is ready to model traffic demand matrices, capacities, or optimization-oriented experiments.

### 4.3 Initial Dataset Scope

Do not start from the full GÉANT or full Europe-wide topology.

Instead, build a `GEANT subset` with approximately:

- 8 to 15 core nodes
- 10 to 20 inter-city links
- stable node metadata: `name`, `city`, optional `country`
- optional edge metadata: `distance_km`, `capacity`, `delay_ms`

## 5. Priority Roadmap

## 5.1 P0: Data-Driven Topology Import

### Goal

Replace the fixed topology with a topology generated from an external dataset.

### Scope

- Add a topology input format under `data/topologies/`
- Create a loader that converts dataset records into an internal topology model
- Add a new topology builder module, separate from `minimal_topology.py`
- Make experiment scripts select a topology file instead of assuming `s1-s2-s3`

### Required Output

- `data/topologies/geant_subset.json`
- `src/topology/data_driven_topology.py`
- CLI or environment support for choosing the topology source

### Acceptance Criteria

- The project can launch a Mininet topology from a data file
- Node and link names are stable across experiment runs
- The twin can still detect `LINK_DOWN` and `LINK_UP` events on the imported topology

## 5.2 P1: Geographic and Link Realism

### Goal

Use real-world structure to make the emulation less synthetic.

### Scope

- Store `city`, optional `country`, and optional coordinates for each node
- Estimate link delay from distance or coordinates
- Optionally attach nominal bandwidth values to links
- Propagate metadata into twin state and exports

### Required Output

- Node metadata fields available in topology data
- Link delay and bandwidth configured during Mininet build
- Twin state enriched with location-aware information where available

### Acceptance Criteria

- At least one generated experiment topology contains named cities
- Links no longer all share the same default delay
- Exported state or experiment metadata preserves the topology context

## 5.3 P1: Richer Fault Scenarios

### Goal

Move beyond a single manual link failure toward more representative failure experiments.

### Scope

- Single-link fault on a core link
- Link recovery
- Dual-link fault
- Node-adjacent fault
- Observation degradation scenario such as partial REST/API failure
- Optional link flap scenario

### Required Output

- Scenario definitions decoupled from hard-coded `s1-s2`
- Ability to target links by topology metadata or link ID
- Per-scenario exported records

### Acceptance Criteria

- Experiments no longer rely on hard-coded toy topology names
- At least four scenarios run on the data-driven topology
- Scenario exports identify the targeted node or link explicitly

## 5.4 P2: Background Traffic and Load-Aware Experiments

### Goal

Evaluate the twin under non-idle conditions.

### Scope

- Add baseline traffic generation between selected hosts
- Add high-load scenarios using `iperf` or equivalent
- Observe whether the twin still reports topology changes correctly under load
- Optionally record link counters before and after fault injection

### Required Output

- Reusable traffic generation helper
- Scenario flag for enabling or disabling background traffic
- Additional exported metrics when traffic is enabled

### Acceptance Criteria

- At least one scenario runs with background traffic enabled
- The twin still detects target failures under load
- Port/link counters change in a way that is visible in the state snapshots

## 5.5 P2: Repeated Trials and Statistical Outputs

### Goal

Turn the experiment pipeline into a repeatable measurement workflow.

### Scope

- Repeat each scenario multiple times
- Export all runs, not only the latest one
- Add summary statistics such as mean, standard deviation, median, and P95
- Replace single-point plots with boxplots, error bars, or grouped comparisons

### Required Output

- Batch experiment runner
- Aggregate CSV / JSON summary
- Improved plotting module

### Acceptance Criteria

- A scenario can be run `N` times with one command
- The exported dataset includes all repetitions
- At least one plot compares multiple runs or multiple scenarios

## 5.6 P3: Larger-Scale Topology Variants

### Goal

Study how the twin behaves as topology size increases.

### Scope

- Keep the existing toy topology as a baseline
- Add a `GEANT subset` topology as the main experiment topology
- Add a larger backbone-style topology as an extension if the VM allows it

### Acceptance Criteria

- The same experiment code works across at least two topology sizes
- Results can be compared by topology scale

## 6. Proposed Implementation Changes

### 6.1 New Data Assets

- `data/topologies/geant_subset.json`
- optional raw input directory:
  - `data/topologies/raw/`

### 6.2 New Modules

- `src/topology/data_driven_topology.py`
- `src/topology/topology_loader.py`
- optional:
  - `src/twin/traffic_runner.py`
  - `src/twin/batch_experiment_runner.py`

### 6.3 Existing Modules to Update

- `src/twin/experiment_runner.py`
  - topology selection
  - topology-aware link targeting
  - batch execution support
- `src/twin/plotting.py`
  - aggregated plotting
  - scenario comparison plots
- `src/twin/models.py`
  - optional metadata support for node and link realism
- `src/twin/sync_engine.py`
  - preserve additional link metadata if introduced

## 7. Experiment Evolution Plan

### Phase 1

Deliver a `GEANT subset` topology and run the current down/up experiments on it.

### Phase 2

Add geographic delay realism and multi-fault scenarios.

### Phase 3

Add background traffic and repeated measurements.

### Phase 4

Evaluate larger topology variants and compare results across scales.

## 8. Success Criteria

The enhancement is considered successful if the project can:

- build a topology from open dataset input instead of hard-coded nodes
- run fault and recovery experiments on that topology
- export results with topology-aware metadata
- repeat experiments multiple times and summarize the measurements
- demonstrate a clear improvement in realism over the current toy setup

## 9. Risks and Constraints

- Full public backbone datasets may be incomplete, inconsistent, or too large for direct Mininet use
- Official GÉANT material may not provide directly importable formats
- A large topology may exceed the VM's CPU and memory budget
- Background traffic can destabilize timing measurements if introduced too early
- More realism increases preprocessing and validation effort

## 10. Recommended Immediate Next Step

Implement `P0` only:

- define `geant_subset.json`
- build a data-driven topology loader
- adapt experiment execution so scenarios target topology-defined links instead of `s1-s2`

This is the smallest change that materially improves realism without overextending the current codebase.

## 11. Reference Datasets

- GÉANT official topology context: <https://network.geant.org/geant-network-topology/>
- Topology Zoo dataset index: <https://topology-zoo.org/dataset.html>
- TopoHub dataset platform: <https://www.topohub.org/>
