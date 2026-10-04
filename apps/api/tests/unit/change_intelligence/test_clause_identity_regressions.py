"""Cross-revision clause identity regressions (Lane C / PR-C1).

TS-UT-CI-IDENT-001

Ingestion assigns synthetic positional codes (``AUTO-001``...). Those codes are
processing artifacts, not identity evidence: before PR-C1 a single clause
inserted near the top of V2 shifted every later code and the L1 diff reported a
cascade of fabricated ``modified`` changes at confidence 1.0 with no review.

These tests pin the fail-closed identity policy:

1. exact normalized content       -> deterministic continuity;
2. source identifier read from the clause's own source text -> deterministic,
   only while the revision pair shows no renumbering;
3. similarity                     -> review-required candidate only;
4. ambiguity                      -> no pairing, review required.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.change_intelligence.application.structural_diff import diff_contract_revisions
from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.documents.domain.models import Clause, ClauseType

PROJECT = uuid4()
TENANT = uuid4()
DOCUMENT = uuid4()
R1 = uuid4()
R2 = uuid4()

SCOPE = "1. Scope. The Contractor shall execute the civil works described in Annex A in full."
PRICE = "2. Price. The contract price is EUR 1,000,000 payable in monthly instalments against valuations."
PENALTIES = "3. Penalties. Delay penalties are 0.5% of the contract price per day, capped at 10% in total."
TERMINATION = "4. Termination. Either party may terminate for material breach after thirty days written notice."
INSURANCE = "2. Insurance. The Contractor shall maintain all-risk insurance for the full duration of works."


def _renumber(text: str, old: str, new: str) -> str:
    return text.replace(f"{old}.", f"{new}.", 1)


def _extract(text: str, revision_id: UUID) -> list[Clause]:
    from src.core.tasks.ingestion_tasks import _extract_contract_clauses

    return _extract_contract_clauses(
        document_id=DOCUMENT,
        project_id=PROJECT,
        tenant_id=TENANT,
        parsed_text=text,
        parsed_payload=None,
        revision_id=revision_id,
    )


def _clause(text: str, *, code: str, revision_id: UUID = R1) -> Clause:
    return Clause(
        id=uuid4(),
        project_id=PROJECT,
        tenant_id=TENANT,
        document_id=DOCUMENT,
        clause_code=code,
        clause_type=ClauseType.OTHER,
        title=None,
        full_text=text,
        text_start_offset=0,
        text_end_offset=len(text),
        extracted_entities={"evidence_location": {"revision_id": str(revision_id)}},
    )


def _positional(texts: list[str], revision_id: UUID) -> list[Clause]:
    """Mirror ingestion: ordinal AUTO codes, which carry no identity."""
    return [
        _clause(text, code=f"AUTO-{index:03d}", revision_id=revision_id)
        for index, text in enumerate(texts, start=1)
    ]


def _diff(old: list[Clause], new: list[Clause]) -> ChangeSet:
    return diff_contract_revisions(
        project_id=PROJECT,
        tenant_id=TENANT,
        from_revision_id=R1,
        to_revision_id=R2,
        old_clauses=old,
        new_clauses=new,
    )


def _of(changeset: ChangeSet, change_type: str) -> list[SemanticChange]:
    return [change for change in changeset.changes if change.change_type == change_type]


def _text(snapshot: dict[str, object] | None) -> str:
    return str((snapshot or {}).get("full_text") or "")


def _assert_revision_bound_evidence(changeset: ChangeSet, old: list[Clause], new: list[Clause]) -> None:
    """Before evidence comes only from V1 and after evidence only from V2."""
    old_text = {clause.full_text for clause in old}
    new_text = {clause.full_text for clause in new}
    for change in changeset.changes:
        if change.before is not None:
            assert _text(change.before) in old_text
        if change.after is not None:
            assert _text(change.after) in new_text
        for ref in change.evidence_refs:
            if ref.ref_id.endswith(":before"):
                assert ref.ref_id.startswith(f"{R1}:")
            else:
                assert ref.ref_id.endswith(":after")
                assert ref.ref_id.startswith(f"{R2}:")


# --- A. unchanged -----------------------------------------------------------


def test_a_identical_revisions_produce_no_changes() -> None:
    text = "\n\n".join([SCOPE, PRICE, PENALTIES, TERMINATION])

    changeset = _diff(_extract(text, R1), _extract(text, R2))

    assert changeset.changes == []


# --- B. insertion (exact P0 repro) -----------------------------------------


def test_b_p0_repro_insertion_does_not_cascade_fabricated_modifications() -> None:
    v1 = "\n\n".join([SCOPE, PRICE, PENALTIES, TERMINATION])
    v2 = "\n\n".join(
        [
            SCOPE,
            INSURANCE,
            _renumber(PRICE, "2", "3"),
            _renumber(PENALTIES, "3", "4"),
            _renumber(TERMINATION, "4", "5"),
        ]
    )
    old, new = _extract(v1, R1), _extract(v2, R2)
    # The extractor still assigns positional codes; identity must not use them.
    assert [clause.clause_code for clause in new][:2] == ["AUTO-001", "AUTO-002"]

    changeset = _diff(old, new)

    assert _of(changeset, "modified") == []
    assert _of(changeset, "removed") == []
    added = _of(changeset, "added")
    assert [_text(change.after) for change in added] == [INSURANCE]
    renumbered = _of(changeset, "renumbered")
    assert sorted((_text(c.before), _text(c.after)) for c in renumbered) == sorted(
        [
            (PRICE, _renumber(PRICE, "2", "3")),
            (PENALTIES, _renumber(PENALTIES, "3", "4")),
            (TERMINATION, _renumber(TERMINATION, "4", "5")),
        ]
    )
    for change in renumbered:
        assert change.match_basis == "exact_content"
        assert change.needs_review is False
    _assert_revision_bound_evidence(changeset, old, new)


def test_b_insertion_without_source_numbers_reports_only_the_added_clause() -> None:
    bodies = [
        "The Contractor shall execute the civil works described in Annex A in full.",
        "The contract price is EUR 1,000,000 payable in monthly instalments.",
        "Delay penalties are 0.5% of the contract price per day, capped at 10%.",
    ]
    inserted = "The Contractor shall maintain all-risk insurance for the full duration of works."
    old = _positional(bodies, R1)
    new = _positional([bodies[0], inserted, *bodies[1:]], R2)

    changeset = _diff(old, new)

    assert [(change.change_type, _text(change.after)) for change in changeset.changes] == [
        ("added", inserted)
    ]


# --- C. removal ---------------------------------------------------------------


def test_c_removal_reports_the_removed_clause_without_cascade() -> None:
    bodies = [
        "The Contractor shall execute the civil works described in Annex A in full.",
        "The contract price is EUR 1,000,000 payable in monthly instalments.",
        "Delay penalties are 0.5% of the contract price per day, capped at 10%.",
        "Either party may terminate for material breach after thirty days notice.",
    ]
    old = _positional(bodies, R1)
    new = _positional([bodies[0], *bodies[2:]], R2)

    changeset = _diff(old, new)

    assert [(change.change_type, _text(change.before)) for change in changeset.changes] == [
        ("removed", bodies[1])
    ]
    _assert_revision_bound_evidence(changeset, old, new)


# --- D. reorder ---------------------------------------------------------------


def test_d_reorder_without_text_change_is_not_reported_as_rewrites() -> None:
    bodies = [
        "The Contractor shall execute the civil works described in Annex A in full.",
        "The contract price is EUR 1,000,000 payable in monthly instalments.",
        "Delay penalties are 0.5% of the contract price per day, capped at 10%.",
    ]
    changeset = _diff(_positional(bodies, R1), _positional(list(reversed(bodies)), R2))

    assert changeset.changes == []


def test_d_reorder_with_source_renumbering_is_renumbering_not_modification() -> None:
    old = _positional([SCOPE, PRICE, PENALTIES], R1)
    new = _positional(
        [SCOPE, _renumber(PENALTIES, "3", "2"), _renumber(PRICE, "2", "3")], R2
    )

    changeset = _diff(old, new)

    assert _of(changeset, "modified") == []
    assert len(_of(changeset, "renumbered")) == 2


# --- E. real modification -----------------------------------------------------


def test_e_modification_of_stable_source_identifier_is_deterministic() -> None:
    edited = PENALTIES.replace("0.5%", "1.0%").replace("10%", "15%")
    old = _positional([SCOPE, PRICE, PENALTIES], R1)
    new = _positional([SCOPE, PRICE, edited], R2)

    changeset = _diff(old, new)

    assert len(changeset.changes) == 1
    change = changeset.changes[0]
    assert change.change_type == "modified"
    assert change.match_basis == "source_identifier"
    assert change.anchor == "3"
    assert change.needs_review is False
    assert (_text(change.before), _text(change.after)) == (PENALTIES, edited)
    _assert_revision_bound_evidence(changeset, old, new)


def test_e_modification_without_stable_identifier_is_a_review_candidate() -> None:
    before = "Delay penalties are 0.5% of the contract price per day, capped at 10% in total."
    after = "Delay penalties are 1.0% of the contract price per day, capped at 10% in total."
    other = "The Contractor shall execute the civil works described in Annex A in full."
    old = _positional([other, before], R1)
    new = _positional([other, after], R2)

    changeset = _diff(old, new)

    assert len(changeset.changes) == 1
    change = changeset.changes[0]
    assert change.change_type == "modified"
    assert change.match_basis == "similarity_candidate"
    assert change.needs_review is True
    assert change.match_rationale
    assert 0.0 < change.match_confidence < 1.0
    assert (_text(change.before), _text(change.after)) == (before, after)


def test_e_insertion_plus_edit_never_pairs_by_shifted_source_number() -> None:
    """Renumbering in the same revision makes source numbers non-identity."""
    edited_price = _renumber(PRICE, "2", "3").replace("1,000,000", "1,200,000")
    old = _positional([SCOPE, PRICE, PENALTIES], R1)
    new = _positional(
        [SCOPE, INSURANCE, edited_price, _renumber(PENALTIES, "3", "4")], R2
    )

    changeset = _diff(old, new)

    for change in _of(changeset, "modified"):
        # "2. Price" must never be presented as rewritten into "2. Insurance".
        assert (_text(change.before), _text(change.after)) != (PRICE, INSURANCE)
        assert change.needs_review is True
    modified = _of(changeset, "modified")
    assert [(_text(c.before), _text(c.after)) for c in modified] == [(PRICE, edited_price)]
    assert [_text(c.after) for c in _of(changeset, "added")] == [INSURANCE]


def test_e_shifted_numbers_with_every_later_clause_edited_are_not_asserted() -> None:
    """No unchanged clause reveals the renumbering, so numbers alone cannot pair."""
    old = _positional([SCOPE, PRICE, PENALTIES], R1)
    new = _positional(
        [
            SCOPE,
            INSURANCE,
            _renumber(PRICE, "2", "3").replace("1,000,000", "1,200,000"),
            _renumber(PENALTIES, "3", "4").replace("0.5%", "0.7%"),
        ],
        R2,
    )

    changeset = _diff(old, new)

    for change in _of(changeset, "modified"):
        if (_text(change.before), _text(change.after)) == (PRICE, INSURANCE):
            assert change.needs_review is True
            assert change.match_confidence < 1.0
    assert all(
        change.needs_review
        for change in _of(changeset, "modified")
        if change.match_basis == "source_identifier"
    )


def test_e_rewritten_clause_under_the_same_number_needs_review() -> None:
    old = _positional([SCOPE, PRICE], R1)
    new = _positional([SCOPE, INSURANCE], R2)

    changeset = _diff(old, new)

    (change,) = changeset.changes
    assert change.change_type == "modified"
    assert change.match_basis == "source_identifier"
    assert change.needs_review is True
    assert change.match_confidence < 1.0
    assert "2" in (change.match_rationale or "")


# --- F. renumbering -----------------------------------------------------------


def test_f_renumbering_is_reported_with_both_source_identifiers() -> None:
    old = _positional(["5.2 Penalty cap is limited to 10 percent of contract value."], R1)
    new = _positional(["6.1 Penalty cap is limited to 10 percent of contract value."], R2)

    changeset = _diff(old, new)

    assert len(changeset.changes) == 1
    change = changeset.changes[0]
    assert change.change_type == "renumbered"
    assert change.match_basis == "exact_content"
    assert change.needs_review is False
    assert change.match_rationale is not None
    assert "5.2" in change.match_rationale and "6.1" in change.match_rationale
    assert changeset.summary_counts["renumbered"] == 1
    assert changeset.summary_counts["modified"] == 0


# --- G. ambiguous duplicates -------------------------------------------------


def test_g_near_duplicate_candidates_fail_closed() -> None:
    old = _positional(
        [
            "The Contractor shall submit the monthly progress report to the Engineer.",
            "The Contractor shall submit the monthly safety report to the Engineer.",
        ],
        R1,
    )
    new = _positional(
        ["The Contractor shall submit the monthly quality report to the Engineer."], R2
    )

    changeset = _diff(old, new)

    assert _of(changeset, "modified") == []
    assert changeset.changes
    for change in changeset.changes:
        assert change.needs_review is True
        assert change.match_basis == "ambiguous"
        assert change.match_confidence < 1.0


def test_g_identical_duplicates_with_unequal_counts_fail_closed() -> None:
    boilerplate = "This clause is intentionally reserved and has no contractual effect."
    old = _positional([boilerplate, boilerplate], R1)
    new = _positional([boilerplate], R2)

    changeset = _diff(old, new)

    assert changeset.changes
    assert all(change.needs_review for change in changeset.changes)
    assert all(change.match_confidence < 1.0 for change in changeset.changes)


def test_g_duplicate_synthetic_codes_are_not_identity() -> None:
    old = [
        _clause("Penalty cap is limited to ten percent.", code="AUTO-001"),
        _clause("Monthly reporting is due on day five.", code="AUTO-001"),
    ]
    new = [_clause("Insurance must cover all risks of works.", code="AUTO-001", revision_id=R2)]

    changeset = _diff(old, new)

    assert _of(changeset, "modified") == []
    assert {change.change_type for change in changeset.changes} == {"added", "removed"}


def test_bare_clause_code_without_source_evidence_is_not_identity() -> None:
    """A code that does not appear in the clause's own source text is unproven."""
    old = [_clause("Penalty cap is 10 percent.", code="5.2")]
    new = [_clause("Insurance is required for all works.", code="5.2", revision_id=R2)]

    changeset = _diff(old, new)

    assert _of(changeset, "modified") == []
    assert {change.change_type for change in changeset.changes} == {"added", "removed"}


# --- H. idempotency -----------------------------------------------------------


def _fingerprint(changeset: ChangeSet) -> list[dict[str, object]]:
    return [change.model_dump(mode="json") for change in changeset.changes]


@pytest.mark.parametrize(
    "new_texts",
    [
        [SCOPE, INSURANCE, _renumber(PRICE, "2", "3"), _renumber(PENALTIES, "3", "4")],
        [SCOPE, PRICE.replace("1,000,000", "1,500,000"), PENALTIES],
        [SCOPE, PENALTIES],
    ],
)
def test_h_repeated_diff_is_deterministic(new_texts: list[str]) -> None:
    old = _positional([SCOPE, PRICE, PENALTIES], R1)
    new = _positional(new_texts, R2)

    first = _diff(old, new)
    second = _diff(old, new)
    reversed_input = _diff(list(reversed(old)), new)

    assert _fingerprint(first) == _fingerprint(second)
    assert sorted(map(str, _fingerprint(first))) == sorted(map(str, _fingerprint(reversed_input)))
