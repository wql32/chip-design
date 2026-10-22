/* GitHub Pages catalog interactions. Local Python pages keep their GET forms. */
(function () {
  "use strict";

  const fields = {
    assets: ["q", "category", "protocol", "status", "tag", "sort", "scope", "view"],
    index: ["q"],
    mappings: ["q", "source", "direction", "response"],
  };
  const defaults = {sort: "name", scope: "library", view: "table"};
  const choices = {
    sort: ["name", "category", "status", "updated"],
    scope: ["library", "all", "samples"],
    view: ["table", "cards"],
  };

  function readState(search, kind) {
    const params = new URLSearchParams(search);
    const state = {};
    for (const field of fields[kind]) {
      let value = params.get(field) || defaults[field] || "";
      if (choices[field] && !choices[field].includes(value)) value = defaults[field];
      state[field] = field === "q" ? value.trim() : value;
    }
    return state;
  }

  function compare(a, b) {
    return a < b ? -1 : a > b ? 1 : 0;
  }

  function selectEntries(kind, entries, state) {
    const needle = (state.q || "").trim().toLowerCase();
    const result = entries.filter((entry) => {
      if (needle && !entry.search.includes(needle)) return false;
      if (kind === "assets") {
        if (state.scope === "library" && entry.sample) return false;
        if (state.scope === "samples" && !entry.sample) return false;
        if (state.category && entry.category !== state.category) return false;
        if (state.protocol && !entry.protocols.includes(state.protocol)) return false;
        if (state.status && entry.status !== state.status) return false;
        if (state.tag && !entry.tags.includes(state.tag)) return false;
      } else if (kind === "mappings") {
        for (const field of ["source", "direction", "response"]) {
          if (state[field] && entry[field] !== state[field]) return false;
        }
      }
      return true;
    });
    if (kind === "assets") {
      result.sort((a, b) => {
        let primary = 0;
        if (state.sort === "category") primary = compare(a.category.toLowerCase(), b.category.toLowerCase());
        if (state.sort === "status") primary = compare(a.status_label, b.status_label);
        if (state.sort === "updated") primary = compare(b.updated, a.updated);
        return primary || compare(a.name, b.name) || compare(a.key, b.key);
      });
    }
    return result;
  }

  // Pure selection functions are also exercised by the publish regression.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {readState, selectEntries};
  }
  if (typeof document === "undefined") return;

  const dataNode = document.getElementById("snapshot-data");
  if (!dataNode) return;
  const {kind, entries} = JSON.parse(dataNode.textContent);
  const form = document.querySelector(".filter-panel form");
  const count = document.querySelector("[data-result-count]");
  const empty = document.querySelector("[data-empty]");
  const containers = [...document.querySelectorAll("[data-results]")].map((element) => ({
    element,
    parent: element.querySelector("tbody") || element,
    nodes: new Map([...element.querySelectorAll("[data-entry]")].map((node) => [node.dataset.entry, node])),
  }));
  let state;

  function urlFor(nextState) {
    const url = new URL(window.location.href);
    url.search = "";
    for (const field of fields[kind]) {
      const value = nextState[field];
      if (value && value !== defaults[field]) url.searchParams.set(field, value);
    }
    return url.pathname + url.search + url.hash;
  }

  function render() {
    state = readState(window.location.search, kind);
    const selected = selectEntries(kind, entries, state);
    for (const {element, parent, nodes} of containers) {
      for (const node of nodes.values()) node.hidden = true;
      const fragment = document.createDocumentFragment();
      for (const entry of selected) {
        const node = nodes.get(String(entry.key));
        node.hidden = false;
        fragment.appendChild(node);
      }
      parent.appendChild(fragment);
      element.hidden = selected.length === 0 || (kind === "assets" && element.dataset.results !== state.view);
    }
    empty.hidden = selected.length > 0;
    const unit = kind === "assets" ? "个结果" : kind === "index" ? "个索引项" : "条 mapping";
    const sampleCount = entries.filter((entry) => entry.sample).length;
    const suffix = kind === "assets" && state.scope === "library" && sampleCount ? `，默认隐藏 ${sampleCount} 个 Sample` : "";
    count.textContent = `共 ${selected.length} ${unit}${suffix}`;

    // A tag can arrive through a shared URL even though it has no visible select.
    if (kind === "assets" && !form.elements.namedItem("tag")) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "tag";
      form.appendChild(input);
    }
    for (const field of fields[kind]) {
      const control = form.elements.namedItem(field);
      if (!control) continue;
      const value = state[field];
      if (control.tagName === "SELECT" && ![...control.options].some((option) => option.value === value)) {
        control.add(new Option(`未知筛选项：${value}`, value));
      }
      control.value = value;
    }
    for (const link of document.querySelectorAll("[data-scope], [data-view]")) {
      const field = link.hasAttribute("data-scope") ? "scope" : "view";
      const value = link.dataset[field];
      const active = state[field] === value;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
      link.href = urlFor({...state, [field]: value});
    }
  }

  function navigate(nextState) {
    const url = urlFor(nextState);
    if (url !== window.location.pathname + window.location.search + window.location.hash) {
      window.history.pushState(null, "", url);
    }
    render();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    navigate({...state, ...Object.fromEntries(new FormData(form))});
  });
  for (const select of form.querySelectorAll("select")) {
    select.addEventListener("change", () => form.requestSubmit());
  }
  for (const link of document.querySelectorAll("[data-scope], [data-view], .clear-filter")) {
    link.addEventListener("click", (event) => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (link.hasAttribute("data-scope")) navigate({...state, scope: link.dataset.scope});
      else if (link.hasAttribute("data-view")) navigate({...state, view: link.dataset.view});
      else navigate(readState("", kind));
    });
  }
  window.addEventListener("popstate", render);
  render();
}());
