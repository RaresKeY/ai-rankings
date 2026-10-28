"""First-party Vals public benchmark data, decoded without executing their JavaScript.

Astro supplies the same JSON and serialized props consumed by the public site. The
adapter follows benchmark/version links, preserving task slices, effort studies,
and evaluator parameters. It never treats standard errors as confidence bounds.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import hashlib
import math
import re
from urllib.parse import urljoin, urlsplit

BASE = "https://www.vals.ai"
CATALOG = BASE + "/benchmarks"
COMPARISON = BASE + "/comparison"


class LiteralReader:
    """Read the JSON-like data subset emitted by Vite; never evaluate JS code."""

    def __init__(self, text, position=0):
        self.text, self.position = text, position

    def skip(self):
        while self.position < len(self.text) and self.text[self.position].isspace():
            self.position += 1

    def value(self):
        self.skip()
        c = self.text[self.position:self.position + 1]
        if c == '"':
            value, end = json.JSONDecoder().raw_decode(self.text, self.position)
            self.position = end
            return value
        if c in ("{", "["):
            self.position += 1
            result = {} if c == "{" else []
            close = "}" if c == "{" else "]"
            self.skip()
            while self.text[self.position] != close:
                if c == "{":
                    self.skip()
                    if self.text[self.position] == '"':
                        key = self.value()
                    else:
                        match = re.match(r"[\w$]+", self.text[self.position:])
                        if not match:
                            raise ValueError("Non-data property in Vals asset")
                        key = match.group()
                        self.position += len(key)
                    self.skip()
                    if self.text[self.position] != ":":
                        raise ValueError("Expected data property separator")
                    self.position += 1
                    result[key] = self.value()
                else:
                    result.append(self.value())
                self.skip()
                if self.text[self.position] == close:
                    break
                if self.text[self.position] != ",":
                    raise ValueError("Non-data expression in Vals asset")
                self.position += 1
                self.skip()
            self.position += 1
            return result
        for token, value in (("!0", True), ("!1", False), ("true", True),
                             ("false", False), ("null", None)):
            if self.text.startswith(token, self.position):
                self.position += len(token)
                return value
        match = re.match(r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", self.text[self.position:])
        if match:
            self.position += len(match.group())
            value = float(match.group())
            if not math.isfinite(value):
                raise ValueError("Non-finite source number")
            return int(value) if value.is_integer() else value
        raise ValueError("Unsupported executable expression in Vals data asset")


def _unpack(value):
    """Decode Astro's tagged JSON values, including explicit undefined/null."""
    if not isinstance(value, list):
        return value
    if len(value) == 1:
        return None
    kind, body = value
    if kind == 0:
        return {key: _unpack(item) for key, item in body.items()} if isinstance(body, dict) else body
    if kind in (1, 6):
        return [_unpack(item) for item in body]
    if kind in (3, 4):  # Date and BigInt are retained as literal source strings.
        return body
    raise ValueError(f"Unsupported Astro value tag: {kind}")


class Page(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.islands, self.links, self.headings = [], [], []
        self.raw = raw.decode("utf-8")
        updated = re.search(r"Updated\s+(\d{1,2})/(\d{1,2})/(\d{4})", re.sub(r"<[^>]+>", " ", self.raw))
        self.updated = f"{updated[3]}-{int(updated[1]):02}-{int(updated[2]):02}" if updated else None
        self._heading = None
        self.feed(raw.decode("utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "astro-island":
            props = {key: _unpack(value) for key, value in json.loads(attrs.get("props", "{}")).items()}
            self.islands.append((attrs.get("component-url", ""), props))
        if tag in ("h1", "h2", "h3"):
            self._heading = []

    def handle_data(self, value):
        if self._heading is not None:
            self._heading.append(value)

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3") and self._heading is not None:
            self.headings.append(" ".join("".join(self._heading).split()))
            self._heading = None


def _url(value, parent=BASE):
    url = urljoin(parent, value)
    if urlsplit(url).hostname != "www.vals.ai":
        raise ValueError("Vals adapter refused non-Vals fetch URL")
    return url


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _category(metadata):
    industry = metadata.get("industry", "")
    return {"index": "General", "coding": "Coding", "finance": "Knowledge work",
            "legal": "Knowledge work", "healthcare": "Knowledge work", "math": "Math",
            "science": "Science", "academic": "General", "education": "Knowledge work",
            "voice": "Multimodal", "social mobility": "Knowledge work", "cyber": "Coding",
            "mental-health": "Knowledge work"}.get(industry, "Other")


def _model_catalog(fetch, comparison):
    component = next(component for component, _ in comparison.islands if "/ModelComparison." in component)
    component_url = _url(component)
    component_text = fetch(component_url).decode()
    match = re.search(r'["\'](\./constants\.[\w-]+\.js)["\']', component_text)
    if not match:
        raise ValueError("Vals model metadata module was not discoverable")
    data_url = _url(match.group(1), component_url)
    text = fetch(data_url).decode()
    match = re.search(r"\bconst\s+\w+=", text)
    if not match:
        raise ValueError("Vals model metadata assignment was not found")
    reader = LiteralReader(text, match.end())
    catalog = reader.value()
    # The following literal dictionaries contain detector and router product metadata.
    for _ in range(2):
        match = re.match(r",\w+=", text[reader.position:])
        if not match:
            break
        reader.position += match.end()
        extra = reader.value()
        if isinstance(extra, dict):
            catalog.update(extra)
    aliases = {}
    for key, model in catalog.items():
        for alternative in model.get("alternative_keys") or []:
            for alias in ([alternative] if isinstance(alternative, str) else alternative):
                aliases.setdefault(alias, key)
    return catalog, aliases, data_url


def _benchmark(metadata, task, url, data_url):
    parent = "vals-" + _slug(url.rsplit("/", 1)[-1])
    name = metadata["benchmark"]
    task_name = metadata.get("tasks", {}).get(task, task)
    if task != "overall":
        name += " · " + task_name
    is_rating = metadata.get("accuracy_label") == "TrueSkill Rating"
    is_rsi = metadata.get("family") == "rsi_index"
    result = {
        "id": parent if task == "overall" else parent + "--" + _slug(task),
        "name": name, "provider": "vals", "category": _category(metadata),
        "unit": "score" if is_rating or is_rsi else "%", "higher_is_better": True,
        "min": None if is_rating else 0, "max": None if is_rating else 1 if is_rsi else 100,
        "version": str(metadata.get("version", "")), "source_url": url,
        "dataset_url": data_url, "description": metadata.get("description", ""),
        "private": {"private": True, "public": False}.get(metadata.get("dataset_type")),
        "kind": "composite" if metadata.get("industry") == "index" else "benchmark",
        "native_category": metadata.get("industry"), "task": task, "task_name": task_name,
        "archived": bool(metadata.get("archived")), "family": metadata.get("family"),
        "mode": metadata.get("mode"), "updated": metadata.get("updated"),
        "score_label": "Reference-anchored index" if is_rsi else metadata.get("accuracy_label", "Accuracy"),
        "cost_label": metadata.get("cost_label", "Cost / Test"),
        "latency_label": metadata.get("latency_label", "Duration / Test"),
    }
    if task != "overall":
        result["parent_benchmark_id"] = parent
    else:
        result["source_metadata"] = {key: value for key, value in metadata.items() if key != "models"}
    return result


def _observation(benchmark, model_key, row, models, aliases, data_url):
    model = models.get(model_key, models.get(aliases.get(model_key), {}))
    prices = model.get("costs_per_million_token") or {}
    props = model.get("properties") or {}
    result = {
        "benchmark_id": benchmark["id"], "model": model.get("label", model_key),
        "lab": model.get("company"), "score": row["accuracy"],
        "source_url": benchmark["source_url"], "data_url": data_url,
        "source_model_id": model_key, "date": benchmark.get("updated"),
        "effort": row.get("reasoning_effort") or row.get("compute_effort"),
        "harness": row.get("harness") or benchmark.get("source_metadata", {}).get("harness"),
        "inference_provider": row.get("provider"), "stderr": row.get("stderr"),
        "uncertainty_type": "standard error", "cost_usd": row.get("cost_per_test") if row.get("cost_per_test", 0) and row["cost_per_test"] > 0 else None,
        "cost_label": benchmark["cost_label"], "latency_seconds": row.get("latency") if row.get("latency", 0) and row["latency"] > 0 else None,
        "input_price": prices.get("input"), "output_price": prices.get("output"),
        "weights": {True: "open", False: "proprietary"}.get(model.get("open_source"), "unknown"),
        "context_tokens": props.get("context_window"), "release_date": model.get("release_date"),
        "country": model.get("country"), "entity_type": model.get("type"),
    }
    result["evaluation_parameters"] = {key: row[key] for key in
        ("temperature", "top_p", "max_output_tokens", "reasoning", "reasoning_effort",
         "compute_effort", "verbosity", "harness_config") if row.get(key) is not None}
    result["tokens"] = {key: value for key, value in row.items()
                       if key.startswith("avg_") or key in ("token_totals", "token_tasks_measured")}
    # Preserve specialized source statistics without turning them into ranked accuracy.
    handled = {"accuracy", "latency", "stderr", "cost_per_test", "temperature", "top_p", "max_output_tokens", "reasoning", "reasoning_effort", "compute_effort", "verbosity", "harness", "harness_config", "provider", "task_results", "token_totals", "token_tasks_measured"}
    extra = {key: value for key, value in row.items() if key not in handled and not key.startswith("avg_")}
    if row.get("latency") == 0:
        extra["unreported_latency_zero"] = 0
    if row.get("cost_per_test") == 0:
        extra["unreported_cost_zero"] = 0
    if benchmark.get("family") == "rsi_index":
        result["score"] /= 100
        extra["accuracy_scaled_100"] = row["accuracy"]
        result["notes"] = "Source JSON stores 100 times the native reference-anchored index; divided by 100 to match the published 0–1 scale."
    gateway = row.get("gateway_metrics", {})
    median_tps = gateway.get("approximate_tps", {}).get("p50")
    if _number(median_tps):
        result["speed_tps"] = median_tps
        result["speed_statistic"] = "median request output-plus-reasoning tokens per second"
    if extra:
        result["source_metrics"] = extra
    if row.get("task_results"):
        result["task_results"] = row["task_results"]
    if model.get("supports"):
        result["modalities"] = [key for key in ("images", "audio", "videos", "files", "transcription") if model["supports"].get(key)]
    if row.get("cost_note"):
        result["notes"] = row["cost_note"]
    return {key: value for key, value in result.items() if value is not None and value != {} and value != []}


CHARTS = {
    "ValsIndexSection": ("Rankings and industry contributions", "bars / stacked contributions"),
    "ScatterGraph": ("Accuracy, cost and latency frontier", "scatter"),
    "BenchmarkViewLoader": ("Leaderboard, accuracy, latency, cost and task selection", "table / bars"),
    "ReasoningEffortChart": ("Reasoning effort and cost", "effort curves"),
    "OverTimeChart": ("Performance by model release date", "timeline"),
    "ValsIndexHeatmap": ("Accuracy by benchmark and sector", "heatmap"),
    "ModelComparison": ("Cross-model benchmark, industry, cost and metadata comparison", "compare / heatmap"),
    "AccuracyHistogram": ("Task accuracy distribution", "histogram"),
    "AnalysisEdgarSpider": ("Task-dimension performance", "radar"),
    "TrajectoryTimeline": ("Agent trajectory progress", "trajectory timeline"),
    "ProviderOverview": ("Inference provider overview", "provider comparison"),
    "InferenceProviderIndex": ("Inference provider performance", "provider comparison"),
    "RsiBenchmarkView": ("Recursive self-improvement index", "RSI comparisons"),
    "MentalHealthResults": ("Mental health benchmark results", "mental health comparisons"),
    "MentalHealthFindings": ("Mental health intervention findings", "study charts"),
    "MentalHealthExplorer": ("Mental health scenario explorer", "scenario explorer"),
    "ProgressChart": ("Cyber offense progress", "progress timeline"),
    "FooterTrendLine": ("Lab frontiers and projections", "timeline"),
}


def _leading_literals(text):
    """Extract a leading literal declaration block; never execute source code."""
    result = {}
    matches = list(re.finditer(r"\bconst\s+([\w$]+)=", text))
    for match in matches:
        if match.group(1).startswith("__vite"):
            continue
        reader, key = LiteralReader(text, match.end()), match.group(1)
        for _ in range(100):
            try:
                value = reader.value()
                reader.skip()
                if text[reader.position:reader.position + 1] not in (",", ";"):
                    break
            except (ValueError, IndexError, json.JSONDecodeError):
                break
            result[key] = value
            match = re.match(r",([\w$]+)=", text[reader.position:])
            if not match:
                break
            key = match.group(1)
            reader.position += match.end()
        if result:
            break
    return result


def _special_asset_data(fetch, component_url):
    """Recover public data literals used by chart components with empty props."""
    text = fetch(component_url).decode()
    assets = []
    literals = _leading_literals(text)
    if literals:
        assets.append({"url": component_url, "literals": literals})
    pattern = r'["\'](\./(?:benchmark_view_rsi_index|shared|routerStudy|routerCoding|jevStudy|metrics|timeHorizon|series)\.[\w-]+\.js)["\']'
    for relative in sorted(set(re.findall(pattern, text))):
        url = _url(relative, component_url)
        values = _leading_literals(fetch(url).decode())
        if values:
            assets.append({"url": url, "literals": values})
    for relative in sorted(set(re.findall(r'["\'](/_astro/[^"\']+\.json)["\']', text))):
        url = _url(relative)
        assets.append({"url": url, "json": json.loads(fetch(url))})
    return {"assets": assets} if assets else {}


EXAMPLE_COMPONENTS = {"GlobalToaster", "BenchmarkSelector", "BenchmarkVersionSelector",
    "QandA", "QandALean", "QandAModelSelector", "LegalModelOutputExamples", "ModelOutputExamples",
    "ChatTranscript", "SnapSampleTranscript", "VoiceCodeBenchExample", "GifSelector", "PatchExamples", "PersonaGrid"}
SPECIAL_COMPONENTS = {"RsiBenchmarkView", "MentalHealthResults", "MentalHealthFindings", "ProgressChart",
    "RouterCard", "RouterResultsTable", "RouterMixChart", "RouterHindsightTable", "FitMatrix", "RiskCoverage",
    "ClaimBenchCascade", "ReportStacks", "ReportTrajectory", "ProgramBenchResultsAnalysis", "KSPScoreOverTime",
    "KSPTimeHorizonIndex", "PokerChipTimeline", "SnapTopicPhaseMap", "SnapEvaluationPipeline", "SnapJudgeConfusionMatrix"}


def _chart_mapping(family):
    lowered = family.lower()
    for token, view in (("scatter", "scatter"), ("heatmap", "heatmap"), ("matrix", "heatmap"),
        ("radar", "radar"), ("spider", "radar"), ("histogram", "histogram"), ("box", "box plot"),
        ("treemap", "treemap"), ("timeline", "timeline"), ("overtime", "timeline"), ("linechart", "lines"),
        ("table", "table"), ("stack", "stacked bars"), ("bar", "bars"), ("dot", "scatter")):
        if token in lowered:
            return view
    return "source charts explorer"


def collect(fetch):
    """Return a complete source pack. ``fetch`` snapshots each official URL."""
    retrieved = datetime.now(timezone.utc).isoformat()
    pack = {"schema_version": 1, "provider": "vals", "retrieved_at": retrieved,
            "sources": [], "benchmarks": [], "observations": [], "inventory": [],
            "visualization_data": []}
    catalog_page, comparison = Page(fetch(CATALOG)), Page(fetch(COMPARISON))
    models, aliases, model_url = _model_catalog(fetch, comparison)
    pack["sources"].append({"id": "vals", "name": "Vals AI", "url": CATALOG,
        "data_url": model_url, "methodology_url": BASE + "/benchmarks/vals_index",
        "status": "ok", "license": "Not stated", "notes":
        "Public first-party Astro JSON and page props, plus literal model metadata from its public JS asset. "
        "No executable JavaScript is evaluated. Score dates are source snapshot dates, not per-run dates. "
        "Published standard errors remain standard errors. Historical versions and task slices remain distinct."})
    pages = {CATALOG: catalog_page, COMPARISON: comparison}
    special_cache = {}
    queue = deque([CATALOG])
    seen, bench_ids = set(), set()
    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            page = pages.get(url) or Page(fetch(url))
        except Exception as exc:
            pack["inventory"].append({"name": url.rsplit("/", 1)[-1], "url": url,
                "type": "dataset", "supported_view": "source audit", "status": "unavailable", "notes": str(exc)})
            continue
        pages[url] = page
        for link in page.links:
            if re.fullmatch(r"/benchmarks/[a-zA-Z0-9_-]+", link):
                target = _url(link)
                if target not in seen:
                    queue.append(target)
        if url == CATALOG:
            continue
        data_url, view, error = url, None, None
        loader = next((props.get("benchmarkViewUrl") for _, props in page.islands if props.get("benchmarkViewUrl")), None)
        if loader:
            data_url = _url(loader)
            try:
                view = json.loads(fetch(data_url))
            except Exception as exc:
                error = str(exc)
        if view is None:
            embedded = [props["benchmarkView"] for _, props in page.islands if isinstance(props.get("benchmarkView"), dict)]
            embedded = [item for item in embedded if "metadata" in item and "tasks" in item]
            if embedded:
                view = max(embedded, key=lambda item: len(json.dumps(item)))
                data_url = url
        if view is None and url.endswith("/rsi_index"):
            component = next((component for component, _ in page.islands if "/RsiBenchmarkView." in component), None)
            if component:
                component_url = _url(component)
                special_cache[component_url] = _special_asset_data(fetch, component_url)
                for asset in special_cache[component_url].get("assets", []):
                    values = list(asset.get("literals", {}).values())
                    metadata = next((item for item in values if isinstance(item, dict) and item.get("benchmark_id") == "rsi_index"), None)
                    tasks = next((item for item in values if isinstance(item, dict) and "overall" in item and isinstance(item["overall"], dict)), None)
                    if metadata and tasks:
                        view, data_url = {"metadata": metadata, "tasks": tasks}, asset["url"]
                        break
        if view and "metadata" in view and "tasks" in view:
            metadata = view["metadata"]
            for task, rows in view["tasks"].items():
                if not isinstance(rows, dict):
                    continue
                benchmark = _benchmark(metadata, task, url, data_url)
                benchmark["upstream_urls"] = sorted({link for link in page.links if urlsplit(link).hostname in {"github.com", "arxiv.org", "huggingface.co", "www.tbench.ai", "tbench.ai", "www.swebench.com", "swebench.com"}})
                if benchmark["id"] not in bench_ids:
                    pack["benchmarks"].append(benchmark)
                    bench_ids.add(benchmark["id"])
                for model_key, row in rows.items():
                    if isinstance(row, dict) and _number(row.get("accuracy")):
                        pack["observations"].append(_observation(benchmark, model_key, row, models, aliases, data_url))
            pack["sources"].append({"id": "vals-" + _slug(url.rsplit("/", 1)[-1]),
                "name": metadata["benchmark"], "url": url, "data_url": data_url,
                "methodology_url": url, "status": "partial" if error else "ok", "license": "Not stated",
                "notes": "Complete published tasks object. " + ("JSON endpoint failed; recovered embedded view: " + error if error else
                "Extracted from first-party benchmark JSON." if data_url != url else "Extracted from first-party embedded Astro props.")})
        else:
            pack["sources"].append({"id": "vals-" + _slug(url.rsplit("/", 1)[-1]),
                "name": page.headings[0] if page.headings else url.rsplit("/", 1)[-1], "url": url,
                "data_url": url, "methodology_url": url, "status": "partial", "license": "Not stated",
                "notes": "Specialized page; no standard benchmark tasks JSON. See visualization inventory."})

    # Inventory every chart family on every discovered page, preserving nonstandard
    # data props for reuse instead of pretending each visualization is an accuracy score.
    for url, page in pages.items():
        family_counts = {}
        for component, props in page.islands:
            family = component.rsplit("/", 1)[-1].split(".")[0]
            if family in EXAMPLE_COMPONENTS or not family:
                continue
            title, mapping = CHARTS.get(family, (props.get("title") or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", family), _chart_mapping(family)))
            family_counts[family] = family_counts.get(family, 0) + 1
            if family == "FooterTrendLine":
                # The global footer repeats the same data across every page.
                if url != CATALOG:
                    continue
            has_standard = any(item["url"] == url and item["status"] == "ok" for item in pack["sources"])
            inventory_id = "vals-chart-" + _slug(url.rsplit("/", 1)[-1]) + "-" + _slug(family) + "-" + str(family_counts[family])
            extra = {key: value for key, value in props.items() if key not in
                     ("benchmarkView", "benchmarkViewUrl", "data-astro-transition-persist", "rawData", "transcript")}
            if family in SPECIAL_COMPONENTS:
                component_url = _url(component)
                try:
                    if component_url not in special_cache:
                        special_cache[component_url] = _special_asset_data(fetch, component_url)
                    extra.update(special_cache[component_url])
                except Exception as exc:
                    extra["extraction_error"] = str(exc)
            if extra:
                pack["visualization_data"].append({"id": inventory_id, "source_url": url,
                    "name": title, "component": family, "data": extra, "updated": page.updated, "asset_url": _url(component)})
            pack["inventory"].append({"name": title, "url": url, "type": "visualization",
                "supported_view": mapping, "status": "data-only" if extra or has_standard else "unavailable",
                "notes": "Data extracted; rendering coverage is tracked by the application. " +
                ("Includes projected frontier values; projections must stay visibly separate from measurements." if family == "FooterTrendLine" else
                 "Original specialized component data retained." if extra else "Uses the source's benchmark observations.")})
            if family == "ReasoningEffortChart" and props.get("records"):
                parent_id = "vals-" + _slug(url.rsplit("/", 1)[-1])
                parent = next((item for item in pack["benchmarks"] if item["id"] == parent_id), None)
                if parent:
                    benchmark = dict(parent, id=parent_id + "--effort-study", name=parent["name"] + " · Reasoning effort study",
                        parent_benchmark_id=parent_id, task="effort-study", task_name="Reasoning effort study",
                        description="Separately published reasoning-effort study; results may differ from the main leaderboard run.")
                    benchmark.pop("source_metadata", None)
                    pack["benchmarks"].append(benchmark)
                    for record in props["records"]:
                        if not _number(record.get("score")):
                            continue
                        row = dict(record, accuracy=record["score"], stderr=record.get("se"),
                                   latency=(record.get("latency_s") or {}).get("mean"), reasoning_effort=record.get("effort"))
                        observation = _observation(benchmark, record["model"], row, models, aliases, url)
                        observation["model"] = record.get("label", observation["model"])
                        observation["notes"] = record.get("cost_basis") or props.get("costNote") or "Separate effort study"
                        observation["effort_rank"] = record.get("effort_rank")
                        observation["is_default_effort"] = record.get("is_default")
                        observation["tokens"] = record.get("tokens", {})
                        pack["observations"].append(observation)
    categories = sorted({item.get("native_category") for item in pack["benchmarks"] if item.get("native_category")})
    for heading in catalog_page.headings:
        if heading.endswith(" benchmarks") or heading == "Vals Indexes":
            pack["inventory"].append({"name": heading, "url": CATALOG, "type": "category",
                "supported_view": "benchmark filters", "status": "data-only",
                "notes": "Published catalog section label; internal dataset industry can differ (for example beta versus Games)."})
    for category in categories:
        pack["inventory"].append({"name": category, "url": CATALOG, "type": "category",
            "supported_view": "benchmark filters", "status": "data-only",
            "notes": "Original Vals industry/category retained alongside the explorer's common category."})
    pack["inventory"].append({"name": "Dataset access, execution mode, version and model facets", "url": CATALOG,
        "type": "category", "supported_view": "filters", "status": "data-only", "notes":
        "Preserved public/private, agentic/non-agentic mode, archived version, model lab/country, "
        "open/proprietary weights, model release date, modalities, inference provider, harness and effort. "
        "Open weights is Vals' original open_source boolean, not an independent license determination."})
    return pack
