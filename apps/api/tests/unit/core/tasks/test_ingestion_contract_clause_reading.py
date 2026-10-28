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
    _infer_contract_clause_type,
)
from src.documents.domain.contract_clause_reader import extract_percentages, penalty_rate_and_cap
from src.documents.domain.models import ClauseType

ES_PENALTY = (
    "Penalizaciones. Por demora en la entrega de las obras se aplicará una penalización del "
    "0,1% diario del precio del contrato, con un tope del 10% del precio del contrato."
)
EN_PENALTY = "Liquidated damages for delay shall accrue at 0.1% per day, capped at 10% of the contract price."


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
    data = _data(
        "Penalizaciones. El retraso en la entrega se penalizará con un 0,1% diario del precio del contrato."
    )

    assert data["daily_penalty_pct"] == pytest.approx(0.001)
    assert "penalty_cap_pct" not in data


def test_a_clause_with_only_a_cap_does_not_invent_a_daily_rate() -> None:
    data = _data(
        "Penalizaciones. La demora se penalizará con un tope del 10% del precio del contrato."
    )

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
    assert extract_percentages(text)[0].value == pytest.approx(expected)


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
        (
            "Garantía. El plazo de garantía será de 24 meses desde la recepción.",
            ClauseType.WARRANTY,
        ),
        ("El contratista responderá de los defectos y vicios ocultos.", ClauseType.WARRANTY),
        (
            "Responsabilidad. La responsabilidad total del contratista queda limitada al 100% del precio.",
            ClauseType.WARRANTY,
        ),
        ("The Contractor warrants the works against defects.", ClauseType.WARRANTY),
        ("Total liability is limited to the contract price.", ClauseType.WARRANTY),
        # SCOPE
        (
            "Alcance. El contrato comprende el suministro y montaje de los equipos.",
            ClauseType.SCOPE,
        ),
        (
            "Objeto. El contratista ejecutará las obras de urbanización descritas en el proyecto.",
            ClauseType.SCOPE,
        ),
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


@pytest.mark.parametrize(
    "text", ["Frameworks and networks are described.", "El capital social asciende a 3.000 euros."]
)
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


# ── review findings (independent review of this fix) ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        # a role term sits BETWEEN the two percentages: each term claims only its nearest number
        "La penalización diaria será del 0,1% y el tope del 10%.",
        "Daily penalty shall be 0.1% and the cap shall be 10%.",
        "Liquidated damages are not to exceed 10% and accrue at 0.1% per day.",
        "La demora se penalizará con 0,1% al día, no superará el 10% del precio.",
        "Penalización por demora: 0,1% diario, hasta un 10% del precio del contrato.",
    ],
)
def test_a_role_term_between_two_percentages_does_not_swap_the_roles(text: str) -> None:
    assert penalty_rate_and_cap(text) == (pytest.approx(0.001), pytest.approx(0.10))


@pytest.mark.parametrize(
    "text",
    [
        "Por demora, penalización de 0,1% diario. La responsabilidad total queda limitada al 100% del precio.",
        "Penalty for delay of 0.1% per day. Total liability shall not exceed 100% of the price.",
        "Por demora 0,1% diario. Retención del 5% de cada pago. Tope del 10%.",
        "Penalty for delay of 0.1% per day. Advance payment of 20% is repaid; maximum 10%.",
        # one sentence: "limited to" marks a liability limit, not a penalty cap
        "Por demora se aplicará 0,1% diario y la responsabilidad total queda limitada al 100% del precio.",
    ],
)
def test_a_liability_limit_or_retention_is_never_taken_for_the_penalty_cap(text: str) -> None:
    daily, cap = penalty_rate_and_cap(text)

    assert daily == pytest.approx(0.001)
    assert cap is None


def test_a_weekly_rate_is_not_a_daily_rate_and_the_cap_survives() -> None:
    daily, cap = penalty_rate_and_cap(
        "Liquidated damages: 0.5% per week, capped at 10% of the price."
    )

    assert daily is None
    assert cap == pytest.approx(0.10)


def test_an_unrelated_maximum_does_not_make_a_percentage_a_cap() -> None:
    daily, cap = penalty_rate_and_cap(
        "Penalización del 10% con un máximo de 90 días y un 0,1% diario."
    )

    assert daily == pytest.approx(0.001)
    assert cap is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10,5.5%", []),
        ("0.5.2%", []),
        ("1.000.000%", []),
        ("1.000%", [0.01]),  # documented: a lone mark in a percentage is the decimal mark
        ("5 per cent", [0.05]),
        ("10 por cien", [0.10]),
        ("10 percentage", []),
        ("entre el 5 y el 10%", [0.10]),
    ],
)
def test_percentage_tokens_are_validated(text: str, expected: list[float]) -> None:
    assert [m.value for m in extract_percentages(text)] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cláusula penal por incumplimiento de plazos.", ClauseType.PENALTY),
        ("Se aplicará una multa del 1% por incidencia.", ClauseType.PENALTY),
        ("Penalisation for late completion.", ClauseType.PENALTY),
        ("Prepayment of 20% is due on signature.", ClauseType.PAYMENT),
        ("El precio se abonará mediante certificaciones mensuales.", ClauseType.PAYMENT),
        ("Final completion and rescheduled milestones.", ClauseType.DELIVERY),
    ],
)
def test_classifier_keeps_the_english_inflections_the_old_substrings_covered(
    text: str, expected: ClauseType
) -> None:
    assert _infer_contract_clause_type(text) is expected


def test_priority_order_is_penalty_payment_warranty_scope_delivery() -> None:
    # A clause naming several things is typed by the first match in this order (unchanged order).
    assert _infer_contract_clause_type("Penalización y garantía de las obras") is ClauseType.PENALTY
    assert _infer_contract_clause_type("Pago de las obras") is ClauseType.PAYMENT
    assert _infer_contract_clause_type("Garantía de las obras") is ClauseType.WARRANTY
    assert _infer_contract_clause_type("El plazo de ejecución de las obras") is ClauseType.SCOPE
    assert _infer_contract_clause_type("El plazo de ejecución") is ClauseType.DELIVERY


def test_spanish_delivery_clauses_do_not_become_at_risk() -> None:
    """Classifying 'plazo/hito/entrega' must not stamp status=at_risk (that manufactured TIME findings)."""
    assert "status" not in _data(
        "Plazo de ejecución: 18 meses desde la firma del acta de replanteo."
    )
    assert "status" not in _data("Hito 2: entrega del informe final antes del 1 de octubre.")


def test_english_delivery_clauses_keep_their_existing_at_risk_status() -> None:
    assert _data("The final deadline is 30 June 2027.")["status"] == "at_risk"


# ── a period right behind a figure (follow-up to #1127) ──────────────────────────────────────────
# "For each day of delay ... a penalty of 0.5% per week" was read as a 0.5% DAILY rate. A figure with another
# period right behind it ("per week", "mensual", "por cada 7 días", "per hour") is neither a daily rate nor a
# total cap. An adjective counts only directly after the figure, a noun only after an introducer.


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "For each day of delay the Contractor shall pay a penalty of 0.5% per week.",
            (None, None),
        ),
        ("For each day of delay a penalty of 0.5% weekly applies", (None, None)),
        ("For each day of delay a penalty of 0.5% quarterly applies", (None, None)),
        ("Por cada día de retraso se aplicará una penalización del 2% mensual.", (None, None)),
        ("Por cada día de retraso penalización del 2% por cada 7 días", (None, None)),
        ("Por cada día de retraso penalización del 2% cada 30 días", (None, None)),
        ("Per each day of delay penalty of 2% per hour.", (None, None)),
        ("Por cada día de retraso, la penalización será del 0,1% anual del precio", (None, None)),
        ("Penalidad del 0,1% por día, tope del 10% semanal.", (0.001, None)),
        ("Penalidad del 0,1% por día, tope del 10% por semana.", (0.001, None)),
        ("Penalidad del 0,1% por día, que no excederá el 10% mensual.", (0.001, None)),
        ("Por cada día de retraso penalización del 0,1% con tope del 10% anual", (0.001, None)),
        # a period word that does not qualify the figure does not hide it
        ("Penalidad de 0,1% por día de retraso, desde el mes 3.", (0.001, None)),
        ("Penalidad diaria del 0,1% con tope del 10%, desde el año 2 del contrato.", (0.001, 0.10)),
        ("Penalty of 0.1% of the monthly invoice per day of delay", (0.001, None)),
        ("Delay penalty: 0.02% per day and 0.1% per week", (0.0002, None)),
        ("Liquidated damages: 0.5% per week, capped at 10% of the price.", (None, 0.10)),
        ("Penalidad diaria de 0,1% (equivalente a 3% mensual)", (0.001, None)),
    ],
)
def test_another_period_right_behind_a_figure_hides_it(
    text: str, expected: tuple[float | None, float | None]
) -> None:
    daily, cap = penalty_rate_and_cap(text)

    assert daily == pytest.approx(expected[0])
    assert cap == pytest.approx(expected[1])
