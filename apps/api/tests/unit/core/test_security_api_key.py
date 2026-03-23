"""TS-SEC-APIKEY-001

Regression checks for API key validation hardening.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.config import settings
from src.core import security as security_module


@pytest.mark.asyncio
async def test_validate_api_key_returns_tenant_for_known_x_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = str(uuid4())
    monkeypatch.setattr(settings, "integration_api_keys", {"key-live-123": tenant_id})

    request = SimpleNamespace(headers={"x-api-key": "key-live-123"})

    resolved = await security_module.validate_api_key(request=request, credentials=None)

    assert resolved == tenant_id


@pytest.mark.asyncio
async def test_validate_api_key_returns_none_for_bearer_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "integration_api_keys", {"key-live-123": str(uuid4())})
    request = SimpleNamespace(headers={})
    credentials = SimpleNamespace(scheme="Bearer", credentials="jwt-token")

    resolved = await security_module.validate_api_key(request=request, credentials=credentials)

    assert resolved is None


@pytest.mark.asyncio
async def test_validate_api_key_rejects_unknown_x_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "integration_api_keys", {"key-live-123": str(uuid4())})
    request = SimpleNamespace(headers={"x-api-key": "bad-key"})

    with pytest.raises(HTTPException, match="Invalid API key"):
        await security_module.validate_api_key(request=request, credentials=None)
