# AXI Channel Slice：模块设计与复盘示例

- **模块名称：** `axi_slice`
- **资产：** `wql32_axi_slice`
- **源码版本：** 资产标记为 `source`，未提供独立版本号
- **复盘日期：** 2026-10-20
- **当前结论：** `Constrained`；以下行为分析基于当前 RTL 静态阅读，仿真、Lint 与综合结果尚未记录

本页示范如何把七章模板填成可复查的设计记录。证据来源是站点内的 `axi_slice.v`、资产 README 和 metadata；推导出的时序性质与尚未执行的验证项会明确区分。

## 1. 模块概述

### 1.1 功能和边界

`axi_slice` 接收一条 `front_valid/front_ready` 输入通道，把完整 `front_payload` 存入两个交替使用的寄存槽 A/B，再通过 `end_valid/end_ready` 输出。它是单条 ready/valid 通道的两项缓冲，不理解 AXI AW/W/B/AR/R 的字段或跨通道关系。

每个独立 AXI 通道需要各自实例化；ID、地址、长度、响应码、LAST 等伴随字段必须与该通道的数据一起打包进 `PAYLOAD_WIDTH`。模块只保证打包位向量按握手顺序移动，不替上层检查 AXI 协议。

### 1.2 应用场景与目标

| 项目 | 本例填写 | 依据或待确认项 |
| --- | --- | --- |
| 适用位置 | 单时钟域 AXI/AXI-Stream 通道上的寄存切片 | 只有一个 `iclk`；不含跨时钟逻辑 |
| 功能目标 | 暂存最多两笔未输出的 payload，按输入顺序输出 | A/B 两个 payload 和 valid 寄存器，读写指针分别轮转 |
| 时序目标 | 切断下游 `end_ready` 到上游 `front_ready` 的直接组合路径 | `front_ready` 只由写指针和 valid 位组合得到 |
| 非目标 | AXI 五通道耦合、burst 检查、错误恢复、CDC | 接口没有相关信号或逻辑 |
| 量化目标 | 目标频率、面积预算和延迟上限待填写 | 仓库中没有目标约束与报告 |

## 2. 接口定义

### 2.1 时钟、复位与参数

| 名称 | 方向/默认值 | 语义 |
| --- | --- | --- |
| `iclk` | 输入 | 唯一工作时钟，所有事务在上升沿推进 |
| `iReset_n` | 输入，低有效 | `AR=1` 时异步断言复位；`AR=0` 时在 `iclk` 上升沿同步复位 |
| `PAYLOAD_WIDTH` | 参数，默认 32 | payload 位宽；使用方应保证大于 0，并包含全部同拍伴随字段 |
| `AR` | 参数，默认 0 | 仅 `1` 选择异步复位分支，其他值进入同步复位分支；建议只使用 0/1 |

复位将两槽数据、valid 位以及读写指针清零。同步复位模式下，复位输入拉低到下一个上升沿之间，组合输出仍可能反映旧状态；系统级使用应按复位契约处理该窗口。复位后 `end_valid=0`，`front_ready=1`，无效时的 `end_payload` 值不应作为事务使用。

### 2.2 端口与握手

| 端口 | 方向/宽度 | 语义 |
| --- | --- | --- |
| `front_valid` | 输入/1 | 上游当前 payload 有效 |
| `front_payload` | 输入/`PAYLOAD_WIDTH` | 与输入 valid 同拍的完整位向量 |
| `front_ready` | 输出/1 | 当前写槽为空，可接收一笔事务 |
| `end_valid` | 输出/1 | 当前读槽有效，可提供一笔事务 |
| `end_payload` | 输出/`PAYLOAD_WIDTH` | 当前读槽数据；仅在 `end_valid=1` 时有事务意义 |
| `end_ready` | 输入/1 | 下游准备接收当前输出 |

输入接受事件是 `front_hs = front_valid && front_ready`，输出完成事件是 `end_hs = end_valid && end_ready`。上游在 `front_valid && !front_ready` 时须保持 valid 与 payload 稳定；下游在 `end_valid && !end_ready` 时会看到稳定的 valid 与 payload，前提是未发生复位。

## 3. 架构设计

### 3.1 数据通路与控制通路

```text
front_payload --[front_hs]--> reg_a / reg_b --[end_step mux]--> end_payload
                    ^                 ^
               front_step       valid_a / valid_b       end_step
                    |                 |                     |
               front_ready      end_valid              end_hs
```

`front_step` 指向下一个写槽，`end_step` 指向下一个读槽。两个指针仅在各自的真实握手事件后翻转。`valid_a/valid_b` 表示槽是否占用；写入置位，读出清零。无直通路径，空缓冲输入必须先经过一次寄存，随后才能在输出端变为有效。

### 3.2 状态推进

该模块没有显式编码的多状态 FSM，状态由两个指针和两个 valid 位组成。以下是按接口可见行为抽象的占用状态：

| 占用 | `front_ready` | `end_valid` | 典型下一步 |
| --- | --- | --- | --- |
| 0 | 1 | 0 | 输入握手写当前槽，变为占用 1 |
| 1 | 1 | 1 | 可同周期读旧槽、写另一槽；顺序由指针保持 |
| 2 | 0 | 1 | 可读出一项；该周期不能同时写入新项 |

占用 1 且输入、输出都握手时，读写不同槽，旧项先出、新项留存。占用 2 且 `end_ready=1` 时，`front_ready` 仍基于时钟沿前的 valid 位为 0，直到读出后才重新拉高；因此满边界有一个不能接收输入的周期。

### 3.3 不变量

- `front_step` 只在输入握手翻转，`end_step` 只在输出握手翻转。
- 任一槽在 valid 为 1 时不得再次写入；输入 ready 指向的槽必须为空。
- 输出 valid 为 1 时，读指针指向最早尚未输出的槽；单槽占用时另一槽是下一个写槽。
- 无复位打断时，已握手输入和已握手输出的差值应等于有效槽数，范围为 0 到 2。
- payload 不做位级变换；字段对齐的责任在打包它们的调用方。

这些是依据 RTL 推导的预期性质，仍需要仿真或断言覆盖来证明实际实现满足全部可达状态。

## 4. 关键 RTL 实现

### 4.1 握手、选槽与保持

```verilog
assign front_ready = front_step ? ~valid_b : ~valid_a;
assign end_valid   = end_step   ?  valid_b :  valid_a;
assign front_hs    = front_valid & front_ready;
assign end_hs      = end_valid   & end_ready;
assign end_payload = end_step ? reg_b : reg_a;
```

`front_ready` 与 `end_ready` 没有组合依赖。数据寄存器仅在 `front_hs` 时写入；读指针仅在 `end_hs` 时翻转，所以反压期间读槽和输出 payload 保持不变。valid 管理使用“写入优先于清除”的分支；按照正常可达状态，同一槽不会在同一周期被读写，但复盘时仍应将该优先级作为审查点。

### 4.2 参数化与边界

| 参数/事件 | 当前处理 | 使用约束 |
| --- | --- | --- |
| `PAYLOAD_WIDTH` | A/B 各有一个该位宽的数据寄存器 | 大于 0；宽度必须覆盖整个通道 payload |
| `AR=0/1` | generate 选择同步/异步低有效复位 | 异步复位释放要求需在系统级确认 |
| 空缓冲读 | `end_valid=0`，不会形成 `end_hs` | 无效 `end_payload` 不得消费 |
| 满缓冲写 | `front_ready=0`，不会形成 `front_hs` | 上游保持 valid/payload，等待可写 |
| 满缓冲同周期出入 | 只允许输出握手，下一周期才重新 ready | 如需满吞吐满边界，需另行设计和验证 look-ahead ready |
| 复位中事务 | valid 与指针清零，未完成事务被丢弃 | 系统要定义复位时的事务处理 |

### 4.3 实现取舍

两个寄存槽切开下游 ready 到上游 ready 的组合链，代价是没有空缓冲直通、输入到输出存在一个寄存边界，且满边界不能在读出当拍接纳新项。这些是当前 RTL 的可观察取舍，尚无数据能说明它们是否满足特定系统的频率或面积预算。

## 5. 时序与性能

### 5.1 从 RTL 推导的能力

| 指标 | 结论 | 条件/证据状态 |
| --- | --- | --- |
| 容量 | 最多 2 笔尚未输出的事务 | 两个 valid 槽；静态推导 |
| 首笔无反压延迟 | 输入握手边沿后的下一上升沿可输出握手，即边沿到边沿 1 周期 | 输出无直通；静态推导，待仿真确认 |
| 连续流吞吐上限 | 每周期 1 笔 | 下游持续 ready 且未遇满槽停顿；静态推导 |
| 满槽恢复 | 满时本周期读出后，下一周期才可再写入 | `front_ready` 使用当前 valid；静态推导 |
| 频率/面积数值 | 未测量 | 缺少工艺库、约束与综合报告 |

这里的“每周期 1 笔”是该单通道的理论稳态能力，不等于完整 AXI 链路的端到端吞吐率或系统 outstanding 数量。

### 5.2 时序路径与资源

重点检查 `front_step/valid_a/valid_b -> front_ready`、`end_step/valid_a/valid_b -> end_valid` 和 `end_step/reg_a/reg_b -> end_payload`；两个指针翻转与 valid 更新也是寄存器输入路径。没有 `end_ready -> front_ready` 的直接组合路径，但实际关键路径只能由目标工艺综合和 STA 确认。

RTL 使用 `2 × PAYLOAD_WIDTH` 个 payload 位和 4 个控制位的寄存状态，另有输出选择 mux 与少量控制门。该计数是 RTL 状态位数，不是综合面积。当前两个 payload 寄存器都在复位分支赋零；复位网络、切换功耗和面积影响待综合分析。

## 6. 验证方案

### 6.1 定向场景

| 场景 | 激励 | 关键检查 |
| --- | --- | --- |
| 复位 | 空/半满/满时分别拉低复位 | 输出 valid 清零，指针回 0，后续事务从 A 槽开始 |
| 单笔 | 输入一项，下游持续 ready | 数据完整，边沿到边沿延迟符合预期 |
| 连续流 | 上下游连续 valid/ready | 稳态按序每周期输出一项 |
| 输出停顿 | 写入两项后拉低 `end_ready` | 输出数据稳定、写满后 `front_ready=0` |
| 同时读写 | 单槽占用时双侧握手 | 旧项先出，新项保留在另一槽 |
| 满槽读出 | 两槽有效时 `end_ready=1`，上游保持 valid | 当拍无输入握手，下一周期重新 ready，不丢失待写事务 |
| 复位方式 | 分别用 `AR=0` 与 `AR=1` | 同步/异步断言行为与复位窗口符合契约 |
| 宽度 | 默认 32 和目标使用位宽 | payload 全位保真，包含 sideband |

使用按输入握手入队、按输出握手出队的 scoreboard 对比 payload 和顺序；若复位打断事务，清空参考队列。随机反压应与上述定向场景结合，覆盖长时间满槽、连续出入和复位交错。

### 6.2 建议断言

```systemverilog
// 无复位打断时，输出反压期间必须保持事务和数据稳定。
assert property (@(posedge iclk) disable iff (!iReset_n)
    end_valid && !end_ready |=> end_valid && $stable(end_payload));
```

另需检查：写指针只在 `front_hs` 翻转、读指针只在 `end_hs` 翻转、有效槽数不超过 2、满槽不接受输入、输出序列与输入序列一致。跨周期断言要按 `AR` 模式处理复位采样。

### 6.3 当前证据

资产 metadata 中 `simulation`、`lint`、`formal`、`synthesis` 均为 `not_run`，没有可引用的运行命令或报告。本页的延迟、吞吐和不变量是源码分析结论，不代表仿真、形式验证、综合或 STA 已通过。将状态升级为 Ready 前，应补齐至少语法/Lint、定向仿真与 scoreboard 证据，并记录运行环境和命令。

## 7. 设计经验与复盘

### 7.1 当前发现

| 观察 | 根因或设计选择 | 建议处理 | 所需证据 |
| --- | --- | --- | --- |
| 满槽同周期读出无法接收新项 | `front_ready` 仅看当前目标槽 valid，没有预计同拍释放 | 若系统需要该边界满吞吐，可评估 look-ahead ready 与同槽读写优先级 | 满槽连续收发仿真、时序对比 |
| 外部误以为是完整 AXI slice | RTL 只暴露一条位向量通道 | 每个 AXI 通道单独实例化并打包 sideband，系统级核对跨通道依赖 | 接口连接审查与多通道压力测试 |
| 复位中未完成事务消失 | 复位清空 valid 和指针 | 系统定义复位/重试契约 | 复位插入测试 |
| `AR` 非 0/1 值进入同步分支 | generate 只有 `AR == 1` 条件 | 实例化约束为 0/1，必要时增加静态参数检查 | 参数扫描或 elaboration 检查 |

源码中有一条 `[BUGFIX]` 注释，但仓库当前文件没有提供该修复的历史测试或前后对比；本页不把它当作已验证的修复记录。

### 7.2 可复用结论

该模块适合在同一时钟域中为单条 ready/valid 通道增加两项寄存缓冲、切断组合 ready 链。当前资产状态保持 `Constrained`：使用前确认打包字段完整、复位语义与满槽气泡可接受，并完成目标环境中的验证。若要用于完整 AXI bridge，仍须分别审查 AW/W/B/AR/R 的反压、事务配对、顺序和系统缓冲容量。

后续可将“满槽 read/write 同周期处理”沉淀进设计模式与问题索引，并用定向回归比较当前实现与可满边界接收的变体。
