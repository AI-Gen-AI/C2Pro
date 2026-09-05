#!/usr/bin/env python3
"""Catalog-driven Supabase security gate for the P0-SEC-A finding classes.

The Supabase Security Advisor is a dashboard, not a gate, and it missed two of
the three most serious findings in the 2026-09-02 audit: it stops looking at a
table once RLS is enabled, so a permissive ``USING (true)`` policy over live
rows produced no lint at all. These checks read `pg_catalog` directly so that
class cannot regress silently.

Scope is deliberately limited to what P0-SEC-A remediates. Function EXECUTE
grants, mutable search_path and fail-open ``COALESCE`` policies are real
findings but belong to P0-SEC-B/D; they are reported as INFO here and must not
fail the build until their own remediation lands.

Usage:
    DATABASE_URL=postgresql://... python apps/api/scripts/supabase_security_lint.py
Exit code 1 if any BLOCKING violation is found.
DSN must be supplied via DATABASE_URL environment variable only (not CLI).
"""

from __future__ import annotations

import argparse
import os
import sys

EXTERNAL_ROLES = ("anon", "authenticated")

# Objects that must never be reachable through the Data API.
PROTECTED_TABLES = (
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
    "evidence_claims",
    "evidence_extraction_events",
    "category_centroids",
    "project_snapshots_2026_06",
    "project_snapshots_2026_07",
    "project_snapshots_2026_08",
    "project_snapshots_default",
)

# NOTE: literal "%" in LIKE patterns is doubled because this query is executed
# with bound parameters; psycopg2 would otherwise treat "%p" as a placeholder.
Q_PERMISSIVE_POLICY = """
SELECT tablename, policyname, roles::text, cmd
  FROM pg_policies
 WHERE schemaname = 'public'
   AND (qual = 'true' OR qual IS NULL AND cmd = 'SELECT')
   AND (roles::text LIKE '%%public%%' OR roles::text LIKE '%%anon%%'
        OR roles::text LIKE '%%authenticated%%')
   AND tablename = ANY(%(protected)s);
"""

Q_RLS_DISABLED = """
SELECT c.relname
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
   AND NOT c.relrowsecurity
   AND c.relname = ANY(%(protected)s);
"""

Q_EXTERNAL_GRANTS = """
SELECT table_name, grantee, string_agg(privilege_type, ',' ORDER BY privilege_type)
  FROM information_schema.role_table_grants
 WHERE table_schema = 'public' AND grantee = ANY(%(roles)s)
 GROUP BY table_name, grantee
 ORDER BY table_name, grantee;
"""

Q_DEFAULT_ACL = """
SELECT pg_get_userbyid(d.defaclrole), d.defaclobjtype, d.defaclacl::text
  FROM pg_default_acl d
  JOIN pg_namespace n ON n.oid = d.defaclnamespace
 WHERE n.nspname = 'public' AND d.defaclobjtype IN ('r', 'S');
"""

Q_INFO_FAIL_OPEN = """
SELECT tablename, policyname FROM pg_policies
 WHERE schemaname = 'public' AND qual LIKE '%COALESCE%';
"""


def run(dsn: str) -> int:
    try:
        import psycopg
        conn = psycopg.connect(dsn)
    except ImportError:  # pragma: no cover - environment dependent
        import psycopg2
        conn = psycopg2.connect(dsn)

    blocking: list[str] = []
    info: list[str] = []
    protected = list(PROTECTED_TABLES)

    with conn, conn.cursor() as cur:
        cur.execute(Q_PERMISSIVE_POLICY, {"protected": protected})
        for table, policy, roles, cmd in cur.fetchall():
            blocking.append(
                f"permissive policy {policy} on {table} ({cmd} to {roles}) "
                f"exposes a protected table"
            )

        cur.execute(Q_RLS_DISABLED, {"protected": protected})
        for (table,) in cur.fetchall():
            blocking.append(f"RLS disabled on protected table {table}")

        cur.execute(Q_EXTERNAL_GRANTS, {"roles": list(EXTERNAL_ROLES)})
        for table, grantee, privs in cur.fetchall():
            blocking.append(
                f"{grantee} holds {privs} on public.{table}; "
                f"no Data API dependency is proven for it"
            )

        cur.execute(Q_DEFAULT_ACL)
        for owner, objtype, acl in cur.fetchall():
            kind = "TABLES" if objtype == "r" else "SEQUENCES"
            for role in EXTERNAL_ROLES:
                if f"{role}=" in (acl or ""):
                    blocking.append(
                        f"default privileges for {owner} grant {kind} to {role}; "
                        f"new objects would be exposed on creation"
                    )

        cur.execute(Q_INFO_FAIL_OPEN)
        for table, policy in cur.fetchall():
            info.append(f"fail-open COALESCE policy {policy} on {table} (P0-SEC-B)")

    for line in info:
        print(f"INFO     {line}")
    for line in blocking:
        print(f"BLOCKING {line}")

    if blocking:
        print(f"\nFAILED: {len(blocking)} blocking violation(s).")
        return 1
    print(f"\nPASSED: no blocking violations ({len(info)} informational).")
    return 0


def main() -> int:
    # Parse args with no custom arguments so any unrecognized flag (including the
    # formerly-supported --dsn) is rejected by argparse. DSN must come from the
    # environment, never from the CLI (S8706: CLI args flow to DB connection).
    argparse.ArgumentParser().parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("no DSN: set DATABASE_URL", file=sys.stderr)
        return 2
    return run(dsn.replace("postgresql+asyncpg://", "postgresql://"))


if __name__ == "__main__":
    raise SystemExit(main())
