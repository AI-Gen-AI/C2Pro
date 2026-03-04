"""
Refers to Suite IDs: TS-UD-DOC-ENT-001, TS-UD-DOC-ENT-002, TS-UD-DOC-ENT-003.
"""

from datetime import date
from decimal import Decimal

from src.documents.domain.services.entity_extraction import (
    extract_dates,
    extract_durations,
    extract_money,
)


def test_extract_dates_supports_iso_and_ddmmyyyy_formats() -> None:
    text = "Hito A: 2026-03-04. Hito B: 15/04/2026."

    dates = extract_dates(text)

    assert date(2026, 3, 4) in dates
    assert date(2026, 4, 15) in dates
    assert len(dates) == 2


def test_extract_money_detects_eur_and_usd() -> None:
    text = "Costo base € 1.250,50 y reserva USD 3000."

    entities = extract_money(text)

    assert {"amount": Decimal("1250.50"), "currency": "EUR"} in entities
    assert {"amount": Decimal("3000"), "currency": "USD"} in entities


def test_extract_durations_normalizes_units() -> None:
    text = "Periodo de ejecución de 3 months con revisión a 10 days."

    durations = extract_durations(text)

    assert {"value": 3, "unit": "months"} in durations
    assert {"value": 10, "unit": "days"} in durations
