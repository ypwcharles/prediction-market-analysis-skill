# CLAUDE.md

## Skill Routing

- Use `skills/prediction-market-analysis/SKILL.md` for prompt behavior, contract language, and eval fixture changes.
- Use `runtime/` for the operational alert bot: scanner, monitor, callback handling, service endpoints, storage, and delivery.
- Use `docs/design-and-plans/` for implementation plans only after the code and tests reflect the described state.
- When the work changes repo health, CI, or runtime verification, run [$health](/Users/peiwenyang/gstack/.agents/skills/gstack-health/SKILL.md) or at minimum the root health command below before wrapping up.
- When the work starts from a new plan or a major refactor, route through [$autoplan](/Users/peiwenyang/gstack/.agents/skills/gstack-autoplan/SKILL.md) before implementation.

## Health Stack

- Repo-root health command: `bash scripts/runtime-health.sh`
- The root health command is the canonical local check and must stay aligned with CI.
- It currently runs:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src`
  - `uv run pytest`
- All of those commands run from `runtime/`, because the real Python project lives there.
