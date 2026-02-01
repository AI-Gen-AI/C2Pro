
import abc
from enum import Enum, auto
from typing import List, NamedTuple, Any

# --- DTOs for events ---
# In a real app, these might be more complex Pydantic models
class ChangeEvent(NamedTuple):
    user_id: str
    timestamp: float

class ResolutionEvent(NamedTuple):
    user_id: str
    issue_hash: str

class ScoreUpdateEvent(NamedTuple):
    user_id: str
    new_score: float

class WeightChangeEvent(ChangeEvent): # Inherits from ChangeEvent for the combined test
    component_id: str
    new_weight: float


# --- Enums and Ports (Interfaces) ---
class AbuseType(Enum):
    MASS_CHANGES = auto()
    RESOLVE_REINTRODUCE = auto()
    HIGH_SCORE_LOW_DOCS = auto()
    LARGE_WEIGHT_CHANGE = auto()

class GamificationAbuseRepository(abc.ABC):
    @abc.abstractmethod
    async def get_change_events_in_last_hour(self, user_id: str) -> List[Any]:
        raise NotImplementedError
    
    @abc.abstractmethod
    async def get_resolution_count_for_hash(self, user_id: str, issue_hash: str) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_user_document_count(self, user_id: str) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_previous_weight_in_last_24h(self, user_id: str, component_id: str) -> float | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def log_change_event(self, event: Any) -> None:
        raise NotImplementedError

class AlertingService(abc.ABC):
    @abc.abstractmethod
    async def trigger_alert(self, user_id: str, abuse_type: AbuseType, reason: str) -> None:
        raise NotImplementedError

class AuditService(abc.ABC):
    @abc.abstractmethod
    async def log_abuse_violation(self, user_id: str, abuse_type: AbuseType) -> None:
        raise NotImplementedError

class PenaltyService(abc.ABC):
    @abc.abstractmethod
    async def apply_penalty(self, user_id: str, abuse_type: AbuseType) -> None:
        raise NotImplementedError

# --- Application Service Implementation ---
class AbuseMonitorService:
    """
    Monitors user activities for signs of gamification abuse.
    """
    
    # --- Thresholds ---
    MASS_CHANGES_LIMIT = 10
    RESOLVE_REINTRODUCE_LIMIT = 2 # Triggers on the 3rd time
    HIGH_SCORE_THRESHOLD = 90.0
    LOW_DOCS_THRESHOLD = 5
    LARGE_WEIGHT_CHANGE_PERCENT_THRESHOLD = 0.25

    def __init__(self, repo: GamificationAbuseRepository, alerting_service: AlertingService, audit_service: AuditService, penalty_service: PenaltyService):
        self.repo = repo
        self.alerting_service = alerting_service
        self.audit_service = audit_service
        self.penalty_service = penalty_service

    async def _handle_violation(self, user_id: str, abuse_type: AbuseType, reason: str):
        """Helper to orchestrate actions when a violation is detected."""
        await self.alerting_service.trigger_alert(user_id, abuse_type, reason)
        await self.audit_service.log_abuse_violation(user_id, abuse_type)
        await self.penalty_service.apply_penalty(user_id, abuse_type)

    async def process_change_event(self, event: ChangeEvent):
        await self.repo.log_change_event(event)
        recent_changes = await self.repo.get_change_events_in_last_hour(event.user_id)
        if len(recent_changes) > self.MASS_CHANGES_LIMIT:
            reason = f"User made {len(recent_changes)} changes in the last hour"
            await self._handle_violation(event.user_id, AbuseType.MASS_CHANGES, reason)

    async def process_issue_resolution_event(self, event: ResolutionEvent):
        await self.repo.log_change_event(event) # Also a change event
        count = await self.repo.get_resolution_count_for_hash(event.user_id, event.issue_hash)
        if count >= self.RESOLVE_REINTRODUCE_LIMIT:
            reason = f"Issue with hash {event.issue_hash} has been re-introduced {count + 1} times."
            await self._handle_violation(event.user_id, AbuseType.RESOLVE_REINTRODUCE, reason)

    async def process_score_update_event(self, event: ScoreUpdateEvent):
        if event.new_score >= self.HIGH_SCORE_THRESHOLD:
            doc_count = await self.repo.get_user_document_count(event.user_id)
            if doc_count < self.LOW_DOCS_THRESHOLD:
                reason = f"User has a high score ({event.new_score}) with only {doc_count} documents."
                await self._handle_violation(event.user_id, AbuseType.HIGH_SCORE_LOW_DOCS, reason)

    async def process_weight_change_event(self, event: WeightChangeEvent):
        await self.repo.log_change_event(event)
        old_weight = await self.repo.get_previous_weight_in_last_24h(event.user_id, event.component_id)
        if old_weight is not None and old_weight > 0: # Avoid division by zero
            change_percent = abs(event.new_weight - old_weight) / old_weight
            if change_percent >= self.LARGE_WEIGHT_CHANGE_PERCENT_THRESHOLD:
                reason = f"Weight for {event.component_id} changed by {change_percent:.1%} in 24 hours."
                await self._handle_violation(event.user_id, AbuseType.LARGE_WEIGHT_CHANGE, reason)

    async def process_event(self, event: Any):
        """A generic event processor that delegates to specific handlers."""
        if isinstance(event, WeightChangeEvent):
            # Must check for most specific type first
            await self.process_weight_change_event(event)
            # Since it's also a ChangeEvent, process for that rule too
            await self.process_change_event(event)
        elif isinstance(event, ChangeEvent):
            await self.process_change_event(event)
        elif isinstance(event, ResolutionEvent):
            await self.process_issue_resolution_event(event)
        elif isinstance(event, ScoreUpdateEvent):
            await self.process_score_update_event(event)
        # In a real system, would log or handle unknown event types
