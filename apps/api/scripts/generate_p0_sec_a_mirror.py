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
import importlib.util
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    REPO_ROOT
    / "apps/api/alembic/versions/20260902_0001_p0_sec_a_data_api_containment.py"
)
MIRROR = REPO_ROOT / "supabase/migrations/20260902000100_p0_sec_a_data_api_containment.sql"

HEADER = """-- P0-SEC-A: contain external Supabase Data API access to the public schema.
--
-- GENERATED FILE -- DO NOT EDIT BY HAND.
-- Canonical source: apps/api/alembic/versions/20260902_0001_p0_sec_a_data_api_containment.py
-- Regenerate with:  python apps/api/scripts/generate_p0_sec_a_mirror.py
-- Parity is enforced by apps/api/tests/security/test_p0_sec_a_containment.py
--
-- Audit record: blackboard/SESSION_2026-09-02_p0-sec-supabase-audit.md
"""


def load_migration() -> types.ModuleType:
    """Import the migration with a stub `alembic.op` that records emitted SQL."""
    collected: list[str] = []
    stub = types.ModuleType("alembic")
    stub.op = types.SimpleNamespace(execute=lambda sql: collected.append(str(sql)))
    saved = sys.modules.get("alembic")
    sys.modules["alembic"] = stub
    try:
        spec = importlib.util.spec_from_file_location("p0_sec_a_migration", MIGRATION)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise RuntimeError(f"cannot load {MIGRATION}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if saved is not None:
            sys.modules["alembic"] = saved
        else:
            del sys.modules["alembic"]
    module._collected = collected  # type: ignore[attr-defined]
    return module


def emitted_sql(module: types.ModuleType, direction: str) -> list[str]:
    module._collected.clear()  # type: ignore[attr-defined]
    getattr(module, direction)()
    return [s.strip().rstrip(";") + ";" for s in module._collected]  # type: ignore[attr-defined]


def render() -> str:
    module = load_migration()
    body = "\n\n".join(emitted_sql(module, "upgrade"))
    return f"{HEADER}\n{body}\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify parity, write nothing")
    args = parser.parse_args()

    rendered = render()
    if args.check:
        if not MIRROR.exists():
            print(f"MISSING mirror: {MIRROR}", file=sys.stderr)
            return 1
        if MIRROR.read_text(encoding="utf-8") != rendered:
            print(
                "Supabase mirror is out of sync with the canonical Alembic migration.\n"
                "Run: python apps/api/scripts/generate_p0_sec_a_mirror.py",
                file=sys.stderr,
            )
            return 1
        print("P0-SEC-A mirror parity: OK")
        return 0

    MIRROR.parent.mkdir(parents=True, exist_ok=True)
    MIRROR.write_text(rendered, encoding="utf-8")
    print(f"wrote {MIRROR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
