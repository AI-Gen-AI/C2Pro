#!/bin/bash
set -euo pipefail

echo "[run_worker.sh] Starting Celery worker..."
exec celery -A src.core.tasks.celery_app.celery_app worker \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --concurrency="${CELERY_CONCURRENCY:-2}" \
  --queues="${CELERY_QUEUES:-document_parsing}" \
  --without-gossip \
  --without-mingle
