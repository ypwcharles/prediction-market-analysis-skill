# Polymarket Alert Bot Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable Polymarket alert-bot runtime inside this repo, with scheduled scanning, Telegram delivery, action-oriented monitoring, SQLite state, calibration reporting, and archive support, while keeping `skills/prediction-market-analysis/` as a pure judgment engine.

**Architecture:** The runtime lives under a dedicated `runtime/` subtree and is `Python-first`. Two scheduled jobs share one SQLite database and one private gitignored runtime-data layer: `scan` handles board discovery, evidence gathering, judgment routing, and alert generation; `monitor` handles trigger evaluation, stale/recheck logic, position reconciliation, and follow-up action alerts. Human-readable high-value artifacts are archived privately, while promoted public notes remain separate in `docs/market-analysis/`.

**Tech Stack:** Python 3.12+, `uv`, `pytest`, `httpx`, `pydantic`, stdlib `sqlite3`, stdlib `argparse`, Telegram Bot API, Polymarket official API, Gamma API, CLOB book endpoints.

---

## File Structure

### Create

- `runtime/pyproject.toml`
- `runtime/README.md`
- `runtime/src/polymarket_alert_bot/__init__.py`
- `runtime/src/polymarket_alert_bot/cli.py`
- `runtime/src/polymarket_alert_bot/config/__init__.py`
- `runtime/src/polymarket_alert_bot/config/settings.py`
- `runtime/src/polymarket_alert_bot/config/source_registry.py`
- `runtime/src/polymarket_alert_bot/models/__init__.py`
- `runtime/src/polymarket_alert_bot/models/enums.py`
- `runtime/src/polymarket_alert_bot/models/records.py`
- `runtime/src/polymarket_alert_bot/storage/__init__.py`
- `runtime/src/polymarket_alert_bot/storage/db.py`
- `runtime/src/polymarket_alert_bot/storage/migrations.py`
- `runtime/src/polymarket_alert_bot/storage/repositories.py`
- `runtime/src/polymarket_alert_bot/storage/locks.py`
- `runtime/src/polymarket_alert_bot/scanner/__init__.py`
- `runtime/src/polymarket_alert_bot/scanner/gamma_client.py`
- `runtime/src/polymarket_alert_bot/scanner/clob_client.py`
- `runtime/src/polymarket_alert_bot/scanner/normalizer.py`
- `runtime/src/polymarket_alert_bot/scanner/board_scan.py`
- `runtime/src/polymarket_alert_bot/sources/__init__.py`
- `runtime/src/polymarket_alert_bot/sources/news_client.py`
- `runtime/src/polymarket_alert_bot/sources/x_client.py`
- `runtime/src/polymarket_alert_bot/sources/evidence_enricher.py`
- `runtime/src/polymarket_alert_bot/judgment/__init__.py`
- `runtime/src/polymarket_alert_bot/judgment/context_builder.py`
- `runtime/src/polymarket_alert_bot/judgment/skill_adapter.py`
- `runtime/src/polymarket_alert_bot/judgment/result_parser.py`
- `runtime/src/polymarket_alert_bot/templates/__init__.py`
- `runtime/src/polymarket_alert_bot/templates/strict_memo.py`
- `runtime/src/polymarket_alert_bot/templates/research_digest.py`
- `runtime/src/polymarket_alert_bot/templates/monitor_alert.py`
- `runtime/src/polymarket_alert_bot/templates/heartbeat.py`
- `runtime/src/polymarket_alert_bot/delivery/__init__.py`
- `runtime/src/polymarket_alert_bot/delivery/telegram_client.py`
- `runtime/src/polymarket_alert_bot/delivery/callback_router.py`
- `runtime/src/polymarket_alert_bot/monitor/__init__.py`
- `runtime/src/polymarket_alert_bot/monitor/position_sync.py`
- `runtime/src/polymarket_alert_bot/monitor/trigger_engine.py`
- `runtime/src/polymarket_alert_bot/monitor/staleness.py`
- `runtime/src/polymarket_alert_bot/calibration/__init__.py`
- `runtime/src/polymarket_alert_bot/calibration/metrics.py`
- `runtime/src/polymarket_alert_bot/calibration/report_writer.py`
- `runtime/src/polymarket_alert_bot/archive/__init__.py`
- `runtime/src/polymarket_alert_bot/archive/writer.py`
- `runtime/src/polymarket_alert_bot/archive/promote.py`
- `runtime/tests/conftest.py`
- `runtime/tests/fixtures/__init__.py`
- `runtime/tests/fixtures/gamma_board.json`
- `runtime/tests/fixtures/clob_books.json`
- `runtime/tests/fixtures/polymarket_positions.json`
- `runtime/tests/fixtures/news_samples.json`
- `runtime/tests/fixtures/x_samples.json`
- `runtime/tests/unit/test_source_registry.py`
- `runtime/tests/unit/test_storage_schema.py`
- `runtime/tests/unit/test_trigger_lifecycle.py`
- `runtime/tests/unit/test_ttl_expiry.py`
- `runtime/tests/unit/test_template_rendering.py`
- `runtime/tests/integration/test_scan_pipeline.py`
- `runtime/tests/integration/test_monitor_pipeline.py`
- `runtime/tests/integration/test_callback_reconciliation.py`
- `runtime/tests/integration/test_calibration_report.py`
- `runtime/tests/snapshots/strict_memo.txt`
- `runtime/tests/snapshots/research_digest.txt`
- `runtime/tests/snapshots/monitor_alert.txt`
- `runtime/tests/snapshots/heartbeat.txt`

### Modify

- `.gitignore`
- `docs/README.md`
- `docs/superpowers/plans/2026-04-17-polymarket-alert-bot-runtime-implementation.md`

### Runtime Tree

```text
runtime/
  pyproject.toml
  README.md
  src/polymarket_alert_bot/
    __init__.py
    cli.py
    config/
      __init__.py
      settings.py
      source_registry.py
    models/
      __init__.py
      enums.py
      records.py
    storage/
      __init__.py
      db.py
      migrations.py
      repositories.py
      locks.py
    scanner/
      __init__.py
      gamma_client.py
      clob_client.py
      normalizer.py
      board_scan.py
    sources/
      __init__.py
      news_client.py
      x_client.py
      evidence_enricher.py
    judgment/
      __init__.py
      context_builder.py
      skill_adapter.py
      result_parser.py
    templates/
      __init__.py
      strict_memo.py
      research_digest.py
      monitor_alert.py
      heartbeat.py
    delivery/
      __init__.py
      telegram_client.py
      callback_router.py
    monitor/
      __init__.py
      position_sync.py
      trigger_engine.py
      staleness.py
    calibration/
      __init__.py
      metrics.py
      report_writer.py
    archive/
      __init__.py
      writer.py
      promote.py
  tests/
    conftest.py
    fixtures/
    unit/
    integration/
    snapshots/

.runtime-data/          # repo root, gitignored
  sqlite/
  archives/
  reports/
  locks/
```

### Responsibility Map

- `runtime/src/polymarket_alert_bot/cli.py`
  Single CLI entrypoint with subcommands for `scan`, `monitor`, and `report`.
- `config/`
  Repo-versioned runtime settings and source registry loading.
- `models/`
  Shared enums and typed record shapes for rows, payloads, and render inputs.
- `storage/`
  SQLite connection, schema migrations, row repositories, and lock handling.
- `scanner/`
  Gamma discovery, CLOB executable checks, board normalization, and factual filtering.
- `sources/`
  News and X fetchers plus evidence enrichment and source-tier tagging.
- `judgment/`
  Adapts runtime candidates into the existing skill/prompt contract and parses structured output back.
- `templates/`
  Canonical Telegram renderers for `STRICT`, `RESEARCH`, `MONITOR`, and `HEARTBEAT/DEGRADED`.
- `delivery/`
  Telegram send/edit/button handling and callback event translation.
- `monitor/`
  Position sync, structured trigger evaluation, stale/recheck logic, and action escalation.
- `calibration/`
  Metrics rollups plus markdown/SQLite calibration report output.
- `archive/`
  Private high-value artifact persistence and optional manual promotion helper into `docs/market-analysis/`.

## SQLite Schema

### Principles

- One `SQLite` file is the runtime truth source.
- Schema stays narrow and operational. No analytics vanity tables.
- Telegram feedback is an intent layer. Polymarket official API remains position truth.
- `thesis_cluster_id` is the memory primary key. `market_id` and `token_id` are expression-level identifiers.

### Table: `runs`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | ULID or UUID |
| `run_type` | TEXT NOT NULL | `scan`, `monitor`, `report` |
| `status` | TEXT NOT NULL | `running`, `clean`, `degraded`, `failed` |
| `started_at` | TEXT NOT NULL | ISO timestamp |
| `finished_at` | TEXT | ISO timestamp |
| `degraded_reason` | TEXT | nullable |
| `scanned_events` | INTEGER DEFAULT 0 | main scan only |
| `scanned_contracts` | INTEGER DEFAULT 0 | main scan only |
| `strict_count` | INTEGER DEFAULT 0 | generated this run |
| `research_count` | INTEGER DEFAULT 0 | generated this run |
| `skipped_count` | INTEGER DEFAULT 0 | rejected/skipped count |
| `heartbeat_sent` | INTEGER DEFAULT 0 | boolean as 0/1 |
| `created_at` | TEXT NOT NULL | ISO timestamp |

### Table: `thesis_clusters`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | stable cluster id |
| `canonical_name` | TEXT NOT NULL | human-facing thesis name |
| `status` | TEXT NOT NULL | `open`, `closed`, `stale`, `pending_recheck` |
| `cluster_version` | INTEGER NOT NULL DEFAULT 1 | bump on merge/split |
| `cluster_reason` | TEXT | why this grouping exists |
| `closed_reason` | TEXT | nullable |
| `closed_at` | TEXT | nullable |
| `reopen_reason` | TEXT | nullable |
| `last_alert_id` | TEXT | nullable |
| `created_at` | TEXT NOT NULL | ISO timestamp |
| `updated_at` | TEXT NOT NULL | ISO timestamp |

### Table: `cluster_expressions`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | row id |
| `thesis_cluster_id` | TEXT NOT NULL | FK to `thesis_clusters.id` |
| `event_id` | TEXT | Polymarket event id |
| `market_id` | TEXT | Polymarket market id |
| `token_id` | TEXT | CLOB token id |
| `event_slug` | TEXT | nullable |
| `market_slug` | TEXT | nullable |
| `expression_label` | TEXT | human summary of this expression |
| `is_primary_expression` | INTEGER DEFAULT 0 | 0/1 |
| `first_seen_at` | TEXT NOT NULL | ISO timestamp |
| `last_seen_at` | TEXT NOT NULL | ISO timestamp |

### Table: `alerts`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | alert id |
| `run_id` | TEXT NOT NULL | FK to `runs.id` |
| `thesis_cluster_id` | TEXT | nullable for pure heartbeat |
| `event_id` | TEXT | nullable |
| `market_id` | TEXT | nullable |
| `token_id` | TEXT | nullable |
| `alert_kind` | TEXT NOT NULL | `strict`, `strict_degraded`, `research`, `reprice`, `monitor`, `heartbeat`, `degraded` |
| `delivery_mode` | TEXT NOT NULL | `immediate`, `digest` |
| `side` | TEXT | `YES`, `NO`, outcome label, or null |
| `theoretical_edge_cents` | REAL | nullable |
| `executable_edge_cents` | REAL | nullable |
| `spread_bps` | REAL | nullable |
| `slippage_bps` | REAL | nullable |
| `max_entry_cents` | REAL | nullable |
| `suggested_size_usdc` | REAL | nullable |
| `why_now` | TEXT | nullable |
| `kill_criteria_text` | TEXT | nullable |
| `evidence_fresh_until` | TEXT | nullable |
| `recheck_required_at` | TEXT | nullable |
| `status` | TEXT NOT NULL | `active`, `stale`, `closed`, `superseded` |
| `telegram_chat_id` | TEXT | nullable |
| `telegram_message_id` | TEXT | nullable |
| `archive_path` | TEXT | nullable |
| `dedupe_key` | TEXT NOT NULL | unique-ish semantic dedupe key |
| `created_at` | TEXT NOT NULL | ISO timestamp |

### Table: `sources`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | source id |
| `source_name` | TEXT NOT NULL | display name |
| `source_kind` | TEXT NOT NULL | `official`, `platform`, `news`, `x`, `unknown` |
| `source_tier` | TEXT NOT NULL | layered registry tier |
| `domain_or_handle` | TEXT NOT NULL | domain or `@handle` |
| `is_primary_allowed` | INTEGER NOT NULL DEFAULT 0 | 0/1 |
| `is_active` | INTEGER NOT NULL DEFAULT 1 | 0/1 |
| `config_version` | TEXT NOT NULL | source-registry version string |
| `created_at` | TEXT NOT NULL | ISO timestamp |
| `updated_at` | TEXT NOT NULL | ISO timestamp |

### Table: `claim_source_mappings`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | row id |
| `alert_id` | TEXT NOT NULL | FK to `alerts.id` |
| `thesis_cluster_id` | TEXT NOT NULL | FK to `thesis_clusters.id` |
| `claim_type` | TEXT NOT NULL | `rules`, `why_now`, `kill_criteria`, `conflict_resolution`, `primary_evidence` |
| `claim_text` | TEXT NOT NULL | exact runtime claim text |
| `source_id` | TEXT NOT NULL | FK to `sources.id` |
| `url` | TEXT NOT NULL | evidence URL |
| `fetched_at` | TEXT NOT NULL | ISO timestamp |
| `conflict_status` | TEXT NOT NULL DEFAULT 'active' | `active`, `conflicted`, `superseded` |
| `superseded_by_mapping_id` | TEXT | self-FK nullable |

### Table: `triggers`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | trigger id |
| `thesis_cluster_id` | TEXT NOT NULL | FK to `thesis_clusters.id` |
| `alert_id` | TEXT NOT NULL | originating alert |
| `trigger_type` | TEXT NOT NULL | e.g. `price_threshold`, `kill_hit`, `edge_decay`, `reprice_zone` |
| `threshold_kind` | TEXT NOT NULL | `price`, `edge`, `spread`, `ttl`, `evidence`, `position` |
| `comparison` | TEXT NOT NULL | `<`, `<=`, `>`, `>=`, `eq`, `state_change` |
| `threshold_value` | TEXT NOT NULL | serialized simple value |
| `suggested_action` | TEXT NOT NULL | `watch`, `add`, `reduce`, `exit`, `recheck` |
| `requires_llm_recheck` | INTEGER NOT NULL DEFAULT 0 | 0/1 |
| `human_note` | TEXT | nullable |
| `state` | TEXT NOT NULL | `armed`, `fired`, `acknowledged`, `snoozed`, `rearmed`, `closed` |
| `cooldown_until` | TEXT | nullable |
| `last_fired_at` | TEXT | nullable |
| `created_at` | TEXT NOT NULL | ISO timestamp |
| `updated_at` | TEXT NOT NULL | ISO timestamp |

### Table: `feedback`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | feedback id |
| `alert_id` | TEXT NOT NULL | FK to `alerts.id` |
| `thesis_cluster_id` | TEXT NOT NULL | FK to `thesis_clusters.id` |
| `feedback_type` | TEXT NOT NULL | `seen`, `snooze`, `claimed_buy`, `disagree`, `close_thesis` |
| `payload_json` | TEXT | serialized callback payload |
| `telegram_chat_id` | TEXT | nullable |
| `telegram_message_id` | TEXT | nullable |
| `created_at` | TEXT NOT NULL | ISO timestamp |

### Table: `positions`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | local row id |
| `condition_id` | TEXT NOT NULL | Polymarket condition id |
| `token_id` | TEXT NOT NULL | token id |
| `market_id` | TEXT | nullable |
| `thesis_cluster_id` | TEXT | nullable |
| `side` | TEXT NOT NULL | `YES`, `NO`, outcome label |
| `size_shares` | REAL NOT NULL | current open size |
| `avg_entry_cents` | REAL | nullable |
| `status` | TEXT NOT NULL | `open`, `closed`, `claimed_only` |
| `truth_source` | TEXT NOT NULL | `official_api`, `telegram_claim` |
| `snapshot_as_of` | TEXT NOT NULL | ISO timestamp |
| `updated_at` | TEXT NOT NULL | ISO timestamp |

## Task 1: Scaffold the Runtime Package

**Files:**
- Create: `runtime/pyproject.toml`
- Create: `runtime/README.md`
- Create: `runtime/src/polymarket_alert_bot/__init__.py`
- Create: `runtime/src/polymarket_alert_bot/cli.py`
- Modify: `.gitignore`

- [x] **Step 1: Create the runtime directory tree**

Run:
```bash
mkdir -p runtime/src/polymarket_alert_bot runtime/tests/{fixtures,unit,integration,snapshots}
mkdir -p .runtime-data/{sqlite,archives,reports,locks}
```
Expected: `runtime/` and `.runtime-data/` directories exist at repo root.

- [x] **Step 2: Add runtime ignore rules**

Append to `.gitignore`:
```gitignore
.runtime-data/
runtime/.venv/
runtime/.pytest_cache/
runtime/.mypy_cache/
runtime/.ruff_cache/
```

- [x] **Step 3: Write `runtime/pyproject.toml`**

Create:
```toml
[project]
name = "polymarket-alert-bot"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.27.0",
  "pydantic>=2.7.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "pytest-cov>=5.0.0",
]

[project.scripts]
polymarket-alert-bot = "polymarket_alert_bot.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [x] **Step 4: Write the runtime README**

Create `runtime/README.md` with sections:
```markdown
# Polymarket Alert Bot Runtime

## Commands
## Environment Variables
## Data Paths
## Scheduler Contract
## Development Workflow
```

- [x] **Step 5: Write the CLI skeleton**

Create `runtime/src/polymarket_alert_bot/cli.py` with:
```python
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="polymarket-alert-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan")
    subparsers.add_parser("monitor")
    subparsers.add_parser("report")
    args = parser.parse_args()
    raise SystemExit(f"not implemented: {args.command}")


if __name__ == "__main__":
    main()
```

- [x] **Step 6: Verify the package boots**

Run:
```bash
cd runtime && uv run polymarket-alert-bot scan
```
Expected: exits non-zero with `not implemented: scan`.

## Task 2: Add Versioned Config and Source Registry

**Files:**
- Create: `runtime/src/polymarket_alert_bot/config/settings.py`
- Create: `runtime/src/polymarket_alert_bot/config/source_registry.py`
- Create: `runtime/config/sources.toml`
- Create: `runtime/tests/unit/test_source_registry.py`

- [x] **Step 1: Write the failing source-registry test**

Create:
```python
from polymarket_alert_bot.config.source_registry import load_source_registry


def test_load_source_registry_marks_primary_sources():
    registry = load_source_registry("runtime/config/sources.toml")
    assert "reuters.com" in registry.primary_domains
    assert "@polymarket" in registry.x_handles
```

- [x] **Step 2: Write the initial source registry config**

Create `runtime/config/sources.toml` with:
```toml
version = "v1"

[tiers]
primary = ["official", "platform", "news"]
supplementary = ["x"]

[[sources]]
name = "Polymarket"
kind = "platform"
domain_or_handle = "polymarket.com"
is_primary_allowed = true

[[sources]]
name = "Reuters"
kind = "news"
domain_or_handle = "reuters.com"
is_primary_allowed = true

[[sources]]
name = "Associated Press"
kind = "news"
domain_or_handle = "apnews.com"
is_primary_allowed = true

[[sources]]
name = "Polymarket X"
kind = "x"
domain_or_handle = "@polymarket"
is_primary_allowed = false
```

- [x] **Step 3: Implement the loader**

Create `source_registry.py` with a loader that returns:
- primary domains
- X handles
- tier metadata
- version string

- [x] **Step 4: Run the unit test**

Run:
```bash
cd runtime && uv run pytest tests/unit/test_source_registry.py -q
```
Expected: `1 passed`.

## Task 3: Build SQLite Schema and Repositories

**Files:**
- Create: `runtime/src/polymarket_alert_bot/storage/db.py`
- Create: `runtime/src/polymarket_alert_bot/storage/migrations.py`
- Create: `runtime/src/polymarket_alert_bot/storage/repositories.py`
- Create: `runtime/src/polymarket_alert_bot/storage/locks.py`
- Create: `runtime/tests/unit/test_storage_schema.py`

- [x] **Step 1: Write the failing schema test**

Create:
```python
from polymarket_alert_bot.storage.db import connect_db
from polymarket_alert_bot.storage.migrations import apply_migrations


def test_schema_creates_expected_tables(tmp_path):
    db_path = tmp_path / "runtime.sqlite3"
    conn = connect_db(db_path)
    apply_migrations(conn)
    rows = conn.execute(
        "select name from sqlite_master where type='table'"
    ).fetchall()
    names = {row[0] for row in rows}
    assert {"runs", "alerts", "thesis_clusters", "triggers", "feedback", "positions", "sources", "claim_source_mappings"} <= names
```

- [x] **Step 2: Implement database connection helper**

Use stdlib `sqlite3`, WAL mode, row factory, and foreign keys on.

- [x] **Step 3: Implement first migration**

Create all tables described in the schema section above.

- [x] **Step 4: Add repository helpers**

Implement narrow repository methods for:
- upserting runs
- inserting alerts
- upserting thesis clusters
- upserting sources
- inserting claim mappings
- updating trigger state
- replacing positions from official sync

- [x] **Step 5: Add SQLite lock helper**

Create a filesystem lock under `.runtime-data/locks/` for `scan.lock` and `monitor.lock`.

- [x] **Step 6: Run storage tests**

Run:
```bash
cd runtime && uv run pytest tests/unit/test_storage_schema.py -q
```
Expected: `1 passed`.

## Task 4: Implement Board Scan and Normalization

**Files:**
- Create: `runtime/src/polymarket_alert_bot/scanner/gamma_client.py`
- Create: `runtime/src/polymarket_alert_bot/scanner/clob_client.py`
- Create: `runtime/src/polymarket_alert_bot/scanner/normalizer.py`
- Create: `runtime/src/polymarket_alert_bot/scanner/board_scan.py`
- Create: `runtime/tests/integration/test_scan_pipeline.py`
- Create: `runtime/tests/fixtures/gamma_board.json`
- Create: `runtime/tests/fixtures/clob_books.json`

- [x] **Step 1: Write the failing scan integration test**

The test should replay:
- one tradable strict candidate
- one low-liquidity reject
- one duplicate expression
- one degraded executable-check path

- [x] **Step 2: Implement `gamma_client.py`**

Requirements:
- browser-like user agent
- timeout handling
- normalized event/market extraction

- [x] **Step 3: Implement `clob_client.py`**

Requirements:
- token-book lookup
- spread/slippage snapshot fields
- graceful degraded return when book missing

- [x] **Step 4: Implement `normalizer.py`**

Convert raw board payload into typed candidate records with:
- event id
- market id
- token id
- slugs
- liquidity/spread facts
- expression summary

- [x] **Step 5: Implement `board_scan.py`**

Factual prefilter only:
- active/open status
- basic liquidity/spread rules
- duplicate-expression grouping
- coverage accounting counters

- [x] **Step 6: Run the integration scan test**

Run:
```bash
cd runtime && uv run pytest tests/integration/test_scan_pipeline.py -q
```
Expected: `1 passed`.

## Task 5: Implement Evidence Enrichment and Judgment Adapter

**Files:**
- Create: `runtime/src/polymarket_alert_bot/sources/news_client.py`
- Create: `runtime/src/polymarket_alert_bot/sources/x_client.py`
- Create: `runtime/src/polymarket_alert_bot/sources/evidence_enricher.py`
- Create: `runtime/src/polymarket_alert_bot/judgment/context_builder.py`
- Create: `runtime/src/polymarket_alert_bot/judgment/skill_adapter.py`
- Create: `runtime/src/polymarket_alert_bot/judgment/result_parser.py`

- [x] **Step 1: Write a failing parser test for strict/research/degraded outputs**

The parser test must cover:
- `strict`
- `strict_degraded`
- `research`
- malformed payload rejection

- [x] **Step 2: Implement evidence clients**

`news_client.py` and `x_client.py` should return normalized source items with:
- source id
- tier
- fetched time
- URL
- claim snippet

- [x] **Step 3: Implement `evidence_enricher.py`**

Apply source registry rules:
- unknown sources cannot independently support `STRICT`
- unresolved primary conflict blocks `STRICT`
- `X` is supplementary by default

- [x] **Step 4: Implement `context_builder.py`**

Build a structured judgment payload containing:
- candidate facts
- rules text
- executable fields
- evidence items
- prior cluster state
- position context

- [x] **Step 5: Implement `skill_adapter.py`**

This file must define the runtime contract to the existing skill:
- input payload format
- expected structured response format
- timeout and parse failure behavior

- [x] **Step 6: Implement `result_parser.py`**

Normalize the judgment result into:
- alert kind
- cluster action
- TTL fields
- citations
- triggers
- archive payload

- [x] **Step 7: Run parser tests**

Run:
```bash
cd runtime && uv run pytest tests/unit/test_result_parser.py -q
```
Expected: `1 passed`.

## Task 6: Implement Telegram Templates and Delivery

**Files:**
- Create: `runtime/src/polymarket_alert_bot/templates/strict_memo.py`
- Create: `runtime/src/polymarket_alert_bot/templates/research_digest.py`
- Create: `runtime/src/polymarket_alert_bot/templates/monitor_alert.py`
- Create: `runtime/src/polymarket_alert_bot/templates/heartbeat.py`
- Create: `runtime/src/polymarket_alert_bot/delivery/telegram_client.py`
- Create: `runtime/src/polymarket_alert_bot/delivery/callback_router.py`
- Create: `runtime/tests/unit/test_template_rendering.py`
- Create: `runtime/tests/snapshots/*.txt`

- [x] **Step 1: Write failing snapshot tests for all four templates**

The templates must cover:
- `STRICT / STRICT-DEGRADED`
- `RESEARCH`
- `MONITOR`
- `HEARTBEAT / DEGRADED`

- [x] **Step 2: Implement canonical template renderers**

Rules:
- `STRICT` and high-value `REPRICE` are long memos
- `RESEARCH`, `MONITOR`, `HEARTBEAT` are short
- citations must be claim-aware, not just source dumps

- [x] **Step 3: Implement Telegram client**

Support:
- send message
- edit message
- inline keyboard
- callback answer

- [x] **Step 4: Implement callback router**

Map buttons to feedback actions:
- `已看`
- `稍后提醒`
- `已下单`
- `不认同`
- `关闭 thesis`

- [x] **Step 5: Run template tests**

Run:
```bash
cd runtime && uv run pytest tests/unit/test_template_rendering.py -q
```
Expected: snapshots pass.

## Task 7: Implement Monitor, Position Reconciliation, and Trigger Lifecycle

**Files:**
- Create: `runtime/src/polymarket_alert_bot/monitor/position_sync.py`
- Create: `runtime/src/polymarket_alert_bot/monitor/trigger_engine.py`
- Create: `runtime/src/polymarket_alert_bot/monitor/staleness.py`
- Create: `runtime/tests/unit/test_trigger_lifecycle.py`
- Create: `runtime/tests/unit/test_ttl_expiry.py`
- Create: `runtime/tests/integration/test_monitor_pipeline.py`
- Create: `runtime/tests/integration/test_callback_reconciliation.py`
- Create: `runtime/tests/fixtures/polymarket_positions.json`

- [x] **Step 1: Write failing trigger lifecycle tests**

Cover:
- `armed -> fired`
- `fired -> acknowledged`
- `fired -> snoozed`
- `snoozed -> rearmed`
- `close thesis`
- stale memo transition

- [x] **Step 2: Implement `position_sync.py`**

Rules:
- Polymarket official API is truth
- Telegram claim is intent only
- reconciliation updates `positions.status` and related cluster context

- [x] **Step 3: Implement `trigger_engine.py`**

Split:
- mechanical triggers
- narrative triggers requiring LLM recheck

- [x] **Step 4: Implement `staleness.py`**

Rules:
- expired memo becomes `stale / pending_recheck`
- monitor stops issuing direct action from stale memo

- [x] **Step 5: Run monitor tests**

Run:
```bash
cd runtime && uv run pytest tests/unit/test_trigger_lifecycle.py tests/unit/test_ttl_expiry.py tests/integration/test_monitor_pipeline.py tests/integration/test_callback_reconciliation.py -q
```
Expected: all pass.

## Task 8: Implement Calibration Reporting and Archive Writing

**Files:**
- Create: `runtime/src/polymarket_alert_bot/calibration/metrics.py`
- Create: `runtime/src/polymarket_alert_bot/calibration/report_writer.py`
- Create: `runtime/src/polymarket_alert_bot/archive/writer.py`
- Create: `runtime/src/polymarket_alert_bot/archive/promote.py`
- Create: `runtime/tests/integration/test_calibration_report.py`

- [x] **Step 1: Write failing calibration report tests**

The report test must verify:
- markdown report exists
- SQLite summary rows exist
- status is one of:
  - `not_ready`
  - `ready_for_limited_trial`
  - `ready_for_production`

- [x] **Step 2: Implement archive writer**

Only write:
- `STRICT` memos
- high-value `REPRICE` memos
- heartbeat summaries

- [x] **Step 3: Implement report metrics**

Must include:
- current quality scorecard
- ex-post short/medium/long review buckets
- cluster coverage
- repeated-cluster sample discounting

- [x] **Step 4: Implement report writer**

Write:
- markdown file under `.runtime-data/reports/`
- SQLite summary rows

- [x] **Step 5: Implement manual promote helper**

This helper should copy a selected archive artifact into `docs/market-analysis/` only on explicit operator request.

- [x] **Step 6: Run calibration tests**

Run:
```bash
cd runtime && uv run pytest tests/integration/test_calibration_report.py -q
```
Expected: `1 passed`.

## Task 9: Wire End-to-End Commands and Final Verification

**Files:**
- Modify: `runtime/src/polymarket_alert_bot/cli.py`
- Modify: `runtime/README.md`
- Modify: `docs/README.md`

- [x] **Step 1: Connect `scan`, `monitor`, and `report` subcommands**

Each subcommand should call exactly one orchestrator path and exit with explicit status codes.

- [x] **Step 2: Add command examples to `runtime/README.md`**

Document:
```bash
uv run polymarket-alert-bot scan
uv run polymarket-alert-bot monitor
uv run polymarket-alert-bot report
```

- [x] **Step 3: Update `docs/README.md`**

Add one line pointing to this plan and clarifying that runtime archives are private and gitignored.

- [x] **Step 4: Run the full runtime test suite**

Run:
```bash
cd runtime && uv run pytest
```
Expected: all unit, integration, and snapshot tests pass.

- [x] **Step 5: Run one dry-run scan and one dry-run monitor**

Run:
```bash
cd runtime && uv run polymarket-alert-bot scan
cd runtime && uv run polymarket-alert-bot monitor
```
Expected:
- no uncaught exception
- SQLite file created under `.runtime-data/sqlite/`
- at least one run row written
- telegram delivery path can be disabled or mocked via env

- [ ] **Step 6: Commit**

```bash
git add runtime docs/README.md .gitignore docs/superpowers/plans/2026-04-17-polymarket-alert-bot-runtime-implementation.md
git commit -m "feat: scaffold polymarket alert bot runtime"
```

## Spec Coverage

Covered in this plan:

- dedicated `runtime/` subtree
- Python-first single-package runtime
- separate `scan` and `monitor` jobs
- SQLite operational schema
- source registry
- strict/research/degraded routing
- Telegram templates and buttons
- trigger lifecycle
- position reconciliation
- calibration report
- private archive layer

Explicitly not covered in code implementation for this round:

- auto-execution
- dashboard
- automatic public promotion into `docs/market-analysis/`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-polymarket-alert-bot-runtime-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
