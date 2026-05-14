# 1. 文档目的

本规范用于约束 Claude Code 为 TER 项目实现一个“网络数字孪生”研究型 PoC（Proof of Concept）系统。

本规范的唯一目标是指导代码代理开展可执行开发工作，而非撰写面向教师的学术报告。文档必须用于：

- 明确项目范围
- 约束实现边界
- 指定模块划分
- 定义里程碑
- 规定验收标准
- 防止代码代理擅自扩大 scope

本项目必须被严格定义为：

- TER 研究型项目
- 面向实验验证的 PoC
- 用于支撑报告写作与结果分析

本项目不得被实现为工业级、生产级、运营级网络管理平台。

# 2. 项目背景与目标

## 2.1 项目主题

项目主题为：网络数字孪生（Network Digital Twin）。

## 2.2 使用场景

本项目面向一个简化网络拓扑，通过 Mininet 模拟网络，通过 Ryu 获取网络观测状态，通过 Python 维护数字孪生状态模型，并围绕故障检测与实验结果导出开展验证。

## 2.3 项目目标

本项目的目标必须限定为以下内容：

- 状态同步
- 状态建模
- 故障检测
- 事件记录
- 实验导出
- 结果支撑 TER 报告

## 2.4 项目定位

本项目是研究型 proof of concept，不是复杂生产系统。实现应优先满足“可运行、可解释、可复现、可用于实验”四项原则，而不是追求功能堆叠、架构炫技或工业级扩展能力。

# 3. 数字孪生定义

## 3.1 本项目中的 Digital Twin 定义

本项目中的 digital twin 不是单纯的监控页面，也不是仅用于展示链路状态的可视化界面。

本项目中的 digital twin 必须同时满足以下定义要求：

- twin 必须包含结构化状态模型
- twin 必须持续从控制器或观测接口同步网络状态
- twin 必须保留历史变化记录
- twin 必须支持状态差分
- twin 必须支持故障检测
- twin 的输出必须服务实验分析与 TER 报告写作

## 3.2 最低成立条件

只有当系统满足以下条件时，才可称为本项目中的 digital twin：

1. 存在可序列化的结构化网络状态对象
2. 状态对象以固定周期持续更新
3. 更新过程包含新旧状态差分
4. 差分结果可生成结构化事件
5. 事件与状态可导出为实验分析结果

若系统仅能展示当前网络信息而不具备结构化状态、持续同步、差分、历史记录与实验导出能力，则不得称为 digital twin。

# 4. 范围定义

## 4.1 必做范围（MVP）

MVP 必须至少包含以下能力：

- 用 Mininet 搭建简化拓扑
- 使用 Open vSwitch 承载交换行为
- 用 Ryu 获取网络状态
- 用 Python 维护 twin 状态对象
- 实现周期性状态同步
- 检测链路 `down` / `up`
- 输出事件日志
- 提供基础 API 或简单页面
- 提供实验脚本
- 导出 `CSV` / `JSON` 结果
- 生成基础图表

## 4.2 扩展范围

仅在 MVP 完成且稳定后，才允许实现以下扩展：

- 5 节点欧洲骨干风格拓扑
- 节点隔离检测
- 状态快照持久化
- 更丰富的实验场景
- 更完整的图表输出
- 更友好的基础 Web 页面

## 4.3 非目标

以下内容必须明确为不做或非必须做：

- 复杂地图可视化
- L3 路由协议实现
- 多控制器
- 机器学习预测
- 工业级数据库
- 容器编排
- 运营商内部 telemetry 接入
- 大规模分布式部署
- 高可用控制平面
- 复杂权限系统
- 实时三维可视化
- 自动化根因分析平台

# 5. 技术原则与默认技术栈

## 5.1 技术原则

默认优先简单、稳定、可解释方案。

实现时必须遵守以下原则：

- 不要引入不必要依赖
- 不要为了“更先进”而增加复杂度
- 优先使用标准库和轻量依赖
- 优先保证实验可复现
- 优先保证结构清晰而不是框架复杂

## 5.2 默认技术栈

默认技术栈必须为：

```text
Mininet
Open vSwitch
Ryu
Python 3.10+
Flask
JSON / CSV
matplotlib
pytest
Git
```

除非存在明确阻塞，不得擅自替换为更重的框架或服务。

# 6. 拓扑规范

## 6.1 MVP 拓扑要求

MVP 必须先实现 3 节点最小拓扑。

该最小拓扑应满足：

- 至少包含交换节点与主机
- 所有主机先放在统一子网
- 先做 L2 连通
- 支持 `pingall`
- 支持 `iperf`
- 支持 `link up/down`
- 链路支持设置 `delay` 和 `bw`

## 6.2 扩展拓扑要求

在 MVP 稳定后，可扩展为 5 节点欧洲骨干风格拓扑，用于模拟跨城市网络骨干结构。节点名称可采用城市语义，例如：

```text
Paris
Frankfurt
Amsterdam
Milan
Madrid
```

城市命名仅用于实验可读性，不代表真实运营商网络。

## 6.3 启动要求

拓扑必须可通过单命令或单脚本启动。

建议命令形式：

```bash
python -m src.topology.minimal_topology
```

或：

```bash
bash scripts/run_demo.sh
```

不得要求用户手工逐条输入大量 Mininet 命令才能完成基本启动。

# 7. 系统架构要求

系统必须划分为以下四层，且每层职责明确。

## 7.1 Network Emulator Layer

职责：

- 定义和启动 Mininet 拓扑
- 配置 Open vSwitch
- 管理链路、主机、带宽、时延等实验参数
- 提供故障注入入口

不得承担：

- twin 状态建模
- Web 展示逻辑
- 状态差分逻辑

## 7.2 SDN Observation Layer

职责：

- 通过 Ryu REST API 获取交换机、端口、流表、链路等状态
- 对 Ryu 接口进行轻量封装
- 处理请求超时、异常与返回格式规范化

不得承担：

- 核心数字孪生状态存储
- 页面渲染
- 实验图表生成

## 7.3 Twin Core Layer

职责：

- 定义状态模型
- 执行周期性同步
- 构造 `NetworkState`
- 执行状态差分
- 生成事件
- 维护当前状态与历史记录
- 提供面向 API 层的只读访问

该层是项目核心，必须保持模块边界清晰、逻辑可测试。

## 7.4 Presentation / Export Layer

职责：

- 提供 Flask API
- 提供基础页面
- 输出事件日志
- 导出实验结果
- 生成图表

不得把前端复杂化成主任务。

# 8. 建议目录结构

Claude Code 必须给出并遵守建议项目目录。至少覆盖以下结构：

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
scripts/
```

建议进一步细化为：

```text
README.md
requirements.txt
docs/
  architecture.md
  experiments.md
  report_notes.md
src/
  topology/
    __init__.py
    minimal_topology.py
    europe5_topology.py
  controller/
    __init__.py
    ryu_api_client.py
  twin/
    __init__.py
    models.py
    sync_engine.py
    diff_engine.py
    event_engine.py
    storage.py
    config.py
  web/
    __init__.py
    app.py
    templates/
scenarios/
  single_link_failure.py
  recovery_scenario.py
  multi_fault_scenario.py
tests/
  test_models.py
  test_diff_engine.py
  test_event_engine.py
  test_ryu_client.py
  test_sync_engine.py
data/
  events/
  snapshots/
  exports/
  plots/
scripts/
  run_demo.sh
  run_experiment.sh
  plot_results.sh
```

# 9. 核心数据模型要求

必须实现以下核心数据模型：

- `NetworkState`
- `SwitchState`
- `PortState`
- `LinkState`
- `HostState`
- `EventRecord`

建议使用 `dataclass` 或等价的轻量模型方式实现。

## 9.1 `NetworkState`

关键字段至少包括：

```text
timestamp
switches
links
hosts
```

说明：

- `timestamp` 表示该快照生成时间
- `switches` 为交换机状态集合
- `links` 为链路状态集合
- `hosts` 为主机状态集合

## 9.2 `SwitchState`

关键字段至少包括：

```text
dpid
name
city
ports
flow_count
```

说明：

- `city` 可为空，但建议为扩展拓扑保留
- `ports` 应包含结构化端口列表或端口映射

## 9.3 `PortState`

关键字段至少包括：

```text
port_no
rx_packets
tx_packets
rx_bytes
tx_bytes
is_up
```

## 9.4 `LinkState`

关键字段至少包括：

```text
src_dpid
dst_dpid
src_port
dst_port
is_up
latency_ms
```

## 9.5 `HostState`

关键字段至少包括：

```text
name
ip
mac
attached_switch
attached_port
```

## 9.6 `EventRecord`

关键字段至少包括：

```text
timestamp
event_type
entity_type
entity_id
old_value
new_value
details
```

## 9.7 模型约束

必须满足以下约束：

- 所有模型可序列化为 `JSON`
- 所有核心字段命名保持稳定
- 不得将关键状态存储为不可解释的自由文本
- 事件对象必须能直接用于导出和实验分析

# 10. Ryu 接入要求

## 10.1 接入方式

必须通过 Ryu REST API 获取网络状态。

至少覆盖：

- `switches`
- `ports`
- `flows`
- `topology links`

## 10.2 客户端封装

必须实现独立的 `RyuAPIClient`。

`RyuAPIClient` 至少负责：

- HTTP 请求发送
- URL 拼接
- 超时控制
- 异常捕获
- 返回数据规范化

## 10.3 稳定性要求

必须满足以下要求：

- 所有 HTTP 请求必须有 `timeout`
- 必须有异常处理
- 单次同步失败不能导致整个服务崩溃
- Ryu API 地址必须可配置

## 10.4 接口容错要求

当某个接口拉取失败时，系统应：

1. 记录 `SYNC_ERROR`
2. 保留上一次稳定状态或返回部分状态
3. 继续后续同步周期

不得因为一次 REST 调用失败而退出整个同步循环。

# 11. 状态同步要求

## 11.1 同步方式

必须采用：

```text
polling-based synchronization
```

## 11.2 默认周期

默认轮询周期必须为 `2` 秒，且周期必须可配置。

## 11.3 单次同步流程

每次同步必须依次执行：

1. 拉取状态
2. 构造 `NetworkState`
3. 与上一状态做 `diff`
4. 生成事件
5. 更新当前状态
6. 按需写入日志或快照

## 11.4 运行约束

必须满足以下要求：

- 同步循环遇到异常不能直接退出
- 同步循环必须可启动、停止、重启
- 同步周期必须从配置读取
- 同步逻辑必须与 Web 层解耦

# 12. 状态差分与故障检测要求

## 12.1 差分机制

检测逻辑必须基于状态快照差分。

不得仅依赖 `ping` 结果作为主检测机制。

`ping` 只能作为辅助验证手段，不能替代 twin 状态判断。

## 12.2 必做检测能力

必须支持：

- 单链路故障检测
- 链路恢复检测

推荐支持：

- 节点隔离检测

## 12.3 事件类型

建议事件类型至少包括：

```text
LINK_DOWN
LINK_UP
NODE_ISOLATED
SYNC_ERROR
```

如有补充事件类型，必须保持命名稳定、含义明确。

## 12.4 差分输出要求

差分逻辑至少需要识别：

- 链路状态变化
- 端口状态变化
- 交换机出现或消失
- 主机附着关系变化

MVP 中可优先保证链路状态变化识别正确。

# 13. 日志、快照与导出要求

## 13.1 事件日志

事件日志必须保存为 `JSON Lines` 或 `JSON` 数组。

日志至少应包含结构化 `EventRecord`。

## 13.2 状态快照

状态快照可选保存，但最好支持。

若实现快照保存，建议使用：

```text
JSON
```

## 13.3 实验结果导出

实验结果必须保存为 `CSV`。

至少包括以下字段：

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

## 13.4 图表输出

必须提供基础图表生成功能，使用 `matplotlib` 即可。

建议至少支持：

- 检测延迟柱状图
- 多次实验结果折线图
- 事件时间线图

# 14. Web/API 要求

## 14.1 基础 API

必须提供基础 API，至少包括：

```text
GET /api/topology
GET /api/state
GET /api/events
GET /api/health
```

## 14.2 API 语义要求

- `GET /api/topology` 返回拓扑结构信息
- `GET /api/state` 返回当前 twin 状态
- `GET /api/events` 返回事件记录列表
- `GET /api/health` 返回服务健康状态

## 14.3 基础页面要求

必须至少有一个基础页面，用于展示：

- 节点列表
- 链路列表
- 当前状态
- 最近事件

页面可以很简单，但必须连接真实数据，而不是纯静态占位页面。

## 14.4 页面边界

不允许把前端复杂化成主任务。

以下内容不应成为 MVP 工作重点：

- 复杂前端工程化
- 高级状态管理
- 地图大屏
- 动画拓扑可视化

# 15. 真实数据接入

## 15.1 定位

真实数据接入必须写为扩展能力，而不是主依赖。

## 15.2 允许用途

真实数据只作为：

- 拓扑参考
- 参数参考
- 故障场景参考
- 报告支撑

## 15.3 禁止依赖

系统核心功能不得依赖真实数据才能运行。

即使外部 API 不可用，系统仍应正常运行最小 demo、状态同步、故障检测、日志导出与实验流程。

## 15.4 禁止目标

不得把目标写成获取运营商内部私有流量、运营商内部 telemetry 或其他不可公开获取的私有运行数据。

# 16. 实验设计要求

必须至少支持以下实验。

## 16.1 实验 1：同步延迟

要求：

- 注入单链路故障
- 记录故障注入时间
- 记录 twin 检测时间
- 计算检测延迟
- 导出 `CSV`
- 输出平均值和标准差

## 16.2 实验 2：故障恢复检测

要求：

- 将链路置为 `down`
- 检测故障
- 将链路恢复为 `up`
- 检测恢复
- 导出时间线

## 16.3 实验 3：多故障场景

要求：

- 同时或顺序注入两个故障
- 检查事件顺序
- 检查漏报与误报

## 16.4 可选实验：流量统计对比

要求：

- 使用 `iperf` 产生流量
- 对比 counters 与 `iperf` 报告

可选实验不能拖慢主线，不得阻塞 MVP 交付。

# 17. 指标定义要求

必须定义并在文档或代码中体现以下指标。

## 17.1 Detection Delay

定义：

```text
detection_timestamp - fault_injection_timestamp
```

表示故障被注入后，twin 识别到故障所需时间。

## 17.2 Recovery Detection Delay

定义：

```text
recovery_detection_timestamp - recovery_action_timestamp
```

表示恢复动作发生后，twin 识别到恢复所需时间。

## 17.3 Event Detection Accuracy

至少统计：

```text
TP
FP
FN
```

文字定义要求：

- `TP`：实际发生且被正确检测的事件数
- `FP`：未实际发生但被错误报告的事件数
- `FN`：实际发生但未被检测到的事件数

## 17.4 State Consistency Ratio

文字定义：

某观测时刻 twin 正确反映的实体数 / 总实体数

MVP 中实体可先使用：

```text
switches
links
```

# 18. 配置要求

关键参数必须可配置，至少包括：

```text
polling interval
Ryu API 地址
是否保存快照
日志路径
输出路径
Web 端口
场景等待时间
```

可建议使用：

```text
.env
yaml
json
```

必须明确禁止把关键参数散落硬编码到多个模块中。

建议集中到：

```text
src/twin/config.py
```

或等价配置模块。

# 19. 工程质量要求

生成的代码必须满足：

- 类型注解
- `docstring`
- 异常处理
- 模块职责清晰
- 避免硬编码
- 避免重复代码
- 核心逻辑可测试
- 输出可复现

必须明确：

- 不接受一次性脚本堆砌
- 不接受把核心逻辑写死在单个超长文件中
- 不接受页面、实验、同步逻辑相互耦合

# 20. 测试要求

## 20.1 单元测试

至少包括：

- 数据模型测试
- 差分逻辑测试
- 事件生成逻辑测试

## 20.2 集成测试

至少包括：

- `RyuAPIClient` 基本调用
- `sync engine` 启动
- 故障注入后事件生成

## 20.3 手动验证清单

至少包括：

- 拓扑能启动
- `pingall` 正常
- `link down` 触发事件
- `link up` 触发恢复事件
- `/api/events` 返回有效数据
- 实验结果文件生成成功

# 21. 文档要求

Claude Code 必须同时生成以下文件：

```text
README.md
docs/architecture.md
docs/experiments.md
docs/report_notes.md
```

## 21.1 `README.md` 必须至少包含

```text
项目简介
目录结构
环境要求
安装方法
启动 Ryu 方法
启动 Mininet 方法
启动 twin service 方法
访问 API / 页面方法
运行实验方法
输出文件说明
已知限制
```

README 中必须包含关键命令，建议使用代码块展示，例如：

```bash
pip install -r requirements.txt
ryu-manager ...
python ...
bash scripts/run_demo.sh
bash scripts/run_experiment.sh
bash scripts/plot_results.sh
```

## 21.2 `docs/architecture.md` 必须至少包含

```text
系统分层架构
模块职责
数据流
同步流程
差分与事件生成流程
```

## 21.3 `docs/experiments.md` 必须至少包含

```text
实验目标
实验场景
实验步骤
实验输入输出
指标计算方法
结果解读方法
```

## 21.4 `docs/report_notes.md` 必须至少包含

```text
可直接支撑 TER 报告的观察点
图表说明建议
指标解释
已知限制如何表述
PoC 定位说明
```

# 22. 交付物要求

最终交付必须包括：

- 完整项目代码
- 可运行 demo
- 实验脚本
- 数据导出文件
- 图表生成脚本
- `README.md`
- `docs/architecture.md`
- `docs/experiments.md`
- 已知限制说明

交付物必须能直接支撑 TER 报告撰写和演示。

# 23. 里程碑要求

必须按顺序完成以下里程碑。每个里程碑都必须写明目标、输出、验证方法、验收标准。

## 23.1 Milestone 1

### 目标

- 最小拓扑启动
- Ryu 连接
- `pingall` 成功

### 输出

- 最小拓扑脚本
- 启动命令
- 基础连通验证结果

### 验证方法

```bash
sudo mn 或等价脚本启动
pingall
Ryu REST 可访问
```

### 验收标准

- 能单命令启动最小拓扑
- 主机之间可互通
- Ryu 能看到交换机

## 23.2 Milestone 2

### 目标

- twin 状态建模
- 拉取 Ryu 状态
- 输出当前状态

### 输出

- `NetworkState` 及相关模型
- `RyuAPIClient`
- 状态拉取与打印或导出功能

### 验证方法

- 运行一次同步
- 查看结构化状态输出

### 验收标准

- 状态对象包含交换机、链路、主机信息
- 同步过程可在无崩溃情况下完成

## 23.3 Milestone 3

### 目标

- 状态差分
- 链路 `down/up` 事件
- 事件日志保存

### 输出

- 差分逻辑
- 事件生成逻辑
- 事件日志文件

### 验证方法

- 注入单链路故障
- 观察事件输出
- 恢复链路并再次观察

### 验收标准

- 至少能正确产生 `LINK_DOWN`
- 至少能正确产生 `LINK_UP`
- 事件被写入日志

## 23.4 Milestone 4

### 目标

- Flask API
- 基础页面

### 输出

- API 服务
- 基础 HTML 页面

### 验证方法

- 访问 `/api/state`
- 访问 `/api/events`
- 打开页面查看真实数据

### 验收标准

- API 返回有效 JSON
- 页面展示节点、链路、状态、最近事件

## 23.5 Milestone 5

### 目标

- 实验脚本
- `CSV` 导出
- 绘图脚本

### 输出

- 实验场景脚本
- `CSV` 结果文件
- `matplotlib` 图表脚本

### 验证方法

- 运行实验脚本
- 检查导出文件
- 运行绘图脚本

### 验收标准

- 至少一组实验结果成功导出
- 图表成功生成

## 23.6 Milestone 6

### 目标

- `README.md`
- `architecture.md`
- `experiments.md`
- 代码清理

### 输出

- 文档集
- 清理后的项目结构

### 验证方法

- 按 README 重跑项目
- 检查文档与代码一致性

### 验收标准

- 文档可指导他人复现
- 代码结构与规范一致
- 已知限制清楚列出

# 24. 严格验收标准

项目最终必须满足以下严格验收标准：

- 项目可按 `README.md` 复现
- 能运行最小拓扑
- 能通过 Ryu 获取状态
- twin 能周期同步
- 能检测至少一种链路故障
- 能输出事件日志
- 能导出实验数据
- 有基础 API 或页面
- 至少有三个可运行脚本

三个脚本至少为：

```text
启动 demo
运行实验
绘制结果图
```

若上述任一项缺失，则不得判定为完成。

# 25. 已知限制要求

必须单独写出已知限制，至少包括：

- 本项目是 PoC，不是生产系统
- 检测延迟受 polling interval 限制
- 控制器视图不等于完整物理真值
- 真实数据只是参考和场景支撑
- 不保证复杂拓扑和高并发下的实时性

可补充但不得淡化以上限制。

# 26. 对 Claude Code 的执行约束

Claude Code 在执行本规范时，必须遵守以下约束：

- 先做 MVP，再做扩展
- 先保证可运行，再考虑美化
- 不得私自扩大范围
- 不得引入不必要框架
- 遇到不确定实现时优先选择简单方案
- 所有关键命令必须写进 `README.md`
- 所有实验步骤必须可复现
- 文档与代码结构必须一致
- 扩展功能不稳定时必须降级
- 所有输出必须服务于 TER 报告写作

若出现“功能更先进但影响稳定性或复现性”的冲突，必须优先选择稳定、简单、可复现方案。

# 27. 输出约束

Claude Code 在生成本 spec 文档时，必须满足以下输出约束：

- 使用规范的 Markdown 标题层级
- 使用清晰的小节编号
- 对目录结构、命令、字段名使用 Markdown 代码块
- 不要写空泛描述
- 所有要求尽量具体
- 文风必须像正式技术规范，而不是聊天回复

本规范文档应能直接驱动后续代码实现，不允许停留在泛化描述层面。
