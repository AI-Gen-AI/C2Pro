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

P0-SEC-D scope (BLOCKING as of 20260906000100):
    - Any SECURITY DEFINER function (any schema) whose EXECUTE privilege is
      held by PUBLIC, anon, or authenticated -- including a NULL proacl
      (Postgres's own default grants PUBLIC execute on every new function
      unless revoked). service_role is intentionally excluded: a backend-
      only SECURITY DEFINER RPC may legitimately grant it EXECUTE.

Usage:
    DATABASE_URL=postgresql://... python apps/api/scripts/supabase_security_lint.py
Exit code 1 if any BLOCKING violation is found.
DSN must be supplied via DATABASE_URL environment variable only (not CLI).
"""

from __future__ import annotations

import argparse
import os
import sys

# ── Gate composition: scope membership sets ─────────────────────────────────
#
# Each historical gate validates only the control family it owns.  The global
# linter (scope=None) validates all families.  These frozensets drive the
# scope-aware run() dispatcher so the logic stays in one place and is testable
# without a live database.
#
# _SCOPE_P0_SEC_A activates: permissive-policy, RLS-disabled, external-grant,
#                             and default-ACL checks.
# _SCOPE_P0_SEC_B activates: COALESCE fail-open and excess-FOR-ALL checks.
# _SCOPE_P0_SEC_D activates: SECURITY DEFINER PUBLIC/anon/authenticated
#                             EXECUTE checks.
# None (global)   activates: all three families.
_SCOPE_P0_SEC_A: frozenset[str | None] = frozenset({"p0_sec_a", None})
_SCOPE_P0_SEC_B: frozenset[str | None] = frozenset({"p0_sec_b", None})
_SCOPE_P0_SEC_D: frozenset[str | None] = frozenset({"p0_sec_d", None})

# Explicit allowlist of recognised scope values.  Any value not in this set is
# rejected by run() before any database work occurs.  This prevents an unknown
# scope from silently setting both run_a and run_b to False and reaching
# "PASSED: no blocking violations" with zero checks executed (fail-open).
_VALID_SCOPES: frozenset[str | None] = frozenset(
    {None, "p0_sec_a", "p0_sec_b", "p0_sec_d"}
)

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


# ── P0-SEC-D: SECURITY DEFINER PUBLIC/anon/authenticated EXECUTE ───────────────
#
# ``acldefault('f', p.proowner)`` reproduces the effective default ACL for a
# function whose ``proacl`` is NULL (Postgres grants PUBLIC EXECUTE on every
# new function unless revoked), so an untouched SECURITY DEFINER function is
# caught even before anything has explicitly granted it to anyone.
# service_role is deliberately not in the grantee list: a backend-only
# SECURITY DEFINER RPC (e.g. public.create_tenant_and_owner) may legitimately
# grant it EXECUTE, and that is a deliberate, reviewed choice, not a leak.
Q_SECURITY_DEFINER_PUBLIC_EXECUTE = """
SELECT DISTINCT n.nspname, p.proname,
       pg_get_function_identity_arguments(p.oid) AS args
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  JOIN LATERAL aclexplode(
      COALESCE(p.proacl, acldefault('f', p.proowner))
  ) AS acl ON true
 WHERE p.prosecdef
   AND n.nspname NOT IN ('pg_catalog', 'information_schema')
   AND acl.privilege_type = 'EXECUTE'
   AND (
       acl.grantee = 0
       OR pg_get_userbyid(acl.grantee) IN ('anon', 'authenticated')
   );
"""


def _check_p0_sec_d(cur: object, blocking: list[str]) -> None:
    """Execute P0-SEC-D control-family checks against an open cursor."""
    cur.execute(Q_SECURITY_DEFINER_PUBLIC_EXECUTE)  # type: ignore[union-attr]
    for schema, name, args in cur.fetchall():  # type: ignore[union-attr]
        blocking.append(
            f"SECURITY DEFINER function {schema}.{name}({args}) is executable "
            f"by PUBLIC/anon/authenticated with no reviewed REVOKE"
        )


def _check_p0_sec_a(cur: object, protected: list[str], blocking: list[str]) -> None:
    """Execute P0-SEC-A control-family checks against an open cursor."""
    cur.execute(Q_PERMISSIVE_POLICY, {"protected": protected})  # type: ignore[union-attr]
    for table, policy, roles, cmd in cur.fetchall():  # type: ignore[union-attr]
        blocking.append(
            f"permissive policy {policy} on {table} ({cmd} to {roles}) "
            f"exposes a protected table"
        )

    cur.execute(Q_RLS_DISABLED, {"protected": protected})  # type: ignore[union-attr]
    for (table,) in cur.fetchall():  # type: ignore[union-attr]
        blocking.append(f"RLS disabled on protected table {table}")

    cur.execute(Q_EXTERNAL_GRANTS, {"roles": list(EXTERNAL_ROLES)})  # type: ignore[union-attr]
    for table, grantee, privs in cur.fetchall():  # type: ignore[union-attr]
        blocking.append(
            f"{grantee} holds {privs} on public.{table}; "
            f"no Data API dependency is proven for it"
        )

    cur.execute(Q_DEFAULT_ACL)  # type: ignore[union-attr]
    for owner, objtype, acl in cur.fetchall():  # type: ignore[union-attr]
        kind = "TABLES" if objtype == "r" else "SEQUENCES"
        for role in EXTERNAL_ROLES:
            if f"{role}=" in (acl or ""):
                blocking.append(
                    f"default privileges for {owner} grant {kind} to {role}; "
                    f"new objects would be exposed on creation"
                )


def _check_p0_sec_b(cur: object, blocking: list[str]) -> None:
    """Execute P0-SEC-B control-family checks against an open cursor."""
    cur.execute(Q_BLOCKING_FAIL_OPEN)  # type: ignore[union-attr]
    for table, policy, location in cur.fetchall():  # type: ignore[union-attr]
        blocking.append(
            f"fail-open COALESCE policy {policy} on {table} ({location}); "
            f"P0-SEC-B migration (20260905_0001) must be applied"
        )

    for table, policy in _EXCESS_POLICY_NAMES:
        cur.execute(  # type: ignore[union-attr]
            "SELECT COUNT(*) FROM pg_policies "
            "WHERE schemaname='public' AND tablename=%s AND policyname=%s",
            (table, policy),
        )
        row = cur.fetchone()  # type: ignore[union-attr]
        if row and row[0] > 0:
            blocking.append(
                f"excess FOR ALL policy {policy} on {table} still present; "
                f"P0-SEC-B migration (20260905_0001) must be applied"
            )


def run(dsn: str, scope: str | None = None) -> int:
    """Check the database against Supabase security controls.

    scope=None        → all controls (global lint, current-head use)
    scope="p0_sec_a"  → P0-SEC-A controls only (permissive-policy, RLS,
                         external-grant, default-ACL)
    scope="p0_sec_b"  → P0-SEC-B controls only (COALESCE fail-open,
                         excess FOR ALL policies)
    scope="p0_sec_d"  → P0-SEC-D controls only (SECURITY DEFINER
                         PUBLIC/anon/authenticated EXECUTE)
    any other value   → returns 1 immediately; no DB connection is made.

    Historical gates must use their own scope so that P0-SEC-B blockers present
    in a P0-SEC-A-only fixture do not cause false failures in the A gate (and
    vice versa).

    Fail-closed scope validation: an unrecognised scope would silently set both
    run_a and run_b to False, execute zero checks, and return 0 — fail-open.
    The explicit guard below prevents that.
    """
    if scope not in _VALID_SCOPES:
        print(
            f"INVALID SCOPE: {scope!r} is not a recognised lint control family. "
            f"Valid values: None (global — all controls), 'p0_sec_a', 'p0_sec_b', "
            f"'p0_sec_d'.",
            file=sys.stderr,
        )
        return 1

    run_a = scope in _SCOPE_P0_SEC_A
    run_b = scope in _SCOPE_P0_SEC_B
    run_d = scope in _SCOPE_P0_SEC_D

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
        if run_a:
            _check_p0_sec_a(cur, protected, blocking)
        if run_b:
            _check_p0_sec_b(cur, blocking)
        if run_d:
            _check_p0_sec_d(cur, blocking)

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
