# Documentation Guide

This directory stores the project documentation that sits around the reusable skill itself: saved market notes, design artifacts, and implementation planning docs.

## Directory Layout

- `market-analysis/`
  Archived market write-ups, thesis memos, and scan notes saved from live analysis sessions.
- `design-and-plans/`
  Project-authored design docs and implementation plans.
- `workflow-references/`
  External gstack and Superpowers workflow docs that were directly relevant to this repo.

## Where To Start

- Read [`../README.md`](../README.md) for the project overview.
- Read [`market-analysis/README.md`](market-analysis/README.md) for the market-note index and naming conventions.
- Read `design-and-plans/` if you want the project's design rationale and implementation history.
- Read `workflow-references/` if you want the external gstack and Superpowers documents that were relevant here.
- The Polymarket alert-bot runtime plan lives in `design-and-plans/2026-04-17-polymarket-alert-bot-runtime-implementation.md`. Runtime archives live under repo-root `.runtime-data/` and are private, gitignored run artifacts.

## Documentation Conventions

- Put durable project-level documentation in `docs/`.
- Put saved market notes in `docs/market-analysis/`.
- Use `YYYY-MM-DD-topic.md` filenames so notes sort chronologically.
- Keep each analysis note self-contained. Include the market link, analysis date, price snapshot date, and final verdict.
- When a note is a saved synthesis of an earlier conversation, state that explicitly near the top so readers do not mistake it for live pricing.
