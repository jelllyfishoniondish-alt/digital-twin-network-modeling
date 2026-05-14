# 网络数字孪生项目实验报告粗稿

## 1. 项目目的

本项目实现了一个面向 SDN 场景的网络数字孪生原型。系统运行在 Mininet 和 Ryu 控制器之上，通过持续采集控制器观测到的交换机、链路、主机、端口统计和流表信息，在孪生侧构建一份结构化的网络状态，再通过前后两次状态差分生成链路故障、链路恢复、交换机上下线、主机变化和同步错误等事件。

本报告不追求完整学术格式，也不展开参考文献。重点说明三件事：

- 实验具体做了什么
- 实验数据来自哪里，依据是什么
- 现有结果能支持什么结论

## 2. 系统做了什么

系统整体可以分成四层：

1. 网络仿真层  
   使用 Mininet 和 Open vSwitch 构建实验网络，并在实验脚本中注入链路故障、链路恢复和观测退化等动作。

2. 状态采集层  
   通过 Ryu REST API 采集网络状态。核心入口在 `src/controller/ryu_api_client.py`，主要访问的接口包括：
   - `/v1.0/topology/switches`
   - `/v1.0/topology/links`
   - `/v1.0/topology/hosts`
   - `/stats/switches`
   - `/stats/portdesc/<switch_id>`
   - `/stats/port/<switch_id>`
   - `/stats/flow/<switch_id>`

3. 孪生核心层  
   `src/twin/sync_engine.py` 负责同步和构造 `NetworkState`，`src/twin/diff_engine.py` 负责状态差分，`src/twin/event_engine.py` 负责把差分结果转化为结构化事件。

4. 展示与实验层  
   `src/web/app.py` 提供 API 和基础页面，`src/twin/experiment_runner.py` 负责编排实验，最后将结果导出为 CSV、JSON 和图表。

因此，这个项目并不只是一个可视化页面，而是一个能够持续同步真实观测、保留状态快照、输出事件和实验结果的数字孪生原型。

![系统架构图](../data/plots/report/architecture.png)

图 1 展示了系统的四层结构，从网络仿真、控制器观测到孪生核心和展示导出，和本项目实际实现是一致的。

![系统数据流图](../data/plots/report/data_flow.png)

图 2 展示了系统中的数据流路径，即 Mininet/OVS 中的变化如何通过 Ryu 控制器进入孪生状态构建、差分和事件生成流程。

## 3. 数据来源与依据

本报告使用的数据全部来自当前工作区内已经存在的文件，主要包括以下几类。

### 3.1 拓扑数据

主实验拓扑来自：

- `data/topologies/geant_backbone_8cities_stage3.json`

这是当前项目的主基线拓扑，包含 8 个城市节点和 10 条主干链路。主实验大多围绕它展开。

跨拓扑对比使用：

- `data/topologies/geant2012_core12.json`

该文件用于与 8 城市骨干子网做对比，观察拓扑规模和结构复杂度变化后，孪生系统的表现是否变化。

![8 城市主实验拓扑](../data/plots/report/topology_geant8.png)

图 3 给出了本项目主实验使用的 8 城市骨干子网示意图。后续大部分主结果都基于这张拓扑得到。

### 3.2 运行时观测数据

运行时状态不是手工编造的，而是由 Ryu 控制器提供，再由孪生程序采集和整理。也就是说，实验中的交换机、链路、端口和流表信息，直接来自控制器当时看到的网络状态。

### 3.3 实验导出数据

本报告主要依据以下导出文件：

- `data/exports/traffic_profile_full_matrix.csv`
- `data/exports/traffic_profile_full_matrix_summary.csv`
- `data/exports/traffic_profile_repeat10.csv`
- `data/exports/traffic_profile_repeat10_summary.csv`
- `data/exports/observation_degradation_stage3.csv`
- `data/exports/observation_degradation_stage3_summary.csv`
- `data/exports/polling_full_matrix_summary.csv`
- `data/exports/p34_full_matrix_summary.csv`

其中：

- 原始 `csv` 记录单次运行结果
- `summary.csv` 给出按场景聚合后的均值、P95 和标准差
- `data/events/events.jsonl` 保存结构化事件日志

### 3.4 导出字段说明

从 `traffic_profile_full_matrix.csv` 可以看到，每条实验记录至少包含这些字段：

- `scenario_name`
- `fault_injection_timestamp`
- `detection_timestamp`
- `recovery_timestamp`
- `detection_delay`
- `recovery_delay`
- `poll_interval`
- `sync_mode`
- `topology_name`
- `topology_file`
- `target_link`
- `controller_app`
- `background_traffic`
- `pre_fault_fidelity`
- `post_fault_fidelity`
- `post_recovery_fidelity`
- `node_count`
- `link_count`
- `sync_duration_ms`
- `api_call_count`
- 目标链路的包和字节计数器

这说明本项目输出的不只是“有没有检测到故障”，还保留了实验环境、孪生质量和目标链路统计信息，因此后续分析是可追溯的。

## 4. 实验设计

### 4.1 主实验基线

本报告采用当前项目已经固定下来的主实验基线：

- 拓扑：`geant_backbone_8cities_stage3`
- 控制器：`src.controller.topology_aware_switch`
- 同步方式：`polling`
- 默认轮询周期：`2.0s`

### 4.2 主要实验场景

1. `recovery_scenario`  
   先让目标链路 down，再恢复 up，观察故障检测和恢复检测是否成功。

2. `link_flap_scenario`  
   让链路发生抖动，观察孪生是否还能及时记录变化。

3. `multi_fault_scenario`  
   顺序注入多个故障，观察事件顺序和检测能力。

4. `observation_degradation_scenario`  
   不是制造真实物理故障，而是制造控制器观测失败，验证系统是否会记录 `SYNC_ERROR` 而不是误报 `LINK_DOWN`。

### 4.3 对比维度

当前工作区中有可直接使用结果文件的对比维度主要有三类：

1. 不同背景流量
   - `none`
   - `icmp`
   - `iperf_tcp`

2. 不同轮询周期
   - `1.0s`
   - `2.0s`
   - `4.0s`

3. 不同拓扑
   - `geant_backbone_8cities_stage3`
   - `geant2012_core12`

说明：代码中还实现了控制器对比和同步模式对比，但当前工作区里没有对应的汇总导出文件，因此本粗稿不把它们写成正式结果。

### 4.4 核心指标

本文主要使用以下指标：

- `detection_delay`：从故障注入到孪生产生检测事件的时延
- `recovery_delay`：从恢复动作到孪生产生恢复事件的时延
- `sync_duration_ms`：单次同步处理耗时
- `api_call_count`：一次同步中调用控制器 API 的次数
- `fidelity`：孪生状态与控制器观测的一致性

## 5. 实验结果与分析

### 5.1 背景流量对检测和恢复时延的影响

主结果来自补跑后的 `data/exports/traffic_profile_repeat10_summary.csv`。这次补跑将主实验矩阵的重复次数从 `3` 提高到 `10`，用于回应“样本数偏少”的问题。

在 `recovery_scenario` 下，三个背景流量配置的结果如下：

- `none`：检测时延 `0.458s`，恢复时延 `1.872s`
- `iperf_tcp`：检测时延 `0.769s`，恢复时延 `1.886s`
- `icmp`：检测时延 `1.144s`，恢复时延 `1.790s`

这个结果说明，增加背景流量后，孪生系统仍然可以工作，但检测和恢复都变慢了，尤其是 `icmp` 条件下检测时延增长更明显。

在 `link_flap_scenario` 中，检测均值分别为：

- `none`：`0.360s`
- `iperf_tcp`：`0.719s`
- `icmp`：`0.970s`

在 `multi_fault_scenario` 中，检测均值分别为：

- `none`：`0.382s`
- `iperf_tcp`：`0.704s`
- `icmp`：`1.068s`

这个趋势在多个场景下都基本一致：无背景流量最快，`iperf_tcp` 次之，`icmp` 最慢。说明流量类型和负载水平都会影响控制器观测和孪生同步的时序表现。

![不同背景流量下的时延对比](../data/plots/traffic_profile_repeat10_summary.png)

图 4 对应 `repeat=10` 主实验矩阵结果，直观展示了不同背景流量下检测时延和恢复时延的变化趋势。

### 5.2 目标链路统计值证明负载确实发生了变化

原始导出文件除了时延，还记录了目标链路的包和字节计数器，例如：

- `pre_fault_total_packets`
- `pre_fault_total_bytes`
- `post_detection_total_packets`
- `post_detection_total_bytes`
- `post_recovery_total_packets`
- `post_recovery_total_bytes`

因此，`iperf_tcp` 并不只是实验标签的变化，而是对应到目标链路真实可观测的流量变化。也就是说，本项目不仅证明了“负载影响时延”，还保留了足够的数据去解释为什么时延会变化。

### 5.3 观测退化实验验证了系统的鲁棒性

`observation_degradation_stage3.csv` 的三条原始记录都带有类似备注：

- `SYNC_ERROR detected, no false LINK_DOWN.`

对应的汇总结果 `observation_degradation_stage3_summary.csv` 中，检测均值约为 `0.381s`。

这类实验的意义不在于时延本身，而在于语义正确性。系统区分了两类情况：

- 控制器暂时看不到链路信息
- 物理链路真的断开

结果说明，当前实现能够把前者记录为 `SYNC_ERROR`，而不是误报成 `LINK_DOWN`。这是一个很重要的正确性结论，因为数字孪生如果把观测异常当成物理故障，会直接破坏后续分析的可信度。

### 5.4 轮询周期越长，恢复时延越大

`polling_full_matrix_summary.csv` 给出了 `1s / 2s / 4s` 三种轮询周期下的结果。最清晰的信号出现在 `recovery_scenario` 的恢复时延上。

在无背景流量 `none` 下：

- `1s`：检测 `0.369s`，恢复 `0.968s`
- `2s`：检测 `0.508s`，恢复 `1.958s`
- `4s`：检测 `0.768s`，恢复 `3.874s`

这个趋势非常清楚：轮询周期越长，恢复确认越慢，而且增长幅度与轮询周期基本一致。这也符合系统实现逻辑，因为恢复后的链路只有在下一轮成功同步时才会被看到。

检测时延也会变差，但没有恢复时延那样单调、稳定。这说明故障检测除了受 polling interval 影响，还会受到控制器收敛速度和事件发生时刻与采样时刻相对位置的影响。

![不同轮询周期下的时延对比](../data/plots/polling_full_matrix_summary.png)

图 5 展示了 `1s / 2s / 4s` 三种轮询周期下的结果，其中恢复时延随轮询周期增大的趋势最清楚。

### 5.5 更复杂的拓扑通常更慢

`p34_full_matrix_summary.csv` 给出了两个拓扑的对比结果。在 `recovery_scenario`、无背景流量 `none` 下：

- `geant_backbone_8cities_stage3`：检测 `0.628s`，恢复 `1.991s`
- `geant2012_core12`：检测 `0.725s`，恢复 `2.300s`

从这组本地结果看，12 节点拓扑相对于 8 城市骨干子网略慢。这支持一个合理判断：随着拓扑规模和结构复杂度增加，孪生系统要完成状态获取、控制器收敛和变化确认，整体更容易变慢。

不过这里也要注意，目前本地跨拓扑汇总数据量不大，因此这部分更适合作为趋势性观察，而不是特别强的统计结论。

![跨拓扑对比结果](../data/plots/p34_full_matrix_summary.png)

图 6 展示了 8 城市骨干子网与 `geant2012_core12` 两种拓扑下的检测和恢复时延对比。

## 6. 本项目从实验中得到的主要结论

基于当前工作区已有结果，可以得出以下结论。

1. 该系统确实具备数字孪生的基本闭环能力。  
   它不是单纯展示当前状态，而是持续采集、构造结构化状态、做差分、生成事件并导出结果。

2. 系统能够稳定检测链路故障和恢复。  
   在主实验拓扑和多个场景下，都得到了可用的检测与恢复结果。

3. 背景流量会显著影响孪生时延。  
   特别是在 `recovery_scenario`、`link_flap_scenario` 和 `multi_fault_scenario` 中，这个趋势都很明显。

4. 轮询周期是影响恢复时延的关键因素。  
   在 `1s / 2s / 4s` 对比中，恢复时延随轮询周期增大而明显增加，这是本项目最稳定的量化结论之一。

5. 系统能够区分观测退化和真实物理故障。  
   观测失败会触发 `SYNC_ERROR`，而不会误报 `LINK_DOWN`，说明系统在鲁棒性和语义正确性上是成立的。

6. 更复杂拓扑下系统通常会更慢。  
   跨拓扑结果表明，拓扑规模和复杂度提升后，检测和恢复时延有上升趋势。

## 7. 局限性

虽然项目已经形成了完整实验链路，但仍有一些局限。

1. 当前结果主要来自 Mininet + Ryu 仿真环境，不代表真实运营网络。
2. 主实验虽然已经从 toy topology 升级到数据驱动骨干子网，但规模仍然有限。
3. 主实验矩阵已经补跑到 `repeat=10`，但 polling 对比、跨拓扑对比等扩展实验仍然样本数较小，更适合做趋势说明，不适合过度解释。
4. 本地可直接引用的控制器对比和同步模式对比汇总文件缺失，因此本报告没有把它们作为正式结果展开。

## 8. 总结

总体来看，本项目已经完成了一个较完整的网络数字孪生 PoC。系统能够从控制器持续获取网络状态，在孪生侧构建结构化镜像，并对链路故障、链路恢复和观测异常做出可解释的事件输出。

从现有实验结果看，本项目最清楚地证明了三件事：

- 数字孪生可以在数据驱动拓扑上稳定完成故障检测和恢复检测
- 背景流量和轮询周期都会显著影响时延表现
- 系统能够把观测退化识别为 `SYNC_ERROR`，而不是误报物理故障

如果后续需要继续扩展成正式提交版，可以在这份粗稿基础上再补封面、图表编号、图注和更完整的结果表述；但就“把实验做了什么、数据依据和结论讲清楚”这个目标来说，这一版已经足够作为基础报告使用。
