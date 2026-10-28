"""Import Epoch's published data, retaining its original evaluator provenance.

No JavaScript is executed. The limited literal reader below reads public data
objects and retains function expressions as text; only explicit numeric scales
are recognized. Raw external observations remain labelled as Epoch's aggregation.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import io
import json
import math
import re
from urllib.parse import urljoin
import zipfile

BASE = "https://epoch.ai"
PAGE = BASE + "/benchmarks"
DATA = BASE + "/data/benchmark_data.zip"
ECI = BASE + "/eci"
CONFIG = BASE + "/generated/external-benchmarks-config.js"
INTERNAL = BASE + "/data/benchmarks.csv"


class LiteralReader:
    """Read inert JS object literals; never evaluate source expressions."""

    def __init__(self, text, start=0):
        self.text, self.pos = text, start

    def whitespace(self):
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text.startswith("//", self.pos):
                self.pos = self.text.find("\n", self.pos)
                if self.pos < 0:
                    self.pos = len(self.text)
            elif self.text.startswith("/*", self.pos):
                self.pos = self.text.index("*/", self.pos + 2) + 2
            else:
                break

    def string(self):
        quote = self.text[self.pos]
        self.pos += 1
        out = []
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == quote:
                return "".join(out)
            if char == "\\":
                char = self.text[self.pos]
                self.pos += 1
                if char == "u":
                    char = chr(int(self.text[self.pos:self.pos + 4], 16))
                    self.pos += 4
                elif char == "x":
                    char = chr(int(self.text[self.pos:self.pos + 2], 16))
                    self.pos += 2
                else:
                    char = {"n": "\n", "r": "\r", "t": "\t"}.get(char, char)
            out.append(char)
        raise ValueError("Unterminated source literal")

    def expression(self):
        start, depth = self.pos, 0
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char in "'\"`":
                self.string()
                continue
            if char in "([{":
                depth += 1
            elif char in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif char == "," and depth == 0:
                break
            self.pos += 1
        return {"expression": self.text[start:self.pos].strip()}

    def value(self):
        self.whitespace()
        char = self.text[self.pos]
        if char in "'\"`":
            return self.string()
        if char in "{[":
            closing = "}" if char == "{" else "]"
            result = {} if char == "{" else []
            self.pos += 1
            while True:
                self.whitespace()
                if self.text[self.pos] == closing:
                    self.pos += 1
                    return result
                if char == "{":
                    if self.text[self.pos] in "'\"`":
                        key = self.string()
                    else:
                        match = re.match(r"[\w$-]+", self.text[self.pos:])
                        if not match:
                            raise ValueError("Unsupported source key at " + self.text[self.pos:self.pos + 40])
                        key = match[0]
                        self.pos += len(key)
                    self.whitespace()
                    if self.text[self.pos] != ":":
                        raise ValueError("Unsupported shorthand source property: " + key)
                    self.pos += 1
                    result[key] = self.value()
                else:
                    result.append(self.value())
                self.whitespace()
                if self.text[self.pos] == ",":
                    self.pos += 1
                elif self.text[self.pos] != closing:
                    raise ValueError("Unsupported source syntax at " + self.text[self.pos:self.pos + 40])
        for word, val in [("true", True), ("false", False), ("null", None), ("!0", True), ("!1", False)]:
            if self.text.startswith(word, self.pos) and self.text[self.pos + len(word):self.pos + len(word) + 1] in ",}] \n\r\t":
                self.pos += len(word)
                return val
        match = re.match(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?=\s*[,}\]])", self.text[self.pos:])
        if match:
            self.pos += len(match[0])
            return float(match[0])
        return self.expression()


def csv_rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def plain(value):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", value or ""))).strip()


def source_url(value):
    if not isinstance(value, str):
        return None
    found = re.search(r"https?://[^\s<>\"']+", value)
    return found[0] if found else None


def weights(value):
    value = (value or "").lower()
    if "open weight" in value:
        return "open"
    if "closed weight" in value or "api access" in value:
        return "proprietary"
    return "unknown"


class Islands(HTMLParser):
    def __init__(self):
        super().__init__()
        self.components = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "astro-island" and "component-url" in attrs:
            self.components.append(attrs["component-url"])


def load_catalog(fetch):
    page = fetch(BASE + "/benchmarks/search").decode()
    islands = Islands()
    islands.feed(page)
    search_path = next(path for path in islands.components if "/BenchmarkSearch." in path)
    search_source = fetch(urljoin(BASE, search_path)).decode()
    imports = re.findall(r'from["\'](\./benchmarks\.[^"\']+\.js)["\']', search_source)
    if not imports:
        raise ValueError("Epoch benchmark catalog import not found")
    wrapper_url = urljoin(urljoin(BASE, search_path), imports[0])
    wrapper = fetch(wrapper_url).decode()
    if wrapper.startswith("var "):
        literal, catalog_url = wrapper, wrapper_url
    else:
        imported = re.findall(r'from["\'](\./benchmarks\.[^"\']+\.js)["\']', wrapper)
        if not imported:
            raise ValueError("Epoch benchmark definitions import not found")
        catalog_url = urljoin(wrapper_url, imported[0])
        literal = fetch(catalog_url).decode()
    start = re.search(r"(?:var|const|let)\s+\w+\s*=\s*\{", literal)
    if not start:
        raise ValueError("Epoch benchmark definitions not a data literal")
    catalog = LiteralReader(literal, start.end() - 1).value()
    return catalog, catalog_url


def native_category(meta):
    domains = meta.get("domains") or []
    mapping = {"Software engineering": "Coding", "Mathematics": "Math", "Science": "Science",
               "Multimodal": "Multimodal", "World knowledge": "General", "Language understanding": "General",
               "Agent": "Knowledge work", "Computer use": "Knowledge work", "Conceptual reasoning": "General"}
    for domain in domains:
        if domain in mapping:
            return mapping[domain]
    return "Other"


def transform_scale(metric):
    """Recognize the explicit affine unit conversion used by Epoch's config."""
    transform = metric.get("transform")
    if not transform:
        return 1.0
    if not isinstance(transform, dict):
        raise ValueError("Unexpected Epoch numeric transform")
    expression = transform.get("expression", "")
    compact = re.sub(r"\s+", "", expression)
    if re.fullmatch(r"\(?(\w+)\)?=>parseFloat\(\1\)", compact):
        return 1.0
    divided = re.fullmatch(r"\(?(\w+)\)?=>parseFloat\(\1\)/(\d+(?:\.\d+)?)", compact)
    if divided:
        return 1 / float(divided[2])
    raise ValueError("Unrecognized Epoch numeric transform: " + expression)


def metric_definition(key, config, meta):
    options = dict(config.get("metrics", {}).get("options", {}))
    default = config.get("accuracy", {})
    if default.get("column") and not any(v.get("column") == default["column"] for v in options.values()):
        options = {default["column"]: default, **options}
    output = []
    for label, metric in options.items():
        if not metric.get("column"):
            continue
        scale = transform_scale(metric)
        percent = metric.get("displayAsAccuracy", not meta.get("non_percentage_score", False))
        unit, multiplier = ("%", scale * 100) if percent else ("score", scale)
        unit_hint = meta.get("score_unit", "")
        if not percent and ("cost" in label.lower() or unit_hint in ("USD", "dollars", "usd")):
            unit = "USD"
        elif not percent and (key == "metr_time_horizons" or unit_hint == "minutes"):
            unit, multiplier = "seconds", scale * 60
        elif not percent and ("seconds" in label.lower() or unit_hint == "seconds"):
            unit = "seconds"
        elif not percent and key == "webdev_arena":
            unit = "Elo"
        elif not percent and key == "vending_bench_2":
            unit = "USD"
        lower = bool(meta.get("lower_is_better", False))
        if any(term in label.lower() for term in ("cost", "distance", "refusal")) or "lower is better" in str(metric.get("label", "")).lower():
            lower = True
        output.append((label, metric, unit, multiplier, lower))
    return output


def model_fields(row, model_meta=None):
    meta = model_meta or {}
    result = {"lab": row.get("Organization") or meta.get("organization") or "Unknown",
              "release_date": row.get("Version release date") or row.get("Release date") or meta.get("date") or None,
              "weights": weights(row.get("Model accessibility") or meta.get("accessibility"))}
    for target, column in [("country", "Country (of organization)"), ("training_compute_flop", "Training compute (FLOP)"),
                           ("parameters", "Parameters")]:
        value = row.get(column) or (row.get("Country") if target == "country" else None) or meta.get(target)
        if target != "country":
            value = number(value)
        if value is not None:
            result[target] = value
    return result


def collect(fetch):
    retrieved_at = datetime.now(timezone.utc).isoformat()
    archive = zipfile.ZipFile(io.BytesIO(fetch(DATA)))
    tables = {name: csv_rows(archive.read(name)) for name in archive.namelist() if name.endswith(".csv")}
    catalog, catalog_url = load_catalog(fetch)
    catalog_by_id = {item["id"]: item for item in catalog.values() if isinstance(item, dict) and "id" in item}
    config_text = fetch(CONFIG).decode()
    marker = re.search(r"var externalBenchmarkConfigs\s*=\s*\{", config_text)
    if not marker:
        raise ValueError("Epoch external config missing")
    configs = LiteralReader(config_text, marker.end() - 1).value()
    models = {r["model_version"]: r for r in tables["model_metadata.csv"] if r["model_version"]}
    internal = csv_rows(fetch(INTERNAL))
    benchmark_metadata = {row["benchmark"]: row for row in tables["benchmark_metadata.csv"]}
    observations, benchmarks, inventory = [], [], []
    sources = [{"id": "epoch", "name": "Epoch AI", "url": PAGE, "data_url": DATA,
                "methodology_url": BASE + "/benchmarks/about", "status": "ok", "license": "CC BY 4.0; external data retains original licenses",
                "notes": "Official downloadable benchmark archive, enriched by official run CSV and website data definitions. Internal evaluations and external aggregations are explicitly separated; external raw origin links are preserved."}]

    def add_benchmark(identifier, title, meta, url, dataset, **extra):
        benchmark = {"id": identifier, "name": title, "provider": "epoch", "category": native_category(meta),
                     "unit": "%", "higher_is_better": True, "min": 0, "max": 100, "version": None,
                     "source_url": url, "dataset_url": dataset, "description": plain(meta.get("short_description", "")),
                     "private": True if "Private" in meta.get("id", "") else None, "kind": "benchmark",
                     "native_category": meta.get("domains", []) or [meta.get("category", "Uncategorized")],
                     "evaluator": meta.get("evaluator"), "creator": meta.get("creator"), **extra}
        benchmarks.append(benchmark)
        return benchmark

    # Primary internal runs use exact model/harness/task-version labels and means.
    internal_ids = {}
    for row in internal:
        if row.get("Status") != "Success":
            continue
        value = number(row.get("mean_score"))
        if value is None:
            continue
        task = row["task"]
        version = row.get("task version") or None
        key = (task, version)
        if key not in internal_ids:
            meta = catalog_by_id.get(task, {})
            identifier = "epoch-" + slug(task) + ("-" + slug(version) if version else "")
            internal_ids[key] = identifier
            url = BASE + "/benchmarks/" + meta.get("slug", slug(task))
            title = meta.get("title", task) + (" · " + version if version else "")
            add_benchmark(identifier, title, meta, url, INTERNAL, evaluator="Epoch AI", version=version,
                          private=True if "Private" in task else False if "Public" in task else None)
        identifier = internal_ids[key]
        model = row.get("Unique display name") or row.get("Display name") or row["model"]
        obs = {"benchmark_id": identifier, "model": model, "source_model_id": row["model"], "score": value * 100,
               "source_url": source_url(row.get("log viewer")) or next(b["source_url"] for b in benchmarks if b["id"] == identifier),
               "data_url": INTERNAL, "source_record_id": row.get("id_runs"), "evaluator": "Epoch AI", "provenance": "internal",
               "date": row.get("started_at") or None, "harness": "Epoch AI / Inspect", "raw_score": value, "raw_unit": "fraction",
               **model_fields(row, models.get(row["model"]))}
        effort = re.search(r"(?:_|\()(max|xhigh|high|medium|low|minimal|\d+K)(?:\)|$)", row["model"], re.I)
        if effort:
            obs["effort"] = effort[1]
        stderr = number(row.get("stderr"))
        if stderr is not None:
            obs.update({"stderr": stderr * 100, "ci_low": (value - stderr) * 100, "ci_high": (value + stderr) * 100,
                        "ci_kind": "±1 standard error", "ci_level": None})
        if row.get("comments"):
            obs["notes"] = row["comments"]
        observations.append(obs)

    # Each externally collected metric remains attributed to its original source.
    for filename, rows in tables.items():
        if not filename.endswith("_external.csv"):
            continue
        key = filename.removesuffix("_external.csv")
        config = configs.get(key)
        meta = catalog_by_id.get(key) or catalog.get(key) or catalog.get(key.replace("_", "-")) or {}
        if not config:
            raise ValueError("No explicit score mapping for Epoch external table " + filename)
        dataset = BASE + "/data/external_benchmarks/" + key + ".csv"
        title = meta.get("title") or config.get("name") or key
        page_url = BASE + "/benchmarks/" + meta.get("slug", key.replace("_", "-"))
        upstream_url = source_url(config.get("sourceLink")) or source_url(meta.get("homepage_link")) or source_url(meta.get("paper_link"))
        definitions = metric_definition(key, config, meta)
        primary_column = config.get("accuracy", {}).get("column")
        for label, metric, unit, multiplier, lower in definitions:
            column = metric["column"]
            identifier = "epoch-" + slug(key)
            if column != primary_column:
                identifier += "-" + slug(column)
            name = title if column == primary_column else title + " · " + str(metric.get("label", label))
            add_benchmark(identifier, name, meta, page_url, dataset, unit=unit, min=0 if unit == "%" else None,
                          max=100 if unit == "%" else None, higher_is_better=not lower, upstream_url=upstream_url,
                          source_column=column, source_multiplier=multiplier, kind="benchmark",
                          parent_benchmark="epoch-" + slug(key) if column != primary_column else None,
                          description=plain(config.get("description")) or plain(meta.get("short_description")))
            for row in rows:
                value = number(row.get(column))
                if value is None:
                    continue
                source = next((source_url(row.get(field)) for field in ["Source link", "Source Link", "Source link (site from table)", "Source"] if source_url(row.get(field))), None) or upstream_url or page_url
                model_version = row.get("Model version", "")
                mm = models.get(model_version, {})
                model = mm.get("display_name") or model_version
                if not model:
                    continue
                obs = {"benchmark_id": identifier, "model": model, "score": value * multiplier, "source_model_id": model_version,
                       "source_url": source, "data_url": dataset, "aggregator_url": page_url,
                       "extraction_url": DATA, "archive_member": filename,
                       "evaluator": row.get("Source") or config.get("source") or meta.get("evaluator") or "External; unspecified",
                       "provenance": "external-via-epoch", "source_record_id": row.get("id") or row.get("UUID"),
                       "date": next((row[x] for x in ["Date of evaluation", "Evaluation date", "Run date", "Graded at", "Last updated"] if row.get(x)), None),
                       "raw_score": value, "raw_column": column, "raw_multiplier": multiplier,
                       **model_fields(row, mm)}
                for field, columns in {"harness": ["Agent", "Harness", "Scaffold"], "effort": ["Reasoning effort", "Reasoning level", "Reasoning"]}.items():
                    val = next((row[c] for c in columns if row.get(c)), None)
                    if val:
                        obs[field] = val
                if row.get("Harness version"):
                    obs["harness"] = (obs.get("harness", "") + " " + row["Harness version"]).strip()
                if row.get("LiveBench Version"):
                    obs["benchmark_version"] = row["LiveBench Version"]
                if not obs.get("effort"):
                    effort = re.search(r"(?:_|\()(max|xhigh|high|medium|low|minimal|\d+K)(?:\)|$)", model_version, re.I)
                    if effort:
                        obs["effort"] = effort[1]
                notes = []
                if row.get("Notes") or row.get("Notes (details)"):
                    notes.append(row.get("Notes") or row["Notes (details)"])
                if not upstream_url and source == page_url:
                    notes.append("Upstream result link not supplied in Epoch export; attributed as secondary aggregation.")
                # Costs preserve their published basis; no inferred task-cost conversion.
                costs = {c: number(row[c]) for c in row if any(t in c.lower() for t in ["cost", "spend"]) and number(row[c]) is not None}
                if costs:
                    obs["published_costs"] = costs
                    task_cost = next((costs[c] for c in ["Cost per task", "Average cost (USD)", "Cost per test (USD)", "Mean cost (USD)", "Average costs"] if c in costs), None)
                    if task_cost is not None:
                        obs["cost_usd"] = task_cost
                        obs["cost_basis"] = "Per task/test as published; varies by benchmark"
                for col, factor in [("Latency (seconds)", 1), ("Time per case (seconds)", 1), ("Average duration (hours)", 3600)]:
                    time = number(row.get(col))
                    if time is not None:
                        obs["latency_seconds"] = time * factor
                        obs["latency_basis"] = col
                        break
                errors = metric.get("errorBars", config.get("errorBars"))
                if isinstance(errors, dict):
                    lo_col, hi_col = errors.get("lowColumn"), errors.get("highColumn")
                    lo, hi = number(row.get(lo_col)), number(row.get(hi_col))
                    if lo is not None and hi is not None:
                        if lo_col == hi_col:
                            obs.update(stderr=lo * multiplier, ci_low=(value - lo) * multiplier, ci_high=(value + hi) * multiplier,
                                       ci_kind="±1 standard error", ci_level=None)
                        else:
                            obs.update(ci_low=lo * multiplier, ci_high=hi * multiplier,
                                       ci_kind="Published interval", ci_level=0.95 if "95" in lo_col or key == "metr_time_horizons" else None)
                if "ci_low" not in obs:
                    ci_columns = {
                        ("weirdml_v3", "Score"): ("Score 95% CI low", "Score 95% CI high", 0.95),
                        ("webdev_arena", "Arena Score"): ("95% CI Low", "95% CI High", 0.95),
                        ("forecastbench", "Overall score"): ("Overall 95% CI low", "Overall 95% CI high", 0.95),
                        ("forecastbench", "Dataset score"): ("Dataset 95% CI low", "Dataset 95% CI high", 0.95),
                        ("forecastbench", "Market score"): ("Market 95% CI low", "Market 95% CI high", 0.95),
                        ("btf3", "Pooled score"): ("Pooled 95% CI low", "Pooled 95% CI high", 0.95),
                        ("enigma_eval", "Accuracy"): ("CI Lower Bound", "CI Upper Bound", None),
                    }
                    interval = ci_columns.get((key, column))
                    if interval:
                        lo, hi = number(row.get(interval[0])), number(row.get(interval[1]))
                        if lo is not None and hi is not None:
                            obs.update(ci_low=lo * multiplier, ci_high=hi * multiplier, ci_level=interval[2], ci_kind="Published interval")
                if "ci_low" not in obs:
                    error_columns = {
                        ("proofbench", "Accuracy"): ("Accuracy Standard Error", None),
                        ("hle", "Accuracy"): ("Accuracy Standard Error", None),
                        ("apex_agents", "Pass@1 score"): ("Pass@1 Standard Error", None),
                        ("terminalbench", "Accuracy mean"): ("Accuracy SE", None),
                        ("weirdml", "Accuracy"): ("Accuracy SE", None),
                        ("deepswe", "Pass@1"): ("95% CI half-width", 0.95),
                        ("lmca", "Score"): ("Score 95% CI (±)", 0.95),
                    }
                    error = error_columns.get((key, column))
                    half = number(row.get(error[0])) if error else None
                    if half is not None:
                        obs.update(ci_low=(value - half) * multiplier, ci_high=(value + half) * multiplier,
                                   ci_level=error[1], ci_kind="Published 95% interval" if error[1] else "±1 standard error")
                        if error[1] is None:
                            obs["stderr"] = half * multiplier
                # Keep all published numeric source columns, including sub-scores not exposed in a metric selector.
                obs["source_metrics"] = {c: number(v) for c, v in row.items() if c not in ["Training compute (FLOP)", "Parameters"] and number(v) is not None}
                if notes:
                    obs["notes"] = " ".join(notes)
                observations.append(obs)

    # ECI is an unbounded statistical composite, not an average percentage.
    for identifier, title, url, raw in [("epoch-eci", "Epoch Capabilities Index", BASE + "/data/eci_scores.csv", archive.read("epoch_capabilities_index/eci_scores.csv")),
                                        ("epoch-cyber-eci", "Cyber ECI", BASE + "/data/cyber/eci_scores.csv", fetch(BASE + "/data/cyber/eci_scores.csv"))]:
        add_benchmark(identifier, title, {}, ECI, url, category="Coding" if "cyber" in identifier else "General",
                      unit="score", min=None, max=None, kind="composite", evaluator="Epoch AI", private=None,
                      description="Statistically fitted capability index. No maximum. General ECI combines internal evaluations, independent benchmark results, and developer-reported results; it is refitted when data changes.")
        for row in csv_rows(raw):
            score = number(row.get("eci"))
            if score is None:
                continue
            observations.append({"benchmark_id": identifier, "model": row.get("Display name") or row["Model"], "score": score,
                                 "lab": row.get("Organization", "Unknown"), "source_url": ECI, "data_url": url,
                                 "extraction_url": DATA if identifier == "epoch-eci" else url,
                                 "release_date": row.get("date") or None, "date": None,
                                 "ci_low": number(row.get("eci_ci_low")), "ci_high": number(row.get("eci_ci_high")), "ci_level": 0.9,
                                 "ci_kind": "90% bootstrap interval", "evaluator": "Epoch AI", "provenance": "composite",
                                 "weights": weights(row.get("Accessibility group") or row.get("Model accessibility")),
                                 "country": row.get("Country (of organization)"), "source_model_id": row["Model"],
                                 "notes": "Current ECI fit plotted at model release date; this is not a historical record of past ECI rankings."})

    # Published fit parameters are retained for the interpretation view, without recomputing a fit.
    fits = []
    for row in tables["epoch_capabilities_index/edi_scores.csv"]:
        bm_meta = benchmark_metadata.get(row["benchmark_name"], {})
        fits.append({"benchmark": row["benchmark_name"], "difficulty": number(row["edi"]),
                     "slope": number(row["estimated_slope_scaled"]), "release_date": row["benchmark_release_date"] or None,
                     "random_baseline": number(bm_meta.get("random_baseline")), "score_ceiling": number(bm_meta.get("score_ceiling")),
                     "source_url": BASE + "/data/edi_scores.csv"})
    processed = tables["epoch_capabilities_index/processed_data_for_eci.csv"]
    # These are baseline/ceiling-adjusted model inputs, deliberately kept outside raw observations.
    eci_inputs = [{"model": r["model"], "model_version": r["model_version"], "benchmark": r["benchmark"],
                   "performance": number(r["performance"]), "source": r["source"], "release_date": r["date"] or None} for r in processed]
    for name, view, notes in [
        ("ECI leaderboard and confidence intervals", "ranking", "General and cyber published ECI estimates; 90% bootstrap intervals."),
        ("Score versus model release date / frontier trend", "timeline", "Actual release dates retained. Current results at release date do not represent historical ranking snapshots."),
        ("Score versus training compute", "scatter", "Published training-compute estimates retained where available; missing estimates stay missing."),
        ("Per-benchmark leaderboards and forest plots", "ranking", "Internal means with one-standard-error intervals; external metrics retain original scoring and interval labels."),
        ("Score versus general ECI", "scatter", "Link exact source model identities; differing run settings remain separate."),
        ("Domain versus general ECI", "scatter", "Cyber ECI published; arbitrary custom-domain ECI refits are not recreated by an arithmetic average."),
        ("ECI benchmark interpretation curves", "difficulty", "Published difficulty and slope parameters plus adjusted ECI inputs retained; fitted expectation is not a raw result."),
        ("Per-benchmark metric selector and task categories", "benchmark", "All metrics exposed in the source configuration are imported separately; other numeric source columns retained per observation."),
        ("Cost versus score and runtime metadata", "scatter", "Only explicitly published per-task costs map to cost_usd. Whole-run costs remain in published_costs with their basis."),
        ("Country, organization, accessibility", "filters", "Original country, lab, release dates and access labels; missing metadata remains unknown."),
        ("Evaluator / source / domain / saturation selection", "filters", "Preserves creator and evaluator distinction, native domains, internal vs externally aggregated provenance."),
    ]:
        inventory.append({"name": name, "url": ECI if "ECI" in name else PAGE, "type": "visualization" if view != "filters" else "category",
                          "supported_view": view, "status": "data-only", "notes": notes})
    inventory.extend([
        {"name": "Custom math and software-engineering ECI refits", "url": ECI, "type": "visualization", "supported_view": "custom-composite",
         "status": "unavailable", "notes": "Epoch's fitted IRT-style custom estimates and bootstrap refits are distinct from user-selected weighted averages. Published general/cyber ECI only; no fabricated domain refits."},
        {"name": "External original-source coverage", "url": BASE + "/benchmarks/use-this-data", "type": "dataset", "supported_view": "sources", "status": "data-only",
         "notes": "External rows in this pack are obtained from Epoch's official aggregation, not independently re-evaluated. The original cited source is linked on each row; original evaluator adapters are separate."},
        {"name": "Benchmark catalog including review-only entries", "url": BASE + "/benchmarks/search", "type": "category", "supported_view": "sources", "status": "data-only",
         "notes": "Complete public catalog metadata retained; entries with no downloadable numeric results do not receive invented observations."},
    ])
    return {"schema_version": 1, "provider": "epoch", "retrieved_at": retrieved_at, "sources": sources,
            "benchmarks": benchmarks, "observations": observations, "inventory": inventory, "eci_fits": fits,
            "eci_inputs": eci_inputs, "native_catalog": [{"id": m.get("id"), "name": m.get("title"), "slug": m.get("slug"),
                    "domains": m.get("domains", []), "category": m.get("category"), "evaluator": m.get("evaluator"),
                    "creator": m.get("creator"), "review_only": m.get("review_only", False), "hidden": m.get("hidden", False),
                    "source_url": catalog_url, "official_url": m.get("homepage_link") or m.get("paper_link")} for m in catalog.values() if isinstance(m, dict)],
            "visualization_data": [
                {"id": "epoch-edi-fit-parameters", "name": "ECI interpretation fit parameters", "component": "difficulty-curves", "type": "logistic-fit",
                 "source_url": BASE + "/data/edi_scores.csv", "data": fits,
                 "notes": "Published fitted difficulty and slope; random baselines and score ceilings come from benchmark_metadata.csv. Predicted values are model fits, not observed results."},
                {"id": "epoch-eci-adjusted-inputs", "name": "ECI adjusted benchmark inputs", "component": "eci-inputs", "type": "scatter",
                 "source_url": BASE + "/data/eci_benchmarks.csv", "data": eci_inputs,
                 "notes": "Published preprocessed ECI inputs after source normalization/adjustment. Kept separate from raw benchmark observations and excluded from custom raw-score weighting."},
            ],
            "extraction": {"method": "Official ZIP/CSV plus inert public metadata/configuration literals", "catalog_url": catalog_url,
                           "config_url": CONFIG, "score_policy": "Raw published metric converted to display unit by explicit source transform; ECI adjusted inputs kept separate."}}
