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
- `POLYMARKET_ALERT_BOT_EXTERNAL_ANCHOR_FEED_URL`
- `POLYMARKET_ALERT_BOT_EXTERNAL_ANCHOR_SAMPLES_PATH`
- `POLYMARKET_ALERT_BOT_EXTERNAL_ANCHOR_MIN_GAP_CENTS` (default `5`; candidates only earn the `anchor_gap` scan sleeve when the absolute gap meets or exceeds this threshold)
- `TELEGRAM_BOT_TOKEN`
- `POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM`

## Scan Discovery Behavior

When `POLYMARKET_ALERT_BOT_ENABLE_SCAN=1`, `scan` no longer acts as a single hot-board sampler. It builds a multi-sleeve discovery universe before spending judgment budget:

- `hot_board` from high-volume Gamma markets
- `short_dated` from near-deadline Gamma markets
- `newly_listed` from recently created Gamma markets
- `family_inconsistency` when same-event family or price-surface checks flag structural issues
- `anchor_gap` when configured external-anchor data disagrees with the executable market price by at least `POLYMARKET_ALERT_BOT_EXTERNAL_ANCHOR_MIN_GAP_CENTS`

The scanner records per-sleeve input, shortlist, and promoted counts in the `runs` table and heartbeat artifacts. Ranking favors conservative executable edge signals, including family structure, catalyst proximity, fill quality, uniqueness, external-anchor gap, crowding penalties, overlap penalties, and category execution haircuts. The judgment budget is still bounded by `POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES`.

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

Evidence rows may include optional claim-graph fields:

- `claim_slot`, such as `settlement_claim`, `timing_gate`, `counter_claim`, or `external_anchor`
- `claim_key`, a normalized identifier for the underlying claim

When those fields are absent, the runtime infers claim slots and keys from the snippet, source kind, and URL. Strict promotion depends on independent corroboration of underlying claims rather than duplicated copies of the same report.

## Semantic Relevance Runner Contract

When `POLYMARKET_ALERT_BOT_SEMANTIC_RELEVANCE_ENABLED=1`, the runtime sends evidence to the configured semantic relevance runner with `contract_version="semantic_relevance.v2"`.

Runner responses may return `decisions`, `items`, or `evidence` arrays. Each decision can target a source with `source_id`, `url`, or `url + claim_snippet`. A decision that only contains `claim_key` is source-scoped by default and will not be applied across every source sharing that claim key.

To apply a decision across all evidence rows for the same underlying claim, the runner must explicitly mark it as claim-level with one of:

- `scope: "claim"`
- `decision_scope: "claim"` / `decision_scope: "claim_key"` / `decision_scope: "claim_level"` / `decision_scope: "cross_source_claim"`
- `claim_level: true`

This keeps one weak or irrelevant source from deleting independent corroboration for the same claim. Prefer exact `source_id` or `url` decisions when the model is judging a specific article or post; use claim-level decisions only when the underlying claim itself is settlement-irrelevant or conflicting across every source.

## External Anchor Contract

External anchors are optional configured rows that represent non-Polymarket fair-value references, such as another venue, model, bookmaker, or curated operator feed. Configure one of:

- `POLYMARKET_ALERT_BOT_EXTERNAL_ANCHOR_FEED_URL`
- `POLYMARKET_ALERT_BOT_EXTERNAL_ANCHOR_SAMPLES_PATH`

Expected payload shape is a JSON list of objects. A row must include one probability field and at least one market identity field.

Supported probability fields:

- `external_anchor_cents`
- `external_probability_cents`
- `external_fair_cents`
- `anchor_cents`
- `anchor_probability_cents`
- `probability_cents`
- `fair_cents`

Supported market identity fields include:

- `condition_id`
- `market_id`
- `token_id`
- `expression_key`
- `event_slug` plus `market_slug`

Optional provenance fields include `source_id` and `url`. If a configured external-anchor feed cannot be loaded, the scan is marked `degraded`; it is not silently treated as a clean no-anchor run. Runtime payloads keep `external_anchor_cents` separate from internally inferred fair value, so reports can distinguish market price, external anchor, rule-adjusted payout probability, and execution-adjusted fair entry.

## Report Scorecard

`uv run polymarket-alert-bot report` writes a markdown report under `.runtime-data/reports/` and inserts a row into `calibration_reports`. In addition to the original high-priority alert and review-window scorecard, reports now include:

- `Discovery Health`: scan run count, degraded scan rate, latest scan events/contracts/shortlist/promoted, total scanned/shortlisted/promoted counts, structural-flag families/candidates, strict/research/skipped totals, retrieved shortlist count, and sleeve input/shortlist/promoted totals.
- `Operator Trust Signals`: stale alerts, total feedback events, claimed-buy feedback, disagree feedback as a false-positive proxy, close-thesis feedback, and average feedback latency.

The report is read-only over existing SQLite artifacts. It does not rerun scan, monitor, or live upstream fetches.

## Alert Artifact Semantics

Strict and research artifacts expose richer scan context:

- family summaries and structural flags explain why a contract was selected relative to nearby expressions
- ranking summaries list the positive and negative contributors used before judgment
- anchor stacks keep market price, external anchor, rule-adjusted payout probability, execution-adjusted fair entry, and edge layers separate
- citations render claim-aware support instead of a flat source dump

Treat `external_anchor_cents` as real external data only when configured anchor rows supplied it. Internal model or rule-adjusted fair value must remain in the rule/fair-entry layers, not in the external-anchor layer.

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
