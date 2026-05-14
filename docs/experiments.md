# Experiments

## 1. 实验目标

本项目的实验目标是验证：

- twin 是否能通过 polling 检测链路故障
- twin 是否能检测链路恢复
- 在多故障场景下是否能维持事件顺序与基础可解释性

## 2. 实验场景

### 2.1 实验 1：同步延迟

- 场景：`single_link_failure`
- 动作：将 `s1-s2` 链路置为 `down`
- 观察：记录故障注入时间与 `LINK_DOWN` 事件时间

### 2.2 实验 2：故障恢复检测

- 场景：`recovery_scenario`
- 动作：先 `down` 再 `up`
- 观察：记录 `LINK_DOWN` 与 `LINK_UP` 对应时间

### 2.3 实验 3：多故障场景

- 场景：`multi_fault_scenario`
- 动作：顺序注入 `s1-s2 down` 与 `s2-s3 down`
- 观察：检查两次 `LINK_DOWN` 事件顺序和漏报情况

## 3. 实验步骤

```text
1. 启动 Ryu
2. 启动实验脚本
3. 脚本自动启动最小拓扑
4. 脚本执行 pingAll 作为基础连通检查
5. 脚本执行链路故障注入
6. twin 轮询检测并生成事件
7. 导出 CSV / JSON
8. 运行 plot_results.sh 生成图表
```

## 4. 实验输入输出

### 4.1 输入

- Ryu REST 地址
- polling interval
- 场景名
- 最小拓扑默认链路 `s1-s2` / `s2-s3`

### 4.2 输出

CSV 字段：

```text
scenario_name
fault_injection_timestamp
detection_timestamp
recovery_timestamp
detection_delay
recovery_delay
poll_interval
notes
```

输出目录：

```text
data/exports/
data/plots/
data/events/
```

## 5. 指标计算方法

### 5.1 Detection Delay

```text
detection_timestamp - fault_injection_timestamp
```

### 5.2 Recovery Detection Delay

```text
recovery_timestamp - recovery_action_timestamp
```

说明：

- `recovery_action_timestamp` 在脚本内记录为链路恢复动作触发时刻
- 若超时未检测到事件，则对应 delay 为空值

## 6. 结果解读方法

- 若 `detection_delay` 接近 polling interval，说明 twin 按预期工作。
- 若 delay 明显大于 polling interval，应检查 Ryu 收敛时间或实验机负载。
- 若多故障场景事件顺序与注入顺序一致，可作为 TER 报告中的“事件顺序稳定性”观察点。
- 若出现空值，表示该实验发生漏检或超时，需要在报告中归入 PoC 局限。
