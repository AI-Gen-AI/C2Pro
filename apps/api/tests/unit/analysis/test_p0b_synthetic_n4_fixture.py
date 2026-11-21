from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

"""Test-only rehearsal fixture: does not represent genuine N4 AI output."""
from tests.e2e_seed.p0b_synthetic_n4 import proposed_fixture_risks


def test_fixture_matches_only_exact_public_contract_source() -> None:
    sample = (
        "SAMPLE CONSTRUCTION CONTRACT\n"
        "The total contract price is EUR 2,400,000 and is fixed.\n"
        "Liquidated damages of EUR 3,000 per calendar day shall apply."
    )
    proposal = proposed_fixture_risks(sample)
    assert len(proposal) == 1
    assert proposal[0]["source_quote"] in sample
    assert proposed_fixture_risks(sample.replace("3,000", "2,000")) == []
    assert proposed_fixture_risks("PRIVATE CONTRACT with unknown material") == []


@pytest.mark.asyncio
async def test_explicit_test_fixture_passes_source_verification_without_model_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fitz

    from src.analysis.adapters.graph.nodes import risk_extractor_node

    pdf = (
        Path(__file__).resolve().parents[4]
        / "web/src/tests/e2e/test-data/sample-contract.pdf"
    )
    with fitz.open(pdf) as doc:
        public_text = "\n".join(page.get_text() for page in doc)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    monkeypatch.setenv("C2PRO_P0B_SYNTHETIC_N4_FIXTURE", "1")
    monkeypatch.setenv("C2PRO_N4_GRAPH_LEDGER_ENABLED", "0")
    state: dict[str, Any] = {
        "document_text": public_text,
        "anonymized_text": public_text,
        "messages": [],
        "node_results": [],
        "doc_type": "contract",
    }
    outcome = await risk_extractor_node(state)
    assert len(outcome["extracted_risks"]) == 1
    assert outcome["extracted_risks"][0]["source_quote_status"] == "VERIFIED"
    assert outcome["human_approval_required"] is True
    assert outcome["confidence_score"] is None
    assert outcome["risk_extraction_outcome"] == "SYNTHETIC_CI_NOT_MODEL_ASSESSED"

    # Without the opt-in, exactly the same source must fail closed.
    monkeypatch.delenv("C2PRO_P0B_SYNTHETIC_N4_FIXTURE")
    without_opt_in = await risk_extractor_node({
        "document_text": public_text, "anonymized_text": public_text,
        "messages": [], "node_results": [], "doc_type": "contract",
    })
    assert without_opt_in["workflow_terminated"] is True
    assert without_opt_in["extracted_risks"] == []
