#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CONFIG_PATH="${CONFIG_PATH:-config/taiwanlife.json}"
OUTPUT_DIR="${OUTPUT_DIR:-reports}"
FLOW_UI_HOST="${FLOW_UI_HOST:-127.0.0.1}"
FLOW_UI_PORT="${FLOW_UI_PORT:-8787}"
FLOW_UI_TOKEN="${FLOW_UI_TOKEN:-}"

if [[ "$FLOW_UI_HOST" != "127.0.0.1" && "$FLOW_UI_HOST" != "localhost" && "$FLOW_UI_HOST" != "::1" && -z "$FLOW_UI_TOKEN" ]]; then
  echo "FLOW_UI_TOKEN is required when FLOW_UI_HOST is not local." >&2
  exit 2
fi

cd "$REPO_ROOT"

args=(
  -m taiwanlife_monitor.flow_ui
  --config "$CONFIG_PATH"
  --output-dir "$OUTPUT_DIR"
  --host "$FLOW_UI_HOST"
  --port "$FLOW_UI_PORT"
  --no-browser
)

if [[ -n "$FLOW_UI_TOKEN" ]]; then
  args+=(--token "$FLOW_UI_TOKEN")
fi

exec "$PYTHON_BIN" "${args[@]}"
