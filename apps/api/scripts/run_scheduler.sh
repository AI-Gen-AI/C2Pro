#!/bin/bash
set -euo pipefail

echo "[run_scheduler.sh] Starting Celery beat scheduler..."
exec celery -A src.core.tasks.celery_app.celery_app beat \
  --loglevel="${CELERY_LOG_LEVEL:-info}"
