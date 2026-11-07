"""Legacy resume writes must not promote an unbound source locator."""

from __future__ import annotations

from uuid import uuid4

from src.analysis.application import trusted_materialization


def test_unbound_resume_risks_are_explicitly_not_verified() -> None:
    """A pre-#714 review has no artifact/revision authority to bind clauses."""
    risk = {
        "title": "Delay exposure",
        "clause_ref": "6.1",
        "source_locator_status": "VERIFIED",
        "source_references": [{
            "document_id": str(uuid4()),
            "revision_id": str(uuid4()),
            "clause_id": str(uuid4()),
            "clause_code": "6.1",
        }],
    }

    [guarded] = trusted_materialization.unverified_resume_risk_sources([risk])

    assert guarded["source_locator_status"] == "NOT_VERIFIED"
    assert guarded["source_references"] == []
