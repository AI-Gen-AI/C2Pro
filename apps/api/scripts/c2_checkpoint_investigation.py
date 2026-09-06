#!/usr/bin/env python3
"""C2 (Option-C checkpoint role contract proof): executable investigation.

Answers MASTER's 6 numbered questions about AsyncPostgresSaver.setup() and
steady-state checkpoint operations using the REAL langgraph-checkpoint-
postgres package actually pinned by C2Pro (requirements.txt:
``langgraph-checkpoint-postgres>=3.1.0``; installed: 3.1.2), against a
disposable PostgreSQL database. No conclusion here is inferred from
documentation alone.

Usage:
    P0_SEC_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres \\
        apps/api/.venv/bin/python apps/api/scripts/c2_checkpoint_investigation.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from security_gate_common import exec_sql as _exec_script  # noqa: E402
from security_gate_common import pg_connection as _connection  # noqa: E402
from security_gate_common import resolve_admin_dsn as _resolve_admin_dsn_impl  # noqa: E402

DB_NAME = "c2_checkpoint_probe"
CHECKPOINT_TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")


def _resolve_admin_dsn() -> str:
    return _resolve_admin_dsn_impl("P0_SEC_ADMIN_DSN")


def _relation_count(dsn: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with _connection(dsn) as conn, conn.cursor() as cur:
        for t in (*CHECKPOINT_TABLES, "checkpoint_migrations"):
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=%s",
                (t,),
            )
            row = cur.fetchone()
            counts[t] = int(row[0]) if row else 0
    return counts


def _migration_watermark(dsn: str) -> int | None:
    with _connection(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT MAX(v) FROM checkpoint_migrations")
        row = cur.fetchone()
        return None if row is None or row[0] is None else int(row[0])


def _role_pool(dsn_as_admin: str, role: str | None):
    """Build an AsyncConnectionPool authenticated as the admin DSN, but with

    every pooled connection immediately SET ROLE'd to ``role`` (or left as
    the admin superuser if ``role`` is None). This mirrors the SET ROLE
    pattern p0_sec_b_gate.py already uses for the same reason: it tests
    real, restricted, NOSUPERUSER/NOBYPASSRLS privilege enforcement without
    depending on separate login credentials or the cluster's pg_hba.conf
    auth method for a second role.
    """
    from psycopg_pool import AsyncConnectionPool

    async def _configure(conn) -> None:  # noqa: ANN001
        if role is not None:
            await conn.execute(f"SET ROLE {role}")

    return AsyncConnectionPool(
        conninfo=dsn_as_admin,
        min_size=0,
        max_size=2,
        open=False,
        configure=_configure,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )


async def _run_setup(dsn_as_admin: str, role: str | None) -> tuple[bool, str]:
    """Instantiate a real AsyncPostgresSaver bound to a SET-ROLE'd pool and call .setup().

    Returns (succeeded, message).
    """
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


async def _run_checkpoint_roundtrip(dsn_as_admin: str, role: str | None) -> tuple[bool, str]:
    """Perform a real put() -> get_tuple() -> put_writes() round trip.

    Uses ONLY the AsyncPostgresSaver's public checkpointing API (the exact
    calls the live LangGraph N13/N14 HITL nodes and every other graph node
    make through BaseCheckpointSaver), never raw SQL, so this proves the
    steady-state contract the runtime actually depends on.
    """
    pool = _role_pool(dsn_as_admin, role)
    try:
        await pool.open(wait=True, timeout=10)

        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError:
            from langgraph.checkpoint.postgres import AsyncPostgresSaver

        from langgraph.checkpoint.base import empty_checkpoint

        saver = AsyncPostgresSaver(conn=pool)

        thread_id = "c2-investigation-thread"
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint = empty_checkpoint()

        put_config = await saver.aput(config, checkpoint, {"source": "c2-probe", "step": 1, "writes": {}, "parents": {}}, {})
        loaded = await saver.aget_tuple(put_config)
        if loaded is None:
            return False, "aget_tuple() returned None after aput() — round trip broken"
        if loaded.checkpoint["id"] != checkpoint["id"]:
            return False, "round-tripped checkpoint id mismatch"

        await saver.aput_writes(put_config, [("channel", {"value": 1})], "task-1")

        return True, "aput() -> aget_tuple() -> aput_writes() round trip succeeded"
    except Exception as exc:  # noqa: BLE001 - capturing the exact failure for the report
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        await pool.close()


def main() -> int:
    admin = _resolve_admin_dsn()
    target = admin.rsplit("/", 1)[0] + "/" + DB_NAME

    _exec_script(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')
    _exec_script(admin, sql=f'CREATE DATABASE "{DB_NAME}"')

    try:
        # Both roles are NOLOGIN: every check below authenticates as the
        # admin DSN's superuser and issues SET ROLE per pooled connection
        # (see _role_pool), the same technique p0_sec_b_gate.py uses to test
        # restricted-role behaviour without depending on a second set of
        # login credentials or the cluster's pg_hba.conf auth method.
        #
        # c2_owner_test: NOSUPERUSER, NOBYPASSRLS, NOCREATEROLE, but CAN
        # create objects in schema public (mirrors an owner/migration role
        # provisioning the checkpoint schema up front).
        _exec_script(
            target,
            sql=(
                "DO $r$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='c2_owner_test') THEN "
                "CREATE ROLE c2_owner_test NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOLOGIN; "
                "END IF; END $r$;"
            ),
        )
        _exec_script(target, sql="GRANT CREATE, USAGE ON SCHEMA public TO c2_owner_test")

        # c2_checkpoint_test: NOSUPERUSER, NOBYPASSRLS, NOCREATEROLE, owns
        # nothing, granted no CREATE on schema public (PostgreSQL 15+
        # default: PUBLIC has no CREATE on the public schema already).
        _exec_script(
            target,
            sql=(
                "DO $r$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='c2_checkpoint_test') THEN "
                "CREATE ROLE c2_checkpoint_test NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOLOGIN; "
                "END IF; END $r$;"
            ),
        )
        _exec_script(target, sql="GRANT USAGE ON SCHEMA public TO c2_checkpoint_test")

        print("=" * 78)
        print("Q1/Q2 — setup() against a FRESH database (owner-shaped role, has CREATE)")
        print("=" * 78)
        before = _relation_count(target)
        ok, msg = asyncio.run(_run_setup(target, "c2_owner_test"))
        print(f"  setup() as c2_owner_test on FRESH db: {'OK' if ok else 'FAILED'} — {msg}")
        after = _relation_count(target)
        print(f"  relations before: {before}")
        print(f"  relations after:  {after}")
        watermark = _migration_watermark(target)
        print(f"  checkpoint_migrations watermark after fresh setup(): v={watermark} (expect 9)")
        if not ok or watermark != 9 or any(after[t] != 1 for t in after):
            raise SystemExit("Q1/Q2 FRESH-DB PROOF FAILED — see output above")

        print()
        print("=" * 78)
        print("Q5/Q6 — steady-state CRUD as c2_checkpoint_test: SELECT/INSERT/UPDATE/")
        print("        DELETE on the 3 checkpoint tables, SELECT-ONLY on")
        print("        checkpoint_migrations (proves no runtime INSERT needed there)")
        print("=" * 78)
        _exec_script(
            target,
            sql=(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
                f"{', '.join(CHECKPOINT_TABLES)} TO c2_checkpoint_test; "
                f"GRANT SELECT ON checkpoint_migrations TO c2_checkpoint_test;"
            ),
        )
        ok, msg = asyncio.run(_run_checkpoint_roundtrip(target, "c2_checkpoint_test"))
        print(f"  aput/aget_tuple/aput_writes round trip: {'OK' if ok else 'FAILED'} — {msg}")
        if not ok:
            raise SystemExit("Q5 STEADY-STATE ROUND TRIP FAILED — see output above")

        print()
        print("=" * 78)
        print("Q2/Q4 — setup() on an ALREADY-CURRENT schema, as c2_checkpoint_test")
        print("        (NO CREATE on schema public, NOT owner of any table)")
        print("=" * 78)
        ok, msg = asyncio.run(_run_setup(target, "c2_checkpoint_test"))
        print(f"  setup() as c2_checkpoint_test on CURRENT schema: {'OK' if ok else 'FAILED'} — {msg}")
        print(
            "  (This is what src/main.py's ensure_checkpointer_ready() calls on EVERY "
            "app boot today, unconditionally, per src/analysis/adapters/graph/workflow.py.)"
        )

        print()
        print("=" * 78)
        print("Q2 (continued) — same call, but WITHOUT even SELECT on checkpoint_migrations")
        print("=" * 78)
        _exec_script(target, sql="REVOKE SELECT ON checkpoint_migrations FROM c2_checkpoint_test")
        ok2, msg2 = asyncio.run(_run_setup(target, "c2_checkpoint_test"))
        print(f"  setup() with zero checkpoint_migrations privilege: {'OK' if ok2 else 'FAILED'} — {msg2}")

        print()
        print("=" * 78)
        print("PROPOSED MODEL VALIDATION — RLS enabled+forced, TO-c2pro_checkpoint-only")
        print("policies (no PUBLIC/anon/authenticated exposure), no tenant semantics")
        print("=" * 78)
        for t in CHECKPOINT_TABLES:
            _exec_script(target, sql=f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            _exec_script(target, sql=f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            _exec_script(
                target,
                sql=(
                    f"CREATE POLICY {t}_checkpoint_role_only ON {t} "
                    f"FOR ALL TO c2_checkpoint_test USING (true) WITH CHECK (true)"
                ),
            )
        ok, msg = asyncio.run(_run_checkpoint_roundtrip(target, "c2_checkpoint_test"))
        print(f"  c2_checkpoint_test round trip WITH RLS forced + TO-role policy: "
              f"{'OK' if ok else 'FAILED'} — {msg}")
        if not ok:
            raise SystemExit("PROPOSED MODEL VALIDATION FAILED — c2pro_checkpoint itself broke under RLS")

        # A second, unrelated restricted role (stands in for c2pro_app / anon /
        # authenticated) must see nothing: the policy is scoped TO c2_checkpoint_test
        # only, and RLS is FORCEd so even a hypothetical owner-like role without
        # BYPASSRLS would still be denied by default (no owner-bypass here since
        # neither test role owns these tables).
        _exec_script(
            target,
            sql=(
                "DO $r$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='c2_other_test') THEN "
                "CREATE ROLE c2_other_test NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOLOGIN; "
                "END IF; END $r$;"
            ),
        )
        _exec_script(
            target,
            sql=(
                f"GRANT USAGE ON SCHEMA public TO c2_other_test; "
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(CHECKPOINT_TABLES)} TO c2_other_test;"
            ),
        )
        with _connection(target) as conn, conn.cursor() as cur:
            cur.execute("SET ROLE c2_other_test")
            try:
                cur.execute("SELECT COUNT(*) FROM checkpoints")
                row = cur.fetchone()
                count = int(row[0]) if row else 0
            finally:
                cur.execute("RESET ROLE")
        print(
            f"  c2_other_test (table GRANTs but NOT named in any policy) sees "
            f"{count} row(s) in checkpoints (expect 0)"
        )
        if count != 0:
            raise SystemExit(
                "PROPOSED MODEL VALIDATION FAILED — a role other than c2pro_checkpoint "
                "can read checkpoint data despite not being named in any policy"
            )

    finally:
        _exec_script(admin, sql=f'DROP DATABASE IF EXISTS "{DB_NAME}"')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
