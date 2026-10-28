# Explorer implementation

## Intent and runtime

The user requested a new workspace project combining the discussed ranking sites, with extensive exploration, direct-source data, test/weight control and clearer attribution. The requested `default-ui-look` supplies compact charcoal surfaces, a left navigation/filter pane, central analysis canvas and attached right controls/evidence pane. This is an original local interface; upstream source code and branded layouts are not reused.

`play.sh` resolves its own directory and execs the stdlib Python server. The server binds loopback only, normally port 8768, and can reuse an existing healthy AI Rankings instance. Player launches open a browser; `PLAYPAD_LAUNCH_MODE=development` leaves it closed. Playpad registration is `ai-rankings`, owning root `~/workspace/ai-rankings`, root icon `icon.svg`. There is one application and no separate lab chooser. No JS package manager, downloaded runtime dependency, container or frontend build is required.

`GET /api/data` serves the generated catalogue, compiling it if absent. `GET /api/chart` lazily serves a specified source chart. `POST /api/refresh` requires same-origin JSON and an allowlisted provider list; it runs acquisition in a background thread. `/api/refresh/status` exposes progress. Static serving is confined to `app/` plus the root icon. Large responses are gzip compressed. The service is local, unauthenticated, and not configured for public hosting.

## Calculations

`app/engine.js` owns the pure calculations. Single-test rankings display the raw source score, sorted in the source's stated direction. Multiple selected tests produce a custom weighted normalized score. Published finite min/max scales map to 0–100; absent bounds fall back to snapshot percentiles. Explicit percentile mode uses the full-snapshot best result per model/test as its fixed reference. Ties use midrank; variants beyond the reference range clamp to 0–100. Filtering cannot change that reference.

Missing results are excluded, renormalized across available tests, or explicitly counted as zero according to the selected policy. Weighted coverage is independently configurable and displayed. Contribution rectangles sum to the exact custom score. No custom confidence interval is inferred.

Default grouping selects the best reported run for a conservative model ID per test. Matched configuration keys also include reported effort, harness and inference provider. This can still group repeated runs with identical labels; it does not claim matched random seeds. Raw run IDs remain in observations. Effort, lab, access, country, modality, release date and deprecated filters are supported. Observation tables apply these filters while preserving all variants; aggregate coverage rules apply only to rankings.

Sensitivity sweeps one test's share in 5% steps, preserves the relative weights of the others and reapplies coverage. The zero endpoint uses a tiny positive target weight to preserve its coverage requirement; 100% removes the other tests. The UI states this endpoint behavior. A custom arithmetic mix is never labelled an Epoch ECI refit or reconstruction of AA's calibrated index.

## Views and state

`app/app.js` owns SVG charts, tables, input handlers and evidence inspection. Views include bars/columns with reported intervals, optional stacked contributions, axis-selectable scatter and Pareto, raw-score heatmap, model comparison/radar, release/history timeline, weight/rank sensitivity, grouped distributions, source chart exploration, test catalog, source inventory and observation table. The scatter can compare two selected tests directly; the vertical test determines which run supplies cost/time. A custom ranking uses the first selected test's metrics. Token prices and endpoint speed/latency have separate axes from task cost/time.

Release timelines use model release dates. History uses actual dated source records and does not interpolate absent results. Radar polygons only connect complete profiles; missing axes remain individual points. Graph labels, source notes and color legends remain present. All rendered upstream text is escaped and links are restricted to HTTP(S).

`app/source-charts.js` discovers bounded nested numeric series. If a component contains configuration only, it resolves separate per-test series from observations whose benchmark page exactly matches the chart page. It does not borrow a similarly named benchmark. Original chart JSON remains downloadable unchanged; the UI identifies shared-table fallback. Embedded fits, projections and adjusted inputs remain separate from ordinary observed rankings. The generic rendering provides control over fields; specialized upstream interactions are not asserted to be reproduced.

Settings persist in localStorage key `ai-rankings-state-v1`; a versioned URL fragment carries the shared view. No server account is used. CSV exports selected ranking observations with original labels and provenance. SVG is standalone. Right-pane evidence preserves original evaluator/aggregator links, effort, harness, endpoint and uncertainty type. Source identity motifs are fixed by provider ID in `sourceShapes`/`sourceMark`; the six shapes and palettes remain stable across sorting, views and reloads, beside visible names. They are original visual aids, not official logos or status indicators.

At narrow widths, navigation and evidence become dismissible attached overlays. Charts keep a readable width and scroll inside the canvas. Main-page body width must not overflow. Focus outlines, input labels and keyboard activation for selectable SVG marks are retained. Quiet scrollbars follow the supplied UI skill.
