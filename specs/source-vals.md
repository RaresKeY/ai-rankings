# Vals AI source adapter

Owning files: `scripts/adapters/vals.py`, `data/sources/vals.json`, `tests/test_vals.py`.

`collect(fetch)` crawls Vals' public benchmark catalog and the linked benchmark/version pages, discovers the first-party `/_astro/benchmark_view_*.json` resources from serialized page props, and imports their complete task objects. Vals runs these evaluations; the measured results are sourced from Vals rather than a secondary leaderboard. Published upstream repository/paper links are retained as `upstream_urls` on benchmarks.

Model labels, creator, release date, weight-access classification, country, modalities, context, and token prices come from the literal data in the public model registry JS asset imported by Vals' comparison page. A small nonexecuting parser accepts only strings, finite numbers, booleans, null, arrays, and data objects. It rejects executable expressions. Refresh fetches stay on `www.vals.ai`.

## Measurement semantics

- Every task and historical benchmark version has its own ID. Task slices carry `parent_benchmark_id`; obsolete versions retain the source `archived` flag. Family, version, source snapshot date, mode, source industry, and page URL survive import.
- Effort-study records are separate from the main leaderboard. The studies sometimes publish different scores at the nominal default effort; they are not silently substituted for the main run.
- Standard errors remain `stderr`, labeled standard error. No confidence interval is fabricated.
- The RSI index is published on a 0–1 reference-anchored scale. Its internal JSON stores 100 times that value; the adapter divides by 100, records the original in `source_metrics.accuracy_scaled_100`, and explains the transformation. Poker's TrueSkill ratings remain unbounded scores.
- Zero cost/duration placeholders that the source displays as dashes are retained as raw missing-value evidence and omitted from the comparable `cost_usd` / `latency_seconds` fields. Zero accuracy remains a valid score.
- Cost and latency labels are preserved, including cost per hand and recorded campaign API cost. Token prices are not substituted for measured task cost.
- The inference-provider study keeps endpoint IDs and the serving provider separate from the model's creator. It retains request distributions, token and tool metrics, paired baseline deltas, and subset hashes. `speed_tps` is the source's median per-request output-plus-reasoning generation speed.
- Null or absent results stay absent. A publication date is not asserted to be an individual run date. Model-release plots are not repeated evaluations of a fixed model.

## Visualization coverage

Every plot component discovered on the benchmark pages is inventoried. Standard chart families reuse normalized observations. Specialized numeric chart props and literal study data are retained in `visualization_data`, with original component name, exact page/asset origins, update date where published, and unmodified nested data. This includes distributions, radar/behavior plots, legal and social-benefit matrices, routing studies, inference-provider diagnostics, KSP progress/human-time proxies, poker, and mental-health risk analyses. The application determines the actual rendered coverage; import records say `data-only`, not `ported`.

Prose sample conversations, patch examples, illustrative screenshots, and source UI code are not copied. Source-only interactive examples and components without extractable numerical data remain visible as inventory limitations. Source projections remain explicitly labeled and separate from observations. Public-benefits judge matrices and KSP proxy bounds must retain their source-specific interpretation; neither is a generic model accuracy confidence interval.

The SAFE-Teen and CyberOffense pages publish specialized studies rather than the standard benchmark tasks format. Their chart data is retained for source-chart exploration, and the source status stays partial because those studies are not flattened into general accuracy rankings. Some external paper/dataset links provide background or benchmark definitions; they are not substituted for Vals' evaluator runs.

Vals does not state a blanket data-reuse license on the examined catalog/benchmark pages. The source pack records `Not stated`. Raw retrieval snapshots are local fetch evidence; the compact pack is the committed dataset. All fetch URLs, exact extraction methods, source labels, and missing-data boundaries are reviewable.

## Validation

`python -m unittest discover -s tests -p test_vals.py` covers nonexecution of JS expressions, URL restrictions, version/task identity, missing costs versus zero accuracy, standard-error semantics, scale preservation, and snapshot referential integrity/score bounds. A refresh should also inspect source statuses and chart extraction errors before accepting the updated pack.
