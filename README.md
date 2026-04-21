# Prediction Market Analysis + Runtime

This repo now has four real surfaces:

- a reusable prediction-market analysis skill in `skills/prediction-market-analysis/`
- an operational alert runtime in `runtime/`
- runtime and prompt eval fixtures in `evals/`
- design, ops, and archived analysis docs in `docs/`

The judgment policy is intentionally conservative across both modes. The interactive skill rejects weak setups by default, while the runtime wraps the same judgment logic in a JSON contract for scan, monitor, report, and callback flows.

## Repository Map

- `skills/prediction-market-analysis/SKILL.md`
  Main skill entrypoint for interactive analysis and runtime judgment mode.
- `skills/prediction-market-analysis/references/`
  Human-readable reference docs for evidence grading, Kelly sizing, domain adapters, and the runtime judgment contract.
- `runtime/`
  The actual Python project: scanner, monitor loop, callback handling, FastAPI service, storage, templates, and Docker packaging.
- `evals/`
  Prompt-eval fixtures, including runtime envelope examples for `runtime.v1`.
- `docs/README.md`
  Documentation hub for design docs, market-analysis archives, and workflow references.
- `docs/market-analysis/`
  Promoted or manually saved market memos.
- `docs/design-and-plans/`
  Project-authored implementation plans and design rationale.

## Modes

### Interactive Skill

- Analyzes single contracts, adjacent buckets, and cross-platform equivalents.
- Screens themes or event clusters for cleaner expressions.
- Explains verdict, evidence quality, mispricing, portfolio overlap, and sizing.
- Uses the numbered interactive report format from the skill.

### Runtime

- Runs scheduled `scan`, `monitor`, `report`, and `callback` flows from `runtime/`.
- Uses the canonical `runtime.v1` judgment contract defined in `runtime/src/polymarket_alert_bot/judgment/contract.py`.
- Persists alerts, clusters, triggers, archives, and reports in `.runtime-data/`.
- Can deliver Telegram messages, monitor rechecks, and degraded-mode heartbeats.

The repo is no longer accurately described as "just a skill that returns `TRADE` / `NO TRADE`". That still applies to parts of the interactive verdict surface, but not to the runtime contract or the stored alert lifecycle.

## Health

Run the canonical repo-root health command before concluding runtime changes:

```bash
bash scripts/runtime-health.sh
```

That command checks the real Python project in `runtime/` with lint, format, type, and test steps.

## Local Usage

To use the skill locally in Codex, symlink the skill directory into your personal skill namespace:

```bash
ln -s "$(pwd)/skills/prediction-market-analysis" "$HOME/.agents/skills/prediction-market-analysis"
```

To run the runtime locally:

```bash
cd runtime
uv run polymarket-alert-bot scan
uv run polymarket-alert-bot monitor
uv run polymarket-alert-bot report
```

## Documentation Guide

Start with [docs/README.md](docs/README.md) for the doc map.
Use [runtime/README.md](runtime/README.md) for runtime commands, service notes, and data-path details.
Use `CLAUDE.md` for repo-specific routing and health expectations.
