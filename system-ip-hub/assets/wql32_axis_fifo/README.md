# AXI4-Stream 同步 FIFO

## 用途

缓存 AXI4-Stream 数据拍，并保持 `tdata/tkeep/tlast` 同步移动。适用于 DMA 数据路径、packet pipeline 和上下游存在 backpressure 的单时钟场景。

## 握手行为

- 写入：`s_axis_tvalid && s_axis_tready`。
- 读取：`m_axis_tvalid && m_axis_tready`。
- 下游停顿时，读指针保持，`m_axis_tdata/tkeep/tlast` 保持为当前 FIFO head。
- FIFO 满时 `s_axis_tready=0`；空时 `m_axis_tvalid=0`。

## 存储格式

每个 entry 保存：

```text
{tlast, tkeep, tdata}
```

模块只保存包边界信息，不检查 packet 长度、非法 `tkeep` 或 `tlast` 位置。

## 参数约束

- `DATA_WIDTH` 必须是 8 的整数倍。
- `DEPTH` 应为 2 的幂，否则低位指针可能访问不存在的数组地址。
- `AFULL_TH` 应位于 `0..DEPTH` 范围内。

## 延迟与吞吐

存储器采用组合读。非空时输出直接对应当前读地址；每次输出握手后，下一 entry 在指针更新后出现。一般情况下支持每周期一拍输入和一拍输出。

## 使用限制

- 完全满且同周期下游读取时，`s_axis_tready` 仍为 0，不能同周期补入新数据，会出现一个周期的满边界 bubble。
- `o_almost_empty` 固定使用 `fifo_cnt <= 2`，没有独立参数。
- 组合读 RAM 的综合映射依赖目标平台。
- 没有 overflow/underflow 事件输出。

## 建议检查场景

单拍包、连续多拍包、任意 backpressure、满边界同时读写、`tkeep` 非全 1，以及 `tlast` 位于 FIFO 首尾和指针回绕位置。
