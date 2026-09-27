#!/bin/bash
# Backward-compatible API entrypoint.
set -euo pipefail
exec bash /app/scripts/run_api.sh
