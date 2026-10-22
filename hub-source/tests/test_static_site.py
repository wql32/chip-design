from __future__ import annotations

import contextlib
import gc
import io
import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from sysip_hub import build_github_pages as build
from sysip_hub import publish
from sysip_hub.system_ip_hub import app
from sysip_hub.system_ip_hub.catalog import Catalog


def embedded_data(html: str) -> dict:
    match = re.search(r"<script id='snapshot-data' type='application/json'>(.*?)</script>", html, re.DOTALL)
    assert match, "Missing browser-side catalog data"
    return json.loads(match.group(1))


class StaticExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix=".system_ip_hub_static_test_", dir=Path.cwd())
        cls.root = Path(cls.temp.name)
        assets = cls.root / "assets"
        for name, sample in (("wql32_axi_slice", False), ("pcie_bridge_sample", True)):
            asset = assets / name
            asset.mkdir(parents=True)
            metadata = {
                "name": name, "display_name": name, "kind": "component",
                "category": "bridges" if sample else "axi", "sample": sample,
                "status": "draft" if sample else "needs_fix", "tags": ["ready-valid"], "protocols": ["AXI4"],
                "features": ["backpressure"], "design_patterns": ["ready-valid pipeline"],
                "problem_index": ["Stall handling"],
            }
            if sample:
                metadata["mapping"] = [{"source_transaction": "pcie_read", "target_transaction": "axi_read", "response_required": True}]
            (asset / "metadata.yaml").write_text(json.dumps(metadata), encoding="utf-8")
            (asset / "README.md").write_text("# 设计说明\n独有检索词 </script><script>alert(1)</script>", encoding="utf-8")
        cls.catalog = Catalog(assets, cls.root / "catalog.db")
        manifest_dir = cls.root / "sysip_hub"
        manifest_dir.mkdir()
        (manifest_dir / "source_manifest.json").write_text(json.dumps({
            "schema_version": 1, "project_files": [],
            "public_asset_roots": ["assets/wql32_axi_slice", "assets/pcie_bridge_sample"],
        }), encoding="utf-8")
        cls.catalog.scan()
        cls.catalog_patch = patch.object(app, "catalog", cls.catalog)
        cls.catalog_patch.start()
        cls.logging_patch = patch.object(app.Handler, "log_message")
        cls.logging_patch.start()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.catalog_patch.stop()
        cls.logging_patch.stop()
        # sqlite connection context managers commit but leave cyclic connection
        # objects for GC; release those handles before Windows removes fixtures.
        gc.collect()
        cls.temp.cleanup()

    def fetch(self, route: str) -> str:
        with urlopen(self.url + route) as response:
            return response.read().decode("utf-8")

    def test_local_get_search_and_filters_still_work(self) -> None:
        data = embedded_data(self.fetch("/assets?q=backpressure&protocol=AXI4"))
        self.assertEqual([entry["key"] for entry in data["entries"]], ["wql32_axi_slice"])
        self.assertEqual(embedded_data(self.fetch("/assets?q=does-not-exist"))["entries"], [])
        self.assertEqual(len(embedded_data(self.fetch("/assets?scope=samples"))["entries"]), 1)
        self.assertEqual(embedded_data(self.fetch("/mappings?source=CXL"))["entries"], [])
        self.assertIn("/assets/wql32_axi_slice/edit", self.fetch("/report"))
        self.assertIn("method='post'", self.fetch("/import"))

    def test_export_has_all_data_and_no_local_actions(self) -> None:
        output = self.root / "export"
        with patch.object(build, "SERVER", self.url), patch.object(build, "OUTPUT", output), patch.object(build, "PROJECT_ROOT", self.root), contextlib.redirect_stdout(io.StringIO()):
            build.main()
            publish.check_static_links(output)
        assets_html = (output / "assets/index.html").read_text(encoding="utf-8")
        data = embedded_data(assets_html)
        self.assertEqual(len(data["entries"]), 2)
        self.assertIn("独有检索词 </script>", data["entries"][0]["search"])
        self.assertNotIn("</script><script>alert", assets_html)
        self.assertTrue((output / "static/catalog.js").is_file())
        for html_file in output.rglob("*.html"):
            parser = publish.StaticPageLinks()
            parser.feed(html_file.read_text(encoding="utf-8"))
            self.assertFalse(parser.errors, html_file)
            self.assertFalse(any("/edit/" in link or "/delete/" in link for link in parser.links), html_file)
        guide = (output / "import/index.html").read_text(encoding="utf-8")
        self.assertIn("本地维护", guide)
        self.assertNotIn("<form", guide)
        self.assertIn("本地维护说明", (output / "report/index.html").read_text(encoding="utf-8"))

    def test_local_only_removal_handles_nested_and_void_elements(self) -> None:
        html = '<main><form class="local-only"><div><input name="x"><button>删除</button></div></form><p>保留 &amp; 显示</p></main>'
        public = build.prepare_html(html, "/")
        self.assertNotIn("<form", public)
        self.assertIn("保留 &amp; 显示", public)

    def test_rewrite_preserves_query_and_fragment(self) -> None:
        self.assertEqual(build.rewrite_path("/assets?category=axi&view=cards#results"), build.BASE + "/assets/?category=axi&view=cards#results")
        self.assertEqual(build.rewrite_path("/assets/a/file/test.sv"), build.BASE + "/assets/a/file/test.sv/")

    def test_link_check_rejects_edit_links_and_missing_scripts(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".system_ip_hub_links_test_", dir=Path.cwd()) as temp:
            output = Path(temp)
            for content in (f'<a href="{build.BASE}/assets/missing/edit/">编辑</a>', f'<script src="{build.BASE}/missing.js"></script>', '<form method="post"></form>'):
                (output / "index.html").write_text(content, encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                    publish.check_static_links(output)


if __name__ == "__main__":
    unittest.main()
