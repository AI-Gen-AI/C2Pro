#!/usr/bin/env python3
"""Project the P0-SEC-B Supabase CLI migration from its canonical Alembic source.

Alembic is authoritative; the supabase/ CLI migrations must stay in sync.
Rather than maintain two hand-written copies of security-critical DDL, the
mirror is generated from the Alembic module and a parity test re-runs this
generator to prove the checked-in mirror still matches.

Usage:  python apps/api/scripts/generate_p0_sec_b_mirror.py [--check]
"""

from __future__ import annotations

import argparse
import sys

from p0_sec_b_common import MIRROR_PATH, REPO_ROOT, emitted_sql

HEADER = """-- P0-SEC-B: replace 24 fail-open COALESCE RLS policies with fail-closed NULLIF.
--
-- GENERATED FILE -- DO NOT EDIT BY HAND.
-- Canonical source: apps/api/alembic/versions/20260905_0001_p0_sec_b_fail_closed_policies.py
-- Regenerate with:  python apps/api/scripts/generate_p0_sec_b_mirror.py
-- Parity is enforced by apps/api/tests/security/test_p0_sec_b_fail_closed_migration.py
--
-- Audit record: docs/security/P0-SEC-B-fail-closed-policies.md
"""


def render() -> str:
    return f"{HEADER}\n{emitted_sql('upgrade')}\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify parity, write nothing")
    args = parser.parse_args()

    rendered = render()
    if args.check:
        if not MIRROR_PATH.exists():
            print(f"MISSING mirror: {MIRROR_PATH}", file=sys.stderr)
            return 1
        if MIRROR_PATH.read_text(encoding="utf-8") != rendered:
            print(
                "Supabase mirror is out of sync with the canonical Alembic migration.\n"
                "Run: python apps/api/scripts/generate_p0_sec_b_mirror.py",
                file=sys.stderr,
            )
            return 1
        print("P0-SEC-B mirror parity: OK")
        return 0

    MIRROR_PATH.parent.mkdir(parents=True, exist_ok=True)
    MIRROR_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {MIRROR_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    raise SystemExit(main())
