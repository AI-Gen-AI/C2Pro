from types import SimpleNamespace

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

    with pytest.raises(HTTPException) as exc_info:
        await require_platform_operator(
            _request_with_identity(
                PlatformIdentity(
                    user_id="user_operator",
                    org_id="org_platform",
                    email="operator@example.test",
                    email_verified=True,
                )
            )
        )

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

    with pytest.raises(HTTPException) as exc_info:
        await require_platform_operator(
            _request_with_identity(
                PlatformIdentity(
                    user_id="user_operator",
                    org_id="org_platform",
                    email="operator@example.test",
                    email_verified=True,
                )
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized"


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
