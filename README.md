# Digital Twin Network Modeling for SDN

A proof-of-concept digital twin for Software-Defined Networks (SDN), developed as a TER research project in Master 1 Computer and System at Université Paris-Saclay.

The project studies how a digital twin can reconstruct, synchronize and analyze the state of an emulated SDN network using Mininet, Open vSwitch, Ryu and Python.

## Overview

The system maintains a structured digital representation of a network and updates it through a synchronization loop between the emulated network and the software model.

Main objectives:

- Reconstruct the current state of an SDN network.
- Detect topology changes such as link failures and recoveries.
- Generate events such as `LINK_DOWN`, `LINK_UP` and `SYNC_ERROR`.
- Evaluate synchronization delay, polling sensitivity, traffic impact and fidelity limits.
- Export experimental traces for reproducible analysis.

## Technologies

- Python
- Mininet
- Open vSwitch
- Ryu SDN Controller
- Flask
- JSON / CSV
- Matplotlib

## System Architecture

The prototype is organized into four main layers:

1. **Network emulation**: Mininet and Open vSwitch.
2. **SDN observation**: Ryu controller and REST APIs.
3. **Digital twin core**: synchronization engine, diff engine, event engine and state storage.
4. **Presentation and experiments**: Flask API, experiment runner and result visualization.

## Main Features

- Network state reconstruction from Ryu REST APIs.
- Snapshot comparison between successive network states.
- Event generation for link failures, recoveries and synchronization errors.
- Experimental scenarios for recovery, link flap, multi-fault and observation degradation.
- Evaluation of detection delay, recovery delay, polling interval sensitivity and background traffic impact.
- Partial ground-truth comparison using OVS / Mininet instrumentation.

## Experiments

The main experimental campaign uses the `geant_backbone_8cities_stage3` topology with:

- 8 switches
- 8 hosts
- 10 active backbone links
- 3 main scenarios:
  - `recovery_scenario`
  - `link_flap_scenario`
  - `multi_fault_scenario`
- 3 traffic profiles:
  - `none`
  - `icmp`
  - `iperf_tcp`

The project also includes experiments on:

- Observation degradation and `SYNC_ERROR` detection.
- Polling interval sensitivity.
- Cross-topology comparison.
- Randomized background load analysis.

## Results Summary

The prototype successfully detects link failures and recoveries in the tested SDN environment. The experiments show that polling interval has a strong impact on recovery delay, and that the relationship between background traffic load and detection delay is non-linear in the observed Mininet/Ryu setup.

## Report

The final TER report is available in:

```text
report/CHEN_Yumeng_DONG_Yujing_TER_Digital_Twin_Network.pdf
