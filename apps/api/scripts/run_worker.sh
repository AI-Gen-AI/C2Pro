#!/bin/bash
set -euo pipefail

echo "[run_worker.sh] Waiting for database schema readiness..."
python scripts/wait_for_schema.py
echo "[run_worker.sh] Starting Celery worker..."
exec celery -A src.core.tasks.celery_entrypoint.celery_app worker \
  --loglevel="${CELERY_LOG_LEVEL:-warning}" \
  --concurrency="${CELERY_CONCURRENCY:-2}" \
  --queues="${CELERY_QUEUES:-document_parsing}" \
  --without-gossip \
  --without-mingle
