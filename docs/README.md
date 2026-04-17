# Documentation Guide

This directory stores the project documentation that sits around the reusable skill itself: saved market notes, design artifacts, and implementation planning docs.

## Directory Layout

- `market-analysis/`
  Archived market write-ups, thesis memos, and scan notes saved from live analysis sessions.
- `superpowers/specs/`
  Design specs for the skill and its operating model.
- `superpowers/plans/`
  Implementation plans and project-planning artifacts.

## Where To Start

- Read [`../README.md`](../README.md) for the project overview.
- Read [`market-analysis/README.md`](market-analysis/README.md) for the market-note index and naming conventions.
- Read `superpowers/specs/` if you want the product and workflow rationale behind the skill.
- Read `superpowers/plans/` if you want the implementation history.
- The Polymarket alert-bot runtime plan lives in `superpowers/plans/2026-04-17-polymarket-alert-bot-runtime-implementation.md`. Runtime archives live under repo-root `.runtime-data/` and are private, gitignored run artifacts.

## Documentation Conventions

- Put durable project-level documentation in `docs/`.
- Put saved market notes in `docs/market-analysis/`.
- Use `YYYY-MM-DD-topic.md` filenames so notes sort chronologically.
- Keep each analysis note self-contained. Include the market link, analysis date, price snapshot date, and final verdict.
- When a note is a saved synthesis of an earlier conversation, state that explicitly near the top so readers do not mistake it for live pricing.
