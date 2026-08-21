"""
Project-identity consistency comparator (SCOPE cross-reference, ADR-023).

Refers to Suite ID: TS-UD-COH-IDENTITY-001.
"""
from __future__ import annotations

import pytest

from src.coherence.cross_document.identity import (
    RULE_PROJECT_IDENTITY_MISMATCH,
    project_identity_mismatch,
)


@pytest.mark.unit
def test_flags_similar_but_different_location() -> None:
    """The golden LA_ROBLA pattern: name says 'Roda', contract says 'Robla' (a mislabel)."""
    finding = project_identity_mismatch(
        "LAV La Roda-Pobla de Lena",
        "ejecucion de las obras en La Robla-Pola de Lena, provincia de Leon",
    )
    assert finding is not None
    assert finding.rule_id == RULE_PROJECT_IDENTITY_MISMATCH
    assert finding.category == "SCOPE"
    assert finding.source == "deterministic"
    assert finding.raw_data["project_token"] == "Roda"
    assert finding.raw_data["contract_token"] == "robla"


@pytest.mark.unit
def test_consistent_name_yields_no_finding() -> None:
    assert (
        project_identity_mismatch(
            "Planta Solar Sanlucar",
            "contrato para la ejecucion de la Planta Solar en Sanlucar de Barrameda",
        )
        is None
    )


@pytest.mark.unit
def test_prefix_divergence_is_not_a_mislabel() -> None:
    """'Bioenergia' vs 'Agroenergia' share a suffix but diverge at the prefix — not a typo."""
    assert (
        project_identity_mismatch(
            "Planta Bioenergia Campillos",
            "contrato de la planta Agroenergia en Campillos",
        )
        is None
    )


@pytest.mark.unit
def test_lowercase_common_words_are_not_matched() -> None:
    """A common lowercase word ('toda') must not spuriously match a name token ('Roda')."""
    finding = project_identity_mismatch("La Roda", "toda la obra ejecutada en La Robla")
    assert finding is not None
    assert finding.raw_data["contract_token"] == "robla"  # matched the proper noun, not 'toda'


@pytest.mark.unit
def test_empty_inputs_are_safe() -> None:
    assert project_identity_mismatch("", "contract text") is None
    assert project_identity_mismatch("Project X", "") is None
    assert project_identity_mismatch("Project X", "lowercase only, no proper nouns") is None
