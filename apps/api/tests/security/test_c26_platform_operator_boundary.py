from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.core.auth.platform_operator import (
    PlatformIdentity,
    require_platform_operator,
)


def _request_with_identity(identity: PlatformIdentity | None) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/admin/dlq"})
    if identity is not None:
        request.state.platform_identity = identity
    return request


@pytest.mark.asyncio
async def test_platform_operator_denies_unconfigured_org_before_any_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.core.auth.platform_operator as platform_operator

    lookup_called = False

    async def _lookup(_: str) -> bool:
        nonlocal lookup_called
        lookup_called = True
        return False

    monkeypatch.setattr(
        platform_operator,
        "settings",
        SimpleNamespace(platform_operator_org_id=None, platform_operator_user_ids=[]),
    )
    monkeypatch.setattr(platform_operator, "operator_org_is_contaminated", _lookup)

    identity = PlatformIdentity(
        user_id="user_operator",
        org_id="org_platform",
        email="operator@example.test",
        email_verified=True,
    )
    request = _request_with_identity(identity)

    with pytest.raises(HTTPException) as exc_info:
        await require_platform_operator(request)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized"
    assert lookup_called is False


@pytest.mark.asyncio
async def test_platform_operator_g5_is_deny_only_and_never_grants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.core.auth.platform_operator as platform_operator

    monkeypatch.setattr(
        platform_operator,
        "settings",
        SimpleNamespace(
            platform_operator_org_id="org_platform",
            platform_operator_user_ids=["user_operator"],
        ),
    )

    async def _contaminated(_: str) -> bool:
        return True

    monkeypatch.setattr(platform_operator, "operator_org_is_contaminated", _contaminated)

    identity = PlatformIdentity(
        user_id="user_operator",
        org_id="org_platform",
        email="operator@example.test",
        email_verified=True,
    )
    request = _request_with_identity(identity)

    with pytest.raises(HTTPException) as exc_info:
        await require_platform_operator(request)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized"


@pytest.mark.asyncio
async def test_customer_clerk_identity_is_denied_before_integrity_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.core.auth.platform_operator as platform_operator

    lookup_called = False

    async def _lookup(_: str) -> bool:
        nonlocal lookup_called
        lookup_called = True
        return False

    monkeypatch.setattr(
        platform_operator,
        "settings",
        SimpleNamespace(
            platform_operator_org_id="org_platform",
            platform_operator_user_ids=[],
        ),
    )
    monkeypatch.setattr(platform_operator, "operator_org_is_contaminated", _lookup)

    identity = PlatformIdentity(
        user_id="user_customer_admin",
        org_id="org_customer",
        email="customer-admin@example.test",
        email_verified=True,
    )
    request = _request_with_identity(identity)

    with pytest.raises(HTTPException) as exc_info:
        await require_platform_operator(request)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized"
    assert lookup_called is False


@pytest.mark.asyncio
async def test_platform_operator_returns_tenantless_principal_only_after_all_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.core.auth.platform_operator as platform_operator

    monkeypatch.setattr(
        platform_operator,
        "settings",
        SimpleNamespace(
            platform_operator_org_id="org_platform",
            platform_operator_user_ids=[],
        ),
    )

    async def _clean(_: str) -> bool:
        return False

    monkeypatch.setattr(platform_operator, "operator_org_is_contaminated", _clean)
    bind_context = Mock()
    granted_log = Mock()
    monkeypatch.setattr(platform_operator.structlog.contextvars, "bind_contextvars", bind_context)
    monkeypatch.setattr(platform_operator.logger, "info", granted_log)

    principal = await require_platform_operator(
        _request_with_identity(
            PlatformIdentity(
                user_id="user_Operator",
                org_id="org_platform",
                email="operator@example.test",
                email_verified=True,
            )
        )
    )

    assert principal.clerk_user_id == "user_Operator"
    assert principal.clerk_org_id == "org_platform"
    assert not hasattr(principal, "tenant_id")
    bind_context.assert_called_once_with(
        platform_operator_id="user_Operator",
        org_id="org_platform",
    )
    granted_log.assert_called_once_with(
        "platform_operator_granted",
        clerk_user_id="user_Operator",
        clerk_org_id="org_platform",
    )


@pytest.mark.asyncio
async def test_operator_org_bootstrap_is_blocked_before_tenant_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.core.auth.dependencies as dependencies

    tenant_lookup = AsyncMock()
    tenant_create = AsyncMock()
    monkeypatch.setattr(
        dependencies,
        "settings",
        SimpleNamespace(platform_operator_org_id="org_platform", environment="test"),
    )
    monkeypatch.setattr(dependencies, "lookup_tenant_by_clerk_org_id", tenant_lookup)
    monkeypatch.setattr(dependencies, "create_bootstrap_tenant", tenant_create)

    session = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await dependencies._provision_clerk_user(
            session,
            clerk_user_id="user_operator",
            clerk_org_id="org_platform",
            email="operator@example.test",
            first_name=None,
            last_name=None,
        )

    assert exc_info.value.status_code == 403
    tenant_lookup.assert_not_awaited()
    tenant_create.assert_not_awaited()
