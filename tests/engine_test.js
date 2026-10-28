import {
  configuration,
  normalized,
  pareto,
  percentile,
  prepare,
  rank,
  sensitivity,
} from "../app/engine.js";

function assert(value, message = "assertion failed") {
  if (!value) throw Error(message);
}
function close(actual, expected) {
  assert(Math.abs(actual - expected) < 1e-7, `${actual} != ${expected}`);
}
const benchmarks = [
  { id: "a", min: 0, max: 100, higher_is_better: true },
  { id: "b", min: 0, max: 10, higher_is_better: false },
];
const models = ["fast", "accurate", "partial"].map((id) => ({
  id,
  name: id,
  lab: id === "partial" ? "Other" : "Lab",
}));
const observations = [
  {
    model_id: "fast",
    model: "fast",
    benchmark_id: "a",
    score: 40,
    effort: "high",
    harness: "same",
  },
  {
    model_id: "fast",
    model: "fast",
    benchmark_id: "b",
    score: 1,
    effort: "high",
    harness: "same",
  },
  {
    model_id: "accurate",
    model: "accurate",
    benchmark_id: "a",
    score: 90,
    effort: "high",
    harness: "same",
  },
  {
    model_id: "accurate",
    model: "accurate",
    benchmark_id: "b",
    score: 9,
    effort: "low",
    harness: "other",
  },
  { model_id: "partial", model: "partial", benchmark_id: "a", score: 100 },
];
const index = prepare({ models, benchmarks, observations });
const state = {
  weights: { a: 1, b: 1 },
  missing: "exclude",
  coverage: 100,
  normalization: "scale",
  group: "models",
};

Deno.test("weighting and direction change the leader without changing raw evidence", () => {
  const equal = rank(index, state);
  assert(equal[0].model.id === "fast");
  close(equal[0].score, 65);
  const weighted = rank(index, { ...state, weights: { a: 9, b: 1 } });
  assert(weighted[0].model.id === "accurate");
  close(weighted[0].score, 82);
  assert(weighted[0].observations.a === observations[2]);
  close(
    Object.values(weighted[0].contributions).reduce((a, b) => a + b),
    weighted[0].score,
  );
  assert(rank(index, { ...state, weights: { b: 1 } })[0].raw === 1);
});
Deno.test("missing evidence has explicit, distinct policies and weighted coverage", () => {
  assert(rank(index, state).length === 2);
  const available = rank(index, { ...state, missing: "available", coverage: 0 })
    .find((r) => r.model.id === "partial");
  close(available.score, 100);
  close(available.coverage, .5);
  close(
    rank(index, { ...state, missing: "zero", coverage: 0 }).find((r) =>
      r.model.id === "partial"
    ).score,
    50,
  );
  assert(
    !rank(index, { ...state, missing: "available", coverage: 51 }).some((r) =>
      r.model.id === "partial"
    ),
  );
});
Deno.test("matched configurations do not combine different effort, agents, or endpoints", () => {
  const rows = rank(index, { ...state, group: "configuration" });
  assert(rows.length === 1 && rows[0].model.id === "fast");
  assert(
    configuration({ ...observations[0], inference_provider: "A" }) !==
      configuration({ ...observations[0], inference_provider: "B" }),
  );
});
Deno.test("percentile baseline stays fixed under filters and clamps weaker variants", () => {
  const s = { ...state, weights: { a: 1, b: 1 }, normalization: "percentile" };
  const before = rank(index, s).find((r) => r.model.id === "fast").score;
  close(rank(index, { ...s, query: "fast" })[0].score, before);
  close(percentile(-20, [10, 20, 30]), 0);
  close(percentile(100, [10, 20, 30]), 100);
  close(percentile(20, [10, 20, 20, 30]), 50);
  close(normalized(9, benchmarks[1], []), 10);
});
Deno.test("Pareto frontier respects both axis directions", () => {
  const a = { x: 1, y: 80 }, b = { x: 2, y: 70 }, c = { x: 3, y: 95 };
  const front = pareto([a, b, c]);
  assert(front.includes(a) && front.includes(c) && !front.includes(b));
  assert(pareto([a, b, c], true, true).length === 1);
});
Deno.test("sensitivity crosses from speed winner to accuracy winner", () => {
  const runs = sensitivity(index, state, "a");
  assert(runs.length === 21);
  assert(runs[0].rows[0].model.id === "fast");
  assert(runs.at(-1).rows[0].model.id === "partial");
  assert(runs[18].rows[0].model.id === "accurate");
});
