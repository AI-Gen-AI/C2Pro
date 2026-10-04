from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.analysis.application.dtos import AlertCreate
from src.analysis.ports.alert_repository import AlertRepository
from src.analysis.ports.types import AlertRecord
from src.coherence.alert_generator import AlertGenerator
from src.coherence.rules_engine.context_rules import CoherenceRuleResult
from src.shared_kernel.enums import AlertSeverity, AlertStatus, AlertType

FINGERPRINT_VERSION = 2


class AlertGeneratorService:
    def __init__(self, repository: AlertRepository) -> None:
        self._repository = repository

    async def process_violations(
        self,
        project_id: UUID,
        violations: list[AlertCreate],
        *,
        tenant_id: UUID | None = None,
        auto_resolve: bool = True,
        commit: bool = True,
    ) -> list[AlertRecord]:
        """
        Persist new alerts, update existing ones, and optionally auto-resolve missing ones.
        """
        # Collapse duplicate findings within the same evaluation before touching
        # persistence.  A repeated detector emission is the same observation, not
        # a second user-visible alert.
        unique_violations: list[tuple[str, AlertCreate]] = []
        seen_fingerprints: set[str] = set()
        for violation in violations:
            fingerprint = self._fingerprint(violation)
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            unique_violations.append((fingerprint, violation))

        fingerprints = set(seen_fingerprints)
        existing = await self._load_existing(project_id, tenant_id=tenant_id)
        existing_by_fp: dict[str, AlertRecord] = {}
        for existing_alert in existing:
            stored_fingerprint = self._fingerprint_existing(existing_alert)
            if stored_fingerprint is None:
                continue
            metadata = dict(existing_alert.alert_metadata or {})
            if (
                metadata.get("fingerprint") != stored_fingerprint
                or metadata.get("fingerprint_version") != FINGERPRINT_VERSION
            ):
                metadata["fingerprint"] = stored_fingerprint
                metadata["fingerprint_version"] = FINGERPRINT_VERSION
                existing_alert.alert_metadata = metadata
            existing_by_fp.setdefault(stored_fingerprint, existing_alert)

        processed: list[AlertRecord] = []
        now = datetime.now(UTC)

        for fingerprint, violation in unique_violations:
            current_alert = existing_by_fp.get(fingerprint)

            if current_alert is None:
                created = await self._create_alert(project_id, violation, fingerprint)
                processed.append(created)
                continue

            if current_alert.status == AlertStatus.RESOLVED:
                # A previously fixed finding detected again is a genuine regression.
                self._reopen_alert(current_alert, violation, fingerprint)
            else:
                # OPEN findings stay open. ACKNOWLEDGED (accepted/genuine variance)
                # and DISMISSED (false positive) are human dispositions and must not
                # be silently rewritten just because the same detector fires again.
                self._update_alert(current_alert, violation, fingerprint)
            await self._repository.update(current_alert)
            processed.append(current_alert)

        if auto_resolve:
            for existing_alert in existing:
                prior_fingerprint = (existing_alert.alert_metadata or {}).get("fingerprint")
                if (
                    existing_alert.status in {AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED}
                    and prior_fingerprint not in fingerprints
                ):
                    existing_alert.status = AlertStatus.RESOLVED
                    existing_alert.resolved_at = now
                    existing_alert.resolution_notes = self._merge_notes(
                        existing_alert.resolution_notes,
                        "Auto-resolved: violation not detected in latest analysis.",
                    )
                    await self._repository.update(existing_alert)

        if commit:
            await self._repository.commit()

        return processed

    async def process_rule_results(
        self,
        project_id: UUID,
        rule_results: Iterable[CoherenceRuleResult],
        *,
        analysis_id: UUID | None = None,
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

    async def _load_existing(
        self, project_id: UUID, *, tenant_id: UUID | None = None
    ) -> list[AlertRecord]:
        items: list[AlertRecord] = []
        cursor = None
        while True:
            page = await self._repository.list_for_project(
                project_id=project_id,
                tenant_id=tenant_id,
                alert_type=AlertType.COHERENCE,
                cursor=cursor,
                limit=200,
            )
            items.extend(page.items)
            if not page.has_more:
                break
            cursor = page.next_cursor
        return items

    async def _create_alert(
        self, project_id: UUID, violation: AlertCreate, fingerprint: str
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
        alert.alert_metadata = self._build_metadata(
            violation,
            fingerprint,
            existing_metadata=alert.alert_metadata,
        )

    def _reopen_alert(self, alert: AlertRecord, violation: AlertCreate, fingerprint: str) -> None:
        alert.status = AlertStatus.OPEN
        alert.resolved_at = None
        alert.resolved_by = None
        alert.resolution_notes = self._merge_notes(
            alert.resolution_notes,
            "Regression detected automatically.",
        )
        self._update_alert(alert, violation, fingerprint)

    def _build_metadata(
        self,
        violation: AlertCreate,
        fingerprint: str,
        *,
        existing_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Detector fields may refresh on every evaluation, but human-managed
        # history/evidence/disposition metadata must survive the refresh.
        metadata = dict(existing_metadata or {})
        legacy_evidence = metadata.get("evidence")
        if isinstance(legacy_evidence, dict):
            metadata.setdefault("detection_evidence", dict(legacy_evidence))
            metadata["evidence"] = []
        elif legacy_evidence is not None and not isinstance(legacy_evidence, list):
            metadata["evidence"] = []

        metadata.update(dict(violation.alert_metadata or {}))
        metadata["fingerprint"] = fingerprint
        metadata["fingerprint_version"] = FINGERPRINT_VERSION
        metadata["requires_human_review"] = self._requires_human_review(violation)
        return metadata

    @staticmethod
    def _normalized_identity_text(value: object) -> str:
        return " ".join(str(value or "").split())

    def _fingerprint_existing(self, alert: AlertRecord) -> str | None:
        metadata = dict(alert.alert_metadata or {})
        fingerprint = metadata.get("fingerprint")
        if (
            metadata.get("fingerprint_version") == FINGERPRINT_VERSION
            and isinstance(fingerprint, str)
            and fingerprint
        ):
            return fingerprint

        # Unversioned/older fingerprints are derived state from a previous
        # identity scheme. Recompute them so legacy rows reconcile in place.
        rule_id = getattr(alert, "rule_id", None)
        if not rule_id:
            return None
        source_clause_id = getattr(alert, "source_clause_id", None)
        if source_clause_id is None:
            detector = metadata.get("detection_evidence")
            if not isinstance(detector, dict):
                legacy = metadata.get("evidence")
                detector = legacy if isinstance(legacy, dict) else {}
            source_clause_id = detector.get("source_clause_id")

        related = getattr(alert, "related_clause_ids", None) or []
        anchors = [str(value) for value in [source_clause_id, *related] if value]
        if anchors:
            base = f"{rule_id}|anchors|" + "|".join(sorted(set(anchors)))
            return hashlib.sha256(base.encode("utf-8")).hexdigest()

        entities = self._flatten_entities(getattr(alert, "affected_entities", {}) or {})
        if entities:
            category = getattr(alert, "category", None) or ""
            base = f"{rule_id}|entities|{category}|" + "|".join(sorted(set(entities)))
            return hashlib.sha256(base.encode("utf-8")).hexdigest()

        detector = metadata.get("detection_evidence")
        if not isinstance(detector, dict):
            legacy = metadata.get("evidence")
            detector = legacy if isinstance(legacy, dict) else {}
        claim = self._normalized_identity_text(detector.get("claim"))
        quote = self._normalized_identity_text(detector.get("quote"))
        category = getattr(alert, "category", None) or ""
        base = f"{rule_id}|fallback|{category}|{claim}|{quote}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _requires_human_review(self, violation: AlertCreate) -> bool:
        if violation.severity in {AlertSeverity.CRITICAL, AlertSeverity.HIGH}:
            return True
        rule_id = (violation.rule_id or "").lower()
        return "penal" in rule_id or "penalty" in rule_id

    def _fingerprint(self, violation: AlertCreate) -> str:
        rule_id = violation.rule_id or "unknown_rule"
        metadata = dict(violation.alert_metadata or {})
        detector = metadata.get("detection_evidence")
        if not isinstance(detector, dict):
            detector = {}

        anchors: list[str] = []
        if violation.source_clause_id:
            anchors.append(str(violation.source_clause_id))
        raw_source_locator = detector.get("source_clause_id")
        if raw_source_locator:
            anchors.append(str(raw_source_locator))
        if violation.related_clause_ids:
            anchors.extend(str(clause_id) for clause_id in violation.related_clause_ids)
        if anchors:
            # Rendered claim/quote/severity/category may evolve while the same
            # revision-bound documentary finding remains. Stable locators own
            # identity whenever they exist.
            base = f"{rule_id}|anchors|" + "|".join(sorted(set(anchors)))
            return hashlib.sha256(base.encode("utf-8")).hexdigest()

        entities = sorted(set(self._flatten_entities(violation.affected_entities)))
        if entities:
            base = f"{rule_id}|entities|{violation.category or ''}|" + "|".join(entities)
            return hashlib.sha256(base.encode("utf-8")).hexdigest()

        # Unanchored findings have no stronger locator. Fall back to detector
        # evidence rather than presentation message/title.
        claim = self._normalized_identity_text(detector.get("claim"))
        quote = self._normalized_identity_text(detector.get("quote"))
        base = f"{rule_id}|fallback|{violation.category or ''}|{claim}|{quote}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _flatten_entities(self, payload: dict[str, Any]) -> list[str]:
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

