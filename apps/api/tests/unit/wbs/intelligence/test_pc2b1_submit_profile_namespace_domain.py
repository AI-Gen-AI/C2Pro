"""PC-2b.1 (#920): ADR-029 rule -- a non-core decomposition_kind needs a pinned profile declaring it.

TS-UW-PC2B1-SUBMIT-001 (domain). ``validate_governed_submission`` refuses a non-core namespace no
pinned profile owns, and a term the pinned profile version does not declare. Core-only candidates
are unchanged.
"""

from __future__ import annotations

from uuid import uuid4

from src.wbs.domain.governance import CandidateNode
from src.wbs.domain.governed_change import validate_governed_submission

TERMS = {"solar_pv": frozenset({"block", "mv_system"})}


def _node(kind: str | None) -> CandidateNode:
    return CandidateNode(node_id=uuid4(), parent_id=None, sort_order=1, code="1", name="Root",
                         decomposition_kind=kind, origin_kind="minted")


def test_core_only_candidates_are_unchanged() -> None:
    assert validate_governed_submission([_node("core:system")], [], [], base_node_ids=None) == []
    assert validate_governed_submission([_node(None)], [], [], base_node_ids=None) == []


def test_a_non_core_kind_without_a_pinned_profile_is_refused() -> None:
    violations = validate_governed_submission([_node("solar_pv:block")], [], [], base_node_ids=None)
    assert any("solar_pv" in v and "pinned" in v for v in violations)


def test_a_pinned_and_declared_term_passes() -> None:
    assert validate_governed_submission([_node("solar_pv:block")], [], [], base_node_ids=None, profile_terms=TERMS) == []


def test_a_term_the_pinned_version_does_not_declare_is_refused() -> None:
    violations = validate_governed_submission([_node("solar_pv:spaceship")], [], [], base_node_ids=None,
                                              profile_terms=TERMS)
    assert any("spaceship" in v and "declare" in v for v in violations)
