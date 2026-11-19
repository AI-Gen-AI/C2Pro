#!/usr/bin/env bash
# G4-BROKER: rootless Redis 7.2.8 and a separately forked Celery worker, disposable PG16.
# No shared services. No production credentials, no real providers, no external model network.
set -euo pipefail
umask 077
[[ "$(id -un)" == aigenadmin ]] || { echo "STOP: wrong user"; exit 10; }
PARENT="$HOME/.cache/ai-gen-qa-g4"
[[ "$(stat -c %u "$PARENT")" == "$(id -u)" ]] || exit 10
[[ "$(stat -c %a "$PARENT")" == 700 ]] || exit 10

SOURCE="/srv/c2pro/ops-c2pro-runner/checkouts/14c35b7f0b89-214064af"
EXPECTED_SOURCE="14c35b7f0b8933a4ff0b4f330f3941073809ff24"
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
EVIDENCE="$HOME/qa_evidence/g4-broker"
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
  for name in seed.log recovery.log verify.log broker-down.log redis.log worker.log controller_events.jsonl worker_events.jsonl; do
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
"$PG_BIN/initdb" -D "$R/data" --username=aigenadmin --auth-local=trust --auth-host=trust --no-instructions > "$R/initdb.log" 2>&1
export PGHOST=127.0.0.1 PGUSER=aigenadmin PGPASSWORD= PGPORT
"$PG_BIN/pg_ctl" -D "$R/data" -l "$R/pg.log" -w \
  -o "-h 127.0.0.1 -p $PGPORT -k $R -c fsync=off" start >/dev/null
"$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PGPORT" -U aigenadmin >/dev/null
createdb c2pro_g3_1276_test
psql -X -d c2pro_g3_1276_test -v ON_ERROR_STOP=1 -q -c \
 "CREATE ROLE c2pro_admin_ops NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;"
export DATABASE_URL="postgresql://aigenadmin:@127.0.0.1:$PGPORT/c2pro_g3_1276_test"
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

# Worker runs as an independent OS process, with actual registered C2Pro Celery tasks.
"$PY" -m celery -A g4_worker_app:app worker -P solo -c 1 \
  -Q document_parsing --loglevel=info --without-gossip --without-mingle \
  --without-heartbeat --hostname=g4-test@localhost > "$R/worker.log" 2>&1 &
WORKER_PID=$!
echo "CELERY_WORKER_OS_PID=$WORKER_PID CONTROLLER_OS_PID=$$"
"$PY" "$QA/g4_controller.py" verify > "$R/verify.log" 2>&1 || {
  echo "G4_REAL_WORKER_VERIFY_FAIL"
  tail -70 "$R/verify.log"
  tail -75 "$R/worker.log"
  exit 15
}
grep '^G4_' "$R/verify.log" || :
echo "CELERY_SEPARATE_WORKER_N4=PASS"

# Actual Redis process outage after completed settlement; no new provider calls.
kill -TERM "$REDIS_PID"
wait "$REDIS_PID" || :
REDIS_PID=
"$PY" "$QA/g4_controller.py" broker-down > "$R/broker-down.log" 2>&1
cat "$R/broker-down.log" | grep '^G4_' || :
echo "REDIS_REAL_SHUTDOWN_CONFIRMED=YES"

cp "$R/alembic.log" "$EVIDENCE/alembic.log"
echo "G4_BROKER_RESULT=PASS_LIMITED; broker real, ACK loss injected at client boundary; no worker-crash proof"
echo "G4_PG_DROPPED_BY_TRAP=YES"
