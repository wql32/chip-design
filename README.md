# Chip Design

个人芯片设计知识与公开 RTL 组件。

- [芯片设计主页](https://wql32.github.io/chip-design/)
- [System IP 设计资产库](https://wql32.github.io/chip-design/system-ip-hub/)
- [可维护源工程与恢复指南](hub-source/README.md)

## 本地运行知识库

```sh
git clone https://github.com/wql32/chip-design.git
cd chip-design/hub-source
python sysip_hub/start_system_ip_hub.py
```

浏览器打开 http://127.0.0.1:8765 。需要 Python 3.10+，基础服务无需额外 Python 依赖；首次启动根据元数据重建本地索引。

`hub-source/` 是源程序、模板、测试及已审核公开资产；`system-ip-hub/` 是自动生成的 GitHub Pages 网页，请勿直接修改生成文件。`mx_rtl/` 保留历史内容，知识库中经过修复的组件以源工程 assets 下版本及其验证说明为准。

发布、公开白名单与数据边界详见源工程指南。本仓库不包含公司保密 RTL；保留各原始组件的版权与授权声明。
