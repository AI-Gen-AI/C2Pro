import abc
from enum import Enum, auto
from typing import Any, NamedTuple
from uuid import UUID


class ChangeEvent(NamedTuple):
    user_id: str
    tenant_id: UUID
    timestamp: float


class ResolutionEvent(NamedTuple):
    user_id: str
    tenant_id: UUID
    issue_hash: str


class ScoreUpdateEvent(NamedTuple):
    user_id: str
    tenant_id: UUID
    new_score: float


class WeightChangeEvent(NamedTuple):
    user_id: str
    tenant_id: UUID
    component_id: str
    new_weight: float


class AbuseType(Enum):
    MASS_CHANGES = auto()
    RESOLVE_REINTRODUCE = auto()
    HIGH_SCORE_LOW_DOCS = auto()
    LARGE_WEIGHT_CHANGE = auto()


class GamificationAbuseRepository(abc.ABC):
    @abc.abstractmethod
    async def get_change_events_in_last_hour(self, user_id: str, *, tenant_id: UUID) -> list[Any]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_resolution_count_for_hash(
        self, user_id: str, issue_hash: str, *, tenant_id: UUID
    ) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_user_document_count(self, user_id: str, *, tenant_id: UUID) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_previous_weight_in_last_24h(
        self, user_id: str, component_id: str, *, tenant_id: UUID
    ) -> float | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def log_change_event(self, event: Any) -> None:
        raise NotImplementedError


class AlertingService(abc.ABC):
    @abc.abstractmethod
    async def trigger_alert(
        self,
        user_id: str,
        abuse_type: AbuseType,
        reason: str,
        *,
        tenant_id: UUID,
    ) -> None:
        raise NotImplementedError


class AuditService(abc.ABC):
    @abc.abstractmethod
    async def log_abuse_violation(
        self,
        user_id: str,
        abuse_type: AbuseType,
        *,
        tenant_id: UUID,
    ) -> None:
        raise NotImplementedError


class PenaltyService(abc.ABC):
    @abc.abstractmethod
    async def apply_penalty(
        self,
        user_id: str,
        abuse_type: AbuseType,
        *,
        tenant_id: UUID,
    ) -> None:
        raise NotImplementedError


class AbuseMonitorService:
    """Monitors user activities for signs of gamification abuse."""

    MASS_CHANGES_LIMIT = 10
    RESOLVE_REINTRODUCE_LIMIT = 2
    HIGH_SCORE_THRESHOLD = 90.0
    LOW_DOCS_THRESHOLD = 5
    LARGE_WEIGHT_CHANGE_PERCENT_THRESHOLD = 0.25

    def __init__(
        self,
        repo: GamificationAbuseRepository,
        alerting_service: AlertingService,
        audit_service: AuditService,
        penalty_service: PenaltyService,
    ):
        self.repo = repo
        self.alerting_service = alerting_service
        self.audit_service = audit_service
        self.penalty_service = penalty_service

    async def _handle_violation(
        self,
        user_id: str,
        abuse_type: AbuseType,
        reason: str,
        *,
        tenant_id: UUID,
    ) -> None:
        await self.alerting_service.trigger_alert(
            user_id,
            abuse_type,
            reason,
            tenant_id=tenant_id,
        )
        await self.audit_service.log_abuse_violation(
            user_id,
            abuse_type,
            tenant_id=tenant_id,
        )
        await self.penalty_service.apply_penalty(
            user_id,
            abuse_type,
            tenant_id=tenant_id,
        )

    async def process_change_event(self, event: ChangeEvent) -> None:
        await self.repo.log_change_event(event)
        recent_changes = await self.repo.get_change_events_in_last_hour(
            event.user_id,
            tenant_id=event.tenant_id,
        )
        total_changes = len(recent_changes) + 1
        if total_changes > self.MASS_CHANGES_LIMIT:
            reason = f"User made {total_changes} changes in the last hour"
            await self._handle_violation(
                event.user_id,
                AbuseType.MASS_CHANGES,
                reason,
                tenant_id=event.tenant_id,
            )

    async def process_issue_resolution_event(self, event: ResolutionEvent) -> None:
        await self.repo.log_change_event(event)
        count = await self.repo.get_resolution_count_for_hash(
            event.user_id,
            event.issue_hash,
            tenant_id=event.tenant_id,
        )
        if count >= self.RESOLVE_REINTRODUCE_LIMIT:
            reason = f"Issue with hash {event.issue_hash} has been re-introduced {count + 1} times."
            await self._handle_violation(
                event.user_id,
                AbuseType.RESOLVE_REINTRODUCE,
                reason,
                tenant_id=event.tenant_id,
            )

    async def process_score_update_event(self, event: ScoreUpdateEvent) -> None:
        if event.new_score >= self.HIGH_SCORE_THRESHOLD:
            doc_count = await self.repo.get_user_document_count(
                event.user_id,
                tenant_id=event.tenant_id,
            )
            if doc_count < self.LOW_DOCS_THRESHOLD:
                reason = (
                    f"User has a high score ({event.new_score}) with only {doc_count} documents."
                )
                await self._handle_violation(
                    event.user_id,
                    AbuseType.HIGH_SCORE_LOW_DOCS,
                    reason,
                    tenant_id=event.tenant_id,
                )

    async def process_weight_change_event(self, event: WeightChangeEvent) -> None:
        await self.repo.log_change_event(event)
        old_weight = await self.repo.get_previous_weight_in_last_24h(
            event.user_id,
            event.component_id,
            tenant_id=event.tenant_id,
        )
        if old_weight is not None and old_weight > 0:
            change_percent = abs(event.new_weight - old_weight) / old_weight
            if change_percent >= self.LARGE_WEIGHT_CHANGE_PERCENT_THRESHOLD:
                reason = (
                    f"Weight for {event.component_id} changed by {change_percent:.1%} in 24 hours."
                )
                await self._handle_violation(
                    event.user_id,
                    AbuseType.LARGE_WEIGHT_CHANGE,
                    reason,
                    tenant_id=event.tenant_id,
                )

    async def process_event(self, event: Any) -> None:
        """A generic event processor that delegates to specific handlers."""
        has_component_id = hasattr(event, "component_id") and hasattr(event, "new_weight")
        has_issue_hash = hasattr(event, "issue_hash")
        has_new_score = hasattr(event, "new_score")

        if has_component_id:
            await self.process_weight_change_event(event)
            await self.process_change_event(event)
        elif has_issue_hash:
            await self.process_issue_resolution_event(event)
        elif has_new_score:
            await self.process_score_update_event(event)
        elif hasattr(event, "user_id"):
            await self.process_change_event(event)
