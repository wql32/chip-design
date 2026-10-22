# 同步 FIFO（标准双端口）

## 用途

单时钟、单写口、单读口 FIFO。写入和读取分别由 full/empty 自动保护，适合作为普通控制队列或数据缓冲。

## 接口行为

- 实际写入：`i_wr_en && !o_full`。
- 实际读取：`i_rd_en && !o_empty`。
- 同周期读写时，占用量保持不变。
- `o_rd_data` 为当前读指针地址的组合读数据，只有非空时有效。

## 参数

- `DATA_WIDTH`：entry 数据宽度。
- `DEPTH`：FIFO 深度。
- `AFULL_TH`：almost-full 阈值。
- `AEMPTY_TH`：almost-empty 阈值。

## 实现说明

写指针和读指针均包含一位额外的 wrap bit。低位地址相同且 wrap bit 不同时表示 full；完整指针相同时表示 empty。占用量由 `wr_ptr-rd_ptr` 得到。

## 使用限制

- `DEPTH` 必须是 2 的幂，才能保证地址低位自然回绕和 full 判定正确。
- `AFULL_TH/AEMPTY_TH` 应位于合法深度范围内。
- 组合读形式能否推断为 RAM 取决于综合模板和目标工艺。
- 满状态即使同周期发生读取，写侧仍被阻塞，因此满边界可能有一个周期 bubble。
- 没有 overflow/underflow pulse；非法请求只会被屏蔽。

## 建议检查场景

空读、满写、同时读写、almost 阈值、连续吞吐和多次指针回绕。
