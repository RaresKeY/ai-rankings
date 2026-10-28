# Verification

## Required checks for relevant changes

- `python -m unittest discover -s tests -v`: adapter correctness, nonexecution of source expressions, version/task identity, pagination, uncertainty/price semantics, source bounds and catalogue provenance.
- `deno test tests/engine_test.js tests/source_charts_test.js`: weighted ranking, missingness, fixed reference normalization, configuration separation, Pareto direction, sensitivity and exact-source chart fallback.
- `deno check app/app.js app/engine.js app/source-charts.js`: buildless module validation.
- With the local server running, `python scripts/browser_check.py`: real offscreen Chromium through Gamescope, using the installed runtime and a private profile. No synthetic browser library or downloaded package.

## Observed browser coverage

Desktop 1560×960 and mobile 390×844 are captured under `.local/visual/`. The script checks all views, index component expansion, contribution bars, a weight edit, radar/matrix/sensitivity, evidence source links, Vals preset, original source-series loading/field controls, CSV/SVG/JSON downloads, mobile navigation/evidence and Escape dismissal. It records JS exceptions, viewport/body widths and real GPU identity. The initial run used ANGLE on NVIDIA RTX 2080 Ti, not a forced software renderer. Processes are scoped to a task-owned session and cleaned on success/failure; no desktop focus is taken.

The JSON report and screenshots are local evidence, not committed generated assets. Source-chart audit confirms that every retained chart record resolves to embedded numeric series or explicitly identified observations from its exact source page. Offline adapter replay checks the actual saved extraction bytes. This does not claim that every private source interaction is available.

## Startup

Root `play.sh` is executable and path-independent. Playpad registration resolves this root and icon. Agent verification uses `playpad run ai-rankings --development`; opening the visible browser is a separate user-facing launch. The healthy server remains available on loopback. New source network activity is confined to explicit refresh or CLI import.
