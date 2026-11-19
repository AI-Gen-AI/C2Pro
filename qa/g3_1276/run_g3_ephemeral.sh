#!/usr/bin/env bash
# G3 exact SHA; invoked ONLY inside pg_virtualenv 16.
set -euo pipefail
test -n "$(printenv PG_CLUSTER_CONF_ROOT)" || { echo "STOP no pg_virtualenv"; exit 10; }
case "$PG_CLUSTER_CONF_ROOT" in /tmp/pg_virtualenv.*) ;; *) echo "STOP non-ephemeral PG"; exit 10;; esac
ROOT=/home/aigenadmin/qa_workspaces/c2pro-g3-1276-20261119
EV=/home/aigenadmin/qa_evidence/g3-1276
EXPECTED=8a84f9ebcd54928347171cef0cc80f34ca3fb949
CURRENT="$(git -C "$ROOT" rev-parse HEAD)"
echo "EXACT_SOURCE_SHA=$CURRENT"
test "$CURRENT" = "$EXPECTED" || { echo "STOP source mismatch"; exit 11; }
test -z "$(git -C "$ROOT" status --porcelain)" || { echo "STOP dirty worktree"; exit 11; }
DB=c2pro_g3_1276_test
createdb "$DB"
psql -X -d "$DB" -v ON_ERROR_STOP=1 -q -c "CREATE ROLE c2pro_admin_ops NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;"
export ENVIRONMENT=test
export JWT_SECRET_KEY=offline-synthetic-g3-only
export DATABASE_URL="postgresql://aigenadmin:$PGPASSWORD@localhost:$PGPORT/$DB"
export TEST_DATABASE_URL="$DATABASE_URL"
export C2PRO_N4_SCRATCH_DSN="$DATABASE_URL"
export PYTHONPATH="$ROOT/apps/api"
export OPENAI_API_KEY=
export ANTHROPIC_API_KEY=
export GOOGLE_API_KEY=
cd "$ROOT/apps/api"
PY=/home/aigenadmin/.cache/c2pro-local-ci/venv-py3.11/bin/python
"$PY" -m alembic upgrade head > "$EV/g3_alembic.log" 2>&1 || {
  echo "MIGRATIONS=FAIL"
  tail -30 "$EV/g3_alembic.log"
  exit 12
}
echo "MIGRATIONS_ALEMBIC_HEAD=PASS"
echo "MIGRATIONS_LOG_SHA256=$(sha256sum "$EV/g3_alembic.log" | cut -d' ' -f1)"
if "$PY" -u "$EV/g3_integrated_sql_celery.py" >"$EV/g3_integrated.log" 2>&1; then
  echo "G3_INTEGRATED_PYTHON_EXIT=0"
  grep -E 'G3_|PASS|CELERY|GET_|Traceback' "$EV/g3_integrated.log" | tail -15
else
  st=$?
  echo "G3_INTEGRATED_PYTHON_EXIT=$st"
  tail -42 "$EV/g3_integrated.log"
  exit "$st"
fi
echo "G3_INTEGRATED_LOG_SHA256=$(sha256sum "$EV/g3_integrated.log" | cut -d' ' -f1)"
echo "EPHEMERAL_DB=DESTROY_ON_PG_VIRTUALENV_EXIT"

