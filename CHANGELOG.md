# Changelog

All notable changes to this repository are tracked here.

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
