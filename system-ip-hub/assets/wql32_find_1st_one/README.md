# Find First One

## 当前结论

当前源码包含多处参数名拼写不一致和非法 generate 初始化，无法通过编译。算法意图可以保留，代码需要重新整理后再使用。

## 设计意图

模块用于从输入 bitmap 中找到索引最小的第一个 `1`，同时输出 one-hot 结果和对应的二进制索引。预期 one-hot 逻辑为：

```text
o_onehot[i] = i_bitmap[i] && !(|i_bitmap[i-1:0])
```

因此，当多个 bit 同时为 `1` 时，低索引 bit 优先。

## 预期接口语义

- 输入全 0：`o_onehot` 应为全 0。
- 单 bit 为 1：输出该 bit 的 one-hot 和索引。
- 多 bit 为 1：输出最低索引的 bit。
- 当前设计没有独立 valid 输出，因此二进制索引为 0 时无法区分“输入全 0”和“bit 0 命中”。

## 已知问题

- `BITMAP_WIDTH` 在源码中被写成多个不同名称，包括 `BITMAP_WDITH`、`BITMAP_WIDHT` 等。
- `BIN_WIDTH` 也存在 `BIN_WIDHT` 拼写错误。
- generate 循环初始化类似 `genvar i = i`，不构成合法的循环起点。
- 参数和切片错误会进一步导致端口宽度与索引越界问题。

## 修复建议

1. 统一参数名称，并在端口、局部参数和 generate 中只使用一套定义。
2. 增加 `o_valid = |i_bitmap`，消除零输入歧义。
3. 明确优先方向，建议在模块名或注释中注明 LSB-first。
4. 对 `BITMAP_WIDTH=1` 单独处理，避免零宽度索引。
5. 若时序压力较大，可改为分层 priority encoder；位宽较小时优先使用简单循环实现以提高可维护性。

## 建议验证项

- 输入全 0、仅 bit 0、仅最高 bit。
- 每个 bit 单独置位的遍历测试。
- 随机 multi-hot 输入，参考模型取最低置位索引。
- `BITMAP_WIDTH=1`、非 2 的幂位宽和较大位宽参数。
- 编译、lint、组合环路和越界检查。
