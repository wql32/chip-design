# AXI Burst Splitter

## 用途

把一笔线性传输拆成多个子 burst，保证每个子 burst 同时满足：

- 不超过 `MAX_BURST_BEATS`
- 不跨越 `BOUNDARY_BYTES` 边界，默认是 4KB

适合放在 DMA 地址生成器、AXI Master 请求生成器或 PCIe-to-AXI 转换路径中。

## 接口约定

- `in_addr`：传输起始字节地址
- `in_beats`：总 beat 数，使用实际数值，不是 `AxLEN`
- `in_size`：每 beat 字节数的 log2，例如 64B 为 6
- `out_addr/out_beats`：当前子 burst 的起始地址和 beat 数
- `out_last`：当前子 burst 是否为整笔传输的最后一段
- `error_pulse/error_code`：非法输入命令错误；1=零 beat，2=地址未按 beat 对齐，3=size 非法

## 设计假设

输入命令在 `in_valid && in_ready` 时被接收；每个输出 burst 在 `out_valid && out_ready` 时推进。输入命令完成前不会接收下一笔命令。

当前版本只接受按 `2**in_size` 对齐的 INCR 类型命令。非法命令不会生成零长度 burst，而是产生一个周期的错误脉冲。
