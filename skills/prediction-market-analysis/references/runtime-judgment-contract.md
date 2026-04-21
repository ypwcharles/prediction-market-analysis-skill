# Runtime Judgment Contract (`runtime.v1`)

Canonical source of truth: `runtime/src/polymarket_alert_bot/judgment/contract.py`.
This markdown file is a human-readable derivative reference and must stay aligned with the contract parity tests.

## 1) Scope and Activation

### Scope Gate
This contract is used only when the caller provides `contract_version: "runtime.v1"`. If `contract_version` is absent or does not equal `"runtime.v1"`, this contract does not apply.

### Activation Inputs
Normal runtime judgment requires all three inputs:
1. `contract_version`
2. `context`
3. `response_schema`

### Activation Precedence and Fallback
Apply precedence in this order:
1. Check `contract_version`.
2. Check activation-input completeness.
3. Run normal judgment mapping rules.

If `contract_version: "runtime.v1"` is present but `context` and/or `response_schema` is missing, do not run normal judgment. Emit a fallback runtime object in `degraded` mode that still follows runtime output rules and includes all required top-level fields.

Required fallback defaults (must use the following deterministic fallback defaults):
- `alert_kind: "degraded"`
- `cluster_action: "none"`
- `ttl_hours: 1`
- `citations: []`
- `triggers: []`
- `archive_payload.reason: "activation_incomplete"`

## 2) Runtime Mode Rules
Runtime mode output must be exactly one JSON object only.
Do not emit markdown headings, prose preambles, or fenced code blocks in runtime output.

## 3) Top-Level Output Contract

### Required Top-Level Fields
- `alert_kind`
- `cluster_action`
- `ttl_hours`
- `citations`
- `triggers`
- `archive_payload`

### Recommended Top-Level Fields
- `thesis`
- `side`
- `theoretical_edge_cents`
- `executable_edge_cents`
- `max_entry_cents`
- `suggested_size_usdc`
- `why_now`
- `kill_criteria_text`
- `summary`
- `watch_item`
- `evidence_fresh_until`
- `recheck_required_at`

## 4) Allowed Enum Values

### `alert_kind`
- `strict`
- `strict_degraded`
- `research`
- `reprice`
- `monitor`
- `heartbeat`
- `degraded`

### `cluster_action`
- `create`
- `update`
- `hold`
- `close`
- `none`

## 5) Mapping Rules by `alert_kind`

### Strictness Gate (`context.source_tier_state`)
Before selecting `alert_kind`, apply source-tier strictness gating:

- Read `context.source_tier_state.strict_allowed` and `context.source_tier_state.strict_block_reason`.
- If `strict_allowed` is `false`, strict mode is blocked.
- If `strict_block_reason` is present and not empty, treat strict mode as blocked even when other inputs look favorable.

When strict mode is blocked:
- Do not emit `alert_kind: "strict"` or `alert_kind: "strict_degraded"`.
- Select a non-strict alert kind (`research`, `reprice`, `monitor`, `heartbeat`, or `degraded`) based on readiness.
- Keep `cluster_action` aligned with the selected non-strict mapping and cluster presence.
- For monitor-style maintenance with an existing active cluster (for example `prior_cluster_state.thesis_cluster_id` present), prefer `cluster_action: "hold"` over `none`.

### `strict`
Use when evidence quality and execution readiness are both sufficient for an actionable judgment.
Default `cluster_action`: `create` for a new thesis cluster, `update` for an existing active cluster.

### `strict_degraded`
Use when likely action exists but one material dependency is degraded (for example partial freshness or temporary liquidity uncertainty).
Default `cluster_action`: `update` for existing clusters; `create` only when degraded constraints are explicitly disclosed.

### `research`
Use when hypothesis quality is not yet high enough for trade execution.
Default `cluster_action`: `none` (or `hold` only if an existing cluster remains open while evidence is gathered).

### `reprice`
Use when thesis remains valid but entry, sizing, or edge needs recalibration due to odds drift, spread changes, or price movement.
Default `cluster_action`: `update` for active clusters; `none` if recalibration is not yet actionable.

### `monitor`
Use when no immediate trade change is warranted and output is primarily future watch conditions.
Default `cluster_action`: `hold` for existing clusters, or `none` if no cluster exists.

### `heartbeat`
Use for scheduled liveness/status pulses where runtime confirms current state without introducing a new trade judgment.
This contract treats `heartbeat` as a valid runtime.v1 alert path (not an out-of-contract path).
Default `cluster_action`: `none`; use `hold` only when an active cluster is explicitly being kept unchanged.

### `degraded`
Use when runtime constraints prevent reliable judgment (for example major source outages or rule ambiguity that blocks conclusion).
Default `cluster_action`: `hold` for active clusters and `none` otherwise.

## 6) Citation Rules
Each citation must support at least one concrete claim used by the judgment.

Each citation should include:
- `source_id`
- `url`
- `claim`

Optional citation metadata:
- `source_name`
- `source_tier`
- `fetched_at`
- `confidence` (numeric if the runner can price it precisely, otherwise a short label such as `high`, `medium`, or `low`)

## 7) Trigger Rules
`triggers` must contain only real future checks. Allowed trigger classes:
- Price-threshold rechecks.
- Evidence-freshness expiry checks.
- Rule-change monitoring checks.
- Catalyst checkpoint checks.

Do not emit placeholder or ceremonial triggers that cannot be executed later.

## 8) Archive Payload Rules
`archive_payload` must preserve durable judgment context for later retrieval and replay.

Include when available:
- `reason`
- `summary`
- `thesis`
- `thesis_cluster_id`
- `trigger_payload` (either one machine-readable object or a list of machine-readable trigger snapshots)
- `trigger_metadata`
