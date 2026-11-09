"""G1 transactional trust boundary: never promote uncited WBS proposals."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
    _require_source_bound_technical_wbs,
)
from src.analysis.domain.trust import CandidateBinding, StaleCandidateError


def _row(payload: dict):
    return SimpleNamespace(
        artifact_id=uuid4(),
        document_id=uuid4(),
        artifact_version=2,
        artifact_hash="0" * 64,
        trust_state="proposed",
        payload=payload,
    )


def _wbs():
    return [{"code": "1.2", "name": "FAT", "source_quote": "Factory acceptance testing shall be completed no later than 2027-06-10"}]


def _cites():
    return [{
        "type": "wbs",
        "item": "1.2",
        "quote": "Factory acceptance testing shall be completed no later than 2027-06-10",
        "found_in_source": True,
    }]


def test_spec_v2_six_wbs_without_citations_is_not_signable() -> None:
    payload = {"doc_type": "technical_spec", "extracted_wbs": [{"code": str(i)} for i in range(6)], "citations": []}
    with pytest.raises(StaleCandidateError, match="TECHNICAL_WBS_SOURCE_EVIDENCE"):
        _require_source_bound_technical_wbs(_row(payload))


@pytest.mark.parametrize("quotes", [
    [],
    [{"type": "wbs", "item": "1.2", "quote": "a fabricated quotation", "found_in_source": True}],
    [{"type": "wbs", "item": "1.2", "quote": "Factory acceptance testing shall be completed no later than 2027-06-10", "found_in_source": False}],
])
def test_incomplete_or_inconsistent_citation_cannot_promote(quotes):
    payload = {"doc_type": "technical_spec", "extracted_wbs": _wbs(), "citations": quotes}
    with pytest.raises(StaleCandidateError, match="TECHNICAL_WBS_SOURCE_EVIDENCE"):
        _require_source_bound_technical_wbs(_row(payload))


def test_fully_cited_spec_passes_evidence_gate_but_is_not_approved() -> None:
    _require_source_bound_technical_wbs(
        _row({"doc_type": "technical_spec", "extracted_wbs": _wbs(), "citations": _cites()})
    )


def test_contract_unchanged_by_technical_spec_gate() -> None:
    _require_source_bound_technical_wbs(
        _row({"doc_type": "contract", "extracted_wbs": [{"code": "1.1"}], "citations": []})
    )


@pytest.mark.asyncio
async def test_commit_refuses_uncited_spec_before_any_trust_mutation(monkeypatch):
    payload = {"doc_type": "technical_spec", "extracted_wbs": _wbs(), "citations": []}
    row = _row(payload)
    binding = CandidateBinding(
        artifact_id=row.artifact_id,
        document_id=row.document_id,
        artifact_version=row.artifact_version,
        artifact_hash=row.artifact_hash,
    )
    repo = object.__new__(SqlAlchemyDocumentArtifactRepository)
    lock = AsyncMock(return_value=row)
    supersede = AsyncMock()
    monkeypatch.setattr(repo, "_lock", lock)
    monkeypatch.setattr(repo, "_supersede_active_trusted", supersede)
    with pytest.raises(StaleCandidateError, match="TECHNICAL_WBS_SOURCE_EVIDENCE"):
        await repo.commit_candidate(binding, tenant_id=uuid4())
    supersede.assert_not_awaited()
