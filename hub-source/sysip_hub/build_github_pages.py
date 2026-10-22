from __future__ import annotations

import json
import os
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import urlopen

if __package__:
    from .public_source import deploy_repo, validate_public_assets
else:
    from public_source import deploy_repo, validate_public_assets


SERVER = os.environ.get("SYSTEM_IP_SERVER", "http://127.0.0.1:8765")
WORKSPACE = Path(__file__).resolve().parent
PROJECT_ROOT = WORKSPACE.parent
OUTPUT = deploy_repo(PROJECT_ROOT) / "system-ip-hub"
BASE = "/chip-design/system-ip-hub"


class PublicHTML(HTMLParser):
    """Remove local-only controls, including their URLs and nested content."""

    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.output: list[str] = []
        self.skipped_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        local = "local-only" in (dict(attrs).get("class") or "").split()
        if self.skipped_depth or local:
            if tag not in self.VOID_TAGS:
                self.skipped_depth += 1
        else:
            self.output.append(self.get_starttag_text())

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self.skipped_depth and "local-only" not in (dict(attrs).get("class") or "").split():
            self.output.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        if self.skipped_depth:
            if tag not in self.VOID_TAGS:
                self.skipped_depth -= 1
        else:
            self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.skipped_depth:
            self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    def handle_decl(self, decl: str) -> None:
        self.handle_data(f"<!{decl}>")

    def handle_comment(self, data: str) -> None:
        self.handle_data(f"<!--{data}-->")


def fetch(path: str) -> str:
    with urlopen(SERVER + path, timeout=10) as response:
        return response.read().decode("utf-8")


def prepare_html(html: str, route: str) -> str:
    if urlsplit(route).path == "/import":
        guide = """<main id="main-content"><div class='eyebrow'>LIBRARY / LOCAL MAINTENANCE</div>
<h1>本地维护</h1><p class='muted'>公开站点支持浏览、搜索和筛选。新增资产、编辑 README、修改关联和删除资产通过本地服务完成。</p>
<div class='card'><h2>更新资产的流程</h2><ol><li>在本机的 <code>sysip_hub</code> 目录运行 <code>python start_system_ip_hub.py</code>。</li><li>打开 <a href='http://127.0.0.1:8765'>本地设计资产库</a>，使用“导入 RTL”或资产详情页的编辑入口更新内容。</li><li>确认修改后，运行 <code>python publish.py</code>，检查通过后会发布到 GitHub Pages。</li><li>发布完成后刷新公开站点；筛选条件可以通过页面 URL 分享。</li></ol><p class='muted'>本地服务中的修改会立即生效；公开站点显示最近一次发布的内容。</p></div><p><a class='secondary-button' href='/assets'>返回资产库</a></p></main>"""
        html = re.sub(r"<main\b[^>]*>.*?</main>", lambda _match: guide, html, count=1, flags=re.DOTALL)
        html = re.sub(r"<title>.*?</title>", "<title>本地维护 - System IP Design Hub</title>", html, count=1, flags=re.DOTALL)
    parser = PublicHTML()
    parser.feed(html)
    parser.close()
    html = "".join(parser.output).replace(">导入 RTL</a>", ">本地维护</a>")
    notice = "<style>.snapshot-only{display:inline!important}a.secondary-button.snapshot-only{display:inline-flex!important}</style><div style='max-width:1320px;margin:12px auto 0;padding:9px 28px;border:1px solid #b9dce5;border-radius:9px;background:#e9f8fb;color:#216477;font-size:13px'>公开资产库 · 支持搜索与筛选 · 更新资产请查看 <a href='/import'>本地维护说明</a></div>"
    html = re.sub(r"(<main\b[^>]*>)", lambda match: notice + match.group(1), html, count=1)
    html = re.sub(r"(href|action)=(['\"])(/[^'\"#]*)\2", lambda match: f"{match.group(1)}={match.group(2)}{rewrite_path(match.group(3))}{match.group(2)}", html)
    if "id='snapshot-data'" in html:
        script = f"<noscript><p class='card'>请启用 JavaScript 以使用搜索、筛选和视图切换。当前展示全部条目（含 Sample）。</p></noscript><script src='{BASE}/static/catalog.js' defer></script>"
        html = html.replace("</body>", script + "</body>")
    return html


def write_page(route: str, relative_output: Path) -> None:
    html = prepare_html(fetch(route), route)
    target = OUTPUT / relative_output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


def rewrite_path(path: str) -> str:
    parts = urlsplit(path)
    if not parts.path.startswith("/") or parts.netloc:
        return path
    return urlunsplit(("", "", BASE + parts.path.rstrip("/") + "/", parts.query, parts.fragment))


def main() -> None:
    assets = json.loads(fetch("/api/assets"))
    validate_public_assets(PROJECT_ROOT, assets)
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to overwrite existing export: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    pages = {
        "/": Path("index.html"),
        # Embed every asset, including Samples, so browser-side scope switching
        # and filtering can work without a Python server or API requests.
        "/assets?scope=all": Path("assets/index.html"),
        "/import": Path("import/index.html"),
        "/patterns": Path("patterns/index.html"),
        "/problems": Path("problems/index.html"),
        "/templates/rtl-module-design-review": Path("templates/rtl-module-design-review/index.html"),
        "/examples/axi-channel-slice": Path("examples/axi-channel-slice/index.html"),
        "/protocols": Path("protocols/index.html"),
        "/mappings": Path("mappings/index.html"),
        "/dependencies": Path("dependencies/index.html"),
        "/report": Path("report/index.html"),
    }
    for route, output in pages.items():
        write_page(route, output)
    (OUTPUT / "static").mkdir()
    shutil.copy2(WORKSPACE / "static" / "catalog.js", OUTPUT / "static" / "catalog.js")

    for asset in assets:
        name = asset["name"]
        write_page(f"/assets/{quote(name)}", Path("assets") / name / "index.html")
        root = Path(asset["root_path"])
        for item in root.rglob("*"):
            if not item.is_file():
                continue
            relative = item.relative_to(root).as_posix()
            # Keep the original asset files beside the browsable snapshot so
            # the GitHub repository remains useful for cloning and reuse.
            source_copy = OUTPUT / "assets" / name / Path(relative)
            source_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, source_copy)
            if item.name in {"metadata.yaml", "metadata.yml", "metadata.json"}:
                continue
            route = f"/assets/{quote(name)}/file/{quote(relative)}"
            output = Path("assets") / name / "file" / Path(relative) / "index.html"
            write_page(route, output)

    (OUTPUT / "README.md").write_text(
        "# System IP Design Hub\n\nStatic GitHub Pages snapshot of the local RTL/DMA/AXI/PCIe/CXL design asset hub.\n\nLocal-only operations such as RTL import, metadata editing and asset deletion remain available in the Python local service.\n",
        encoding="utf-8",
    )
    print(f"Exported {len(assets)} assets to {OUTPUT}")


if __name__ == "__main__":
    main()
