import { chartPath, readJSON, runtime } from "./data.js";
import { chartSeries, numeric } from "./source-charts.js";
import {
  clamp,
  finite,
  matches,
  normalized,
  pareto,
  prepare,
  rank,
  sensitivity,
} from "./engine.js";

const $ = (s) => document.querySelector(s);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]),
  );
const fmt = (v, digits = 1) =>
  finite(v)
    ? v.toLocaleString(undefined, { maximumFractionDigits: digits })
    : "—";
const short = (s, n = 32) =>
  String(s || "").length > n
    ? String(s).slice(0, n - 1) + "…"
    : String(s || "");
const url = (v) => {
  try {
    const u = new URL(v);
    return ["http:", "https:"].includes(u.protocol) ? esc(u.href) : "#";
  } catch {
    return "#";
  }
};
const link = (href, label = "Original source ↗") =>
  `<a href="${url(href)}" target="_blank" rel="noopener noreferrer">${
    esc(label)
  }</a>`;
const providerNames = {
  aa: "Artificial Analysis",
  vals: "Vals AI",
  epoch: "Epoch AI",
  arena: "Arena",
  terminalbench: "Terminal-Bench",
  swebench: "SWE-bench",
};
const colors = {
  "OpenAI": "#c6c6c6",
  "Anthropic": "#d99073",
  "Google": "#82bfa0",
  "Meta": "#79aaf0",
  "Moonshot AI": "#c5a9e7",
  "xAI": "#ac9bed",
  "DeepSeek": "#7894e9",
  "Alibaba": "#e3b679",
  "Z AI": "#b6b4a6",
  "Mistral": "#ed997c",
  "MiniMax": "#db91ae",
  "Xiaomi": "#daa86e",
  "NVIDIA": "#a7c872",
  "Unknown": "#999",
};
const sourceColors = {
  aa: "#b8a1dc",
  vals: "#87b7a6",
  epoch: "#d1ad79",
  arena: "#8aafdc",
  terminalbench: "#b4ba8a",
  swebench: "#cc9ea8",
};
const sourceShapes = {
  aa:
    '<path d="M12 2 21 8 18 20 6 20 3 8Z"/><path d="m12 2 6 18M12 2 6 20M3 8h18" fill="none" stroke="currentColor"/>',
  vals:
    '<ellipse cx="12" cy="7" rx="4" ry="6"/><ellipse cx="17" cy="14" rx="6" ry="4" transform="rotate(-30 17 14)"/><ellipse cx="7" cy="14" rx="6" ry="4" transform="rotate(30 7 14)"/>',
  epoch:
    '<path d="m12 1 2 6 6-3-3 6 6 2-6 2 3 6-6-3-2 6-2-6-6 3 3-6-6-2 6-2-3-6 6 3Z"/>',
  arena:
    '<path d="M12 12V2c7 0 9 7 0 10Zm0 0h10c0 7-7 9-10 0Zm0 0v10c-7 0-9-7 0-10Zm0 0H2c0-7 7-9 10 0Z"/>',
  terminalbench:
    '<path d="m12 2 10 10-10 10L2 12Z"/><path d="m7 7 5 5-5 5m6 0h5" stroke="currentColor" fill="none"/>',
  swebench:
    '<path d="m3 7 7-4 4 7-7 4Zm7 7 7-4 4 7-7 4Z"/><circle cx="17" cy="5" r="3"/>',
};
const sourceMark = (id) =>
  `<svg class="source-mark" viewBox="0 0 24 24" aria-hidden="true" style="fill:${
    sourceColors[id] || "#aaa"
  };color:var(--side)">${sourceShapes[id] || ""}</svg>`;
const palette = [
  "#a6bae8",
  "#e2a687",
  "#9ec5ae",
  "#c6a8dd",
  "#dfc284",
  "#8bc2cb",
  "#d899ad",
  "#b9c08e",
  "#a4a4d4",
  "#c9c9c9",
];
const iconPaths = {
  rankings: "M3 18h18M6 15V9m6 6V4m6 11V7",
  frontier: "M4 3v17h17M8 14l4-4 5 2 3-7",
  matrix: "M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18",
  compare: "M5 4v16m14-16v16M8 8h8M8 16h8m-5-3 3 3-3 3m5-14-3 3 3 3",
  timeline: "M3 19h18M3 4v15m2-4 5-5 4 2 6-8",
  sensitivity: "M3 6h18M3 12h18M3 18h18M7 3v6m10 0v6m-7 0v6",
  distribution: "M3 20h18M5 20v-6h4v6m0 0V7h5v13m0 0V3h5v17",
  benchmarks: "M4 3h16v18H4zM7 7h10M7 12h10M7 17h6",
  sources: "M8 8h8v8H8zM12 2v6m0 8v6M2 12h6m8 0h6",
  charts: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 21v-4l3-3 4 5",
  data: "M3 5h18v14H3zM3 10h18M9 5v14M15 5v14",
  method: "M12 17v-5m0-5h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${
    iconPaths[name] || iconPaths.rankings
  }"/></svg>`;
const views = [
  ["rankings", "Rankings"],
  ["frontier", "Cost & performance"],
  ["matrix", "Benchmark matrix"],
  ["compare", "Compare models"],
  ["timeline", "Timeline"],
  ["sensitivity", "Weight sensitivity"],
  ["distribution", "Distributions"],
  ["charts", "Source charts"],
  ["benchmarks", "Test catalog"],
  ["sources", "Sources & coverage"],
  ["data", "Observation table"],
  ["method", "Scoring"],
];
const defaults = {
  view: "rankings",
  weights: {},
  query: "",
  lab: "",
  access: "",
  effort: "",
  country: "",
  modality: "",
  since: "",
  deprecated: false,
  normalization: "scale",
  missing: "exclude",
  coverage: 100,
  group: "models",
  limit: 25,
  layout: "horizontal",
  color: "lab",
  metric: "cost_usd",
  axisY: "ranking",
  log: true,
  labels: true,
  stacked: false,
  compare: [],
  inspectorTab: "weights",
  selected: null,
  benchSearch: "",
  benchProvider: "",
  benchCategory: "",
  benchKind: "",
  subtasks: false,
  archived: false,
  page: 0,
  distributionBy: "lab",
  timelineAxis: "release",
  sensitivityTarget: "",
  showNav: false,
  showInspector: false,
  hideInspector: false,
  sourceChart: "",
  chartPath: "",
  chartY: "",
  chartX: "",
  chartLabel: "",
  chartMode: "bars",
};
let state = { ...defaults },
  index,
  rows = [],
  rowMap = new Map(),
  chartCache = new Map(),
  loadedChart = null,
  renderPending = false;
try {
  state = {
    ...defaults,
    ...JSON.parse(localStorage.getItem("ai-rankings-state-v1") || "{}"),
  };
} catch {}
try {
  if (location.hash.startsWith("#v1=")) {
    state = {
      ...state,
      ...JSON.parse(decodeURIComponent(escape(atob(location.hash.slice(4))))),
    };
  }
} catch {}
const save = () => {
  const out = { ...state };
  delete out.showNav;
  delete out.showInspector;
  localStorage.setItem("ai-rankings-state-v1", JSON.stringify(out));
};
const selectedTests = () =>
  Object.keys(state.weights).filter((id) =>
    index.benchmarks.has(id) && state.weights[id] > 0
  );
const primary = () => index.benchmarks.get(selectedTests()[0]);
const native = () => selectedTests().length === 1;
const value = (row) => native() ? row.raw : row.score;
const unit = () => native() ? (primary()?.unit || "score") : "custom / 100";
const color = (row) =>
  state.color === "source"
    ? sourceColors[Object.values(row.observations)[0]?.provider] || "#aaa"
    : colors[row.model.lab] ||
      palette[
        Math.abs([...row.model.lab].reduce((a, c) => a + c.charCodeAt(0), 0)) %
        palette.length
      ];
const observation = (row) =>
  row.observations[selectedTests()[0]] || Object.values(row.observations)[0];
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $("#toast").hidden = true, 3500);
}
function empty(title, message) {
  return `<div class="empty"><h2>${esc(title)}</h2><p>${
    esc(message)
  }</p><button data-action="reset-filters">Reset filters</button></div>`;
}
function set(patch, rerender = true) {
  Object.assign(state, patch);
  if (rerender) render();
  save();
}
function options(values, selected, all = "") {
  return (all ? `<option value="">${esc(all)}</option>` : "") +
    values.map((v) => {
      const [id, label] = Array.isArray(v) ? v : [v, v];
      return `<option value="${esc(id)}" ${
        String(selected) === String(id) ? "selected" : ""
      }>${esc(label)}</option>`;
    }).join("");
}
function select(id, values, current, all = "", extra = "") {
  return `<select id="${id}" ${extra}>${
    options(values, current, all)
  }</select>`;
}
function bestBenchmark() {
  return index.data.benchmarks.find((b) =>
    b.provider === "aa" && /intelligence index/i.test(b.name) &&
    b.observation_count > 10 && !b.archived
  ) ||
    index.data.benchmarks.find((b) => b.id === "epoch-eci") ||
    index.data.benchmarks.find((b) =>
      b.kind === "composite" && b.observation_count > 10
    ) || index.data.benchmarks.find((b) => b.observation_count > 0);
}
function preset(name) {
  const bs = index.data.benchmarks.filter((b) =>
    b.observation_count && !b.parent_benchmark_id && !b.archived &&
    !["metric", "trait"].includes(b.kind)
  );
  let picks = [];
  if (name === "balanced") {
    picks = ["Coding", "Science", "Knowledge work", "General"].map((cat) =>
      bs.find((b) =>
        b.provider === "aa" && b.category === cat && b.kind !== "composite"
      )
    ).filter(Boolean);
  } else if (name === "coding") {
    picks = bs.filter((b) =>
      b.provider === "aa" && /FrontierCode 2|Terminal-Bench 4/i.test(b.name)
    ).slice(0, 2);
  } else if (name === "professional") {
    picks = [
      bs.find((b) => b.provider === "vals" && /^Vals Index$/i.test(b.name)),
    ].filter(Boolean);
  } else if (name === "epoch") {
    picks = [
      bs.find((b) =>
        b.provider === "epoch" &&
        (/epoch capabilities index|^eci$/i.test(b.name))
      ),
    ].filter(Boolean);
  } else if (name === "arena") {
    picks = [
      bs.find((b) =>
        b.provider === "arena" && /text/i.test(b.name) &&
        /overall/i.test(b.name) && /style/i.test(b.name)
      ) || bs.find((b) => b.provider === "arena" && /text/i.test(b.name)),
    ].filter(Boolean);
  } else picks = [bestBenchmark()].filter(Boolean);
  if (!picks.length) {
    return toast(
      "No matching source data is available. Choose a test from the catalog.",
    );
  }
  set({
    weights: Object.fromEntries(picks.map((b) => [b.id, 100])),
    view: "rankings",
    page: 0,
    selected: null,
    coverage: 100,
    missing: "exclude",
  });
}
function sidebar() {
  const labs = [...new Set(index.data.models.map((m) => m.lab))].sort();
  const countries = [
    ...new Set(
      index.data.models.map((m) => m.country).filter((v) =>
        typeof v === "string"
      ),
    ),
  ].sort();
  return `<aside class="sidebar quiet-scroll"><div class="nav-label">Charts</div>${
    views.slice(0, 8).map(([id, label]) =>
      `<button class="nav-item ${
        state.view === id ? "active" : ""
      }" data-view="${id}">${icon(id)}${label}</button>`
    ).join("")
  }<div class="divider"></div><div class="nav-label">Evidence</div>${
    views.slice(8).map(([id, label]) =>
      `<button class="nav-item ${
        state.view === id ? "active" : ""
      }" data-view="${id}">${icon(id)}${label}</button>`
    ).join("")
  }<div class="divider"></div><div class="nav-label">Model filters</div><div class="field"><input id="model-query" type="search" aria-label="Search models" placeholder="Find a model…" value="${
    esc(state.query)
  }"></div><label for="lab">Lab</label><div class="field">${
    select("lab", labs, state.lab, "All labs")
  }</div><label for="access">Weights</label><div class="field">${
    select(
      "access",
      [["open", "Open weights"], ["proprietary", "Proprietary"], [
        "unknown",
        "Not reported",
      ]],
      state.access,
      "Any access",
    )
  }</div><label for="effort">Reasoning effort</label><div class="field">${
    select(
      "effort",
      ["max", "xhigh", "high", "medium", "low", "non-reasoning"],
      state.effort,
      "All settings",
    )
  }</div><details style="margin:13px 8px"><summary class="small muted">More filters</summary><label for="country">Country</label>${
    select("country", countries, state.country, "All countries")
  }<label for="modality">Input modality</label>${
    select(
      "modality",
      ["text", "image", "audio", "video"],
      state.modality,
      "All modalities",
    )
  }<label for="since">Released after</label><input id="since" type="date" value="${
    esc(state.since)
  }"><label class="small-check"><input id="deprecated" type="checkbox" ${
    state.deprecated ? "checked" : ""
  }>Include deprecated</label></details><div class="divider"></div>${
    Object.entries(providerNames).filter(([id]) =>
      index.data.sources.some((s) => s.provider === id)
    ).map(([id, name]) => {
      const count = index.data.benchmarks.filter((b) =>
        b.provider === id && b.observation_count
      ).length;
      return `<div class="source-mini"><span>${
        sourceMark(id)
      }${name}</span><span>${count}</span></div>`;
    }).join("")
  }</aside>`;
}
function shell() {
  return `<div class="shell ${state.showNav ? "show-nav" : ""} ${
    state.showInspector ? "show-inspector" : ""
  } ${
    state.hideInspector ? "full-width" : ""
  }"><header class="topbar"><button class="icon-button quiet-button nav-toggle" data-action="nav" aria-label="Toggle navigation">☰</button><div class="brand"><img src="icon.svg" alt="">AI Rankings</div><span class="spacer"></span><span class="refresh-date small muted">${
    index.data.sources.length
      ? `Built ${
        new Date(index.data.generated_at).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        })
      }`
      : "No sources loaded"
  }</span><button class="quiet-button share-button" data-action="share" title="Copy a link containing these settings">Copy view link</button><button class="export-button" data-action="export">Export CSV</button><button class="icon-button" data-action="inspector" title="Toggle controls and evidence" aria-label="Toggle controls and evidence">☷</button></header>${sidebar()}<main class="main quiet-scroll" id="main"></main><aside class="inspector quiet-scroll" id="inspector"></aside><footer class="statusbar"><span>${
    fmt(index.data.models.length, 0)
  } models · ${
    fmt(index.data.benchmarks.filter((b) => b.observation_count).length, 0)
  } tests & slices · ${
    fmt(index.data.observations.length, 0)
  } observations</span><span>${
    native() ? "Original source scale" : "Custom weighted score"
  } · ${
    state.group === "models"
      ? "Best reported per model/test"
      : "Matched effort + agent"
  }</span></footer></div>`;
}
function head(title, description, extra = "") {
  if (
    ["sources", "benchmarks", "charts", "data", "method"].includes(state.view)
  ) {
    return `<div class="page-head"><div class="eyebrow">Source library <span class="badge">Public evidence</span></div><div class="head-row"><h1>${
      esc(title)
    }</h1>${extra}</div><p>${esc(description)}</p></div>`;
  }
  return `<div class="page-head"><div class="eyebrow">${
    native()
      ? esc(
        providerNames[primary()?.provider] || primary()?.provider || "Source",
      )
      : "Selected tests"
  } <span class="badge ${native() ? "" : "custom"}">${
    native() ? "Source score" : "Custom ranking"
  }</span></div><div class="head-row"><h1>${esc(title)}</h1>${extra}</div><p>${
    esc(description)
  }</p></div>`;
}
function commonToolbar(extra = "") {
  const choices = index.data.benchmarks.filter((b) =>
    b.observation_count && !b.archived && !b.parent_benchmark_id &&
    !["metric", "trait"].includes(b.kind)
  );
  const popular = choices.filter((b) =>
    b.kind === "composite" ||
    /intelligence|overall|terminal-bench 4|frontiercode 2/i.test(b.name)
  );
  return `<div class="toolbar">${
    select(
      "quick-test",
      popular.map(
        (b) => [b.id, `${providerNames[b.provider] || b.provider} · ${b.name}`],
      ),
      native() ? selectedTests()[0] : "",
      "Choose a source ranking…",
      'class="wide" aria-label="Source ranking"',
    )
  }<span class="spacer"></span><label for="limit">Show</label>${
    select("limit", [10, 15, 25, 40, 60, 100], state.limit)
  }${extra}</div>`;
}
function note() {
  const selected = selectedTests();
  return `<p class="chart-note">${
    state.group === "models"
      ? "Best reported result per model and test; different tests may use different effort settings or agents."
      : "Rows match the model, reported effort, agent label and inference endpoint across selected tests."
  } ${
    selected.length > 1
      ? `Weights: ${selected.length} tests. ${
        state.normalization === "percentile"
          ? "Snapshot percentiles"
          : "Published scale bounds where available; snapshot percentiles otherwise"
      }. Missing results: ${
        state.missing === "exclude"
          ? "exclude incomplete models"
          : state.missing === "zero"
          ? "explicitly count as zero"
          : "renormalize across available tests"
      }. Minimum weighted coverage ${state.coverage}%.`
      : "Click any result to inspect its exact source, effort, agent and uncertainty."
  }</p>`;
}
function legend(items = rows.slice(0, state.limit)) {
  const groups = new Map();
  items.forEach((r) =>
    groups.set(
      state.color === "source"
        ? providerNames[observation(r)?.provider]
        : r.model.lab,
      color(r),
    )
  );
  return `<div class="legend">${
    [...groups].map(([name, c]) =>
      `<span><i class="swatch" style="background:${c}"></i>${esc(name)}</span>`
    ).join("")
  }</div>`;
}
function svgStart(w, h, label) {
  return `<svg class="chart" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${
    esc(label)
  }">`;
}
function render() {
  if (!index) return;
  const focus = document.activeElement?.id,
    selection = document.activeElement?.selectionStart;
  const scroll = $("#main")?.scrollTop || 0,
    paneScroll = $("#inspector")?.scrollTop || 0;
  rows = rank(index, state);
  rowMap = new Map(rows.map((r) => [r.key, r]));
  $("#app").innerHTML = shell();
  $("#main").innerHTML = renderMain();
  $("#inspector").innerHTML = inspector();
  $("#main").scrollTop = scroll;
  $("#inspector").scrollTop = paneScroll;
  if (focus && document.getElementById(focus)) {
    document.getElementById(focus).focus({ preventScroll: true });
    try {
      document.getElementById(focus).setSelectionRange(selection, selection);
    } catch {}
  }
  if (state.view === "charts") loadSourceChart();
}
function renderMain() {
  if (!index.data.observations.length) {
    return empty(
      "No source snapshots yet",
      "Use Refresh sources after the import adapters are ready.",
    );
  }
  const renderers = {
    rankings: rankingView,
    frontier: frontierView,
    matrix: matrixView,
    compare: compareView,
    timeline: timelineView,
    sensitivity: sensitivityView,
    distribution: distributionView,
    benchmarks: benchmarkView,
    sources: sourcesView,
    data: dataView,
    method: methodView,
    charts: sourceChartsView,
  };
  return (renderers[state.view] || rankingView)();
}
function rankingView() {
  const title = native() ? primary().name : "Weighted ranking";
  return head(
    title,
    native()
      ? (primary().description ||
        "Published evaluation results with source attribution.")
      : "Scores calculated from the selected tests and weights. Click a result for its source measurements.",
  ) +
    commonToolbar(
      `<div class="segmented"><button data-layout="horizontal" class="${
        state.layout === "horizontal" ? "active" : ""
      }" title="Horizontal bars">Bars</button><button data-layout="vertical" class="${
        state.layout === "vertical" ? "active" : ""
      }" title="Vertical bars">Columns</button></div><button class="quiet-button" data-action="svg" title="Download the chart as SVG">↓ SVG</button>`,
    ) + (!rows.length
      ? empty(
        "No models meet this selection",
        "Try fewer tests, a lower coverage threshold, or different model filters.",
      )
      : `<div class="chart-wrap"><div class="chart-title"><div><h3>${
        native() ? "Published " + unit() : "Weighted normalized score"
      }</h3><p>${rows.length} matching ${
        state.group === "models"
          ? "models · best reported per test"
          : "configurations"
      } · ${
        primary()?.higher_is_better === false && native() ? "Lower" : "Higher"
      } is better</p></div><label class="small muted">Color ${
        select("color", [["lab", "Lab"], ["source", "Evaluator"]], state.color)
      }</label>${
        !native()
          ? `<label class="small-check"><input id="stacked" type="checkbox" ${
            state.stacked ? "checked" : ""
          }>Test contributions</label>`
          : ""
      }</div>${barChart(rows.slice(0, state.limit))}</div>${
        state.stacked && !native() ? contributionLegend() : legend()
      }${note()}${table(rows.slice(0, state.limit))}`);
}
function contributionRects(row, ids, x, y, thickness, scale, vertical) {
  let offset = 0;
  return ids.map((id, i) => {
    const size = row.contributions[id] * scale;
    const rect = `<rect x="${vertical ? x : x + offset}" y="${
      vertical ? y - offset - size : y
    }" width="${vertical ? thickness : size}" height="${
      vertical ? size : thickness
    }" fill="${palette[i % palette.length]}" opacity=".88"><title>${
      esc(index.benchmarks.get(id).name)
    }: ${fmt(row.contributions[id], 2)} points</title></rect>`;
    offset += size;
    return rect;
  }).join("");
}
function contributionLegend() {
  return `<div class="legend">${
    selectedTests().map((id, i) =>
      `<span><i class="swatch" style="background:${
        palette[i % palette.length]
      }"></i>${esc(index.benchmarks.get(id).name)}</span>`
    ).join("")
  }</div>`;
}
function barChart(items) {
  const stacked = state.stacked && !native(), ids = selectedTests();
  const w = 950,
    n = items.length,
    values = items.map(value),
    intervals = native()
      ? items.flatMap((r) => {
        const o = observation(r);
        return [o?.ci_low, o?.ci_high].filter(finite);
      })
      : [],
    min = Math.min(0, ...values, ...intervals),
    max = Math.max(...values, ...intervals, 1),
    span = max - min || 1;
  const pad = state.layout === "vertical" ? 45 : 235,
    right = 65,
    top = 25,
    inner = w - pad - right;
  if (state.layout === "vertical") {
    const h = 440,
      bottom = 145,
      height = h - bottom - top,
      bw = inner / Math.max(1, n),
      x0 = pad;
    let out = svgStart(w, h, "Model ranking column chart");
    for (let i = 0; i <= 4; i++) {
      const y = top + height - i * height / 4;
      out += `<line class="grid" x1="${pad}" x2="${
        w - right
      }" y1="${y}" y2="${y}"/><text x="${pad - 8}" y="${
        y + 4
      }" text-anchor="end">${fmt(min + i * span / 4)}</text>`;
    }
    items.forEach((r, i) => {
      const y = top + height - (value(r) - min) / span * height,
        x = x0 + i * bw + 3;
      out += `<g data-row="${
        esc(r.key)
      }" tabindex="0" role="button" aria-label="${esc(r.model.name)} ${
        fmt(value(r))
      }">${
        stacked
          ? contributionRects(
            r,
            ids,
            x,
            top + height,
            Math.max(3, bw - 6),
            height / span,
            true,
          )
          : `<rect x="${x}" y="${y}" width="${Math.max(3, bw - 6)}" height="${
            Math.max(1, top + height - y)
          }" fill="${color(r)}" opacity=".86"/>`
      }<text class="label" x="${x + bw / 2 - 3}" y="${
        Math.max(14, y - 7)
      }" text-anchor="middle" style="font-size:11px">${
        fmt(value(r))
      }</text><text transform="translate(${x + bw / 2},${
        top + height + 15
      }) rotate(-55)" text-anchor="end">${
        esc(short(r.model.name, 28))
      }</text></g>`;
    });
    return out + "</svg>";
  }
  const rh = 36,
    h = top + n * rh + 35,
    x = (v) => pad + (v - min) / span * inner;
  let out = svgStart(w, h, "Model ranking bar chart");
  for (let i = 0; i <= 4; i++) {
    const tick = min + i * span / 4, px = x(tick);
    out += `<line class="grid" x1="${px}" x2="${px}" y1="12" y2="${
      h - 24
    }"/><text x="${px}" y="${h - 5}" text-anchor="middle">${fmt(tick)}</text>`;
  }
  items.forEach((r, i) => {
    const y = top + i * rh, obs = observation(r), zero = x(0), v = x(value(r));
    out += `<g data-row="${
      esc(r.key)
    }" tabindex="0" role="button" aria-label="${esc(r.model.name)} ${
      fmt(value(r))
    }"><rect x="0" y="${y - 13}" width="${w}" height="${
      rh - 1
    }" fill="transparent"/><text x="0" y="${
      y + 5
    }" style="fill:var(--dim);font-size:11px">${
      i + 1
    }</text><text class="label" x="25" y="${y + 5}" style="font-size:13px">${
      esc(short(r.model.name, 29))
    }</text>${
      stacked
        ? contributionRects(r, ids, zero, y - 9, 23, inner / span, false)
        : `<rect x="${Math.min(zero, v)}" y="${y - 9}" width="${
          Math.max(1, Math.abs(v - zero))
        }" height="23" fill="${color(r)}" opacity="${
          state.selected === r.key ? 1 : .8
        }" rx="1"/>`
    }<text class="label" x="${
      Math.max(v, native() && finite(obs?.ci_high) ? x(obs.ci_high) : v) + 8
    }" y="${y + 6}" style="font-variant-numeric:tabular-nums">${
      fmt(value(r))
    }</text>`;
    if (native() && finite(obs?.ci_low) && finite(obs?.ci_high)) {
      out += `<path d="M${x(obs.ci_low)} ${y + 2}H${x(obs.ci_high)}M${
        x(obs.ci_low)
      } ${y - 3}v10M${x(obs.ci_high)} ${
        y - 3
      }v10" stroke="#f0f0f0" fill="none" stroke-width="1.2"/>`;
    }
    out += "</g>";
  });
  return out + "</svg>";
}
function table(items, showSelect = true) {
  const ids = selectedTests();
  return `<div class="table-wrap quiet-scroll"><table><thead><tr><th>#</th>${
    showSelect ? '<th title="Select models to compare">Compare</th>' : ""
  }<th>Model / setup</th><th class="num">${
    esc(unit())
  }</th><th class="num">Coverage</th><th>Evidence</th></tr></thead><tbody>${
    items.map((r) => {
      const o = observation(r);
      return `<tr data-row="${esc(r.key)}" class="${
        state.selected === r.key ? "selected" : ""
      }"><td class="rank">${r.rank}</td>${
        showSelect
          ? `<td><input type="checkbox" data-compare="${
            esc(r.model.id)
          }" aria-label="Compare ${esc(r.model.name)}" ${
            state.compare.includes(r.model.id) ? "checked" : ""
          }></td>`
          : ""
      }<td class="model-cell"><div class="model-title"><span class="model-mark" style="background:${
        color(r)
      }"></span><span>${esc(r.model.name)}</span></div><div class="model-sub">${
        esc(r.model.lab)
      } · ${esc(o?.effort || "effort unreported")}${
        o?.harness ? " · " + esc(short(o.harness, 45)) : ""
      }</div></td><td class="num"><strong>${fmt(value(r), 2)}</strong>${
        native() && finite(o?.stderr ?? o?.standard_error)
          ? `<div class="model-sub">±${
            fmt(o.stderr ?? o.standard_error, 2)
          } SE</div>`
          : ""
      }</td><td class="num coverage">${fmt(r.coverage * 100, 0)}% · ${
        Object.keys(r.observations).length
      }/${ids.length}</td><td>${
        link(
          o?.source_url,
          providerNames[o?.provider] || o?.provider || "Source",
        )
      }</td></tr>`;
    }).join("")
  }</tbody></table></div>`;
}

const metrics = [
  ["cost_usd", "Task cost · USD"],
  ["latency_seconds", "Task duration · seconds"],
  ["speed_tps", "Task output speed · tokens/s"],
  ["endpoint_speed_tps", "API output speed · tokens/s"],
  ["endpoint_latency_seconds", "API response latency · seconds"],
  ["input_price", "Input price · $/M tokens"],
  ["output_price", "Output price · $/M tokens"],
  ["context_tokens", "Context window · tokens"],
  ["parameters", "Parameters"],
  ["training_compute_flop", "Training compute · FLOP"],
];
function metricValue(r, field, benchmarkId) {
  if (field.startsWith("test:")) {
    return r.observations[field.slice(5)]?.score ?? null;
  }
  const o = benchmarkId ? r.observations[benchmarkId] : observation(r);
  const v = o?.[field] ?? r.model[field];
  return finite(v) ? v : null;
}
function frontierView() {
  const yTest = selectedTests().includes(state.axisY)
    ? index.benchmarks.get(state.axisY)
    : null;
  const yLabel = yTest ? `${yTest.name} · ${yTest.unit}` : unit();
  const axisChoices = [
    ...metrics,
    ...selectedTests().map(
      (id) => [`test:${id}`, `${index.benchmarks.get(id).name} · raw score`],
    ),
  ];
  const field = state.metric,
    points = rows.map((r) => ({
      row: r,
      x: metricValue(r, field, yTest?.id),
      y: yTest ? r.observations[yTest.id]?.score : value(r),
    })).filter((p) => finite(p.x) && finite(p.y) && (!state.log || p.x > 0));
  const xLabel = axisChoices.find(([id]) => id === field)?.[1] || field;
  const higherX = field.startsWith("test:")
      ? index.benchmarks.get(field.slice(5))?.higher_is_better !== false
      : ["speed_tps", "endpoint_speed_tps", "context_tokens"].includes(field),
    higherY = yTest
      ? yTest.higher_is_better !== false
      : !native() || primary().higher_is_better !== false;
  return head(
    "Cost & performance",
    "Inspect the tradeoff on the selected evaluation. Cost and timing are taken from that exact reported run, when available.",
  ) + commonToolbar() +
    `<div class="toolbar"><label for="metric">Horizontal axis</label>${
      select("metric", axisChoices, field)
    }<label for="axisY">Vertical axis</label>${
      select("axisY", [
        ["ranking", "Current ranking"],
        ...selectedTests().map(
          (id) => [id, index.benchmarks.get(id).name + " · raw score"],
        ),
      ], yTest?.id || "ranking")
    }<label class="small-check"><input id="log" type="checkbox" ${
      state.log ? "checked" : ""
    }>Log scale</label><label class="small-check"><input id="labels" type="checkbox" ${
      state.labels ? "checked" : ""
    }>Labels</label><span class="spacer"></span><button class="quiet-button" data-action="svg">↓ SVG</button></div>` +
    (points.length
      ? `<div class="chart-wrap"><div class="chart-title"><div><h3>${
        esc(yLabel)
      } vs ${esc(xLabel)}</h3><p>${points.length} points · ${
        rows.length - points.length
      } missing this measurement${
        state.log ? " or non-positive" : ""
      }</p></div><span class="badge">Dashed line: Pareto frontier</span></div>${
        scatter(points, {
          xLabel,
          yLabel,
          log: state.log,
          frontier: pareto(points, higherY, higherX),
          labels: state.labels,
        })
      }</div>${
        legend(points.map((p) => p.row))
      }${note()}<p class="chart-note">${
        field === "cost_usd"
          ? "Per-task costs from different benchmarks measure different workloads. Cost follows the selected vertical test; a custom ranking uses the first selected test."
          : "A point’s evaluation settings are available by clicking it."
      }</p>`
      : empty(
        "No comparable measurements",
        "This test does not publish the selected cost or performance field. Choose another horizontal axis or test.",
      ));
}
function scatter(
  points,
  {
    xLabel = "",
    yLabel = "",
    log = false,
    frontier = [],
    labels = true,
    date = false,
  } = {},
) {
  const w = 950, h = 520, l = 70, r = 35, t = 30, b = 60;
  const xs = points.map((p) => log ? Math.log10(p.x) : p.x),
    ys = points.map((p) => p.y),
    loX = Math.min(...xs),
    hiX = Math.max(...xs),
    loY = Math.min(0, ...ys),
    hiY = Math.max(...ys);
  const dx = hiX - loX || 1,
    dy = hiY - loY || 1,
    x = (v) => l + ((log ? Math.log10(v) : v) - loX) / dx * (w - l - r),
    y = (v) => h - b - (v - loY) / dy * (h - t - b);
  let out = svgStart(w, h, `${yLabel} by ${xLabel}`);
  for (let i = 0; i <= 5; i++) {
    const py = t + i * (h - t - b) / 5,
      px = l + i * (w - l - r) / 5,
      vx = loX + dx * i / 5;
    out += `<line class="grid" x1="${l}" x2="${
      w - r
    }" y1="${py}" y2="${py}"/><text x="${l - 12}" y="${
      py + 4
    }" text-anchor="end">${
      fmt(hiY - dy * i / 5)
    }</text><line class="grid" x1="${px}" x2="${px}" y1="${t}" y2="${
      h - b
    }"/><text x="${px}" y="${h - b + 23}" text-anchor="middle">${
      date
        ? new Date(vx).toLocaleDateString(undefined, {
          month: "short",
          year: "2-digit",
        })
        : compact(log ? 10 ** vx : vx)
    }</text>`;
  }
  if (frontier.length > 1) {
    out += `<path d="${
      frontier.map((p, i) => `${i ? "L" : "M"}${x(p.x)},${y(p.y)}`).join(" ")
    }" fill="none" stroke="#a6a6a6" stroke-dasharray="5 5" opacity=".7"/>`;
  }
  points.forEach((p, i) => {
    const selected = state.selected === p.row.key ||
      state.compare.includes(p.row.model.id);
    out += `<g data-row="${
      esc(p.row.key)
    }" tabindex="0" role="button" aria-label="${
      esc(p.row.model.name)
    }"><circle cx="${x(p.x)}" cy="${y(p.y)}" r="${selected ? 7 : 5}" fill="${
      color(p.row)
    }" opacity=".85" stroke="${selected ? "white" : "#202020"}" stroke-width="${
      selected ? 2 : 1
    }"/>${
      labels && (points.length <= 22 || selected || p.row.rank <= 8)
        ? `<text class="label" text-anchor="${
          x(p.x) > w - 190 ? "end" : "start"
        }" x="${x(p.x) + (x(p.x) > w - 190 ? -9 : 9)}" y="${
          y(p.y) + (i % 2 ? -8 : 15)
        }" style="font-size:11px">${esc(short(p.row.model.name, 25))}</text>`
        : ""
    }</g>`;
  });
  return out +
    `<text x="${w / 2}" y="${h - 6}" text-anchor="middle">${
      esc(xLabel)
    }</text><text transform="translate(16,${
      h / 2
    }) rotate(-90)" text-anchor="middle">${esc(yLabel)}</text></svg>`;
}
function compact(v) {
  if (!finite(v)) return "—";
  if (Math.abs(v) >= 1e12) return (v / 1e12).toPrecision(3) + "T";
  if (Math.abs(v) >= 1e9) return (v / 1e9).toPrecision(3) + "B";
  if (Math.abs(v) >= 1e6) return (v / 1e6).toPrecision(3) + "M";
  if (Math.abs(v) >= 1e3) return fmt(v / 1e3, 1) + "k";
  if (v > 0 && v < .01) return v.toPrecision(2);
  return fmt(v, 2);
}
function matrixView() {
  const ids = selectedTests();
  return head(
    "Benchmark matrix",
    "Published results by test. Color uses the selected normalization; empty cells mean no matching published result.",
  ) + commonToolbar() +
    `<div class="toolbar"><button data-action="matrix-expand">Add related tests</button><span class="small muted">${ids.length} columns · ${rows.length} qualifying rows</span></div>` +
    (rows.length
      ? `<div class="table-wrap quiet-scroll"><table class="matrix"><thead><tr><th>Model</th>${
        ids.map((id) => {
          const b = index.benchmarks.get(id);
          return `<th title="${esc(b.name)}">${esc(b.name)}<div class="dim">${
            esc(providerNames[b.provider])
          } · ${esc(b.unit)}</div></th>`;
        }).join("")
      }</tr></thead><tbody>${
        rows.slice(0, state.limit).map((r) =>
          `<tr><td data-row="${
            esc(r.key)
          }"><div class="model-title"><span class="model-mark" style="background:${
            color(r)
          }"></span>${esc(r.model.name)}</div></td>${
            ids.map((id) => {
              const o = r.observations[id], v = r.values[id];
              return o
                ? `<td class="heat-cell" data-observation="${
                  esc(o.id)
                }" style="background:rgba(134,163,207,${
                  .06 + v / 100 * .48
                })" title="${esc(o.model)} · ${
                  esc(o.effort || "effort unreported")
                } · ${esc(o.harness || "agent unreported")}">${
                  fmt(o.score, 2)
                }</td>`
                : '<td class="dim">—</td>';
            }).join("")
          }</tr>`
        ).join("")
      }</tbody></table></div>${note()}`
      : empty(
        "No shared results",
        "Select “Available tests” in the missing-results control and lower minimum coverage to inspect gaps.",
      ));
}
function compareView() {
  const ids = selectedTests();
  let picked = rows.filter((r) => state.compare.includes(r.model.id)).slice(
    0,
    6,
  );
  if (!picked.length) picked = rows.slice(0, 3);
  const selectedIds = picked.map((r) => r.model.id);
  return head(
    "Compare models",
    "Compare scores by test. Select models in a ranking table.",
  ) + commonToolbar() +
    `<div class="compare-strip">${
      picked.map((r) =>
        `<span class="chip"><i class="source-dot" style="background:${
          color(r)
        };margin:0"></i>${esc(r.model.name)}<button data-remove-compare="${
          esc(r.model.id)
        }" aria-label="Remove ${esc(r.model.name)}">×</button></span>`
      ).join("")
    }<button data-action="matrix-expand">Add related tests</button></div>` +
    (picked.length
      ? `<div class="chart-wrap"><div class="chart-title"><div><h3>Capability profile</h3><p>${
        ids.length < 3
          ? "Select at least three tests for a radial profile."
          : "Normalized scores · polygon area is not an overall score"
      }</p></div></div>${
        ids.length >= 3
          ? radar(picked, ids.slice(0, 12))
          : comparisonBars(picked, ids)
      }</div>${
        legend(picked)
      }<div class="table-wrap quiet-scroll"><table><thead><tr><th>Test</th>${
        picked.map((r) => `<th class="num">${esc(r.model.name)}</th>`).join("")
      }</tr></thead><tbody>${
        ids.map((id) => {
          const b = index.benchmarks.get(id);
          return `<tr><td>${esc(b.name)}<div class="model-sub">${
            esc(providerNames[b.provider])
          } · ${esc(b.unit)}</div></td>${
            picked.map((r) => {
              const o = r.observations[id];
              return `<td class="num" ${
                o ? `data-observation="${esc(o.id)}"` : ""
              }>${fmt(o?.score, 2)}<div class="model-sub">${
                esc(o?.effort || "—")
              }</div></td>`;
            }).join("")
          }</tr>`;
        }).join("")
      }</tbody></table></div>${note()}`
      : empty(
        "No models to compare",
        "Choose a test with results, then select models in its ranking.",
      ));
}
function radar(items, ids) {
  const w = 950,
    h = 470,
    cx = 475,
    cy = 225,
    r = 160,
    n = ids.length,
    point = (
      i,
      v,
    ) => [
      cx + Math.sin(i / n * Math.PI * 2) * r * v / 100,
      cy - Math.cos(i / n * Math.PI * 2) * r * v / 100,
    ];
  let out = svgStart(w, h, "Normalized model capability profiles");
  for (const v of [25, 50, 75, 100]) {
    out += `<polygon points="${
      ids.map((_, i) => point(i, v).join(",")).join(" ")
    }" fill="none" stroke="#404040"/>`;
  }
  ids.forEach((id, i) => {
    const [x, y] = point(i, 100), [tx, ty] = point(i, 119);
    out +=
      `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#363636"/><text x="${tx}" y="${ty}" text-anchor="${
        tx < cx - 20 ? "end" : tx > cx + 20 ? "start" : "middle"
      }">${esc(short(index.benchmarks.get(id).name, 30))}</text>`;
  });
  items.forEach((row) => {
    if (ids.every((id) => finite(row.values[id]))) {
      out += `<polygon data-row="${esc(row.key)}" points="${
        ids.map((id, i) => point(i, row.values[id]).join(",")).join(" ")
      }" fill="${color(row)}" fill-opacity=".07" stroke="${
        color(row)
      }" stroke-width="2"/>`;
    } else {ids.forEach((id, i) => {
        if (finite(row.values[id])) {
          const [x, y] = point(i, row.values[id]);
          out += `<circle data-row="${
            esc(row.key)
          }" cx="${x}" cy="${y}" r="4" fill="${color(row)}"/>`;
        }
      });}
  });
  return out + "</svg>";
}
function comparisonBars(items, ids) {
  const w = 950, rh = 33, h = 60 + items.length * ids.length * rh, l = 300;
  let out = svgStart(w, h, "Scores by test and model");
  ids.forEach((id, j) =>
    items.forEach((r, i) => {
      const yy = 30 + (j * items.length + i) * rh, v = r.values[id];
      out += `<text x="0" y="${yy + 5}" class="label">${
        esc(short(r.model.name, 25))
      } · ${esc(short(index.benchmarks.get(id).name, 20))}</text>${
        finite(v)
          ? `<rect data-row="${esc(r.key)}" x="${l}" y="${yy - 10}" width="${
            v * 5.5
          }" height="22" fill="${color(r)}" opacity=".8"/><text x="${
            l + v * 5.5 + 8
          }" y="${yy + 5}">${fmt(v)}</text>`
          : ""
      }`;
    })
  );
  return out + "</svg>";
}
function timelineView() {
  const useHistory = state.timelineAxis === "observation",
    ids = selectedTests();
  let points = [];
  if (useHistory) {
    const history = index.data.history || [];
    for (const o of history) {
      const r = rows.find((r) => r.model.id === o.model_id);
      if (!r || !ids.includes(o.benchmark_id)) continue;
      const x = Date.parse(o.date);
      if (Number.isFinite(x)) points.push({ row: r, x, y: o.score });
    }
  } else {points = rows.map((r) => ({
      row: r,
      x: Date.parse(observation(r)?.release_date || r.model.release_date),
      y: value(r),
    })
    ).filter((p) => Number.isFinite(p.x));}
  return head(
    useHistory ? "Observation history" : "Model release timeline",
    useHistory
      ? "Published historical measurements only. Changes in benchmark version remain separate tests."
      : "How measured scores relate to model release dates. This is not a history of changes to each model’s score.",
  ) + commonToolbar() +
    `<div class="toolbar"><label for="timelineAxis">Date axis</label>${
      select("timelineAxis", [["release", "Model release date"], [
        "observation",
        "Historical result date",
      ]], state.timelineAxis)
    }<label class="small-check"><input id="labels" type="checkbox" ${
      state.labels ? "checked" : ""
    }>Labels</label></div>` +
    (points.length
      ? `<div class="chart-wrap">${
        scatter(points, {
          xLabel: useHistory ? "Observation date" : "Model release date",
          yLabel: unit(),
          date: true,
          labels: state.labels,
        })
      }</div>${legend(points.map((p) => p.row))}${note()}`
      : empty(
        useHistory
          ? "No published history for this selection"
          : "Release dates are unavailable",
        useHistory
          ? "This snapshot contains historical series only where an original source publishes them. Try an Arena Agent test, or use the release timeline."
          : "Choose another test; dates are never inferred from model names.",
      ));
}
function sensitivityView() {
  const ids = selectedTests(),
    target = ids.includes(state.sensitivityTarget)
      ? state.sensitivityTarget
      : ids[0],
    runs = ids.length > 1 ? sensitivity(index, state, target) : [];
  const chosen = state.compare.length
    ? rows.filter((r) => state.compare.includes(r.model.id)).slice(0, 8)
    : rows.slice(0, 6);
  return head(
    "Weight sensitivity",
    "Rank changes as one test’s weight varies from 0% to 100%. The other weights keep their relative proportions.",
  ) + commonToolbar() +
    `<div class="toolbar"><label for="sensitivityTarget">Sweep</label>${
      select(
        "sensitivityTarget",
        ids.map((id) => [id, index.benchmarks.get(id).name]),
        target,
      )
    }<span class="small muted">${chosen.length} models shown</span></div>` +
    (runs.length && chosen.length
      ? `<div class="chart-wrap">${sensitivityChart(runs, chosen)}</div>${
        legend(chosen)
      }<p class="chart-note">The endpoints remove the other tests at 100%. Coverage rules apply at every step, so a missing result can make a model disappear. The 0% endpoint uses a tiny positive weight to keep the selected-test coverage cohort stable.</p>`
      : empty(
        "Select two or more tests",
        "Add tests in the right pane, then inspect how changing one weight changes the ranking.",
      ));
}
function sensitivityChart(runs, chosen) {
  const w = 950,
    h = 470,
    l = 55,
    r = 40,
    t = 30,
    b = 55,
    all = runs.flatMap((run) =>
      run.rows.filter((row) => chosen.some((c) => c.key === row.key)).map(
        (row) => row.rank,
      )
    ),
    max = Math.max(5, ...all),
    x = (v) => l + v / 100 * (w - l - r),
    y = (v) => t + (v - 1) / (max - 1) * (h - t - b);
  let out = svgStart(w, h, "Rank changes as benchmark weight changes");
  for (let i = 0; i <= 5; i++) {
    const px = x(i * 20);
    out += `<line class="grid" x1="${px}" x2="${px}" y1="${t}" y2="${
      h - b
    }"/><text x="${px}" y="${h - b + 25}" text-anchor="middle">${
      i * 20
    }%</text>`;
  }
  for (let i = 0; i <= 4; i++) {
    const v = Math.round(1 + (max - 1) * i / 4), py = y(v);
    out += `<line class="grid" x1="${l}" x2="${
      w - r
    }" y1="${py}" y2="${py}"/><text x="${l - 12}" y="${
      py + 4
    }" text-anchor="end">#${v}</text>`;
  }
  chosen.forEach((row) => {
    let path = "", connected = false;
    runs.forEach((run) => {
      const v = run.rows.find((v) => v.key === row.key);
      if (!v) {
        connected = false;
        return;
      }
      path += `${connected ? "L" : "M"}${x(run.share)},${y(v.rank)} `;
      connected = true;
    });
    out += `<path data-row="${esc(row.key)}" d="${path}" fill="none" stroke="${
      color(row)
    }" stroke-width="2.2"/>`;
  });
  return out +
    `<text x="${w / 2}" y="${
      h - 5
    }" text-anchor="middle">Selected test’s share of total weight</text></svg>`;
}
function distributionView() {
  const groups = new Map();
  for (const r of rows) {
    const key = state.distributionBy === "provider"
      ? providerNames[observation(r)?.provider]
      : state.distributionBy === "weights"
      ? (observation(r)?.weights || r.model.weights || "unknown")
      : state.distributionBy === "country"
      ? (observation(r)?.country || r.model.country || "Unknown")
      : r.model.lab;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  const sorted = [...groups].sort((a, b) => b[1].length - a[1].length).slice(
      0,
      20,
    ),
    w = 950,
    h = 55 + sorted.length * 37,
    l = 160,
    max = Math.max(1, ...rows.map(value)),
    min = Math.min(0, ...rows.map(value)),
    x = (v) => l + (v - min) / (max - min || 1) * (w - l - 45);
  let chart = svgStart(
    w,
    h,
    "Score distributions grouped by " + state.distributionBy,
  );
  sorted.forEach(([name, rs], i) => {
    const yy = 25 + i * 37,
      vs = rs.map(value).sort((a, b) => a - b),
      median = vs.length % 2
        ? vs[(vs.length - 1) / 2]
        : (vs[vs.length / 2 - 1] + vs[vs.length / 2]) / 2;
    chart += `<text class="label" x="0" y="${yy + 4}">${
      esc(short(name, 21))
    }</text><line x1="${x(vs[0])}" x2="${
      x(vs.at(-1))
    }" y1="${yy}" y2="${yy}" stroke="#626262" stroke-width="2"/>`;
    rs.forEach((r, j) =>
      chart += `<circle data-row="${esc(r.key)}" cx="${x(value(r))}" cy="${
        yy + (j % 3 - 1) * 4
      }" r="3.3" fill="${color(r)}" opacity=".7"/>`
    );
    chart += `<path d="M${x(median)} ${
      yy - 9
    }v18" stroke="white" stroke-width="2"/><text x="${w - 5}" y="${
      yy + 4
    }" text-anchor="end">n=${rs.length}</text>`;
  });
  chart += "</svg>";
  return head(
    "Distributions",
    "Score distributions by lab, country or weight access. White marks show medians.",
  ) + commonToolbar() +
    `<div class="toolbar"><label for="distributionBy">Group by</label>${
      select("distributionBy", [["lab", "Lab"], ["country", "Country"], [
        "weights",
        "Weight access",
      ], ["provider", "Evaluator"]], state.distributionBy)
    }</div>` +
    (rows.length
      ? `<div class="chart-wrap">${chart}</div><p class="chart-note">Each dot is a model or configuration in the filtered results. Groups with few published models have limited coverage; their median is not a measure of the whole organization or country.</p>`
      : empty("No distribution available", "Choose a test and relax filters."));
}

function filteredBenchmarks() {
  return index.data.benchmarks.filter((b) =>
    b.observation_count &&
    (!state.benchSearch ||
      `${b.name} ${b.description} ${b.native_category} ${b.provider}`
        .toLowerCase().includes(state.benchSearch.toLowerCase())) &&
    (!state.benchProvider || b.provider === state.benchProvider) &&
    (!state.benchCategory || b.category === state.benchCategory) &&
    (!state.benchKind || b.kind === state.benchKind) &&
    (state.subtasks || !b.parent_benchmark_id) &&
    (state.archived || !b.archived)
  ).sort((a, b) =>
    (a.kind === "composite" ? -1 : 0) - (b.kind === "composite" ? -1 : 0) ||
    b.observation_count - a.observation_count
  );
}
function benchmarkView() {
  const bs = filteredBenchmarks(),
    page = state.page || 0,
    shown = bs.slice(page * 60, (page + 1) * 60),
    categories = [...new Set(index.data.benchmarks.map((b) => b.category))]
      .sort();
  return head(
    "Test catalog",
    "Tests, versions, categories, scoring units and source links. Open a ranking or add tests to the selected mix.",
  ) +
    `<div class="toolbar"><input id="benchSearch" type="search" class="search-large" placeholder="Search tests, tasks and categories…" aria-label="Search tests" value="${
      esc(state.benchSearch)
    }">${
      select(
        "benchProvider",
        Object.entries(providerNames).filter(([id]) =>
          index.data.sources.some((s) => s.provider === id)
        ),
        state.benchProvider,
        "All evaluators",
      )
    }${
      select("benchCategory", categories, state.benchCategory, "All domains")
    }${
      select(
        "benchKind",
        [
          ["benchmark", "Individual tests"],
          ["composite", "Published indices"],
          ["metric", "Cost / performance"],
          ["trait", "Traits"],
        ],
        state.benchKind,
        "All measurement types",
      )
    }</div><div class="toolbar"><label class="small-check"><input id="subtasks" type="checkbox" ${
      state.subtasks ? "checked" : ""
    }>Include task and category slices</label><label class="small-check"><input id="archived" type="checkbox" ${
      state.archived ? "checked" : ""
    }>Include historical versions</label><span class="spacer"></span><span class="small muted">${bs.length} matching tests</span></div><div class="catalog-grid">${
      shown.map((b) =>
        `<article class="catalog-item"><div><h3>${esc(b.name)}</h3><p>${
          esc(b.description || "Published score from the original evaluation.")
        }</p><div class="catalog-meta"><span class="badge">${
          esc(providerNames[b.provider])
        }</span><span class="badge">${
          esc(b.category)
        }</span><span class="badge">${esc(b.unit)} · ${
          b.higher_is_better === false ? "lower" : "higher"
        } is better</span><span class="badge">${b.observation_count} results</span>${
          b.private === true ? '<span class="badge">Private test</span>' : ""
        }${b.archived ? '<span class="badge">Archived</span>' : ""}${
          b.parent_benchmark_id
            ? '<span class="badge">Task / category slice</span>'
            : ""
        }</div><p>${link(b.source_url, "Evaluation ↗")} ${
          b.dataset_url ? " · " + link(b.dataset_url, "Dataset ↗") : ""
        } · Native category: ${
          esc(
            Array.isArray(b.native_category)
              ? b.native_category.join(", ")
              : b.native_category || b.category,
          )
        }</p></div><div class="actions"><button data-open-test="${
          esc(b.id)
        }">Open</button><button data-add-test="${
          esc(b.id)
        }" title="Add to the weighted ranking">${
          state.weights[b.id] > 0 ? "Added" : "＋ Add"
        }</button></div></article>`
      ).join("") ||
      empty(
        "No matching tests",
        "Change the evaluator, category, or search filter.",
      )
    }</div>${pagination(bs.length, 60)}`;
}
function pagination(total, size = 60) {
  const max = Math.max(1, Math.ceil(total / size));
  return `<div class="pagination"><span>Page ${
    Math.min(state.page + 1, max)
  } of ${max} · ${
    fmt(total, 0)
  } rows</span><div class="inline-actions"><button data-page="${
    Math.max(0, state.page - 1)
  }" ${state.page <= 0 ? "disabled" : ""}>Previous</button><button data-page="${
    state.page + 1
  }" ${state.page + 1 >= max ? "disabled" : ""}>Next</button></div></div>`;
}
function publicationPanel() {
  const policy = index.data.publication;
  if (!policy) return "";
  const updates = index.data.updates;
  return `<section class="source-card"><h2>Public data policy</h2><p>Only data licensed for commercial reuse is included. ${
    esc(runtime.schedule)
  }.</p><p>${
    policy.attribution.map((s) =>
      `${link(s.url, s.name)} · ${link(s.license_url, "CC BY 4.0")}`
    ).join("<br>")
  }</p><p>${esc(policy.modifications)}</p><p>${
    link(runtime.repository, "GitHub repository")
  } · ${link(runtime.repository + "/actions", "Update runs")} · ${
    link("attribution.txt", "Attribution")
  }</p>${
    updates
      ? `<p>Last update attempt: ${
        esc(new Date(updates.finished_at).toLocaleString())
      }</p>${
        updates.sources.map((s) =>
          `<p>${esc(providerNames[s.provider])}: ${
            s.status === "ok"
              ? "updated"
              : `previous data retained. ${esc(s.error)}`
          }</p>`
        ).join("")
      }`
      : ""
  }<details><summary>Excluded sources</summary>${
    policy.excluded.map((s) =>
      `<p><strong>${link(s.evidence_url || s.url, s.name)}</strong>: ${
        esc(s.reason)
      }</p>`
    ).join("")
  }</details></section>`;
}
function sourcesView() {
  const all = index.data.sources.filter((s, i, a) =>
    a.findIndex((t) => t.provider === s.provider) === i
  );
  return head(
    "Sources & coverage",
    "Data sources, licenses, coverage and update status.",
    `<button data-action="refresh">${
      runtime.mode === "static" ? "Reload data" : "Refresh sources"
    }</button>`,
  ) +
    `${publicationPanel()}<div id="refresh-status"></div><div class="stat-line"><span><strong>${all.length}</strong>Evaluators</span><span><strong>${
      fmt(index.data.observations.length, 0)
    }</strong>Observed results</span><span><strong>${
      index.data.visualizations?.length || 0
    }</strong>Original chart records</span><span><strong>${index.data.inventory.length}</strong>Chart / category inventory</span></div>${
      all.map((s) => {
        const bs = index.data.benchmarks.filter((b) =>
            b.provider === s.provider
          ),
          obs = index.data.observations.filter((o) =>
            o.provider === s.provider
          ),
          inv = index.data.inventory.filter((i) => i.provider === s.provider),
          secondary = obs.filter((o) =>
            o.provenance === "external-via-epoch"
          ).length;
        return `<article class="source-card"><h2>${sourceMark(s.provider)}${
          esc(providerNames[s.provider] || s.name)
        }<span class="badge">${esc(s.status || "snapshot")}</span></h2><p>${
          esc(
            s.notes || s.description ||
              "Data imported from public first-party sources.",
          )
        }</p><dl class="kv"><dt>Retrieved</dt><dd>${
          esc(
            s.retrieved_at
              ? new Date(s.retrieved_at).toLocaleString()
              : "Not reported",
          )
        }</dd><dt>Coverage</dt><dd>${
          fmt(obs.length, 0)
        } observations · ${bs.length} test series</dd><dt>License</dt><dd>${
          s.license_url
            ? link(s.license_url, s.license)
            : esc(s.license || "Not stated")
        }</dd>${
          secondary
            ? `<dt>Aggregated results</dt><dd>${
              fmt(secondary, 0)
            } rows cite external evaluators; these are not new independent runs.</dd>`
            : ""
        }</dl><div class="source-links">${link(s.url, "Website ↗")}${
          s.data_url ? link(s.data_url, "Data source ↗") : ""
        }${s.methodology_url ? link(s.methodology_url, "Methodology ↗") : ""}${
          runtime.mode === "local"
            ? `<button class="quiet-button" data-refresh-source="${
              esc(s.provider)
            }">Refresh this source</button>`
            : ""
        }</div><details><summary>Chart and category inventory · ${inv.length} entries</summary><div class="table-wrap quiet-scroll"><table><thead><tr><th>Original view</th><th>Available view</th><th>Availability / limits</th></tr></thead><tbody>${
          inv.map((v) =>
            `<tr><td>${link(v.url || s.url, v.name || v.type)}</td><td>${
              esc(v.supported_view || v.type || "Source charts")
            }</td><td>${esc(v.status || "data-only")}${
              v.notes
                ? '<div class="model-sub" style="white-space:normal">' +
                  esc(v.notes) + "</div>"
                : ""
            }</td></tr>`
          ).join("")
        }</tbody></table></div></details></article>`;
      }).join("")
    }<section class="section"><h3>Exports</h3><p class="help-copy">CSV exports include the original model label, benchmark version, evaluation setup, raw score, source URL and snapshot date. Model aliases are conservative and visible in the evidence pane. Results collected through an aggregator remain labelled with the original evaluator.</p></section>`;
}
function dataView() {
  const selected = selectedTests();
  const obs = index.data.observations.filter((o) =>
    selected.includes(o.benchmark_id) &&
    matches(index.models.get(o.model_id), o, state)
  );
  const shown = obs.slice(state.page * 60, (state.page + 1) * 60);
  return head(
    "Observation table",
    "All runs matching the model filters and selected tests, including variants grouped together in rankings. Aggregate coverage rules apply to rankings only.",
  ) + commonToolbar() +
    `<div class="table-wrap quiet-scroll"><table><thead><tr><th>Original model label</th><th>Test</th><th class="num">Raw score</th><th>Effort / agent</th><th>Evaluator / provenance</th><th>Date</th><th>Source</th></tr></thead><tbody>${
      shown.map((o) => {
        const b = index.benchmarks.get(o.benchmark_id);
        return `<tr data-observation="${esc(o.id)}"><td>${
          esc(o.model)
        }<div class="model-sub">${
          esc(o.source_model_id || o.model_id)
        }</div></td><td>${esc(b.name)}<div class="model-sub">${
          esc(b.version || "Version unreported")
        }</div></td><td class="num">${fmt(o.score, 3)} ${esc(b.unit)}</td><td>${
          esc(o.effort || "Unreported")
        }<div class="model-sub">${esc(o.harness || "Agent unreported")}${
          o.inference_provider ? " · " + esc(o.inference_provider) : ""
        }</div></td><td>${
          esc(o.evaluator || providerNames[o.provider])
        }<div class="model-sub">${
          esc(o.provenance || "direct source")
        }</div></td><td>${
          esc((o.date || "").slice(0, 10) || "Not reported")
        }</td><td>${link(o.source_url, "Source ↗")}</td></tr>`;
      }).join("")
    }</tbody></table></div>${pagination(obs.length)}`;
}
function methodView() {
  return head(
    "Scoring",
    "Published scores, custom scores, normalization and missing results.",
  ) +
    `<section class="section help-copy"><h3>Original rankings</h3><p>With one test selected, the chart displays its original score and direction. A provider’s published composite stays a published composite; it is not reconstructed from rounded component scores.</p><h3>Weighted ranking</h3><p>With multiple tests selected, each result is normalized to 0–100. “Published scale” uses the test’s stated minimum and maximum. Unbounded scores use snapshot percentiles. “Percentiles” uses each test’s fixed, full-snapshot distribution of best reported model scores. Changing visible model filters does not change this reference distribution.</p><p><code>score = sum(weight × normalized result) / included weight</code></p><p>This weighted score uses the selected tests and settings. It is separate from each provider’s published index. Combining a published index with its own components can double-count evidence. The selected-test pane identifies those overlaps when the source publishes the relationships.</p><h3>Missing results</h3><p>“Require all tests” excludes incomplete rows. “Available tests” renormalizes the weights across the results that exist. “Count missing as zero” is an explicit pessimistic policy. Weighted coverage is always shown; a model with missing results has not necessarily failed those tasks.</p><h3>Models and configurations</h3><p>“Best reported per test” groups source variants by a conservatively normalized model label and picks the best result for each selected test. That can combine different effort settings, agents or endpoints. “Match effort + agent” keeps those configurations separate. The original labels and settings remain in every observation.</p><h3>Costs, timing and uncertainty</h3><p>Only published per-task costs belong on the task-cost axis. A complete benchmark run cost is not divided into a fictional per-task estimate. Token pricing, throughput and context length have separate axes. Reported uncertainty retains its source meaning: a standard error is not a 95% confidence interval. No uncertainty interval is invented for a custom score.</p><h3>Dates and trends</h3><p>The release timeline plots a current measured score against the model’s reported release date. Observation history uses actual historical source records. Neither a renamed version nor a new snapshot is interpolated into a fabricated history.</p><h3>Source chart explorer</h3><p>Original public chart datasets are retained separately. Pick a chart, nested data series, labels and numeric fields to inspect it in bars, lines, scatter or a table. Fitted parameters are labelled separately from observed benchmark scores.</p><h3>Refresh and retention</h3><p>${
      runtime.mode === "static"
        ? "Data updates daily through GitHub Actions. A failed import keeps the previous successful data. Sources & coverage lists the latest update outcome and each source’s retrieval date."
        : "Refresh downloads the selected sources. Failed imports keep the previous data. The last twelve replaced snapshots are retained locally."
    }</p></section>`;
}
function inspector() {
  return `<div class="pane-title"><span>Controls & evidence</span><button class="quiet-button icon-button" data-action="inspector" aria-label="Close controls">×</button></div><div class="pane-tabs">${
    [["weights", "Test mix"], ["evidence", "Evidence"], ["settings", "Scoring"]]
      .map(([id, name]) =>
        `<button data-pane="${id}" class="${
          state.inspectorTab === id ? "active" : ""
        }">${name}</button>`
      ).join("")
  }</div>${
    state.inspectorTab === "evidence"
      ? evidencePane()
      : state.inspectorTab === "settings"
      ? settingsPane()
      : weightsPane()
  }`;
}
function weightsPane() {
  const ids = selectedTests(),
    sum = ids.reduce((s, id) => s + +state.weights[id], 0),
    query = state.addSearch || "",
    bs = index.data.benchmarks.filter((b) =>
      b.observation_count && !b.archived && !b.parent_benchmark_id &&
      !["metric", "trait"].includes(b.kind) &&
      (!query ||
        `${b.name} ${b.provider} ${b.category}`.toLowerCase().includes(
          query.toLowerCase(),
        ))
    ).sort((a, b) =>
      (a.kind === "composite" ? -1 : 0) - (b.kind === "composite" ? -1 : 0) ||
      b.observation_count - a.observation_count
    ).slice(0, query ? 45 : 12);
  let overlap = false;
  for (const id of ids) {
    const b = index.benchmarks.get(id);
    if ((b.components || []).some((c) => ids.includes(c.benchmark_id))) {
      overlap = true;
    }
  }
  return `<section class="pane-section"><label for="preset">Preset</label>${
    select(
      "preset",
      [
        ["aa", "AA Intelligence Index"],
        ["professional", "Vals professional work"],
        ["epoch", "Epoch Capabilities Index"],
        ["arena", "Arena text preference"],
        ["balanced", "Balanced domains · custom"],
        ["coding", "Coding & terminal · custom"],
      ].filter(([id]) =>
        runtime.mode !== "static" || ["epoch", "arena"].includes(id)
      ),
      "",
      "Choose a preset…",
    )
  }<p style="margin-top:9px">Select a preset or add individual tests.</p></section><section class="pane-section"><div class="section-head"><h3>${ids.length} selected ${
    ids.length === 1 ? "test" : "tests"
  }</h3><button class="quiet-button small" data-action="equal">Equal weights</button></div>${
    ids.map((id) => {
      const b = index.benchmarks.get(id);
      return `<div class="weight-item"><div class="weight-head"><span>${
        esc(b.name)
      }</span><span class="dim mono">${
        fmt(state.weights[id] / sum * 100, 0)
      }%</span><button data-remove-test="${esc(id)}" aria-label="Remove ${
        esc(b.name)
      }">×</button></div><small>${esc(providerNames[b.provider])} · ${
        esc(b.unit)
      }</small><div class="control-row"><input type="range" min="0" max="100" step="1" value="${
        Math.min(100, state.weights[id])
      }" data-weight="${esc(id)}" aria-label="Weight for ${
        esc(b.name)
      }"><input type="number" min="0" max="1000" step="1" value="${
        state.weights[id]
      }" data-weight-number="${esc(id)}" aria-label="Exact weight for ${
        esc(b.name)
      }"></div></div>`;
    }).join("")
  }${
    overlap
      ? '<p class="warn" style="margin-top:10px">This selection includes a composite and one of its components. That can count the same evidence twice.</p>'
      : ""
  }${
    ids.length > 1
      ? `<button class="quiet-button small" data-pane="settings" style="margin-top:10px">Coverage & normalization →</button>`
      : ""
  }</section><section class="pane-section"><h3>Add a test</h3><input id="add-search" type="search" value="${
    esc(query)
  }" placeholder="Search all tests…" aria-label="Find a test to add"><div class="add-list quiet-scroll">${
    bs.map((b) =>
      `<button class="add-item" data-add-test="${esc(b.id)}"><span>${
        esc(short(b.name, 50))
      }<small>${
        esc(providerNames[b.provider])
      } · ${b.observation_count} results</small></span><span class="plus">${
        state.weights[b.id] > 0 ? "✓" : "+"
      }</span></button>`
    ).join("")
  }</div><button class="quiet-button small" data-view="benchmarks" style="margin-top:8px">Browse full test catalog →</button></section>`;
}
function settingsPane() {
  return `<section class="pane-section"><h3>Model grouping</h3>${
    select("group", [["models", "Best reported per model / test"], [
      "configuration",
      "Match effort + agent",
    ]], state.group)
  }<p style="margin-top:8px">Best-per-test can combine different setups. Matching configurations is stricter and usually reduces shared coverage.</p></section><section class="pane-section"><h3>Normalization</h3>${
    select("normalization", [["scale", "Published scale → 0–100"], [
      "percentile",
      "Snapshot percentile → 0–100",
    ]], state.normalization)
  }<p style="margin-top:8px">Unbounded metrics use percentiles. Percentile baselines stay fixed when you filter models.</p></section><section class="pane-section"><h3>Missing results</h3>${
    select("missing", [["exclude", "Require every selected test"], [
      "available",
      "Use available tests",
    ], ["zero", "Count missing as zero"]], state.missing)
  }<label for="coverage" style="margin-top:14px">Minimum weighted coverage</label><div class="control-row"><input id="coverage" type="range" min="0" max="100" value="${state.coverage}"><input id="coverage-number" type="number" min="0" max="100" value="${state.coverage}" aria-label="Minimum weighted coverage percent"><span>%</span></div><p style="margin-top:8px">The coverage percentage measures how much selected weight has a published result.</p></section><section class="pane-section"><h3>View settings</h3><label for="color">Color by</label>${
    select(
      "color",
      [["lab", "Model lab"], ["source", "Evaluator"]],
      state.color,
    )
  }<button style="margin-top:12px" data-action="reset">Reset explorer</button></section>`;
}
function evidencePane() {
  let r = rowMap.get(state.selected);
  const exact = state.selectedObservation
    ? index.data.observations.find((o) => o.id === state.selectedObservation)
    : null;
  if (!r && exact) {
    r = {
      model: index.models.get(exact.model_id),
      observations: { [exact.benchmark_id]: exact },
      coverage: 1,
    };
  }
  if (!r) {
    return `<section class="pane-section"><h3>Inspect a result</h3><p>Click a bar, point, matrix cell or table row to see the original result and its attribution.</p></section><section class="pane-section"><h3>Current selection</h3>${
      selectedTests().map((id) => {
        const b = index.benchmarks.get(id);
        return `<div class="evidence-item"><strong class="small">${
          esc(b.name)
        }</strong><p>${esc(b.description)}</p>${
          link(b.source_url, "Methodology / results ↗")
        }</div>`;
      }).join("")
    }</section>`;
  }
  return `<section class="pane-section"><div class="model-title"><span class="model-mark" style="background:${
    colors[r.model.lab] || "#aaa"
  }"></span><h3>${esc(r.model.name)}</h3></div><p>${esc(r.model.lab)} · ${
    esc(r.model.weights || "weight access unreported")
  }</p><button style="margin-top:10px" data-toggle-compare="${
    esc(r.model.id)
  }">${
    state.compare.includes(r.model.id)
      ? "Remove from comparison"
      : "Add to comparison"
  }</button><dl class="kv"><dt>Aliases</dt><dd>${
    esc(r.model.aliases.slice(0, 6).join(" · "))
  }</dd><dt>Release</dt><dd>${
    esc(r.model.release_date || "Not reported")
  }</dd><dt>Context</dt><dd>${
    r.model.context_tokens ? compact(r.model.context_tokens) : "Not reported"
  }</dd></dl></section><section class="pane-section">${
    Object.values(r.observations).map((o) => {
      const b = index.benchmarks.get(o.benchmark_id);
      return `<div class="evidence-item"><div class="evidence-score"><strong>${
        esc(b.name)
      }</strong><strong class="mono">${fmt(o.score, 3)} ${
        esc(b.unit)
      }</strong></div><dl class="kv"><dt>Original label</dt><dd>${
        esc(o.model)
      }</dd><dt>Evaluator</dt><dd>${
        esc(o.evaluator || providerNames[o.provider])
      }</dd><dt>Provenance</dt><dd>${
        esc(o.provenance || "Direct public source")
      }</dd><dt>Effort</dt><dd>${
        esc(o.effort || "Not reported")
      }</dd><dt>Agent</dt><dd>${esc(o.harness || "Not reported")}</dd>${
        o.inference_provider
          ? `<dt>Endpoint</dt><dd>${esc(o.inference_provider)}</dd>`
          : ""
      }<dt>Test version</dt><dd>${
        esc(b.version || "Not reported")
      }</dd><dt>Evaluated</dt><dd>${
        esc(o.date || "Not reported")
      }</dd><dt>Retrieved</dt><dd>${
        esc(o.retrieved_at?.slice(0, 10) || "Unknown")
      }</dd>${
        finite(o.ci_low) && finite(o.ci_high)
          ? `<dt>${
            esc(o.ci_kind || ((o.ci_level || "Reported") + " interval"))
          }</dt><dd>${fmt(o.ci_low, 2)} – ${fmt(o.ci_high, 2)}</dd>`
          : ""
      }${
        finite(o.stderr ?? o.standard_error)
          ? `<dt>Standard error</dt><dd>±${
            fmt(o.stderr ?? o.standard_error, 3)
          }</dd>`
          : ""
      }${
        finite(o.cost_usd)
          ? `<dt>Task cost</dt><dd>$${fmt(o.cost_usd, 4)}</dd>`
          : ""
      }${
        finite(o.latency_seconds)
          ? `<dt>Duration</dt><dd>${fmt(o.latency_seconds, 1)} seconds</dd>`
          : ""
      }</dl>${
        o.notes
          ? `<p>${
            esc(typeof o.notes === "string" ? o.notes : JSON.stringify(o.notes))
          }</p>`
          : ""
      }${link(o.source_url, "Original result ↗")}${
        o.aggregator_url
          ? "<br>" + link(o.aggregator_url, "Aggregator record ↗")
          : ""
      }${
        b.dataset_url
          ? "<br>" + link(b.dataset_url, "Underlying dataset ↗")
          : ""
      }</div>`;
    }).join("")
  }</section>`;
}

function sourceChartsView() {
  const vs = (index.data.visualizations || []).filter((v) =>
    (!state.benchProvider || v.provider === state.benchProvider) &&
    (!state.chartSearch ||
      `${v.name} ${v.component} ${v.source_url}`.toLowerCase().includes(
        state.chartSearch.toLowerCase(),
      ))
  );
  const chosen =
    vs.find((v) => `${v.provider}:${v.source_index}` === state.sourceChart) ||
    vs[0];
  if (chosen) state.sourceChart = `${chosen.provider}:${chosen.source_index}`;
  return head(
    "Source charts",
    "Original chart datasets and published result tables. Select a series and fields.",
  ) +
    `<div class="toolbar">${
      select(
        "benchProvider",
        Object.entries(providerNames).filter(([id]) =>
          index.data.sources.some((s) => s.provider === id)
        ),
        state.benchProvider,
        "All evaluators",
      )
    }<input id="chartSearch" type="search" placeholder="Find an original chart…" value="${
      esc(state.chartSearch || "")
    }" aria-label="Find original chart">${
      select(
        "sourceChart",
        vs.map(
          (v) => [
            `${v.provider}:${v.source_index}`,
            `${providerNames[v.provider]} · ${
              v.source_url.split("/").filter(Boolean).at(-1).replaceAll(
                "_",
                " ",
              )
            } · ${v.name || v.component}`,
          ],
        ),
        state.sourceChart,
        "",
        'class="wide" aria-label="Original chart dataset"',
      )
    }<button data-action="chart-json">↓ JSON</button></div><div id="source-chart-content">${
      chosen ? '<div class="empty">Reading original chart data…</div>' : empty(
        "No numeric chart datasets match",
        "Choose a different source or search term.",
      )
    }</div>`;
}
async function loadSourceChart() {
  const key = state.sourceChart;
  if (!key) return;
  const [provider, i] = key.split(":");
  try {
    let chart = chartCache.get(key);
    if (!chart) {
      chart = await readJSON(chartPath(provider, i));
      chartCache.set(key, chart);
    }
    if (state.view !== "charts" || state.sourceChart !== key) return;
    loadedChart = chart;
    renderSourceChart(chart);
  } catch (error) {
    if ($("#source-chart-content")) {
      $("#source-chart-content").innerHTML = empty(
        "Chart unavailable",
        error.message,
      );
    }
  }
}
function renderSourceChart(chart) {
  const sets = chartSeries(chart, index),
    chosen = sets.find((s) => s.path === state.chartPath) || sets[0];
  const sourceHeader = `<section class="section"><h3>${
    esc(chart.name || chart.component)
  }</h3><p class="small muted" style="margin-top:5px">Original component: ${
    esc(chart.component || "data")
  } · ${link(chart.source_url, "Original visualization ↗")}</p>${
    chart.notes
      ? `<p class="small warn" style="margin-top:7px">${
        esc(
          typeof chart.notes === "string"
            ? chart.notes
            : JSON.stringify(chart.notes),
        )
      }</p>`
      : ""
  }${
    chosen?.origin === "observations"
      ? `<p class="small muted" style="margin-top:8px">This source component loads its values from a shared results table. The series below uses the published observations from that exact benchmark page.</p><button style="margin-top:10px" data-open-test="${
        esc(chosen.benchmark_id)
      }">Open benchmark ranking</button>`
      : ""
  }</section>`;
  if (!chosen) {
    $("#source-chart-content").innerHTML = sourceHeader +
      `<div class="empty"><h2>No flat numeric series</h2><p>The original dataset is retained. Download its JSON to inspect this specialized structure.</p></div>`;
    return;
  }
  state.chartPath = chosen.path;
  const records = chosen.records,
    keys = [...new Set(records.flatMap(Object.keys))],
    nums = keys.filter((k) => records.some((r) => numeric(r[k]) !== null)),
    labels = keys.filter((k) =>
      records.some((r) => typeof r[k] === "string" && numeric(r[k]) === null)
    );
  if (!nums.includes(state.chartY)) {
    state.chartY = nums.find((k) =>
      /score|accuracy|performance|mean|pass|rating|value/i.test(k)
    ) || nums[0];
  }
  if (!nums.includes(state.chartX)) {
    state.chartX = nums.find((k) =>
      /cost|time|date|step|difficulty|effort_rank/i.test(k) &&
      k !== state.chartY
    ) || nums.find((k) =>
      k !== state.chartY
    ) || nums[0];
  }
  if (!labels.includes(state.chartLabel)) {
    state.chartLabel = labels.find((k) =>
      /model|label|name|company/i.test(k)
    ) || labels[0] || "";
  }
  const rows = records.map((r, i) => ({
    ...r,
    __label: String(r[state.chartLabel] ?? i + 1),
    __x: numeric(r[state.chartX]),
    __y: numeric(r[state.chartY]),
  })).filter((r) => r.__y !== null);
  const controls = `<div class="toolbar"><label for="chartPath">Series</label>${
    select(
      "chartPath",
      sets.map((s) => [s.path, `${s.path} (${s.records.length})`]),
      state.chartPath,
      "",
      'class="wide"',
    )
  }<label for="chartMode">View</label>${
    select("chartMode", [["bars", "Bars"], ["line", "Line"], [
      "scatter",
      "Scatter",
    ], ["table", "Table"]], state.chartMode)
  }</div><div class="toolbar"><label for="chartLabel">Label</label>${
    select("chartLabel", labels, state.chartLabel, "Row number")
  }<label for="chartY">Value / Y</label>${
    select("chartY", nums, state.chartY)
  }${
    ["line", "scatter"].includes(state.chartMode)
      ? `<label for="chartX">X</label>${select("chartX", nums, state.chartX)}`
      : ""
  }<span class="small muted">${rows.length} numeric rows · source field units</span></div>`;
  const picked = rows.slice(0, Math.max(state.limit, 40));
  let plot = "";
  if (state.chartMode !== "table") {
    const w = 950,
      l = state.chartMode === "bars" ? 240 : 65,
      r = 40,
      t = 25,
      b = 50,
      h = state.chartMode === "bars"
        ? Math.max(200, picked.length * 29 + 60)
        : 460,
      min = Math.min(0, ...picked.map((r) => r.__y)),
      max = Math.max(1, ...picked.map((r) => r.__y)),
      dy = max - min || 1;
    plot = svgStart(w, h, `${chart.name}: ${state.chartY}`);
    if (state.chartMode === "bars") {
      const x = (v) => l + (v - min) / dy * (w - l - r);
      picked.forEach((rec, i) => {
        const yy = t + i * 29;
        plot += `<g><title>${esc(rec.__label)} · ${
          esc(state.chartY)
        }: ${rec.__y}</title><text class="label" x="0" y="${yy + 5}">${
          esc(short(rec.__label, 31))
        }</text><rect x="${Math.min(x(0), x(rec.__y))}" y="${yy - 9}" width="${
          Math.max(1, Math.abs(x(rec.__y) - x(0)))
        }" height="20" fill="${
          palette[i % palette.length]
        }" opacity=".8"/><text x="${x(rec.__y) + 6}" y="${yy + 5}">${
          fmt(rec.__y, 3)
        }</text></g>`;
      });
    } else {
      const ps = picked.filter((r) => r.__x !== null).sort((a, b) =>
          a.__x - b.__x
        ),
        lo = Math.min(...ps.map((r) => r.__x)),
        hi = Math.max(...ps.map((r) => r.__x)),
        x = (v) => l + (v - lo) / (hi - lo || 1) * (w - l - r),
        y = (v) => h - b - (v - min) / dy * (h - t - b);
      for (let i = 0; i <= 4; i++) {
        const yy = t + (h - b - t) * i / 4;
        plot += `<line class="grid" x1="${l}" x2="${
          w - r
        }" y1="${yy}" y2="${yy}"/><text x="${l - 8}" y="${
          yy + 4
        }" text-anchor="end">${compact(max - dy * i / 4)}</text>`;
        const xx = l + (w - l - r) * i / 4;
        plot += `<text x="${xx}" y="${h - b + 24}" text-anchor="middle">${
          compact(lo + (hi - lo) * i / 4)
        }</text>`;
      }
      if (state.chartMode === "line") {
        plot += `<path d="${
          ps.map((p, i) => `${i ? "L" : "M"}${x(p.__x)},${y(p.__y)}`).join(" ")
        }" stroke="${palette[0]}" fill="none" stroke-width="2"/>`;
      }
      ps.forEach((p, i) =>
        plot += `<circle cx="${x(p.__x)}" cy="${y(p.__y)}" r="4" fill="${
          palette[i % palette.length]
        }"><title>${esc(p.__label)} · ${esc(state.chartX)}: ${p.__x}, ${
          esc(state.chartY)
        }: ${p.__y}</title></circle>`
      );
      plot += `<text x="${w / 2}" y="${h - 4}" text-anchor="middle">${
        esc(state.chartX)
      }</text>`;
    }
    plot += "</svg>";
  }
  const tableKeys = [
    ...new Set([
      state.chartLabel,
      state.chartX,
      state.chartY,
      ...keys.slice(0, 9),
    ]),
  ].filter(Boolean).slice(0, 12);
  $("#source-chart-content").innerHTML = sourceHeader + controls +
    (plot
      ? `<div class="chart-wrap">${plot}</div><p class="chart-note">Showing the first ${picked.length} rows in this series. Field names and units come from the original chart. Line connections are an exploratory rendering, not an inferred historical series.</p>`
      : "") +
    `<div class="table-wrap quiet-scroll"><table><thead><tr>${
      tableKeys.map((k) => `<th>${esc(k)}</th>`).join("")
    }</tr></thead><tbody>${
      records.slice(0, 250).map((rec) =>
        `<tr>${
          tableKeys.map((k) =>
            `<td>${
              esc(
                typeof rec[k] === "number" ? fmt(rec[k], 4) : short(rec[k], 90),
              )
            }</td>`
          ).join("")
        }</tr>`
      ).join("")
    }</tbody></table></div>`;
}

function openTest(id) {
  set({
    weights: { [id]: 100 },
    view: "rankings",
    selected: null,
    selectedObservation: null,
    page: 0,
    showNav: false,
  });
  $("#main").scrollTop = 0;
}
function addTest(id) {
  const current = Object.keys(state.weights);
  if (!state.weights[id]) {
    state.weights[id] = current.length
      ? Math.max(1, ...Object.values(state.weights))
      : 1;
  }
  set({ weights: { ...state.weights }, page: 0 });
}
function expandTests() {
  const b = primary();
  if (!b) return;
  let ids = (b.components || []).map((c) => c.benchmark_id).filter((id) =>
    index.benchmarks.has(id)
  );
  if (ids.length) {
    state.weights = Object.fromEntries(
      b.components.filter((c) => ids.includes(c.benchmark_id)).map(
        (c) => [c.benchmark_id, Math.round(c.weight * 100) || 1],
      ),
    );
  } else {
    ids = index.data.benchmarks.filter((t) =>
      t.provider === b.provider && !t.parent_benchmark_id && !t.archived &&
      t.kind === "benchmark" && !["Other", "Preference"].includes(t.category) &&
      t.observation_count > 10
    ).slice(0, 8).map((t) => t.id);
    state.weights = Object.fromEntries(ids.map((id) => [id, 1]));
  }
  set({ weights: state.weights, missing: "available", coverage: 30 });
}
function compareToggle(id) {
  const list = new Set(state.compare);
  list.has(id) ? list.delete(id) : list.add(id);
  if (list.size > 6) return toast("Compare up to six models at a time.");
  set({ compare: [...list] });
}
function inspectRow(key) {
  set({
    selected: key,
    selectedObservation: null,
    inspectorTab: "evidence",
    hideInspector: false,
    showInspector: innerWidth < 920,
  });
}
function inspectObservation(id) {
  set({
    selected: null,
    selectedObservation: id,
    inspectorTab: "evidence",
    hideInspector: false,
    showInspector: innerWidth < 920,
  });
}
function download(name, text, type) {
  const blob = new Blob([text], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function exportCSV() {
  const fields = [
    "rank",
    "canonical_model",
    "original_model",
    "lab",
    "custom_score",
    "coverage",
    "test",
    "version",
    "raw_score",
    "unit",
    "effort",
    "harness",
    "inference_provider",
    "evaluator",
    "provenance",
    "cost_usd",
    "ci_low",
    "ci_high",
    "ci_kind",
    "stderr",
    "result_date",
    "retrieved_at",
    "source_url",
    "license_url",
    "modifications",
  ];
  const lines = [fields];
  for (const r of rows) {
    for (const o of Object.values(r.observations)) {
      const b = index.benchmarks.get(o.benchmark_id);
      lines.push([
        r.rank,
        r.model.name,
        o.model,
        r.model.lab,
        native() ? "" : r.score,
        r.coverage,
        b.name,
        b.version,
        o.score,
        b.unit,
        o.effort,
        o.harness,
        o.inference_provider,
        o.evaluator || providerNames[o.provider],
        o.provenance || "direct",
        o.cost_usd,
        o.ci_low,
        o.ci_high,
        o.ci_kind,
        o.stderr ?? o.standard_error,
        o.date,
        o.retrieved_at,
        o.source_url,
        index.data.sources.find((s) => s.provider === o.provider)
          ?.license_url || "",
        "Units normalized; weighted scores calculated by AI Rankings",
      ]);
    }
  }
  const quote = (v) =>
    '"' + String(v ?? "").replace(/^[=+@]/, "'$&").replaceAll('"', '""') + '"';
  download(
    "ai-rankings.csv",
    lines.map((row) => row.map(quote).join(",")).join("\r\n"),
    "text/csv;charset=utf-8",
  );
  toast("Exported scores with source attribution.");
}
function exportSVG() {
  const original = $("#main svg.chart");
  if (!original) return toast("This view has no SVG chart.");
  const svg = original.cloneNode(true);
  const metadata = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "metadata",
  );
  metadata.textContent = JSON.stringify({
    sources: index.data.sources.map((s) => ({
      name: s.name,
      url: s.url,
      license: s.license_url,
    })),
    tests: selectedTests(),
    weights: state.weights,
    modifications:
      "Chart rendered by AI Rankings; custom scores use selected weights.",
  });
  svg.prepend(metadata);
  svg.insertAdjacentHTML(
    "afterbegin",
    '<style>text{font-family:system-ui,sans-serif;font-size:12px;fill:#a6a6a6}.label{fill:#ececec}.grid{stroke:#343434;stroke-width:1}.axis{stroke:#575757}</style><rect width="100%" height="100%" fill="#1b1b1b"/>',
  );
  download(
    "ai-rankings-chart.svg",
    new XMLSerializer().serializeToString(svg),
    "image/svg+xml",
  );
}
async function refreshSources(sources) {
  if (runtime.mode === "static") {
    chartCache.clear();
    await loadData(false);
    toast("Published data reloaded.");
    return;
  }
  try {
    const response = await fetch("/api/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sources ? { sources } : {}),
    });
    if (!response.ok && response.status !== 409) {
      throw Error("Refresh could not start");
    }
    set({ view: "sources" });
    toast("Source refresh started. Existing results remain available.");
    const poll = async () => {
      const s = await (await fetch("/api/refresh/status")).json();
      const node = $("#refresh-status");
      if (node) {
        node.innerHTML = `<section class="section"><h3>${
          s.running ? "Refreshing public sources…" : "Refresh finished"
        }</h3><pre class="progress-log quiet-scroll">${
          esc(s.messages.slice(-12).join("\n"))
        }</pre></section>`;
      }
      if (s.running) setTimeout(poll, 1500);
      else {
        await loadData(false);
        toast(
          "Source refresh finished. Check source status for any retained snapshots.",
        );
      }
    };
    poll();
  } catch (e) {
    toast(e.message);
  }
}
document.addEventListener("click", async (event) => {
  const target = event.target.closest(
    "button,[data-row],[data-observation],[data-compare]",
  );
  if (!target) return;
  if (target.dataset.compare) return;
  if (target.dataset.view) {
    set({ view: target.dataset.view, page: 0, showNav: false });
    $("#main").scrollTop = 0;
    return;
  }
  if (target.dataset.pane) {
    set({ inspectorTab: target.dataset.pane });
    return;
  }
  if (target.dataset.openTest) {
    openTest(target.dataset.openTest);
    return;
  }
  if (target.dataset.addTest) {
    addTest(target.dataset.addTest);
    return;
  }
  if (target.dataset.removeTest) {
    delete state.weights[target.dataset.removeTest];
    set({ weights: { ...state.weights } });
    return;
  }
  if (target.dataset.toggleCompare) {
    compareToggle(target.dataset.toggleCompare);
    return;
  }
  if (target.dataset.removeCompare) {
    set({
      compare: state.compare.filter((id) =>
        id !== target.dataset.removeCompare
      ),
    });
    return;
  }
  if (target.dataset.refreshSource) {
    await refreshSources([target.dataset.refreshSource]);
    return;
  }
  if (target.dataset.layout) {
    set({ layout: target.dataset.layout });
    return;
  }
  if (target.dataset.page !== undefined) {
    set({ page: +target.dataset.page });
    $("#main").scrollTop = 0;
    return;
  }
  if (target.dataset.observation) {
    inspectObservation(target.dataset.observation);
    return;
  }
  if (target.dataset.row) {
    if (event.target.closest("a,input")) return;
    inspectRow(target.dataset.row);
    return;
  }
  const action = target.dataset.action;
  if (action === "nav") set({ showNav: !state.showNav });
  if (action === "inspector") {
    if (innerWidth < 920) {
      set({ showInspector: !state.showInspector, hideInspector: false });
    } else set({ hideInspector: !state.hideInspector });
  }
  if (action === "reset-filters") {
    set({
      query: "",
      lab: "",
      access: "",
      effort: "",
      country: "",
      modality: "",
      since: "",
      benchSearch: "",
      benchProvider: "",
      benchCategory: "",
      benchKind: "",
      page: 0,
    });
  }
  if (action === "reset") {
    state = { ...defaults, weights: { [bestBenchmark().id]: 100 } };
    render();
    save();
  }
  if (action === "equal") {
    set({
      weights: Object.fromEntries(selectedTests().map((id) => [id, 100])),
    });
  }
  if (action === "matrix-expand") expandTests();
  if (action === "export") exportCSV();
  if (action === "svg") exportSVG();
  if (action === "refresh") await refreshSources();
  if (action === "share") {
    const config = { ...state };
    delete config.addSearch;
    delete config.showNav;
    delete config.showInspector;
    const hash = btoa(unescape(encodeURIComponent(JSON.stringify(config))));
    const link = new URL("./", location.href).href + "#v1=" + hash;
    try {
      await navigator.clipboard.writeText(link);
      toast("View link copied, including selected tests and weights.");
    } catch {
      location.hash = "v1=" + hash;
      toast("Settings are in the address bar. Copy its URL.");
    }
  }
  if (action === "chart-json" && loadedChart) {
    download(
      "source-chart.json",
      JSON.stringify(loadedChart, null, 2),
      "application/json",
    );
  }
});
document.addEventListener("change", (event) => {
  const t = event.target;
  if (t.dataset.compare) {
    compareToggle(t.dataset.compare);
    return;
  }
  if (t.dataset.weight || t.dataset.weightNumber) {
    const id = t.dataset.weight || t.dataset.weightNumber;
    state.weights[id] = clamp(+t.value || 0, 0, 1000);
    set({ weights: { ...state.weights } });
    return;
  }
  if (t.id === "quick-test" && t.value) {
    openTest(t.value);
    return;
  }
  if (t.id === "preset" && t.value) {
    preset(t.value);
    return;
  }
  if (t.id === "coverage-number") {
    set({ coverage: clamp(+t.value || 0, 0, 100) });
    return;
  }
  if (t.id in defaults || ["chartSearch"].includes(t.id)) {
    let v = t.type === "checkbox" ? t.checked : t.value;
    if (["limit", "coverage"].includes(t.id)) v = +v;
    const patch = { [t.id]: v };
    if (t.id === "sourceChart") {
      Object.assign(patch, {
        chartPath: "",
        chartY: "",
        chartX: "",
        chartLabel: "",
      });
    }
    if (t.id.startsWith("bench") || ["subtasks", "archived"].includes(t.id)) {
      patch.page = 0;
    }
    if (
      ["chartPath", "chartY", "chartX", "chartLabel", "chartMode"].includes(
        t.id,
      )
    ) {
      Object.assign(state, patch);
      if (loadedChart) renderSourceChart(loadedChart);
      save();
    } else set(patch);
  }
});
let inputTimer;
document.addEventListener("input", (event) => {
  const t = event.target,
    keys = {
      "model-query": "query",
      "add-search": "addSearch",
      benchSearch: "benchSearch",
      chartSearch: "chartSearch",
    };
  if (keys[t.id]) {
    clearTimeout(inputTimer);
    inputTimer = setTimeout(() => set({ [keys[t.id]]: t.value, page: 0 }), 160);
  }
  if (t.id === "coverage") $("#coverage-number").value = t.value;
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    set({ showNav: false, showInspector: false });
    $("#tooltip").hidden = true;
  }
  if (
    (event.key === "Enter" || event.key === " ") &&
    event.target.matches("svg [data-row]")
  ) {
    event.preventDefault();
    inspectRow(event.target.dataset.row);
  }
});
document.addEventListener("pointermove", (event) => {
  const target = event.target.closest(
    "svg [data-row],.heat-cell[data-observation]",
  );
  const tooltip = $("#tooltip");
  if (!target) {
    tooltip.hidden = true;
    return;
  }
  const row = target.dataset.row ? rowMap.get(target.dataset.row) : null;
  const o = target.dataset.observation
    ? index.data.observations.find((o) => o.id === target.dataset.observation)
    : row
    ? observation(row)
    : null;
  if (!o) {
    tooltip.hidden = true;
    return;
  }
  const b = index.benchmarks.get(o.benchmark_id);
  tooltip.innerHTML = `<strong>${esc(o.model)}</strong><div>${esc(b.name)}: ${
    fmt(o.score, 3)
  } ${esc(b.unit)}</div><div class="muted">${
    esc(providerNames[o.provider])
  } · ${esc(o.effort || "effort unreported")}</div>${
    o.harness ? `<div class="muted">${esc(short(o.harness, 80))}</div>` : ""
  }<div class="muted">Click for evidence</div>`;
  tooltip.hidden = false;
  tooltip.style.left = Math.min(event.clientX + 14, innerWidth - 350) + "px";
  tooltip.style.top =
    Math.min(event.clientY + 14, innerHeight - tooltip.offsetHeight - 12) +
    "px";
});
async function loadData(initial = true) {
  const data = await readJSON(runtime.catalog);
  index = prepare(data);
  state.weights = Object.fromEntries(
    Object.entries(state.weights || {}).filter(([id]) =>
      index.benchmarks.has(id)
    ),
  );
  if (!selectedTests().length && bestBenchmark()) {
    state.weights = { [bestBenchmark().id]: 100 };
  }
  render();
  save();
  window.__rankings = {
    state,
    index,
    get rows() {
      return rows;
    },
    set,
    rank,
    render,
    selectedTests,
  };
}
loadData().catch((error) => {
  $("#app").innerHTML =
    `<div class="boot"><h1>Could not load the catalog</h1><p>${
      esc(error.message)
    }</p><a href="./">Retry</a></div>`;
});
