#!/usr/bin/env bash
# #1274 offline PostgreSQL gate; invoked inside pg_virtualenv only.
set -euo pipefail
test -n "$PGHOST" || { echo 'PGHOST absent: run in pg_virtualenv'; exit 10; }
test -n "$PGPORT" || { echo 'PGPORT absent: run in pg_virtualenv'; exit 10; }
test -n "$BUDGET_QA_PYTHON" || { echo 'BUDGET_QA_PYTHON absent'; exit 10; }
HERE="$(cd "$(dirname "$0")" && pwd)"
API_ROOT="$(cd "$HERE/../../.." && pwd)"
psql -X -q -v ON_ERROR_STOP=1 -f "$HERE/platform_budget_pg_gate.sql" >/dev/null
PYTHONPATH="$API_ROOT" "$BUDGET_QA_PYTHON" "$HERE/platform_budget_write_pg_exercise.py"
echo 'PLATFORM_BUDGET_DISPOSABLE_PG_GATE=PASS'
