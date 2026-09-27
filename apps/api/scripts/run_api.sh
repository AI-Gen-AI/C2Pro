#!/bin/bash
set -euo pipefail

echo "[run_api.sh] Running Alembic migrations..."
alembic upgrade head
echo "[run_api.sh] Migrations complete."

echo "[run_api.sh] Starting uvicorn API on port ${PORT:-8000}..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
