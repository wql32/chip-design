# Round-Robin Scheduler

## 当前结论

当前 `rr_sch` 源码存在 generate 结构、掩码算法、端口位宽和有效判断等多类问题，不能直接编译或作为可靠仲裁器使用。建议改用已审查的 `rr_arbiter`，或根据明确接口重新实现。

## 设计意图

模块希望为多路请求生成 round-robin grant：记录上一次服务位置，对其后的请求赋予更高优先级，在尾部无请求时回绕到低索引位置，并输出 grant、grant id 和有效标志。

一个可靠的 scheduler 还需要明确两类事件：

- “选中了谁”：组合候选 grant。
- “谁真正完成服务”：仅在下游接受后更新轮询状态。

当前接口和实现没有把这两个语义稳定地区分开。

## 已知问题

- 条件 generate 与 `endgenerate` 的结构不匹配或不符合目标编译模式。
- `mask_0` 的构造使用当前 bit 参与前缀条件，可能把预期可见请求一并屏蔽，只留下错误的优先范围。
- `o_gnt_vld` 的声明是向量，但逻辑上被当作标量有效位赋值。
- 使用 `(masked_req == 1'b1)` 判断“存在请求”，对于多 bit 向量语义错误；应使用归约 OR：`|masked_req`。
- grant 没有被 scheduler enable 或实际接受条件完整门控。
- 状态更新条件没有清晰对应“grant 被接受”，可能造成轮询指针空转或跳过请求。
- 未定义全 0 请求、multi-request、反压和请求提前撤销时的稳定行为。

## 推荐重构方式

1. 统一接口为 `req`、`grant`、`grant_valid` 和 `grant_accept`。
2. 使用 last-grant mask 加两次 priority encode：先搜索 last-grant 之后，再回绕搜索全请求。
3. 仅在 `grant_valid && grant_accept` 时更新 last-grant。
4. `grant_valid` 使用标量，`grant` 使用 one-hot 向量，`grant_id` 位宽至少为 1。
5. 明确反压期间 grant 是否必须保持；若必须保持，应增加 pending grant 寄存器。
6. 对 `REQ_NUM=1` 和非 2 的幂端口数增加参数处理。

## 建议验证项

- 单请求、全请求、稀疏请求和请求动态变化。
- grant 长时间不被接受，检查状态不应前进。
- 每次接受后检查下一优先位置和尾部回绕。
- 持续请求条件下的无饥饿检查。
- 断言 grant one-hot0、valid 与 grant 一致、grant 必须对应有效请求。
- 编译、lint、位宽、未驱动和组合环路检查。
