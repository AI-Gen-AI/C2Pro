"""
TS-UD-DOC-ENT-002: Money entity extraction tests.
"""

from __future__ import annotations

import pytest

from src.documents.domain.money_entity_extractor import (
    ExtractedMoney,
    ExtractedPercentage,
    MoneyContextType,
    MoneyEntityExtractor,
)


@pytest.fixture
def money_extractor() -> MoneyEntityExtractor:
    """Refers to Suite ID: TS-UD-DOC-ENT-002."""
    return MoneyEntityExtractor()


@pytest.mark.asyncio
class TestMoneyEntityExtractor:
    """Refers to Suite ID: TS-UD-DOC-ENT-002."""

    @pytest.mark.parametrize(
        "text, expected_amount",
        [
            ("Total: 5.000,50 €", 5000.50),
            ("€25.50", 25.50),
            ("Cost is 100 euros", 100.0),
            ("Amount 1.234.567,89 euros", 1234567.89),
        ],
    )
    async def test_001_002_003_004_money_eur_formats(
        self, money_extractor: MoneyEntityExtractor, text: str, expected_amount: float
    ) -> None:
        results = await money_extractor.extract(text)
        money_results = [item for item in results if isinstance(item, ExtractedMoney)]
        assert len(money_results) == 1
        assert money_results[0].amount == expected_amount
        assert money_results[0].currency == "EUR"

    @pytest.mark.parametrize(
        "text, expected_amount",
        [
            ("Price: $1,250.99", 1250.99),
            ("It costs 300 dollars", 300.0),
            ("$ 1,234,567.89", 1234567.89),
        ],
    )
    async def test_005_006_007_money_usd_formats(
        self, money_extractor: MoneyEntityExtractor, text: str, expected_amount: float
    ) -> None:
        results = await money_extractor.extract(text)
        money_results = [item for item in results if isinstance(item, ExtractedMoney)]
        assert len(money_results) == 1
        assert money_results[0].amount == expected_amount
        assert money_results[0].currency == "USD"

    @pytest.mark.parametrize(
        "text, expected_context",
        [
            ("Anticipo: 1.000€", MoneyContextType.ADVANCE),
            ("Pago final de 2.500 euros", MoneyContextType.FINAL_PAYMENT),
            ("Penalización de -500,00€", MoneyContextType.PENALTY),
            ("TOTAL: $10,000.00", MoneyContextType.TOTAL),
        ],
    )
    async def test_008_009_010_011_money_context_extraction(
        self, money_extractor: MoneyEntityExtractor, text: str, expected_context: MoneyContextType
    ) -> None:
        results = await money_extractor.extract(text)
        money_results = [item for item in results if isinstance(item, ExtractedMoney)]
        assert len(money_results) == 1
        assert money_results[0].context is expected_context

    async def test_012_multiple_amounts_extraction(
        self, money_extractor: MoneyEntityExtractor
    ) -> None:
        text = "The price is $50.99 and the tax is 10,00 €."
        results = await money_extractor.extract(text)
        money_results = [item for item in results if isinstance(item, ExtractedMoney)]
        assert len(money_results) == 2
        usd_result = next(item for item in money_results if item.currency == "USD")
        eur_result = next(item for item in money_results if item.currency == "EUR")
        assert usd_result.amount == 50.99
        assert eur_result.amount == 10.00

    async def test_013_money_percentage_extraction(
        self, money_extractor: MoneyEntityExtractor
    ) -> None:
        text = "A 21% discount will be applied."
        results = await money_extractor.extract(text)
        percentage_results = [item for item in results if isinstance(item, ExtractedPercentage)]
        assert len(percentage_results) == 1
        assert percentage_results[0].value == 21.0
        assert percentage_results[0].text == "21%"

    async def test_014_money_negative_amount(self, money_extractor: MoneyEntityExtractor) -> None:
        text = "A deduction of -50.25 € applies."
        results = await money_extractor.extract(text)
        money_results = [item for item in results if isinstance(item, ExtractedMoney)]
        assert len(money_results) == 1
        assert money_results[0].amount == -50.25
        assert money_results[0].currency == "EUR"
