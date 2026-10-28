import { finite } from "./engine.js";
export function numeric(v) {
  if (finite(v)) return v;
  if (typeof v === "string" && /^[-+]?\d[\d,]*(\.\d+)?\s*%?$/.test(v.trim())) {
    return +v.replace(/[,%\s]/g, "");
  }
  return null;
}
function flatten(record, prefix = "", out = {}, depth = 0) {
  if (depth > 3 || !record || typeof record !== "object") return out;
  for (const [k, v] of Object.entries(record)) {
    const key = prefix ? prefix + "." + k : k;
    if (v === null || ["string", "number", "boolean"].includes(typeof v)) {
      out[key] = v;
    } else if (!Array.isArray(v)) flatten(v, key, out, depth + 1);
  }
  return out;
}
export function datasets(data) {
  const found = [];
  let budget = 0;
  function visit(v, path, depth) {
    if (++budget > 6000 || depth > 7 || !v || typeof v !== "object") return;
    if (Array.isArray(v)) {
      if (
        v.length &&
        v.some((x) => x && typeof x === "object" && !Array.isArray(x))
      ) {
        const records = v.filter((x) =>
          x && typeof x === "object" && !Array.isArray(x)
        ).map((x) => flatten(x));
        if (
          records.some((r) => Object.values(r).some((x) => numeric(x) !== null))
        ) found.push({ path: path || "data", records });
      }
      v.slice(0, 50).forEach((x, i) => visit(x, `${path}[${i}]`, depth + 1));
    } else {
      const entries = Object.entries(v);
      if (entries.length > 1 && entries.every(([, x]) => numeric(x) !== null)) {
        found.push({
          path: path || "data",
          records: entries.map(([name, value]) => ({
            name,
            value: numeric(value),
          })),
        });
      } else if (
        entries.length > 1 &&
        entries.every(([, x]) =>
          x && typeof x === "object" && !Array.isArray(x)
        )
      ) {
        const records = entries.map(([name, x]) => ({ name, ...flatten(x) }));
        if (
          records.some((r) => Object.values(r).some((x) => numeric(x) !== null))
        ) found.push({ path: (path || "data") + " {by key}", records });
      }
      entries.forEach(([k, x]) =>
        visit(x, path ? path + "." + k : k, depth + 1)
      );
    }
  }
  visit(data, "", 0);
  return found;
}

// Shared loader components store presentation props separately from result data.
// Resolve those against exactly the same source page, keeping tests separate.
export function chartSeries(chart, index) {
  const embedded = datasets(chart.data);
  if (embedded.length) return embedded;
  return index.data.benchmarks.filter((b) => b.source_url === chart.source_url)
    .map((b) => ({
      path: "Published observations · " + b.name,
      origin: "observations",
      benchmark_id: b.id,
      records: (index.byBenchmark.get(b.id) || []).map((o) => ({
        model: o.model,
        score: o.score,
        unit: b.unit,
        effort: o.effort,
        harness: o.harness,
        cost_usd: o.cost_usd,
        latency_seconds: o.latency_seconds,
        release_date: o.release_date,
        source_url: o.source_url,
        inference_provider: o.inference_provider,
      })),
    })).filter((s) => s.records.length);
}
