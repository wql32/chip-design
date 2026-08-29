# 基础同步 FIFO

## 当前结论

该文件是单写单读同步 FIFO 的早期实现，但当前源码存在明确的编译错误和状态保护缺陷，**不能直接使用**。功能上可作为理解读写指针与计数器结构的草稿。

## 预期接口

- `i_we/i_wdata`：写请求和写数据。
- `i_re`：读请求。
- `o_rdata`：当前读指针指向的组合数据。
- `o_full/o_afull/o_empty`：容量状态。
- `o_overflow/o_underflow`：满写和空读告警。

## 参数

- `FIFO_WIDTH`：entry 数据宽度。
- `FIFO_DEPTH`：FIFO 深度。
- `AFULL_DEPTH`：almost-full 阈值。
- `FIFO_NAME`：当前未使用。

## 已知问题

1. 写指针更新中使用了不存在的 `fifp_wptr`，会导致编译失败。
2. `fifo_cnt_delta` 使用圆括号代替拼接花括号，语法错误。
3. 读指针没有按 `FIFO_DEPTH` 显式回绕。
4. 写操作没有由 `!o_full` 保护，读操作没有由 `!o_empty` 保护。
5. overflow/underflow 只产生信号，但非法请求仍然改变指针和计数器。
6. `fifo_wptr_plus1` 被声明但没有使用。

## 修复方向

建议统一定义：

```text
write_fire = i_we && !o_full
read_fire  = i_re && !o_empty
```

所有存储器写入、指针推进和计数器更新都只能使用 fire 条件。若需要支持满状态下同时读写，应明确是否允许读操作释放的 entry 被同周期写入。
