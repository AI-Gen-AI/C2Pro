"""
TS-UC-SEC-GAM-001: Anti-gaming detection domain logic.

Refers to Suite ID: TS-UD-COH-GAM-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID


@dataclass(frozen=True)
class AlertEvent:
    """Refers to Suite ID: TS-UC-SEC-GAM-001 and TS-UD-COH-GAM-001."""

    type: str
    user_id: UUID
    signature: str
    timestamp: datetime
    weight_change_percent: float | None = None


@dataclass(frozen=True)
class AntiGamingResult:
    """Refers to Suite ID: TS-UC-SEC-GAM-001 and TS-UD-COH-GAM-001."""

    is_gaming: bool
    reason: str | None
    violations: list[str]
    penalty_points: int
    audit_logs: list[str]


class AntiGamingDetector:
    """Refers to Suite ID: TS-UC-SEC-GAM-001 and TS-UD-COH-GAM-001."""

    def __init__(
        self,
        mass_changes_threshold: int = 10,
        mass_changes_window_minutes: int = 60,
        window_minutes: int | None = None,
        repeat_threshold: int = 3,
        repeat_window_minutes: int = 5,
        high_score_threshold: float = 90.0,
        few_docs_threshold: int = 5,
        weight_change_threshold: float = 20.0,
        weight_window_hours: int = 24,
        penalty_per_violation: int = 5,
    ) -> None:
        self.mass_changes_threshold = mass_changes_threshold
        self.mass_changes_window_minutes = (
            window_minutes if window_minutes is not None else mass_changes_window_minutes
        )
        self.repeat_threshold = repeat_threshold
        self.repeat_window_minutes = repeat_window_minutes
        self.high_score_threshold = high_score_threshold
        self.few_docs_threshold = few_docs_threshold
        self.weight_change_threshold = weight_change_threshold
        self.weight_window_hours = weight_window_hours
        self.penalty_per_violation = penalty_per_violation

    def detect(
        self,
        events: list[AlertEvent],
        *,
        score: float | None = None,
        document_count: int | None = None,
        now: datetime | None = None,
    ) -> AntiGamingResult:
        reference_time = now or self._resolve_reference_time(events)
        violations: list[str] = []

        if self._is_mass_changes(events, reference_time):
            violations.append("mass_changes")
        if self._is_resolve_reintroduce(events, reference_time):
            violations.append("resolve_reintroduce")
        if self._is_suspicious_high_score(score, document_count):
            violations.append("suspicious_high_score")
        if self._is_weight_manipulation(events, reference_time):
            violations.append("weight_manipulation")

        if not violations:
            return AntiGamingResult(
                is_gaming=False,
                reason=None,
                violations=[],
                penalty_points=0,
                audit_logs=[],
            )

        reason = violations[0] if len(violations) == 1 else "multiple_violations"
        audit_logs = [f"anti_gaming_violation:{violation}" for violation in violations]
        return AntiGamingResult(
            is_gaming=True,
            reason=reason,
            violations=violations,
            penalty_points=len(violations) * self.penalty_per_violation,
            audit_logs=audit_logs,
        )

    def _is_mass_changes(self, events: list[AlertEvent], reference_time: datetime) -> bool:
        cutoff = reference_time - timedelta(minutes=self.mass_changes_window_minutes)
        relevant = [
            event
            for event in events
            if event.type in {"change", "created", "resolved", "updated"}
            and event.timestamp >= cutoff
            and event.timestamp <= reference_time
        ]
        return len(relevant) > self.mass_changes_threshold

    def _is_resolve_reintroduce(self, events: list[AlertEvent], reference_time: datetime) -> bool:
        cutoff = reference_time - timedelta(minutes=self.repeat_window_minutes)
        recent = [event for event in events if cutoff <= event.timestamp <= reference_time]
        by_signature: dict[str, list[str]] = {}
        for event in recent:
            by_signature.setdefault(event.signature, []).append(event.type)

        for types in by_signature.values():
            created_count = types.count("created")
            resolved_count = types.count("resolved")
            if created_count >= self.repeat_threshold and resolved_count >= self.repeat_threshold - 1:
                return True
        return False

    def _is_suspicious_high_score(
        self, score: float | None, document_count: int | None
    ) -> bool:
        if score is None or document_count is None:
            return False
        return score >= self.high_score_threshold and document_count <= self.few_docs_threshold

    def _is_weight_manipulation(self, events: list[AlertEvent], reference_time: datetime) -> bool:
        cutoff = reference_time - timedelta(hours=self.weight_window_hours)
        for event in events:
            if not (cutoff <= event.timestamp <= reference_time):
                continue
            if event.weight_change_percent is None:
                continue
            if event.weight_change_percent > self.weight_change_threshold:
                return True
        return False

    @staticmethod
    def _resolve_reference_time(events: list[AlertEvent]) -> datetime:
        if not events:
            return datetime.now(timezone.utc)
        latest = max(event.timestamp for event in events)
        if latest.tzinfo is None:
            return latest.replace(tzinfo=timezone.utc)
        return latest.astimezone(timezone.utc)
