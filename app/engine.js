// Pure ranking calculations. Source results and custom scores stay separate.
export const finite = (v) => typeof v === "number" && Number.isFinite(v);
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export function percentile(value, values, higher = true) {
  if (!values.length) return null;
  if (values.length === 1) return 50;
  const below = values.filter((v) => v < value).length;
  const equal = values.filter((v) => v === value).length;
  const p = clamp(
    100 * (below + (equal - 1) / 2) / (values.length - 1),
    0,
    100,
  );
  return higher ? p : 100 - p;
}
export function normalized(value, benchmark, reference, mode = "scale") {
  if (!finite(value)) return null;
  if (
    mode === "percentile" || !finite(benchmark.min) || !finite(benchmark.max) ||
    benchmark.max <= benchmark.min
  ) {
    return percentile(value, reference, benchmark.higher_is_better !== false);
  }
  const score = clamp(
    100 * (value - benchmark.min) / (benchmark.max - benchmark.min),
    0,
    100,
  );
  return benchmark.higher_is_better === false ? 100 - score : score;
}
export function configuration(o) {
  return `${o.model_id}|${String(o.effort || "unspecified").toLowerCase()}|${
    o.harness || "unspecified"
  }|${o.inference_provider || "unspecified"}`;
}
export function prepare(data) {
  const benchmarks = new Map(data.benchmarks.map((b) => [b.id, b]));
  const models = new Map(data.models.map((m) => [m.id, m]));
  const byBenchmark = new Map();
  for (const o of data.observations) {
    if (!byBenchmark.has(o.benchmark_id)) byBenchmark.set(o.benchmark_id, []);
    byBenchmark.get(o.benchmark_id).push(o);
  }
  // Percentile baselines are fixed to this entire snapshot, never the visible filter.
  const references = new Map();
  for (const [id, values] of byBenchmark) {
    const b = benchmarks.get(id), best = new Map();
    for (const o of values) {
      const previous = best.get(o.model_id);
      if (
        !previous ||
        (b.higher_is_better === false
          ? o.score < previous.score
          : o.score > previous.score)
      ) best.set(o.model_id, o);
    }
    references.set(id, [...best.values()].map((o) => o.score));
  }
  return { data, benchmarks, models, byBenchmark, references };
}
export function matches(model, o, state) {
  if (!model) return false;
  if (
    state.query &&
    !`${model.name} ${o.model} ${model.lab}`.toLowerCase().includes(
      state.query.toLowerCase(),
    )
  ) return false;
  if (state.lab && model.lab !== state.lab) return false;
  const access = o.weights || model.weights || "unknown";
  if (state.access && access !== state.access) return false;
  if (
    state.effort && !String(o.effort || "").toLowerCase().includes(state.effort)
  ) return false;
  if (state.country && (o.country || model.country) !== state.country) {
    return false;
  }
  if (
    state.modality &&
    !String(o.modalities || model.modalities || "").toLowerCase().includes(
      state.modality,
    )
  ) return false;
  if (!state.deprecated && o.deprecated === true) return false;
  if (
    state.since && (o.release_date || model.release_date || "") < state.since
  ) return false;

  return true;
}
export function rank(index, state) {
  const selected = Object.entries(state.weights || {}).filter(([id, weight]) =>
    index.benchmarks.has(id) && finite(+weight) && +weight > 0
  );
  const totalWeight = selected.reduce((sum, [, w]) => sum + +w, 0);
  if (!totalWeight) return [];
  const groups = new Map();
  for (const [id, weight] of selected) {
    const b = index.benchmarks.get(id);
    for (const o of index.byBenchmark.get(id) || []) {
      const model = index.models.get(o.model_id);
      if (!model) continue;
      if (!matches(model, o, state)) continue;
      const key = state.group === "configuration"
        ? configuration(o)
        : o.model_id;
      const group = groups.get(key) ||
        { key, model, values: {}, observations: {}, availableWeight: 0 };
      const previous = group.observations[id];
      if (
        !previous ||
        (b.higher_is_better === false
          ? o.score < previous.score
          : o.score > previous.score)
      ) {
        group.observations[id] = o;
        group.values[id] = normalized(
          o.score,
          b,
          index.references.get(id) || [],
          state.normalization,
        );
      }
      groups.set(key, group);
    }
  }
  const rows = [];
  for (const group of groups.values()) {
    let numerator = 0, availableWeight = 0;
    for (const [id, weight] of selected) {
      if (finite(group.values[id])) {
        numerator += group.values[id] * +weight;
        availableWeight += +weight;
      }
    }
    const coverage = availableWeight / totalWeight;
    if (state.missing === "exclude" && coverage < 1 - 1e-9) continue;
    if (coverage * 100 + 1e-9 < +(state.coverage || 0)) continue;
    const denominator = state.missing === "zero"
      ? totalWeight
      : availableWeight;
    if (!denominator) continue;
    const raw = selected.length === 1
      ? group.observations[selected[0][0]].score
      : null;
    rows.push({
      ...group,
      coverage,
      score: numerator / denominator,
      raw,
      availableWeight,
      totalWeight,
      contributions: Object.fromEntries(
        selected.map((
          [id, w],
        ) => [
          id,
          finite(group.values[id]) ? group.values[id] * +w / denominator : 0,
        ]),
      ),
    });
  }
  const single = selected.length === 1
    ? index.benchmarks.get(selected[0][0])
    : null;
  rows.sort((a, b) =>
    single
      ? (single.higher_is_better === false ? a.raw - b.raw : b.raw - a.raw) ||
        a.model.name.localeCompare(b.model.name)
      : b.score - a.score || a.model.name.localeCompare(b.model.name)
  );
  rows.forEach((row, i) => row.rank = i + 1);
  return rows;
}
export function pareto(points, higherY = true, higherX = false) {
  return points.filter((p) =>
    !points.some((q) =>
      q !== p && (higherX ? q.x >= p.x : q.x <= p.x) &&
      (higherY ? q.y >= p.y : q.y <= p.y) && (q.x !== p.x || q.y !== p.y)
    )
  ).sort((a, b) => a.x - b.x);
}
export function sensitivity(index, state, target) {
  const others = Object.keys(state.weights).filter((id) =>
    id !== target && state.weights[id] > 0
  );
  const total = others.reduce((s, id) => s + +state.weights[id], 0);
  if (!total) return [];
  return Array.from({ length: 21 }, (_, i) => {
    const share = i * 5;
    const weights = Object.fromEntries(
      others.map((id) => [id, (100 - share) * state.weights[id] / total]),
    );
    weights[target] = share || 0.000001;
    return { share, rows: rank(index, { ...state, weights }) };
  });
}
