# TER Network Digital Twin

## 项目简介

本项目是一个面向 TER 报告写作与实验分析的网络数字孪生 PoC。项目围绕一个最小 Mininet 拓扑，通过 Ryu REST API 获取网络观测状态，使用 Python 构建 twin 状态、执行差分、生成事件，并输出实验数据与基础图表。

本项目刻意保持为研究型 PoC，而不是生产级网络管理平台。优先目标是：

- 可运行
- 可解释
- 可复现
- 可用于 TER 报告写作

## 目录结构

```text
README.md
requirements.txt
docs/
  architecture.md
  experiments.md
  report_notes.md
src/
  topology/
  controller/
  twin/
  web/
scenarios/
tests/
data/
  events/
  snapshots/
  exports/
  plots/
scripts/
```

## 环境要求

```text
Python 3.10+
Mininet
Open vSwitch
Ryu
```

## 安装方法

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 启动 Ryu

```bash
PYTHONPATH="$PWD" ryu-manager --observe-links src.controller.topology_aware_switch ryu.app.ofctl_rest ryu.app.rest_topology
```

如果需要回退到最简单的二层学习交换版本：

```bash
PYTHONPATH="$PWD" ryu-manager --observe-links ryu.app.simple_switch_13 ryu.app.ofctl_rest ryu.app.rest_topology
```

如果要做 P3.5 的控制面对比，可使用树路由版本：

```bash
PYTHONPATH="$PWD" ryu-manager --observe-links src.controller.tree_routing_switch ryu.app.ofctl_rest ryu.app.rest_topology
```

当前推荐的控制面对比是：

- `src.controller.topology_aware_switch`
  最短路径 + 生成树泛洪
- `src.controller.tree_routing_switch`
  生成树路径 + 生成树泛洪

如果要在同一拓扑上批量对比这两个控制器，可使用：

```bash
TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json \
SCENARIOS="recovery_scenario" \
TRAFFIC_PROFILES="none icmp" \
bash scripts/run_controller_comparison.sh
```

控制面对比会额外生成：

- `data/exports/controller_compare_summary.csv`
- `data/exports/controller_compare_summary.json`
- `data/plots/controller_compare_summary.png`

控制器事件驱动同步默认使用的共享事件流文件是：

- `data/events/controller_events.jsonl`

## 启动最小拓扑

```bash
sudo bash scripts/run_demo.sh
```

或：

```bash
sudo python3 -m src.topology.minimal_topology --controller-host 127.0.0.1 --controller-port 6633 --pingall
```

启动数据驱动拓扑：

```bash
sudo TOPOLOGY_FILE=data/topologies/geant_subset.json bash scripts/run_demo.sh
```

## 启动 twin service

```bash
python3 -m src.twin.sync_engine --base-url http://127.0.0.1:8080 --loop --print-state
```

如果要切换同步模式，可设置：

```bash
SYNC_MODE=polling
SYNC_MODE=event_driven
SYNC_MODE=hybrid
```

`hybrid` 模式还支持：

```bash
HYBRID_POLL_INTERVAL_SECONDS=10
EVENT_QUEUE_WAIT_SECONDS=0.5
```

## 访问 API / 页面方法

```bash
python3 -m src.web.app --host 127.0.0.1 --port 5000 --sync-on-start
```

访问：

```text
http://127.0.0.1:5000/
http://127.0.0.1:5000/topology
http://127.0.0.1:5000/api/health
http://127.0.0.1:5000/api/topology
http://127.0.0.1:5000/api/state
http://127.0.0.1:5000/api/events
http://127.0.0.1:5000/api/fidelity
http://127.0.0.1:5000/api/anomalies
```

## 运行实验方法

默认运行恢复场景：

```bash
sudo bash scripts/run_experiment.sh
```

切换实验场景：

```bash
sudo SCENARIO_NAME=single_link_failure bash scripts/run_experiment.sh
sudo SCENARIO_NAME=multi_fault_scenario bash scripts/run_experiment.sh
sudo SCENARIO_NAME=observation_degradation_scenario bash scripts/run_experiment.sh
```

使用数据驱动拓扑运行实验：

```bash
sudo TOPOLOGY_FILE=data/topologies/geant_subset.json bash scripts/run_experiment.sh
```

如果要在故障注入前先施加背景流量，可追加：

```bash
sudo TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json BACKGROUND_TRAFFIC=icmp bash scripts/run_experiment.sh
```

如果要用更高负载的 TCP 背景流量，可改为：

```bash
sudo TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json BACKGROUND_TRAFFIC=iperf_tcp bash scripts/run_experiment.sh
```

如果要重复同一实验多次并输出统计汇总，可追加：

```bash
sudo TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json BACKGROUND_TRAFFIC=icmp REPEAT=5 bash scripts/run_experiment.sh
```

重复实验会额外生成：

- `data/exports/<scenario>_summary.csv`
- `data/exports/<scenario>_summary.json`

每条原始记录和 summary 现在还会带上：

- `topology_file`
- `controller_app`
- `configured_repeat_count`
- `poll_interval`

对于链路目标场景，原始记录还会额外导出目标链路两端端口的聚合 counters：

- `pre_fault_total_packets`
- `pre_fault_total_bytes`
- `post_detection_total_packets`
- `post_detection_total_bytes`
- `post_recovery_total_packets`
- `post_recovery_total_bytes`

实验记录现在还会导出保真度采样点：

- `pre_fault_fidelity`
- `post_fault_fidelity`
- `post_recovery_fidelity`

如果要批量运行完整实验矩阵（`recovery`、`flap`、`multi_fault`、`observation_degradation` 各自对比 `none` 和 `icmp`），可使用：

```bash
sudo TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json REPEAT=3 bash scripts/run_experiment_matrix.sh
```

如果要做跨拓扑对比矩阵，可一次传入多个拓扑文件：

```bash
sudo TOPOLOGY_FILES="data/topologies/geant_backbone_8cities_stage3.json data/topologies/generated/geant2012_core12.json" \
REPEAT=3 \
bash scripts/run_experiment_matrix.sh
```

如果要比较不同 polling interval（默认 `1s / 2s / 4s`）对实验结果的影响，可使用：

```bash
sudo TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json \
SCENARIOS="recovery_scenario observation_degradation_scenario" \
TRAFFIC_PROFILES="none icmp" \
REPEAT=3 \
bash scripts/run_polling_comparison.sh
```

如果要比较 `polling`、`event_driven`、`hybrid` 三种同步模式，可使用：

```bash
TOPOLOGY_FILE=data/topologies/geant_backbone_8cities_stage3.json \
bash scripts/run_sync_mode_comparison.sh
```

同步模式对比会生成：

- `data/exports/sync_mode_comparison.csv`
- `data/exports/sync_mode_comparison.json`
- `data/exports/sync_mode_comparison_summary.csv`
- `data/exports/sync_mode_comparison_summary.json`
- `data/exports/sync_mode_comparison_manifest.json`

`sync_mode_comparison.csv` 会保留完整实验字段，包括：

- `sync_mode`
- `sync_duration_ms`
- `pre_fault_fidelity`
- `post_fault_fidelity`
- `post_recovery_fidelity`
- `api_call_count`

如果要运行规模可扩展性实验，可使用：

```bash
bash scripts/run_scalability_experiment.sh
```

该脚本会生成：

- `data/exports/scalability.csv`
- `data/plots/scalability.png`

`scalability.csv` 主要包含：

- `detection_delay`
- `sync_duration_ms`
- `node_count`
- `link_count`
- `api_call_count`
- `repeat_index`

矩阵运行会生成：

- `data/exports/experiment_matrix.csv`
- `data/exports/experiment_matrix.json`
- `data/exports/experiment_matrix_summary.csv`
- `data/exports/experiment_matrix_summary.json`
- `data/exports/experiment_matrix_manifest.json`

异常检测会把最近的端口级异常写入：

- `data/events/anomaly_alerts.jsonl`

异常类型包括：

- `TRAFFIC_SPIKE`
- `TRAFFIC_DROP`
- `COUNTER_STALL`

当前提供两个 8 城市相关拓扑文件：

- `data/topologies/geant_subset.json`
  当前可直接运行的 loop-free 子网
- `data/topologies/geant_backbone_8cities.json`
  更完整的 8 城市主链路模型，其中部分链路标记为 `enabled=false`，用于保留骨干结构但避免当前简单二层控制器在带环拓扑上失效
- `data/topologies/geant_backbone_8cities_stage1.json`
  第一阶段启用 `Paris-Amsterdam` 的小环版本，用于验证 `src.controller.topology_aware_switch` 是否能支持逐步打开 disabled 主链路
- `data/topologies/geant_backbone_8cities_stage2.json`
  第二阶段在 stage1 基础上进一步启用 `Amsterdam-Frankfurt`，用于验证更密集西欧骨干环下的拓扑感知转发
- `data/topologies/geant_backbone_8cities_stage3.json`
  第三阶段启用最后一条 `Vienna-Milan`，用于验证完整 10 条主链路骨干在当前控制面下是否仍可稳定运行

如果要从原始 `GraphML` 导入研究拓扑，可使用：

```bash
python3 -m src.topology.importers.graphml_importer \
  --input data/topologies/raw/geant_sample.graphml \
  --output data/topologies/generated/geant_sample_imported.json \
  --name geant_sample_imported
```

当前仓库已包含：

- `data/topologies/raw/geant_sample.graphml`
  一个最小原始 GraphML 示例
- `data/topologies/generated/geant_sample_imported.json`
  由导入器生成的内部拓扑 JSON 示例
- `data/topologies/raw/Geant2012.graphml`
  一个真实的 Topology Zoo `Geant2012` 原始拓扑文件
- `data/topologies/generated/geant2012_full_imported.json`
  由真实 `Geant2012` 原始文件导入得到的完整内部拓扑 JSON

如果要从原始 `GML` 导入研究拓扑，可使用：

```bash
python3 -m src.topology.importers.gml_importer \
  --input data/topologies/raw/geant_sample.gml \
  --output data/topologies/generated/geant_sample_gml_imported.json \
  --name geant_sample_gml_imported
```

当前仓库也已包含：

- `data/topologies/raw/geant_sample.gml`
  一个最小原始 GML 示例
- `data/topologies/generated/geant_sample_gml_imported.json`
  由 GML 导入器生成的内部拓扑 JSON 示例

如果要从已导入的完整研究拓扑中切出一个中等规模、连通的实验子图，可使用：

```bash
python3 -m src.topology.subset_builder \
  --input data/topologies/generated/geant2012_full_imported.json \
  --output data/topologies/generated/geant2012_core12.json \
  --name geant2012_core12 \
  --description "12-node connected core subset derived from real Geant2012 Topology Zoo data." \
  --switches s1 s3 s5 s7 s8 s13 s14 s16 s20 s30 s36 s40
```

当前仓库也已包含：

- `data/topologies/generated/geant2012_core12.json`
  一个从真实 `Geant2012` 导入结果中切出的 12 节点连通核心子图，可作为 P3.2 的中等规模实验输入

## 绘图方法

```bash
bash scripts/plot_results.sh
```

## 验证方法

最小手动验证清单：

```text
1. 启动 Ryu
2. 启动最小拓扑
3. 在 Mininet CLI 内执行 pingall
4. 执行 python3 -m src.controller.ryu_probe --base-url http://127.0.0.1:8080
5. 启动 python3 -m src.twin.sync_engine --base-url http://127.0.0.1:8080 --loop --print-state
6. 在 Mininet CLI 注入 link s1 s2 down / up
7. 检查 data/events/events.jsonl
8. 运行 bash scripts/run_experiment.sh
9. 运行 bash scripts/plot_results.sh
```

## 输出文件说明

```text
data/events/
  事件日志（JSON Lines）
data/snapshots/
  状态快照（JSON）
data/exports/
  实验结果导出（CSV/JSON）
data/plots/
  图表输出
```

## 已知限制

- 本项目是 PoC，不是生产系统。
- 故障检测延迟受 polling interval 限制。
- 控制器视图不等于完整物理真值。
- 真实数据与真实网络行为只作为场景参考，不作为系统运行前提。
- 不保证复杂拓扑和高并发下的实时性。
