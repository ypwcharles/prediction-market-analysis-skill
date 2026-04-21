# Runtime Ops Delta: Docker-First Service Shell

Status: PROPOSED  
Date: 2026-04-20  
Repo: `/Users/peiwenyang/Development/polymarket-research`

## Purpose

This document captures a proposed change in **runtime operating model**, not a change in product wedge.

The 2026-04-17 design and implementation docs assumed:

- Hermes/OpenClaw provide the runtime shell
- the alert bot is invoked as scheduled CLI jobs
- Telegram remains the user-facing surface

The new proposal is:

- the alert bot runtime becomes the long-running shell
- it runs as a Dockerized service
- Hermes/OpenClaw become optional operator surfaces and integration clients

This delta exists so the team can review the ops-model change explicitly before changing code.

## Decision Summary

Recommendation: **yes, this runtime-shell change is worth doing** if both of these are true:

1. the bot is expected to run continuously rather than opportunistically inside an agent shell
2. future distribution should work even for users who do not use Hermes/OpenClaw

If those two goals are real, Docker-first runtime ownership is the cleaner long-term architecture.

## Why This Change Is Worth It

### 1. It removes an unnecessary outer dependency

If the runtime already owns:

- scanning
- monitoring
- SQLite state
- Telegram delivery
- callback state transitions
- archive/calibration

then making Hermes/OpenClaw the primary runtime shell adds orchestration indirection without adding core product value.

### 2. It improves future distribution

For distribution, "run this container with these env vars and one persistent volume" is much easier to explain and support than:

- install Hermes/OpenClaw
- enable the right plugin/skill
- configure cron inside that shell
- route Telegram callbacks through the shell

Docker-first packaging also keeps the product usable outside the current personal agent environment.

### 3. It aligns ownership with the true source of state

The runtime already has the real durable system state:

- SQLite
- trigger lifecycle
- feedback
- thesis memory
- calibration reports
- archive artifacts

That makes the runtime the natural operational center.

### 4. The codebase is still at a cheap pivot point

The current implementation has not yet drifted into a server-only or Hermes-coupled shape. The key business flows are still concentrated in reusable functions and CLI entrypoints:

- `execute_scan_flow(...)`
- `execute_monitor_flow(...)`
- `run_report(...)`
- callback ingestion via `CallbackRouter`

That means a service wrapper can be added now without rewriting the core product logic.

## Why This Change Is Not Free

This is still a meaningful architecture change. It introduces:

- a long-running service process
- service health and restart semantics
- Telegram webhook ingress ownership
- internal scheduling ownership
- container packaging and volume layout
- admin/API surface decisions

So this should not be treated as a casual implementation tweak. It needs explicit engineering review.

## What Does Not Change

The following product decisions remain intact:

- Telegram is still the primary user-facing surface
- `prediction-market-analysis` stays the judgment engine
- discovery remains the wedge
- monitoring remains secondary but action-oriented
- SQLite remains the V1 state source of truth
- Polymarket official API remains position truth
- the product remains human-in-the-loop

This is an ops/deployment model change, not a product thesis change.

## Current Documented Assumptions That Would Change

### Design doc assumptions

The 2026-04-17 design doc currently assumes:

- Hermes/OpenClaw provide the scheduler/runtime shell
- the system runs on a schedule inside Hermes/OpenClaw

### Consolidated decision assumptions

The consolidated CEO decision doc currently assumes:

- Telegram is the primary surface
- Hermes/OpenClaw is the primary runtime shell

### Implementation plan assumptions

The implementation plan currently assumes:

- two scheduled jobs
- CLI-oriented runtime invocation
- no service layer or webhook server layer

These assumptions would need to be updated after review if the new operating model is accepted.

## Proposed Target Operating Model

### Primary runtime

The runtime becomes a single deployable Docker service that owns:

- scan scheduling
- monitor scheduling
- Telegram send path
- Telegram webhook/callback ingress
- SQLite
- archive/report output
- health/status surface

### Deployment topology

V1 should target an explicitly boring topology:

- exactly one active runtime instance
- exactly one writable persistent volume
- exactly one scheduler owner
- exactly one Telegram webhook ingress owner

This change does **not** introduce:

- active-active replicas
- leader election
- external queueing
- distributed locks
- multi-region failover

If the service is restarted, it should recover from durable local state. If a second copy is started accidentally, lock enforcement should prevent overlapping scan/monitor work rather than pretending multi-instance support exists.

### Hermes/OpenClaw role

Hermes/OpenClaw become optional operator clients used for:

- manual trigger
- inspection
- explanation
- debugging
- optional future adapter/plugin ergonomics

They are no longer the required runtime shell.

### CLI role

The existing CLI should remain as stable internal primitives:

- `scan`
- `monitor`
- `report`
- `callback`
- `promote`

These remain valuable for:

- local smoke tests
- cron-free manual runs
- debugging
- service wrapper reuse
- backward-compatible automation

### Service/API role

The runtime should add a thin service layer around the existing flow functions, not rewrite the domain logic.

Likely responsibilities:

- webhook endpoint for Telegram callback ingress
- admin endpoints for scan/monitor/report/status
- internal scheduler loop
- health/readiness endpoints

### HTTP trust boundary

The HTTP surface should split into two classes:

#### Public ingress

- `POST /telegram/webhook`

This endpoint exists only so Telegram can deliver callback updates into the runtime. It should validate the expected webhook secret or equivalent authenticity mechanism before state changes are accepted.

#### Private control plane

- `GET /healthz`
- `GET /status`
- `POST /internal/scan`
- `POST /internal/monitor`
- `POST /internal/report`

Rules:

- `healthz` may be exposed without authentication if deployment requires it
- `status` should default to authenticated access
- all `/internal/*` endpoints must require explicit authentication
- Hermes/OpenClaw or any future operator client should call only this authenticated control plane, never the Telegram ingress path

The first acceptable V1 auth shape is a shared bearer token or equivalent single-secret guard. Do not overbuild auth in the same change.

## Recommended Migration Principle

**Wrap, do not rewrite.**

The existing flow code should stay authoritative. The service layer should call the same underlying runtime functions that the CLI calls today.

That means:

- keep domain logic in `runtime_flow.py`, monitor, scanner, and storage
- add a transport layer on top
- keep CLI and service both as valid entrypoints

## Recommended Scope Boundary For The Next Change

### In scope

- define Docker-first runtime shell
- define scheduler ownership
- define Telegram webhook ownership
- define service/admin surface
- define Hermes/OpenClaw's reduced role
- preserve CLI compatibility
- define single-instance deployment boundary
- define HTTP auth boundary
- define minimum Docker distribution artifact set

### Out of scope

- autonomous execution
- full dashboard
- distributed multi-node scaling
- replacing SQLite in this same change
- refactoring judgment logic for this same change
- production-grade multi-tenant auth
- Kubernetes or multi-service orchestration

## Questions For `/gstack-plan-eng-review`

The next engineering review should answer these questions explicitly.

### 1. Who is the primary runtime shell?

Why it matters:
This is the root decision that changes deployment, ownership, and integration boundaries.

Recommended answer:
`Dockerized alert-bot service` becomes the primary runtime shell. Hermes/OpenClaw become optional operator clients.

### 2. Who owns scheduling?

Why it matters:
The current plan assumes externally scheduled CLI jobs. A Docker-first runtime needs a clear scheduler owner.

Recommended answer:
The runtime service should own the default scheduler for V1. Preserve manual one-shot CLI commands for debugging and explicit operator-triggered runs.

### 3. Who owns Telegram callback ingress?

Why it matters:
This determines where feedback state transitions happen and where operational failures must be debugged.

Recommended answer:
The runtime service should own Telegram webhook ingress directly. Do not route callback traffic through Hermes/OpenClaw by default.

### 4. Should the service expose HTTP endpoints, or only keep CLI?

Why it matters:
Hermes/OpenClaw and other future surfaces need a stable way to query status or trigger actions.

Recommended answer:
Add a minimal authenticated HTTP control plane plus health endpoints. Keep the CLI as a first-class local/debug path.

Suggested initial endpoints:

- `GET /healthz`
- `GET /status`
- `POST /internal/scan`
- `POST /internal/monitor`
- `POST /internal/report`
- `POST /telegram/webhook`

### 5. Should Hermes/OpenClaw integration be plugin-first?

Why it matters:
This affects how much Hermes-specific code gets written into the product.

Recommended answer:
No. Start with direct HTTP or thin wrapper integration. If needed later, add a thin plugin that only adapts operator commands to runtime API calls.

### 6. Should SQLite remain the state backend after this ops-model change?

Why it matters:
A service shell change often tempts a storage rewrite. That would expand scope fast.

Recommended answer:
Yes. Keep SQLite plus a persistent Docker volume for V1. Do not combine the shell change with a storage migration.

### 7. What deployment topology should V1 target?

Why it matters:
The scheduler, SQLite, and webhook assumptions depend on whether V1 is single-instance or multi-instance.

Recommended answer:
Target a single-instance service for V1. Use one mounted persistent volume for SQLite, archives, and reports. Revisit HA/distributed topology later.

### 8. How should the service be packaged for distribution?

Why it matters:
The distribution story is one of the main reasons to make this change.

Recommended answer:
Ship a single Docker image plus a small example deployment package:

- `Dockerfile`
- `.env.example`
- optional `docker-compose.yml`
- volume layout documentation
- webhook/base-url setup notes
- one CI workflow that builds the image

### 9. How should runtime internals be refactored to support both CLI and service entrypoints?

Why it matters:
This is the main risk of accidental logic duplication.

Recommended answer:
Keep flow orchestration in reusable Python functions. Add a small transport layer for HTTP. Both CLI and service should call the same runtime functions.

### 10. What should Hermes/OpenClaw still do after this change?

Why it matters:
Without a clear reduced role, the system risks duplicate shells and confusing ownership.

Recommended answer:
Hermes/OpenClaw should support:

- manual trigger
- status lookup
- explanation queries
- optional future plugin ergonomics

They should not be required for the bot to keep scanning or processing Telegram callbacks.

### 11. What is the minimum acceptable auth model for the new HTTP control plane?

Why it matters:
Without an explicit answer here, the plan risks adding remote execution endpoints with hand-waved protection.

Recommended answer:
Use one boring V1 scheme:

- webhook secret validation for `POST /telegram/webhook`
- one shared bearer token for `GET /status` and all `/internal/*` endpoints

Do not expand this change to user accounts, OAuth, or RBAC.

### 12. Is distribution part of this change, or intentionally deferred?

Why it matters:
The case for this architecture partly rests on future distribution. That should either be delivered now or explicitly deferred, not implied.

Recommended answer:
Include the minimum distribution path in this change:

- `Dockerfile`
- `.env.example`
- example compose file
- persistent volume documentation
- one CI workflow that builds the image

Do not require a polished public registry/release automation in the same change if that would delay the service transition, but do not leave the image build path undefined.

## Recommended Next Step

Do **not** update the 2026-04-17 design/implementation documents yet.

Instead:

1. use this delta doc as the new review input
2. run `/gstack-plan-eng-review` specifically on the operating-model change
3. only after approval, update:
   - the consolidated decisions doc
   - the runtime implementation plan
   - the runtime code

That preserves decision history and avoids silently rewriting the already-approved plan.
