# Polymarket Alert Bot Runtime

## Commands

- `uv run polymarket-alert-bot scan`
- `uv run polymarket-alert-bot monitor`
- `uv run polymarket-alert-bot report`

## Environment Variables

- `POLYMARKET_ALERT_BOT_DATA_DIR`
- `POLYMARKET_ALERT_BOT_DB_PATH`
- `POLYMARKET_ALERT_BOT_SOURCES_PATH`
- `POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM`

## Data Paths

- SQLite: `.runtime-data/sqlite/runtime.sqlite3`
- Archives: `.runtime-data/archives/`
- Reports: `.runtime-data/reports/`
- Locks: `.runtime-data/locks/`

## Scheduler Contract

- `scan` is the slow discovery job.
- `monitor` is the fast trigger and position job.
- `report` emits calibration artifacts.

## Development Workflow

1. Add a failing test.
2. Run the smallest relevant `pytest` target.
3. Implement the minimum code to pass.
4. Re-run the targeted tests, then the broader suite.

