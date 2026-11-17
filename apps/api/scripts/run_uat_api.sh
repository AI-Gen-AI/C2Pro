#!/usr/bin/env bash
# Isolated UAT bootstrap: creates the restricted admin capability role and
# governed LangGraph checkpoint schema before the normal Alembic migration.
# This entrypoint is UAT-only; do not use it in production without review.
set -euo pipefail

echo "[run_uat_api.sh] Preparing restricted database roles and checkpoints..."
python scripts/admin_ops_bootstrap.py
python scripts/checkpoint_bootstrap.py

echo "[run_uat_api.sh] Starting standard API and migrations..."
exec bash scripts/run_api.sh
