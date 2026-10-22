from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sysip_hub.public_source import deploy_repo, safe_path, source_files, sync_public_source, validate_public_assets


class PublicSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix=".system_ip_hub_source_test_", dir=Path.cwd())
        self.root = Path(self.temp.name)
        self.project = self.root / "workspace"
        self.repo = self.project / ".deploy_repo"
        (self.repo / ".git").mkdir(parents=True)
        self.hub = self.project / "sysip_hub"
        self.hub.mkdir()
        (self.hub / "SOURCE_CONTROL.md").write_text("# Restore guide", encoding="utf-8")
        (self.hub / "source.gitignore").write_text("*.db\n", encoding="utf-8")
        (self.hub / "app.py").write_text("print('public')\n", encoding="utf-8")
        self.asset = self.hub / "assets/public_fifo"
        self.asset.mkdir(parents=True)
        (self.asset / "metadata.yaml").write_text('{"name":"fifo"}', encoding="utf-8")
        (self.asset / "fifo.v").write_text("module fifo; endmodule\n", encoding="utf-8")
        self.manifest = {"schema_version": 1, "project_files": ["sysip_hub/app.py"],
                         "public_asset_roots": ["sysip_hub/assets/public_fifo"]}
        self.save_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def save_manifest(self) -> None:
        (self.hub / "source_manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def sync(self) -> dict:
        with contextlib.redirect_stdout(io.StringIO()):
            return sync_public_source(self.project, self.repo)

    def test_only_approved_sources_are_copied_and_hashes_are_stable(self) -> None:
        (self.hub / "private.db").write_text("local database", encoding="utf-8")
        (self.hub / ".env").write_text("private", encoding="utf-8")
        (self.asset / "wave.vcd").write_text("local wave", encoding="utf-8")
        (self.hub / "internal.v").write_text("company RTL", encoding="utf-8")
        first = self.sync()
        self.assertEqual(first, self.sync())
        self.assertEqual(len(first["files"]), 5)
        names = list(first["files"])
        self.assertFalse(any("private" in name or "internal" in name or "wave" in name for name in names))
        self.assertTrue((self.repo / "hub-source/sysip_hub/assets/public_fifo/fifo.v").is_file())

    def test_removed_owned_files_do_not_remove_unmanaged_files(self) -> None:
        self.sync()
        target = self.repo / "hub-source"
        (target / "personal-note.txt").write_text("keep", encoding="utf-8")
        self.manifest["project_files"] = []
        self.save_manifest()
        self.sync()
        self.assertFalse((target / "sysip_hub/app.py").exists())
        self.assertTrue((target / "personal-note.txt").exists())

    def test_unknown_destination_file_is_not_overwritten(self) -> None:
        target = self.repo / "hub-source/sysip_hub"
        target.mkdir(parents=True)
        (target / "app.py").write_text("user changes", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            self.sync()
        self.assertEqual((target / "app.py").read_text(), "user changes")

    def test_managed_destination_edits_are_not_overwritten_or_deleted(self) -> None:
        self.sync()
        target = self.repo / "hub-source/sysip_hub/app.py"
        target.write_text("local edits", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "local edits"):
            self.sync()
        self.manifest["project_files"] = []
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "local edits"):
            self.sync()
        self.assertEqual(target.read_text(), "local edits")

    def test_escape_paths_runtime_and_credentials_fail_before_copy(self) -> None:
        for relative in ("../outside", ".env", "sysip_hub/../outside", "__pycache__/x.py", "sysip_hub/private.db", "sysip_hub/credentials.json", "sysip_hub/secret.key"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                safe_path(self.project, relative)
        (self.hub / "app.py").write_text("-----BEGIN " + "PRIVATE KEY-----", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "credential"):
            self.sync()
        self.assertFalse((self.repo / "hub-source").exists())

    def test_new_asset_and_wrong_server_cannot_be_exported(self) -> None:
        assets = [{"root_path": str(self.asset)}]
        validate_public_assets(self.project, assets)
        for unsafe in ([], assets + [{"root_path": str(self.hub / "assets/private")}], [{"root_path": str(self.root / "other")} ]):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                validate_public_assets(self.project, unsafe)

    def test_old_workspace_and_fresh_clone_choose_correct_repo(self) -> None:
        self.assertEqual(deploy_repo(self.project), self.repo)
        self.assertEqual(deploy_repo(self.repo / "hub-source"), self.repo)

    def test_real_source_can_rebuild_catalog_from_clean_copy(self) -> None:
        real_root = Path(__file__).resolve().parents[1]
        clone = self.root / "fresh-clone"
        (clone / ".git").mkdir(parents=True)
        with contextlib.redirect_stdout(io.StringIO()):
            snapshot = sync_public_source(real_root, clone)
        restored = clone / "hub-source"
        self.assertGreater(len(snapshot["files"]), 100)
        self.assertFalse(list(restored.rglob("*.db")))
        script = "\n".join([
            "from pathlib import Path",
            "from sysip_hub.system_ip_hub.catalog import Catalog",
            "from sysip_hub import publish, build_github_pages",
            "from sysip_hub.system_ip_hub import app",
            "from http.server import ThreadingHTTPServer",
            "from urllib.request import urlopen",
            "import threading, json",
            "root = Path.cwd()",
            "catalog = Catalog(root / 'sysip_hub/assets', root / 'restore-test.db')",
            "result = catalog.scan()",
            "assert result['scanned'] == 23 and not result['errors'], result",
            "assert publish.DEPLOY_REPO == root.parent",
            "assert build_github_pages.OUTPUT == root.parent / 'system-ip-hub'",
            "assert (root / 'sysip_hub/data/rtl_module_design_review_template.md').is_file()",
            "app.catalog.scan()",
            "server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)",
            "thread = threading.Thread(target=server.serve_forever, daemon=True)",
            "thread.start()",
            "build_github_pages.SERVER = f'http://127.0.0.1:{server.server_port}'",
            "try:",
            "    build_github_pages.main()",
            "    publish.check_static_links(root.parent / 'system-ip-hub')",
            "finally:",
            "    server.shutdown(); server.server_close(); thread.join()",
            "assert len(list((root.parent / 'system-ip-hub').rglob('*.html'))) == 84",
            "print('RESTORE PASS: 23 assets, source imports, publish paths, 84 exported pages')",
        ])
        result = subprocess.run([sys.executable, "-c", script], cwd=restored,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESTORE PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
