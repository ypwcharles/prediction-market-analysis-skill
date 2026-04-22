#!/usr/bin/env bash
set -euo pipefail

PROFILE_ENV="/home/yangp/.hermes/profiles/pmalert/.env"
REPO_ROOT="/home/yangp/workspace/prediction-market-analysis-skill"
RUNTIME_DIR="$REPO_ROOT/runtime"
DATA_DIR="$REPO_ROOT/.runtime-data-pmalert"
RUNNER_SCRIPT_DEFAULT="$REPO_ROOT/scripts/hermes_runtime_real_runner.py"

if [[ ! -f "$PROFILE_ENV" ]]; then
  echo "missing profile env: $PROFILE_ENV" >&2
  exit 1
fi

set -a
source "$PROFILE_ENV"
set +a

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "pmalert TELEGRAM_BOT_TOKEN is empty; fill ~/.hermes/profiles/pmalert/.env first" >&2
  exit 2
fi

mkdir -p "$DATA_DIR"

export POLYMARKET_ALERT_BOT_DATA_DIR="$DATA_DIR"
export POLYMARKET_ALERT_BOT_ENABLE_SCAN=1
export POLYMARKET_ALERT_BOT_SERVICE_HOST=127.0.0.1
export POLYMARKET_ALERT_BOT_SERVICE_PORT=18083
export POLYMARKET_ALERT_BOT_SERVICE_ENABLE_SCHEDULER=1
export POLYMARKET_ALERT_BOT_SERVICE_BEARER_TOKEN='pmalert-runtime-bearer'
export POLYMARKET_ALERT_BOT_INTERNAL_BEARER_TOKEN='pmalert-runtime-bearer'
export POLYMARKET_ALERT_BOT_TELEGRAM_CHAT_ID='-1003785749142'
export POLYMARKET_ALERT_BOT_TELEGRAM_MESSAGE_THREAD_ID='8369'
export POLYMARKET_ALERT_BOT_TELEGRAM_BASE_URL='http://127.0.0.1:8081'
export POLYMARKET_ALERT_BOT_DISABLE_TELEGRAM=0
export POLYMARKET_ALERT_BOT_GAMMA_LIMIT=100
export POLYMARKET_ALERT_BOT_SCAN_MAX_JUDGMENT_CANDIDATES=1
if [[ ! -f "$RUNNER_SCRIPT_DEFAULT" ]]; then
  echo "missing runtime runner script: $RUNNER_SCRIPT_DEFAULT" >&2
  exit 3
fi
export POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD="python3 $RUNNER_SCRIPT_DEFAULT"
export POLYMARKET_ALERT_BOT_JUDGMENT_TIMEOUT_SECONDS=600
export HERMES_RUNTIME_REAL_RUNNER_LOG="$DATA_DIR/hermes-runner-log.jsonl"

cd "$RUNTIME_DIR"
exec uv run polymarket-alert-bot serve
