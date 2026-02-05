"""
Incoterm adjustment rules for lead-time ownership.

Refers to Suite ID: TS-UD-PROC-LTM-002.
"""

from src.procurement.domain.incoterm_adjuster import (
    AdjustedLeadTime,
    FullRoute,
    Incoterm,
    IncotermAdjuster,
    LogisticsLeg,
    Party,
)


def _standard_route() -> FullRoute:
    return FullRoute(
        legs=[
            LogisticsLeg(name="Production", duration_days=20),
            LogisticsLeg(name="Origin Inland Transit", duration_days=3),
            LogisticsLeg(name="Origin Customs Clearance", duration_days=2),
            LogisticsLeg(name="Ocean Freight", duration_days=15),
            LogisticsLeg(name="Insurance", duration_days=1),
            LogisticsLeg(name="Destination Customs Clearance", duration_days=4),
            LogisticsLeg(name="Destination Inland Transit", duration_days=2),
        ]
    )


class TestIncotermAdjuster:
    """Refers to Suite ID: TS-UD-PROC-LTM-002"""

    def test_001_exw_buyer_full_responsibility(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.EXW)
        assert isinstance(result, AdjustedLeadTime)
        assert result.seller_responsible_days == 20
        assert result.buyer_responsible_days == 27

    def test_002_exw_transit_time_included(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.EXW)
        assert result.breakdown["Origin Inland Transit"] == Party.BUYER
        assert result.breakdown["Ocean Freight"] == Party.BUYER
        assert result.breakdown["Destination Inland Transit"] == Party.BUYER

    def test_003_exw_customs_included(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.EXW)
        assert result.breakdown["Origin Customs Clearance"] == Party.BUYER
        assert result.breakdown["Destination Customs Clearance"] == Party.BUYER

    def test_004_fob_shared_responsibility(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.FOB)
        assert result.seller_responsible_days == 25
        assert result.buyer_responsible_days == 22

    def test_005_fob_port_handover(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.FOB)
        assert result.breakdown["Origin Customs Clearance"] == Party.SELLER
        assert result.breakdown["Ocean Freight"] == Party.BUYER

    def test_006_fob_insurance_buyer(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.FOB)
        assert result.breakdown["Insurance"] == Party.BUYER

    def test_007_cif_seller_insurance(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.CIF)
        assert result.breakdown["Insurance"] == Party.SELLER

    def test_008_cif_port_to_port(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.CIF)
        assert result.breakdown["Ocean Freight"] == Party.SELLER
        assert result.breakdown["Destination Inland Transit"] == Party.BUYER

    def test_009_cif_customs_buyer(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.CIF)
        assert result.breakdown["Destination Customs Clearance"] == Party.BUYER

    def test_010_ddp_seller_full_responsibility(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.DDP)
        assert result.buyer_responsible_days == 0
        assert result.seller_responsible_days == 47

    def test_011_ddp_no_customs_buyer(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.DDP)
        assert result.breakdown["Origin Customs Clearance"] == Party.SELLER
        assert result.breakdown["Destination Customs Clearance"] == Party.SELLER

    def test_012_ddp_door_to_door(self) -> None:
        result = IncotermAdjuster().calculate(_standard_route(), Incoterm.DDP)
        assert result.breakdown["Origin Inland Transit"] == Party.SELLER
        assert result.breakdown["Destination Inland Transit"] == Party.SELLER

    def test_013_incoterm_comparison_same_route(self) -> None:
        adjuster = IncotermAdjuster()
        route = _standard_route()

        exw = adjuster.calculate(route, Incoterm.EXW)
        fob = adjuster.calculate(route, Incoterm.FOB)
        cif = adjuster.calculate(route, Incoterm.CIF)
        ddp = adjuster.calculate(route, Incoterm.DDP)

        assert exw.buyer_responsible_days > fob.buyer_responsible_days > cif.buyer_responsible_days > ddp.buyer_responsible_days

    def test_014_incoterm_impact_on_lead_time(self) -> None:
        adjuster = IncotermAdjuster()
        route = _standard_route()

        exw = adjuster.calculate(route, Incoterm.EXW)
        ddp = adjuster.calculate(route, Incoterm.DDP)

        assert exw.total_days == ddp.total_days == 47
        assert exw.buyer_responsible_days == 27
        assert ddp.buyer_responsible_days == 0
