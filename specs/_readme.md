# AI Rankings Specs Map

`specs/` is committed project memory for current intent and implementation. Read the relevant spec before changing its owning behavior, contract, boundary, source area, or verification flow, and update it with the implementation.

## Spec Map

| Spec | Owning sources | Scope | Read when |
|---|---|---|---|
| [Explorer](explorer.md) | `app/`, `server.py`, `play.sh` | Interface, calculations, local runtime and state | Changing views, controls, score semantics or startup |
| [Data contract](data-contract.md) | `scripts/catalog.py`, `scripts/refresh.py`, `data/` | Records, identifiers, acquisition and retention | Changing import, aggregation or metadata |
| [Source integrations](sources.md) | `scripts/adapters/`, `data/sources/` | Official origins and coverage boundaries | Refreshing or extending a provider |
| [Epoch source](epoch-source.md) | `scripts/adapters/epoch.py` | ECI, internal/external runs and source-specific units | Changing Epoch extraction or presentation |
| [Vals source](source-vals.md) | `scripts/adapters/vals.py` | Page/asset discovery, task identity and chart props | Changing Vals extraction or presentation |
| [Publishing](publishing.md) | `scripts/*public*.py`, `scripts/build_static.py`, `scripts/publish_pages.py`, `.github/`, `ci/` | Public data policy, source export, CI and Pages | Publishing or changing public ingestion |
| [Verification](verification.md) | `tests/`, `scripts/browser_check.py` | Data/calculation checks and offscreen UI verification | Validating behavior or preparing a handoff |

## Maintenance

- Keep specs compact, evidence-based, and current.
- Update this map when a spec is added, moved, split, or removed.
- Keep plans, TODOs, work logs, and merge handoffs outside `specs/`.
- Label planned behavior and open decisions; do not present them as implemented facts.
