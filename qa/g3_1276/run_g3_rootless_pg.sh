#!/usr/bin/env bash
# Rootless, isolated PostgreSQL 16 bootstrap for QA regression only.
# No system service, no external egress, no shared PostgreSQL.
set -euo pipefail
umask 077
case "${1:-}" in legacy|recovery) export G3_CASE="$1" ;; *) echo "usage: $0 legacy|recovery"; exit 2 ;; esac
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PG_BIN=/usr/lib/postgresql/16/bin
for bin in initdb pg_ctl pg_isready; do [[ -x "$PG_BIN/$bin" ]] || exit 10; done
[[ "$(id -un)" == "aigenadmin" ]] || { echo "STOP: wrong user"; exit 10; }
PRIVATE_PARENT="$HOME/.cache/ai-gen-qa-g4"
mkdir -p -m 0700 -- "$PRIVATE_PARENT"
[[ "$(stat -c %u "$PRIVATE_PARENT")" == "$(id -u)" ]] || exit 10
[[ "$(stat -c %a "$PRIVATE_PARENT")" == "700" ]] || exit 10
export C2PRO_G3_EPHEMERAL_PG_DIR="$(mktemp -d "$PRIVATE_PARENT/c2pro-g4-pg.XXXXXXXX")"
ROOT="$C2PRO_G3_EPHEMERAL_PG_DIR"
cleanup() {
  local rc=$?
  trap - EXIT
  if [[ -d "$ROOT/data" ]]; then
    "$PG_BIN/pg_ctl" -D "$ROOT/data" -m immediate -w stop >/dev/null 2>&1 || :
  fi
  case "$ROOT" in "$PRIVATE_PARENT"/c2pro-g4-pg.*) rm -rf -- "$ROOT" ;; *) echo "BAD TEMP PATH" >&2 ;; esac
  echo "ROOTLESS_PG16_TERMINATED_AND_REMOVED=YES"
  exit "$rc"
}
trap cleanup EXIT INT TERM

"$PG_BIN/initdb" -D "$ROOT/data" --username=aigenadmin \
    --auth-local=trust --auth-host=trust --no-instructions >"$ROOT/initdb.log" 2>&1
export PGHOST=127.0.0.1
export PGUSER=aigenadmin
export PGPASSWORD=
export PGPORT="$(python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
"$PG_BIN/pg_ctl" -D "$ROOT/data" -l "$ROOT/server.log" -w \
   -o "-h 127.0.0.1 -p $PGPORT -k $ROOT -c fsync=off" start >/dev/null
"$PG_BIN/pg_isready" -h 127.0.0.1 -p "$PGPORT" -U aigenadmin >/dev/null
echo "ROOTLESS_PG16_RUNNING=YES PG_PORT=$PGPORT PG_OWNER=$(id -un)"
# Legacy/recovery wrapper delegates to common exact-SHA guard and real PG tests.
bash "$HERE/run_g3_common.sh"
