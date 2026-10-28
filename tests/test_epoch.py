"""Source contract checks for the distinctions most likely to mislead rankings."""
import csv
import io
import json
from pathlib import Path
import unittest
import zipfile

from scripts.adapters.epoch import (
    BASE, CONFIG, DATA, INTERNAL, LiteralReader, collect, metric_definition,
    transform_scale,
)


def as_csv(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def fixture_fetch():
    contents = {
        "model_metadata.csv": as_csv([{"model_version": "model_high", "display_name": "Model (high)", "organization": "Lab", "date": "2025-01-01", "accessibility": "Open weights (unrestricted)"}]),
        "benchmark_metadata.csv": as_csv([{"benchmark": "GPQA diamond", "source_file": "gpqa_diamond.csv", "random_baseline": 0.25, "score_ceiling": 1}]),
        "weirdml_external.csv": as_csv([{"Model version": "model_high", "Accuracy": 0.75, "Cost per run": 17, "Source": "Original evaluator", "Source link": "https://upstream.example/result", "Release date": "2025-01-01", "Accuracy SE": 0.02}]),
        "epoch_capabilities_index/eci_scores.csv": as_csv([{"Model": "Model", "Display name": "Model", "eci": 151, "eci_ci_low": 149, "eci_ci_high": 154, "date": "2025-01-01", "Organization": "Lab", "Model accessibility": "Open weights (unrestricted)"}]),
        "epoch_capabilities_index/edi_scores.csv": as_csv([{"benchmark_name": "GPQA diamond", "edi": 130, "estimated_slope_scaled": 0.1, "benchmark_release_date": "2023-01-01"}]),
        "epoch_capabilities_index/processed_data_for_eci.csv": as_csv([{"model": "Model", "model_version": "model_high", "benchmark": "GPQA diamond", "performance": 0.6, "source": "", "date": "2025-01-01"}]),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    catalog = b'''var data={gpqa:{id:`GPQA diamond`,title:`GPQA Diamond`,slug:`gpqa-diamond`,evaluator:`epoch-ai`,domains:[`Science`]},weirdml:{id:`weirdml`,title:`WeirdML`,slug:`weirdml`,evaluator:`benchmark-creator`,domains:[`Software engineering`]}};'''
    config = b'''var externalBenchmarkConfigs = {weirdml:{name:"WeirdML",source:"WeirdML evaluator",sourceLink:"https://upstream.example",accuracy:{column:"Accuracy",transform:(value)=>parseFloat(value)}}};'''
    internal = as_csv([{"Status": "Success", "task": "GPQA diamond", "task version": "1.0.1", "model": "model_high", "Display name": "Model (high)", "mean_score": 0.7, "stderr": 0.03, "started_at": "2025-01-20T10:00:00Z", "Version release date": "2025-01-01", "id_runs": "run-1", "Organization": "Lab", "Training compute (FLOP)": "1e25", "Parameters": "1e11"}])
    responses = {
        DATA: buffer.getvalue(),
        BASE + "/benchmarks/search": b'<astro-island component-url="/_astro/BenchmarkSearch.fixture.js"></astro-island>',
        BASE + "/_astro/BenchmarkSearch.fixture.js": b'import{x}from"./benchmarks.fixture.js";',
        BASE + "/_astro/benchmarks.fixture.js": catalog,
        CONFIG: config,
        INTERNAL: internal,
        BASE + "/data/cyber/eci_scores.csv": contents["epoch_capabilities_index/eci_scores.csv"],
    }
    return responses.__getitem__


class EpochAdapterTests(unittest.TestCase):
    def test_data_parser_does_not_execute_functions(self):
        parsed = LiteralReader('{value:`safe`, enabled:!0, transform:(x)=>dangerous(x), nested:[1,2]}').value()
        self.assertEqual(parsed["transform"], {"expression": "(x)=>dangerous(x)"})
        self.assertTrue(parsed["enabled"])
        self.assertEqual(parsed["nested"], [1, 2])
        with self.assertRaises(ValueError):
            transform_scale({"transform": parsed["transform"]})

    def test_percentage_scaling_and_lower_is_better(self):
        rows = metric_definition("aider", {"accuracy": {"column": "Percent correct", "transform": {"expression": "(x) => parseFloat(x) / 100"}}}, {})
        self.assertEqual(rows[0][2:4], ("%", 1))
        rows = metric_definition("btf3", {"accuracy": {"column": "Pooled score"}}, {"non_percentage_score": True, "lower_is_better": True})
        self.assertEqual(rows[0][2:], ("score", 1, True))

    def test_result_date_is_not_model_release_date(self):
        pack = collect(fixture_fetch())
        internal = next(o for o in pack["observations"] if o["provenance"] == "internal")
        self.assertEqual(internal["date"], "2025-01-20T10:00:00Z")
        self.assertEqual(internal["release_date"], "2025-01-01")
        self.assertEqual(internal["training_compute_flop"], 1e25)
        self.assertEqual(internal["parameters"], 1e11)
        self.assertEqual(internal["score"], 70)
        self.assertEqual(internal["ci_kind"], "±1 standard error")
        self.assertIsNone(internal["ci_level"])
        self.assertEqual(internal["benchmark_id"], "epoch-gpqa-diamond-1-0-1")
        for row in pack["observations"]:
            if row["provenance"] == "composite":
                self.assertIsNone(row["date"])
                self.assertEqual(row["ci_level"], 0.9)

    def test_external_provenance_and_cost_basis_survive(self):
        pack = collect(fixture_fetch())
        external = next(o for o in pack["observations"] if o["provenance"] == "external-via-epoch")
        self.assertEqual(external["source_url"], "https://upstream.example/result")
        self.assertEqual(external["evaluator"], "Original evaluator")
        self.assertEqual(external["published_costs"], {"Cost per run": 17})
        self.assertNotIn("cost_usd", external)
        self.assertEqual(external["effort"], "high")
        self.assertEqual(external["extraction_url"], DATA)
        self.assertEqual(external["archive_member"], "weirdml_external.csv")
        self.assertIsNone(external["date"])

    def test_adjusted_eci_inputs_are_not_raw_observations(self):
        pack = collect(fixture_fetch())
        self.assertEqual(len(pack["eci_inputs"]), 1)
        self.assertEqual(len(pack["observations"]), 4)
        self.assertEqual(pack["eci_fits"][0]["random_baseline"], 0.25)
        self.assertEqual(len(pack["visualization_data"]), 2)

    def test_committed_snapshot_integrity(self):
        path = Path(__file__).resolve().parents[1] / "data/sources/epoch.json"
        if not path.exists():
            self.skipTest("No committed source snapshot")
        pack = json.loads(path.read_text())
        benchmarks = {b["id"]: b for b in pack["benchmarks"]}
        self.assertEqual(len(benchmarks), len(pack["benchmarks"]))
        for row in pack["observations"]:
            b = benchmarks[row["benchmark_id"]]
            self.assertTrue(row["source_url"].startswith(("https://", "http://")))
            if b["unit"] == "%":
                self.assertGreaterEqual(row["score"], -1e-9, b["name"])
                self.assertLessEqual(row["score"], 100 + 1e-9, b["name"])
        self.assertFalse(benchmarks["epoch-btf3"]["higher_is_better"])
        self.assertFalse(benchmarks["epoch-ale-bench-rank"]["higher_is_better"])
        self.assertEqual(benchmarks["epoch-btf3"]["unit"], "score")


if __name__ == "__main__":
    unittest.main()
