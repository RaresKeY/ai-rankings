# AI Rankings

Local workspace project. Use Python standard library for ingestion/server and buildless browser JavaScript/SVG for the interface. No Node or downloaded JS dependencies.

Read `specs/_readme.md` and relevant specs before edits. Keep sources, evaluator runs, model effort, harness and benchmark versions distinct. Never fabricate unavailable scores, confidence intervals, release dates, costs or historical results. Preserve the original source label and URL on every observation.

Upstream scores are untrusted data: escape rendered content and restrict refresh URLs to curated official endpoints. Every imported pack must record its retrieval date, exact origin and extraction method. Missing results remain missing.

Publication: read `specs/publishing.md`. The original workspace's `main` includes private research snapshots and must never be pushed. Use `python3 scripts/commit_public.py` to prepare local `public`, then publish only `public:main` to the confirmed repository. Do not push all branches. A public clone has only approved seeds on its `main`; its normal source history can be used. Never add `data/sources`, raw responses or local evidence to the public tree. CI refreshes only Arena and Epoch's own results.
