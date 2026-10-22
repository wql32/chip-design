# System IP Design Hub MVP

## 启动

以下命令均在 `sysip_hub` 目录下执行。

使用 Python 3.10+（也可使用自己安装的 Python 完整路径）：

```powershell
python start_system_ip_hub.py
```

然后打开：

```text
http://127.0.0.1:8765
```

## 一键发布到 GitHub Pages

在工作目录执行：

```powershell
python publish.py
```

发布脚本会自动完成：

- 检查或启动本地服务
- 执行 Python 编译检查
- 执行单元测试
- 生成 GitHub Pages 静态快照
- 检查静态页面内部链接
- 按 source_manifest.json 白名单同步源工程到仓库 hub-source
- 提交并推送源工程和静态网站到 GitHub；原工作目录使用 .deploy_repo，克隆副本直接使用父仓库

GitHub Pages 公开页面支持浏览器端搜索、组合筛选、排序、Sample 范围和表格/卡片切换；查询条件保存在 URL 中，可直接分享，也支持刷新和浏览器前进/后退。资产搜索覆盖 README、Feature、设计模式和问题索引，设计模式、问题索引和 Bridge Mapping 也可直接检索。

公开站点的“本地维护”页说明导入、编辑和删除流程，不提供需要服务器处理的表单。发布检查会拦截失效页面链接、缺失脚本和遗漏的本地操作控件。JavaScript 未启用时仍可浏览全部条目，但不能筛选。

只构建和检查、不提交推送时使用：

```powershell
python publish.py --no-push
```

自定义 Git commit 信息：

```powershell
python publish.py -m "Update AXI bridge notes"
```

## 资产扫描

服务启动时会自动扫描 `assets/` 下的 `metadata.yaml`、`metadata.yml` 和 `metadata.json`。

也可以手动触发：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8765/api/catalog/scan
```

## 当前 MVP 功能

- SQLite 资产索引
- 资产分类和搜索
- 标签和协议索引
- 依赖记录
- 资产详情页
- Metadata 查看
- 健康检查 API
- 本地文件根目录约束

第一版 metadata 使用 JSON 语法保存为 `metadata.yaml`，这是合法的 YAML 子集，可以在没有第三方 YAML 包的环境下运行。后续安装 YAML 解析器后再支持完整 YAML 语法。

## 环境变量

```text
SYSTEM_IP_ASSET_ROOT=自定义资产根目录
SYSTEM_IP_DB=自定义 SQLite 文件路径
```

当前版本只读展示资产文件，不在线编辑 RTL，也不执行资产目录中的命令。

### 验证状态范围

基础 `rtl_component`/`component` 资产默认只展示：

- simulation
- lint
- synthesis

CDC、formal 和 performance 属于系统集成或专项验证维度，默认保留给 Bridge 和系统级资产；如有特殊组件需要增加检查项，可在 metadata 中使用 `verification_scope` 覆盖默认范围。

## 已导入的公开 RTL 资产

当前已录入 `https://wql32.github.io/chip-design/#codes` 中的 16 个模块，覆盖：

- FIFO 与缓冲：5 个
- 仲裁与调度：2 个
- CDC 与时钟：2 个
- AXI 总线接口：1 个
- 存储与查找：3 个
- 编解码与选择：3 个

这些条目保存模块名称、分类、用途、标签、限制和本地资产信息；RTL 源码与逐模块 README 已同步到各资产目录，资产详情页可以直接查看本地 Verilog 文件和设计说明，不再依赖原始代码或外部文档链接。

源码同步来源为公开仓库的浅克隆和网页内嵌源码提取；后续如上游更新，建议通过版本号/commit 做差异检查后再同步，避免覆盖本地注释或修改。

## 页面

- `/`：Dashboard
- `/assets`：资产库和搜索
- `/protocols`：协议索引
- `/mappings`：PCIe/CXL/AXI Bridge transaction mapping
- `/verification`：验证矩阵
- `/dependencies`：依赖关系
- `/report`：资产健康度报告
- `/templates/rtl-module-design-review`：RTL 模块设计与复盘模板
- `/examples/axi-channel-slice`：基于现有 AXI Channel Slice RTL 的七章填写示例

## 测试

在 sysip_hub 目录运行回归测试：

```powershell
python -m unittest discover -s ../tests -v
```

测试只使用临时目录，不会修改 `assets/` 或现有 RTL 工具。

## 源工程版本控制与恢复

程序、公开资产、模板、测试与发布脚本均由 source_manifest.json 管理，源工程同步到发布仓库 hub-source；生成网页仍在 system-ip-hub。数据库、缓存、工具安装包、凭据和未经审核的资产不参与同步。

完整克隆、恢复、开发与备份流程见 [SOURCE_CONTROL.md](SOURCE_CONTROL.md)。在新电脑上可从仓库 hub-source 运行服务，metadata 会重建本地数据库。新增文件或公开资产需要先审查并更新白名单；未审核资产会阻止网页导出。
