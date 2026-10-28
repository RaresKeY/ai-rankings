# Public distribution

The user chose commercially reusable data only. The public repository is `RaresKeY/ai-rankings`; the static website uses GitHub Pages from `gh-pages:/`. Local `main` contains the complete research snapshots and must never be pushed. Local `public` tracks the clean public source history, published as remote `main`. Never push all branches or local history.

`scripts/export_public_repo.py` creates an explicit allowlisted source tree under `.local/public-source`. Its initial Git commit has no parent. Code, tests, specs and compressed approved seed packs may be included. Private packs, raw responses, local manifests and caches are excluded. Later public commits use the previous public commit as parent. `python3 scripts/commit_public.py` prepares that commit without changing the checkout; `git push origin public:main` publishes only that branch. The owning local checkout remains unchanged.

## Data policy

`scripts/public_data.py` accepts only Arena and Epoch packs with CC BY 4.0 metadata. Arena's official Hugging Face dataset is licensed CC BY 4.0. Epoch observations must identify Epoch AI as evaluator and have `internal` or `composite` provenance. Epoch's adjusted ECI input records and externally aggregated results are excluded. Published EDI fit parameters remain available separately from observed results. Unknown providers fail closed. Filtering runs again at build time and seed export time.

Artificial Analysis is excluded: its website terms restrict similar services, and Data Platform Terms §§2.4–2.5 restrict raw redistribution, combining sources and public ranking services without written consent. A free API key or commercial plan alone does not grant these permissions. SWE-bench's website results repository is CC BY-NC 4.0 and is excluded. Vals and Terminal-Bench leaderboard results lack verified blanket commercial redistribution permission in the reviewed sources; framework/task licenses are insufficient evidence. See THIRD_PARTY_NOTICES.md for links.

## Static build and updates

`scripts/build_static.py` consumes only `data/public/{arena,epoch}.json`, falling back to approved `data/seed/*.json.gz` on a fresh clone. It produces `dist/` with relative module/data URLs, compressed catalog/chart files, source snapshots and a hashed build manifest. Browser DecompressionStream handles static gzip bytes. No server API is used by the public edition. Its Sources page lists licenses, exclusions, retrieval times and update outcomes. CSV and SVG exports retain source and license attribution.

The workflow runs on main pushes, manual dispatch and daily at 05:37 UTC. It uses installed Python, Git, gh and Chromium; it invokes no Node tooling, pip or downloaded executable dependencies. Before the first network access it installs the reviewed, hash-pinned public CA bundle embedded in the workflow and selects it for Python, Git, curl and gh. SSL_CERT_DIR/GIT_SSL_CAPATH point to an empty directory. Unused runner/pip bundles are not used for network operations. The selected roots were copied from the workstation's advisory-audited trust store; validation to GitHub, Epoch and Hugging Face passed. Regenerate workflow with `scripts/configure_ci.py` after a reviewed trust change. Certificate rotation can require a reviewed bundle update; TLS verification is never bypassed.

The updater restores the last deployed approved snapshots, requests only approved providers, checks published licensing signals, retries transient HTTP failures, and preserves previous data when extraction fails, a populated test disappears, or observation count drops over 20%. A first import without a usable fallback fails. Failed updates are shown on the website and fail the final CI step after publishing retained data. Seeds are a fallback, not claimed to be newly refreshed.

The generated gh-pages branch retains one current snapshot to bound binary history. `scripts/publish_pages.py` validates output hashes and destination, then pushes with an explicit expected old SHA. Only this generated branch is replaced. It explicitly requests a Pages build through the REST API because GITHUB_TOKEN pushes do not automatically trigger Pages builds. Source history is preserved. GitHub may delay schedules or disable them after 60 days without repository activity; the Actions page supports manual runs.

## Verification and retention

Python tests check source rejection, Epoch provenance filtering, exclusion of auxiliary external data, fallback preservation and static build isolation. Browser calculation tests run the same eight JS tests as Deno using an installed browser and no packages. Workstation UI checks use Gamescope offscreen with real GPU rendering. `scripts/verify_hosted.py` verifies the hosted manifest and HTML/JS/config/catalog hashes in CI. Verify browser startup after deployment. Remove reproducible dist and export directories after hosted verification; retain source, approved fallback packs and verification evidence.
