# System IP Design Hub 设计规范

## 1. 目标

System IP Design Hub 是一个本地优先的设计资产与知识管理平台，第一阶段覆盖：

- RTL/IP 资产
- DMA、AXI、PCIe、CXL 协议知识
- PCIe/CXL/AXI Bridge transaction mapping
- 验证状态
- 资产依赖关系
- Debug case 和设计文档

平台不替代公司已有的 lint、CDC、仿真、形式验证和性能工具，而是管理这些工具的配置、结果和关联关系。

## 2. 设计原则

1. 资产文件与资产描述分离：RTL、文档和测试文件保存在目录中，索引信息保存在 metadata 中。
2. 元数据版本化：metadata 与资产一起进入 Git 或其他版本管理系统。
3. 本地优先：默认不上传代码和文档，不依赖外部网络。
4. 协议语义优先：Bridge 资产除了记录端口，还记录 transaction、ordering、error 和 backpressure 规则。
5. 渐进式验证：资产可以从 draft 逐步升级到 production_ready。
6. 可扩展但少必填：第一版只要求能搜索、理解和复用，复杂字段允许后续补充。

## 3. 资产目录规范

```text
assets/
├── dma/
├── axi/
├── pcie/
├── cxl/
├── bridges/
├── primitives/
├── cdc_reset/
├── verification/
├── performance/
└── debug_cases/
```

单个资产建议使用以下结构：

```text
<asset-name>/
├── metadata.yaml
├── README.md
├── rtl/
├── tb/
├── sva/
├── docs/
├── examples/
├── reports/
└── CHANGELOG.md
```

目录不是强制全部存在。只有 `metadata.yaml` 和 `README.md` 是推荐的基础文件。

## 4. Metadata 规范

示例：

```yaml
schema_version: 1
name: pcie_mem_to_axi_bridge
display_name: PCIe Memory to AXI Bridge
version: 0.1.0
kind: bridge
category: bridges
description: Converts PCIe memory transactions into AXI transactions.

protocols:
  input:
    - pcie
  output:
    - axi4

tags:
  - pcie
  - axi
  - bridge
  - backpressure

features:
  - memory_read
  - memory_write
  - outstanding_tracking
  - error_mapping

parameters:
  - name: addr_width
    type: integer
    default: 64
    required: true
  - name: data_width
    type: integer
    default: 256
    required: true

interfaces:
  - name: pcie_tlp
    protocol: pcie
    direction: input
  - name: axi_m
    protocol: axi4
    direction: output

limitations:
  - Does not support atomic operations.
  - Maximum payload is implementation dependent.

dependencies:
  - name: async_fifo
    version: '>=1.0.0'
    relation: required

verification:
  simulation: passed
  lint: passed
  cdc: reviewed
  formal: not_run
  synthesis: not_run
  performance: not_run
  last_checked: 2026-08-16
  notes: Basic read/write scenarios covered.

files:
  rtl:
    - rtl/pcie_mem_to_axi_bridge.sv
  testbench:
    - tb/pcie_mem_to_axi_bridge_tb.sv
  assertions:
    - sva/pcie_mem_to_axi_bridge_sva.sv
  documents:
    - README.md

mapping:
  - source_transaction: pcie_memory_read
    target_transaction: axi_read
    split: possible
    response_required: true
    ordering: preserve
    error_mapping: axi_rresp_to_pcie_completion_status
```

## 5. 核心实体关系

```text
Asset
 ├── Files
 ├── Protocols
 ├── Parameters
 ├── Verification Results
 ├── Dependencies
 ├── Mappings
 ├── Debug Cases
 └── Documents
```

第一版数据库建议包含以下实体：

### assets

- id
- name
- display_name
- kind
- category
- version
- description
- metadata_path
- root_path
- status
- created_at
- updated_at

### tags

- id
- name

### asset_tags

- asset_id
- tag_id

### protocols

- id
- name
- version
- direction

### asset_protocols

- asset_id
- protocol_id
- direction

### dependencies

- asset_id
- dependency_asset_id
- version_constraint
- relation

### mappings

- id
- asset_id
- source_transaction
- target_transaction
- ordering
- split_behavior
- response_required
- error_mapping
- notes

### verification_results

- id
- asset_id
- check_type
- status
- command
- report_path
- checked_at
- notes

### knowledge_cases

- id
- title
- case_type
- protocol
- symptom
- root_cause
- trigger_condition
- resolution
- notes

## 6. 状态定义

资产状态：

```text
draft
simulation_checked
lint_checked
cdc_reviewed
formal_checked
synthesis_checked
production_ready
deprecated
```

验证状态：

```text
not_run
passed
failed
partial
waived
unknown
```

状态只表示记录状态，不宣称工具结果一定正确。报告路径和备注必须保留，便于追溯。

## 7. 第一版必填字段

为了降低维护成本，第一版只要求：

- name
- schema_version
- kind
- category
- description
- version
- tags
- files
- verification

Bridge 类型额外建议填写：

- input/output protocol
- source/target transaction
- ordering
- response_required
- error_mapping

## 8. 不纳入个人资产库的内容

以下内容默认不直接复制进个人平台：

- 公司专有 RTL
- 未公开协议实现细节
- 受限的设计文档
- 公司内部路径和账号信息
- 不能脱离项目环境运行的脚本

这些内容可以抽象为通用模板、设计原则、验证方法和匿名化案例。
