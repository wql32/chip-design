# PCIe Memory to AXI Bridge（通用样例）

这是一个不包含公司专有 RTL 的 Bridge 设计卡片，用于验证 System IP Design Hub 的协议映射页面。

## 设计路径

```text
PCIe TLP
  -> TLP Decode
  -> Address / Length Check
  -> Outstanding Tracker
  -> AXI Request
  -> AXI Response
  -> PCIe Completion / Error Mapping
```

重点记录：

- PCIe memory read/write 到 AXI read/write 的映射
- response 是否必需
- transaction 拆分条件
- ordering 和 error mapping
- tag、byte enable 和 backpressure 的处理要求
