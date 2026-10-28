import { chartSeries, datasets, numeric } from "../app/source-charts.js";
function assert(value, message = "assertion failed") {
  if (!value) throw Error(message);
}

Deno.test("chart structures retain units, labels and negative numbers", () => {
  const result = datasets({
    study: [{ model: "A", metrics: { score: "-12.5%", usd: 0 } }, {
      model: "B",
      metrics: { score: "72%", usd: null },
    }],
  });
  assert(result[0].records[0]["metrics.score"] === "-12.5%");
  assert(numeric(result[0].records[0]["metrics.score"]) === -12.5);
  assert(
    numeric(null) === null && numeric(false) === null &&
      numeric("missing") === null,
  );
});
Deno.test("shared chart props resolve only the exact source page, without mixing tests", () => {
  const page = "https://www.vals.ai/benchmarks/example";
  const index = {
    data: {
      benchmarks: [{ id: "a", name: "A", source_url: page, unit: "%" }, {
        id: "b",
        name: "B",
        source_url: page,
        unit: "USD",
      }, { id: "c", name: "A", source_url: page + "-old", unit: "%" }],
    },
    byBenchmark: new Map([
      ["a", [{ model: "A", score: 80, source_url: page }]],
      ["b", [{ model: "A", score: 2, source_url: page }]],
      ["c", [{ model: "A", score: 99 }]],
    ]),
  };
  const result = chartSeries(
    { source_url: page, data: { title: "Example" } },
    index,
  );
  assert(result.length === 2);
  assert(result[0].origin === "observations");
  assert(
    result[0].records[0].score === 80 && result[1].records[0].unit === "USD",
  );
  assert(result[0].records[0].cost_usd === undefined);
  const embedded = chartSeries({
    source_url: page,
    data: { projections: [{ model: "A", score: 90 }] },
  }, index);
  assert(embedded.length === 1 && embedded[0].path === "projections");
  assert(
    !embedded[0].origin,
    "Projections must not become observed benchmark results",
  );
});
