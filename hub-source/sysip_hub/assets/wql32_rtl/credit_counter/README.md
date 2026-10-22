# Credit Counter

## 用途

管理有限资源的 credit。常见用途包括 PCIe/CXL outstanding request、buffer slot、descriptor slot 和链路流控。

## 行为

- `alloc_ready=1` 表示当前 credit 足够接受 `alloc_count`。
- `alloc_valid && alloc_ready` 时消耗 credit。
- `return_valid` 时归还 `return_count`。
- 同周期分配和归还先计算净变化；净结果超过 `MAX_CREDITS` 时计数器饱和，并置位 `overflow_error`。
- `clear_errors` 清除 sticky 错误。

同周期归还的 credit 不参与当前周期的 `alloc_ready` 判断，避免组合依赖；归还后的 credit 从下一周期可见。

当 `clear_errors` 与新的 overflow 同周期发生时，新 overflow 优先保留。

实例化时要保证 `CREDIT_WIDTH` 能够表示 `MAX_CREDITS` 本身；例如 `MAX_CREDITS=256` 时至少使用 9 bit。
