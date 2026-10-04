#!/bin/bash
set -euo pipefail

echo "[run_scheduler.sh] Waiting for database schema readiness..."
python scripts/wait_for_schema.py
echo "[run_scheduler.sh] Starting Celery beat scheduler..."
exec celery -A src.core.tasks.celery_entrypoint.celery_app beat \
  --loglevel="${CELERY_LOG_LEVEL:-warning}" \
  --schedule="${CELERY_BEAT_SCHEDULE_FILE:-/tmp/c2pro-celerybeat-schedule}"
