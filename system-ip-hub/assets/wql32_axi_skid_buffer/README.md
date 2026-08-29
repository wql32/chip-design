# AXI Ready/Valid Skid Buffer

## 用途

两级 ready/valid 缓冲。适合放在 AXI/AXI-Stream 通道中，切断下游 `m_ready` 到上游 `s_ready` 的组合路径，并吸收 ready 关闭过程中已经被接受的一拍数据。

## 接口约定

- `s_valid/s_ready/s_data`：输入通道
- `m_valid/m_ready/m_data`：输出通道
- `reset_n`：低有效复位，`AR=0` 为同步复位，`AR=1` 为异步复位

## 行为

- 空 buffer 时，输入握手后数据在下一周期出现在输出端。
- 满 buffer 且 `m_ready=0` 时，保持数据不变。
- 非满状态支持输入和输出同周期握手。
- 完全满状态释放一个 entry 后，`s_ready` 在下一周期恢复。
- 不提供 fall-through，因而输出数据路径是寄存的。

## 典型实例化

```systemverilog
wql32_axi_skid_buffer #(.DATA_WIDTH(256)) u_skid_buffer (...);
```
