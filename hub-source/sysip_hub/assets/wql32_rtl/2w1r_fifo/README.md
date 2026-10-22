# 双写单读 FIFO

## 当前结论

2026-10-21 修复双写地址、剩余容量判断、端口 1 单写、非法操作保护及非 2 的幂回绕。状态 **Constrained**，实际 RTL 仿真通过。

## 接口与参数

模块名 fifo_2w1r 不变；单时钟、低有效同步复位。FIFO_WIDTH >= 1、FIFO_DEPTH >= 1，AFULL_DEPTH 建议在 0 到深度之间，FIFO_NAME 未使用。组合输出队首，消费者在有效读的上升沿采样，空或复位时输出零。

两个写端没有单独 accept/ready，采用**整批接受或整批拒绝**契约，不能隐式部分接收。

## 接受条件与顺序

```text
read_fire = i_rst_n && i_re && !o_empty
requested_writes = i_we_0 + i_we_1
available_slots = FIFO_DEPTH - occupancy + read_fire
accept_group = i_rst_n && requested_writes != 0
               && requested_writes <= available_slots
```

- 双写且空间足够：端口 0 在前，端口 1 在后。
- 仅端口 1 写：直接使用当前尾地址，不留空洞。
- 空间不足容纳整批：两路均拒绝，overflow=1；调用者重试整个批次。
- 满且同时读：只释放一个名额，可接受单写，不能接受双写。
- 空且同时读写：读拒绝、underflow=1；可接受放得下的写批次，不支持旁路。
- 深度 1 支持单写，始终拒绝双写。
- o_full 只表示完全占满，不代表一定能接收双写；告警为组合输出，不是粘滞位。

## 架构与修复

指针逐步显式回绕，第二笔使用下一合法地址，占用更新为“旧占用 - 实际读 + 实际接受笔数”。复位清控制状态，不清阵列。若替换为 SRAM，需重新处理端口数量、读写冲突及读延迟。

## 验证记录

Icarus Verilog 执行 tb/tb_fifos.sv，联合检查 basic_fifo，深度 1/2/3/8/9，每组 3,000 次随机操作，覆盖端口 1 单写、批次拒绝、满读写、回绕、告警及复位。独立队列核对顺序与占用，pyslang 12.0.0 展开通过。

旧版本手工验证结果保存在 verification_history，不自动继承到修复版。当前未执行 formal、综合、时序或性能签核。
