# RTL 修复回归

工作目录根目录运行：

```powershell
python -m unittest discover -s tests -p 'test_rtl_*repairs.py' -v
```

- 始终运行 Python 表达式／周期模型，使用独立参考算法和事务队列检查结果。
- 检测到 `pyslang` 时，会对实际 RTL 和 testbench 的 19 组参数执行语法、类型与参数展开检查。支持当前 Python 环境或项目内 `.rtl_tools/python` 安装；检查器版本为 12.0.0。
- 优先检测项目内 `.rtl_tools/iverilog/app/bin/iverilog.exe` 和 `vvp.exe`，也支持 PATH 中的 Icarus。检测到后实际执行两批共 53 组参数配置；工具缺失时明确标记为 skipped，不能当成仿真通过。
- Python 模型不执行 RTL，不模拟亚稳态，不能代替 RTL 仿真、CDC 或综合签核。

静态检查器可以安装到项目内目录，不修改系统 Python：

```powershell
python -m pip install --target .rtl_tools/python -r tests/rtl_priority/requirements.txt
```

依赖来自 [pyslang 项目发布](https://pypi.org/project/pyslang/)。工具目录不参与网站导出。

| Testbench | 检查内容 |
| --- | --- |
| `tb_encoder.sv` | one-hot 全位置、零输入、宽度 1/非 2 的幂/253/512；现有 find-first-one 的最低位优先行为 |
| `tb_scheduler.sv` | 原始 bit 1 失败用例、优先位置和请求组合、暂停、复位、随机请求、持续请求轮询 |
| `tb_handshake.sv` | 异频、同频、不同相位、连续 valid、数据顺序与唯一性、双域协调复位后恢复 |

握手同步器的单边复位恢复不在接口保证范围内；协调复位会丢弃在途事务，由系统重新发起。

所有 testbench 位于对应资产的 `tb/` 子目录，随 RTL 一起导出，网站“源码”页可查看。

| 新增 Testbench | 参数与检查 |
| --- | --- |
| `2w1r_fifo/tb/tb_fifos.sv` | basic/dual FIFO；深度 1/2/3/8/9，独立队列核对满空、同拍读写、双写整批拒绝、告警、复位，每组 3,000 次随机操作 |
| `ff_cam/tb/tb_storage.sv` | FF array/CAM；深度 1/3/9 × 输入寄存 0/1 × 输出寄存 0/1；12 组，每组 1,500 次随机事务，检查冲突、有效位、重复 key、越界和复位 |
| `free_ptr_mng/tb/tb_pointer_pool.sv` | 指针数 1/2/3/9/64/384；6 组，耗尽唯一性、重复与越界释放、并发分配释放、总空闲数；每组 3,000 次随机事务 |
| `clk_divider/tb/tb_divider.sv` | 偶数因子 2/4/8、奇数 3/5/7/9、4 组非法参数；11 组，逐半周期检查波形、随机使能、异步复位 |

2026-10-21 本机使用 pyslang 12.0.0 和 Icarus Verilog 12.0(devel) 完成 53 组实际 RTL 展开与仿真。模型与仿真均不替代 formal、CDC、综合、STA 或 CTS。

Windows 便携 Icarus 的编译库位于 `.rtl_tools/iverilog/app/lib/ivl`，运行器自动添加 `-B`/`-M`，使用相对路径避开原生工具对中文绝对路径的限制。工具本身不导出到网站。可从维护者 [Windows 发布页](https://bleyer.org/icarus/) 获取工具；运行器不自动下载或安装软件。
