#!/usr/bin/env python3
"""Project the P0-SEC-A Supabase CLI migration from its canonical Alembic source.

`CLAUDE.md` makes Alembic authoritative while requiring the `supabase/` CLI
migrations to stay in sync. Rather than maintain two hand-written copies of
security-critical DDL, the mirror is generated from the Alembic module and a
parity test re-runs this generator to prove the checked-in mirror still matches.

Usage:  python apps/api/scripts/generate_p0_sec_a_mirror.py [--check]
"""

from __future__ import annotations

import argparse
import sys

from p0_sec_a_common import MIRROR_PATH, REPO_ROOT, emitted_sql

HEADER = """-- P0-SEC-A: contain external Supabase Data API access to the public schema.
--
-- GENERATED FILE -- DO NOT EDIT BY HAND.
-- Canonical source: apps/api/alembic/versions/20260902_0001_p0_sec_a_data_api_containment.py
-- Regenerate with:  python apps/api/scripts/generate_p0_sec_a_mirror.py
-- Parity is enforced by apps/api/tests/security/test_p0_sec_a_containment.py
--
-- Audit record: blackboard/SESSION_2026-09-02_p0-sec-supabase-audit.md
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
                "Run: python apps/api/scripts/generate_p0_sec_a_mirror.py",
                file=sys.stderr,
            )
            return 1
        print("P0-SEC-A mirror parity: OK")
        return 0

    MIRROR_PATH.parent.mkdir(parents=True, exist_ok=True)
    MIRROR_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {MIRROR_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    raise SystemExit(main())
