#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPORT_PATH="reports/latest.json"
if [[ ! -f "$DEFAULT_REPORT_PATH" && -f "/opt/data/twltool/reports/latest.json" ]]; then
  DEFAULT_REPORT_PATH="/opt/data/twltool/reports/latest.json"
fi
if [[ ! -f "$DEFAULT_REPORT_PATH" && -f "/home/ubuntu/.hermes/twltool/reports/latest.json" ]]; then
  DEFAULT_REPORT_PATH="/home/ubuntu/.hermes/twltool/reports/latest.json"
fi

REPORT_PATH="${1:-${REPORT_PATH:-$DEFAULT_REPORT_PATH}}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-14}"
MIN_SCREENSHOTS="${MIN_SCREENSHOTS:-7}"
WARN_IS_FAILURE="${WARN_IS_FAILURE:-1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" - "$REPORT_PATH" "$MAX_AGE_HOURS" "$MIN_SCREENSHOTS" "$WARN_IS_FAILURE" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_dt(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("missing timestamp")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


report_path = Path(sys.argv[1])
max_age_hours = float(sys.argv[2])
min_screenshots = int(sys.argv[3])
warn_is_failure = sys.argv[4] not in {"0", "false", "False", "no", "NO"}

errors: list[str] = []

if not report_path.exists():
    print(f"WATCHDOG: report not found: {report_path}")
    raise SystemExit(1)

try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"WATCHDOG: cannot parse JSON report {report_path}: {exc}")
    raise SystemExit(1)

run_id = report.get("run_id") or "(unknown)"
summary = report.get("summary") or {}
fail_count = int(summary.get("fail") or 0)
warn_count = int(summary.get("warn") or 0)

finished_at_raw = report.get("finished_at") or report.get("started_at")
try:
    finished_at = parse_dt(finished_at_raw)
    age_hours = (datetime.now(timezone.utc) - finished_at.astimezone(timezone.utc)).total_seconds() / 3600
except Exception as exc:
    age_hours = None
    errors.append(f"cannot parse finished_at/started_at: {exc}")

if age_hours is not None and age_hours > max_age_hours:
    errors.append(f"latest report is stale: age={age_hours:.1f}h > {max_age_hours:g}h")

if fail_count > 0:
    errors.append(f"report has fail={fail_count}")
if warn_is_failure and warn_count > 0:
    errors.append(f"report has warn={warn_count}")

screenshots = report.get("screenshots") or []
if len(screenshots) < min_screenshots:
    errors.append(f"not enough screenshots: {len(screenshots)} < {min_screenshots}")

if errors:
    print(
        "WATCHDOG: abnormal "
        f"run_id={run_id} fail={fail_count} warn={warn_count} "
        f"screenshots={len(screenshots)} report={report_path}"
    )
    for item in errors:
        print(f"- {item}")
    raise SystemExit(1)

print(
    "WATCHDOG: ok "
    f"run_id={run_id} fail={fail_count} warn={warn_count} "
    f"screenshots={len(screenshots)} age_hours={age_hours:.1f} report={report_path}"
)
PY
