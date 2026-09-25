#!/bin/bash
# Startup script: runs DB migrations, then starts Celery worker + API in the same container.
# The Celery worker and API share /app/uploads so LocalFileStorageService works without R2.
set -e

echo "[start.sh] Running Alembic migrations..."
alembic upgrade head
echo "[start.sh] Migrations complete."

# Restart Celery worker automatically if it crashes.
_start_celery() {
    while true; do
        echo "[start.sh] Starting Celery worker..."
        # --without-gossip/--without-mingle: this is a single worker node, so
        # worker-to-worker gossip and startup mingle are pure Redis pub/sub noise.
        # Heartbeat is intentionally kept (broker-connection liveness).
        celery -A src.core.tasks.celery_app.celery_app worker \
            --loglevel=info \
            --concurrency=2 \
            --queues=document_parsing \
            --without-gossip \
            --without-mingle \
            || true
        echo "[start.sh] Celery worker exited. Restarting in 5s..."
        sleep 5
    done
}

_start_celery &
CELERY_LOOP_PID=$!

# Trap SIGTERM/SIGINT to clean up the background loop.
trap "kill $CELERY_LOOP_PID 2>/dev/null; exit 0" TERM INT

echo "[start.sh] Starting uvicorn API on port ${PORT:-8000}..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
