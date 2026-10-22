# RTL 模块设计与复盘

> 模块名称：`<module_name>`
>
> 版本：`<version>`
>
> 作者：`<owner>`
>
> 最近更新：`<YYYY-MM-DD>`
> 当前状态：`Draft / Review / Ready / Deprecated`

## 1. 模块概述

### 1.1 功能说明

- 模块解决什么问题？
- 输入事务经过该模块后产生什么结果？
- 它在系统中的上游、下游和边界分别是什么？

### 1.2 应用场景

- 典型使用位置：`<DMA / AXI / PCIe / CXL / 通用控制路径>`
- 适用条件：`<时钟、带宽、协议或资源约束>`
- 不适用场景：`<明确列出复用边界>`

### 1.3 设计目标与非目标

| 类型 | 内容 | 验收标准 |
| --- | --- | --- |
| 功能目标 | `<必须实现的行为>` | `<可检查的结果>` |
| 性能目标 | `<吞吐率、延迟或频率目标>` | `<量化指标>` |
| 可靠性目标 | `<错误检测、恢复或保护>` | `<断言或测试结果>` |
| 非目标 | `<本版本明确不支持的能力>` | `不应被调用者假设` |

## 2. 接口定义

### 2.1 时钟与复位

| 信号 | 类型 | 有效方式 | 说明 |
| --- | --- | --- | --- |
| `<clk>` | Clock | `<posedge/negedge>` | `<频率或时钟域>` |
| `<rst_n>` | Reset | `<同步/异步，低有效>` | `<复位与释放要求>` |

记录复位后各状态寄存器、输出 valid、计数器和缓存的初始值。

### 2.2 端口定义

| 端口 | 方向 | 位宽 | 协议/时序 | 说明 |
| --- | --- | --- | --- | --- |
| `<signal>` | `input/output` | `<N>` | `<ready-valid / pulse / level>` | `<语义>` |

### 2.3 握手与稳定性约束

- 真实事务接受条件：`fire = valid && ready`。
- backpressure 期间哪些 payload 必须保持稳定？
- valid、ready、credit、request、response 之间是否存在组合依赖？
- 是否允许同周期接收与发送、push 与 pop、allocate 与 release？
- 请求、数据和响应是否可能独立到达？如何重新配对？

## 3. 架构设计

### 3.1 模块框图

```text
Upstream -> Input Buffer -> Control / Scheduler -> Datapath -> Output Buffer -> Downstream
                             |                    |
                             +-> Status/Error ----+
```

使用实际模块名称替换框图，并标出寄存切分点、队列、跨时钟边界和反馈路径。

### 3.2 数据通路

- 数据宽度与格式转换：`<输入格式 -> 内部格式 -> 输出格式>`
- buffer 深度、旁路条件和数据保持策略。
- burst、packet、descriptor 或 flit 的拆分与合并规则。
- 首拍、中间拍、末拍和单拍事务分别如何处理？

### 3.3 控制通路与状态机

| 状态 | 进入条件 | 状态行为 | 退出条件 | 异常处理 |
| --- | --- | --- | --- | --- |
| `<IDLE>` | `<condition>` | `<actions>` | `<condition>` | `<recovery>` |

记录每个状态寄存器由哪个真实事件推进，避免只根据 `valid` 或请求电平更新状态。

### 3.4 关键不变量

- 数据不丢失、不重复、不乱序的条件。
- 计数器、指针、credit 和 outstanding 的合法范围。
- grant、select、valid 等 one-hot/one-hot0 要求。
- 命令、数据、响应之间必须保持的对应关系。

## 4. 关键 RTL 实现

### 4.1 核心逻辑

```systemverilog
// 只保留最能表达设计意图的核心片段，并说明它对应的协议规则。
wire fire = valid && ready;
```

### 4.2 参数化设计

| 参数 | 默认值 | 合法范围 | 对位宽/容量/时序的影响 |
| --- | --- | --- | --- |
| `<PARAM>` | `<value>` | `<constraint>` | `<impact>` |

记录 `$clog2`、非 2 的幂深度、零宽度、最大值以及参数组合限制。

### 4.3 边界与异常处理

- FIFO empty/full、almost-full、同周期 push/pop。
- counter overflow/underflow、credit 耗尽与归还。
- burst 边界、地址对齐、最大长度和 4 KB 边界。
- timeout、abort、错误响应和复位中断事务。
- 输入非法或协议违例时，模块是阻止、丢弃、报错还是继续？

### 4.4 实现取舍

| 方案 | 优点 | 缺点 | 采用/放弃原因 |
| --- | --- | --- | --- |
| `<方案 A>` | `<...>` | `<...>` | `<...>` |

## 5. 时序与性能

### 5.1 性能模型

| 指标 | 目标 | 当前结果 | 测量条件 |
| --- | --- | --- | --- |
| 吞吐率 | `<transactions/cycle 或 bytes/cycle>` | `<...>` | `<持续流/无反压>` |
| 首事务延迟 | `<cycles>` | `<...>` | `<输入 fire 到输出 fire>` |
| 稳态延迟 | `<cycles>` | `<...>` | `<pipeline 条件>` |
| 最大 outstanding | `<count>` | `<...>` | `<参数/资源限制>` |

明确区分接口每周期打包能力、AXI outstanding 数量和端到端有效吞吐率。

### 5.2 关键路径

- 预计关键组合路径：`<ready 链 / priority encode / compare / address calculation>`
- 是否存在 ready-valid 组合环路？
- 哪些位置可以增加寄存切片或 skid buffer？
- 参数增大时，扇出、比较树和 mux 深度如何变化？

### 5.3 面积与功耗权衡

- FF、RAM、FIFO、CAM、计数器和比较器的主要资源来源。
- clock enable、数据门控和无效翻转控制。
- 为更高频率增加寄存器后，对面积和延迟的影响。

## 6. 验证方案

### 6.1 基础测试

- 复位进入、复位释放及复位过程中存在事务。
- 单事务、连续事务、间歇事务。
- 上游连续 valid、下游连续 backpressure。
- 最小参数、默认参数和最大目标参数。

### 6.2 边界与并发场景

- 空/满边界与同周期增减事件。
- 单拍、首拍、中间拍、末拍和跨边界事务。
- 多请求竞争、响应乱序或独立通道停顿。
- timeout、abort、错误注入和恢复路径。

### 6.3 断言

```systemverilog
// 示例：反压期间 payload 必须稳定
assert property (@(posedge clk) disable iff (!rst_n)
    valid && !ready |=> valid && $stable(payload));
```

建议覆盖：状态合法、计数范围、one-hot、请求最终完成、无丢失/重复、握手时序和复位行为。

### 6.4 覆盖与结果

| 项目 | 方法 | 通过标准 | 结果/报告 |
| --- | --- | --- | --- |
| 语法/Lint | `<tool/command>` | `0 error` | `<link/path>` |
| 仿真 | `<testbench>` | `<cases passed>` | `<link/path>` |
| 断言 | `<SVA/formal>` | `<properties passed>` | `<link/path>` |
| 综合 | `<target/library>` | `<timing/area goal>` | `<link/path>` |

## 7. 设计经验与复盘

### 7.1 问题记录

| 现象 | 根因 | 修复方法 | 验证证据 | 可复用经验 |
| --- | --- | --- | --- | --- |
| `<symptom>` | `<root cause>` | `<fix>` | `<test/assertion>` | `<pattern>` |

### 7.2 容易出错的地方

- `<协议理解偏差>`
- `<同周期事件优先级>`
- `<位宽、符号扩展或边界计算>`
- `<CDC、复位释放或时序假设>`

### 7.3 后续改进

- 当前实现仍有哪些限制？
- 哪些优化需要新的接口契约或性能目标？
- 哪些经验应沉淀为设计模式、问题索引或独立基础组件？

### 7.4 复用结论

| 项目 | 结论 |
| --- | --- |
| 复用状态 | `Ready / Constrained / Needs Fix / Experimental` |
| 使用前提 | `<参数、协议、时钟或系统约束>` |
| 禁止事项 | `<明确不能这样使用>` |
| 关联资产 | `<模块、模式、问题索引>` |
