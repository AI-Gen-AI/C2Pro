"""Onboarding sample-project creates a REAL project (ADR-024).

The previous stub returned a non-UUID id (proj_sample_001) that 422'd every downstream call.

Refers to Suite ID: TS-UA-ONBOARDING-SAMPLE-PROJECT-001.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.core.frontend_support.router import _SAMPLE_PROJECT_CODE, start_sample_project


def _db(existing: object | None) -> MagicMock:
    db = MagicMock()
    db.scalar = AsyncMock(return_value=existing)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.unit
def test_creates_real_project_when_none_exists() -> None:
    tenant_id = uuid4()
    db = _db(existing=None)
    result = asyncio.run(start_sample_project(SimpleNamespace(tenant_id=tenant_id), db))

    db.add.assert_called_once()
    added = db.add.call_args.args[0]
    assert added.tenant_id == tenant_id
    assert added.code == _SAMPLE_PROJECT_CODE
    UUID(result["projectId"])  # a REAL uuid (raises if not)
    assert result["projectId"] in result["route"]
    assert result["reused"] is False
    assert result["duplicateCreated"] is True


@pytest.mark.unit
def test_reuses_existing_sample_project_idempotently() -> None:
    tenant_id = uuid4()
    existing_id = uuid4()
    db = _db(existing=SimpleNamespace(id=existing_id))
    result = asyncio.run(start_sample_project(SimpleNamespace(tenant_id=tenant_id), db))

    db.add.assert_not_called()  # no duplicate created
    assert result["projectId"] == str(existing_id)
    assert result["reused"] is True
    assert result["duplicateCreated"] is False


@pytest.mark.unit
def test_returned_id_is_never_the_old_stub_placeholder() -> None:
    db = _db(existing=None)
    result = asyncio.run(start_sample_project(SimpleNamespace(tenant_id=uuid4()), db))
    assert result["projectId"] != "proj_sample_001"  # the bug we fixed
