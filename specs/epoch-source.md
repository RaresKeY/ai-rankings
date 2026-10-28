# Epoch AI source contract

Owner: `scripts/adapters/epoch.py`; snapshot: `data/sources/epoch.json`; validation: `tests/test_epoch.py`.

## Collection

The adapter downloads Epoch's [official CSV ZIP](https://epoch.ai/data/benchmark_data.zip), [internal run CSV](https://epoch.ai/data/benchmarks.csv), and [Cyber ECI](https://epoch.ai/data/cyber/eci_scores.csv). It discovers the current benchmark catalog from the official search page's data imports and reads [the public external benchmark configuration](https://epoch.ai/generated/external-benchmarks-config.js). A bounded inert literal reader extracts data; it never executes JavaScript. Unknown score transformations stop collection rather than guessing a scale.

All main external metrics and source-configured metric selectors are imported. Numeric fields not exposed as a selector remain in each observation's `source_metrics`. The original 99-entry catalog is preserved in `native_catalog`, including review-only/hidden entries for which no result is fabricated. Provider-specific categorization survives in `native_category`; the common category is a documented mapping from native domains.

## Provenance and identities

`internal` observations come from Epoch's own successful runs. Exact task versions become distinct benchmark IDs. Model display labels, raw model identifiers, effort, run IDs, release dates, and run start times are preserved. Internal score means are used, with the published standard error. Bars are labelled **one standard error**, never relabelled as 95% confidence intervals.

`external-via-epoch` observations are secondary aggregation. `source_url` links to the originally cited source, `evaluator` preserves Epoch's source label, `aggregator_url` links to Epoch's benchmark page, and `extraction_url` plus `archive_member` identify the bytes actually imported. A direct-source adapter should remain separately selectable; these rows must not silently be presented as fresh independent evaluations or double-counted with their upstream equivalents. Unavailable original links are explicitly noted.

The imported general/cyber ECI is a statistical composite with an unbounded score scale. Published bootstrap intervals are 90%. Its `date` remains null because the CSV's date is a **model release date**, not when a past ECI score was measured. Current ECI plotted at model release dates is a frontier comparison, not historical ranking snapshots.

## Units and metadata

Source numeric transforms define score units. Fractional accuracy is converted to percentage points; already-percent scores retain their numeric values. Non-percentage metrics remain score/Elo/USD; METR's minute-valued time horizon is explicitly converted to seconds. Lower-is-better flags, including BTF-3 and rank, survive.

Costs are retained in `published_costs` with original column names. Only explicitly per-task/test costs enter `cost_usd`; full-evaluation or per-run costs never become per-task prices. Published latency values retain their basis, with hour-to-second conversion where explicit. Country, release date, accessibility, numeric training-compute estimates and parameters are retained where present. The adapter does not infer missing prices, context windows, histories or compute.

## ECI auxiliary chart data

`visualization_data` contains published EDI difficulty/slope fit parameters and preprocessed ECI input points, with source URLs and interpretation notes. Both also survive in `eci_fits` and `eci_inputs`. The input performance values are adjusted by Epoch's methodology and are deliberately excluded from raw observations and ordinary weighted composites. Baselines and score ceilings come from the benchmark metadata CSV. Rendering fitted curves requires respecting this adjusted scale; expected performance is not a measured result.

The inventory maps score/date, score/compute, score/ECI, domain/general, ranking/forest, difficulty curves, metric selectors and metadata filters. It marks these as `data-only` until the owning UI implements them. Epoch's arbitrary custom-domain ECI refits/bootstrap computation are unavailable here; a user-weighted arithmetic composite must not be labelled an ECI refit.

## Rights

Epoch's own data is [CC BY 4.0](https://epoch.ai/benchmarks/use-this-data). Credit Epoch AI and the original external sources. External projects retain their own licenses. Benchmark questions, private tasks and model traces are not downloaded or republished.
