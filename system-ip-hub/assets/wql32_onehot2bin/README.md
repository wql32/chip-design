# One-Hot to Binary Encoder

## 当前结论

2026-10-21 已替换有偏移和越界的分段切片实现，保持 `onehot2bin/i_bitmap/o_binary` 接口。当前状态为 **Constrained**：实际 RTL 多参数展开、表达式模型及 Icarus 动态仿真通过；未进行综合时序评估。

## 功能与输入约定

这是严格 one-hot 编码器，不是 priority encoder：

- 输入只有 bit k 为 1 时，输出 k。
- 输入全 0 时，输出 0；需要区分零输入与 bit 0 命中时，调用者使用 `|i_bitmap` 作为 valid。
- multi-hot 输入不在有效输入约定中；当前电路会按位 OR 合并各个置位索引，不能将结果解释为某一有效命中。
- 需要最低位置优先时，应先使用 `find_1st_one` 或等价优先选择逻辑。

未新增 valid 或 multi-match 端口，以保持已有调用方式。调用者应在验证环境中检查 `$onehot0(i_bitmap)`，或以严格 one-hot 约束驱动。

## 实现结构

对每个输出 bit b，只归约输入 bitmap 中“索引的第 b 位为 1”的位置。所有位置选择在参数展开时确定，不使用补齐数组、变动切片或跨 generate 作用域的函数。

该结构保证每个输出 bit 都被完整驱动，也消除了原实现对 bit 1 漏选及最高端越界的问题。

## 参数

| 参数 | 约束 |
| --- | --- |
| `BITMAP_WIDTH` | 大于等于 1，可为非 2 的幂 |
| `BIN_WIDTH` | 大于等于 max(1, ceil(log2(BITMAP_WIDTH)))，默认自动计算 |

位宽为 1 时端口仍为 1 bit，零输入和 bit 0 命中均编码为 0。若手工将 BIN_WIDTH 设得过小，索引会截断，属于非法参数配置。

## 时序与复用边界

纯组合电路，无时钟和复位。端口位宽较大时存在输入扇出和 OR 归约路径，目标频率、面积和布线需要通过目标工艺综合确认，不能仅凭功能模型推断性能。

CAM 如允许重复 key，必须先定义 multi-match 的处理规则；直接连接本模块无法实现可靠的优先匹配。

## 验证记录

- pyslang 12.0.0：实际 RTL 与 `tb_encoder.sv` 在 1/2/3/8/9/16/253/256/257/384/512 等 11 种宽度下展开，无编译错误。
- Python 表达式模型：14 种输入宽度、最小与加宽输出索引，遍历零输入及每个单独置位的位置，与整数索引参考值比较。
- Icarus Verilog/vvp 已实际执行自检 testbench，11 种宽度全部通过。
- 不将非法 multi-hot 的输出解释为 priority encoder 结果。

项目根目录可运行：`python -m unittest discover -s tests -p test_rtl_priority_repairs.py -v`。
