from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from src.analysis.application.dtos import AlertCreate
from src.analysis.ports.alert_repository import AlertRepository
from src.analysis.ports.types import AlertRecord
from src.coherence.alert_generator import AlertGenerator
from src.coherence.rules_engine.context_rules import CoherenceRuleResult
from src.shared_kernel.enums import AlertSeverity, AlertStatus, AlertType

FINGERPRINT_VERSION = 4

_POSITIONAL_RAG_LOCATOR = re.compile(r"^chunk_\d+_([0-9a-fA-F]{8})$")
_PARSED_TEXT_LOCATOR = re.compile(r"^parsed_([0-9a-fA-F]{8})$")




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
                or metadata.get("finding_key") != stored_fingerprint
                or metadata.get("identity_schema_version") != FINGERPRINT_VERSION
                or "identity_quality" not in metadata
            ):
                metadata["fingerprint"] = stored_fingerprint
                metadata["fingerprint_version"] = FINGERPRINT_VERSION
                metadata["finding_key"] = stored_fingerprint
                metadata["identity_schema_version"] = FINGERPRINT_VERSION
                metadata["identity_quality"] = self._identity_quality_existing(existing_alert)
                existing_alert.alert_metadata = metadata

            previous = existing_by_fp.get(stored_fingerprint)
            if previous is not None and previous is not existing_alert:
                raise RuntimeError(
                    "LEGACY_IDENTITY_CONFLICT:"
                    f"{project_id}:{stored_fingerprint}"
                )
            existing_by_fp[stored_fingerprint] = existing_alert

        processed: list[AlertRecord] = []
        now = datetime.now(UTC)

        for fingerprint, violation in unique_violations:
            current_alert = existing_by_fp.get(fingerprint)

            if current_alert is None:
                created = await self._create_alert(project_id, violation, fingerprint)
                processed.append(created)
                continue

            basis_changed = self._review_basis_changed(current_alert, violation)
            if (
                current_alert.status in {AlertStatus.ACKNOWLEDGED, AlertStatus.DISMISSED}
                and basis_changed
            ):
                self._reopen_for_basis_change(current_alert, violation, fingerprint)
            elif current_alert.status == AlertStatus.RESOLVED:
                # A previously fixed finding detected again is a genuine regression.
                self._reopen_alert(current_alert, violation, fingerprint)
            else:
                # OPEN findings stay open. ACKNOWLEDGED/DISMISSED remain stable only
                # while the exact reviewed evidence basis remains the same.
                self._update_alert(current_alert, violation, fingerprint)
            await self._repository.update(current_alert)
            processed.append(current_alert)

        if auto_resolve:
            for existing_alert in existing:
                prior_fingerprint = (existing_alert.alert_metadata or {}).get("fingerprint")
                if (
                    existing_alert.status == AlertStatus.OPEN
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

    def _reopen_for_basis_change(
        self,
        alert: AlertRecord,
        violation: AlertCreate,
        fingerprint: str,
    ) -> None:
        """Revalidate a basis-sensitive human disposition on new trusted evidence."""
        existing_metadata = dict(alert.alert_metadata or {})
        from_key = (
            existing_metadata.get("disposition_basis_key")
            or existing_metadata.get("current_observation_key")
            or self._observation_key(existing_metadata)
        )
        incoming_metadata = dict(violation.alert_metadata or {})
        to_key = self._observation_key(incoming_metadata)

        history_raw = existing_metadata.get("history", [])
        history = list(history_raw) if isinstance(history_raw, list) else []
        already_recorded = any(
            isinstance(item, dict)
            and item.get("action") == "basis_changed_reopened"
            and item.get("to_observation_key") == to_key
            for item in history
        )
        if not already_recorded:
            history.append(
                {
                    "action": "basis_changed_reopened",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "from_observation_key": from_key,
                    "to_observation_key": to_key,
                }
            )
        existing_metadata["history"] = history
        alert.alert_metadata = existing_metadata
        alert.status = AlertStatus.OPEN
        alert.resolved_at = None
        alert.resolved_by = None

        current_approval = getattr(alert, "approval_status", None)
        if current_approval is not None:
            writable_alert = cast(Any, alert)
            try:
                writable_alert.approval_status = type(current_approval)("pending")
            except (TypeError, ValueError):
                writable_alert.approval_status = "pending"

        self._update_alert(alert, violation, fingerprint)

    def _review_basis_changed(
        self,
        alert: AlertRecord,
        violation: AlertCreate,
    ) -> bool:
        existing_metadata = dict(alert.alert_metadata or {})
        reviewed_basis = (
            existing_metadata.get("disposition_basis_key")
            or existing_metadata.get("current_observation_key")
            or self._observation_key(existing_metadata)
        )
        incoming_basis = self._observation_key(dict(violation.alert_metadata or {}))
        return bool(
            isinstance(reviewed_basis, str)
            and reviewed_basis
            and incoming_basis is not None
            and incoming_basis != reviewed_basis
        )

    @staticmethod
    def _observation_key(metadata: dict[str, Any]) -> str | None:
        detector = metadata.get("detection_evidence")
        if not isinstance(detector, dict):
            return None

        basis_fields = (
            "revision_id",
            "artifact_id",
            "content_sha256",
            "source_document_id",
            "source_clause_id",
        )
        parts = [
            f"{field}={detector[field]}"
            for field in basis_fields
            if detector.get(field) not in (None, "")
        ]
        if not parts:
            return None
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

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
        metadata["finding_key"] = fingerprint
        metadata["identity_schema_version"] = FINGERPRINT_VERSION
        metadata["identity_quality"] = self._identity_quality_violation(violation)
        metadata["requires_human_review"] = self._requires_human_review(violation)
        observation_key = self._observation_key(metadata)
        if observation_key is not None:
            metadata["current_observation_key"] = observation_key
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
        detector = metadata.get("detection_evidence")
        if not isinstance(detector, dict):
            legacy = metadata.get("evidence")
            detector = legacy if isinstance(legacy, dict) else {}

        source_clause_id = getattr(alert, "source_clause_id", None)
        raw_source_locator = detector.get("source_clause_id")
        if source_clause_id is None and raw_source_locator:
            source_clause_id = raw_source_locator

        if raw_source_locator and self._is_revision_unstable_locator(raw_source_locator):
            return self._synthetic_fallback_fingerprint(rule_id, detector)

        category = getattr(alert, "category", None) or ""
        affected = getattr(alert, "affected_entities", {}) or {}
        family = self._document_family_fingerprint(
            rule_id=rule_id,
            category=category,
            detector=detector,
            affected_entities=affected,
        )
        if family is not None:
            return family

        non_document_entities = self._flatten_entities(
            {key: value for key, value in affected.items() if key != "documents"}
        )
        if non_document_entities:
            base = (
                f"{rule_id}|entities|{category}|"
                + "|".join(sorted(set(non_document_entities)))
            )
            return hashlib.sha256(base.encode("utf-8")).hexdigest()

        related = getattr(alert, "related_clause_ids", None) or []
        anchors = [
            str(value)
            for value in [source_clause_id, *related]
            if value and not self._is_revision_unstable_locator(value)
        ]
        if anchors:
            base = f"{rule_id}|revision_anchors|" + "|".join(sorted(set(anchors)))
            return hashlib.sha256(base.encode("utf-8")).hexdigest()

        claim = self._normalized_identity_text(detector.get("claim"))
        quote = self._normalized_identity_text(detector.get("quote"))
        base = f"{rule_id}|fallback|{category}|{claim}|{quote}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _identity_quality_violation(self, violation: AlertCreate) -> str:
        metadata = dict(violation.alert_metadata or {})
        detector = metadata.get("detection_evidence")
        if not isinstance(detector, dict):
            detector = {}

        raw_source_locator = detector.get("source_clause_id")
        if raw_source_locator and self._is_revision_unstable_locator(raw_source_locator):
            return "weak"

        if (
            self._document_family_fingerprint(
                rule_id=violation.rule_id or "unknown_rule",
                category=violation.category or "",
                detector=detector,
                affected_entities=violation.affected_entities,
            )
            is not None
        ):
            return "strong"

        non_document_entities = self._flatten_entities(
            {
                key: value
                for key, value in (violation.affected_entities or {}).items()
                if key != "documents"
            }
        )
        if non_document_entities:
            return "strong"

        if (
            violation.source_clause_id
            or violation.related_clause_ids
            or raw_source_locator
        ):
            return "revision_bound"

        return "weak"

    def _identity_quality_existing(self, alert: AlertRecord) -> str:
        metadata = dict(alert.alert_metadata or {})
        detector = metadata.get("detection_evidence")
        if not isinstance(detector, dict):
            legacy = metadata.get("evidence")
            detector = legacy if isinstance(legacy, dict) else {}

        raw_source_locator = detector.get("source_clause_id")
        if raw_source_locator and self._is_revision_unstable_locator(raw_source_locator):
            return "weak"

        rule_id = getattr(alert, "rule_id", None) or "unknown_rule"
        category = getattr(alert, "category", None) or ""
        affected = getattr(alert, "affected_entities", {}) or {}
        if (
            self._document_family_fingerprint(
                rule_id=rule_id,
                category=category,
                detector=detector,
                affected_entities=affected,
            )
            is not None
        ):
            return "strong"

        non_document_entities = self._flatten_entities(
            {key: value for key, value in affected.items() if key != "documents"}
        )
        if non_document_entities:
            return "strong"

        if (
            getattr(alert, "source_clause_id", None)
            or getattr(alert, "related_clause_ids", None)
            or raw_source_locator
        ):
            return "revision_bound"

        return "weak"

    def _requires_human_review(self, violation: AlertCreate) -> bool:
        if violation.severity in {AlertSeverity.CRITICAL, AlertSeverity.HIGH}:
            return True
        rule_id = (violation.rule_id or "").lower()
        return "penal" in rule_id or "penalty" in rule_id

    def finding_key(self, violation: AlertCreate) -> str:
        """Return the canonical durable family key for one Coherence finding."""
        return self._fingerprint(violation)

    def _fingerprint(self, violation: AlertCreate) -> str:
        rule_id = violation.rule_id or "unknown_rule"
        metadata = dict(violation.alert_metadata or {})
        detector = metadata.get("detection_evidence")
        if not isinstance(detector, dict):
            detector = {}

        raw_source_locator = detector.get("source_clause_id")
        if raw_source_locator and self._is_revision_unstable_locator(raw_source_locator):
            return self._synthetic_fallback_fingerprint(rule_id, detector)

        family = self._document_family_fingerprint(
            rule_id=rule_id,
            category=violation.category or "",
            detector=detector,
            affected_entities=violation.affected_entities,
        )
        if family is not None:
            return family

        non_document_entities = self._flatten_entities(
            {
                key: value
                for key, value in (violation.affected_entities or {}).items()
                if key != "documents"
            }
        )
        if non_document_entities:
            base = (
                f"{rule_id}|entities|{violation.category or ''}|"
                + "|".join(sorted(set(non_document_entities)))
            )
            return hashlib.sha256(base.encode("utf-8")).hexdigest()

        anchors: list[str] = []
        if violation.source_clause_id:
            anchors.append(str(violation.source_clause_id))
        if violation.related_clause_ids:
            anchors.extend(str(clause_id) for clause_id in violation.related_clause_ids)
        if raw_source_locator and not anchors:
            anchors.append(str(raw_source_locator))
        if anchors:
            # No stable document/business anchor is available. Keep the family
            # revision-bound rather than guessing cross-revision continuity.
            base = f"{rule_id}|revision_anchors|" + "|".join(sorted(set(anchors)))
            return hashlib.sha256(base.encode("utf-8")).hexdigest()

        claim = self._normalized_identity_text(detector.get("claim"))
        quote = self._normalized_identity_text(detector.get("quote"))
        base = f"{rule_id}|fallback|{violation.category or ''}|{claim}|{quote}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _document_family_fingerprint(
        self,
        *,
        rule_id: str,
        category: str,
        detector: dict[str, Any],
        affected_entities: dict[str, Any],
    ) -> str | None:
        """Stable family identity when document + semantic claim are available.

        Exact clause/revision IDs belong to observation identity. A document
        anchor alone is not enough when the same rule may fire multiple times,
        so claim (or quote fallback) disambiguates the semantic family.
        """
        documents: set[str] = set()
        detector_document = detector.get("source_document_id")
        if detector_document:
            documents.add(str(detector_document))
        raw_documents = affected_entities.get("documents")
        if isinstance(raw_documents, list):
            documents.update(str(value) for value in raw_documents if value)
        elif raw_documents:
            documents.add(str(raw_documents))

        if not documents:
            return None

        claim = self._normalized_identity_text(detector.get("claim"))
        quote = self._normalized_identity_text(detector.get("quote"))
        if not claim and not quote:
            return None

        # Conservative weak semantic anchor: when both are available require
        # both to remain stable. Losing continuity is safer than collapsing
        # distinct same-rule findings in one document.
        semantic_anchor = f"claim={claim}|quote={quote}"
        base = (
            f"{rule_id}|documents|{category}|"
            + "|".join(sorted(documents))
            + f"|{semantic_anchor}"
        )
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_revision_unstable_locator(value: object) -> bool:
        """True for synthetic locators that are not bound to one durable revision."""

        text = str(value or "")
        return bool(
            _POSITIONAL_RAG_LOCATOR.fullmatch(text)
            or _PARSED_TEXT_LOCATOR.fullmatch(text)
        )

    @staticmethod
    def _synthetic_locator_document_token(value: object) -> str:
        """Recover the stable document token embedded in legacy synthetic locators."""

        text = str(value or "")
        for pattern in (_POSITIONAL_RAG_LOCATOR, _PARSED_TEXT_LOCATOR):
            match = pattern.fullmatch(text)
            if match:
                return match.group(1).lower()
        return ""

    def _synthetic_fallback_fingerprint(
        self, rule_id: str, detector: dict[str, Any]
    ) -> str:
        """Identity fallback for revision-unstable parsed/RAG locators.

        Query position is excluded. The embedded document token keeps legacy
        rows compatible even when they predate source_document_id. Claim/quote
        remain part of identity so a later document revision cannot inherit an
        old human disposition merely because it reused the same synthetic locator.
        """

        document_token = self._synthetic_locator_document_token(
            detector.get("source_clause_id")
        )
        if not document_token:
            document_id = self._normalized_identity_text(
                detector.get("source_document_id")
            )
            document_token = document_id[:8].lower()
        claim = self._normalized_identity_text(detector.get("claim"))
        quote = self._normalized_identity_text(detector.get("quote"))
        base = f"{rule_id}|synthetic|{document_token}|{claim}|{quote}"
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

