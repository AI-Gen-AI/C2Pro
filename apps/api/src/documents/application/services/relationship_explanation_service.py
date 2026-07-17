"""
TS-UA-SVC-EXT-002

Evidence relationship explanation service grounded in document clauses,
alert linkages, and explicit citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import cast
from uuid import UUID

from src.analysis.domain.enums import AlertSeverity
from src.core.json_types import JsonDict
from src.documents.domain.models import Document


@dataclass(frozen=True)
class ExplanationAlertInput:
    """Minimal alert shape needed to explain document relationships."""

    id: UUID
    title: str
    severity: AlertSeverity
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    source_clause_id: UUID | None = None


@dataclass(frozen=True)
class ExplanationCitation:
    """Citation grounding for a relationship explanation."""

    clause_id: UUID
    clause_code: str
    label: str
    page: int | None
    reason: str


@dataclass(frozen=True)
class RelationshipExplanation:
    """Structured explanation returned to API/UI layers."""

    summary: str
    strongest_cluster: str
    review_priority: str
    latest_signal: str
    citations: list[ExplanationCitation] = field(default_factory=list)


class EvidenceRelationshipExplanationService:
    """Build a concise, citation-grounded narrative for a document graph."""

    def build(
        self,
        *,
        document: Document,
        alerts: list[ExplanationAlertInput],
    ) -> RelationshipExplanation:
        {clause.id: clause for clause in document.clauses}
        clause_scores: dict[UUID, int] = {clause.id: 0 for clause in document.clauses}

        for alert in alerts:
            if alert.source_clause_id and alert.source_clause_id in clause_scores:
                clause_scores[alert.source_clause_id] += 2

        for clause in document.clauses:
            confidence = clause.extraction_confidence or 0.0
            clause_scores[clause.id] += int(round(confidence * 10))

        strongest_clause = max(
            document.clauses,
            key=lambda clause: clause_scores.get(clause.id, 0),
            default=None,
        )

        critical_count = sum(1 for alert in alerts if alert.severity == AlertSeverity.CRITICAL)
        latest_alert = max(
            alerts,
            key=lambda alert: alert.updated_at or alert.created_at,
            default=None,
        )

        citations: list[ExplanationCitation] = []
        for clause in document.clauses:
            evidence_location = cast(
                JsonDict,
                clause.extracted_entities.get("evidence_location", {}),
            )
            citations.append(
                ExplanationCitation(
                    clause_id=clause.id,
                    clause_code=clause.clause_code,
                    label=clause.title or clause.full_text or clause.clause_code,
                    page=cast(int | None, evidence_location.get("page_number")),
                    reason=(
                        "Linked to active alert"
                        if any(alert.source_clause_id == clause.id for alert in alerts)
                        else "Extracted clause in document graph"
                    ),
                )
            )

        citations.sort(
            key=lambda citation: (
                0 if any(alert.source_clause_id == citation.clause_id for alert in alerts) else 1,
                next(
                    (
                        document.clauses[index].title or document.clauses[index].clause_code
                        for index, clause in enumerate(document.clauses)
                        if clause.id == citation.clause_id
                    ),
                    citation.clause_code,
                ),
            )
        )

        summary = (
            f"This document connects {len(document.clauses)} extracted clauses "
            f"to {len(alerts)} active alerts."
        )
        strongest_cluster = (
            f"The strongest relationship cluster centers on {(strongest_clause.title or strongest_clause.clause_code).lower()}."
            if strongest_clause
            else "No clause cluster is available yet."
        )
        review_priority = (
            f"Review priority is elevated because {critical_count} alert"
            f"{'' if critical_count == 1 else 's'} are critical."
            if critical_count > 0
            else "Review priority is moderate because there are no critical alerts in the current graph."
        )
        latest_signal = (
            f"Most recent signal: {latest_alert.title.lower()}."
            if latest_alert
            else "Most recent signal: no active alerts are linked to this document yet."
        )

        return RelationshipExplanation(
            summary=summary,
            strongest_cluster=strongest_cluster,
            review_priority=review_priority,
            latest_signal=latest_signal,
            citations=citations,
        )
