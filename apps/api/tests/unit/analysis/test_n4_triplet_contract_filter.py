"""N4 must receive all substantive contract clauses, not only penalties.

This tests actual, committed DOCX bytes before any LLM/provider invocation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from src.analysis.adapters.ai.tools.risk_extraction_tool import RiskExtractionTool

_FIXTURES = Path(__file__).resolve().parents[4] / "web/src/tests/e2e/test-data/triplet"


@pytest.mark.parametrize(
    ("filename", "required"),
    [
        (
            "triplet-contract.docx",
            (
                "Objeto.",
                "precio del contrato asciende a 1.000.000 euros",
                "30 de junio de 2027",
                "Penalizaciones.",
            ),
        ),
        (
            "triplet-contract-b.docx",
            (
                "Objeto.",
                "precio del contrato asciende a 1.000.000 euros",
                "30 de junio de 2027",
                "Penalizaciones.",
                "Garantía.",
            ),
        ),
    ],
)
def test_n4_prepreserves_source_contract_scope_price_deadline_and_obligations(
    filename: str,
    required: tuple[str, ...],
) -> None:
    paragraphs = [
        p.text.strip() for p in Document(_FIXTURES / filename).paragraphs if p.text.strip()
    ]
    source = "\n\n".join(paragraphs)
    result = RiskExtractionTool().extract_input_from_state({"document_text": source})
    for expected in required:
        assert expected.casefold() in result.document_text.casefold()
    assert len(result.document_text) < 40_000  # not a truncation issue


@pytest.mark.parametrize(
    "source",
    [
        "2. The contract price is EUR 1,000,000 fixed under this agreement.",
        "3. The completion date is 30 June 2027, with extension only by written variation.",
        "4. El objeto del contrato comprende la ejecución de los trabajos definidos.",
        "5. El plazo de finalización será el 30 de junio de 2027.",
    ],
)
def test_n4_keeps_bilingual_contract_scope_commercial_and_completion_clause(source: str) -> None:
    filtered = RiskExtractionTool()._filter_relevant_text(
        "Some unrelated title.\n\n"
        + source
        + "\n\nPenalty. Delay shall trigger liquidated damages."
    )
    assert source in filtered


@pytest.mark.parametrize(
    "table_line",
    [
        "Tabla de precios unitarios: Precio del contrato, subtotal de partidas y cantidades.",
        "Price schedule: Contract price unit prices subtotal and tax values.",
    ],
)
def test_n4_preserves_price_tables_even_when_terms_match(table_line: str) -> None:
    source = table_line + "\n\nThe Contractor shall maintain a warranty for thirty months."
    filtered = RiskExtractionTool()._filter_relevant_text(source)
    assert table_line in filtered
    assert "warranty" in filtered


@pytest.mark.parametrize(
    "narrative",
    [
        "El presupuesto contractual asciende a EUR 1.200.000, con plazo de finalización 2027-03-31 y garantía de doce meses.",
        "El presupuesto contractual asciende a EUR 1.200.000 y deberá ser pagado por el Cliente tras la recepción.",
    ],
)
def test_n4_does_not_discard_narrative_contract_budget_obligation(narrative: str) -> None:
    price_table = "Tabla de presupuesto contractual: subtotal 2.500 EUR, precio unitario 25 EUR."
    source = narrative + "\n\n" + price_table
    filtered = RiskExtractionTool()._filter_relevant_text(source)
    assert narrative in filtered
    assert price_table in filtered


def test_n4_safeguards_tabular_commercial_claim_even_with_contract_language() -> None:
    table = "Price schedule: Contract price, unit price, subtotal, bill of materials."
    context = "2. The contract price is fixed at EUR 1,000,000."
    filtered = RiskExtractionTool()._filter_relevant_text(table + "\n\n" + context)
    assert context in filtered
    assert table in filtered


def test_n4_golden_epc_all_nine_source_clauses_reach_the_model() -> None:
    """No paid AI: pre-model input must retain every oracle clause verbatim."""
    from scripts.n4_n12_real_ai_eval import _source_text, load_fixture

    fixture = load_fixture()  # verifies immutable source SHA-256
    source = _source_text(fixture)
    filtered = RiskExtractionTool()._filter_relevant_text(source)
    for clause in fixture["contract"]["clauses"]:
        marker = f"{clause['id']}: {clause['text']}"
        assert marker in filtered, f"N4 silently dropped {clause['id']}"
    assert len(filtered) <= 40_000


@pytest.mark.parametrize(
    "clause",
    [
        "Defects. The Contractor shall rectify each notified defect within 14 days.",
        "Variations. The Contractor may act in emergency but must obtain written confirmation.",
        "Defectos. El contratista deberá subsanar cualquier defecto en 14 días.",
        "Variaciones. El contratista ejecutará una orden de cambio únicamente con autorización.",
    ],
)
def test_n4_retains_defects_and_variation_obligations_without_filter_fallthrough(
    clause: str,
) -> None:
    source = (
        "This is an unrelated note.\n\n"
        + clause
        + "\n\nThe Contractor shall pay penalties for delay."
    )
    filtered = RiskExtractionTool()._filter_relevant_text(source)
    assert clause in filtered
    assert "unrelated note" in filtered


def test_n4_preserves_price_table_containing_defects_or_variations() -> None:
    table = "Price schedule: unit price of defect repair and variation, subtotal EUR 12,000."
    clause = "Defects. The Contractor shall rectify each notified defect within 14 days."
    filtered = RiskExtractionTool()._filter_relevant_text(table + "\n\n" + clause)
    assert table in filtered
    assert clause in filtered
