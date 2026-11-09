"""G1: technical WBS citations must exist in PROPOSED before human interrupt.

The graph's N15 branch runs AFTER HITL. These tests pin the earlier N5
source-evidence seam so a V3 with valid literal quotes is reviewable.
"""
from uuid import uuid4

import pytest

from src.analysis.adapters.graph.document_artifact_builder import build_document_artifact
from src.analysis.adapters.graph.nodes import (
    _stamp_pre_hitl_technical_wbs_evidence,
    _technical_wbs_review_summary,
)

SOURCE = (
    "6.1 Equipment Technical requirements for transformer, substation, electrical "
    "installation and commissioning. 6.3 Factory Acceptance Test 6.3 Factory "
    "acceptance testing shall be completed no later than 2027-06-10 before dispatch. "
    "The FAT protocol and result must be traceable."
)
QUOTE = "Factory acceptance testing shall be completed no later than 2027-06-10"


def _state(quote: str | None = QUOTE, *, other: str | None = None) -> dict:
    items = [{
        "code": "1.2",
        "name": "Factory Acceptance Test",
        "description": "FAT before dispatch.",
        "parent_code": None,
        "source_quote": quote,
    }]
    if other is not None:
        items.append({
            "code": "1.2.1",
            "name": "Invented secondary activity",
            "parent_code": "1.2",
            "source_quote": other,
        })
    return {
        "doc_type": "technical_spec",
        "document_id": str(uuid4()),
        "document_revision_id": str(uuid4()),
        "document_text": SOURCE,
        "anonymized_text": SOURCE,
        "extracted_wbs": items,
        "extracted_risks": [],
        "citations": [],
        "human_approval_required": True,
    }


def test_n5_pre_hitl_cites_literal_source_and_initial_artifact_keeps_it() -> None:
    state = _state()
    _stamp_pre_hitl_technical_wbs_evidence(state)
    assert state["citation_validation_passed"] is True
    assert state["citations"] == [{
        "type": "wbs", "item": "1.2", "quote": QUOTE, "found_in_source": True
    }]
    artifact = build_document_artifact(state)
    payload = artifact.model_dump(mode="json")
    assert payload["extracted_wbs"][0]["source_quote"] == QUOTE
    assert payload["citations"] == state["citations"]
    assert state["human_approval_required"] is True


@pytest.mark.parametrize("bad", [
    None,
    "",
    QUOTE.lower(),
    "Factory  acceptance testing shall be completed no later than 2027-06-10",
    "Calibrate FAT equipment at 500 MPa",
])
def test_missing_fabricated_case_or_whitespace_changed_quote_fails_before_hitl(bad: str | None) -> None:
    state = _state(bad)
    _stamp_pre_hitl_technical_wbs_evidence(state)
    assert state["citation_validation_passed"] is False
    assert state["citations"][0]["found_in_source"] is False
    summary = _technical_wbs_review_summary(state)
    assert summary["wbs_source_evidence_passed"] is False
    assert summary["wbs_source_evidence_verified"] == 0
    assert summary["wbs_source_evidence"][0]["source_quote"] is None


def test_one_fabricated_item_among_valid_items_blocks_candidate_but_preserves_valid_quote() -> None:
    state = _state(other="Invented mandatory project work package")
    _stamp_pre_hitl_technical_wbs_evidence(state)
    assert state["citation_validation_passed"] is False
    summary = _technical_wbs_review_summary(state)
    assert summary["wbs_source_evidence_total"] == 2
    assert summary["wbs_source_evidence_verified"] == 1
    assert summary["wbs_source_evidence"][0]["source_quote"] == QUOTE
    assert summary["wbs_source_evidence"][1]["source_quote"] is None


def test_no_wbs_is_unassessed_not_validation_passed() -> None:
    state = _state()
    state["extracted_wbs"] = []
    _stamp_pre_hitl_technical_wbs_evidence(state)
    assert state["citation_validation_passed"] is False
    summary = _technical_wbs_review_summary(state)
    assert summary["wbs_source_evidence_total"] == 0
    assert summary["wbs_source_evidence_passed"] is False


def test_critique_or_human_feedback_cannot_supply_source_quote() -> None:
    state = _state("fabricated follow-up criterion")
    state["critique_notes"] = "fabricated follow-up criterion"
    state["human_feedback"] = "fabricated follow-up criterion"
    _stamp_pre_hitl_technical_wbs_evidence(state)
    assert state["citation_validation_passed"] is False


def test_non_technical_document_unchanged() -> None:
    state = _state()
    state["doc_type"] = "contract"
    _stamp_pre_hitl_technical_wbs_evidence(state)
    assert state["citations"] == []
    assert _technical_wbs_review_summary(state) == {}


def test_duplicate_verified_citations_not_shown_as_unique_evidence() -> None:
    state = _state()
    _stamp_pre_hitl_technical_wbs_evidence(state)
    state["citations"].append(dict(state["citations"][0]))
    summary = _technical_wbs_review_summary(state)
    assert summary["wbs_source_evidence"][0]["found_in_analysis_text"] is False
    assert summary["wbs_source_evidence_passed"] is False


@pytest.mark.asyncio
async def test_non_hitl_completion_rejects_failed_n15_before_database_init() -> None:
    from src.analysis.application.document_artifact_completion import _persist_artifact
    from src.analysis.domain.trust import StaleCandidateError

    state = _state()
    _stamp_pre_hitl_technical_wbs_evidence(state)
    assert state["citation_validation_passed"] is True
    # The post-HITL N15 check may degrade even if early N5 validation passed.
    state["citation_validation_passed"] = False
    state["human_approval_required"] = False
    state["tenant_id"] = str(uuid4())
    with pytest.raises(StaleCandidateError, match="TECHNICAL_WBS_FINAL_CITATION_VALIDATION_REQUIRED"):
        await _persist_artifact(state)


@pytest.mark.asyncio
async def test_n17_skips_technical_spec_without_final_n15_evidence() -> None:
    from src.analysis.adapters.graph.nodes import save_to_db_node
    from src.analysis.domain.node_result import NodeStatus

    state = _state()
    _stamp_pre_hitl_technical_wbs_evidence(state)
    state["citation_validation_passed"] = False
    state["human_approval_required"] = False
    state["tenant_id"] = str(uuid4())
    state["node_results"] = []
    state["messages"] = []
    result = await save_to_db_node(state)
    assert result["node_results"][-1].status is NodeStatus.SKIPPED
    assert result["node_results"][-1].degradation_reason == "technical_wbs_source_validation_required"
    assert result.get("analysis_id") is None


@pytest.mark.asyncio
async def test_direct_trusted_repository_save_refuses_uncited_spec_before_supersede(monkeypatch) -> None:
    from unittest.mock import AsyncMock
    from src.analysis.adapters.persistence.document_artifact_repository import SqlAlchemyDocumentArtifactRepository
    from src.analysis.domain.trust import StaleCandidateError, TrustState

    state = _state()
    # Simulates a direct non-HITL save without pre-HITL N5 stamping.
    artifact = build_document_artifact(state)
    repo = object.__new__(SqlAlchemyDocumentArtifactRepository)
    supersede = AsyncMock()
    monkeypatch.setattr(repo, "_supersede_proposed", supersede)
    with pytest.raises(StaleCandidateError, match="TECHNICAL_WBS_SOURCE_EVIDENCE"):
        await repo.save(
            artifact,
            project_id=uuid4(),
            tenant_id=uuid4(),
            trust_state=TrustState.TRUSTED,
        )
    supersede.assert_not_awaited()
