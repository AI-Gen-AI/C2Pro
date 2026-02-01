import abc
from datetime import date, timedelta
from typing import List, NamedTuple, Optional, Union
from enum import Enum, auto

# --- DTOs and Enums ---

class LeadTimeSeverity(Enum):
    CRITICAL = auto()
    WARNING = auto()

class LeadTimeStatus(Enum):
    DATE_PASSED = auto()
    TIGHT_MARGIN = auto()
    OK = auto()

class LeadTimeAlert(NamedTuple):
    status: LeadTimeStatus
    severity: LeadTimeSeverity
    message: str

class LeadTimeComponents(NamedTuple):
    production_days: int = 0
    transit_days: int = 0
    buffer_days: int = 0

class LeadTimeResult(NamedTuple):
    optimal_required_on_site_date: date
    lead_time_breakdown: LeadTimeComponents
    alerts: List[LeadTimeAlert]

# --- Ports ---

class CalendarService(abc.ABC):
    """
    Port for a service that provides calendar-related functionalities,
    such as identifying working days and adding/subtracting business days.
    """
    @abc.abstractmethod
    def is_working_day(self, day: date) -> bool:
        """Returns True if the given day is a working day, False otherwise."""
        raise NotImplementedError

    @abc.abstractmethod
    def add_business_days(self, start_date: date, days: int) -> date:
        """
        Adds or subtracts a specified number of business days from a start date.
        
        Args:
            start_date: The date to start counting from.
            days: The number of business days to add (positive) or subtract (negative).

        Returns:
            The resulting date after adding/subtracting business days.
        """
        raise NotImplementedError

# --- Domain Service ---

class LeadTimeCalculator:
    """
    Calculates optimal required on-site dates for procurement items,
    considering various lead time components, business days, holidays,
    and generating alerts based on deadlines.
    """

    TIGHT_MARGIN_DAYS = 3 # Margin for warning alert

    def __init__(self, calendar_service: CalendarService):
        self.calendar_service = calendar_service
        # For temporary access in tests before real models exist
        self.LeadTimeSeverity = LeadTimeSeverity
        self.LeadTimeStatus = LeadTimeStatus
        self.LeadTimeAlert = LeadTimeAlert
        self.LeadTimeComponents = LeadTimeComponents
        self.LeadTimeResult = LeadTimeResult

    async def calculate_optimal_required_on_site_date(
        self, 
        required_by_date: date, 
        components: LeadTimeComponents
    ) -> LeadTimeResult:
        """
        Calculates the optimal date an item needs to be on-site to meet a required-by date.
        """
        total_lead_time_days = components.production_days + components.transit_days + components.buffer_days
        
        # Calculate the initial optimal date by subtracting business days
        optimal_date = self.calendar_service.add_business_days(required_by_date, -total_lead_time_days)

        # Ensure the final optimal_date itself falls on a working day (adjust backwards if not)
        while not self.calendar_service.is_working_day(optimal_date):
            optimal_date = self.calendar_service.add_business_days(optimal_date, -1)
            
        alerts = await self._check_deadlines(optimal_date, required_by_date)
        
        return LeadTimeResult(
            optimal_required_on_site_date=optimal_date,
            lead_time_breakdown=components,
            alerts=alerts
        )

    async def _check_deadlines(self, optimal_date: date, required_by_date: date) -> List[LeadTimeAlert]:
        """
        Checks for deadline violations and generates appropriate alerts.
        """
        alerts: List[LeadTimeAlert] = []
        
        margin_days = (required_by_date - optimal_date).days
        
        if margin_days < 0:
            alerts.append(LeadTimeAlert(
                status=LeadTimeStatus.DATE_PASSED,
                severity=LeadTimeSeverity.CRITICAL,
                message=f"Optimal required on-site date ({optimal_date}) is after the required by date ({required_by_date})."
            ))
        elif 0 <= margin_days <= self.TIGHT_MARGIN_DAYS:
            alerts.append(LeadTimeAlert(
                status=LeadTimeStatus.TIGHT_MARGIN,
                severity=LeadTimeSeverity.WARNING,
                message=f"Tight margin of {margin_days} day(s) between optimal on-site date and required by date."
            ))
            
        return alerts