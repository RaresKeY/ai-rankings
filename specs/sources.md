# Official source integrations

The catalogue is built from six evaluator/source families. Each adapter exposes `collect(fetch)` and receives an HTTPS fetch callback. Parsers read inert public JSON/CSV/HTML data; they do not execute downloaded code. Source observations remain distinct across providers. External citations aggregated by Epoch are explicitly secondary and must not be counted as fresh independent runs.

| Source | Actual data origin | Initial coverage |
|---|---|---|
| Artificial Analysis | Public serialized page data from the model page, evaluation catalog and media leaderboards | 22,511 observations, 256 series; index components, domain indices, cost/performance and media categories |
| Vals AI | Public benchmark catalog/pages, discovered `benchmark_view_*.json`, model-registry literals and specialized chart props | 27,946 observations, 505 series; tasks/versions, 327 original chart records and 95 component families |
| Epoch AI | Official benchmark ZIP/internal CSV/Cyber ECI CSV, benchmark catalog and external benchmark configuration | 9,392 distinct observations, 224 series; original evaluator citations, ECI, fits and adjusted input data |
| Arena | Official `lmarena-ai/leaderboard-dataset` on Hugging Face via its paginated rows API | 30,652 observations, 145 series; text, vision, search, code, image, video and Agent categories; 1,949 dated Agent history records |
| Terminal-Bench | Official public Harbor leaderboard-read endpoint used by `tbench.ai` | 456 observations, 13 series; 4.0, 3.0, 2.1, 2.0 and Science 0.1, including available pass@k |
| SWE-bench | Official website repository's `data/leaderboards.json` | 1,336 observations, 59 series; official splits, submissions, harness/model setups and published metrics |

Counts reflect the initial snapshot, not a promise that every source publishes the same models or tests. Epoch's pack has 9,395 rows; the compiler removes three exactly duplicate observations. Grouped catalogue totals: 92,293 observations, 1,202 series, 2,075 conservative model IDs. The 109 source entries preserve category/page-level metadata but are grouped into six UI families.

## Semantics and incomplete coverage

AA's published composite is imported directly. Individual source component weights are available for exploration, but raw arithmetic does not reconstruct calibrated Elo components. General endpoint speed/latency cannot impersonate task runtime. Privacy can be mixed: a partially private composite is not simply public or private.

Arena raw and style-controlled ratings/categories stay separate. Bradley–Terry ratings are not labelled literal Elo. Agent IPS effects are percentage-point effects that can be negative, not success rates. The full historical Arena archive is not downloaded; only the imported dated Agent history is displayed.

Terminal-Bench and SWE-bench are submitted model-plus-agent runs. Their evidence must retain run IDs, harness versions and effort. Partial reported run cost cannot become mean task cost. Terminal mean trial cost is derived only from complete total cost and trial count. Pass@k remains distinct from single-attempt accuracy, without borrowed intervals. Science standard errors are not 95% intervals.

The source inventory has 530 chart/category/dataset records and keeps the adapters' availability status. The 329 source-chart records comprise 156 embedded numeric structures and 173 source components whose values come from separately imported benchmark tables. All 329 resolve to exploratory series. This does not reproduce every original interaction: private task/trial records, conversation examples, some API/time histories, legacy categories and arbitrary ECI statistical refits remain unavailable. Vals trajectory/conversation structures can remain source-only details even when the same page's benchmark results are explorable. Inventory status `data-only` describes extraction; the explorer maps the data to its own chart families.

## Refresh, evidence and retention

`scripts/refresh.py` restricts hosts and redirects to verified official origins. The Supabase exception allows only the verified Terminal-Bench public reader path. Responses are bounded at 64 MiB with a 45-second timeout, cached for six hours when cache mode is enabled, and retained compressed by URL hash with URL, content hash, size and available response metadata. The UI's refresh bypasses cached reads. TLS verification stays enabled.

Source packs replace atomically only after successful extraction/serialization. Empty results, parser failures, or loss of any previously populated test series retain the previous pack; upstream retirement/schema changes require review. The last twelve replaced snapshots per provider are compressed under `data/history/`. `data/refresh-status.json` retains the most recent refresh outcome. The catalogue is generated from successful packs and reports missing references.

Initial extraction evidence was consolidated from task worktrees to `.local/import-evidence/` before cleanup. Its manifest maps 563 responses to preserved files/URLs/hashes, including the five checked Terminal-Bench payloads. Some initial fetchers did not capture HTTP headers: local file mtimes are explicitly not claimed as server timestamps. All six adapters were replayed offline from those exact saved bytes. New refreshes record their own timestamps and headers. The workstation's system/Python CA check passed before acquisition; evidence is `.local/ca-trust.json`. Recheck when the runtime, trust store or TLS settings change.
