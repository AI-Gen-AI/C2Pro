from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Iterable

from src.analysis.application.dtos import AlertCreate
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.analysis.ports.alert_repository import AlertRepository
from src.analysis.ports.types import AlertRecord
from src.coherence.alert_generator import AlertGenerator
from src.coherence.rules_engine.context_rules import CoherenceRuleResult


class AlertGeneratorService:
    def __init__(self, repository: AlertRepository) -> None:
        self._repository = repository

    async def process_violations(
        self,
        project_id,
        violations: list[AlertCreate],
        *,
        auto_resolve: bool = True,
    ) -> list[AlertRecord]:
        """
        Persist new alerts, update existing ones, and optionally auto-resolve missing ones.
        """
        fingerprints = {self._fingerprint(violation) for violation in violations}
        existing = await self._load_existing(project_id)
        existing_by_fp = {
            (alert.alert_metadata or {}).get("fingerprint"): alert for alert in existing
        }

        processed: list[AlertRecord] = []
        now = datetime.utcnow()

        for violation in violations:
            fingerprint = self._fingerprint(violation)
            alert = existing_by_fp.get(fingerprint)

            if alert is None:
                created = await self._create_alert(project_id, violation, fingerprint)
                processed.append(created)
                continue

            if alert.status == AlertStatus.OPEN:
                self._update_alert(alert, violation, fingerprint)
            else:
                self._reopen_alert(alert, violation, fingerprint)
            await self._repository.update(alert)
            processed.append(alert)

        if auto_resolve:
            for alert in existing:
                fingerprint = (alert.alert_metadata or {}).get("fingerprint")
                if alert.status == AlertStatus.OPEN and fingerprint not in fingerprints:
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = now
                    alert.resolution_notes = self._merge_notes(
                        alert.resolution_notes,
                        "Auto-resolved: violation not detected in latest analysis.",
                    )
                    await self._repository.update(alert)

        await self._repository.commit()

        return processed

    async def process_rule_results(
        self,
        project_id,
        rule_results: Iterable[CoherenceRuleResult],
        *,
        analysis_id=None,
        auto_resolve: bool = True,
    ) -> list[AlertRecord]:
        generator = AlertGenerator(project_id=project_id, analysis_id=analysis_id)
        violations: list[AlertCreate] = []
        for result in rule_results:
            violations.extend(generator.generate(result))
        return await self.process_violations(
            project_id=project_id,
            violations=violations,
            auto_resolve=auto_resolve,
        )

    async def _load_existing(self, project_id) -> list[AlertRecord]:
        items: list[AlertRecord] = []
        cursor = None
        while True:
            page = await self._repository.list_for_project(
                project_id=project_id,
                cursor=cursor,
                limit=200,
            )
            items.extend(page.items)
            if not page.has_more:
                break
            cursor = page.next_cursor
        return items

    async def _create_alert(
        self, project_id, violation: AlertCreate, fingerprint: str
    ) -> AlertRecord:
        metadata = self._build_metadata(violation, fingerprint)
        payload = violation.model_copy(update={"alert_metadata": metadata, "project_id": project_id})
        return await self._repository.create(payload)

    def _update_alert(self, alert: AlertRecord, violation: AlertCreate, fingerprint: str) -> None:
        alert.severity = violation.severity
        alert.category = violation.category
        alert.rule_id = violation.rule_id
        alert.title = violation.title
        alert.description = violation.description
        alert.recommendation = violation.recommendation
        alert.source_clause_id = violation.source_clause_id
        alert.related_clause_ids = violation.related_clause_ids
        alert.affected_entities = violation.affected_entities
        alert.impact_level = violation.impact_level
        alert.alert_metadata = self._build_metadata(violation, fingerprint)

    def _reopen_alert(self, alert: AlertRecord, violation: AlertCreate, fingerprint: str) -> None:
        alert.status = AlertStatus.OPEN
        alert.resolved_at = None
        alert.resolved_by = None
        alert.resolution_notes = self._merge_notes(
            alert.resolution_notes,
            "Regression detected automatically.",
        )
        self._update_alert(alert, violation, fingerprint)

    def _build_metadata(self, violation: AlertCreate, fingerprint: str) -> dict:
        metadata = dict(violation.alert_metadata or {})
        metadata["fingerprint"] = fingerprint
        metadata["requires_human_review"] = self._requires_human_review(violation)
        return metadata

    def _requires_human_review(self, violation: AlertCreate) -> bool:
        if violation.severity in {AlertSeverity.CRITICAL, AlertSeverity.HIGH}:
            return True
        rule_id = (violation.rule_id or "").lower()
        return "penal" in rule_id or "penalty" in rule_id

    def _fingerprint(self, violation: AlertCreate) -> str:
        rule_id = violation.rule_id or "unknown_rule"
        entities = self._flatten_entities(violation.affected_entities)
        if violation.source_clause_id:
            entities.append(str(violation.source_clause_id))
        if violation.related_clause_ids:
            entities.extend(str(clause_id) for clause_id in violation.related_clause_ids)
        entities = sorted(set(entities))
        base = f"{rule_id}_" + "_".join(entities) if entities else rule_id
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _flatten_entities(self, payload: dict) -> list[str]:
        if not payload:
            return []
        collected: list[str] = []
        for value in payload.values():
            if isinstance(value, list):
                collected.extend(str(item) for item in value)
            elif value is not None:
                collected.append(str(value))
        return collected

    def _merge_notes(self, existing: str | None, note: str) -> str:
        if not existing:
            return note
        if note in existing:
            return existing
        return f"{existing} | {note}"

