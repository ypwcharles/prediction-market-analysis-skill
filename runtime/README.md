# Polymarket Alert Bot Runtime

## Commands

- `uv run polymarket-alert-bot scan`
- `uv run polymarket-alert-bot monitor`
- `uv run polymarket-alert-bot report`
- `uv run polymarket-alert-bot callback --payload-file callback.json`
- `uv run polymarket-alert-bot promote .runtime-data/archives/strict/example.md`

## Environment Variables

- `POLYMARKET_ALERT_BOT_DATA_DIR`
- `POLYMARKET_ALERT_BOT_DB_PATH`
- `POLYMARKET_ALERT_BOT_SOURCES_PATH`
- `POLYMARKET_ALERT_BOT_GAMMA_EVENTS_URL`
- `POLYMARKET_ALERT_BOT_GAMMA_LIMIT`
- `POLYMARKET_ALERT_BOT_CLOB_BOOK_URL`
- `POLYMARKET_ALERT_BOT_POSITIONS_URL`
- `POLYMARKET_ALERT_BOT_POSITIONS_USER`
- `POLYMARKET_ALERT_BOT_JUDGMENT_COMMAND`
- `POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD`
- `POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS`
- `POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID`
- `POLYMARKET_ALERT_BOT_NEWS_FEED_URL`
- `POLYMARKET_ALERT_BOT_X_FEED_URL`
- `POLYMARKET_ALERT_BOT_NEWS_SAMPLES_PATH`
- `POLYMARKET_ALERT_BOT_X_SAMPLES_PATH`
- `TELEGRAM_BOT_TOKEN`
- `POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM`

## Evidence Feed Contract

- `POLYMARKET_ALERT_BOT_NEWS_FEED_URL` and `POLYMARKET_ALERT_BOT_X_FEED_URL` accept either:
  - local file paths
  - `file://` URLs
  - remote `https://` JSON feeds
- Expected payload shape is a JSON list of objects.
- News rows should include:
  - `source_id`
  - `url`
  - `claim_snippet`
  - optional `tier`
  - optional `conflict_status`
  - optional `fetched_at`
- X rows should include the same fields, plus a handle field such as:
  - `handle`
  - `author_handle`
  - `username`
  - or a resolvable `url`
- X feed rows are filtered against the allowlisted handles in `runtime/config/sources.toml`.
- If no live feed URL is configured, runtime falls back to the corresponding `*_SAMPLES_PATH` when provided.
- If a configured feed cannot be loaded, the scan run is marked `degraded` and high-priority alerts are downgraded to `STRICT-DEGRADED`.

## Data Paths

- SQLite: `.runtime-data/sqlite/runtime.sqlite3`
- Archives: `.runtime-data/archives/`
- Reports: `.runtime-data/reports/`
- Locks: `.runtime-data/locks/`

## Scheduler Contract

- `scan` is the slow discovery job.
- `monitor` is the fast trigger and position job.
- `report` emits calibration artifacts.
- `callback` writes Telegram button feedback into SQLite and applies state transitions.
- `promote` manually copies a private archive artifact into `docs/market-analysis/`.

## Delivery Contract

- `STRICT` and high-value `REPRICE` alerts render long memos with claim-aware citations and direct market links when slugs are available.
- `RESEARCH` alerts are batched into a digest.
- `MONITOR` alerts are sparse and action-oriented; narrative triggers route through the judgment runner before delivery.
- `HEARTBEAT` fires when no strict alert is found and records coverage/system status.

## Development Workflow

1. Add a failing test.
2. Run the smallest relevant `pytest` target.
3. Implement the minimum code to pass.
4. Re-run the targeted tests, then the broader suite.
