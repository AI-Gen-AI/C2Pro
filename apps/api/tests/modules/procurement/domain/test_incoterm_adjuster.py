
import pytest
from typing import List, NamedTuple
from enum import Enum, auto

# This import will fail as the modules do not exist yet.
from apps.api.src.procurement.domain.incoterm_adjuster import (
    IncotermAdjuster,
    Incoterm,
    LogisticsLeg,
    FullRoute,
    Party,
    AdjustedLeadTime,
)

# --- Temporary definitions for test development ---
class TempParty(Enum):
    SELLER = auto()
    BUYER = auto()

class TempIncoterm(Enum):
    EXW = "Ex Works"
    FOB = "Free On Board"
    CIF = "Cost, Insurance, and Freight"
    DDP = "Delivered Duty Paid"

class TempLogisticsLeg(NamedTuple):
    name: str
    duration_days: int
    default_responsible_party: TempParty
    
class TempFullRoute(NamedTuple):
    legs: List[TempLogisticsLeg]
    
class TempAdjustedLeadTime(NamedTuple):
    buyer_responsible_days: int
    seller_responsible_days: int
    breakdown: dict

# --- Test Fixtures ---
@pytest.fixture
def adjuster() -> IncotermAdjuster:
    """Provides an instance of the IncotermAdjuster."""
    return IncotermAdjuster()

@pytest.fixture
def standard_route() -> TempFullRoute:
    """Provides a standard, complete logistics route for testing."""
    return TempFullRoute(legs=[
        TempLogisticsLeg("Production", 20, TempParty.SELLER),
        TempLogisticsLeg("Origin Inland Transit", 3, TempParty.SELLER),
        TempLogisticsLeg("Origin Customs Clearance", 2, TempParty.SELLER),
        TempLogisticsLeg("Ocean Freight", 15, TempParty.BUYER),
        TempLogisticsLeg("Destination Customs Clearance", 4, TempParty.BUYER),
        TempLogisticsLeg("Destination Inland Transit", 2, TempParty.BUYER),
    ])

# --- Test Cases ---
@pytest.mark.asyncio
class TestIncotermAdjuster:
    """Refers to Suite ID: TS-UD-PROC-LTM-002"""

    async def test_001_exw_buyer_full_responsibility(self, adjuster, standard_route):
        """Under EXW, the buyer is responsible for the entire journey after production."""
        result = await adjuster.calculate(standard_route, Incoterm.EXW)
        
        # Expected: Origin Transit (3) + Origin Customs (2) + Ocean (15) + Dest Customs (4) + Dest Transit (2) = 26
        assert result.buyer_responsible_days == 26
        assert result.seller_responsible_days == 20 # Just production

    async def test_004_fob_shared_responsibility(self, adjuster, standard_route):
        """Under FOB, buyer responsibility starts after goods are on the vessel."""
        result = await adjuster.calculate(standard_route, Incoterm.FOB)
        
        # Expected: Ocean (15) + Dest Customs (4) + Dest Transit (2) = 21
        assert result.buyer_responsible_days == 21
        # Expected: Production (20) + Origin Transit (3) + Origin Customs (2) = 25
        assert result.seller_responsible_days == 25

    async def test_007_cif_seller_insurance(self, adjuster, standard_route):
        """Under CIF, buyer responsibility starts at the destination port."""
        result = await adjuster.calculate(standard_route, Incoterm.CIF)
        
        # Expected: Dest Customs (4) + Dest Transit (2) = 6
        assert result.buyer_responsible_days == 6
        # Expected: Production (20) + Origin Transit (3) + Origin Customs (2) + Ocean (15) = 40
        assert result.seller_responsible_days == 40

    async def test_010_ddp_seller_full_responsibility(self, adjuster, standard_route):
        """Under DDP, seller is responsible for the entire journey."""
        result = await adjuster.calculate(standard_route, Incoterm.DDP)
        
        # Expected: 0 (or a final 'last mile' if defined, here it's 0)
        assert result.buyer_responsible_days == 0
        # Expected: All legs sum up
        assert result.seller_responsible_days == 20 + 3 + 2 + 15 + 4 + 2

    async def test_014_incoterm_impact_on_lead_time(self, adjuster, standard_route):
        """Verify that lead time for the buyer decreases as seller responsibility increases."""
        exw_res = await adjuster.calculate(standard_route, Incoterm.EXW)
        fob_res = await adjuster.calculate(standard_route, Incoterm.FOB)
        cif_res = await adjuster.calculate(standard_route, Incoterm.CIF)
        ddp_res = await adjuster.calculate(standard_route, Incoterm.DDP)
        
        exw_time = exw_res.buyer_responsible_days
        fob_time = fob_res.buyer_responsible_days
        cif_time = cif_res.buyer_responsible_days
        ddp_time = ddp_res.buyer_responsible_days
        
        assert exw_time > fob_time > cif_time >= ddp_time
        assert ddp_time == 0

    async def test_breakdown_returned(self, adjuster, standard_route):
        """Test that a breakdown of responsibilities is returned."""
        result = await adjuster.calculate(standard_route, Incoterm.FOB)
        
        breakdown = result.breakdown
        assert breakdown["Production"] == Party.SELLER
        assert breakdown["Origin Inland Transit"] == Party.SELLER
        assert breakdown["Origin Customs Clearance"] == Party.SELLER
        assert breakdown["Ocean Freight"] == Party.BUYER
        assert breakdown["Destination Customs Clearance"] == Party.BUYER
        assert breakdown["Destination Inland Transit"] == Party.BUYER
