#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/runtime"

uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
