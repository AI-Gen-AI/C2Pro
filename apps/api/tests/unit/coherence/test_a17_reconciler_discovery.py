"""A17 scoped-recovery hardening; no schema, provider or cross-tenant privilege."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.tasks.coherence_reconciler import (
    DEFAULT_BATCH_SIZE,
    reconcile_pending_postapproval,
)


class Rows:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def all(self):
        return self.rows

    def scalars(self):
        return self


def sessions(*fixtures):
    active = list(fixtures)
    calls = []

    @asynccontextmanager
    async def factory(tenant):
        calls.append(tenant)
        yield active.pop(0)

    return factory, calls


def unscoped(*ids):
    session = AsyncMock()
    session.execute.return_value = Rows(ids)

    @asynccontextmanager
    async def scan():
        yield session

    return scan, session


@pytest.mark.asyncio
async def test_known_tenant_recovery_never_enumerates_other_tenants():
    tenant, project, review = uuid4(), uuid4(), uuid4()
    scanning = AsyncMock()
    scanning.execute.return_value = Rows([(review, tenant, project)])
    completion = AsyncMock()
    completion.scalar.return_value = "done"
    factory, called = sessions(scanning, completion)
    scan, raw = unscoped()
    evaluator = AsyncMock()

    result = await reconcile_pending_postapproval(
        tenant_id=tenant,
        scan_factory=scan,
        tenant_factory=factory,
        evaluator=evaluator,
    )
    assert result == {"scanned": 1, "completed": 1, "retry": 0, "operator_required": 0}
    assert called == [tenant, tenant]
    raw.execute.assert_not_awaited()
    assert scanning.execute.await_args.args[0].text.startswith("\nSELECT r.id")
    assert scanning.execute.await_args.args[1] == {"tenant_id": tenant, "limit": 20}
    evaluator.assert_awaited_once_with(
        tenant_id=tenant, project_id=project, review_id=review, actor_user_id=None
    )


@pytest.mark.asyncio
async def test_global_nonowner_zero_visible_tenants_fails_closed():
    scan, raw = unscoped()
    never = AsyncMock()
    with pytest.raises(RuntimeError, match="A17_RECOVERY_TENANT_DISCOVERY_UNAVAILABLE"):
        await reconcile_pending_postapproval(
            scan_factory=scan, tenant_factory=never, evaluator=never
        )
    assert "SELECT id FROM tenants ORDER BY id" in raw.execute.await_args.args[0].text
    never.assert_not_awaited()


@pytest.mark.asyncio
async def test_global_discovery_still_honours_existing_compatibility_with_visible_tenant():
    tenant, project, review = uuid4(), uuid4(), uuid4()
    scan, raw = unscoped(tenant)
    pending = AsyncMock()
    pending.execute.return_value = Rows([(review, tenant, project)])
    status = AsyncMock()
    status.scalar.return_value = "done"
    factory, called = sessions(pending, status)
    evaluator = AsyncMock()

    result = await reconcile_pending_postapproval(
        scan_factory=scan,
        tenant_factory=factory,
        evaluator=evaluator,
    )
    assert result["completed"] == 1
    assert result["scanned"] == 1
    assert called == [tenant, tenant]
    raw.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_known_tenant_empty_batch_is_valid_without_global_scan():
    tenant = uuid4()
    pending = AsyncMock()
    pending.execute.return_value = Rows()
    factory, called = sessions(pending)
    scan, raw = unscoped()
    evaluator = AsyncMock()

    result = await reconcile_pending_postapproval(
        tenant_id=tenant,
        scan_factory=scan,
        tenant_factory=factory,
        evaluator=evaluator,
    )
    assert result == {"scanned": 0, "completed": 0, "retry": 0, "operator_required": 0}
    assert called == [tenant]
    raw.execute.assert_not_awaited()
    evaluator.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "retry_state", "expected"),
    [
        ("pending", "pending", "retry"),
        ("pending", "operator_required", "operator_required"),
        ("done", None, "completed"),
        ("operator_required", None, None),
    ],
)
async def test_retry_and_terminal_states_remain_durable(state, retry_state, expected):
    tenant, project, review = uuid4(), uuid4(), uuid4()
    pending = AsyncMock()
    pending.execute.return_value = Rows([(review, tenant, project)])
    status = AsyncMock()
    status.scalar.side_effect = [state] if retry_state is None else [state, retry_state]
    factory, called = sessions(pending, status)
    scan, raw = unscoped()
    evaluator = AsyncMock(side_effect=RuntimeError("synthetic failure"))

    result = await reconcile_pending_postapproval(
        tenant_id=tenant,
        scan_factory=scan,
        tenant_factory=factory,
        evaluator=evaluator,
    )
    assert result["scanned"] == 1
    assert sum(result[k] for k in ("completed", "retry", "operator_required")) == (
        1 if expected else 0
    )
    if expected is not None:
        assert result[expected] == 1
    assert called == [tenant, tenant]
    raw.execute.assert_not_awaited()
    evaluator.assert_awaited_once()
    if retry_state is not None:
        assert status.scalar.await_count == 2
    else:
        assert status.scalar.await_count == 1


@pytest.mark.asyncio
async def test_tenant_scope_rejects_invalid_tenant_identity():
    scan, raw = unscoped()
    factory, called = sessions()
    with pytest.raises(ValueError):
        await reconcile_pending_postapproval(
            tenant_id="not-a-valid-tenant-uuid",
            scan_factory=scan,
            tenant_factory=factory,
            evaluator=AsyncMock(),
        )
    raw.execute.assert_not_awaited()
    assert not called


@pytest.mark.asyncio
async def test_scope_enforces_global_ceiling_and_minimum_batch():
    tenant = uuid4()
    for requested, expected in ((999, DEFAULT_BATCH_SIZE), (-100, 1)):
        pending = AsyncMock()
        pending.execute.return_value = Rows()
        factory, called = sessions(pending)
        scan, raw = unscoped()
        await reconcile_pending_postapproval(
            tenant_id=tenant,
            batch_size=requested,
            scan_factory=scan,
            tenant_factory=factory,
            evaluator=AsyncMock(),
        )
        assert pending.execute.await_args.args[1]["limit"] == expected
        assert called == [tenant]
        raw.execute.assert_not_awaited()
