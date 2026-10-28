# Source packs

Each source adapter writes `data/sources/PROVIDER.json`, with `schema_version: 1`, `provider` (id), `retrieved_at` (UTC ISO), `sources`, `benchmarks`, `observations`, and `inventory` arrays. Python adapters live in `scripts/adapters/PROVIDER.py`, expose `collect(fetch)` returning the pack, and do not write the unified data directly. `fetch(url)` returns bytes and records a raw snapshot. Use only verified source facts. No synthetic scores.

Source entry: `id`, `name`, `url`, `data_url`, `methodology_url`, `status` (ok/partial/unavailable), `license` (published license or `Not stated`), `notes`.

Benchmark entry: `id` (provider-prefixed stable slug), `name`, `provider`, `category` (General, Coding, Science, Knowledge work, Math, Preference, Multimodal, Other), `unit` (%, score, Elo, seconds, USD), `higher_is_better` (boolean), `min`/`max` (known published scale or null), `version`, `source_url`, `dataset_url`, `description`, `private` (true/false/null), `kind` (benchmark/composite), optional `native_category` and `components`.

Observation entry: `benchmark_id`, `model` (exact source model label), `lab` (if known), `score` (number), `source_url`, optional `effort`, `harness`, `date` (actual result/snapshot date or null), `cost_usd`, `latency_seconds`, `speed_tps`, `input_price`, `output_price`, `ci_low`, `ci_high`, `weights` (open/proprietary/unknown), `context_tokens`, `release_date`, `source_model_id`, `notes`. Prices are per million tokens. Do not infer per-task costs from token prices. Original labels survive canonical identity mapping in the compiler. Source records from different evaluators must never overwrite one another.

Inventory entry: `name`, `url`, `type` (visualization/category/dataset), `supported_view` (our planned mapping), `status` (ported/data-only/unavailable), `notes`. Inventory the provider's chart families/categories and extraction coverage, and record limitations candidly.

The UI composes custom weighted scores only from explicit selected measurements; raw source metrics remain available. Missing-score policy and normalization must be visible and configurable. A snapshot is not a time-series history.

## Extended records and compilation

`kind` also accepts `metric` and `trait`. Task/category slices use `parent_benchmark_id`; historical versions use `archived`. Published index `components` contain referenced benchmark IDs and source weights. `private` may be null for mixed or unspecified privacy; `private_share` can retain a documented fraction. Native categories and the imported catalog survive without forcing every source into one taxonomy.

Observations can retain `source_metrics`, `provenance`, `evaluator`, `aggregator_url`, `extraction_url`, `archive_member`, `inference_provider`, run/submission identifiers and original metadata. `stderr` or `standard_error` is separate from `ci_low`/`ci_high`; `ci_kind` and `ci_level` preserve interval meaning. Endpoint performance uses `endpoint_latency_seconds` / `endpoint_speed_tps` and its explicit basis. Task metrics cannot silently inherit generic endpoint numbers. Original complete evaluation costs remain separate from per-task/trial costs.

`scripts/catalog.py` compiles packs into the ignored `data/catalog.json`. Source labels survive in `model`, canonical display names and aliases live in `models`, and known lab/country spellings are harmonized only for navigation. Original country is retained as `source_country`; the raw lab remains on observations. Conservative model identities remove recognized reasoning qualifiers but retain version/subfamily distinctions. They do not infer that two differing source endpoint names represent the same weights. Observation IDs hash the complete source record including provider and retrieval metadata; exact duplicate rows are removed, while differing evaluator/setup/version records survive. Every finite score must reference a benchmark and have an original label/source URL. Problems are reported, never filled with synthetic values.

Optional `history` stores actual dated records. `visualization_data` retains original chart metadata and nested public props/data. The compiled catalogue includes chart metadata and stable source indices but excludes large chart payloads; `/api/chart` reads them on demand. Source-chart structures are not promoted to measured benchmark observations. Adapter-native extras (such as source catalog, ECI inputs/fits and manifests) remain in the source packs.
