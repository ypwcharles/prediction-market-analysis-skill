# Polymarket Alert Bot Runtime Live Validation

Date: 2026-04-21

Status: Temporary test validation completed. This was not a production deployment.

## Scope

This note records the temporary real-environment validation of the Polymarket alert-bot runtime:

- public HTTPS reachability through Cloudflare
- Telegram send path from runtime to a private chat
- Telegram webhook ingress back into runtime
- SQLite persistence of callback feedback
- user-visible Telegram message update after callback interaction

The environment was intentionally temporary and test-only. It used ad hoc local processes plus a temporary Cloudflare Tunnel and temporary Telegram bot configuration.

## Temporary Test Setup

- Public base URL: `https://pm-bot.ypwcharles.games`
- Public webhook path: `https://pm-bot.ypwcharles.games/telegram/webhook`
- Local runtime bind: `127.0.0.1:8080`
- Temporary runtime data dir: `/tmp/polymarket-runtime-live-data`
- Temporary SQLite path: `/tmp/polymarket-runtime-live-data/sqlite/runtime.sqlite3`
- Delivery target: Telegram private chat `6442103483`
- Tunnel model: Cloudflare Tunnel to local runtime
- Scheduler mode during validation: disabled for manual control

Secrets are intentionally omitted from this note. The bot token and webhook secret used for the validation are temporary test credentials and should not be reused as production defaults.

## What Was Verified

### 1. Runtime health over public HTTPS

- Local `GET /healthz` returned `200` on `127.0.0.1:8080`.
- Public `GET /healthz` returned `200` on `https://pm-bot.ypwcharles.games/healthz`.
- This confirmed the Cloudflare Tunnel path to the local FastAPI runtime.

### 2. Telegram send path

- Direct Telegram API send succeeded before runtime integration.
- Runtime-triggered heartbeat delivery also succeeded and persisted the Telegram message reference into SQLite.
- This confirmed that the runtime could send outbound Telegram messages with the configured bot.

### 3. Webhook registration and ingress

- Telegram webhook was registered to the public runtime webhook path.
- Runtime verified the Telegram secret header before accepting webhook payloads.
- Public webhook requests reached the runtime through Cloudflare.

### 4. Real callback persistence

- Human button clicks generated `callback_query` webhook deliveries.
- Runtime persisted callback feedback rows into SQLite.
- Final successful human validation for the temporary visible test recorded:
  - `feedback_type = seen`
  - `alert_id = 66eaf291-2635-479e-b6b3-31df46d752b1`
  - `telegram_message_id = 53`
  - `created_at = 2026-04-21T11:36:26.130963+00:00`

### 5. User-visible callback confirmation

- The original Telegram message now updates in place after clicking `已看`.
- Expected visible outcome:
  - the original message appends `反馈状态：已看`
  - the inline buttons disappear
- This behavior was confirmed by live manual testing after the runtime callback fix landed.

### 6. Local service control plane and runtime flow validation

An additional local-only validation pass was run on 2026-04-21 to exercise the non-Telegram runtime paths with a temporary mock Polymarket API and a real local FastAPI runtime service.

Temporary setup for this pass:

- mock upstream API: `http://127.0.0.1:18081`
- local runtime service: `http://127.0.0.1:18082`
- temporary runtime data dir: `/tmp/polymarket-runtime-functional-test.Ms1CmD`
- scheduler mode: disabled
- Telegram delivery: disabled

Validated endpoints and outcomes:

- `GET /status`
  - bearer auth rejected unauthenticated access
  - authenticated access returned current run and count snapshots
- `POST /internal/scan`
  - returned run `13e32829-02db-47c4-a8a0-8ebba3d6730e`
  - produced 2 strict alerts, 2 open thesis clusters, and 4 armed triggers
  - wrote strict archive files under `/tmp/polymarket-runtime-functional-test.Ms1CmD/archives/`
- `POST /internal/monitor`
  - returned run `a66b3712-9f68-40e4-9264-61f35eeca20c`
  - synced 1 official position into SQLite with `truth_source = official_api`
  - delivered 4 monitor alerts:
    - 2 price-trigger alerts from direct price checks
    - 2 narrative-trigger alerts via the LLM recheck path
- `POST /internal/report`
  - returned run `1a7846ce-4bf4-474e-aeb4-b8e852bf89ec`
  - wrote calibration report `/tmp/polymarket-runtime-functional-test.Ms1CmD/reports/calibration-a3b93904-6f8c-4d99-92f4-151dd8945a89.md`
  - persisted `status = ready_for_limited_trial`

Design-sensitive checks confirmed during this pass:

- settlement rules now reach the judgment runner
  - persisted `why_now` text included both event-level and market-level settlement language, for example:
    - `Settlement uses certified election authority result.`
    - `Resolves YES only if Candidate A is certified as winner.`
- price triggers are evaluated from live orderbook observations
  - delivered monitor alerts recorded `observation: 51.0` and `observation: 50.0`, matching the temporary mock book instead of the stored recommendation price
- narrative triggers do not bypass recheck
  - the temporary runner only approved narrative deliveries when invoked in monitor recheck mode, and the runtime produced narrative monitor alerts only through that path
- scan, monitor, and report all persisted clean run records visible through `/status`

## Live Issues Found And Fixed

### Issue 1: Non-callback Telegram updates caused webhook `500`

Problem:

- Telegram sends many update types to the same webhook URL.
- Runtime originally treated non-`callback_query` payloads as fatal and raised `unsupported callback payload`.
- That caused webhook `500` responses and retry noise.

Fix:

- `runtime/src/polymarket_alert_bot/service/app.py`
- Non-callback Telegram updates are now accepted and returned as `{"ignored": true}` with HTTP `200`.

Validation:

- Webhook stopped failing on ordinary message updates.
- Regression test added in `runtime/tests/integration/test_service_endpoints.py`.

### Issue 2: Callback success had no visible user feedback

Problem:

- Clicking `已看` wrote feedback into SQLite, but the Telegram message itself usually did not visibly change.
- For alerts without fired trigger state, the user experience looked like “nothing happened.”

Fix:

- `runtime/src/polymarket_alert_bot/delivery/callback_router.py`
- `runtime/src/polymarket_alert_bot/runtime_flow.py`
- Runtime now reads the original message text from the callback payload and, after accepting the callback, edits the original message to append a visible status line.

Validation:

- Live callback flow now updates the same Telegram message in place.
- Callback-related tests extended in:
  - `runtime/tests/unit/test_template_rendering.py`
  - `runtime/tests/integration/test_cli_operator_commands.py`

### Issue 3: Telegram rejected reply-markup clearing payload

Problem:

- Runtime initially attempted to clear the inline keyboard with `reply_markup = null`.
- Telegram returned:
  - `Bad Request: object expected as reply markup`
- This caused webhook `500` responses even though feedback had already been persisted.

Fix:

- `runtime/src/polymarket_alert_bot/delivery/telegram_client.py`
- Clearing the inline keyboard now uses `{"inline_keyboard": []}`, which Telegram accepts.

Validation:

- Runtime webhook returned `200 OK`.
- Callback feedback persisted successfully.
- The visible confirmation flow completed without webhook failure.

## Current Interpretation

- The temporary public-HTTPS path works.
- The temporary Telegram send path works.
- The temporary Telegram webhook ingress works.
- Callback persistence and user-visible callback confirmation both work.
- SQLite recorded the human callback event from the public webhook flow.

This is sufficient to treat the runtime callback design as live-validated for the tested temporary path.

## Remaining Caveats

- This was a temporary test environment, not the final service deployment model.
- The runtime and tunnel were run ad hoc, not as durable managed services.
- Telegram `getWebhookInfo` may still show an old `last_error_message` from earlier failed retries. That field is historical; the successful final callback validation is the current truth.
- The temporary Cloudflare Tunnel, DNS route, webhook registration, and bot secrets should be cleaned up or rotated after the test window closes.

## Cleanup State

At the end of this note:

- local temporary validation evidence has been written to SQLite and this document
- local temporary processes can be stopped safely
- remote cleanup for the temporary Cloudflare and Telegram resources should be done deliberately, because it is destructive to the current temporary test path
