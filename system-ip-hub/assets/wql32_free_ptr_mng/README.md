# Free Pointer Manager

## 当前结论

该模块试图实现带预取缓存的空闲指针池，但当前源码存在语法错误、组合锁存和计数语义不一致等问题，不能直接编译或集成。

## 设计意图

模块使用 bitmap 维护空闲指针，并设置一个两项预分配缓存，使申请路径不必每次都直接对整张 bitmap 做组合搜索。预期流程为：

1. bitmap 记录每个 pointer 是否空闲。
2. 预取逻辑从 bitmap 中寻找空闲 pointer，填入两项缓存。
3. 收到申请请求后，从缓存输出一个 pointer。
4. 收到释放请求后，将对应 pointer 重新置为空闲。

这种架构适合 DMA descriptor、tag、queue entry 或 outstanding transaction ID 的资源管理。

## 预期接口语义

- allocation 请求成功时，应同时给出有效标志和唯一 pointer。
- release 只应增加一个尚未空闲的合法 pointer。
- `o_ptr_num` 应明确表示“bitmap 加缓存的总空闲数”或“缓存中可立即分配数”，不能混用。
- 空池申请、满池释放和重复释放都应有定义明确的处理方式。

## 已知问题

- 参数列表中 `PTR_WIDTH` 与 `END_OF_LIST` 之间缺少逗号，属于直接语法错误。
- 循环变量 `i` 未声明。
- `pre_alc_req` 的声明宽度与其逻辑用途不一致。
- 预取 pointer 的组合逻辑没有完整默认赋值，会推导锁存器。
- 搜索范围排除了 pointer 0，导致 0 号资源无法正常分配。
- 申请读指针可能在没有有效缓存项时仍翻转，破坏缓存状态。
- `o_ptr_num` 当前更接近缓存项计数，而不是完整空闲池数量。
- 未防止重复释放、非法 pointer 释放或同一 pointer 被重复分配。

## 推荐重构方式

1. 先定义清晰不变量：每个 pointer 必须且只能存在于“已分配、bitmap 空闲、预取缓存”三种状态之一。
2. 将总空闲计数与预取缓存计数分开维护。
3. 使用经过验证的 first-one/priority encoder 搜索 bitmap，并覆盖 pointer 0。
4. 仅在 `alloc_req && alloc_valid` 时弹出缓存项。
5. 仅在合法且当前已分配的 pointer 释放时更新 bitmap；调试版本可增加 duplicate-free 断言。
6. 对同周期 allocate、prefetch、release 明确定义优先级和 next-state 计算。

## 建议验证项

- 初始化后逐个申请直到耗尽，检查唯一性和总数量。
- 随机申请/释放，并用软件集合模型比较空闲集合。
- pointer 0、最大 pointer、空池申请、满池释放和重复释放。
- 同周期申请与释放，包括释放刚申请的 pointer。
- 断言“无重复分配”“计数范围合法”“缓存与 bitmap 不重叠”。
- 编译、lint、锁存和越界检查。
