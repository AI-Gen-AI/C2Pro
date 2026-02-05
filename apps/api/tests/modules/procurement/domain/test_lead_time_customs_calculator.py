"""
Customs lead time calculation tests.
"""

from src.procurement.domain.customs_lead_time_calculator import (
    CustomsContext,
    CustomsLeadTimeCalculator,
    Incoterm,
    TransportMode,
)


class TestCustomsLeadTimeCalculator:
    """Refers to Suite ID: TS-UD-PROC-LTM-003"""

    def test_001_customs_eu_internal_zero_days(self) -> None:
        calculator = CustomsLeadTimeCalculator()
        context = CustomsContext(
            origin_country="ES",
            destination_country="FR",
            is_eu_internal=True,
            incoterm=Incoterm.FOB,
            transport_mode=TransportMode.ROAD,
        )

        result = calculator.calculate(context)
        assert result.customs_days == 0

    def test_002_customs_international_base_days(self) -> None:
        calculator = CustomsLeadTimeCalculator()
        context = CustomsContext(
            origin_country="CN",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.FOB,
            transport_mode=TransportMode.SEA,
        )

        result = calculator.calculate(context)
        assert result.customs_days == 4

    def test_003_customs_high_risk_origin_adds_days(self) -> None:
        calculator = CustomsLeadTimeCalculator(high_risk_origins={"IR"})
        context = CustomsContext(
            origin_country="IR",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.FOB,
            transport_mode=TransportMode.SEA,
        )

        result = calculator.calculate(context)
        assert result.customs_days == 6

    def test_004_customs_incomplete_documents_adds_days(self) -> None:
        calculator = CustomsLeadTimeCalculator()
        context = CustomsContext(
            origin_country="US",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.FOB,
            transport_mode=TransportMode.SEA,
            documents_complete=False,
        )

        result = calculator.calculate(context)
        assert result.customs_days == 7

    def test_005_customs_sea_mode_adds_one_day(self) -> None:
        calculator = CustomsLeadTimeCalculator()
        context = CustomsContext(
            origin_country="US",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.FOB,
            transport_mode=TransportMode.SEA,
        )

        result = calculator.calculate(context)
        assert result.customs_days == 4

    def test_006_customs_air_mode_reduces_one_day(self) -> None:
        calculator = CustomsLeadTimeCalculator()
        context = CustomsContext(
            origin_country="US",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.FOB,
            transport_mode=TransportMode.AIR,
        )

        result = calculator.calculate(context)
        assert result.customs_days == 2

    def test_007_ddp_customs_not_buyer_responsibility(self) -> None:
        calculator = CustomsLeadTimeCalculator()
        context = CustomsContext(
            origin_country="US",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.DDP,
            transport_mode=TransportMode.SEA,
        )

        result = calculator.calculate(context)
        assert result.buyer_customs_days == 0
        assert result.seller_customs_days == 4

    def test_008_exw_customs_buyer_responsibility(self) -> None:
        calculator = CustomsLeadTimeCalculator()
        context = CustomsContext(
            origin_country="US",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.EXW,
            transport_mode=TransportMode.SEA,
        )

        result = calculator.calculate(context)
        assert result.buyer_customs_days == 4
        assert result.seller_customs_days == 0

    def test_009_customs_days_never_negative(self) -> None:
        calculator = CustomsLeadTimeCalculator()
        context = CustomsContext(
            origin_country="US",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.FOB,
            transport_mode=TransportMode.AIR,
            fast_track_clearance=True,
        )

        result = calculator.calculate(context)
        assert result.customs_days >= 0

    def test_010_customs_breakdown_returned(self) -> None:
        calculator = CustomsLeadTimeCalculator(high_risk_origins={"US"})
        context = CustomsContext(
            origin_country="US",
            destination_country="ES",
            is_eu_internal=False,
            incoterm=Incoterm.FOB,
            transport_mode=TransportMode.SEA,
            documents_complete=False,
        )

        result = calculator.calculate(context)
        assert result.breakdown["base"] == 3
        assert result.breakdown["transport"] == 1
        assert result.breakdown["high_risk"] == 2
        assert result.breakdown["incomplete_documents"] == 3
