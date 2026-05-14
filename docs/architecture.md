# Architecture

## 1. 系统分层架构

系统按 SPEC 划分为 4 层：

```text
Network Emulator Layer
  Mininet + Open vSwitch

SDN Observation Layer
  Ryu REST API + RyuAPIClient

Twin Core Layer
  models / sync_engine / diff_engine / event_engine / storage / service

Presentation / Export Layer
  Flask API / HTML 页面 / CSV 导出 / matplotlib 绘图
```

## 2. 模块职责

### 2.1 Network Emulator Layer

- `src/topology/minimal_topology.py`
- 定义 3 交换机线形拓扑与 3 台主机
- 负责链路带宽、时延、`pingall` 和链路注入运行基础

### 2.2 SDN Observation Layer

- `src/controller/ryu_probe.py`
- `src/controller/ryu_api_client.py`
- 负责 Ryu REST 探测、超时控制、异常捕获与响应规范化

### 2.3 Twin Core Layer

- `src/twin/models.py`
- `src/twin/sync_engine.py`
- `src/twin/diff_engine.py`
- `src/twin/event_engine.py`
- `src/twin/storage.py`
- `src/twin/service.py`

职责：

- 构造 `NetworkState`
- 周期同步
- 快照差分
- 事件生成
- 状态与事件持久化

### 2.4 Presentation / Export Layer

- `src/web/app.py`
- `src/web/templates/index.html`
- `src/twin/experiment_runner.py`
- `src/twin/plotting.py`

职责：

- 提供 `/api/topology`
- 提供 `/api/state`
- 提供 `/api/events`
- 提供 `/api/health`
- 导出 `CSV` / `JSON`
- 生成基础 PNG 图表

## 3. 数据流

```text
Mininet / OVS
  -> Ryu
  -> Ryu REST API
  -> RyuAPIClient
  -> SyncEngine
  -> NetworkState
  -> DiffEngine
  -> EventEngine
  -> JSONL / JSON / CSV / Flask API / HTML
```

## 4. 同步流程

单次同步流程如下：

```text
1. RyuAPIClient 拉取 switches / links / hosts / port stats / flows
2. SyncEngine 构造 NetworkState
3. DiffEngine 与上一状态比较
4. EventEngine 生成 LINK_DOWN / LINK_UP / SYNC_ERROR
5. Storage 写入 current_state.json 与 events.jsonl
6. Flask / 实验模块读取最新状态与事件
```

## 5. 差分与事件生成流程

### 5.1 差分重点

MVP 中优先保证链路状态变化识别：

- 链路存在且 `is_up=True` -> 正常
- 链路在新观测中消失 -> 标记为 `is_up=False`
- 链路重新出现 -> 标记为 `is_up=True`

### 5.2 事件生成规则

```text
True  -> False : LINK_DOWN
False -> True  : LINK_UP
API 拉取失败     : SYNC_ERROR
```

## 6. 设计取舍

- 不引入数据库，使用 JSON/JSONL 以保证可解释性和复现性。
- 不引入复杂消息队列，使用 polling 直接驱动 twin 更新。
- 页面保持基础展示，避免前端工程化挤占核心实验工作。
