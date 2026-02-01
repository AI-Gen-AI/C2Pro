"""
Entity Extraction - Money (TDD - RED Phase)

Refers to Suite ID: TS-UD-DOC-ENT-002.
"""

from __future__ import annotations

from decimal import Decimal

from src.documents.domain.services.entity_extraction import extract_money


class TestEntityExtractionMoney:
    """Refers to Suite ID: TS-UD-DOC-ENT-002."""

    def test_extracts_eur_amount_with_symbol(self):
        text = "El precio total es €1,200.50."
        money = extract_money(text)
        assert {"amount": Decimal("1200.50"), "currency": "EUR"} in money

    def test_extracts_usd_amount_with_prefix(self):
        text = "Pago inicial: USD 2500."
        money = extract_money(text)
        assert {"amount": Decimal("2500"), "currency": "USD"} in money

    def test_extracts_eur_amount_with_suffix(self):
        text = "Se abonaran 1.000,00 EUR al firmar."
        money = extract_money(text)
        assert {"amount": Decimal("1000.00"), "currency": "EUR"} in money

    def test_ignores_invalid_money(self):
        text = "Monto: EUR XX."
        money = extract_money(text)
        assert money == []

