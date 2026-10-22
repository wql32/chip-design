# System IP Design Hub 网页功能规范

## 1. 导航结构

```text
Dashboard
├── Assets
├── Protocols
├── Bridge Mappings
├── Verification
├── Dependencies
├── Debug Cases
└── Settings
```

## 2. 页面定义

### Dashboard

目标：快速了解资产库健康度和最近活动。

组件：

- 资产总数
- DMA/AXI/PCIe/CXL/Bridge 分类统计
- 验证状态统计
- 最近更新资产
- 待补充 metadata 的资产
- 最近 Debug Case
- 依赖异常提示

### Assets

目标：按功能、协议和验证状态查找可复用资产。

筛选条件：

- 关键词
- category
- kind
- protocol
- tags
- verification status
- asset status

列表字段：

- 名称
- 类型
- 协议
- 版本
- 状态
- 验证摘要
- 更新时间

### Asset Detail

目标：在复用前理解资产的能力和边界。

页面区域：

1. Summary：名称、版本、描述、状态
2. Interfaces：输入输出接口和协议
3. Parameters：参数和默认值
4. Features：支持的功能
5. Limitations：明确不支持的场景
6. Verification：验证矩阵和报告链接
7. Dependencies：依赖资产图
8. Files：RTL、SVA、TB、文档
9. Related：关联协议、mapping、debug case
10. History：版本和变更记录

### Protocols

目标：管理协议语义和设计规则。

第一版协议分类：

- AXI4
- AXI4-Lite
- AXI-Stream
- PCIe
- CXL.io
- CXL.cache
- CXL.mem

协议卡片内容：

- transaction 类型
- ordering
- response
- error
- credit/backpressure
- 对齐和边界条件
- 关联资产
- 关联 Debug Case

### Bridge Mappings

目标：管理跨协议 transaction 转换。

列表字段：

- Bridge 名称
- 输入协议
- 输出协议
- transaction 数量
- 是否支持拆分
- 是否需要 response
- ordering
- 错误映射

详情页面：

- source transaction
- target transaction
- 字段映射表
- 拆分/合并规则
- 地址转换
- 数据宽度转换
- byte enable 规则
- outstanding 管理
- error mapping
- transaction flow 图
- 相关 RTL 和验证项

### Verification

目标：查看资产验证成熟度和缺失项。

支持：

- 按验证类型筛选
- 查看通过/失败/未运行项
- 查看报告路径
- 查看验证命令
- 查看最后检查时间
- 生成资产健康度摘要

### Dependencies

目标：了解复用资产的组成和影响范围。

支持：

- 资产依赖树
- 反向依赖查询
- 缺失依赖提示
- 循环依赖提示
- 版本约束展示

### Debug Cases

目标：复用过往问题定位经验。

字段：

- 标题
- 协议
- 症状
- 根因
- 触发条件
- 修复方式
- 关联资产
- 关联波形/日志

## 3. 第一版 API 边界

第一版可以使用简单的本地 HTTP API，不要求登录和远程访问。

```text
GET  /api/health
GET  /api/assets
GET  /api/assets/{name}
GET  /api/assets/{name}/files
GET  /api/assets/{name}/dependencies
GET  /api/protocols
GET  /api/mappings
GET  /api/verification/summary
GET  /api/debug-cases
POST /api/catalog/scan
```

第一版不开放任意文件路径访问。所有文件读取都必须通过资产根目录校验。

## 4. 典型用户流程

### 流程 A：复用一个 FIFO

```text
Assets
 → category=fifo
 → tag=cdc
 → 查看 async_fifo
 → 阅读 limitations
 → 查看 verification
 → 查看 dependencies
```

### 流程 B：设计 PCIe 到 AXI Bridge

```text
Bridge Mappings
 → 选择 PCIe → AXI
 → 查看 transaction mapping
 → 查看 ordering/error 规则
 → 查看相关 corner cases
 → 关联 RTL 和 SVA 资产
```

### 流程 C：排查 CXL transaction 问题

```text
Debug Cases
 → protocol=CXL.mem
 → 搜索症状
 → 查看可能根因
 → 查看关联 mapping
 → 查看相关验证项
```

### 流程 D：检查现有时钟/复位工具

```text
Assets
 → category=clock_reset
 → 查看 ../clock_reset_analysis/extract_clk_rst.py
 → 查看 Makefile
 → 查看报告输出
 → 查看运行约束和依赖工具
```

## 5. 第一版不做的交互

- 在线编辑 RTL
- 在线执行任意 shell 命令
- 文件上传到远端
- 自动修改资产代码
- 自动判定协议合规性
- 自动推断公司内部协议规则

这些功能会带来较高的安全、权限和误操作风险，放到后续阶段评估。
