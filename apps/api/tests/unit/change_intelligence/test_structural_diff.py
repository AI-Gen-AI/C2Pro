"""Structural contract diff tests (ADR-016 / TASK-V3-016-02).

TS-UT-CI-DIFF-001
"""

from __future__ import annotations

from uuid import UUID, uuid4

from src.documents.domain.models import Clause, ClauseType


def _clause(
    code: str,
    text: str,
    *,
    project_id: UUID,
    tenant_id: UUID,
    document_id: UUID | None = None,
) -> Clause:
    return Clause(
        id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        document_id=document_id or uuid4(),
        clause_code=code,
        clause_type=ClauseType.OTHER,
        title=f"Clause {code}",
        full_text=text,
        text_start_offset=10,
        text_end_offset=10 + len(text),
    )


def test_rev_c_to_rev_d_detects_added_removed_and_modified_with_anchors() -> None:
    from src.change_intelligence.application.structural_diff import diff_contract_revisions

    project_id = uuid4()
    tenant_id = uuid4()
    from_revision_id = uuid4()
    to_revision_id = uuid4()
    old_clauses = [
        _clause(
            "1.1",
            "The contractor shall mobilize within 10 days.",
            project_id=project_id,
            tenant_id=tenant_id,
        ),
        _clause("5.2", "Penalty cap is 10 percent.", project_id=project_id, tenant_id=tenant_id),
        _clause("9.1", "Legacy reporting clause.", project_id=project_id, tenant_id=tenant_id),
    ]
    new_clauses = [
        _clause(
            "1.1",
            "The contractor shall mobilize within 10 days.",
            project_id=project_id,
            tenant_id=tenant_id,
        ),
        _clause("5.2", "Penalty cap is 15 percent.", project_id=project_id, tenant_id=tenant_id),
        _clause(
            "12.1",
            "New sustainability reporting clause.",
            project_id=project_id,
            tenant_id=tenant_id,
        ),
    ]

    changeset = diff_contract_revisions(
        project_id=project_id,
        tenant_id=tenant_id,
        from_revision_id=from_revision_id,
        to_revision_id=to_revision_id,
        old_clauses=old_clauses,
        new_clauses=new_clauses,
    )

    by_type = {change.change_type: change for change in changeset.changes}
    assert set(by_type) == {"added", "removed", "modified"}
    assert by_type["modified"].anchor == "5.2"
    assert by_type["modified"].before["clause_code"] == "5.2"
    assert by_type["modified"].after["clause_code"] == "5.2"
    assert by_type["added"].before is None
    assert by_type["added"].after["clause_code"] == "12.1"
    assert by_type["removed"].before["clause_code"] == "9.1"
    assert by_type["removed"].after is None
    assert changeset.summary_counts == {
        "added": 1,
        "removed": 1,
        "modified": 1,
        "needs_review": 0,
    }


def test_whitespace_only_changes_are_omitted() -> None:
    from src.change_intelligence.application.structural_diff import diff_contract_revisions

    project_id = uuid4()
    tenant_id = uuid4()
    changeset = diff_contract_revisions(
        project_id=project_id,
        tenant_id=tenant_id,
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        old_clauses=[
            _clause(
                "1.1",
                "The contractor shall mobilize within 10 days.",
                project_id=project_id,
                tenant_id=tenant_id,
            )
        ],
        new_clauses=[
            _clause(
                "1.1",
                "The contractor shall   mobilize\nwithin 10 days.",
                project_id=project_id,
                tenant_id=tenant_id,
            )
        ],
    )

    assert changeset.changes == []


def test_modified_change_carries_evidence_and_l1_honest_null_fields() -> None:
    from src.change_intelligence.application.structural_diff import diff_contract_revisions

    project_id = uuid4()
    tenant_id = uuid4()
    changeset = diff_contract_revisions(
        project_id=project_id,
        tenant_id=tenant_id,
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        old_clauses=[
            _clause("5.2", "Penalty cap is 10 percent.", project_id=project_id, tenant_id=tenant_id)
        ],
        new_clauses=[
            _clause("5.2", "Penalty cap is 15 percent.", project_id=project_id, tenant_id=tenant_id)
        ],
    )

    change = changeset.changes[0]
    assert change.evidence_refs
    assert change.severity is None
    assert change.confidence is None


def test_low_confidence_anchor_sets_needs_review() -> None:
    from src.change_intelligence.application.structural_diff import diff_contract_revisions

    project_id = uuid4()
    tenant_id = uuid4()
    changeset = diff_contract_revisions(
        project_id=project_id,
        tenant_id=tenant_id,
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        old_clauses=[
            _clause(
                "5.2",
                "Penalty cap is limited to 10 percent of contract value.",
                project_id=project_id,
                tenant_id=tenant_id,
            )
        ],
        new_clauses=[
            _clause(
                "6.1",
                "Penalty cap is capped at 15 percent of contract value.",
                project_id=project_id,
                tenant_id=tenant_id,
            )
        ],
        fuzzy_threshold=0.8,
    )

    assert len(changeset.changes) == 1
    assert changeset.changes[0].change_type == "modified"
    assert changeset.changes[0].needs_review is True
