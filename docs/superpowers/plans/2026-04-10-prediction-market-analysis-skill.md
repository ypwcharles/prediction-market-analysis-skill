# Prediction Market Analysis Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish a conservative prediction-market analysis skill that evaluates Polymarket/Kalshi opportunities, rejects weak trades by default, and outputs probability intervals plus conservative Kelly sizing.

**Architecture:** The repository will contain a reusable skill under `skills/prediction-market-analysis/` plus focused reference documents under `references/` and eval definitions under `evals/`. The skill will encode a reject-first analysis pipeline, while the repo also includes enough metadata and tests to benchmark the skill and publish it cleanly to GitHub.

**Tech Stack:** Markdown skills, JSON eval definitions, shell/git workflow, GitHub publication workflow, optional benchmark viewer from `@skill-creator`.

---

## File Structure

### Repository files

- Create: `README.md`
- Create: `.gitignore`
- Create: `skills/prediction-market-analysis/SKILL.md`
- Create: `skills/prediction-market-analysis/references/evidence-engine.md`
- Create: `skills/prediction-market-analysis/references/probability-and-kelly.md`
- Create: `skills/prediction-market-analysis/references/domain-adapters.md`
- Create: `skills/prediction-market-analysis/references/research-and-open-source.md`
- Create: `evals/evals.json`
- Create: `docs/superpowers/specs/2026-04-10-prediction-market-analysis-skill-design.md`
- Create: `docs/superpowers/plans/2026-04-10-prediction-market-analysis-skill.md`

### Generated / local-only during evaluation

- Create later: `prediction-market-analysis-workspace/iteration-1/...`

### Responsibility map

- `README.md`
  Explains what the skill does, how to use it, how to install it locally, and how to run evaluations.
- `.gitignore`
  Keeps benchmark outputs, generated review artifacts, and local workspaces out of git.
- `skills/prediction-market-analysis/SKILL.md`
  Main triggerable skill document with workflow, output contract, refusal policy, and references.
- `skills/prediction-market-analysis/references/evidence-engine.md`
  Detailed evidence grading model and source hierarchy.
- `skills/prediction-market-analysis/references/probability-and-kelly.md`
  Probability interval construction, edge logic, and conservative Kelly sizing rules.
- `skills/prediction-market-analysis/references/domain-adapters.md`
  Initial adapter rules for politics/macro, crypto, and sports.
- `skills/prediction-market-analysis/references/research-and-open-source.md`
  Research foundation and open-source inspirations.
- `evals/evals.json`
  Test prompts for baseline and with-skill comparisons.

## Task 1: Scaffold the Repository

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `skills/prediction-market-analysis/`
- Create: `skills/prediction-market-analysis/references/`
- Create: `evals/evals.json`

- [ ] **Step 1: Create the repository directory structure**

Run:
```bash
mkdir -p skills/prediction-market-analysis/references evals
```
Expected: directories exist under the repo root.

- [ ] **Step 2: Write the ignore file**

Create `.gitignore` with:
```gitignore
.DS_Store
prediction-market-analysis-workspace/
review-feedback/
benchmark.json
benchmark.md
*.pyc
__pycache__/
```

- [ ] **Step 3: Write the README skeleton**

Create `README.md` with sections:
```markdown
# Prediction Market Analysis Skill

## What this is
## What it does
## What it does not do
## Repository structure
## Local usage
## Evaluation workflow
## Publishing notes
```

- [ ] **Step 4: Create the eval file skeleton**

Create `evals/evals.json` with:
```json
{
  "skill_name": "prediction-market-analysis",
  "evals": []
}
```

- [ ] **Step 5: Verify the scaffold**

Run:
```bash
find . -maxdepth 3 -type f | sort
```
Expected: `README.md`, `.gitignore`, and `evals/evals.json` appear, and the skill directory exists.

## Task 2: Write the Core Skill Document

**Files:**
- Create: `skills/prediction-market-analysis/SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Write the failing eval prompts before drafting the skill**

Update `evals/evals.json` with at least three prompts:
```json
{
  "skill_name": "prediction-market-analysis",
  "evals": [
    {
      "id": 1,
      "prompt": "Analyze this Polymarket market and tell me whether there is a trade after fees and slippage. Use my current portfolio exposure if relevant.",
      "expected_output": "Structured trade or no-trade report with market summary, evidence review, probability interval, net edge, portfolio impact, and conservative Kelly sizing.",
      "files": []
    },
    {
      "id": 2,
      "prompt": "Search Polymarket and Kalshi for markets related to the next Fed decision. Rank the strongest setups and reject weak ones.",
      "expected_output": "Shortlisted candidate markets plus full analysis only for markets that survive screening.",
      "files": []
    },
    {
      "id": 3,
      "prompt": "This market looks attractive, but my portfolio already has similar crypto exposure. Re-evaluate whether I should trade it.",
      "expected_output": "Portfolio-aware decision with reduced sizing or no-trade if concentration is too high.",
      "files": []
    }
  ]
}
```

- [ ] **Step 2: Write the `SKILL.md` frontmatter**

Use:
```yaml
---
name: prediction-market-analysis
description: Use when analyzing Polymarket, Kalshi, or related prediction-market contracts for tradeability, fair odds, mispricing, cross-market comparisons, or Kelly-based sizing. Trigger on requests to analyze a specific market, scan a theme for opportunities, compare related contracts, estimate probability ranges, size a trade conservatively, or decide whether to reject a setup as too weak to trade.
---
```

- [ ] **Step 3: Write the main skill overview and trigger guidance**

Include sections for:
```markdown
# Prediction Market Analysis

## Overview
## When to Use
## Core Principles
## Supported Entry Modes
```

The body must encode:
- reject-first behavior
- two input modes
- requirement to output main probability plus interval
- requirement to use conservative Kelly only

- [ ] **Step 4: Write the full workflow into `SKILL.md`**

Add sections covering:
```markdown
## Workflow
1. Normalize input
2. Discover related markets
3. Filter for tradeability
4. Gather and grade evidence
5. Build the thesis
6. Estimate probability and interval
7. Compute net edge
8. Check portfolio risk
9. Size conservatively
10. Return TRADE or NO TRADE
```

- [ ] **Step 5: Write the required output template**

Add a strict report template matching the spec:
```markdown
## Output Format
ALWAYS use this exact structure:
1. Verdict
2. Market Summary
3. Probability Assessment
4. Evidence Review
5. Mispricing / Edge
6. Portfolio Impact
7. Sizing
8. Kill Criteria
```

- [ ] **Step 6: Document refusal policy and common mistakes**

Add:
```markdown
## Refusal Rules
## Common Mistakes
```

Common mistakes must include:
- mistaking quantity of evidence for quality
- using market price as literal truth
- sizing from the central estimate
- ignoring related exposure

- [ ] **Step 7: Verify the skill is concise enough to trigger cleanly**

Run:
```bash
wc -l skills/prediction-market-analysis/SKILL.md
```
Expected: the main skill stays reasonably compact, with heavy detail pushed into references.

## Task 3: Add Reference Documents

**Files:**
- Create: `skills/prediction-market-analysis/references/evidence-engine.md`
- Create: `skills/prediction-market-analysis/references/probability-and-kelly.md`
- Create: `skills/prediction-market-analysis/references/domain-adapters.md`
- Create: `skills/prediction-market-analysis/references/research-and-open-source.md`

- [ ] **Step 1: Write evidence-engine reference**

Create `skills/prediction-market-analysis/references/evidence-engine.md` with:
```markdown
# Evidence Engine

## Source Tiers
## Evidence scoring dimensions
## Deduplication rules
## Conflict handling
## When evidence is too weak to proceed
```

- [ ] **Step 2: Write probability-and-kelly reference**

Create `skills/prediction-market-analysis/references/probability-and-kelly.md` with:
```markdown
# Probability and Kelly

## Anchor selection
## Evidence adjustments
## Confidence interval rules
## Net edge computation
## Conservative Kelly
## Portfolio-blind haircut rule
```

- [ ] **Step 3: Write domain-adapters reference**

Create `skills/prediction-market-analysis/references/domain-adapters.md` with:
```markdown
# Domain Adapters

## Politics / Macro
## Crypto
## Sports
```

For each adapter, include:
- preferred evidence sources
- common market traps
- when to trust market price more
- when to widen intervals

- [ ] **Step 4: Write research-and-open-source reference**

Create `skills/prediction-market-analysis/references/research-and-open-source.md` with:
```markdown
# Research and Open Source Foundations

## Key research findings
## Open-source inspirations
## Concepts borrowed
## Concepts explicitly not copied
```

- [ ] **Step 5: Link all references from the main skill**

Modify `skills/prediction-market-analysis/SKILL.md` so each heavy section points to the relevant reference:
```markdown
Read `references/evidence-engine.md` when grading evidence.
Read `references/probability-and-kelly.md` before pricing edge or sizing.
Read `references/domain-adapters.md` for market-specific adjustments.
```

## Task 4: Build Evaluation and Review Scaffolding

**Files:**
- Modify: `evals/evals.json`
- Create later during evaluation: `prediction-market-analysis-workspace/iteration-1/...`

- [ ] **Step 1: Expand eval metadata with expected output notes**

Ensure each eval in `evals/evals.json` describes:
- whether the correct answer is likely `TRADE` or `NO TRADE`
- whether portfolio context matters
- what sections must appear in the report

- [ ] **Step 2: Draft assertions for later grading**

Prepare assertions to check:
```text
- Includes explicit TRADE or NO TRADE verdict
- Includes probability interval, not only a point estimate
- Includes net edge after costs
- Includes portfolio-aware reasoning when asked
- Uses conservative Kelly framing
- Refuses weak setups instead of forcing a trade
```

- [ ] **Step 3: Document the intended eval workflow in the README**

Add to `README.md`:
```markdown
## Evaluation Workflow
1. Run baseline without the skill
2. Run with the skill
3. Grade outputs
4. Compare benchmark deltas
```

- [ ] **Step 4: Run a baseline structure check**

Run:
```bash
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("evals/evals.json").read_text())
assert data["skill_name"] == "prediction-market-analysis"
assert len(data["evals"]) >= 3
print("eval file OK")
PY
```
Expected: `eval file OK`

## Task 5: Review, Initialize Git, and Publish to GitHub

**Files:**
- Modify: `README.md`
- Modify: all created files as needed from review
- Create: `.git/` via `git init`

- [ ] **Step 1: Perform an inline plan/spec alignment review before implementation wrap-up**

Review the created files against:
- `docs/superpowers/specs/2026-04-10-prediction-market-analysis-skill-design.md`
- this plan

Check:
- no placeholders
- no missing output sections
- refusal logic present
- references linked correctly

- [ ] **Step 2: Initialize the git repository**

Run:
```bash
git init
git branch -M main
```
Expected: repository initialized with `main` as default branch.

- [ ] **Step 3: Stage and commit the first version**

Run:
```bash
git add README.md .gitignore skills evals docs
git commit -m "feat: add prediction market analysis skill"
```
Expected: initial commit succeeds.

- [ ] **Step 4: Create or connect a GitHub repository**

Preferred path:
- use `@github:yeet` if a compatible GitHub publishing flow is available

Fallback path:
```bash
gh repo create prediction-market-analysis-skill --public --source=. --remote=origin --push
```

Expected: remote `origin` exists and `main` is pushed.

- [ ] **Step 5: Verify publication**

Run:
```bash
git remote -v
git status --short
git log --oneline -1
```
Expected:
- `origin` points at GitHub
- working tree is clean
- latest commit is the skill commit

## Task 6: Optional Post-Publish Improvement Loop

**Files:**
- Modify later: `skills/prediction-market-analysis/SKILL.md`
- Modify later: `evals/evals.json`

- [ ] **Step 1: Run the qualitative and benchmark review loop from `@skill-creator` when ready**

Use:
- baseline without skill
- with-skill run
- grading
- benchmark aggregation

- [ ] **Step 2: Tighten the description field only after behavior is correct**

Optimize trigger quality once the core skill content passes the eval prompts.

- [ ] **Step 3: Publish follow-up improvements in small commits**

Run:
```bash
git add skills/prediction-market-analysis evals README.md
git commit -m "refactor: improve prediction market skill evaluation"
git push origin main
```

Expected: iterative improvements are easy to review and benchmark.
