
import pytest
from typing import List, NamedTuple
from enum import Enum, auto

# This import will fail as the modules do not exist yet.
from apps.api.src.documents.domain.money_entity_extractor import (
    MoneyEntityExtractor,
    ExtractedMoney,
    MoneyContextType,
    ExtractedPercentage,
)

# --- Temporary definitions for test development ---
class TempMoneyContextType(Enum):
    ADVANCE = auto()
    FINAL_PAYMENT = auto()
    PENALTY = auto()
    TOTAL = auto()
    GENERIC = auto()

class TempExtractedMoney(NamedTuple):
    amount: float
    currency: str
    context: TempMoneyContextType
    text: str
    start: int
    end: int
    
class TempExtractedPercentage(NamedTuple):
    value: float
    context: TempMoneyContextType
    text: str
    start: int
    end: int


# --- Test Fixture ---
@pytest.fixture
def money_extractor() -> MoneyEntityExtractor:
    """Fixture for the MoneyEntityExtractor service."""
    service = MoneyEntityExtractor()
    # Temporarily attach the temp classes for testing
    service.MoneyContextType = TempMoneyContextType
    service.ExtractedMoney = TempExtractedMoney
    service.ExtractedPercentage = TempExtractedPercentage
    return service

# --- Test Cases ---
@pytest.mark.asyncio
class TestMoneyEntityExtractor:
    """Refers to Suite ID: TS-UD-DOC-ENT-002"""

    # --- EUR Tests (test_001-004) ---
    @pytest.mark.parametrize("text, expected_amount", [
        ("Total: 5.000,50 €", 5000.50),
        ("€25.50", 25.50),
        ("Cost is 100 euros", 100.0),
        ("Ammount 1.234.567,89 euros", 1234567.89),
    ])
    async def test_001_002_003_004_money_eur_formats(self, money_extractor, text, expected_amount):
        results = await money_extractor.extract(text)
        money_results = [r for r in results if isinstance(r, money_extractor.ExtractedMoney)]
        assert len(money_results) == 1
        assert money_results[0].amount == expected_amount
        assert money_results[0].currency == "EUR"

    # --- USD Tests (test_005-007) ---
    @pytest.mark.parametrize("text, expected_amount", [
        ("Price: $1,250.99", 1250.99),
        ("It costs 300 dollars", 300.0),
        ("$ 1,234,567.89", 1234567.89),
    ])
    async def test_005_006_007_money_usd_formats(self, money_extractor, text, expected_amount):
        results = await money_extractor.extract(text)
        money_results = [r for r in results if isinstance(r, money_extractor.ExtractedMoney)]
        assert len(money_results) == 1
        assert money_results[0].amount == expected_amount
        assert money_results[0].currency == "USD"

    # --- Context Tests (test_008-011) ---
    @pytest.mark.parametrize("text, expected_context", [
        ("Anticipo: 1.000€", TempMoneyContextType.ADVANCE),
        ("Pago final de 2.500 euros", TempMoneyContextType.FINAL_PAYMENT),
        ("Penalización de -500,00€", TempMoneyContextType.PENALTY),
        ("TOTAL: $10,000.00", TempMoneyContextType.TOTAL),
    ])
    async def test_008_009_010_011_money_context_extraction(self, money_extractor, text, expected_context):
        results = await money_extractor.extract(text)
        money_results = [r for r in results if isinstance(r, money_extractor.ExtractedMoney)]
        assert len(money_results) == 1
        assert money_results[0].context == expected_context
    
    async def test_014_money_negative_amount(self, money_extractor):
        """Test negative amounts are parsed correctly."""
        text = "A deduction of -50.25 € applies."
        results = await money_extractor.extract(text)
        money_results = [r for r in results if isinstance(r, money_extractor.ExtractedMoney)]
        assert len(money_results) == 1
        assert money_results[0].amount == -50.25
        assert money_results[0].currency == "EUR"
        
    # --- Other Tests (test_012-013) ---
    async def test_012_multiple_amounts_extraction(self, money_extractor):
        text = "The price is $50.99 and the tax is 10,00 €."
        results = await money_extractor.extract(text)
        money_results = [r for r in results if isinstance(r, money_extractor.ExtractedMoney)]

        assert len(money_results) == 2
        
        usd_result = next((r for r in money_results if r.currency == "USD"), None)
        eur_result = next((r for r in money_results if r.currency == "EUR"), None)
        
        assert usd_result is not None
        assert eur_result is not None
        
        assert usd_result.amount == 50.99
        assert eur_result.amount == 10.00

    async def test_013_money_percentage_extraction(self, money_extractor):
        text = "A 21% discount will be applied."
        results = await money_extractor.extract(text)
        percentage_results = [r for r in results if isinstance(r, money_extractor.ExtractedPercentage)]
        
        assert len(percentage_results) == 1
        assert percentage_results[0].value == 21.0
        assert percentage_results[0].text == "21%"
