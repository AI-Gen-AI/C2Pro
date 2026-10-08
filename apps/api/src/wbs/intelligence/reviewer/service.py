"""WBS Reviewer application service -- OFFLINE ONLY (PC-2b.4 #923, PC2B4_OFFLINE_ONLY).

One explicit human request reviews ONE exact target:

* ``IMPORT_REVIEW`` -- a human-created DRAFT candidate from an immutable WBS import;
* ``DRAFT`` -- any existing governed DRAFT candidate;
* ``REVIEW_OPTIMIZE`` -- the project's current approved Baseline #N.

The review binds tenant, project, target kind and id, the exact tree digest, the candidate revision
and its base baseline, the profile pins and the evidence manifest digest; it is opened, completed,
failed or cancelled ONLY through the existing PC-2b.2 intelligence store (no second store, terminal
runs frozen, items immutable). It never creates or edits a change set, never submits, approves or
applies anything and never creates a baseline: proposals wait for the human decision loop.

Live model execution is BLOCKED: the service refuses any non-synthetic adapter before anything else.
Provenance of a run made with the synthetic adapter says so (``synthetic: true``,
``production_invocation: false``); usage is attributed to tenant, project and run in an append-only
``wbs.intelligence.run_usage`` project event that carries counts only -- never evidence, prompts or
model output, which are not logged either.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Final
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tenants.types import require_tenant_id
from src.wbs.adapters.persistence.governance_models import WBSChangeSetORM
from src.wbs.adapters.persistence.governance_repository import Actor
from src.wbs.adapters.persistence.import_models import WBSImportSourceORM
from src.wbs.adapters.persistence.intelligence_models import WBSIntelligenceRunORM
from src.wbs.domain.governance import ChangeSetStatus, EntryMode, can_author
from src.wbs.intelligence.application.service import (
    WBSIntelligenceForbiddenError,
    WBSIntelligenceInvalidError,
    WBSIntelligenceNotFoundError,
    WBSIntelligenceService,
    WBSIntelligenceStateError,
    _baseline_snapshot,
    _candidate_snapshot,
    _resolve_profiles,
)
from src.wbs.intelligence.contracts.evidence import EvidenceManifest
from src.wbs.intelligence.contracts.proposal import PROPOSAL_CONTRACT_VERSION
from src.wbs.intelligence.contracts.qualification import QUALIFICATION_VOCAB_VERSION
from src.wbs.intelligence.contracts.run import (
    ExecutionType,
    IntelligenceMode,
    RunScope,
    RunStatus,
    RunTarget,
    TargetKind,
    idempotency_key,
)
from src.wbs.intelligence.reviewer.evidence import (
    Anonymizer,
    EvidenceRequest,
    ImportStructure,
    ManifestScopedChunkReader,
    build_manifest,
    default_anonymizer,
    inventory_evidence,
)
from src.wbs.intelligence.reviewer.limits import ReviewLimits
from src.wbs.intelligence.reviewer.model_port import WBSReviewerModelPort, require_offline_adapter
from src.wbs.intelligence.reviewer.pipeline import (
    ORCHESTRATION_VERSION,
    PipelineResult,
    PipelineStatus,
    ReviewInputs,
    run_review_pipeline,
)
from src.wbs.intelligence.reviewer.prompts import template_refs
from src.wbs.intelligence.validation.simulation import TargetSnapshot

logger = structlog.get_logger()

EVENT_RUN_USAGE: Final = "wbs.intelligence.run_usage"


class ReviewTargetKind(StrEnum):
    IMPORT_REVIEW = "IMPORT_REVIEW"
    DRAFT = "DRAFT"
    REVIEW_OPTIMIZE = "REVIEW_OPTIMIZE"


@dataclass(frozen=True)
class ReviewResult:
    run: WBSIntelligenceRunORM
    reused: bool
    manifest: EvidenceManifest
    pipeline: PipelineResult | None  # None when an equivalent run was reused (no model call)


@dataclass(frozen=True)
class _Target:
    mode: IntelligenceMode
    run_target: RunTarget
    snapshot: TargetSnapshot
    pins: list[dict[str, Any]]
    import_source_id: UUID | None


def _import_outline(snapshot: dict[str, Any]) -> str:
    rows = sorted(snapshot.get("rows", []), key=lambda r: int(r.get("source_ordinal", 0)))
    return "\n".join(" ".join(part for part in (str(r.get("raw_code") or r.get("normalized_code") or ""),
                                                str(r.get("name") or "")) if part) for r in rows)


class WBSReviewerService:
    """The offline Reviewer over one transactional session (the caller commits)."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        model: WBSReviewerModelPort,
        anonymize: Anonymizer | None = None,
        limits: ReviewLimits | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        require_offline_adapter(model)
        self.session = session
        self.model = model
        self.anonymize = anonymize or default_anonymizer
        self.limits = limits or ReviewLimits()
        self.clock = clock
        self.store = WBSIntelligenceService(session)

    # ------------------------------------------------------------------ target capture
    async def _capture(self, *, scope: RunScope, target: ReviewTargetKind, change_set_id: UUID | None,
                       baseline_id: UUID | None) -> _Target:
        store = self.store
        if target in (ReviewTargetKind.IMPORT_REVIEW, ReviewTargetKind.DRAFT):
            if change_set_id is None or baseline_id is not None:
                raise WBSIntelligenceInvalidError("a candidate review names exactly its change set")
            # FOR SHARE until commit: the revision and the nodes this review binds are one consistent state
            change_set: WBSChangeSetORM = await store._change_set(change_set_id, scope.project_id, scope.tenant_id,
                                                                  share=True)
            if change_set.status != ChangeSetStatus.DRAFT.value:
                raise WBSIntelligenceStateError(f"only a DRAFT candidate is reviewed (this one is {change_set.status})",
                                                code="WBS_INTELLIGENCE_TARGET_NOT_DRAFT", status=change_set.status)
            if target is ReviewTargetKind.IMPORT_REVIEW and (
                    change_set.entry_mode != EntryMode.IMPORT_REVIEW.value or change_set.source_import_id is None):
                raise WBSIntelligenceStateError("the change set is not an IMPORT_REVIEW candidate from a WBS import",
                                                code="WBS_REVIEWER_NOT_IMPORT_REVIEW")
            snapshot = _candidate_snapshot(scope.project_id, await store._candidate_nodes(change_set))
            run_target = RunTarget(kind=TargetKind.CANDIDATE, target_id=change_set.id, digest=snapshot.digest,
                                   change_set_revision=change_set.revision,
                                   base_baseline_id=change_set.base_baseline_id)
            mode = (IntelligenceMode.IMPORT_REVIEW if target is ReviewTargetKind.IMPORT_REVIEW
                    else IntelligenceMode.REVIEW_OPTIMIZE)
            import_id = change_set.source_import_id if target is ReviewTargetKind.IMPORT_REVIEW else None
            return _Target(mode, run_target, snapshot, list(change_set.profile_refs or []), import_id)
        if baseline_id is None or change_set_id is not None:
            raise WBSIntelligenceInvalidError("a baseline review names exactly its baseline")
        current = await store.repo.current_baseline(scope.project_id, scope.tenant_id)
        if current is None or current.id != baseline_id:
            raise WBSIntelligenceStateError("only the project's current baseline is reviewed",
                                            code="WBS_INTELLIGENCE_TARGET_NOT_CURRENT")
        snapshot = _baseline_snapshot(scope.project_id, await store._baseline_nodes(current))
        run_target = RunTarget(kind=TargetKind.BASELINE, target_id=current.id, digest=current.tree_digest,
                               base_baseline_id=current.parent_baseline_id)
        return _Target(IntelligenceMode.REVIEW_OPTIMIZE, run_target, snapshot, list(current.profile_refs or []), None)

    async def _import_structure(self, scope: RunScope, import_id: UUID | None) -> ImportStructure | None:
        if import_id is None:
            return None
        source = await self.session.scalar(select(WBSImportSourceORM).where(
            WBSImportSourceORM.id == import_id, WBSImportSourceORM.tenant_id == scope.tenant_id,
            WBSImportSourceORM.project_id == scope.project_id))
        if source is None:
            raise WBSIntelligenceNotFoundError("WBS import", import_id)
        return ImportStructure(document_id=source.document_id, revision_id=source.revision_id,
                               blob_hash=source.blob_hash, outline=_import_outline(source.snapshot or {}))

    # ------------------------------------------------------------------ review
    async def review(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        target: ReviewTargetKind,
        change_set_id: UUID | None = None,
        baseline_id: UUID | None = None,
        evidence: EvidenceRequest | None = None,
        rerun: bool = False,
        cancelled: Callable[[], bool] | None = None,
    ) -> ReviewResult:
        require_offline_adapter(self.model)
        if not can_author(actor.kind, actor.role):
            raise WBSIntelligenceForbiddenError("only a human user or admin can request a WBS review "
                                                "(never AI, api or a service)")
        tenant_id = require_tenant_id(tenant_id)
        await self.store._require_project(project_id, tenant_id)
        scope = RunScope(tenant_id=tenant_id, project_id=project_id)
        request = evidence or EvidenceRequest()
        captured = await self._capture(scope=scope, target=target, change_set_id=change_set_id,
                                       baseline_id=baseline_id)
        profiles = _resolve_profiles(captured.pins)
        inventory = await inventory_evidence(self.session, scope=scope, request=request)
        chunks = await ManifestScopedChunkReader(self.session).read(
            tenant_id=tenant_id, project_id=project_id,
            allowed=[(s.document_id, s.revision_id) for s in inventory.sources],
            per_document=self.limits.max_excerpts_per_document, total=self.limits.max_excerpts)
        manifest = build_manifest(scope=scope, inventory=inventory, chunks=chunks, anonymize=self.anonymize,
                                  limits=self.limits,
                                  import_structure=await self._import_structure(scope, captured.import_source_id),
                                  user_context=request.user_context)
        fingerprint = self.model.fingerprint
        templates = template_refs()
        nonce = uuid4().hex if rerun else None
        key = idempotency_key(scope=scope, mode=captured.mode, target=captured.run_target,
                              evidence_set_digest=manifest.evidence_set_digest,
                              profile_digests=[pin["profile_digest"] for pin in profiles.pins()],
                              prompt_templates=templates, model=fingerprint,
                              orchestration_version=ORCHESTRATION_VERSION, rerun_nonce=nonce)
        provenance = {
            "synthetic": True, "production_invocation": False, "adapter": type(self.model).__name__,
            "provider": fingerprint.provider, "model": fingerprint.model, "routing_tier": fingerprint.routing_tier,
            "temperature_milli": fingerprint.temperature_milli, "max_tokens": fingerprint.max_tokens,
            "prompt_templates": [t.model_dump() for t in templates], "orchestration_version": ORCHESTRATION_VERSION,
            "proposal_contract_version": PROPOSAL_CONTRACT_VERSION,
            "qualification_vocab_version": QUALIFICATION_VOCAB_VERSION, "limits": asdict(self.limits),
        }
        opened = await self.store.open_run(
            scope=scope, mode=captured.mode, execution_type=ExecutionType.AI, target=captured.run_target,
            evidence_set_digest=manifest.evidence_set_digest, profile_refs=profiles.pins(),
            orchestration_version=ORCHESTRATION_VERSION, key=key, requested_by=actor.user_id, rerun_nonce=nonce,
            model_provenance=provenance)
        if opened.reused:
            return ReviewResult(run=opened.run, reused=True, manifest=manifest, pipeline=None)
        run = opened.run

        async def is_cancelled() -> bool:
            if cancelled is not None and cancelled():
                return True
            status = await self.session.scalar(select(WBSIntelligenceRunORM.status).where(
                WBSIntelligenceRunORM.id == run.id, WBSIntelligenceRunORM.tenant_id == tenant_id,
                WBSIntelligenceRunORM.project_id == project_id).execution_options(populate_existing=True))
            return status == RunStatus.CANCELLED.value

        inputs = ReviewInputs(scope=scope, mode=captured.mode, target=captured.snapshot, manifest=manifest,
                              profiles=profiles, has_trusted_contract=inventory.has_trusted_contract,
                              has_trusted_scope_evidence=inventory.has_trusted_scope_evidence, run_id=run.id,
                              limits=self.limits)
        result = await run_review_pipeline(inputs, self.model, cancelled=is_cancelled, clock=self.clock)
        actor_ref = f"user:{actor.user_id}"
        if result.status is PipelineStatus.COMPLETED:
            assert result.outcome is not None and result.qualification is not None
            run = await self.store.complete_run(run, outcome=result.outcome, qualification=result.qualification,
                                                findings=result.findings, proposals=result.proposals,
                                                finding_refs=result.finding_refs, actor=actor_ref)
        elif result.status is PipelineStatus.FAILED:
            run = await self.store.fail_run(run, reason=result.failure_reason or "the review failed", actor=actor_ref)
        else:
            run = await self.store.cancel_run(project_id=project_id, run_id=run.id, tenant_id=tenant_id, actor=actor)
        await self._usage_event(run, result, actor_ref)
        logger.info("wbs_review_finished", run_id=str(run.id), status=run.status, outcome=run.outcome,
                    calls=result.usage.calls, synthetic=True)
        return ReviewResult(run=run, reused=False, manifest=manifest, pipeline=result)

    async def _usage_event(self, run: WBSIntelligenceRunORM, result: PipelineResult, actor: str) -> None:
        """Usage attributed to tenant, project and run -- counts only, never content."""
        usage = result.usage
        await self.store._event(
            project_id=run.project_id, tenant_id=run.tenant_id, event_type=EVENT_RUN_USAGE, actor=actor,
            payload={
                "tenant_id": str(run.tenant_id), "project_id": str(run.project_id), "run_id": str(run.id),
                "synthetic": True, "external_calls": 0, "provider": self.model.fingerprint.provider,
                "status": run.status, "outcome": run.outcome, "calls": usage.calls, "retries": usage.retries,
                "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                "cost_micro_usd": usage.cost_micro_usd, "elapsed_ms": usage.elapsed_ms,
                "stop_reason": None if result.stop_reason is None else result.stop_reason.value,
                "per_call": [{"call_index": c.call_index, "task": c.task.value, "cluster_id": c.cluster_id,
                              "attempt": c.attempt, "status": c.status, "input_tokens": c.input_tokens,
                              "output_tokens": c.output_tokens, "cost_micro_usd": c.cost_micro_usd}
                             for c in result.calls],
            })


__all__ = ["EVENT_RUN_USAGE", "ReviewResult", "ReviewTargetKind", "WBSReviewerService"]
