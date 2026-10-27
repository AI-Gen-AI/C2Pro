"""#1126: deterministic contract-clause reading for Spanish and English clauses.

Spanish contracts (the product's main input) were read as ``OTHER`` because the classifier only knew
English substrings, and ``0,1%`` was read as ``1%`` because the decimal comma was not understood. A
penalty clause's daily rate and its cap were also stored as the same number. These tests pin the
intended behaviour for realistic Spanish EPC clauses and for their English equivalents (which already
worked and must not regress).

Percentages are fractions (``0.001`` is 0.1%), the unit the LEGAL evaluators already expect.
"""

from __future__ import annotations

import pytest

from src.coherence.models import Clause
from src.coherence.rules_engine.base import ApplicabilityState
from src.coherence.rules_engine.deterministic import PenaltyCapEvaluator
from src.core.tasks.ingestion_tasks import (
    _build_contract_clause_data,
    _extract_percentage,
    _infer_contract_clause_type,
)
from src.documents.domain.models import ClauseType

ES_PENALTY = (
    "Penalizaciones. Por demora en la entrega de las obras se aplicará una penalización del "
    "0,1% diario del precio del contrato, con un tope del 10% del precio del contrato."
)
EN_PENALTY = (
    "Liquidated damages for delay shall accrue at 0.1% per day, capped at 10% of the contract price."
)


def _data(text: str) -> dict:
    return _build_contract_clause_data(text, text)


# ── rate and cap, Spanish and English, comma and point ───────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        ES_PENALTY,
        EN_PENALTY,
        # decimal comma inside an English sentence, and the roles in the other order
        "Liquidated damages for delay: capped at 10% of the price, accruing at 0,1% per day.",
        "Penalización por demora: tope máximo del 10% y 0,1% por cada día de retraso.",
        "La demora se penalizará hasta un máximo del 10% del precio, a razón de un 0.1% al día.",
    ],
)
def test_daily_rate_and_cap_are_extracted_separately(text: str) -> None:
    data = _data(text)

    assert data["daily_penalty_pct"] == pytest.approx(0.001)
    assert data["penalty_cap_pct"] == pytest.approx(0.10)


def test_a_clause_with_only_a_daily_rate_does_not_invent_a_cap() -> None:
    data = _data("Penalizaciones. El retraso en la entrega se penalizará con un 0,1% diario del precio del contrato.")

    assert data["daily_penalty_pct"] == pytest.approx(0.001)
    assert "penalty_cap_pct" not in data


def test_a_clause_with_only_a_cap_does_not_invent_a_daily_rate() -> None:
    data = _data("Penalizaciones. La demora se penalizará con un tope del 10% del precio del contrato.")

    assert data["penalty_cap_pct"] == pytest.approx(0.10)
    assert "daily_penalty_pct" not in data


def test_an_unlabelled_percentage_is_not_guessed_as_rate_or_cap() -> None:
    data = _data("Penalty for delay of 5% of the contract price shall apply.")

    assert "daily_penalty_pct" not in data and "penalty_cap_pct" not in data


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0,1% diario", 0.001),
        ("0.1% per day", 0.001),
        ("un 10 % del precio", 0.10),
        ("2,5%", 0.025),
        ("0,125%", 0.00125),
        ("1.000,5%", 10.005),
        ("1,000.5%", 10.005),
        ("12.5 por ciento", 0.125),
    ],
)
def test_decimal_comma_and_point_are_read_by_context(text: str, expected: float) -> None:
    assert _extract_percentage(text) == pytest.approx(expected)


# ── classification, Spanish and English ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # PENALTY
        ("Penalización por demora del 0,1% diario.", ClauseType.PENALTY),
        ("El retraso en la entrega se penalizará con un 0,1% diario.", ClauseType.PENALTY),
        ("PENALIZACIONES. Daños y perjuicios liquidados por retraso.", ClauseType.PENALTY),
        ("Penalty for delay shall apply.", ClauseType.PENALTY),
        ("Liquidated damages are payable by the Contractor.", ClauseType.PENALTY),
        # PAYMENT
        ("Los pagos se realizarán contra certificación mensual.", ClauseType.PAYMENT),
        ("La factura se abonará a 30 días desde su recepción.", ClauseType.PAYMENT),
        ("Payment shall be made against each certified invoice.", ClauseType.PAYMENT),
        # WARRANTY
        ("Garantía. El plazo de garantía será de 24 meses desde la recepción.", ClauseType.WARRANTY),
        ("El contratista responderá de los defectos y vicios ocultos.", ClauseType.WARRANTY),
        ("Responsabilidad. La responsabilidad total del contratista queda limitada al 100% del precio.", ClauseType.WARRANTY),
        ("The Contractor warrants the works against defects.", ClauseType.WARRANTY),
        ("Total liability is limited to the contract price.", ClauseType.WARRANTY),
        # SCOPE
        ("Alcance. El contrato comprende el suministro y montaje de los equipos.", ClauseType.SCOPE),
        ("Objeto. El contratista ejecutará las obras de urbanización descritas en el proyecto.", ClauseType.SCOPE),
        ("The scope includes all deliverables listed in Annex A.", ClauseType.SCOPE),
        # DELIVERY
        ("Plazo. El hito de entrega parcial será el 30 de junio de 2027.", ClauseType.DELIVERY),
        ("Hito 2: entrega del informe final antes del 1 de octubre.", ClauseType.DELIVERY),
        ("The milestone and the final deadline are set in the programme.", ClauseType.DELIVERY),
        # nothing recognisable
        ("Jurisdicción. Las partes se someten a los tribunales de Madrid.", ClauseType.OTHER),
        ("Governing law is the law of Spain.", ClauseType.OTHER),
    ],
)
def test_clause_type_is_inferred_in_spanish_and_english(text: str, expected: ClauseType) -> None:
    assert _infer_contract_clause_type(text) is expected


def test_accents_and_case_do_not_change_the_classification() -> None:
    assert _infer_contract_clause_type("GARANTÍA de 24 meses") is ClauseType.WARRANTY
    assert _infer_contract_clause_type("garantia de 24 meses") is ClauseType.WARRANTY


@pytest.mark.parametrize("text", ["Frameworks and networks are described.", "El capital social asciende a 3.000 euros."])
def test_terms_match_whole_words_not_arbitrary_substrings(text: str) -> None:
    # "frameworks"/"networks" contain "works"; "capital" starts with "cap": neither is a clause type or a cap.
    assert _infer_contract_clause_type(text) is ClauseType.OTHER
    assert "penalty_cap_pct" not in _data(text)


# ── the point of the fix: the LEGAL penalty evaluator can now see Spanish clauses ─────────────────


def _clause(text: str) -> Clause:
    return Clause(id="c1", text=text, data=_data(text))


def test_spanish_penalty_clause_makes_the_legal_penalty_rule_applicable_and_clean() -> None:
    clause = _clause(ES_PENALTY)

    evaluator = PenaltyCapEvaluator()
    assert evaluator.applicability(clause) is ApplicabilityState.EVALUATED
    # 0.1% per day is the configured maximum and a 10% cap is under 15%: assessed, nothing to flag.
    assert evaluator.evaluate_v3(clause) is None


def test_spanish_excessive_penalty_is_flagged_with_the_right_numbers() -> None:
    clause = _clause(
        "Penalizaciones. Por demora se aplicará un 0,5% diario del precio, con un tope del 25% del precio."
    )

    signal = PenaltyCapEvaluator().evaluate_v3(clause)

    assert signal is not None
    assert clause.data["daily_penalty_pct"] == pytest.approx(0.005)
    assert clause.data["penalty_cap_pct"] == pytest.approx(0.25)
