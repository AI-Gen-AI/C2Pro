"""Change-intelligence contract tests (ADR-016 / TASK-V3-016-01).

TS-UT-CI-CON-001
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier


def test_semantic_change_is_frozen_forbid_extra_and_honest_null_l1() -> None:
    from src.change_intelligence.domain.contracts import SemanticChange

    change = SemanticChange(
        object_type="clause",
        change_type="modified",
        anchor="5.2",
        before={"clause_code": "5.2"},
        after={"clause_code": "5.2"},
        semantic_summary="clause 5.2 text modified",
        match_confidence=1.0,
        evidence_refs=[
            EvidenceRef(
                ref_id="rev-a:5.2",
                source="contract_clause",
                tier=EvidenceTier.WEAK,
                locator="clause_code=5.2",
            )
        ],
    )

    assert change.severity is None
    assert change.confidence is None
    with pytest.raises(ValidationError):
        change.anchor = "5.3"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SemanticChange(
            object_type="clause",
            change_type="modified",
            anchor="5.2",
            before=None,
            after=None,
            semantic_summary="x",
            match_confidence=1.0,
            unexpected=True,
        )


def test_semantic_change_requires_bounded_match_confidence() -> None:
    from src.change_intelligence.domain.contracts import SemanticChange

    with pytest.raises(ValidationError):
        SemanticChange(
            object_type="clause",
            change_type="modified",
            anchor="5.2",
            before=None,
            after=None,
            semantic_summary="x",
        )
    with pytest.raises(ValidationError):
        SemanticChange(
            object_type="clause",
            change_type="modified",
            anchor="5.2",
            before=None,
            after=None,
            semantic_summary="x",
            match_confidence=1.1,
        )


def test_changeset_is_frozen_and_summarizes_l1_counts() -> None:
    from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange

    changeset = ChangeSet(
        changeset_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        created_at=datetime(2026, 6, 16, 12, 0, 0),
        changes=[
            SemanticChange(
                object_type="clause",
                change_type="added",
                anchor="7.1",
                before=None,
                after={"clause_code": "7.1"},
                semantic_summary="clause 7.1 added",
                match_confidence=1.0,
            ),
            SemanticChange(
                object_type="clause",
                change_type="modified",
                anchor="5.2",
                before={"clause_code": "5.2"},
                after={"clause_code": "5.2"},
                semantic_summary="clause 5.2 text modified",
                match_confidence=0.86,
                needs_review=True,
            ),
        ],
    )

    assert changeset.object_scope == "contract"
    assert changeset.layer == "L1"
    assert changeset.summary_counts == {
        "added": 1,
        "removed": 0,
        "modified": 1,
        "needs_review": 1,
    }
    with pytest.raises(ValidationError):
        changeset.layer = "L2"  # type: ignore[misc]
