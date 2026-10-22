const {test} = require("node:test");
const assert = require("node:assert/strict");
const {readState, selectEntries} = require("../sysip_hub/static/catalog.js");

const assets = [
  {key: "a", name: "alpha", sample: false, search: "alpha 独有检索词 backpressure", category: "fifo", protocols: ["AXI4"], tags: ["buffer"], status: "draft", status_label: "Draft", updated: "2026-01-01"},
  {key: "b", name: "beta", sample: false, search: "beta backpressure", category: "axi", protocols: ["AXI4"], tags: ["bridge"], status: "needs_fix", status_label: "Needs Fix", updated: "2026-02-01"},
  {key: "s", name: "sample", sample: true, search: "sample", category: "bridges", protocols: ["PCIe"], tags: [], status: "constrained", status_label: "Constrained", updated: "2026-03-01"},
];
const select = (search) => selectEntries("assets", assets, readState(search, "assets")).map((entry) => entry.key);

test("default scope, Samples and combined asset filters", () => {
  assert.deepEqual(select(""), ["a", "b"]);
  assert.deepEqual(select("?scope=all"), ["a", "b", "s"]);
  assert.deepEqual(select("?scope=samples"), ["s"]);
  assert.deepEqual(select("?q=BACKPRESSURE&category=axi&protocol=AXI4&status=needs_fix&tag=bridge"), ["b"]);
  assert.deepEqual(select("?q=独有检索词"), ["a"]);
  assert.deepEqual(select("?q=missing"), []);
  assert.deepEqual(select("?category=unknown"), []);
});

test("all sort modes and unknown URL values", () => {
  assert.deepEqual(select("?sort=name"), ["a", "b"]);
  assert.deepEqual(select("?sort=category"), ["b", "a"]);
  assert.deepEqual(select("?scope=all&sort=status"), ["s", "a", "b"]);
  assert.deepEqual(select("?sort=updated"), ["b", "a"]);
  assert.equal(readState("?view=cards", "assets").view, "cards");
  assert.deepEqual(select("?scope=invalid&sort=invalid&view=invalid"), ["a", "b"]);
});

test("pattern and problem searches include descriptions and checks", () => {
  const entries = [{key: "ready-valid", search: "ready-valid 保持 payload 稳定"}];
  assert.equal(selectEntries("index", entries, readState("?q=payload", "index")).length, 1);
  assert.equal(selectEntries("index", entries, readState("?q=missing", "index")).length, 0);
});

test("mapping filters compose with keyword, direction and response", () => {
  const entries = [
    {key: "1", search: "bridge pcie_read axi_read", source: "PCIe", direction: "read", response: "required"},
    {key: "2", search: "bridge pcie_write axi_write", source: "PCIe", direction: "write", response: "not_required"},
    {key: "3", search: "cxl_read axi_read", source: "CXL", direction: "read", response: "required"},
  ];
  const filter = (search) => selectEntries("mappings", entries, readState(search, "mappings")).map((entry) => entry.key);
  assert.deepEqual(filter("?q=bridge&source=PCIe&direction=write&response=not_required"), ["2"]);
  assert.deepEqual(filter("?source=CXL&direction=write"), []);
  assert.deepEqual(filter("?response=required"), ["1", "3"]);
});
