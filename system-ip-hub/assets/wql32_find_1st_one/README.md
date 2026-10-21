# Find First One

## 当前结论

2026-10-21 重新核对现有 RTL：之前记录的参数拼写、generate 初始化等语法问题已修复，旧的“无法编译”说明已删除。本次未修改该模块 RTL。状态更新为 **Constrained**，适用参数与输出有效性要求见下文。

## 功能与接口

从 bitmap 中选取索引最小的置位 bit，同时输出 one-hot 和二进制索引：

- 零输入：`o_onehot=0`、`o_binary=0`。
- 单 bit 输入：输出该 bit 和对应索引。
- multi-hot 输入：最低索引优先。
- `|o_onehot` 可作为有效标志；仅看 binary=0 无法区分无命中和 bit 0 命中。

## 架构与关键实现

组合循环从高索引向低索引扫描并覆盖索引变量，因此最终保留最低置位位置。one-hot 各位使用“本位有效且所有更低位均为 0”的前缀条件，两个输出采用一致的 LSB-first 语义。

## 参数与约束

- 当前默认 `BIN_WIDTH=$clog2(BITMAP_WIDTH)`；要求 **BITMAP_WIDTH >= 2**，避免默认索引位宽为 0。
- BIN_WIDTH 至少能表示最大合法索引，不能人为缩窄。
- 支持非 2 的幂输入宽度；纯组合模块，无时钟或复位。
- 大位宽的优先路径需要目标综合和时序检查；尚未承诺性能。

## 验证记录

- pyslang 12.0.0：与编码器 bench 一同展开，覆盖 2/3/8/9/16/253/256/257/384/512 等宽度，无编译错误。
- Python 表达式模型：在宽度 2/3/4/8/9/12 下穷举共 4,892 个向量，检查两个输出与最低置位参考值一致。
- 已提供零输入、全位置 one-hot、小宽度穷举和大宽度随机 multi-hot 的自检 testbench；只完成静态编译，尚未执行 RTL 仿真。
- 本次没有增加端口或声称支持默认参数下的 BITMAP_WIDTH=1。

项目根目录可运行：`python -m unittest discover -s tests -p test_rtl_priority_repairs.py -v`。
