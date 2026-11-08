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
def test_n4_still_excludes_price_tables_even_when_terms_match(table_line: str) -> None:
    source = table_line + "\n\nThe Contractor shall maintain a warranty for thirty months."
    filtered = RiskExtractionTool()._filter_relevant_text(source)
    assert table_line not in filtered
    assert "warranty" in filtered
