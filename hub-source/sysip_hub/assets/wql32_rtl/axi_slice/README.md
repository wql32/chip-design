# AXI Channel Slice

## 功能概述

`axi_slice` 是一个两级寄存的 ready/valid 通道缓冲器，用于切断长组合路径并提高接口时序裕量。它只处理一条抽象的 payload 通道，不是包含 AW、W、B、AR、R 五个通道的完整 AXI 模块。

实例化到 AXI 或 AXI-Stream 接口时，应将该通道的全部伴随信号（例如 ID、ADDR、LEN、LAST、KEEP、RESP）打包进 `PAYLOAD_WIDTH`，确保它们与 valid 同步流动。

## 参数

| 参数 | 含义 | 约束 |
| --- | --- | --- |
| `PAYLOAD_WIDTH` | payload 位宽 | 必须大于 0 |
| `AR` | 复位方式选择 | 需结合 RTL 中的 generate 分支确认同步/异步复位模式 |

## 接口语义

- `front_valid/front_payload`：上游输入。
- `front_ready`：模块能够接收当前输入。
- `end_valid/end_payload`：下游输出。
- `end_ready`：下游能够接收当前输出。
- 输入事务仅在 `front_valid && front_ready` 时进入模块。
- 输出事务仅在 `end_valid && end_ready` 时离开模块。

## 内部行为

模块使用 A、B 两个 payload 寄存器构成两项缓冲。控制逻辑在两个存储项之间轮换，最多保存两个尚未被下游接收的事务。下游反压期间，`end_valid` 和 `end_payload` 保持稳定。

该实现没有从 `end_ready` 到 `front_ready` 的直接组合通路，适合用于时序切分，但会增加寄存延迟。

## 使用限制与注意事项

- 缓冲区已满且下游在同一周期取走一项时，当前 `front_ready` 计算方式不能同步接收新的输入，会在满边界产生一个周期气泡。
- 每个 AXI 通道需要独立实例化，不能只缓存 valid 而遗漏对应的 sideband 信号。
- 上游在 `front_valid && !front_ready` 时必须保持 payload 稳定，符合标准 ready/valid 约定。
- 该模块不检查 AXI 协议顺序、burst 属性或跨通道依赖。

## 建议验证项

1. 连续无反压传输，检查顺序和 payload 完整性。
2. 随机切换 `end_ready`，检查反压期间输出稳定。
3. 缓冲区从空到满、从满到空以及满状态下的同时出入边界。
4. 复位发生在空闲、半满和满状态时，检查 valid 被正确清除。
5. 使用 scoreboard 验证无丢失、无重复、无乱序。
