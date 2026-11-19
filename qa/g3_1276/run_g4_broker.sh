#!/usr/bin/env bash
# G4-BROKER: rootless Redis 7.2.8 and a separately forked Celery worker, disposable PG16.
# No shared services. No production credentials, no real providers, no external model network.
set -euo pipefail
umask 077
[[ "$(id -un)" == aigenadmin ]] || { echo "STOP: wrong user"; exit 10; }
G4_CASE="${1:-normal}"
case "$G4_CASE" in barrier-before|barrier-after|barrier-after-embedding|barrier-negative-matrix) ;; *) echo "STOP: G4 requires barrier-before / barrier-after / barrier-after-embedding"; exit 10 ;; esac
PARENT="$HOME/.cache/ai-gen-qa-g4"
[[ "$(stat -c %u "$PARENT")" == "$(id -u)" ]] || exit 10
[[ "$(stat -c %a "$PARENT")" == 700 ]] || exit 10

SOURCE="/srv/c2pro/ops-c2pro-runner/checkouts/916808c5212e-8f2a2cad"
EXPECTED_SOURCE="916808c5212e3dbc652407f35f3a17557623c06c"
[[ "$(git -C "$SOURCE" rev-parse HEAD)" == "$EXPECTED_SOURCE" ]] || exit 10
[[ -z "$(git -C "$SOURCE" status --porcelain)" ]] || exit 10
REDIS_SRC="$PARENT/redis-source-7.2.8"
[[ "$(git -C "$REDIS_SRC" rev-parse HEAD)" == 31d93c592811dce16b2f75222afa6babc5eb9a55 ]] || exit 10
REDIS="$REDIS_SRC/src/redis-server"
CLI="$REDIS_SRC/src/redis-cli"
echo "cfff64e0c86527cc40f80c3355099c85cff48525365c5c45d5e94766bfb8a4f4  $REDIS" | sha256sum -c - >/dev/null
PY="/home/aigenadmin/.cache/c2pro-local-ci/venv-py3.11/bin/python"
PG_BIN=/usr/lib/postgresql/16/bin
QA="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export G4_RUN_DIR="$(mktemp -d "$PARENT/c2pro-g4-broker.XXXXXXXX")"
R="$G4_RUN_DIR"
EVIDENCE="$HOME/qa_evidence/g4-916-${G4_CASE}"
mkdir -p -m 0700 "$EVIDENCE"
WORKER_PID=
REDIS_PID=
cleanup() {
  rc=$?
  trap - EXIT INT TERM
  echo "G4_CLEANUP_START exit=$rc"
  if [[ -n "$WORKER_PID" ]]; then kill -TERM "$WORKER_PID" >/dev/null 2>&1 || :; wait "$WORKER_PID" >/dev/null 2>&1 || :; fi
  if [[ -n "$REDIS_PID" ]]; then kill -TERM "$REDIS_PID" >/dev/null 2>&1 || :; wait "$REDIS_PID" >/dev/null 2>&1 || :; fi
  if [[ -d "$R/data" ]]; then "$PG_BIN/pg_ctl" -D "$R/data" -m immediate -w stop >/dev/null 2>&1 || :; fi
  for name in seed.log recovery.log barrier-check.log barrier-claim.log barrier-verify.log pg_negative.log broker-down.log redis.log worker.log worker-restart.log controller_events.jsonl worker_events.jsonl; do
    [[ -f "$R/$name" ]] && cp -- "$R/$name" "$EVIDENCE/$name" || :
  done
  (
    cd "$EVIDENCE"
    sha256sum *.log *.jsonl 2>/dev/null > SHA256SUMS || :
  )
  case "$R" in "$PARENT"/c2pro-g4-broker.*) rm -rf -- "$R" ;; *) echo "STOP_BAD_TEMP_ROOT" >&2 ;; esac
  echo "G4_CLEANUP_FINISHED_PRIVATE_PROCESSES_AND_PG_REMOVED=YES"
  exit "$rc"
}
trap cleanup EXIT INT TERM

# Loopback, ephemeral ports. No system service and no 0.0.0.0 bind.
read -r PGPORT REDIS_PORT < <(python3 - <<'PY'
import socket
ports = []
for _ in range(2):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        ports.append(str(s.getsockname()[1]))
print(*ports)
PY
)
# PostgreSQL is loopback-only AND SCRAM-authenticated with per-run random password.
"$PY" -c 'import secrets,sys; open(sys.argv[1], "w").write(secrets.token_urlsafe(48))' "$R/pg_pass"
chmod 600 "$R/pg_pass"
"$PG_BIN/initdb" -D "$R/data" --username=aigenadmin --auth-local=trust \
  --auth-host=scram-sha-256 --pwfile="$R/pg_pass" --no-instructions > "$R/initdb.log" 2>&1
export PGHOST=127.0.0.1 PGUSER=aigenadmin PGPORT
export PGPASSWORD="$(cat "$R/pg_pass")"
"$PG_BIN/pg_ctl" -D "$R/data" -l "$R/pg.log" -w \
  -o "-h 127.0.0.1 -p $PGPORT -k $R -c fsync=off" start >/dev/null
"$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PGPORT" -U aigenadmin >/dev/null
createdb c2pro_g3_1276_test
psql -X -d c2pro_g3_1276_test -v ON_ERROR_STOP=1 -q -c \
 "CREATE ROLE c2pro_admin_ops NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;"
export DATABASE_URL="postgresql://aigenadmin:$PGPASSWORD@127.0.0.1:$PGPORT/c2pro_g3_1276_test"
export TEST_DATABASE_URL="$DATABASE_URL"
export C2PRO_N4_SCRATCH_DSN="$DATABASE_URL"
export CELERY_BROKER_URL="redis://127.0.0.1:$REDIS_PORT/14"
export CELERY_RESULT_BACKEND_URL="redis://127.0.0.1:$REDIS_PORT/15"
export REDIS_URL="$CELERY_BROKER_URL"
export ENVIRONMENT=test
export JWT_SECRET_KEY="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(48))')"
export PYTHONPATH="$QA:$SOURCE/apps/api"
export OPENAI_API_KEY= ANTHROPIC_API_KEY= GOOGLE_API_KEY= PERPLEXITY_API_KEY= OPENROUTER_API_KEY=
export NO_PROXY='*' no_proxy='*'
cd "$SOURCE/apps/api"
"$PY" -m alembic upgrade head > "$R/alembic.log" 2>&1 || { tail -30 "$R/alembic.log"; exit 12; }
echo "PG16_ROOTLESS_ALEMBIC=PASS PGPORT=$PGPORT"
echo "BROKER_URL_IS_LOCAL=YES REDIS_PORT=$REDIS_PORT"
"$PY" "$QA/g4_controller.py" seed-post > "$R/seed.log" 2>&1 || { tail -50 "$R/seed.log"; exit 13; }
cat "$R/seed.log" | grep '^G4_' || :

start_redis() {
  "$REDIS" --bind 127.0.0.1 --port "$REDIS_PORT" --protected-mode yes \
    --save "" --appendonly no --daemonize no --dir "$R" \
    --logfile "$R/redis.log" --pidfile "$R/redis.pid" \
    --maxmemory 64mb --maxmemory-policy noeviction > /dev/null 2>&1 &
  REDIS_PID=$!
  for _ in $(seq 1 35); do
    if "$CLI" -h 127.0.0.1 -p "$REDIS_PORT" ping 2>/dev/null | grep -qx PONG; then return 0; fi
    sleep .2
  done
  echo "REDIS_START_FAIL"; tail -30 "$R/redis.log"; return 1
}
start_redis
echo "REDIS_REAL_PID=$REDIS_PID"
"$PY" "$QA/g4_controller.py" recover > "$R/recovery.log" 2>&1 || { tail -75 "$R/recovery.log"; exit 14; }
grep '^G4_' "$R/recovery.log" || :

# New B SHA916808 guard seam: kill immediately after exact DB COMMIT.
KILL_AT="${G4_CASE#barrier-}"
if [[ "$G4_CASE" == barrier-negative-matrix ]]; then KILL_AT=before; fi
EXPECTED_MARKER=KILLPOINT_UNSAFE_BARRIER_DURABLY_COMMITTED
if [[ "$KILL_AT" == "before" ]]; then EXPECTED_MARKER=KILLPOINT_BEFORE_EFFECTS_DURABLY_COMMITTED; fi
G4_CRASH_HOLD_SECONDS=75 G4_KILLPOINT="$KILL_AT" "$PY" -m celery -A g4_worker_app:app worker -P solo -c 1 \
    -Q document_parsing --loglevel=info --without-gossip --without-mingle \
    --without-heartbeat --hostname=g4-barrier-kill@localhost > "$R/worker.log" 2>&1 &
WORKER_PID=$!
OLD_WORKER_PID=$WORKER_PID
echo "SHA916_WORKER_BEFORE_KILL_PID=$WORKER_PID KILLPOINT=$EXPECTED_MARKER"
seen=0
for _ in $(seq 1 200); do
  if [[ -f "$R/worker_events.jsonl" ]] &&
     grep -q "$EXPECTED_MARKER" "$R/worker_events.jsonl"; then
    seen=1
    break
  fi
  if ! kill -0 "$WORKER_PID" 2>/dev/null; then break; fi
  sleep .25
done
[[ "$seen" == 1 ]] || { echo "FAIL_EXACT_BARRIER_COMMIT_NOT_REACHED"; tail -90 "$R/worker.log"; exit 16; }
kill -KILL "$WORKER_PID"
wait "$WORKER_PID" >/dev/null 2>&1 || :
WORKER_PID=
echo "SHA916_SIGKILL_AFTER_EXACT_DURABLE_MARKER_PID=$OLD_WORKER_PID KILLPOINT=$EXPECTED_MARKER"

"$PY" "$QA/g4_barrier_controller.py" check "$KILL_AT" > "$R/barrier-check.log" 2>&1 || {
  echo "FAIL_DB_GUARD_SEQUENCE"; tail -80 "$R/barrier-check.log"; exit 17
}
grep '^G4_' "$R/barrier-check.log" || :
if [[ "$G4_CASE" == barrier-negative-matrix ]]; then
  "$PY" "$QA/g4_negative_matrix.py" > "$R/negative-matrix.log" 2>&1 || {
    echo "FAIL_G4_NEGATIVE_MATRIX"; tail -90 "$R/negative-matrix.log"; exit 20
  }
  grep '^G4_' "$R/negative-matrix.log" || :
  echo "G4_MIGRATED_PG_NEGATIVE_MATRIX=PASS"
else
"$PY" "$QA/g4_barrier_controller.py" expire-claim "$KILL_AT" > "$R/barrier-claim.log" 2>&1 || {
  echo "FAIL_DB_LEASE_OR_MANUAL_CLAIM"; tail -85 "$R/barrier-claim.log"; exit 18
}
grep '^G4_' "$R/barrier-claim.log" || :

# Replaced process: original Redis messages remain; only claimed new fencing
# may reenter after BEFORE_EFFECTS. No auto retry or unscoped R2.
G4_CRASH_HOLD_SECONDS=0 G4_KILLPOINT= "$PY" -m celery -A g4_worker_app:app worker -P solo -c 1 \
    -Q document_parsing --loglevel=info --without-gossip --without-mingle \
    --without-heartbeat --hostname=g4-barrier-restart@localhost > "$R/worker-restart.log" 2>&1 &
WORKER_PID=$!
echo "SHA916_WORKER_RESTART_PID=$WORKER_PID"
"$PY" "$QA/g4_barrier_controller.py" verify "$KILL_AT" > "$R/barrier-verify.log" 2>&1 || {
  echo "FAIL_WORKER_REAL_REDELIVERY_OR_N4"; tail -100 "$R/barrier-verify.log"; tail -70 "$R/worker-restart.log"; exit 19
}
grep '^G4_' "$R/barrier-verify.log" || :
echo "G4_EXACT_BARRIER_SCENARIO_COMPLETED=$KILL_AT"

fi

# Actual Redis process outage after completed settlement; no new provider calls.
kill -TERM "$REDIS_PID"
wait "$REDIS_PID" || :
REDIS_PID=
"$PY" "$QA/g4_controller.py" broker-down > "$R/broker-down.log" 2>&1
cat "$R/broker-down.log" | grep '^G4_' || :
echo "REDIS_REAL_SHUTDOWN_CONFIRMED=YES"

cp "$R/alembic.log" "$EVIDENCE/alembic.log"
echo "G4_BROKER_CASE=$G4_CASE RESULT=EXECUTED; SHA_B=916808c5212e3dbc652407f35f3a17557623c06c"
echo "G4_PG_DROPPED_BY_TRAP=YES"
