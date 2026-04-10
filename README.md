# Prediction Market Analysis Skill

## What this is

This repository contains a reusable skill for analyzing prediction markets such as Polymarket and Kalshi. The skill is designed to reject weak setups by default, estimate a main probability plus confidence interval, and size only the strongest setups using a conservative Kelly-based framework.

## What it does

- Supports both single-market analysis and theme-driven market discovery.
- Forces evidence grading instead of narrative accumulation.
- Compares fair value with executable prices after fees and slippage.
- Incorporates portfolio overlap before final sizing.
- Outputs only `TRADE` or `NO TRADE`, never a vague middle state.

## What it does not do

- It does not guarantee profitable trades.
- It does not auto-execute orders.
- It does not assume market price is literal truth.
- It does not size from the central estimate when uncertainty is material.

## Repository structure

- `skills/prediction-market-analysis/SKILL.md`
  Main skill entrypoint and workflow.
- `skills/prediction-market-analysis/references/`
  Detailed reference documents for evidence grading, probability/Kelly, domain adapters, and research foundations.
- `evals/evals.json`
  Early benchmark prompts for baseline vs with-skill comparisons.
- `docs/superpowers/specs/`
  Design specification.
- `docs/superpowers/plans/`
  Implementation plan.

## Local usage

To use the skill locally in Codex, symlink the skill directory into your personal skill namespace if desired:

```bash
ln -s "$(pwd)/skills/prediction-market-analysis" "$HOME/.agents/skills/prediction-market-analysis"
```

If the link already exists, inspect it first and replace it intentionally.

## Evaluation workflow

1. Run representative prompts without the skill.
2. Run the same prompts with the skill loaded.
3. Grade whether the output includes the required sections and refusal discipline.
4. Compare pass rates, token cost, and qualitative output quality.

See `evals/evals.json` for the initial prompt set.

## Publishing notes

This repository is intended to be publishable as a standalone GitHub repo. After the first commit:

```bash
git init
git branch -M main
git add .
git commit -m "feat: add prediction market analysis skill"
```

Then publish either through the GitHub plugin workflow or:

```bash
gh repo create prediction-market-analysis-skill --public --source=. --remote=origin --push
```
