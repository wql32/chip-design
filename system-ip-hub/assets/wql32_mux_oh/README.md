# One-Hot Mux

## 功能概述

`mux_oh` 是一个纯组合 one-hot 多路选择器。每个输入端口的数据先由对应的 select bit 掩码，再对所有掩码结果按位 OR，得到最终输出。

## 参数与数据打包

| 参数 | 含义 | 约束 |
| --- | --- | --- |
| `PORT_NUM` | 输入端口数量 | 必须大于 0 |
| `DATA_WIDTH` | 每个端口的数据位宽 | 必须大于 0 |

`i_data` 是扁平化总线。端口 0 位于最低 `DATA_WIDTH` 位，端口 `n` 位于：

```text
i_data[n*DATA_WIDTH +: DATA_WIDTH]
```

`i_sel[n]` 选择对应端口。

## 实际行为

- `i_sel` 为合法 one-hot：输出被选中的一组数据。
- `i_sel` 全 0：输出全 0。
- `i_sel` 为 multi-hot：被选中的多组数据按位 OR 合并，不会自动选择优先级。
- 模块不输出 valid、one-hot error 或 multi-hot error。

因此，该模块只有在调用者能保证 `$onehot0(i_sel)` 时才等价于传统 mux。若 multi-hot 输入属于非法状态，建议在上层增加断言。

## 时序与实现注意事项

- 这是组合路径，延迟随 `PORT_NUM` 和 `DATA_WIDTH` 增大。
- 大规模端口可能形成高扇入 OR 树，应检查综合后的逻辑级数。
- 若处于高频路径，可在输出端增加寄存器，或改为分层选择结构。
- 输入和 select 必须属于同一时序语义，避免 select 切换时组合毛刺被下游采样。

## 建议验证项

1. 遍历每个合法 one-hot select，检查端口切片顺序。
2. 检查全 0 select 输出全 0。
3. 显式检查 multi-hot 时的按位 OR 行为。
4. 对 `PORT_NUM=1`、非 2 的幂端口数和不同数据位宽做参数测试。
5. 在集成处加入 `assert ($onehot0(i_sel));`，如果设计不允许 multi-hot。
