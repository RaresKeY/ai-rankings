"""Data extraction safeguards that protect cross-provider ranking semantics."""
import json
from pathlib import Path
import unittest

from scripts.adapters.vals import LiteralReader, Page, _benchmark, _observation, _url


class ValsExtractionTests(unittest.TestCase):
    def test_public_asset_literal_reader_never_executes_expressions(self):
        parsed = LiteralReader('{name:"A \\"quoted\\" model",open:!0,missing:null,price:.5,limit:128e3,rows:[1,!1]}').value()
        self.assertEqual(parsed["name"], 'A "quoted" model')
        self.assertEqual(parsed["limit"], 128000)
        self.assertEqual(parsed["rows"], [1, False])
        with self.assertRaises(ValueError):
            LiteralReader('{score:fetch("https://bad.example")}').value()

    def test_untrusted_data_cannot_redirect_refresh_to_another_host(self):
        with self.assertRaises(ValueError):
            _url("https://example.org/payload.json")
        self.assertEqual(_url("/_astro/result.json"), "https://www.vals.ai/_astro/result.json")

    def test_missing_costs_and_standard_errors_remain_distinct(self):
        metadata = {"benchmark": "Test", "tasks": {"overall": "Overall"}, "industry": "coding"}
        benchmark = _benchmark(metadata, "overall", "https://www.vals.ai/benchmarks/test", "https://www.vals.ai/test.json")
        observation = _observation(benchmark, "lab/model", {"accuracy": 0, "stderr": 2, "cost_per_test": 0, "latency": 0}, {}, {}, "source")
        self.assertEqual(observation["score"], 0)
        self.assertEqual(observation["stderr"], 2)
        self.assertNotIn("ci_low", observation)
        self.assertNotIn("ci_high", observation)
        self.assertNotIn("cost_usd", observation)
        self.assertNotIn("latency_seconds", observation)
        self.assertEqual(observation["source_metrics"]["unreported_cost_zero"], 0)

    def test_reference_index_and_poker_ratings_do_not_become_percentages(self):
        common = {"benchmark": "Index", "tasks": {"overall": "Overall"}, "industry": "index"}
        rsi = _benchmark(dict(common, family="rsi_index"), "overall", "https://www.vals.ai/benchmarks/rsi_index", "source")
        observation = _observation(rsi, "lab/model", {"accuracy": 37.31}, {}, {}, "source")
        self.assertEqual((rsi["unit"], rsi["max"]), ("score", 1))
        self.assertAlmostEqual(observation["score"], 0.3731)
        self.assertEqual(observation["source_metrics"]["accuracy_scaled_100"], 37.31)
        poker = _benchmark(dict(common, accuracy_label="TrueSkill Rating"), "overall", "https://www.vals.ai/benchmarks/poker_agent", "source")
        self.assertEqual(poker["unit"], "score")
        self.assertIsNone(poker["max"])

    def test_task_and_version_identity_survives(self):
        metadata = {"benchmark": "Index", "tasks": {"overall": "Overall", "legal": "Legal"}, "version": "1", "archived": True}
        overall = _benchmark(metadata, "overall", "https://www.vals.ai/benchmarks/index-v1", "source")
        task = _benchmark(metadata, "legal", "https://www.vals.ai/benchmarks/index-v1", "source")
        self.assertNotEqual(overall["id"], task["id"])
        self.assertEqual(task["parent_benchmark_id"], overall["id"])
        self.assertTrue(task["archived"])
        self.assertEqual(task["version"], "1")

    def test_checked_source_pack_references_and_metric_bounds(self):
        source = Path(__file__).resolve().parents[1] / "data/sources/vals.json"
        if not source.exists():
            self.skipTest("No local snapshot")
        pack = json.loads(source.read_text())
        benchmarks = {row["id"]: row for row in pack["benchmarks"]}
        self.assertEqual(len(benchmarks), len(pack["benchmarks"]))
        chart_ids = [row["id"] for row in pack.get("visualization_data", [])]
        self.assertEqual(len(chart_ids), len(set(chart_ids)))
        self.assertTrue(pack["observations"])
        for row in pack["observations"]:
            benchmark = benchmarks[row["benchmark_id"]]
            if benchmark["min"] is not None:
                self.assertGreaterEqual(row["score"], benchmark["min"])
            if benchmark["max"] is not None:
                self.assertLessEqual(row["score"], benchmark["max"])
            self.assertTrue(row["source_url"].startswith("https://www.vals.ai/"))
            self.assertNotIn("ci_low", row)
            self.assertNotIn("ci_high", row)


if __name__ == "__main__":
    unittest.main()
