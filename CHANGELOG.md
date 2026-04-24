# Changelog

All notable changes to this repository are tracked here.

## [0.2.1.0] - 2026-04-24

### Changed

- Changed strict memo anchor accounting so market price anchors come from live market quotes or explicit market-anchor payload fields, while model max-entry recommendations stay in fair-entry accounting.
- Changed semantic relevance filtering to `semantic_relevance.v2`, where same-claim decisions only apply across sources when the runner explicitly marks them as claim-level decisions.
- Changed calibration readiness so production status requires real clean scan coverage and clean operator-trust signals, not just a manual report override.

### Fixed

- Fixed anchor-gap reporting that could display a model-recommended entry price as the market price anchor.
- Fixed source-level semantic relevance decisions that could accidentally remove independent evidence sharing the same claim key.
- Fixed production readiness reporting so `strict_degraded` alerts and zero-scan runs cannot satisfy the production-ready gate.

## [0.2.0.0] - 2026-04-22

### Added

- Added richer scan payloads so judgment now sees best bid, best ask, mid, last price, event metadata, family context, and ranking context in one path from scan to archive.
- Added shortlist retrieval inputs that pull in sibling-expression and deadline phrases, plus heartbeat output that shows shortlist, retrieval, and promoted-seed counts directly in the archive.
- Added coverage for ranking metadata, retrieval query shaping, richer executable fields, and the updated heartbeat/reporting path.

### Changed

- Changed scan accounting so runs now persist shortlist size, retrieved-shortlist size, promoted seed count, missing-metadata counters, and rejection explanations instead of relying on coarse ops-style counts alone.
- Changed ranking to expose explicit metadata-missing flags and supported-domain context, which makes shortlist ordering and later miss review easier to inspect.
- Changed the scan smoke path and fixtures so real fixture-backed runs exercise the richer payload shape and recall-first counters.

### Fixed

- Fixed the remaining gap between the scan discovery foundation plan and the shipped runtime by making shortlist and retrieval accounting visible in run state and heartbeat artifacts.
- Fixed retrieval query generation so promoted candidates can use same-event family and deadline context instead of relying only on the primary expression text.
- Fixed heartbeat verification drift by snapshotting the richer deploy-time counters and keeping the fixture-backed runtime flow consistent with persisted scan semantics.

## [0.1.0.0] - 2026-04-21

### Added

- Added the `runtime/` Polymarket alert bot package with scan, monitor, callback, report, service, storage, archive, template, and source modules.
- Added the runtime service shell, Docker and compose examples, runtime CI, and a repo-root health command that points at the real Python project.
- Added unit and integration coverage for contract parity, scan and monitor execution, callback flows, service endpoints, archive rendering, and CLI smoke paths.

### Changed

- Moved the runtime judgment contract into canonical Python code, then aligned the adapter, parser, skill references, and eval payloads to that single source of truth.
- Split orchestration out of `runtime_flow.py` into dedicated `flows/scan.py`, `flows/monitor.py`, and `flows/callback.py` modules while keeping public entrypoints stable.
- Updated the root README, docs tree, CLAUDE routing, and runtime references so the repo now describes the skill plus operational runtime accurately.

### Fixed

- Fixed strict gating, degraded evidence handling, market-link persistence, and earlier runtime review findings across the scan, monitor, and callback paths.
- Fixed narrative monitor triggers so they advance to `fired` and stop requeueing on every monitor cycle.
- Fixed Telegram callback replay handling so duplicate deliveries are idempotent and callback side effects commit transactionally.
