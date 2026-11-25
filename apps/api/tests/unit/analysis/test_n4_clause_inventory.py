"""JV1-A5 deterministic, synthetic N2 clause inventory; no provider calls."""
from __future__ import annotations

import pytest

from src.analysis.domain.n4_clause_inventory import (
    build_n4_clause_inventory,
    render_n4_clause_inventory_messages,
)


def test_multilingual_numbered_headings_have_exact_source_offsets():
    source = (
        "SECTION 1 Scope\n"
        "The scope includes all equipment.\n"
        "SECCIÓN 2 Plazos\n"
        "Se aplican plazos garantizados.\n"
        "SEÇÃO 3 Pagamento\n"
        "O pagamento depende da aceitação.\n"
        "4.1 Performance testing\n"
        "Testing must occur before acceptance.\n"
    )
    clauses = build_n4_clause_inventory(source)
    assert [clause.clause_ref for clause in clauses] == ["1", "2", "3", "4.1"]
    assert [clause.language for clause in clauses] == ["EN", "ES", "PT", None]
    assert all(
        source[clause.start_offset:clause.end_offset].lstrip().startswith(
            ("SECTION", "SECCIÓN", "SEÇÃO", "4.1")
        )
        for clause in clauses
    )
    assert clauses[-1].end_offset == len(source)


def test_inventory_message_rendering_has_no_3000_character_truncation():
    source = "".join(
        f"{n}.1 Clause heading for equipment and testing obligations\n"
        f"Detailed source paragraph number {n}.\n"
        for n in range(1, 130)
    )
    clauses = build_n4_clause_inventory(source)
    assert len(clauses) == 129
    messages = render_n4_clause_inventory_messages(clauses)
    assert len(messages) > 1
    assert all(len(message) <= 3000 for message in messages)
    for clause in clauses:
        assert sum(
            f"- {clause.clause_ref} |" in message
            for message in messages
        ) == 1


def test_inventory_missing_headings_not_equated_to_verified_absence():
    assert build_n4_clause_inventory("Unnumbered prose without headings.") == ()
    messages = render_n4_clause_inventory_messages(())
    assert len(messages) == 1
    assert "none detected" in messages[0]
    with pytest.raises(ValueError):
        render_n4_clause_inventory_messages((), max_chars=20)


def test_clause_inventory_rejects_non_string_projection():
    with pytest.raises(TypeError):
        build_n4_clause_inventory(None)  # type: ignore[arg-type]
