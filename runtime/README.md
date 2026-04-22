# Polymarket Alert Bot Runtime

This directory is the real Python project for the operational runtime. If you are starting from repo root, use `bash scripts/runtime-health.sh` instead of relying on root autodetection.

## Commands

- `uv run polymarket-alert-bot serve`
- `uv run polymarket-alert-bot scan`
- `uv run polymarket-alert-bot monitor`
- `uv run polymarket-alert-bot report`
- `uv run polymarket-alert-bot callback --payload-file callback.json`
- `uv run polymarket-alert-bot promote .runtime-data/archives/strict/example.md`

## Health Checks

From repo root:

- `bash scripts/runtime-health.sh`

From `runtime/` directly:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy src`
- `uv run pytest`

## Docker Service (Single Instance)

1. From `runtime/`, copy the env template:
   - `cp .env.example .env`
2. Fill `.env` secrets, especially:
   - `POLYMARKET_ALERT_BOT_INTERNAL_BEARER_TOKEN`
   - `POLYMARKET_ALERT_BOT_TELEGRAM_WEBHOOK_SECRET`
   - `TELEGRAM_BOT_TOKEN`
3. Start the service:
   - `docker compose -f docker-compose.example.yml up --build -d`
4. Stop the service:
   - `docker compose -f docker-compose.example.yml down`

The compose file mounts a persistent named volume to `/app/.runtime-data`, so SQLite, archives, reports, and locks survive container restarts.

## Webhook and Base URL Notes

- `POLYMARKET_ALERT_BOT_BASE_URL` should be the public HTTPS base URL for callbacks and webhook registration.
- `POLYMARKET_ALERT_BOT_TELEGRAM_WEBHOOK_SECRET` is a shared secret for Telegram webhook verification; keep it private.
- `POLYMARKET_ALERT_BOT_INTERNAL_BEARER_TOKEN` is intended for internal service-to-service authorization and should be a long random token.
- Keep `POLYMARKET_ALERT_BOT_HOST=0.0.0.0` and expose `POLYMARKET_ALERT_BOT_PORT` in Docker so webhook callbacks can reach the container.

## Environment Variables

- `POLYMARKET_ALERT_BOT_DATA_DIR`
- `POLYMARKET_ALERT_BOT_DB_PATH`
- `POLYMARKET_ALERT_BOT_SOURCES_PATH`
- `POLYMARKET_ALERT_BOT_ENABLE_SCAN` (set this to `1` for real board discovery; if omitted, scan commands/service runs only record an empty dry run)
- `POLYMARKET_ALERT_BOT_GAMMA_EVENTS_URL` (default `https://gamma-api.polymarket.com/markets`, because the events feed surfaces too many stale/closed markets for live discovery)
- `POLYMARKET_ALERT_BOT_GAMMA_LIMIT`
- `POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES` (default `2`; for live real-Hermes discovery, consider temporarily lowering it to `1` to keep each scan bounded)
- `POLYMARKET_ALERT_BOT_CLOB_BOOK_URL`
- `POLYMARKET_ALERT_BOT_POSITIONS_URL`
- `POLYMARKET_ALERT_BOT_POSITIONS_USER`
- `POLYMARKET_ALERT_BOT_HOST`
- `POLYMARKET_ALERT_BOT_PORT`
- `POLYMARKET_ALERT_BOT_BASE_URL`
- `POLYMARKET_ALERT_BOT_INTERNAL_BEARER_TOKEN`
- `POLYMARKET_ALERT_BOT_TELEGRAM_WEBHOOK_SECRET`
- `POLYMARKET_ALERT_BOT_JUDGMENT_COMMAND`
- `POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD`
- `POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS` (default `600`; real Hermes judgment on live upstream markets can exceed five minutes, so the old 90s and later 300s defaults were too low)
- `POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID`
- `POLYMARKET_ALERT_BOT_TELEGRAM_MESSAGE_THREAD_ID` (optional; set this for Telegram forum topics so alerts land in the intended topic instead of the main chat)
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
4. Re-run the targeted tests, then the root health command.
