# 基于真实拓扑子网的网络数字孪生原型设计与实验验证

## 摘要

本项目实现并验证了一个面向计算机网络场景的数字孪生原型系统。系统以 Ryu 控制器和 Mininet 仿真网络为基础，通过持续采集控制平面的拓扑、端口和流表信息，在孪生侧构建结构化网络状态，并进一步完成状态差分、事件生成、实验导出、可视化展示以及鲁棒性分析。与仅基于简单线形拓扑的演示型实验不同，本项目将实验拓扑扩展为数据驱动的欧洲骨干网子图，构建了一个包含 8 个欧洲核心城市和 10 条主干链路的可运行骨干模型，并进一步引入真实 `Geant2012` 原始拓扑文件，生成了 12 节点中等规模子图用于扩展比较。

在实验部分，本文围绕“数字孪生能否及时、稳定、可解释地反映物理网络中的拓扑变化”这一核心问题展开。我们设计了链路故障、链路恢复、链路 flap、多故障、观测退化、不同背景流量、不同轮询周期、不同控制器策略以及不同同步模式等多类实验，并输出 CSV、JSON、summary、manifest 和图表等结构化结果。实验结果表明，数字孪生能够在真实感更强的数据驱动骨干拓扑上稳定检测链路状态变化；背景流量会显著影响检测时延；较长轮询周期会明显增大恢复时延；观测退化场景能够触发 `SYNC_ERROR` 而不会误报链路下线；在同步模式对比中，`event_driven` 和 `hybrid` 均能在真实 VM 环境中稳定运行，且恢复时延优于纯轮询模式。

总体来看，本项目完成了一个从最小可运行 PoC 到较完整实验原型的升级过程，不仅满足课程项目对数字孪生概念验证、实验设计和结果分析的要求，还在真实性、可扩展性和工程完整性上超出了基础要求。

## 1. 引言

数字孪生（Digital Twin）是一种在虚拟空间中构建实体系统实时映射模型的方法。在工业控制、制造、交通和网络运维等领域，数字孪生都被用于实现对物理系统状态的观测、分析、预测和辅助决策。对于网络系统而言，数字孪生的核心价值在于：它能够持续同步控制平面的网络状态，并将网络中真实发生的拓扑变化、故障事件和运行异常，以结构化、可查询、可视化的方式反映出来。

本项目的目标是实现一个网络数字孪生原型，并验证其是否能够：

1. 及时检测网络中发生的拓扑变化；
2. 正确反映链路故障与恢复；
3. 在观测退化或接口异常时避免产生误报；
4. 在不同流量负载、不同拓扑规模和不同同步/控制策略下保持稳定工作。

与仅在极简网络上做功能演示不同，本项目在后期进一步引入了数据驱动拓扑、真实欧洲骨干网语义、原始拓扑导入、扩展实验矩阵和同步模式对比，使系统具备了更强的实验说服力。

## 2. 项目目标与研究问题

### 2.1 总体目标

本项目的总体目标是构建一个可运行的网络数字孪生原型，并通过实验验证该原型是否能够及时、稳定、可解释地反映物理网络中的状态变化。

### 2.2 具体研究问题

围绕上述目标，本文关注以下问题：

1. 当物理网络中发生链路故障或恢复时，数字孪生是否能够正确检测并生成对应事件？
2. 数字孪生检测故障与恢复的时延分别是多少？
3. 背景流量是否会影响数字孪生的检测与恢复时延？
4. 不同轮询周期是否会影响孪生网络的同步性能？
5. 在控制器观测退化时，孪生网络是否会误报链路故障？
6. 不同控制策略和不同同步模式是否会显著改变孪生系统的时延表现？

## 3. 系统设计与实现

### 3.1 系统总体结构

系统总体上由四个部分组成：

1. 物理/仿真网络层  
   采用 Mininet + OVS 构建实验拓扑，由 Ryu 控制器负责基础控制逻辑。

2. 状态采集层  
   通过 Ryu REST API 获取交换机、链路、主机、端口统计和流表信息。

3. 孪生同步与事件层  
   对采集到的观测数据构建 `NetworkState`，与上一轮状态做差分，并生成结构化事件。

4. 展示与实验层  
   提供 Web API、拓扑可视化页面、实验运行器、统计导出和图表生成。

### 3.2 关键实现模块

项目的核心实现包括以下模块：

- `src/controller/ryu_api_client.py`  
  负责调用 Ryu REST API，并对 DPID、端口号和失败场景做兼容处理。

- `src/twin/sync_engine.py`  
  负责轮询模式下的状态同步、状态构建、差分和事件生成。

- `src/twin/event_sync_engine.py`  
  负责事件驱动/混合同步模式，根据控制器事件触发同步。

- `src/twin/diff_engine.py`  
  对网络状态进行差分，除了链路上下线，还支持交换机上线/下线、主机加入/离开/迁移等扩展事件。

- `src/twin/event_engine.py`  
  将状态差分转化为结构化事件记录。

- `src/twin/fidelity.py`  
  计算孪生状态与控制器真实观测之间的一致性指标。

- `src/twin/anomaly_detector.py`  
  进行基于计数器变化的流量异常检测。

- `src/web/app.py` 与 `src/web/templates/topology.html`  
  提供 Web API 和拓扑可视化页面。

### 3.3 同步模式

为增强系统能力，项目最终支持三种同步模式：

1. `polling`  
   周期性轮询控制器 REST API。

2. `event_driven`  
   依赖控制器事件驱动同步，在检测到控制器事件后再采集一次完整状态。

3. `hybrid`  
   结合事件驱动与轮询回退，在保留事件响应性的同时保证长时间无事件时仍能刷新状态。

### 3.4 保真度与异常检测

升级版系统还引入了两个增强模块：

- Fidelity：用于衡量当前孪生视图与控制器真实视图之间的匹配程度；
- Anomaly Detection：用于根据端口流量计数变化检测异常突增或突降。

这使得系统不再只是一个“拓扑事件记录器”，而逐步具备了“运行态镜像”的能力。

## 4. 拓扑建模与数据来源

### 4.1 从手写最小拓扑到数据驱动拓扑

项目最初仅使用简单的 3 交换机线形网络进行原型验证。为提高实验真实性，后续完成了数据驱动拓扑建模，将拓扑定义从硬编码迁移到外部 JSON 文件。

### 4.2 主实验拓扑：8 城市欧洲骨干子网

最终主实验基线采用 `geant_backbone_8cities_stage3`，它包含以下 8 个城市节点：

- London
- Paris
- Amsterdam
- Frankfurt
- Prague
- Vienna
- Milan
- Madrid

该拓扑共建模 10 条主干链路，代表一个带有环路结构的欧洲骨干子网。与最早的 toy topology 相比，这一拓扑在地理语义、链路结构和实验解释性上都更强，同时又能在当前 VM 环境中稳定运行。

### 4.3 原始研究数据导入

在主实验拓扑之外，项目还实现了原始拓扑导入能力：

- 支持 GraphML 导入；
- 支持 GML 导入；
- 能够从原始研究拓扑生成内部 JSON 格式；
- 基于 `Geant2012.graphml` 生成了 `geant2012_core12` 12 节点中等规模子图。

这部分工作提高了数据来源的可追溯性，也为后续跨拓扑对比提供了基础。

## 5. 实验设计

### 5.1 主实验基线

根据最终基线定义，主实验采用以下默认配置：

- 拓扑：`geant_backbone_8cities_stage3`
- 控制器：`src.controller.topology_aware_switch`
- 默认轮询周期：`2.0s`
- 主场景：
  - `recovery_scenario`
  - `link_flap_scenario`
  - `multi_fault_scenario`

主结果集为：

- `traffic_profile_full_matrix`

主鲁棒性结果为：

- `observation_degradation_stage3`

### 5.2 实验指标

本文主要关注以下指标：

1. Detection Delay  
   从故障注入到孪生产生对应检测事件的时延。

2. Recovery Delay  
   从链路恢复到孪生产生恢复事件的时延。

3. Fidelity  
   孪生状态与控制器真实观测的一致程度。

4. Sync Duration  
   单次同步处理耗时。

5. API Call Count  
   单次同步过程中调用控制器 API 的次数。

### 5.3 实验场景

本文主要使用以下实验场景：

1. `single_link_failure`  
   用于验证基本故障检测能力。

2. `recovery_scenario`  
   用于验证链路故障与恢复的完整过程。

3. `link_flap_scenario`  
   用于验证短时间 down/up/down 抖动场景。

4. `multi_fault_scenario`  
   用于验证多事件顺序和更复杂故障链。

5. `observation_degradation_scenario`  
   用于验证控制器观测退化时系统是否仅记录 `SYNC_ERROR`，而不误报 `LINK_DOWN`。

### 5.4 流量配置

为了研究负载对孪生系统的影响，本文在主实验中使用了三种背景流量配置：

- `none`
- `icmp`
- `iperf_tcp`

其中：

- `icmp` 表示持续的探测流量；
- `iperf_tcp` 表示更接近高负载运行条件的持续 TCP 流量。

### 5.5 扩展比较实验

除主实验外，还进行了以下扩展实验：

- 跨拓扑对比：`geant_backbone_8cities_stage3` vs `geant2012_core12`
- polling interval 对比：`1s / 2s / 4s`
- 控制器对比：`topology_aware_switch` vs `tree_routing_switch`
- 同步模式对比：`polling` vs `event_driven` vs `hybrid`

## 6. 实验结果

### 6.1 主实验结果：不同背景流量下的故障检测与恢复

主结果来自 `traffic_profile_full_matrix_summary.csv` 与 `traffic_profile_full_matrix_summary.png`。

在 `recovery_scenario` 中，三种背景流量下的结果如下：

- `none`：detection `0.448443s`，recovery `2.032022s`
- `iperf_tcp`：detection `0.752905s`，recovery `1.858643s`
- `icmp`：detection `1.567610s`，recovery `1.624801s`

在 `link_flap_scenario_down_1` 中：

- `none`：`0.477773s`
- `iperf_tcp`：`0.684838s`
- `icmp`：`1.561406s`

在 `multi_fault_scenario_fault_1` 中：

- `none`：`0.233982s`
- `iperf_tcp`：`0.917180s`
- `icmp`：`1.381603s`

这些结果说明，在主场景的第一阶段故障检测中：

- 无背景流量时延最短；
- `iperf_tcp` 会使检测时延上升；
- `icmp` 造成的检测时延提升最明显。

### 6.2 高负载与计数器变化

高负载实验进一步表明，`iperf_tcp` 不只是“有流量”这一抽象状态，而是真正改变了目标链路的计数器水平。  
在 `recovery_scenario + iperf_tcp` 的 VM 验证中，目标链路字节计数从：

- 故障前：`34500`
- 检测后：`19679780`
- 恢复后：`56426416`

这说明高负载背景流量确实改变了网络运行状态，也进一步说明孪生系统导出的 counters 能用于辅助分析。

### 6.3 鲁棒性结果：观测退化不会误报链路故障

在 `observation_degradation_scenario` 中，系统通过注入 `/v1.0/topology/links` 观测失败，验证了以下行为：

- 系统能够记录 `SYNC_ERROR`；
- 系统不会错误地产生目标链路的 `LINK_DOWN`。

在 VM 上的验证结果中，`notes` 明确记录：

- 预期出现一次 `SYNC_ERROR`
- 观测结果 `Observed link_down=False`

这说明修复后的同步逻辑已经能够区分“控制器观测失败”和“物理链路真实故障”。

### 6.4 轮询周期敏感性结果

在 `polling_full_matrix` 中，最稳定的信号出现在 `recovery_scenario` 的恢复时延上。

无背景流量时：

- `1s`：`0.993098s`
- `2s`：`1.977366s`
- `4s`：`3.983571s`

`icmp` 背景流量下：

- `1s`：`0.919655s`
- `2s`：`1.622013s`
- `4s`：`3.851688s`

可见，恢复时延随着 polling interval 增大而明显上升，这是整个对比中最稳定、最强的量化趋势。

### 6.5 跨拓扑结果

在跨拓扑对比中，`geant2012_core12` 整体时延通常高于 8 城市骨干主拓扑。例如在 `recovery_scenario` 中：

- `geant_backbone_8cities_stage3 / none`：detection `0.545329s`
- `geant2012_core12 / none`：detection `0.893741s`

这说明拓扑规模与结构复杂度会影响孪生系统的检测性能。

### 6.6 控制器对比结果

在控制平面对比中，`topology_aware_switch` 与 `tree_routing_switch` 均可在完整骨干拓扑上稳定运行，但表现并不完全一致。

以 `recovery_scenario` 的 `repeat=3` 结果为例：

- `topology_aware_switch / none`：detection `0.4663s`
- `tree_routing_switch / none`：detection `2.0445s`

而在 `icmp` 背景流量下：

- `topology_aware_switch / icmp`：detection `1.5695s`
- `tree_routing_switch / icmp`：detection `1.0098s`

这表明控制策略会影响孪生系统的时延特征，而且这种影响会随流量条件变化。

### 6.7 同步模式对比结果

在升级版 `sync_mode_comparison` 中，我们比较了：

- `polling`
- `event_driven`
- `hybrid`

正式结果表明，三种模式都已能在 VM 中运行，且导出包含 `sync_mode`、`sync_duration_ms`、`fidelity` 和 `api_call_count`。

在最新正式结果中：

- `polling / single_link_failure`：`api_call_count = 28`
- `event_driven / single_link_failure`：`api_call_count = 28`
- `hybrid / single_link_failure`：`api_call_count = 28`

从同步处理耗时上看：

- `polling`：约 `60ms`
- `event_driven`：约 `1.7-2.0ms`
- `hybrid`：约 `1.7ms`

这说明事件驱动与混合同步在运行时同步开销上明显低于纯轮询模式。

## 7. 讨论

### 7.1 与课程项目需求的契合度

从课程项目要求来看，本项目已经完整满足并超出基础 TER 需求：

- 完成了一个可运行的网络数字孪生 PoC；
- 在可解释的实验环境中完成了故障检测与恢复验证；
- 引入了更接近真实网络的拓扑和数据来源；
- 建立了结构化实验输出和对比分析链路。

### 7.2 项目优势

本项目的主要优势在于：

1. 不停留在最小 toy demo，而是逐步升级到真实语义更强的数据驱动骨干拓扑；
2. 实验链闭环完整，包含原始结果、summary、manifest 和图表；
3. 对鲁棒性、拓扑规模、轮询周期、控制器策略和同步模式都进行了系统性扩展；
4. 工程实现较完整，包括 API、前端、fidelity、anomaly detection 等增强模块。

### 7.3 局限性

尽管项目整体已闭环，但仍存在一些局限：

1. 主实验拓扑仍然是“真实语义子图”，而非完整运营级网络；
2. 高负载场景主要采用 `iperf_tcp` 近似模拟，尚未引入真实业务需求矩阵；
3. 实验依然基于 Mininet + Ryu 仿真环境，不能完全替代真实运营网络环境；
4. 某些对比实验目前采用较小重复次数，后续如需更强统计结论，可继续增加重复轮次。

## 8. 结论

本文实现并验证了一个面向网络场景的数字孪生原型系统。系统能够从控制器持续采集网络观测数据，在孪生侧构建结构化状态，并通过差分机制生成拓扑变化事件。相比最初的简化实验，本项目进一步完成了数据驱动拓扑建模、真实研究拓扑导入、背景流量实验、轮询敏感性分析、跨拓扑对比、控制器对比和同步模式对比，使得实验体系更加完整、真实和可解释。

实验结果表明：

1. 数字孪生能够在数据驱动骨干子网上稳定检测链路故障与恢复；
2. 背景流量会显著影响故障检测时延；
3. 较长的 polling interval 会明显拉长恢复时延；
4. 观测退化会触发 `SYNC_ERROR`，但不会误报链路下线；
5. 控制器策略和同步模式都会改变孪生系统的时延表现。

总体而言，本项目已经完成了一个具有较强工程完整性和实验说服力的网络数字孪生原型，为后续进一步研究更大规模拓扑、更真实业务流量和更复杂控制策略打下了基础。

## 9. 最终使用的核心结果文件

正文建议优先引用以下结果：

- 主结果图：`/home/yumeng/twin/data/plots/traffic_profile_full_matrix_summary.png`
- 主结果表：`/home/yumeng/twin/data/exports/traffic_profile_full_matrix_summary.csv`
- 鲁棒性结果：`/home/yumeng/twin/data/exports/observation_degradation_stage3_summary.csv`

附录建议引用：

- 跨拓扑对比：`/home/yumeng/twin/data/exports/p34_full_matrix_summary.csv`
- polling 对比：`/home/yumeng/twin/data/exports/polling_full_matrix_summary.csv`
- 控制器对比：`/home/yumeng/twin/data/exports/controller_compare_summary.csv`
- 同步模式对比：`/home/yumeng/twin/data/exports/sync_mode_comparison_summary.csv`

## 10. 可继续补充的内容

如果后续需要提交正式 PDF 或 LaTeX 版本，可以在本草稿基础上继续补充：

- 封面、作者、课程和日期信息；
- 图编号、表编号和交叉引用；
- 参考文献格式；
- 更严格的统计表述；
- 英文摘要。
