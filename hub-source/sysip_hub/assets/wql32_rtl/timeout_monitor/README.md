# Transaction Timeout Monitor

## 用途

监控一个已经发出的事务是否在规定周期内完成。适合放在 DMA request、PCIe request、CXL request 或内部资源分配流程旁边。

## 行为

- `start_valid && start_ready` 时开始计时，并锁存当前 `timeout_limit`。
- `done` 或 `abort` 时结束当前监控。
- `timeout_limit=0` 表示关闭超时。
- 超时时产生一个周期的 `timeout_pulse`，同时置位 `timeout_sticky`。
- `clear_sticky` 清除锁存的超时错误。
- `done` 与超时在同一周期发生时，`done` 优先。
- `done/abort` 与下一笔 `start_valid` 同周期时，可以无 bubble 地开始下一笔监控。
- 超时后 `elapsed` 保留超时门限值；下一笔事务开始时重新清零。

该版本是单 outstanding 监视器，不包含 Tag 匹配逻辑。
