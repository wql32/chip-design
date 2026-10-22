# Asynchronous FIFO（通用样例）

用于记录跨时钟域 transaction buffering 的通用资产卡片，不包含生产 RTL。

关注点：

- 独立读写时钟
- Gray pointer 同步
- full/empty 标志延迟
- reset release
- backpressure
