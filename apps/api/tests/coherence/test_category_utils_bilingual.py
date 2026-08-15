"""Bilingual (Spanish + English) coherence category inference tests.

The deterministic clause categorizer (`infer_category`) was English-keyword-only,
so Spanish clauses defaulted to SCOPE. These tests pin the bilingual behaviour AND
the honesty guard: an administrative clause that merely references the "pliego de
prescripciones técnicas" must classify as LEGAL — NOT TECHNICAL. `infer_category`
picks the max-scoring category, so a legal-dense administrative clause never
fabricates a technical assessment from a passing technical reference.
"""

from __future__ import annotations

import pytest

from src.coherence.models import Clause
from src.coherence.rules_engine.category_utils import infer_category


def _clause(text: str) -> Clause:
    return Clause(id="c-1", text=text, data={})


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Real pilot administrative clauses -> LEGAL, never TECHNICAL.
        (
            "CONTRATO ADMINISTRATIVO DE OBRAS. Partes contratantes: Administración: "
            "Consorcio para el Abastecimiento de Aguas. Empresario: INABENSA, S.A.",
            "LEGAL",
        ),
        (
            "Octava.- las partes se someten a lo dispuesto en el Real Decreto "
            "Legislativo 3/2011, texto refundido de la Ley de Contratos.",
            "LEGAL",
        ),
        # Genuine technical specification clause -> TECHNICAL.
        (
            "La bomba tendrá una potencia nominal de 50 kW y un caudal de 100 m3/h; "
            "las válvulas y tubería de diámetro 200 mm cumplirán la norma UNE aplicable.",
            "TECHNICAL",
        ),
        # Spanish budget / schedule clauses.
        (
            "El importe del contrato es de 1.609.282,94 euros; el pago se realizará "
            "mediante certificación mensual con una retención del 5%.",
            "BUDGET",
        ),
        (
            "El plazo de ejecución será de 12 meses desde la fecha del acta, sin "
            "prórroga salvo causa justificada.",
            "TIME",
        ),
    ],
)
def test_infer_category_bilingual(text: str, expected: str) -> None:
    assert infer_category(_clause(text)) == expected


@pytest.mark.unit
def test_pliego_reference_is_not_technical() -> None:
    """Honesty guard: citing the technical pliego must NOT fabricate a TECHNICAL clause.

    This is the exact shape of the pilot clauses that made TECHNICAL look 'missing';
    withholding is correct — the specs live in a separate, unuploaded pliego.
    """
    text = (
        "El adjudicatario ejecutará las obras conforme al Pliego de prescripciones "
        "técnicas y a las cláusulas administrativas particulares del contrato."
    )
    assert infer_category(_clause(text)) != "TECHNICAL"


@pytest.mark.unit
def test_english_clauses_still_classify() -> None:
    """Adding Spanish keywords must not regress English classification."""
    assert infer_category(_clause("The total contract price and payment retention")) == "BUDGET"
    assert infer_category(_clause("Delivery schedule milestone and deadline dates")) == "TIME"
    assert infer_category(
        _clause("Material specification: pump power rating per ISO standard")
    ) == "TECHNICAL"
