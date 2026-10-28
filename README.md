# AI Rankings

Compare published AI benchmark results, select tests and weights, and inspect source attribution.

[Website](https://rareskey.github.io/ai-rankings/) · [Update runs](https://github.com/RaresKeY/ai-rankings/actions) · [Data policy](specs/publishing.md)

The public edition includes **Arena** and **Epoch AI's own evaluations and published indices**, under CC BY 4.0. The initial public snapshot has 32,785 observations, 253 test series and 1,029 conservatively grouped model labels. Counts change with updates. External results aggregated by Epoch are excluded unless their original redistribution rights are established.

## Views and controls

- Rankings with original scores or selected tests and weights; horizontal bars, columns and score contributions.
- Cost and performance scatterplots with adjustable axes, logarithmic scales and Pareto frontier. Missing cost/timing data stays missing.
- Benchmark matrix, model comparisons and normalized radar charts.
- Release timelines, available observation histories, weight sensitivity and distributions by lab, country or weight access.
- Source charts with selectable fields and bar, line, scatter or table views.
- Test catalog, observation table and source coverage with licenses, dates and original evaluation links.

Custom scores use explicit normalization and missing-result policies. Published source indices remain separate from custom weighted averages. Model variants retain effort, agent and endpoint details; matched-configuration mode keeps these setups separate. CSV exports retain raw scores, source links and licenses. SVG exports include attribution metadata. View links preserve settings.

## Run locally

Python 3 and a modern browser are sufficient. No package installation is needed.

```sh
./play.sh
# http://127.0.0.1:8768
```

A public clone builds a static website from the approved seeds. To update and rebuild:

```sh
python3 scripts/refresh_public.py
python3 scripts/build_static.py
python3 -m http.server 8770 --bind 127.0.0.1 --directory dist
```

The original workspace also supports a larger local research dataset under `data/sources/`. If those packs exist, the launcher uses its local server and refresh controls. These files and their Git history are not part of the public repository. Importer code does not grant rights to redistribute upstream data.

## Automated updates and hosting

GitHub Actions updates approved providers daily at **05:37 UTC**, on main pushes, and on manual dispatch. It checks calculations, filters public data, builds static files and publishes to GitHub Pages. Failed or unexpectedly incomplete imports preserve the last successful data. The Sources page reports update failures, and CI marks the run unsuccessful after publishing retained data.

The workflow uses installed Python, Git, gh and Chromium. It installs no dependencies. TLS uses a reviewed, pinned CA bundle configured before checkout. See [publishing specs](specs/publishing.md) for trust maintenance, retention and deployment details. GitHub schedules may be delayed and may be disabled after prolonged repository inactivity.

## Source permissions

- **Included:** Arena's official dataset and Epoch AI's own results, CC BY 4.0 with attribution.
- **Artificial Analysis:** excluded. Its terms require written consent for this kind of combined public ranking service and raw-data redistribution.
- **SWE-bench website results:** excluded because the repository uses CC BY-NC 4.0.
- **Vals and Terminal-Bench results:** excluded pending verified commercial redistribution permission. Open-source benchmark code does not establish a license to every leaderboard result.

See [source notices](THIRD_PARTY_NOTICES.md) for primary links and attribution. No endorsement by the evaluators is implied.

## Verification

```sh
python3 -m unittest discover -s tests -v
deno test tests/engine_test.js tests/source_charts_test.js
deno check app/app.js app/engine.js app/source-charts.js
# Without Deno, use installed Chromium for the same calculation tests:
python3 scripts/browser_unit_tests.py
```

[Specs map](specs/_readme.md) · [Publishing](specs/publishing.md)
