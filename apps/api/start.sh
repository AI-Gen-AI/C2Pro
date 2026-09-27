#!/bin/bash
# Backward-compatible API entrypoint. Production worker and scheduler have
# dedicated service start commands and independent lifecycles.
set -euo pipefail
exec bash /app/scripts/run_api.sh
