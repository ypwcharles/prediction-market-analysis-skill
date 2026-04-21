# Prediction Market Analysis Skill

This repository holds a reusable skill for analyzing prediction markets such as Polymarket and Kalshi, plus the supporting research notes used to test and refine that workflow.

The skill is intentionally conservative. It rejects weak setups by default, separates directional edge from timing edge, and sizes only from a conservative probability boundary rather than a single-point estimate.

## What The Skill Does

- Analyzes single contracts, adjacent buckets, and cross-platform equivalents
- Screens entire themes or event clusters for cleaner expressions
- Grades evidence quality instead of accumulating narrative
- Compares fair value with realistic executable prices after spread, fees, and slippage
- Applies conservative Kelly sizing with portfolio-overlap checks
- Returns only `TRADE` or `NO TRADE`

## What The Skill Does Not Do

- It does not guarantee profitable trades
- It does not auto-execute orders
- It does not treat market price as ground truth
- It does not size from the central estimate when uncertainty is material

## Repository Map

- `skills/prediction-market-analysis/SKILL.md`
  Main skill entrypoint and workflow.
- `skills/prediction-market-analysis/references/`
  Reference material for evidence grading, probability/Kelly, domain adapters, and research foundations.
- `evals/evals.json`
  Early benchmark prompts for baseline vs skill-guided comparisons.
- `docs/README.md`
  Documentation hub for project docs, analysis notes, and internal specs.
- `docs/market-analysis/`
  Saved market write-ups and thesis-specific research memos.
- `docs/superpowers/specs/`
  Skill design specifications.
- `docs/superpowers/plans/`
  Implementation plans.

## Documentation Guide

Start with [docs/README.md](docs/README.md) if you want the documentation map.

- Use [docs/market-analysis/README.md](docs/market-analysis/README.md) for saved market notes and naming conventions.
- Use `docs/superpowers/specs/` for the design rationale behind the skill.
- Use `docs/superpowers/plans/` for implementation planning history.

## Local Usage

To use the skill locally in Codex, symlink the skill directory into your personal skill namespace:

```bash
ln -s "$(pwd)/skills/prediction-market-analysis" "$HOME/.agents/skills/prediction-market-analysis"
```

If the link already exists, inspect it first and replace it intentionally.

## Evaluation Workflow

1. Run representative prompts without the skill.
2. Run the same prompts with the skill loaded.
3. Grade whether the output includes the required sections and refusal discipline.
4. Compare pass rates, token cost, and qualitative output quality.

See `evals/evals.json` for the initial prompt set.

## Publishing Notes

This repository is structured to be publishable as a standalone GitHub repo. After the first commit:

```bash
git init
git branch -M main
git add .
git commit -m "feat: add prediction-market-analysis skill"
```

Then publish either through the GitHub plugin workflow or:

```bash
gh repo create prediction-market-analysis-skill --public --source=. --remote=origin --push
```
