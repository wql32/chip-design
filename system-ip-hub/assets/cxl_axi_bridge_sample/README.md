# CXL.mem to AXI Bridge（通用样例）

该样例用于记录 CXL.mem 到 AXI 转换时需要明确的设计决策，不包含任何专有实现。

重点关注：

- request/response 转换
- memory ordering 和可见性策略
- backpressure
- retry、poison 和 error 传播
- CXL 语义到 AXI response 的映射
