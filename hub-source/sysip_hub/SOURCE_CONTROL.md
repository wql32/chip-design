# System IP Hub · 可维护源工程

本目录是知识站点的源工程，不是静态网页。Python 3.10+ 标准库即可启动；Node 和 HDL 工具只用于对应测试，不是浏览站点的必需依赖。

## 仓库结构

```text
chip-design/
├── hub-source/                  # 在这里维护程序、模板和公开资产
│   ├── sysip_hub/
│   │   ├── system_ip_hub/        # Python 服务、索引与 RTL 信息提取
│   │   ├── assets/               # 已确认公开的 RTL、README、metadata
│   │   ├── data/                 # 设计模板、示例、验证记录（不含数据库）
│   │   ├── static/               # 浏览器交互代码
│   │   ├── source_manifest.json  # 明确的公开文件、资产目录白名单
│   │   ├── public_source.py      # 安全同步与仓库路径定位
│   │   └── publish.py            # 检查、源工程同步、静态导出、提交推送
│   ├── tests/                    # 站点测试、RTL 回归运行器及依赖说明
│   ├── SOURCE_SNAPSHOT.json      # 自动生成的源文件清单与 SHA-256
│   └── .gitignore
└── system-ip-hub/                # 自动生成网站，勿在这里直接修改
```

原本的 index.html、mx_rtl 和其他网页保持不变。GitHub Pages 地址仍是 `/chip-design/system-ip-hub/`。

## 换电脑或源目录丢失后的恢复

```powershell
git clone https://github.com/wql32/chip-design.git
cd chip-design/hub-source
python sysip_hub/start_system_ip_hub.py
```

打开 http://127.0.0.1:8765 。启动会从 metadata 重建本机 SQLite 索引，不需要复制旧数据库。程序只绑定 127.0.0.1，不建议直接作为公网编辑服务器使用。

本地编辑以 hub-source 下文件为准：页面与高亮修改 `sysip_hub/system_ip_hub/app.py`，浏览器筛选修改 `sysip_hub/static/catalog.js`，模块文档和状态修改对应资产 README/metadata，设计模板修改 `sysip_hub/data/`。

不要同时把旧工作目录与仓库副本作为主编辑源。迁移后请选择一份继续维护，避免发布时互相覆盖。

## 修改、检查和发布

以下命令均在 hub-source 目录执行：

```powershell
# 网站与模型测试。缺少可选 HDL 工具时，对应测试会显示 skipped。
python -m unittest discover -s tests -v

# 可选：浏览器端筛选测试，需要 Node.js。
node --test tests/static_catalog.test.cjs

# 完整构建预览：不提交、不推送。
python sysip_hub/publish.py --no-push

# 检查源工程与静态网站的 diff，再正式提交推送。
git diff --stat
git status --short
python sysip_hub/publish.py -m "Update design knowledge base"
```

发布脚本自动识别“旧工作目录/.deploy_repo”或“克隆仓库/hub-source”两种布局。静态输出固定到仓库根目录 system-ip-hub，不会生成嵌套仓库。

已有 8765 服务时会校验资产根目录，不能把另一份工程的内容误发布。存在已暂存改动时发布中止，避免把无关提交夹带进去。

RTL 检查器安装方法与真实仿真范围见 tests/rtl_priority/README.md。没有 pyslang/Icarus 的新电脑仍能浏览网站，但 skipped 不等于 HDL 验证通过，不可据此修改已有验证结论。

## 什么可以公开

source_manifest.json 明确列出程序/文档/测试文件和 23 个现有公开资产根目录。资产内只允许文本源码、Markdown 和 JSON/YAML 元数据。发布前同时校验网站资产集合，未审核的新导入资产不能绕过白名单进入静态网站。

新增公开资产前：确认来源、授权与内容可公开，再将其相对目录加入 public_asset_roots。新增程序/模板/测试文件需加入 project_files。新目录中的未知扩展名不会自动纳入源备份；确实需要时应审查同步规则。

**公司 RTL、协议内部资料、项目路径、凭据、客户数据不可放进此公开工程。** 白名单和私钥/token 检测只是辅助防线，不是完整秘密扫描器，最终仍需人工检查 Git diff。原 FF array 版权声明保持不变，本工程不为第三方 RTL 重新授权。

不保存数据库、缓存、日志、虚拟环境、HDL 工具安装包、.env、密钥、.codex、原始上游仓库副本及本机测试残留。运行器按当前工程定位路径，公开使用说明不依赖个人电脑绝对目录。

## 备份与回滚

只有成功提交并推送后，GitHub 才有这一版的异地副本；未提交工作仍只在本机。提交前用 git diff 检查，提交后用 git log 和 git status 确认。其他机器恢复时从仓库克隆，并运行上述测试与预览命令。

SQLite 只是可重建索引，不能代替 README/metadata/模板的版本控制。公司保密资产需要另行保存到私有离线工程，不应通过本公开备份流程处理。

需要历史版本时，优先在单独目录克隆并 checkout 指定 commit 检查；不要在有未提交修改的主工作目录强制 reset。公开网站的回退应在确认目标版本后另行执行，不自动重写历史。

SOURCE_SNAPSHOT.json 记录文本统一为 LF 换行后的 SHA-256，便于检查副本是否与源文件一致；它不是数字签名。同步不会覆盖或删除目标副本中尚未协调的本地内容修改；遇到冲突会中止，需先选择保留哪一份。
