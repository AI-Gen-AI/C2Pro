"""PQ-HITL-06/#942 & #713: source location must stay tenant/revision-bound.

These are repository-boundary, offline synthetic unit tests, not proof of
original-PDF page highlights, multi-clause links or live database RLS.
"""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.documents.application.services.source_locator import SourceLocator
from src.documents.domain.models import Clause, ClauseType


def _clause(
    *,
    tenant_id: UUID,
    document_id: UUID,
    revision_id: UUID,
    clause_code: str,
    text: str,
) -> Clause:
    return Clause(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=tenant_id,
        document_id=document_id,
        revision_id=revision_id,
        clause_code=clause_code,
        clause_type=ClauseType.QUALITY,
        title="Synthetic source",
        full_text=text,
    )


@pytest.mark.asyncio
async def test_same_clause_code_uses_only_requested_revision_and_tenant() -> None:
    """A §5.2 and B §5.2 must never silently collapse into the same source."""
    tenant_id, document_id, revision_a, revision_b = (uuid4() for _ in range(4))
    a = _clause(
        tenant_id=tenant_id,
        document_id=document_id,
        revision_id=revision_a,
        clause_code="5.2",
        text="5.2 Contractor bears the cost within fourteen days of written notice.",
    )
    b = _clause(
        tenant_id=tenant_id,
        document_id=document_id,
        revision_id=revision_b,
        clause_code="5.2",
        text="5.2 Proposed revision: Contractor cost and timeframe are unresolved.",
    )
    repository = AsyncMock()

    async def select_by_revision(**kwargs: object) -> Clause | None:
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["document_id"] == document_id
        assert kwargs["clause_code"] == "5.2"
        return {revision_a: a, revision_b: b}.get(kwargs["revision_id"])

    repository.get_clause_by_document_and_code.side_effect = select_by_revision
    locator = SourceLocator(repository)
    location_a = await locator.locate_evidence(
        "Clause 5.2", document_id, tenant_id, revision_id=revision_a
    )
    location_b = await locator.locate_evidence(
        "Clause 5.2", document_id, tenant_id, revision_id=revision_b
    )

    assert location_a is not None and location_b is not None
    assert location_a.chunk_text == a.full_text
    assert location_b.chunk_text == b.full_text
    assert location_a.chunk_text != location_b.chunk_text
    assert location_a.page_number is None and location_a.bbox is None
    assert location_b.page_number is None and location_b.bbox is None
    assert repository.get_clause_by_document_and_code.await_count == 2
    repository.list_revision_clauses.assert_not_awaited()
    repository.list_current_clauses.assert_not_awaited()
    repository.list_clauses_for_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_fuzzy_path_never_queries_other_revisions_or_all_clause_rows() -> None:
    tenant_id, document_id, revision_id = (uuid4() for _ in range(3))
    text = "The contractor shall remedy defective work within fourteen days."
    source = _clause(
        tenant_id=tenant_id,
        document_id=document_id,
        revision_id=revision_id,
        clause_code="5.2",
        text=text,
    )
    repository = AsyncMock()
    repository.list_revision_clauses.return_value = [source]
    location = await SourceLocator(repository).locate_evidence(
        text, document_id, tenant_id, revision_id=revision_id
    )

    assert location is not None
    assert location.document_id == document_id
    assert location.chunk_text == text
    assert location.page_number is None and location.bbox is None
    repository.list_revision_clauses.assert_awaited_once_with(
        tenant_id, document_id, revision_id
    )
    repository.list_current_clauses.assert_not_awaited()
    repository.list_clauses_for_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_unresolved_trusted_current_never_falls_back_to_historical_rows() -> None:
    tenant_id, document_id = uuid4(), uuid4()
    repository = AsyncMock()
    repository.list_current_clauses.return_value = []

    location = await SourceLocator(repository).locate_evidence(
        "Unresolved current terms", document_id, tenant_id
    )

    assert location is None
    repository.list_current_clauses.assert_awaited_once_with(tenant_id, document_id)
    repository.list_revision_clauses.assert_not_awaited()
    repository.list_clauses_for_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_foreign_tenant_or_missing_revision_has_no_fallback_locator() -> None:
    tenant_id, document_id, revision_id = (uuid4() for _ in range(3))
    repository = AsyncMock()
    repository.get_clause_by_document_and_code.return_value = None
    repository.list_revision_clauses.return_value = []

    location = await SourceLocator(repository).locate_evidence(
        "Clause 6.3", document_id, tenant_id, revision_id=revision_id
    )

    assert location is None
    repository.get_clause_by_document_and_code.assert_awaited_once_with(
        tenant_id=tenant_id,
        document_id=document_id,
        clause_code="6.3",
        revision_id=revision_id,
    )
    repository.list_revision_clauses.assert_awaited_once_with(
        tenant_id, document_id, revision_id
    )
    repository.list_clauses_for_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_tenant_fails_before_calling_repository() -> None:
    repository = AsyncMock()
    with pytest.raises(ValueError, match="tenant_id is required"):
        await SourceLocator(repository).locate_evidence(
            "Clause 5.2", uuid4(), None  # type: ignore[arg-type]
        )
    repository.get_clause_by_document_and_code.assert_not_awaited()
    repository.list_current_clauses.assert_not_awaited()
    repository.list_revision_clauses.assert_not_awaited()
