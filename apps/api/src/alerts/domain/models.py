"""
Alert Domain Model.

Pure Python domain entity - NO SQLAlchemy, NO external dependencies.
Contains business logic for alert lifecycle management.
Refers to TASK-REV-006, TS-BUG-ALRT-IMPORT-001.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus


@dataclass
class Alert:
    id: UUID
    project_id: UUID
    severity: AlertSeverity
    category: str
    status: AlertStatus
    approval_status: ApprovalStatus
    rule_id: str | None
    title: str
    description: str
    affected_entities: dict[str, Any] = field(default_factory=dict)
    alert_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    resolution_notes: str | None = None
    source_clause_id: UUID | None = None

    def apply_review(
        self,
        user_id: UUID,
        decision: str,
        comment: str,
    ) -> None:
        """Apply review decision to alert."""
        self.reviewed_by = user_id
        self.reviewed_at = datetime.now(UTC)
        self.review_comment = comment

        if decision == "approve":
            self.approval_status = ApprovalStatus.APPROVED
            self.status = AlertStatus.ACKNOWLEDGED
        else:
            self.approval_status = ApprovalStatus.REJECTED
            self.status = AlertStatus.DISMISSED
            self.resolved_at = datetime.now(UTC)
            self.resolved_by = user_id
            self.resolution_notes = comment

        self.updated_at = datetime.now(UTC)

    def apply_resolution(
        self,
        user_id: UUID,
        resolution: str,
        root_cause: str | None = None,
    ) -> None:
        """Apply resolution to alert."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        self.resolved_by = user_id
        self.resolution_notes = resolution
        self.updated_at = datetime.now(UTC)

        if root_cause:
            metadata = dict(self.alert_metadata or {})
            metadata["root_cause"] = root_cause
            self.alert_metadata = metadata

    def requires_root_cause(self) -> bool:
        """Check if alert requires root cause for resolution."""
        return self.severity in {AlertSeverity.CRITICAL, AlertSeverity.HIGH}

    def calculate_sla_due_at(self) -> tuple[str | None, datetime | None]:
        """Calculate SLA policy and due date based on severity."""
        policy_by_severity = {
            AlertSeverity.CRITICAL: ("Critical severity: first response in 2 hours", 2),
            AlertSeverity.HIGH: ("High severity: response in 24 hours", 24),
            AlertSeverity.MEDIUM: ("Medium severity: response in 72 hours", 72),
            AlertSeverity.LOW: ("Low severity: response in 120 hours", 120),
        }
        policy = policy_by_severity.get(self.severity)
        if policy is None:
            return None, None

        policy_name, hours = policy
        due_at = self.coerce_datetime(self.created_at) + timedelta(hours=hours)
        return policy_name, due_at

    def append_history(
        self,
        action: str,
        user_id: UUID,
        **details: str,
    ) -> None:
        """Append action to alert history."""
        metadata = dict(self.alert_metadata or {})
        history = list(metadata.get("history", []))
        history.append(
            {
                "action": action,
                "timestamp": datetime.now(UTC).isoformat(),
                "user_id": str(user_id),
                **details,
            }
        )
        metadata["history"] = history
        self.alert_metadata = metadata

    def attach_evidence(
        self,
        evidence_type: str,
        content: str,
        source: str,
        added_by: UUID,
    ) -> None:
        """Attach evidence to alert."""
        metadata = dict(self.alert_metadata or {})
        evidence = list(metadata.get("evidence", []))
        evidence.append(
            {
                "type": evidence_type,
                "content": content,
                "source": source,
                "added_by": str(added_by),
                "added_at": datetime.now(UTC).isoformat(),
            }
        )
        metadata["evidence"] = evidence
        self.alert_metadata = metadata

    @staticmethod
    def normalize_affected_entities(value: object) -> dict[str, Any]:
        """
        Normalize affected_entities to standard dict format.

        Handles legacy format where entities were stored as a list:
        - list: ["doc-1", "doc-2"] -> {"items": ["doc-1", "doc-2"]}
        - dict: {"items": [...]} -> unchanged
        - other: None -> {}

        Args:
            value: The affected_entities value (list, dict, or other)

        Returns:
            Normalized dict with standard format
        """
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"items": value}
        return {}

    @staticmethod
    def normalize_metadata(value: object) -> dict[str, Any]:
        """
        Normalize alert_metadata to standard dict format.

        Args:
            value: The metadata value (dict or other)

        Returns:
            Normalized dict or empty dict
        """
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def coerce_text(primary: object, fallback: object, default: str) -> str:
        """
        Coerce to first non-empty string from candidates.

        Args:
            primary: Primary candidate
            fallback: Fallback candidate if primary is empty
            default: Default value if no candidates are non-empty

        Returns:
            First non-empty stripped string or default
        """
        for candidate in (primary, fallback):
            if isinstance(candidate, str):
                stripped = candidate.strip()
                if stripped:
                    return stripped
        return default

    @staticmethod
    def coerce_category(value: object) -> str:
        """
        Coerce to non-empty category string.

        Args:
            value: Category value

        Returns:
            Non-empty stripped category or "risk"
        """
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return "risk"

    @staticmethod
    def coerce_state(value: object, default: str) -> str:
        """
        Coerce to non-empty lowercase state string.

        Args:
            value: State value
            default: Default value if coercion fails

        Returns:
            Non-empty lowercase string or default
        """
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped.lower()
        return default

    @staticmethod
    def coerce_datetime(value: object) -> datetime:
        """
        Coerce to datetime.

        Args:
            value: Value to coerce

        Returns:
            datetime if value is datetime, otherwise current UTC datetime
        """
        if isinstance(value, datetime):
            return value
        return datetime.now(UTC)
