#!/usr/bin/env bash
# Delegates to common disposable-PG bootstrap; no global service changes.
set -euo pipefail
export G3_CASE=recovery
exec bash "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/run_g3_common.sh"
