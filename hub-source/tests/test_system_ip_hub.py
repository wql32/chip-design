from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from sysip_hub.system_ip_hub.catalog import Catalog
from sysip_hub.system_ip_hub.rtl_importer import make_draft, scan_project


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dirs: list[Path] = []

    def tearDown(self) -> None:
        for temp_dir in self.temp_dirs:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def make_catalog(self) -> tuple[Catalog, Path]:
        temp_dir = Path.cwd() / "tests" / "fixtures"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dirs.append(temp_dir)
        asset_root = temp_dir
        metadata = {
            "schema_version": 1,
            "name": "test_bridge",
            "display_name": "Test Bridge",
            "version": "1.0.0",
            "kind": "bridge",
            "category": "bridges",
            "description": "Test asset",
            "tags": ["test", "bridge"],
            "protocols": {"input": ["PCIe"], "output": ["AXI4"]},
            "dependencies": [{"name": "test_fifo", "version_constraint": ">=1.0.0", "relation": "required"}],
            "verification": {"simulation": "passed", "formal": "not_run", "last_checked": "2026-08-16"},
            "mapping": [{
                "source_transaction": "pcie_read",
                "target_transaction": "axi_read",
                "ordering": "preserve",
                "split_behavior": "possible",
                "response_required": True,
                "error_mapping": "rresp_to_completion",
                "field_mapping": [{"source": "tag", "target": "id", "rule": "track"}],
            }],
        }
        (asset_root / "metadata.yaml").write_text(json.dumps(metadata), encoding="utf-8")
        (asset_root / "README.md").write_text("# Test Bridge", encoding="utf-8")
        return Catalog(asset_root, temp_dir / f"catalog_{self._testMethodName}.db"), temp_dir

    def test_scan_and_search(self) -> None:
        catalog, _ = self.make_catalog()
        result = catalog.scan()
        self.assertEqual(result["scanned"], 1)
        self.assertFalse(result["errors"])
        self.assertEqual(len(catalog.list_assets(query="bridge")), 1)
        self.assertEqual(catalog.list_assets()[0]["tags"], ["bridge", "test"])

    def test_mapping_verification_and_dependencies(self) -> None:
        catalog, _ = self.make_catalog()
        catalog.scan()
        asset = catalog.get_asset("test_bridge")
        self.assertEqual(len(asset["mappings"]), 1)
        self.assertEqual(len(asset["mappings"][0]["field_mapping"]), 1)
        self.assertEqual(len(asset["verification_results"]), 2)
        graph = catalog.dependency_graph()
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["missing_dependencies"], ["test_fifo"])

    def test_scan_is_idempotent(self) -> None:
        catalog, _ = self.make_catalog()
        catalog.scan()
        catalog.scan()
        self.assertEqual(catalog.summary()["total_assets"], 1)
        self.assertEqual(len(catalog.mappings()), 1)

    def test_rtl_importer_extracts_module_interface(self) -> None:
        fixture_root = Path(__file__).parent / "rtl_fixture"
        result = scan_project(fixture_root)
        modules = [module for module in result["modules"] if module["name"] == "import_sample"]
        self.assertEqual(len(modules), 1)
        module = modules[0]
        self.assertEqual([item["name"] for item in module["parameters"]], ["DATA_WIDTH", "DEPTH"])
        self.assertEqual([item["name"] for item in module["ports"]], ["i_clk", "i_rst_n", "i_data", "o_valid"])
        self.assertTrue(module["has_clock"])
        self.assertTrue(module["has_reset"])
        self.assertEqual(make_draft(module, result["project_root"])["kind"], "rtl_component")


if __name__ == "__main__":
    unittest.main()
