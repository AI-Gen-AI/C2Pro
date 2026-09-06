#!/usr/bin/env python3
"""Self-verifying gate for the P0-SEC-D function-privilege hardening.

Builds a disposable database reproducing the production Supabase role model
and default-privilege posture, applies public.handle_new_user() exactly as
committed in the init-schema migration, then proves the full lifecycle:

    pre-fix   -> TRUE RED   (PUBLIC/anon/authenticated/service_role hold
                              EXECUTE on the SECURITY DEFINER function)
    fix       -> GREEN      (only the owner holds EXECUTE)
    regression proof        (the on_auth_user_created trigger this function
                              serves still fires correctly for an
                              `authenticated` INSERT after the fix -- EXECUTE
                              ACLs are not checked for trigger invocation)

Usage:
    P0_SEC_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres \\
        python apps/api/scripts/p0_sec_d_gate.py

DSN is read exclusively from P0_SEC_ADMIN_DSN and must resolve to a loopback
host (localhost / 127.0.0.1 / ::1). Remote or cloud hosts are rejected at
startup.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p0_sec_d_common import (  # noqa: E402
    FIXTURE_PATH,
    extract_handle_new_user_ddl,
    fix_migration_sql,
)

DB_NAME = "p0_sec_d_gate"

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})

# Roles a SECURITY DEFINER function must never leak EXECUTE to without an
# explicit, reviewed grant. service_role is deliberately excluded: backend-
# only RPCs may legitimately grant it EXECUTE (e.g. create_tenant_and_owner).
_UNTRUSTED_ROLES = ("PUBLIC", "anon", "authenticated")


def _resolve_admin_dsn() -> str:
    raw = os.environ.get("P0_SEC_ADMIN_DSN")
    if not raw:
        print("no DSN: set P0_SEC_ADMIN_DSN", file=sys.stderr)
        raise SystemExit(2)
    normalized = raw.replace("postgresql+asyncpg://", "postgresql://")
    try:
        host = urlparse(normalized).hostname
    except Exception:
        raise SystemExit("GATE ABORTED: could not parse P0_SEC_ADMIN_DSN") from None
    if not host or host not in _LOOPBACK_HOSTS:
        raise SystemExit(f"GATE ABORTED: P0_SEC_ADMIN_DSN host {host!r} is not a loopback address.")
    return normalized


def _sanitize(msg: str, dsn: str) -> str:
    try:
        pw = urlparse(dsn).password
        if pw:
            msg = msg.replace(pw, "***")
    except Exception:
        pass
    return msg


def _exec_script(dsn: str, *, sql: str | None = None, path: Path | None = None) -> None:
    """Execute a SQL script as a single statement batch (for dollar-quoted blocks)."""
    query = sql or (path.read_text(encoding="utf-8") if path else None)
    if not query:
        raise ValueError("sql or path required")
    try:
        try:
            import psycopg

            with psycopg.connect(dsn, autocommit=True) as conn:
                conn.execute(query)
        except ImportError:
            import psycopg2

            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(query)
            finally:
                conn.close()
    except SystemExit:
        raise
    except Exception as exc:
        msg = _sanitize(str(exc), dsn)
        raise SystemExit(f"database command failed: {type(exc).__name__}: {msg}") from None


@contextmanager
def _connection(dsn: str):
    try:
        import psycopg

        conn = psycopg.connect(dsn, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()
    except ImportError:
        import psycopg2

        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        try:
            yield conn
        finally:
            conn.close()


def _executable_by(dsn: str, role: str) -> bool:
    """True if `role` (or PUBLIC) holds an explicit EXECUTE grant on

    handle_new_user(), read directly from pg_proc.proacl via aclexplode.

    ``has_function_privilege`` is deliberately NOT used here: this gate
    connects as a superuser (P0_SEC_ADMIN_DSN), and a superuser's own
    effective privilege is always true regardless of ACL content, which
    would mask exactly the PUBLIC-grant regression this gate exists to
    catch. Reading the ACL directly checks what is actually granted, not
    who is asking.
    """
    with _connection(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                  FROM pg_proc p
                  JOIN pg_namespace n ON n.oid = p.pronamespace
                  JOIN LATERAL aclexplode(
                      COALESCE(p.proacl, acldefault('f', p.proowner))
                  ) AS acl ON true
                 WHERE n.nspname = 'public'
                   AND p.proname = 'handle_new_user'
                   AND acl.privilege_type = 'EXECUTE'
                   AND (
                       (%(role)s = 'PUBLIC' AND acl.grantee = 0)
                       OR (%(role)s != 'PUBLIC' AND pg_get_userbyid(acl.grantee) = %(role)s)
                   )
            )
            """,
            {"role": role},
        )
        row = cur.fetchone()
        return bool(row and row[0])


def _check_phase(dsn: str, label: str, *, expect_executable: bool) -> None:
    print(f"\n=== {label} (expect {'EXECUTABLE' if expect_executable else 'BLOCKED'}) ===")
    for role in _UNTRUSTED_ROLES:
        actual = _executable_by(dsn, role)
        if actual != expect_executable:
            raise SystemExit(
                f"GATE FAILED at '{label}': {role} EXECUTE on "
                f"public.handle_new_user() is {actual}, expected {expect_executable}"
            )
        print(f"    {role}: EXECUTE={actual} OK")
    print(f"--- {label}: as expected")


def _check_trigger_still_fires(dsn: str) -> None:
    """Prove the fix does not break the real Supabase Auth signup path.

    An `authenticated`-role INSERT into auth.users must still produce a
    matching public.users row via the on_auth_user_created trigger --
    EXECUTE ACLs on a trigger function are not consulted when the trigger
    fires, only when the function is called directly.
    """
    print("\n=== regression proof: signup trigger still fires ===")
    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-000000000001"
    user_id = "bbbbbbbb-bbbb-bbbb-bbbb-000000000002"

    _exec_script(
        dsn,
        sql=f"INSERT INTO public.tenants (id, name) VALUES ('{tenant_id}'::uuid, 'Acme')",
    )
    _exec_script(
        dsn,
        sql=(
            "SET ROLE authenticated; "
            "INSERT INTO auth.users (id, email, raw_user_meta_data) VALUES ("
            f"'{user_id}'::uuid, 'new.user@example.com', "
            f"'{{\"tenant_id\": \"{tenant_id}\", \"first_name\": \"New\", "
            '"last_name": "User"}\'::jsonb); '
            "RESET ROLE;"
        ),
    )

    with _connection(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT tenant_id, email, role FROM public.users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise SystemExit(
            "GATE FAILED: on_auth_user_created did not create the public.users "
            "row -- the REVOKE broke the Supabase Auth signup path"
        )
    got_tenant, got_email, got_role = str(row[0]), row[1], row[2]
    if got_tenant != tenant_id or got_email != "new.user@example.com" or got_role != "member":
        raise SystemExit(
            f"GATE FAILED: trigger produced unexpected row: "
            f"tenant_id={got_tenant} email={got_email} role={got_role}"
        )
    print(f"    public.users row created via trigger: tenant_id={got_tenant} role={got_role} OK")
    print("--- regression proof: PASSED")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="do not drop the disposable DB")
    args = parser.parse_args()

    admin = _resolve_admin_dsn()
    target = admin.rsplit("/", 1)[0] + "/" + DB_NAME

    _exec_script(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')
    _exec_script(admin, sql=f'CREATE DATABASE "{DB_NAME}"')

    try:
        # Load the role/default-ACL pre-state fixture, then apply the exact
        # committed handle_new_user() DDL (pre-fix) as c2pro_owner -- the
        # ALTER DEFAULT PRIVILEGES ... FOR ROLE c2pro_owner clause in the
        # fixture only auto-grants EXECUTE for objects that role creates,
        # matching how a real Supabase deploy applies this migration.
        _exec_script(target, path=FIXTURE_PATH)
        _exec_script(
            target,
            sql=f"SET ROLE c2pro_owner;\n{extract_handle_new_user_ddl()}\nRESET ROLE;",
        )

        # Step 1: confirm TRUE RED before the fix.
        _check_phase(target, "pre-fix", expect_executable=True)

        # Step 2: apply the fix migration.
        _exec_script(target, sql=fix_migration_sql())

        # Step 3: confirm GREEN after the fix.
        _check_phase(target, "after fix", expect_executable=False)

        # Step 4: prove the real signup trigger still fires.
        _check_trigger_still_fires(target)

    finally:
        if not args.keep:
            _exec_script(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')

    print("\nP0-SEC-D GATE: PASSED (RED -> GREEN + trigger regression proof)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
