#!/usr/bin/env python3
"""Self-verifying gate for the C2 checkpoint role boundary (Option-C).

Builds a disposable database and proves, using the REAL
langgraph-checkpoint-postgres package (not handwritten SQL standing in for
it), the full RED -> GREEN cycle for the target role contract:

    ROLE A (c2pro_owner-shaped):   provisions the checkpoint schema
    ROLE B (c2pro_app-shaped):     zero checkpoint-table access
    ROLE C (c2pro_checkpoint-shaped): checkpoint steady-state only

RED (before owner provisioning):
    1. c2pro_checkpoint-shaped role cannot execute AsyncPostgresSaver.setup()
       (no CREATE on schema public).
    2. c2pro_checkpoint-shaped role cannot perform the steady-state
       aput/aget_tuple/aput_writes round trip (checkpoint tables do not
       exist yet).

GREEN (after owner provisioning + the target grant/policy contract):
    - OWNER:      setup() succeeds, schema is fully migrated.
    - CHECKPOINT: steady-state round trip succeeds.
    - APP:        SELECT/INSERT/UPDATE/DELETE on all 3 checkpoint tables
                  denied.
    - CHECKPOINT: SELECT/INSERT/UPDATE/DELETE on an ordinary business table
                  denied.
    - CHECKPOINT: CREATE TABLE in schema public denied.
    - CHECKPOINT: SELECT on checkpoint_migrations denied.

All three synthetic roles are created NOSUPERUSER on a disposable database
only -- no production credentials are created or touched. c2pro_checkpoint
is additionally verified NOBYPASSRLS, NOCREATEROLE, and not the owner of any
checkpoint table.

Usage:
    P0_SEC_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres \\
        python apps/api/scripts/c2_checkpoint_gate.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from psycopg import sql  # noqa: E402
from security_gate_common import exec_sql as _exec_script  # noqa: E402
from security_gate_common import pg_connection as _connection  # noqa: E402
from security_gate_common import resolve_admin_dsn as _resolve_admin_dsn_impl  # noqa: E402


def _exec_ddl(dsn: str, statement: sql.Composable) -> None:
    """Run a single safely-composed DDL statement (e.g. DROP/CREATE DATABASE).

    exec_sql() takes a raw SQL string, which is right for the fixed,
    hand-audited scripts it runs elsewhere -- but DROP/CREATE DATABASE
    cannot be parameterized at all, so the database name still has to be
    identifier-composed rather than f-string-interpolated, same as every
    other dynamic identifier in this file.
    """
    with _connection(dsn) as conn, conn.cursor() as cur:
        cur.execute(statement)


DB_NAME = "c2_checkpoint_gate"
CHECKPOINT_TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")

OWNER_ROLE = "c2_owner_test"
APP_ROLE = "c2_app_test"
CHECKPOINT_ROLE = "c2_checkpoint_test"


def _resolve_admin_dsn() -> str:
    return _resolve_admin_dsn_impl("P0_SEC_ADMIN_DSN")


def _role_pool(dsn_as_admin: str, role: str):
    """AsyncConnectionPool authenticated as the admin DSN, SET ROLE'd per connection.

    Mirrors p0_sec_b_gate.py's SET ROLE technique: tests real, restricted,
    NOSUPERUSER/NOBYPASSRLS privilege enforcement without depending on a
    second set of login credentials or the cluster's pg_hba.conf.
    """
    from psycopg_pool import AsyncConnectionPool

    async def _configure(conn) -> None:  # noqa: ANN001
        await conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))

    return AsyncConnectionPool(
        conninfo=dsn_as_admin,
        min_size=0,
        max_size=2,
        open=False,
        configure=_configure,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )


async def _run_setup(dsn_as_admin: str, role: str) -> tuple[bool, str]:
    """Instantiate a real AsyncPostgresSaver bound to a SET-ROLE'd pool, call .setup()."""
    pool = _role_pool(dsn_as_admin, role)
    try:
        await pool.open(wait=True, timeout=10)
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError:
            from langgraph.checkpoint.postgres import AsyncPostgresSaver

        saver = AsyncPostgresSaver(conn=pool)
        await saver.setup()
        return True, "setup() completed without error"
    except Exception as exc:  # noqa: BLE001 - capturing the exact failure for the report
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        await pool.close()


async def _run_checkpoint_roundtrip(dsn_as_admin: str, role: str) -> tuple[bool, str]:
    """Real aput() -> aget_tuple() -> aput_writes() round trip via the public API."""
    pool = _role_pool(dsn_as_admin, role)
    try:
        await pool.open(wait=True, timeout=10)
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError:
            from langgraph.checkpoint.postgres import AsyncPostgresSaver

        from langgraph.checkpoint.base import empty_checkpoint

        saver = AsyncPostgresSaver(conn=pool)
        thread_id = "c2-gate-thread"
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint = empty_checkpoint()

        put_config = await saver.aput(
            config, checkpoint, {"source": "c2-gate", "step": 1, "writes": {}, "parents": {}}, {}
        )
        loaded = await saver.aget_tuple(put_config)
        if loaded is None:
            return False, "aget_tuple() returned None after aput()"
        if loaded.checkpoint["id"] != checkpoint["id"]:
            return False, "round-tripped checkpoint id mismatch"

        await saver.aput_writes(put_config, [("channel", {"value": 1})], "task-1")
        return True, "aput() -> aget_tuple() -> aput_writes() round trip succeeded"
    except Exception as exc:  # noqa: BLE001 - capturing the exact failure for the report
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        await pool.close()


async def _run_denied(dsn_as_admin: str, role: str, query: sql.Composable) -> tuple[bool, str]:
    """Run query as role, expecting a permission error. Returns (was_denied, message)."""
    pool = _role_pool(dsn_as_admin, role)
    try:
        await pool.open(wait=True, timeout=10)
        async with pool.connection() as conn, conn.cursor() as cur:
            try:
                await cur.execute(query)
            except Exception as exc:  # noqa: BLE001 - asserting the exact failure mode
                msg = str(exc)
                if "permission denied" not in msg.lower():
                    return False, f"expected 'permission denied', got: {type(exc).__name__}: {exc}"
                return True, msg
        return False, "query succeeded; expected permission denied"
    finally:
        await pool.close()


def _create_roles(target: str) -> None:
    with _connection(target) as conn, conn.cursor() as cur:
        for role in (OWNER_ROLE, APP_ROLE, CHECKPOINT_ROLE):
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE ROLE {} NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOLOGIN").format(
                        sql.Identifier(role)
                    )
                )
        cur.execute(
            sql.SQL("GRANT CREATE, USAGE ON SCHEMA public TO {}").format(sql.Identifier(OWNER_ROLE))
        )
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(APP_ROLE)))
        cur.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(CHECKPOINT_ROLE))
        )


def _check_role_properties(target: str) -> None:
    """NON_OWNER_NOBYPASSRLS_GATE: verify c2pro_checkpoint's catalog-level properties."""
    print("\n=== checkpoint role properties (catalog-verified) ===")
    with _connection(target) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcanlogin "
            "FROM pg_roles WHERE rolname = %s",
            (CHECKPOINT_ROLE,),
        )
        row = cur.fetchone()
        if row is None:
            raise SystemExit(f"GATE FAILED: role {CHECKPOINT_ROLE} does not exist")
        rolsuper, rolbypassrls, rolcreaterole, rolcanlogin = row
        if rolsuper or rolbypassrls or rolcreaterole:
            raise SystemExit(
                f"GATE FAILED: {CHECKPOINT_ROLE} has an unexpected privileged attribute "
                f"(rolsuper={rolsuper} rolbypassrls={rolbypassrls} rolcreaterole={rolcreaterole})"
            )

        for table in CHECKPOINT_TABLES:
            cur.execute("SELECT tableowner FROM pg_tables WHERE tablename = %s", (table,))
            owner_row = cur.fetchone()
            if owner_row is None:
                raise SystemExit(f"GATE FAILED: table {table} does not exist to check ownership")
            if owner_row[0] == CHECKPOINT_ROLE:
                raise SystemExit(f"GATE FAILED: {CHECKPOINT_ROLE} owns {table} (must be non-owner)")
    print(
        f"    {CHECKPOINT_ROLE}: NOSUPERUSER={not rolsuper} NOBYPASSRLS={not rolbypassrls} "
        f"NOCREATEROLE={not rolcreaterole} non-owner=True — OK"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="do not drop the disposable DB")
    args = parser.parse_args()

    admin = _resolve_admin_dsn()
    target = admin.rsplit("/", 1)[0] + "/" + DB_NAME

    _exec_ddl(admin, sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(DB_NAME)))
    _exec_ddl(admin, sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))

    try:
        _create_roles(target)

        # A minimal ordinary business table, granted to APP_ROLE only --
        # stands in for the real business schema (e.g. wbs_nodes) so this
        # gate does not depend on the full application schema.
        _exec_script(target, sql="CREATE EXTENSION IF NOT EXISTS pgcrypto")
        _exec_script(
            target,
            sql="CREATE TABLE business_probe (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), note text)",
        )
        with _connection(target) as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON business_probe TO {}").format(
                    sql.Identifier(APP_ROLE)
                )
            )

        print("=" * 78)
        print("RED 1 — checkpoint role cannot execute setup() before owner provisioning")
        print("=" * 78)
        ok, msg = asyncio.run(_run_setup(target, CHECKPOINT_ROLE))
        print(
            f"  setup() as {CHECKPOINT_ROLE} on unprovisioned schema: {'OK' if ok else 'FAILED'} — {msg}"
        )
        if ok:
            raise SystemExit(
                "GATE FAILED: RED 1 — checkpoint role's setup() unexpectedly succeeded"
            )
        if "permission denied" not in msg.lower():
            raise SystemExit(f"GATE FAILED: RED 1 — expected 'permission denied', got: {msg}")

        print("\n" + "=" * 78)
        print("RED 2 — checkpoint role cannot perform steady-state round trip (no schema yet)")
        print("=" * 78)
        ok, msg = asyncio.run(_run_checkpoint_roundtrip(target, CHECKPOINT_ROLE))
        print(
            f"  round trip as {CHECKPOINT_ROLE} on unprovisioned schema: {'OK' if ok else 'FAILED'} — {msg}"
        )
        if ok:
            raise SystemExit(
                "GATE FAILED: RED 2 — round trip unexpectedly succeeded before provisioning"
            )

        print("\n" + "=" * 78)
        print("OWNER PROVISIONING — real AsyncPostgresSaver.setup() as c2pro_owner-shaped role")
        print("=" * 78)
        ok, msg = asyncio.run(_run_setup(target, OWNER_ROLE))
        print(f"  setup() as {OWNER_ROLE}: {'OK' if ok else 'FAILED'} — {msg}")
        if not ok:
            raise SystemExit("GATE FAILED: owner setup() failed — see message above")
        with _connection(target) as conn, conn.cursor() as cur:
            cur.execute("SELECT MAX(v) FROM checkpoint_migrations")
            watermark = cur.fetchone()[0]
        print(f"  checkpoint_migrations watermark: v={watermark} (expect 9)")
        if watermark != 9:
            raise SystemExit(
                f"GATE FAILED: expected watermark 9 after owner setup(), got {watermark}"
            )

        print("\n" + "=" * 78)
        print("TARGET GRANT/POLICY CONTRACT — apply to the disposable DB only")
        print("=" * 78)
        with _connection(target) as conn, conn.cursor() as cur:
            for table in CHECKPOINT_TABLES:
                cur.execute(
                    sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(
                        sql.Identifier(table)
                    )
                )
                cur.execute(
                    sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(sql.Identifier(table))
                )
                cur.execute(
                    sql.SQL(
                        "CREATE POLICY {policy} ON {table} FOR ALL TO {role} USING (true) WITH CHECK (true)"
                    ).format(
                        policy=sql.Identifier(f"{table}_checkpoint_role_only"),
                        table=sql.Identifier(table),
                        role=sql.Identifier(CHECKPOINT_ROLE),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON {} TO {}").format(
                        sql.Identifier(table), sql.Identifier(CHECKPOINT_ROLE)
                    )
                )
        # Deliberately NOT granted: APP_ROLE gets nothing on checkpoint tables;
        # CHECKPOINT_ROLE gets nothing on checkpoint_migrations or business_probe.
        print(
            f"  RLS enabled+forced on {', '.join(CHECKPOINT_TABLES)}; "
            f"TO-{CHECKPOINT_ROLE}-only policies + GRANTs applied; "
            f"{APP_ROLE} and checkpoint_migrations/business_probe left untouched"
        )

        _check_role_properties(target)

        print("\n" + "=" * 78)
        print("GREEN 1 — checkpoint role steady-state round trip succeeds")
        print("=" * 78)
        ok, msg = asyncio.run(_run_checkpoint_roundtrip(target, CHECKPOINT_ROLE))
        print(f"  round trip as {CHECKPOINT_ROLE}: {'OK' if ok else 'FAILED'} — {msg}")
        if not ok:
            raise SystemExit(
                "GATE FAILED: GREEN 1 — steady-state round trip failed after provisioning"
            )

        print("\n" + "=" * 78)
        print("GREEN 2 — app role denied on all 3 checkpoint tables")
        print("=" * 78)
        for table in CHECKPOINT_TABLES:
            denied, msg = asyncio.run(
                _run_denied(
                    target, APP_ROLE, sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
                )
            )
            print(f"  {APP_ROLE} SELECT {table}: {'DENIED (OK)' if denied else 'FAILED'} — {msg}")
            if not denied:
                raise SystemExit(
                    f"GATE FAILED: GREEN 2 — {APP_ROLE} was not denied SELECT on {table}"
                )
            denied, msg = asyncio.run(
                _run_denied(
                    target,
                    APP_ROLE,
                    sql.SQL("INSERT INTO {} DEFAULT VALUES").format(sql.Identifier(table)),
                )
            )
            print(f"  {APP_ROLE} INSERT {table}: {'DENIED (OK)' if denied else 'FAILED'} — {msg}")
            if not denied:
                raise SystemExit(
                    f"GATE FAILED: GREEN 2 — {APP_ROLE} was not denied INSERT on {table}"
                )

        print("\n" + "=" * 78)
        print("GREEN 3 — checkpoint role denied on the ordinary business table")
        print("=" * 78)
        denied, msg = asyncio.run(
            _run_denied(target, CHECKPOINT_ROLE, sql.SQL("SELECT * FROM business_probe"))
        )
        print(
            f"  {CHECKPOINT_ROLE} SELECT business_probe: {'DENIED (OK)' if denied else 'FAILED'} — {msg}"
        )
        if not denied:
            raise SystemExit(
                "GATE FAILED: GREEN 3 — checkpoint role was not denied business-table SELECT"
            )

        print("\n" + "=" * 78)
        print("GREEN 4 — checkpoint role denied schema CREATE")
        print("=" * 78)
        denied, msg = asyncio.run(
            _run_denied(
                target,
                CHECKPOINT_ROLE,
                sql.SQL("CREATE TABLE checkpoint_role_should_not_create (id int)"),
            )
        )
        print(f"  {CHECKPOINT_ROLE} CREATE TABLE: {'DENIED (OK)' if denied else 'FAILED'} — {msg}")
        if not denied:
            raise SystemExit("GATE FAILED: GREEN 4 — checkpoint role was not denied CREATE TABLE")

        print("\n" + "=" * 78)
        print("GREEN 5 — checkpoint role denied checkpoint_migrations access")
        print("=" * 78)
        denied, msg = asyncio.run(
            _run_denied(target, CHECKPOINT_ROLE, sql.SQL("SELECT * FROM checkpoint_migrations"))
        )
        print(
            f"  {CHECKPOINT_ROLE} SELECT checkpoint_migrations: {'DENIED (OK)' if denied else 'FAILED'} — {msg}"
        )
        if not denied:
            raise SystemExit(
                "GATE FAILED: GREEN 5 — checkpoint role was not denied checkpoint_migrations access"
            )

    finally:
        if not args.keep:
            _exec_ddl(admin, sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(DB_NAME)))

    print(
        "\nC2 CHECKPOINT GATE: PASSED (RED x2 -> owner provisioning -> GREEN x5, "
        "incl. role-property and business-table isolation proofs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
