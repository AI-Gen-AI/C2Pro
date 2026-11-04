#!/usr/bin/env bash
set -euo pipefail

# Only intended for the isolated, owner-authorized, synthetic ProjectGraph pilot.
# Uses the pilot's own DATABASE_URL. Never point this to a production DSN.
python scripts/admin_ops_bootstrap.py
python scripts/checkpoint_bootstrap.py
