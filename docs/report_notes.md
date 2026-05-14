# Report Notes

## 1. 可直接支撑 TER 报告的观察点

- twin 具备结构化状态对象，而不是只有监控页面。
- 状态通过固定 polling 周期同步，满足 digital twin 的最小成立条件。
- 故障检测基于状态差分，而不是只依赖 `ping`。
- 系统能够输出 `LINK_DOWN`、`LINK_UP`、`SYNC_ERROR` 等结构化事件。
- 事件、快照、CSV 和图表可以直接复用于 TER 报告附图与实验章节。

## 2. 图表说明建议

- `detection_delay.png` 可以用于展示不同场景下 twin 的检测延迟。
- 柱状部分用于对比不同实验的 `detection_delay`。
- 折线部分用于展示存在恢复动作时的 `recovery_delay`。
- 图表标题建议直接写成 “Twin Detection and Recovery Delays” 或等价中文标题。

## 3. 指标解释

- `Detection Delay`：故障注入后 twin 检测到 `LINK_DOWN` 所需时间。
- `Recovery Detection Delay`：链路恢复后 twin 检测到 `LINK_UP` 所需时间。
- `TP / FP / FN`：当前代码尚未做自动统计，但事件日志已具备后续统计基础。
- `State Consistency Ratio`：当前可先围绕交换机与链路做人工或脚本化统计。

## 4. 已知限制如何表述

- 本项目是面向 TER 的研究型 PoC，不是生产级运维平台。
- 检测时延受到 polling interval 限制，因此无法保证亚秒级反应。
- twin 依赖控制器视图，控制器视图不等于完整物理真值。
- 实验拓扑是简化拓扑，用于验证方法可行性，而不是复现真实运营商全网。
- 在复杂拓扑、高并发或异常控制面条件下，不保证实时性与完备性。

## 5. PoC 定位说明

- 重点不是构建工业级平台，而是验证“状态同步 + 状态差分 + 事件生成 + 实验导出”这条研究链路是可运行的。
- 当前系统已经覆盖最小拓扑、控制器观测、链路故障检测、事件日志、CSV 导出和图表生成。
- 这使系统可以直接支撑 TER 报告中的系统设计、实验方法、结果分析与局限性讨论。
