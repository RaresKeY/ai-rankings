# Source attribution and distribution

The public edition includes data from the sources below. The interface and importers are original project code. No upstream frontend library, font, branded graphic or executable website bundle is distributed in the app.

## Included data

- **Arena / LMArena**, [official leaderboard dataset](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset), [dataset license declaration](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset/blob/main/README.md). Licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). The import preserves published categories, style-control distinctions, original model labels, uncertainty, source URLs and dates.
- **Epoch AI, Capabilities & benchmarking**, published online at epoch.ai, [data and citation](https://epoch.ai/benchmarks/use-this-data), [methodology and licensing](https://epoch.ai/benchmarks/about). Licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). Initial access: 28 October 2026; each snapshot records its retrieval date. Only Epoch-administered evaluations, published ECI scores and fitted difficulty parameters are distributed. Externally aggregated results and adjusted ECI input observations are excluded. Benchmark questions and answers remain the property of their respective creators and are not included.

Changes by this project: units normalized, model labels grouped conservatively, source fields selected and categorized, and new chart renderings generated. Custom scores use selected tests, normalization and weights. Raw results and custom scores are identified separately. These changes are not attributed to the original evaluators. Source names indicate provenance, without affiliation or endorsement. JSON, CSV and SVG exports retain attribution; downstream users must preserve applicable attribution and license notices.

## Excluded data sources

The original local research workspace can contain the following datasets. They are excluded from public source history, seed packs, CI inputs and website output.

- **Artificial Analysis:** [Website Terms](https://artificialanalysis.ai/terms-of-use), [Data Platform Terms v1.1](https://artificialanalysiscdn.com/legal/ProDataPlatformTerms.pdf), [API documentation](https://artificialanalysis.ai/data-api/docs). The terms restrict similar public ranking services, raw-data redistribution and combining data into public services. Written consent is required for this use. Free API access or a commercial subscription alone does not resolve those restrictions.
- **SWE-bench website results:** [website repository license](https://github.com/SWE-bench/swe-bench.github.io/blob/master/LICENSE), [result file](https://github.com/SWE-bench/swe-bench.github.io/blob/master/data/leaderboards.json). The website repository uses CC BY-NC 4.0. Noncommercial-only data is excluded from the public edition. The benchmark harness and submitted agents can have different licenses.
- **Vals AI:** [benchmark catalog](https://www.vals.ai/benchmarks). No blanket commercial redistribution permission was established for the reviewed website result tables and chart datasets. Licenses on individual evaluation-code repositories do not by themselves license these results.
- **Terminal-Bench / Harbor:** [official leaderboard](https://www.tbench.ai/), [Harbor hub](https://hub.harborframework.com/). No verified commercial redistribution license was established for the imported public leaderboard backend. Task and framework licenses do not establish rights to every submitted result table.

## TLS certificates

`ci/ca-bundle.pem` contains public CA root certificates selected from the workstation's audited trust store. These are public trust anchors, not private keys. Their fingerprints are pinned in `ci/ca-bundle.sha256`; source, maintenance and usage are documented in `ci/README.md`.
