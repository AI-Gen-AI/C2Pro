#!/usr/bin/env python3
"""Catalog-driven Supabase security gate for P0-SEC-A and P0-SEC-B findings.

The Supabase Security Advisor is a dashboard, not a gate, and it missed two of
the three most serious findings in the 2026-09-02 audit: it stops looking at a
table once RLS is enabled, so a permissive ``USING (true)`` policy over live
rows produced no lint at all. These checks read `pg_catalog` directly so that
class cannot regress silently.

P0-SEC-A scope (always BLOCKING):
    - Permissive policies on protected tables
    - RLS disabled on protected tables
    - External-role grants
    - Default-privilege grants to external roles

P0-SEC-B scope (BLOCKING as of 20260905_0001):
    - COALESCE fail-open expressions in any public-schema RLS policy (any table)
    - Excess permissive FOR ALL policies by the known legacy names

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

# ── P0-SEC-B: COALESCE fail-open detection (BLOCKING since 20260905_0001) ──────
#
# Detects any RLS policy whose USING or WITH CHECK expression contains the
# COALESCE fail-open pattern regardless of which table it is on.  Raised from
# INFO to BLOCKING because the migration that removes all 24 instances has
# landed; any surviving COALESCE now means the migration was partially applied
# or a new fail-open policy was introduced.
Q_BLOCKING_FAIL_OPEN = """
SELECT tablename, policyname,
       CASE WHEN qual LIKE '%%COALESCE%%' AND with_check LIKE '%%COALESCE%%'
            THEN 'USING+WITH CHECK'
            WHEN qual LIKE '%%COALESCE%%' THEN 'USING'
            ELSE 'WITH CHECK'
       END AS coalesce_in
  FROM pg_policies
 WHERE schemaname = 'public'
   AND (qual LIKE '%%COALESCE%%' OR with_check LIKE '%%COALESCE%%');
"""

# ── P0-SEC-B: excess permissive FOR ALL policies (BLOCKING) ────────────────────
#
# These named policies are the legacy FOR ALL overrides that should have been
# removed by the P0-SEC-B migration.  Their presence means the migration was
# not applied or was reverted.
_EXCESS_POLICY_NAMES: tuple[tuple[str, str], ...] = (
    ("analyses",          "tenant_isolation_analyses"),
    ("alerts",            "tenant_isolation_alerts"),
    ("coherence_results", "tenant_isolation_coherence_results"),
    ("clause_embeddings", "tenant_isolation_clause_embeddings"),
    ("clause_embeddings", "clause_embeddings_tenant_isolation"),
)


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

        # P0-SEC-B: COALESCE fail-open (BLOCKING)
        cur.execute(Q_BLOCKING_FAIL_OPEN)
        for table, policy, location in cur.fetchall():
            blocking.append(
                f"fail-open COALESCE policy {policy} on {table} ({location}); "
                f"P0-SEC-B migration (20260905_0001) must be applied"
            )

        # P0-SEC-B: excess permissive FOR ALL policies (BLOCKING)
        for table, policy in _EXCESS_POLICY_NAMES:
            cur.execute(
                "SELECT COUNT(*) FROM pg_policies "
                "WHERE schemaname='public' AND tablename=%s AND policyname=%s",
                (table, policy),
            )
            row = cur.fetchone()
            if row and row[0] > 0:
                blocking.append(
                    f"excess FOR ALL policy {policy} on {table} still present; "
                    f"P0-SEC-B migration (20260905_0001) must be applied"
                )

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
