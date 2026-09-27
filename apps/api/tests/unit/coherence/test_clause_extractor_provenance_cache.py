"""#713: coherence cache enrichment must never erase evidence provenance."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.coherence.extraction import clause_extractor
from src.coherence.extraction.clause_extractor import _merge_cache_payload


def test_merge_cache_payload_preserves_evidence_location() -> None:
    evidence_location = {
        "revision_id": "11111111-1111-1111-1111-111111111111",
        "page_number": 3,
        "page_numbers": [3],
        "bbox": [10.0, 20.0, 30.0, 40.0],
        "normalized": True,
    }
    existing = {
        "evidence_location": evidence_location,
        "legacy_field": "keep-me",
        "payment_term_days": 15,
    }

    merged = _merge_cache_payload(
        existing,
        {
            "payment_term_days": 30,
            "warranty_months": 24,
            # An LLM must never be able to overwrite parser-owned provenance.
            "evidence_location": {"page_number": 999},
            "unexpected_model_field": "drop-me",
        },
    )

    assert merged["evidence_location"] == evidence_location
    assert merged["legacy_field"] == "keep-me"
    assert merged["payment_term_days"] == 30
    assert merged["warranty_months"] == 24
    assert "unexpected_model_field" not in merged
    assert existing["payment_term_days"] == 15


def test_merge_cache_payload_handles_empty_existing_payload() -> None:
    assert _merge_cache_payload(None, {"warranty_months": 12}) == {
        "warranty_months": 12
    }



@pytest.mark.asyncio
async def test_write_cache_uses_tenant_scoped_rls_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid4()
    clause_id = uuid4()
    evidence_location = {
        "revision_id": str(uuid4()),
        "page_number": 2,
        "page_numbers": [2],
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "normalized": True,
    }
    clause = SimpleNamespace(
        extracted_entities={
            "evidence_location": evidence_location,
            "payment_term_days": 15,
        }
    )
    row = SimpleNamespace(scalar_one_or_none=lambda: clause)
    session = SimpleNamespace(
        execute=AsyncMock(return_value=row),
        commit=AsyncMock(),
    )
    used_tenants: list[object] = []

    @asynccontextmanager
    async def tenant_session(requested_tenant: object):
        used_tenants.append(requested_tenant)
        yield session

    monkeypatch.setattr(
        "src.core.database.get_session_with_tenant",
        tenant_session,
    )

    await clause_extractor._write_cache(
        str(clause_id),
        {"payment_term_days": 30},
        tenant_id=tenant_id,
    )

    assert used_tenants == [tenant_id]
    assert clause.extracted_entities["evidence_location"] == evidence_location
    assert clause.extracted_entities["payment_term_days"] == 30
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_cache_without_tenant_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    @asynccontextmanager
    async def forbidden_session(_tenant_id: object):
        nonlocal called
        called = True
        yield SimpleNamespace()

    monkeypatch.setattr(
        "src.core.database.get_session_with_tenant",
        forbidden_session,
    )

    await clause_extractor._write_cache(
        str(uuid4()),
        {"warranty_months": 12},
        tenant_id=None,
    )

    assert called is False
