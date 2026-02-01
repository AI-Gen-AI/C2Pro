
from typing import List, NamedTuple, Dict
from enum import Enum, auto

# --- Data Models and Enums ---

class Party(Enum):
    """Represents the party responsible for a logistics leg."""
    SELLER = auto()
    BUYER = auto()

class Incoterm(Enum):
    """Enumerates the supported Incoterms."""
    EXW = "Ex Works"
    FOB = "Free On Board"
    CIF = "Cost, Insurance, and Freight"
    DDP = "Delivered Duty Paid"

class LogisticsLeg(NamedTuple):
    """Represents a single segment of a logistics journey."""
    name: str
    duration_days: int
    # The default can be overridden by Incoterm rules.
    default_responsible_party: Party

class FullRoute(NamedTuple):
    """Represents a complete, end-to-end logistics route."""
    legs: List[LogisticsLeg]

class AdjustedLeadTime(NamedTuple):
    """The result of an Incoterm adjustment, detailing responsibilities."""
    buyer_responsible_days: int
    seller_responsible_days: int
    breakdown: Dict[str, Party]

# --- Domain Service ---

class IncotermAdjuster:
    """
    A domain service to adjust lead time responsibilities based on Incoterms.
    It calculates the number of lead time days each party (buyer/seller) is
    responsible for along a given logistics route.
    """

    async def calculate(self, route: FullRoute, incoterm: Incoterm) -> AdjustedLeadTime:
        """
        Calculates the buyer and seller lead time based on the Incoterm.

        Args:
            route: The full logistics route with all its legs.
            incoterm: The Incoterm rule to apply.

        Returns:
            An AdjustedLeadTime object with the breakdown of responsibilities.
        """
        buyer_days = 0
        seller_days = 0
        breakdown: Dict[str, Party] = {}

        # Define the handover points where responsibility shifts from seller to buyer
        # These are flags that change as we iterate through the legs
        responsibility_is_buyers = False

        if incoterm == Incoterm.EXW:
            # Buyer takes responsibility immediately after production.
            handover_leg_name = "Production"
        elif incoterm == Incoterm.FOB:
            # Buyer takes responsibility after goods are on the ship (i.e., after origin customs).
            handover_leg_name = "Origin Customs Clearance"
        elif incoterm == Incoterm.CIF:
            # Buyer takes responsibility after the main carriage (ocean freight).
            handover_leg_name = "Ocean Freight"
        elif incoterm == Incoterm.DDP:
            # Seller has full responsibility, so handover is effectively at the end.
            handover_leg_name = "Destination Inland Transit" 
        else:
            raise ValueError(f"Unsupported Incoterm: {incoterm}")

        for leg in route.legs:
            current_party: Party
            
            if leg.name == "Production": # Production is always the seller's responsibility
                current_party = Party.SELLER
            elif responsibility_is_buyers:
                current_party = Party.BUYER
            else:
                # If we haven't reached the handover point yet, it's the seller's responsibility
                current_party = Party.SELLER

            # Update who is responsible for the remaining legs
            if leg.name == handover_leg_name:
                responsibility_is_buyers = True

            # Assign days to the responsible party
            if current_party == Party.BUYER:
                buyer_days += leg.duration_days
            else:
                seller_days += leg.duration_days
            
            breakdown[leg.name] = current_party

        return AdjustedLeadTime(
            buyer_responsible_days=buyer_days,
            seller_responsible_days=seller_days,
            breakdown=breakdown
        )
