#!/usr/bin/env bash
# Unified G3 offline harness. Runs only in disposable pg_virtualenv, never shared PG.
set -euo pipefail

EXPECTED_QA_PARENT="$HOME/.cache/ai-gen-qa-g4"
case "${C2PRO_G3_EPHEMERAL_PG_DIR:-}" in
  "$EXPECTED_QA_PARENT"/c2pro-g4-pg.*) ;;
  *) echo "STOP: invalid private cluster root"; exit 10 ;;
esac
[[ -d "${C2PRO_G3_EPHEMERAL_PG_DIR}/data" ]] || exit 10
[[ "${PGHOST:-}" == "127.0.0.1" ]] || { echo "STOP: PGHOST not loopback"; exit 10; }
for target in "$EXPECTED_QA_PARENT" "$C2PRO_G3_EPHEMERAL_PG_DIR" "${C2PRO_G3_EPHEMERAL_PG_DIR}/data"; do
  [[ "$(stat -c %u "$target")" == "$(id -u)" ]] || exit 10
  [[ "$(stat -c %a "$target")" == "700" ]] || exit 10
done

case "${G3_CASE:-}" in
  legacy)
    SOURCE=/home/aigenadmin/qa_workspaces/c2pro-g3-1276-20261119
    EVIDENCE=/home/aigenadmin/qa_evidence/g4-1277-sonar-regression/legacy
    EXPECTED_SHA=8a84f9ebcd54928347171cef0cc80f34ca3fb949
    DRIVER=g3_integrated_sql_celery.py
    ;;
  recovery)
    SOURCE=/srv/c2pro/ops-c2pro-runner/checkouts/14c35b7f0b89-214064af
    EVIDENCE=/home/aigenadmin/qa_evidence/g4-1277-sonar-regression/recovery
    EXPECTED_SHA=14c35b7f0b8933a4ff0b4f330f3941073809ff24
    DRIVER=g3_recovery_14c35_sql_celery.py
    ;;
  *) echo "STOP: unknown G3_CASE"; exit 10 ;;
esac

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_SHA="$(git -C "$SOURCE" rev-parse HEAD)"
echo "SOURCE_SHA=$CURRENT_SHA G3_CASE=$G3_CASE"
[[ "$CURRENT_SHA" == "$EXPECTED_SHA" ]] || { echo "STOP: checkout drift"; exit 11; }
[[ -z "$(git -C "$SOURCE" status --porcelain)" ]] || { echo "STOP: dirty source checkout"; exit 11; }
mkdir -p "$EVIDENCE"
DB=c2pro_g3_1276_test
createdb "$DB"
psql -X -d "$DB" -v ON_ERROR_STOP=1 -q -c \
  "CREATE ROLE c2pro_admin_ops NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;"
export ENVIRONMENT=test
PY=/home/aigenadmin/.cache/c2pro-local-ci/venv-py3.11/bin/python
# Synthetic, per-execution JWT secret: no hardcoded credentials and no value logged.
export JWT_SECRET_KEY="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DATABASE_URL="postgresql://aigenadmin:${PGPASSWORD}@127.0.0.1:${PGPORT}/${DB}"
export TEST_DATABASE_URL="$DATABASE_URL"
export C2PRO_N4_SCRATCH_DSN="$DATABASE_URL"
export PYTHONPATH="$SOURCE/apps/api"
export OPENAI_API_KEY=
export ANTHROPIC_API_KEY=
export GOOGLE_API_KEY=
cd "$SOURCE/apps/api"

"$PY" -m alembic upgrade head >"$EVIDENCE/g3_alembic.log" 2>&1 || {
  echo "MIGRATIONS=FAIL"; tail -30 "$EVIDENCE/g3_alembic.log"; exit 12
}
echo "ALEMBIC_HEAD=PASS LOG_SHA256=$(sha256sum "$EVIDENCE/g3_alembic.log" | cut -d' ' -f1)"
if "$PY" -u "$ROOT_DIR/$DRIVER" >"$EVIDENCE/g3_integrated.log" 2>&1; then
  echo "INTEGRATION_EXIT=0"
  grep -E 'G3_|PASS|CELERY|GET_|Traceback' "$EVIDENCE/g3_integrated.log" | tail -16 || :
else
  exitcode=$?
  echo "INTEGRATION_EXIT=$exitcode"; tail -45 "$EVIDENCE/g3_integrated.log"; exit "$exitcode"
fi
echo "INTEGRATION_SHA256=$(sha256sum "$EVIDENCE/g3_integrated.log" | cut -d' ' -f1)"

if "$PY" -m pytest -q \
  tests/integration/analysis/test_n4_window_runner_pg.py \
  tests/integration/analysis/test_n4_incremental_store_pg.py \
  tests/integration/analysis/test_n4_shared_tenant_budget_pg.py \
  -k "simultaneous_runners_replay or provider_timeout_preserves_unknown_charge or no_cost_receipt_is_not_zero or idempotency_budget_resume_fencing_and_rls or global_cap_serializes_two_independent_n4_project_workers" \
  --disable-warnings >"$EVIDENCE/g3_negative_pg.log" 2>&1; then
  grep -E 'passed|skipped|failed|100%' "$EVIDENCE/g3_negative_pg.log" | tail -4
  echo "G3_NEGATIVE_PG_EXIT=0"
else
  exitcode=$?
  echo "G3_NEGATIVE_PG_EXIT=$exitcode"; tail -35 "$EVIDENCE/g3_negative_pg.log"; exit "$exitcode"
fi
echo "G3_NEGATIVE_SHA256=$(sha256sum "$EVIDENCE/g3_negative_pg.log" | cut -d' ' -f1)"
echo "DB_IS_EPHEMERAL=YES; DESTRUCTION_BY_WRAPPER_CLEANUP"
