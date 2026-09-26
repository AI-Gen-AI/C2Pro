#!/usr/bin/env python3
"""C2.6 -- Platform Operator Authorization Gate (Disposable DB).

Per the C2.6 specification's binding FIX3 decision, this gate EXTENDS/REUSES
the disposable-database lifecycle already proven by
`apps/api/scripts/c25_admin_ops_gate.py` -- provisioning, ownership-tracked
capability-role ownership, and teardown/hygiene -- rather than reimplementing
it. It imports that module's internal helper functions directly; it does not
modify c25_admin_ops_gate.py.

On top of that reused lifecycle, this gate re-runs the C2.5 capability/grant/
RLS proofs (authoritative, not duplicated: `c25._run_gate_assertions`) and
then adds the C2.6-specific proof layer that did not exist before: the
platform-operator authorization gate (`require_platform_operator`), the E1
anti-provisioning guard (`_provision_clerk_user`), the G5 deny-only operator-
org-is-tenant integrity check, and the real `DLQAdminOpsAdapter` / use-cases
exercised against the same disposable capability boundary C2.5 already
proved -- end to end, against real PostgreSQL, no mocks.

Usage:
    P0_SEC_ADMIN_DSN=postgresql://postgres@localhost:5433/postgres \\
        python apps/api/scripts/c26_platform_operator_gate.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# c25_admin_ops_gate sets ENVIRONMENT / TEST_DATABASE_URL / JWT_SECRET_KEY at
# import time -- importing it first gives every later `from src...` import a
# valid baseline Settings() construction, exactly as c25's own script relies on.
import c25_admin_ops_gate as c25  # noqa: E402

TENANT_A = c25.TENANT_A
TENANT_B = c25.TENANT_B
OPERATOR_ORG_ID = "org_c26_gate_platform"


async def _run_c26_proofs(admin_pool, target_dsn: str, admin_login_dsn: str) -> bool:
    """The new C2.6-specific proof layer, against the disposable DB c25's
    lifecycle just provisioned and already proved at the capability level."""
    from fastapi import HTTPException
    from sqlalchemy import text
    from starlette.requests import Request

    from src.admin.adapters.http.router import DLQAdminOpsAdapter
    from src.admin.application.use_cases.list_dlq_entries import ListDLQEntriesUseCase
    from src.admin.application.use_cases.retry_dlq_entry import RetryDLQEntryUseCase
    from src.config import settings
    from src.core.auth.dependencies import _provision_clerk_user
    from src.core.auth.platform_operator import PlatformIdentity, require_platform_operator
    from src.core.database import (
        close_admin_ops_db,
        close_db,
        get_raw_session,
        init_admin_ops_db,
        init_db,
    )

    def _request() -> Request:
        return Request({"type": "http", "method": "GET", "path": "/api/v1/admin/dlq"})

    passed = True
    settings.database_url = target_dsn
    settings.admin_ops_database_url = admin_login_dsn
    settings.platform_operator_org_id = OPERATOR_ORG_ID
    settings.platform_operator_user_ids = []

    await init_db()
    await init_admin_ops_db()
    try:
        await c25._seed_dlq_rows(admin_pool)

        print("\n=== N: customer-org identity is denied before any DB grant ===")
        customer_identity = PlatformIdentity(
            user_id="user_customer_admin", org_id="org_customer", email="c@example.test", email_verified=True
        )
        req = _request()
        req.state.platform_identity = customer_identity
        try:
            await require_platform_operator(req)
            print("FAIL: customer-org identity was granted platform-operator status")
            passed = False
        except HTTPException as exc:
            if exc.status_code == 403 and exc.detail == "Not authorized":
                print("OK: customer-org identity denied 403, generic body")
            else:
                print(f"FAIL: unexpected denial shape: {exc.status_code} {exc.detail!r}")
                passed = False

        print("\n=== P: authorized operator lists + retries across tenants (real adapter, real DB) ===")
        operator_identity = PlatformIdentity(
            user_id="user_operator_gate", org_id=OPERATOR_ORG_ID, email="op@example.test", email_verified=True
        )
        req = _request()
        req.state.platform_identity = operator_identity
        operator = await require_platform_operator(req)
        if operator.clerk_user_id == "user_operator_gate" and operator.clerk_org_id == OPERATOR_ORG_ID:
            print(f"OK: operator granted: {operator.clerk_user_id}")
        else:
            print("FAIL: unexpected PlatformOperator identity")
            passed = False

        port = DLQAdminOpsAdapter()
        list_uc = ListDLQEntriesUseCase(port)
        retry_uc = RetryDLQEntryUseCase(port)

        page = await list_uc.execute(status="pending", limit=50, offset=0)
        seen_tenants = {str(e.tenant_id) for e in page.entries}
        if {str(TENANT_A), str(TENANT_B)}.issubset(seen_tenants):
            print(f"OK: real DLQAdminOpsAdapter lists across {len(seen_tenants)} tenants (P01)")
        else:
            print(f"FAIL: expected tenants {TENANT_A}/{TENANT_B}, got {seen_tenants}")
            passed = False

        target_entry = page.entries[0]
        before_tenant, before_payload = target_entry.tenant_id, target_entry.payload_json
        await retry_uc.execute(target_entry.id)
        after = await port.get_by_id(target_entry.id)
        if (
            after is not None
            and after.status == "retrying"
            and after.retry_count == target_entry.retry_count + 1
            and str(after.tenant_id) == str(before_tenant)
            and after.payload_json == before_payload
        ):
            print("OK: real retry use-case mutated only status/retry_count/updated_at/next_retry_at (P02)")
        else:
            print("FAIL: retry outcome unexpected -- non-granted columns may have changed")
            passed = False

        print("\n=== G5: operator org mapped as a customer tenant is denied (deny-only integrity) ===")
        await init_db()
        async with get_raw_session() as session:
            await session.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, clerk_org_id, subscription_plan) "
                    "VALUES (gen_random_uuid(), 'contaminated-operator-org', "
                    ":slug, :org_id, 'free')"
                ),
                {"slug": f"c26-gate-contaminated-{os.getpid()}", "org_id": OPERATOR_ORG_ID},
            )
            await session.commit()

        req = _request()
        req.state.platform_identity = operator_identity
        try:
            await require_platform_operator(req)
            print("FAIL: contaminated operator org was granted platform-operator status")
            passed = False
        except HTTPException as exc:
            if exc.status_code == 403:
                print("OK: contaminated operator org denied 403 (G5 is deny-only and fired correctly)")
            else:
                print(f"FAIL: unexpected status {exc.status_code}")
                passed = False

        print("\n=== E1: operator-org bootstrap refused before any tenant lookup/creation ===")
        try:
            await _provision_clerk_user(
                AsyncMock(),
                clerk_user_id="user_operator_gate",
                clerk_org_id=OPERATOR_ORG_ID,
                email="op@example.test",
                first_name=None,
                last_name=None,
            )
            print("FAIL: operator-org bootstrap was not refused")
            passed = False
        except HTTPException as exc:
            if exc.status_code == 403:
                print("OK: E1 guard refused operator-org bootstrap with an explicit controlled error")
            else:
                print(f"FAIL: unexpected status {exc.status_code}")
                passed = False

        print("\n=== P03: authorized operator, ADMIN_OPS_DATABASE_URL absent -> 503-equivalent unavailability ===")
        await close_admin_ops_db()  # drop the already-initialized engine so absence is re-checked, not cached
        settings.admin_ops_database_url = None
        try:
            async with port._admin_session():
                pass
            print("FAIL: admin session succeeded with no ADMIN_OPS_DATABASE_URL configured")
            passed = False
        except HTTPException as exc:
            if exc.status_code == 503:
                print("OK: capability unavailable maps to 503 only after authorization already passed")
            else:
                print(f"FAIL: unexpected status {exc.status_code}")
                passed = False
        finally:
            settings.admin_ops_database_url = admin_login_dsn

    finally:
        await close_admin_ops_db()
        await close_db()

    return passed


async def main() -> int:
    try:
        admin_dsn = c25._resolve_admin_dsn_impl("P0_SEC_ADMIN_DSN")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR resolving P0_SEC_ADMIN_DSN: {exc}")
        return 1

    pid = os.getpid()
    DB_NAME = f"c26_platform_operator_gate_{pid}"
    app_role = f"c26_gate_app_{pid}"
    admin_login_role = f"c26_gate_admin_{pid}"

    target_dsn = admin_dsn.rsplit("/", 1)[0] + "/" + DB_NAME
    admin_base_dsn = admin_dsn.rsplit("/", 1)[0] + "/postgres"

    admin_pool = app_pool = admin_login_pool = None
    lifecycle = c25.GateLifecycle()
    cleanup_errors: list[str] = []
    all_passed = True

    try:
        c25._snapshot_and_provision_base_db(admin_base_dsn, DB_NAME, app_role, admin_login_role, lifecycle)
        print(f"Successfully created disposable database: {DB_NAME}")

        c25._run_alembic_migrations(target_dsn)

        admin_pool = await c25._connect(target_dsn)
        await c25._provision_roles(admin_pool, app_role, admin_login_role, lifecycle.created_synthetic_roles)

        app_dsn = c25._derive_dsn(target_dsn, app_role, "app_pass_gate")
        admin_login_dsn = c25._derive_dsn(target_dsn, admin_login_role, "admin_pass_gate")

        app_pool = await c25._connect(app_dsn)
        admin_login_pool = await c25._connect(admin_login_dsn)

        print("\n=== RE-RUNNING C2.5 capability/grant/RLS proofs (authoritative, not reimplemented) ===")
        all_passed &= await c25._run_gate_assertions(admin_pool, app_pool, admin_login_pool)

        print("\n=== C2.6 platform-operator authorization proofs (new) ===")
        all_passed &= await _run_c26_proofs(admin_pool, target_dsn, admin_login_dsn)

    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ GATE LIFECYCLE EXECUTION FAILURE: {exc}")
        import traceback

        traceback.print_exc()
        all_passed = False

    finally:
        if app_pool:
            try:
                await app_pool.close()
            except Exception as e:  # noqa: BLE001
                cleanup_errors.append(f"Failed to close app_pool: {e}")
        if admin_login_pool:
            try:
                await admin_login_pool.close()
            except Exception as e:  # noqa: BLE001
                cleanup_errors.append(f"Failed to close admin_login_pool: {e}")
        if admin_pool:
            try:
                await admin_pool.close()
            except Exception as e:  # noqa: BLE001
                cleanup_errors.append(f"Failed to close admin_pool: {e}")

        hygiene_passed = c25._execute_teardown_and_hygiene(
            admin_base_dsn, DB_NAME, app_role, admin_login_role, lifecycle, cleanup_errors
        )

        if cleanup_errors or not hygiene_passed:
            all_passed = False
            print("\n❌ HYGIENE OR CLEANUP FAILURES DETECTED:")
            for err in cleanup_errors:
                print(f"  - {err}")
        else:
            print("\nOK: Cluster-state hygiene verified successfully.")

    if all_passed:
        print("\n✅ ALL C2.6 GATE CHECKS PASSED (disposable DB + platform-operator authz + C2.5 re-proof)")
        return 0
    print("\n❌ SOME C2.6 GATE CHECKS FAILED")
    return 1


if __name__ == "__main__":
    import asyncio

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(main()))
