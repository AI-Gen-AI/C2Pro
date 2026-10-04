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


# --- Review hardening (PR #819) -----------------------------------------------

PROGRESS = "2. The Contractor shall submit the monthly progress report to the Engineer."
SAFETY = "2. The Contractor shall submit the monthly safety report to the Engineer."
PROGRESS_SHIFTED = "3. The Contractor shall submit the monthly progress report to the Engineer for prompt approval."
SCOPE_A = "1. Scope of the works is defined in Annex A of this contract."


def test_reused_number_with_a_competing_candidate_is_never_deterministic() -> None:
    """Codex P1: the shifted, lightly edited clause competes with the inserted one."""
    old = _positional([SCOPE_A, PROGRESS], R1)
    new = _positional([SCOPE_A, SAFETY, PROGRESS_SHIFTED], R2)

    changeset = _diff(old, new)

    assert changeset.changes
    for change in changeset.changes:
        assert change.needs_review is True
        assert change.match_basis != "source_identifier"
    assert (PROGRESS, SAFETY) not in [(_text(c.before), _text(c.after)) for c in changeset.changes]


@pytest.mark.parametrize(
    "text",
    [
        "1.5 million EUR shall be paid to the Contractor on signature.",
        "1.000.000 EUR is the total contract price for the works.",
        "12.5 % of every payment is retained until final acceptance.",
        "Clause 14.1 shall not apply to variations instructed by the Engineer.",
        "2) the contractor shall comply with the site safety rules at all times.",
        "3. the works include demolition of the existing structures on site.",
        "04.10.2026 is the commencement date of the works under this contract.",
        "Page 3 of 10",
    ],
)
def test_incidental_numbers_are_not_source_identifiers(text: str) -> None:
    from src.change_intelligence.application.anchor_resolver import split_source_label

    label, _ = split_source_label(text)

    assert label is None


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("4.2 Payment terms apply to every interim certificate.", "4.2"),
        ("Clause 14.1 Payment of the contract price.", "clause 14.1"),
        ("CLÁUSULA 4.2.- Plazo de ejecución de las obras.", "clausula 4.2"),
        ("Annex III.2 Technical scope of the works.", "annex iii.2"),
        ("2. Price. The contract price is fixed.", "2"),
    ],
)
def test_genuine_headings_remain_source_identifiers(text: str, label: str) -> None:
    from src.change_intelligence.application.anchor_resolver import split_source_label

    assert split_source_label(text)[0] == label


def test_a_number_repeated_inside_one_revision_is_not_an_identifier() -> None:
    old = _positional(
        [
            "1. The Contractor shall provide the following documents to the Engineer.",
            "1. The Employer shall provide access to the site within seven days.",
        ],
        R1,
    )
    new = _positional(
        [
            "1. The Contractor shall provide the following documents to the Engineer promptly.",
            "1. The Employer shall provide access to the site within ten days.",
        ],
        R2,
    )

    changeset = _diff(old, new)

    assert all(change.match_basis != "source_identifier" for change in changeset.changes)
    assert all(change.needs_review for change in changeset.changes)


def test_duplicated_text_under_new_numbers_is_not_a_deterministic_renumbering() -> None:
    old = _positional(["5. Reserved.", "6. Reserved.", "7. Termination for convenience is excluded."], R1)
    new = _positional(["6. Reserved.", "7. Reserved.", "8. Termination for convenience is excluded."], R2)

    changeset = _diff(old, new)

    for change in changeset.changes:
        if _text(change.before).endswith("Reserved.") or _text(change.after).endswith("Reserved."):
            assert change.needs_review is True


@pytest.mark.parametrize(
    ("old_text", "new_text", "allowed"),
    [
        # 1. same content, new identifier -> deterministic renumbering
        ("5.2 Penalty cap is ten percent of the contract value.", "6.1 Penalty cap is ten percent of the contract value.", {"renumbered"}),
        # 2. small edit + new identifier -> never a harmless renumbering
        ("5.2 Penalty cap is ten percent of the contract value.", "6.1 Penalty cap is eleven percent of the contract value.", {"modified"}),
        # 3. material edit + new identifier -> no identity claimed
        ("5.2 Penalty cap is ten percent of the contract value.", "6.1 Insurance must cover all construction risks for the works.", {"added", "removed"}),
    ],
)
def test_renumbering_never_hides_an_edit(old_text: str, new_text: str, allowed: set[str]) -> None:
    changeset = _diff(_positional([old_text], R1), _positional([new_text], R2))

    assert {change.change_type for change in changeset.changes} == allowed
    for change in changeset.changes:
        if change.change_type == "renumbered":
            from src.change_intelligence.application.anchor_resolver import split_source_label

            assert split_source_label(_text(change.before))[1] == split_source_label(_text(change.after))[1]
        if change.change_type == "modified":
            assert change.needs_review is True


LONG_PROGRAMME = (
    "The Contractor shall submit to the Engineer, within twenty-eight days after the Commencement Date, "
    "a detailed time programme showing the order in which the Contractor proposes to carry out the Works, "
    "including each stage of design, procurement, manufacture, delivery, construction, erection and testing, "
    "and shall submit a revised programme whenever the previous programme is inconsistent with actual progress."
)


def test_a_small_edit_to_a_long_clause_is_paired_in_both_directions() -> None:
    other = "The Employer shall give the Contractor right of access to all parts of the Site."
    edited = LONG_PROGRAMME.replace("twenty-eight", "fourteen")
    old, new = _positional([other, LONG_PROGRAMME], R1), _positional([other, edited], R2)

    forward, backward = _diff(old, new), _diff(new, old)

    for changeset in (forward, backward):
        assert [change.change_type for change in changeset.changes] == ["modified"]
        assert changeset.changes[0].match_basis == "similarity_candidate"
    assert forward.changes[0].match_confidence == backward.changes[0].match_confidence


def _inverse(changeset: ChangeSet) -> list[tuple[str, str, str, bool, str | None]]:
    flip = {"added": "removed", "removed": "added"}
    return sorted(
        (flip.get(c.change_type, c.change_type), _text(c.after), _text(c.before), c.needs_review, c.match_basis)
        for c in changeset.changes
    )


def _plain(changeset: ChangeSet) -> list[tuple[str, str, str, bool, str | None]]:
    return sorted(
        (c.change_type, _text(c.before), _text(c.after), c.needs_review, c.match_basis)
        for c in changeset.changes
    )


@pytest.mark.parametrize(
    ("old_texts", "new_texts"),
    [
        ([SCOPE, PRICE, PENALTIES, TERMINATION], [SCOPE, INSURANCE, _renumber(PRICE, "2", "3"), _renumber(PENALTIES, "3", "4"), _renumber(TERMINATION, "4", "5")]),
        ([SCOPE, PRICE, PENALTIES], [SCOPE, PRICE, PENALTIES.replace("0.5%", "1.0%")]),
        ([SCOPE_A, PROGRESS], [SCOPE_A, SAFETY, PROGRESS_SHIFTED]),
        ([SCOPE, PRICE], [SCOPE, INSURANCE]),
        (["5. Reserved.", "6. Reserved.", "7. Termination for convenience is excluded."], ["6. Reserved.", "7. Reserved.", "8. Termination for convenience is excluded."]),
        ([LONG_PROGRAMME, SCOPE], [SCOPE, LONG_PROGRAMME.replace("detailed", "revised detailed")]),
    ],
)
def test_reverse_diff_is_the_inverse_and_calls_do_not_share_state(old_texts: list[str], new_texts: list[str]) -> None:
    old, new = _positional(old_texts, R1), _positional(new_texts, R2)

    forward = _diff(old, new)
    backward = diff_contract_revisions(
        project_id=PROJECT, tenant_id=TENANT, from_revision_id=R2, to_revision_id=R1,
        old_clauses=new, new_clauses=old,
    )
    again = _diff(old, new)

    assert _inverse(forward) == _plain(backward)
    assert _plain(forward) == _plain(again)


def test_every_change_type_carries_revision_bound_evidence() -> None:
    old = _positional(
        [SCOPE, PRICE, PENALTIES, "9. Legacy reporting obligations apply to the Contractor monthly.",
         "The Contractor shall submit the monthly progress report to the Engineer.",
         "The Contractor shall submit the monthly safety report to the Engineer."],
        R1,
    )
    new = _positional(
        [_renumber(SCOPE, "1", "0"), PRICE.replace("1,000,000", "1,100,000"),
         "12. New sustainability reporting obligations apply to the Contractor.",
         "The Contractor shall submit the monthly quality report to the Engineer.",
         PENALTIES.replace("0.5% of the contract price per day", "0.6% of the contract price per day")],
        R2,
    )

    changeset = _diff(old, new)

    assert {"added", "removed", "modified"} <= {change.change_type for change in changeset.changes}
    _assert_revision_bound_evidence(changeset, old, new)
    for change in changeset.changes:
        sides = {ref.ref_id.rsplit(":", 1)[-1] for ref in change.evidence_refs}
        expected = {side for side, snapshot in (("before", change.before), ("after", change.after)) if snapshot}
        assert sides == expected


def test_comparison_budget_fails_closed_instead_of_guessing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Too many mutually similar unpaired clauses: review everything, assert nothing."""
    import src.change_intelligence.application.anchor_resolver as resolver

    monkeypatch.setattr(resolver, "_MAX_FULL_COMPARISONS", 3)
    old = _positional(
        [f"{n}. The Contractor shall submit the monthly report number {n} to the Engineer." for n in range(1, 5)], R1
    )
    new = _positional(
        [f"{n}. The Contractor shall submit the weekly report number {n} to the Engineer." for n in range(1, 5)], R2
    )

    changeset = _diff(old, new)

    assert changeset.changes
    assert _of(changeset, "modified") == []
    for change in changeset.changes:
        assert change.needs_review is True
        assert change.match_basis == "ambiguous"
        assert "comparison budget" in (change.match_rationale or "")
