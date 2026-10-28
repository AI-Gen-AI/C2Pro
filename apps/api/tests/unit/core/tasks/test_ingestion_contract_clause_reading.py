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


# ── recall on the usual wording (second review of #1127) ─────────────────────────────────────────
# The reader is safe (no wrong number, only "no data"), but the daily term often sits too far from the
# rate to claim it, and a few usual formulas were not read at all. Each literal below is real wording.

USUAL_WORDING = [
    pytest.param(
        "Por cada día natural de retraso en la finalización de las obras, el Contratista abonará "
        "una penalización del 0,1% del Precio del Contrato, hasta un máximo del 10% del Precio "
        "del Contrato.",
        (0.001, 0.10),
        id="es-daily-term-far-from-the-rate",
    ),
    pytest.param(
        "For each day of delay beyond the Time for Completion, the Contractor shall pay liquidated "
        "damages amounting to 0.05% of the Contract Price, the total amount of which shall not "
        "exceed 7.5% of the Contract Price.",
        (0.0005, 0.075),
        id="en-daily-term-far-from-the-rate",
    ),
    pytest.param(
        "se le impondrá una penalidad del 0,2 por 100 del precio del contrato por cada día de "
        "retraso, con un límite del 10 por 100.",
        (0.002, 0.10),
        id="es-por-100",
    ),
    pytest.param(
        "Se aplicará una penalidad del 0,05% por día de demora. Las penalidades no podrán superar "
        "el 5% del precio.",
        (0.0005, 0.05),
        id="es-plural-cap-verb-in-the-next-sentence",
    ),
    pytest.param(
        "Las penalidades no podrán exceder del 5% del precio. Penalidad del 0,05% por día de demora.",
        (0.0005, 0.05),
        id="es-plural-cap-verb-exceder",
    ),
    pytest.param(
        "La penalidad del 0,05% por día de demora no excederán del 5% del precio acumulado.",
        (0.0005, 0.05),
        id="es-plural-future-no-excederan",
    ),
    pytest.param(
        "Las penalidades diarias se aplicarán en la proporción de 0,60 euros por cada 1.000 euros "
        "del precio del contrato.",
        (0.0006, None),
        id="lcsp-193-euros-per-thousand",
    ),
    pytest.param(
        "Penalidades diarias en la proporción de 0,60 euros por cada 1.000 euros del precio del "
        "contrato, que no podrán superar el 10% del precio.",
        (0.0006, None),  # a bare "que" does not reach back past the ratio's base: no data
        id="lcsp-193-bare-que-gives-no-cap",
    ),
]


@pytest.mark.parametrize(("text", "expected"), USUAL_WORDING)
def test_usual_wording_gives_rate_and_cap(
    text: str, expected: tuple[float | None, float | None]
) -> None:
    daily, cap = penalty_rate_and_cap(text)

    assert daily == pytest.approx(expected[0])
    assert cap == pytest.approx(expected[1])


@pytest.mark.parametrize(("text", "expected"), USUAL_WORDING)
def test_usual_wording_reaches_the_clause_data_the_penalty_rule_reads(
    text: str, expected: tuple[float | None, float | None]
) -> None:
    data = _data(text)

    assert data.get("daily_penalty_pct") == pytest.approx(expected[0])
    assert data.get("penalty_cap_pct") == pytest.approx(expected[1])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0,2 por 100 del precio", [0.002]),
        ("un 10 por 100.", [0.10]),
        ("el 5 por 100, y", [0.05]),
        ("15 por 100 metros de retraso", []),  # not a percentage: "por 100" starts a quantity
        ("20 por 1000 unidades", []),
    ],
)
def test_por_100_is_a_percentage_only_when_it_is_not_the_start_of_a_quantity(
    text: str, expected: list[float]
) -> None:
    assert [m.value for m in extract_percentages(text)] == pytest.approx(expected)


# What the recall change must never do: read a threshold, a base, a condition, a retention, a bond or
# someone else's cap as the penalty. Found by the independent review of the first version.
NOT_THE_RATE = [
    # no daily phrase anywhere: nothing says the lone percentage is a rate
    "Penalización del 0,1% del Precio del Contrato por el retraso en la finalización.",
    # the percentage is a cap, a threshold, a base or a condition, not the rate
    "Por cada día de retraso se aplicará una penalización hasta alcanzar el 10% del precio del contrato.",
    "Por cada día de retraso se aplicará una penalización limitada al 10% del precio.",
    "Por cada día de retraso se aplicará una penalización acumulada total del 10% del precio.",
    "Por cada día de retraso se aplicará una penalización y si el retraso supera el 20% del plazo podrá resolverse el contrato.",
    "Por cada día de retraso se aplicará una penalidad cuando el avance sea inferior al 80% del programa.",
    "Por cada día de retraso se aplicará una penalidad una vez transcurrido el 10% del plazo.",
    "Por cada día de retraso la penalización se calculará sobre el 100% del importe.",
    "Por cada día de retraso se aplicará una penalidad reducida al 50% si el contratista avisa antes.",
    "For each day of delay, a penalty applies if progress is below 80% of plan.",
    "For each day of delay the penalty shall be calculated on the unpaid 5% of the price.",
    # another subject in the same sentence
    "Por cada día de retraso se aplicará la penalización pactada y se retendrá un 5% de cada pago.",
    "For each day of delay the Contractor pays liquidated damages and the Employer retains 5% of each payment.",
    "Por cada día natural de retraso el Contratista reconocerá al Subcontratista un 3% de intereses.",
    # the "per day" phrase belongs to something else than the delay
    "Se aplicará una penalización del 5% del precio por incumplimiento del plan de seguridad, cuya vigilancia se realizará cada día.",
    "Penalty of 3% of the price for missing the quality inspections, which are performed daily.",
    "Se impondrá una penalidad del 1% del precio del contrato por cada incumplimiento del parte diario.",
    "A penalty of 5% of the price for failure to deliver the safety plan, and site working hours are 8 hours per day.",
    # another period behind the figure
    "For each day of delay the Contractor shall pay a penalty of 0.5% per week.",
    "Por cada día de retraso se aplicará una penalización del 2% mensual.",
    "Por cada día de retraso se aplicará una penalización del 2% por cada 7 días.",
    "Por cada día de retraso se aplicará una penalización del 2% cada 30 días.",
    "Por cada día de retraso se aplicará una penalización del 2% por cada hora.",
    "Por cada día de retraso se aplicará una penalización del 2% por periodo bimestral.",
    "Per each day of delay penalty of 2% per hour.",
    # two figures and no way to tell which one is the rate
    "Por cada día natural de retraso en la finalización de las obras, el Contratista abonará una "
    "penalización del 0,1% del precio del contrato y una multa adicional del 1% por incumplimiento.",
    # a range: the first figure is not read, so the second must not look like the only one
    "Penalidad diaria 0,2 por 100 a 5 por 100 de los pagos.",
]


@pytest.mark.parametrize("text", NOT_THE_RATE)
def test_a_figure_that_is_not_the_rate_is_never_read_as_the_daily_rate(text: str) -> None:
    daily, _ = penalty_rate_and_cap(text)

    assert daily is None


def test_a_later_correct_rate_is_not_displaced_by_an_earlier_wrong_figure() -> None:
    daily, cap = penalty_rate_and_cap(
        "Por cada día de retraso se aplicará una penalización hasta alcanzar el 10% del precio. "
        "La penalidad diaria será del 0,1%."
    )

    assert (daily, cap) == (pytest.approx(0.001), None)


@pytest.mark.parametrize(
    "text",
    [
        "Penalidad de 600 euros por cada día de retraso y fianza de 4 euros por cada 1.000 euros del precio.",
        "Penalidad diaria de 600 euros, y la fianza será de 4 euros por cada 1.000 euros del precio del contrato.",
        "Penalidad diaria de 600 euros, y los intereses de demora de 4 euros por cada 1.000 euros.",
        "Penalidad de 1.000 euros por cada día de retraso y 5 euros por cada 1.000 euros de precio.",
        "Penalidad diaria: 3 euros por cada 1.000 euros de interés.",
        # not a thousand: a different base is never rescaled
        "Penalidades diarias de 0,60 euros por cada 100 euros del precio.",
        # not a daily rate: a ratio without a daily term, or outside a penalty sentence
        "Las penalidades se aplicarán en la proporción de 0,60 euros por cada 1.000 euros del precio.",
        "Se abonarán 0,60 euros por cada 1.000 euros del precio.",
    ],
)
def test_euros_per_thousand_is_a_daily_rate_only_when_it_is_the_sentences_one_amount(
    text: str,
) -> None:
    assert penalty_rate_and_cap(text)[0] is None


@pytest.mark.parametrize(
    "text",
    [
        "La penalidad diaria del 0,1% y las retenciones no podrán superar el 5%.",
        "La penalidad diaria del 0,1% y la responsabilidad total no podrán superar el 100% del precio.",
        "La penalidad diaria del 0,1% y los intereses de demora no podrán exceder el 8%.",
        "La penalidad diaria del 0,1%, mientras que las garantías no podrán superar el 5%.",
        "La penalidad diaria del 0,1% y los subcontratistas no podrán superar el 30% de la obra.",
        "La penalidad diaria del 0,1% y los pagos no podrán exceder del 30%.",
        "Delay penalty of 0.1% per day and the Employer's liability shall not exceed 100%.",
        "Delay penalty of 0.1% per day and advances shall not exceed 20% of the price.",
        # "limited" marks a liability limit, in English as well
        "Liquidated damages of 0.1% per day, total liability limited to 10%.",
        # a weekly or monthly cap is not a cumulative cap
        "Penalidad del 0,1% por día, tope del 10% semanal.",
        "Penalidad del 0,1% por día, que no excederá el 10% mensual.",
        # the cap verb's subject is another clause
        "Las modificaciones no podran superar el 20% y las penalidades por demora el 10%.",
    ],
)
def test_a_cap_that_belongs_to_another_subject_or_period_is_never_the_penalty_cap(
    text: str,
) -> None:
    _, cap = penalty_rate_and_cap(text)

    assert cap is None


@pytest.mark.parametrize(
    "text",
    [
        "2 por 100.000 habitantes",
        "2 por 100.000 euros",
        "5 por 100,5 euros",
        "7 por 100-000",
        "7 por 100/hora",
        "7 por 100 de metros lineales",
        "7 por 100 a 200 metros",
        "7 por 100 en 100 días",
        "7 por 100 y 3 metros",
        "8 por 100 por m2",
        "15 por 100 metros de retraso",
        "20 por 1000 unidades",
    ],
)
def test_por_100_that_may_start_a_quantity_is_not_a_percentage(text: str) -> None:
    assert extract_percentages(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "Penalidad del 0,2 por 100 diario del precio.",
        "Penalidad de 0,2 por 100 cada día de retraso.",
        "Penalidad diaria 0,2 por 100 respecto del precio.",
    ],
)
def test_por_100_before_a_daily_word_or_a_connector_is_a_percentage(text: str) -> None:
    daily, _ = penalty_rate_and_cap(text)

    assert daily == pytest.approx(0.002)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # a period word that does not qualify the figure does not hide it
        ("Penalidad de 0,1% por día de retraso, desde el mes 3.", (0.001, None)),
        ("Penalidad diaria del 0,1% con tope del 10%, desde el año 2 del contrato.", (0.001, 0.10)),
        (
            "Penalty of 0.1% per day, capped at 10%, within the month following the deadline.",
            (0.001, 0.10),
        ),
        ("Delay penalty: 0.02% per day and 0.1% per week", (0.0002, None)),
        ("Penalidad diaria de 0,1% (equivalente a 3% mensual)", (0.001, None)),
    ],
)
def test_a_period_word_only_hides_the_figure_it_qualifies(
    text: str, expected: tuple[float | None, float | None]
) -> None:
    daily, cap = penalty_rate_and_cap(text)

    assert daily == pytest.approx(expected[0])
    assert cap == pytest.approx(expected[1])


def test_a_residual_rate_never_displaces_a_rate_that_a_term_already_claimed() -> None:
    daily, cap = penalty_rate_and_cap(
        "Por cada día de retraso se aplicará una penalización del 0,1% diario, hasta un máximo del 10%."
    )

    assert (daily, cap) == (pytest.approx(0.001), pytest.approx(0.10))


# Second review round: the cases that were still wrong after the first hardening.
SECOND_ROUND_NO_DAILY_RATE = [
    # fixed money amount plus a second penalty term: the lone percentage is not the daily rate
    "Por cada día natural de retraso en la terminación de las obras, el Contratista abonará una "
    "penalización de 600 euros y una multa del 5% por resolución del contrato.",
    "For each day of delay the Contractor shall pay a penalty of USD 500 plus liquidated damages of 5% on termination.",
    # the delay is not the day-by-day delay: a daily report
    "El retraso en la entrega del informe diario de avance de obra dará lugar a una penalización del 3% del precio del contrato.",
    "Any delay in submitting the daily progress report shall be subject to a penalty of 2% of the Contract Price.",
    # a cap word before the ratio
    "La penalidad, con un máximo de 100 euros por cada 1.000 euros y diaria, se aplicará por demora.",
    "Penalidad máxima diaria de 0,60 euros por cada 1.000 euros",
    # "por 100" that is a threshold, a base or another subject's, claimed by a per-day word
    "Por cada día de retraso superior al 10 por 100 del plazo, penalidad de 600 euros.",
    "Si el retraso supera el 20 por 100 del plazo, penalidad diaria de 600 euros.",
    "Penalidad diaria del 2 por 100 de los pagos retenidos.",
    # a line break may cut "por 100" from its unit
    "Por cada día de retraso la penalidad será de 15 por 100\nmetros ejecutados fuera de plazo.",
    # a thousand-separated amount is not 1,2 euros
    "Penalidad diaria de 1.200 euros por cada 1.000 euros del precio",
    # the ratio's own base, then another period
    "Penalidad diaria de 0,60 euros por cada 1.000 euros del precio del contrato por semana",
    # a condition after the figure is the only guard here
    "Por cada día natural de retraso en la finalización de las obras, el Contratista abonará una "
    "penalización del 0,1% del precio si no avisa con antelación.",
]


@pytest.mark.parametrize("text", SECOND_ROUND_NO_DAILY_RATE)
def test_second_round_figures_are_not_read_as_the_daily_rate(text: str) -> None:
    assert penalty_rate_and_cap(text)[0] is None


@pytest.mark.parametrize(
    "text",
    [
        # coordinated subject, in both orders: the cap is shared, so it is not the penalty's alone
        "Las retenciones y las penalidades por demora no podrán superar el 10% del precio.",
        "Las penalidades por demora y las retenciones no podrán superar el 10% del precio.",
        "La responsabilidad total y las penalidades por demora no podrán superar el 100%.",
        # a delay is not the penalty
        "Los retrasos acumulados no podrán superar el 20% del plazo.",
        "Las demoras en el pago no podrán superar el 30% de las certificaciones.",
        # a bare relative points at the noun behind it, which is not a penalty word
        "Se aplicará una penalidad por demora sobre los hitos, que no podrán superar el 10% del precio.",
        "Se aplicará una penalidad diaria del 0,1% a los subcontratistas, que no podrán superar el 30% de la obra.",
        # the verb is about a rate
        "Las penalidades diarias no podrán superar el 0,5% del precio.",
        # a bare relative may point at any noun: no data, even when the antecedent is the penalty
        "Se aplicará una penalidad a los subcontratos, que no podrán superar el 30% de la obra.",
        "Liquidated damages of 0.05% per day, which shall not exceed 10% of the Contract Price.",
        # another penalty's cap
        "Las sanciones por incumplimiento de las normas de seguridad no podrán superar el 5% del presupuesto.",
        "Las penalidades por calidad no podrán superar el 5% y las penalidades por demora el 10%.",
        # a joint subject whose other part is not a penalty, whatever its noun
        "Los pagos a cuenta y las penalidades por demora no podrán superar el 10% del precio.",
        "Las penalidades por demora más el beneficio industrial no podrán superar el 6%.",
    ],
)
def test_second_round_caps_that_are_not_the_penalty_cap(text: str) -> None:
    _, cap = penalty_rate_and_cap(text)

    assert cap is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Penalidad del 0,1% diario, la cual no podrá superar el 10%.", (0.001, 0.10)),
        # FIDIC wording: "delay damages" names the penalty
        ("Delay damages: 0.05% per day. Total delay damages shall not exceed 10%.", (0.0005, 0.10)),
        (
            "The aggregate amount of delay damages shall not exceed 10% of the Contract Price.",
            (None, 0.10),
        ),
        (
            "Penalidad del 0,1% diario del precio, de la cual el total no podrá superar el 10%.",
            (0.001, 0.10),
        ),
        # a period word inside the base does not hide the rate
        ("Penalty of 0.1% of the monthly invoice per day of delay", (0.001, None)),
        ("Penalidad diaria del 0,1% de la mensualidad", (0.001, None)),
    ],
)
def test_second_round_recall_that_must_survive(
    text: str, expected: tuple[float | None, float | None]
) -> None:
    daily, cap = penalty_rate_and_cap(text)

    assert daily == pytest.approx(expected[0])
    assert cap == pytest.approx(expected[1])


def test_a_clause_beyond_any_plausible_length_is_not_read() -> None:
    text = "Penalización del 0,1% diario " + "y " * 3000 + "del precio."

    assert penalty_rate_and_cap(text) == (None, None)


# Third review round: neighbours of the earlier wordings.
THIRD_ROUND_NO_DAILY_RATE = [
    # a total, said before the penalty word
    "For each day of delay as set out in Annex 3, the aggregate penalties shall be 10% of the Contract Price.",
    "For each day of delay per Annex 2, the cumulative penalty shall be 10%.",
    "Por cada día de retraso (anexo 2), el importe total de la penalidad del 10% del precio.",
    "Por cada día de retraso según el anexo 3, el acumulado de las penalidades será del 10% del precio.",
    # a total or a limit, said after the figure
    "For each day of delay in achieving Completion of the Works under the Contract, the penalty shall be 10% in total.",
    "For each day of delay in achieving Completion of the Works under the Contract, the penalty shall be 10% at most.",
    "Por cada día de retraso en la terminación de las obras objeto del contrato, penalidad del 10% como máximo.",
    "Por cada día de retraso en la terminación de las obras objeto del contrato, penalidad del 10% del precio, alcanzado el cual podrá resolverse.",
    "For each day of delay in achieving Completion of the Works under the Contract, the penalty is 10% of the price, beyond which the Employer may terminate.",
    # a different penalty with a different trigger and no money amount
    "For each day of delay the Contractor shall pay the amounts in Schedule 4, and a penalty of 3% for safety breaches.",
    "Por cada día de retraso se aplicará lo dispuesto en el anexo 2, sin perjuicio de una multa del 5% por resolución anticipada.",
    # two penalty words before the figure: which one it belongs to is a guess
    "Por cada día de retraso, el Contratista abonará la penalización prevista y una multa del 5% del precio.",
    # a ratio whose daily word is weak, or with another period anywhere in the sentence
    "Penalidad de 0,60 euros por cada 1.000 euros del precio si el retraso supera un día natural.",
    "Penalidad de 0,60 euros por cada 1.000 euros por retraso al día siguiente del vencimiento.",
    "Penalidad diaria de 0,60 euros por cada 1.000 euros para el hito final y semanal para el resto.",
]


@pytest.mark.parametrize("text", THIRD_ROUND_NO_DAILY_RATE)
def test_third_round_figures_are_not_read_as_the_daily_rate(text: str) -> None:
    assert penalty_rate_and_cap(text)[0] is None


@pytest.mark.parametrize(
    "text",
    [
        # another penalty, said with participles, other prepositions or a delay in something else
        "Las penalidades impuestas por incumplimiento de las normas de seguridad no podrán superar el 5% del precio.",
        "Las penalidades aplicadas por defectos de calidad no podrán superar el 5% del precio.",
        "Las penalidades por demora y/o por defectos no podrán superar el 5% del precio.",
        "Las penalidades por demora en el pago no podrán superar el 5% de la factura.",
        # a joint cap, whatever links the parts
        "Las penalidades por demora, junto con las retenciones, no podrán superar el 10%.",
        "Las penalidades por demora, junto con el IVA, no podrán superar el 21%.",
        "Las penalidades por demora con los daños no podrán superar el 10%.",
        # a rejected cap verb does not hand its figure to the per-day word
        "La penalidad diaria no podrá superar el 0,5% del precio.",
        "The daily penalty shall not exceed 0.5% of the price.",
        "Delay damages per day shall not exceed 0.5% of the price.",
    ],
)
def test_third_round_caps_that_are_not_the_penalty_cap(text: str) -> None:
    daily, cap = penalty_rate_and_cap(text)

    assert cap is None
    assert daily is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Liquidated damages: 0.05% per day, not to exceed 10% of the Contract Price.",
            (0.0005, 0.10),
        ),
        ("The delay damages shall not exceed 10% of the Contract Price.", (None, 0.10)),
        (
            "Penalidad diaria de 0,60 euros por cada 1.000 euros del precio del contrato, IVA excluido.",
            (0.0006, None),
        ),
        ("Por cada día de retraso, la penalización será del 0,1% del precio.", (0.001, None)),
        (
            "Por cada día natural de retraso en la finalización de las obras, el Contratista abonará una penalización equivalente al 0,1% del precio.",
            (0.001, None),
        ),
        ("Penalidad por demora: 0,1% diario, retención del 5%, máximo 10%", (0.001, 0.10)),
    ],
)
def test_third_round_recall_that_must_survive(
    text: str, expected: tuple[float | None, float | None]
) -> None:
    daily, cap = penalty_rate_and_cap(text)

    assert daily == pytest.approx(expected[0])
    assert cap == pytest.approx(expected[1])


def test_cap_verb_terms_are_a_subset_of_the_cap_terms() -> None:
    from src.documents.domain.contract_clause_lexicon import CAP_VERB_TERMS, PERCENT_ROLE_TERMS

    cap_terms = {term for terms in PERCENT_ROLE_TERMS["CAP"].values() for term in terms}
    verb_terms = {term for terms in CAP_VERB_TERMS.values() for term in terms}

    assert verb_terms <= cap_terms


# Fourth review round: the residual fallback and the cap verbs read only plain statements.
FOURTH_ROUND_NO_DAILY_RATE = [
    # a second statement joins the first: the figure belongs to the second
    "Por cada día de retraso el adjudicatario abonará el importe fijado en el anexo II, y en caso de resolución "
    "por culpa del contratista la penalización será del 10% del precio del contrato.",
    "For each day of delay the Contractor pays the amount in the Contract Data, and the Employer may terminate "
    "on reaching liquidated damages of 10% of the Contract Price.",
    "Por cada día de retraso se aplicará el importe fijado en el anexo II, pudiendo resolverse el contrato al "
    "alcanzar una penalidad del 10% del precio.",
    # the per-day phrase is a duty (to record), not the penalty basis; or it does not open the sentence
    "The Contractor shall record each day of delay in the register, and non-compliance carries a penalty of 1% of the Contract Price.",
    "Cada día de retraso se anotará en el parte, siendo la penalidad del 1% del precio.",
    "Where the daily late arrival of staff occurs, the penalty shall be 1% of the Contract Price.",
    # the verb between the phrase and the penalty word imposes nothing
    "Por cada día de retraso (anexo 2), el importe de la penalización del 0,1% del precio.",
    # a money amount in another currency or written with the symbol first
    "Por cada día de retraso, el Contratista abonará €1.000 y una penalización del 5% del precio.",
    # a date, not a rate
    "La penalidad por demora será del 5 por 100 sobre el importe pendiente al día siguiente del vencimiento.",
    # euros per thousand with a daily word that belongs to another noun
    "Para la limpieza diaria, la penalidad será de 0,60 euros por cada 1.000 euros del precio del contrato por cada incumplimiento.",
    "Si el parte diario no se entrega, la penalidad será de 0,60 euros por cada 1.000 euros del precio del contrato.",
]


@pytest.mark.parametrize("text", FOURTH_ROUND_NO_DAILY_RATE)
def test_fourth_round_figures_are_not_read_as_the_daily_rate(text: str) -> None:
    assert penalty_rate_and_cap(text)[0] is None


@pytest.mark.parametrize(
    "text",
    [
        # joint, coordinated or elided-subject caps
        "Los intereses de demora, junto con las penalidades por demora, no podrán superar el 10% del precio.",
        "Costes y penalidades por demora: no podrán superar el 10% del precio.",
        "No podrán superar el 90% los pagos a cuenta, ni el 10% las penalidades por demora.",
        "Liquidated damages for delay and for performance shall not exceed 10% of the Contract Price.",
        # a cap relative to something else than the price: the time, each payment, each milestone
        "Las penalidades por demora no podrán superar el 3% del plazo.",
        "Las penalidades por demora no podrán superar el 3% de cada pago.",
        "Por demora, las penalidades no podrán superar el 5% por hito y el 10% en total.",
        # a cap per month, said before the figure
        "Las penalidades por demora no podrán superar mensualmente el 1% del precio.",
        "Las penalidades por demora no podrán superar, cada mes, el 1% del precio.",
        # "each penalty" is a per-unit cap
        "Cada penalidad por demora no podrán superar el 0,5% del precio.",
    ],
)
def test_fourth_round_caps_that_are_not_the_penalty_cap(text: str) -> None:
    assert penalty_rate_and_cap(text)[1] is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Liquidated damages for delay payable by the Contractor shall not exceed 10% of the Contract Price.",
            (None, 0.10),
        ),
        (
            "Liquidated damages for delay payable under Sub-Clause 8.7 shall not exceed 10% of the Contract Price.",
            (None, 0.10),
        ),
        (
            "Las penalidades no podrán superar en conjunto el 10 por 100 del presupuesto del contrato.",
            (None, 0.10),
        ),
        ("Delay damages of 0.1% per day shall apply and shall not exceed 10%.", (0.001, None)),
        ("La demora se penalizará con 0,1% al día, no superará el 10% del precio.", (0.001, 0.10)),
        (
            "La penalidad por demora será del 0,10 por 100 diario del precio del contrato.",
            (0.001, None),
        ),
        (
            "18.1 Por cada día natural de retraso en la entrega de la obra, el CONTRATISTA abonará una penalización del 0,1% del Precio.",
            (0.001, None),
        ),
    ],
)
def test_fourth_round_recall_that_must_survive(
    text: str, expected: tuple[float | None, float | None]
) -> None:
    daily, cap = penalty_rate_and_cap(text)

    assert daily == pytest.approx(expected[0])
    assert cap == pytest.approx(expected[1])


# Each guard of the residual rule and of the cap rules is pinned by a sentence that only it rejects.
ONLY_ONE_GUARD_REJECTS = [
    # a condition before the per-day phrase
    "Si por cada día de retraso, el Contratista abonará una penalización del 0,1% del precio.",
    # the per-day phrase does not open the sentence
    "En la fase de ejecución de las obras, por cada día natural de retraso, el Contratista abonará una penalización del 0,1% del precio.",
    # a money amount later in the sentence
    "Por cada día de retraso, el Contratista abonará una penalización del 0,1% del precio, sin perjuicio de 500 euros.",
    # a total said before the penalty word
    "Por cada día de retraso, el total de la penalización del 0,1% del precio.",
    # the figure is said to be a limit reached later
    "Por cada día de retraso, el Contratista abonará una penalización del 10% del precio, superado el cual podrá resolverse el contrato.",
    # another period elsewhere in the sentence
    "Por cada día de retraso, el Contratista abonará una penalización del 0,1% del precio, liquidable por semana.",
]


@pytest.mark.parametrize("text", ONLY_ONE_GUARD_REJECTS)
def test_each_residual_guard_is_pinned_by_a_sentence_only_it_rejects(text: str) -> None:
    assert penalty_rate_and_cap(text)[0] is None


def test_a_tax_qualifier_does_not_hide_the_rate() -> None:
    daily, _ = penalty_rate_and_cap(
        "Por cada día de retraso, el Contratista abonará una penalización del 0,3% del precio (IVA excluido)."
    )

    assert daily == pytest.approx(0.003)


def test_two_different_caps_in_one_sentence_give_no_cap() -> None:
    _, cap = penalty_rate_and_cap(
        "Las penalidades por demora no podrán superar el 5% del precio, con un máximo del 10% del precio."
    )

    assert cap is None
