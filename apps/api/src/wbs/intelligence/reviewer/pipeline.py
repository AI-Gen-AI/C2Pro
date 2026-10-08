"""The bounded WBS review pipeline (PC-2b.4 #923, ADR-030 §A17) -- a workflow, never an agent.

Pure and offline: no database, no network, no provider. Given the exact target, the run's evidence
manifest (anonymised model-visible excerpts with canonical locators captured before anonymisation),
the pinned profiles and the evidence summary, it:

1. qualifies the target deterministically (PC-2b.2 engine);
2. applies the sufficiency gate -- without trusted scope evidence the run ABSTAINS
   (INSUFFICIENT_EVIDENCE) with ZERO model calls and honest NOT_EVALUATED reasons;
3. partitions the target into bounded clusters;
4. MAP: one model call per cluster for findings and proposals of THAT cluster only;
5. merges and de-duplicates the MAP items deterministically;
6. REDUCE: one model call for the tree-level qualification of the 19 dimensions;
7. validates the assembled envelope with the PC-2b.1 validator (strict schema, manifest-only
   evidence, deterministic quote verification, availability matrix, invented-id refusal,
   simulated application) -- nothing is repaired;
8. reconciles with the deterministic qualification: AI evidence may add severity, it never softens a
   deterministic finding and never moves an unavailable dimension off NOT_EVALUATED.

Every call is admitted by the ``CallBudget`` (calls incl. retries, tokens, cost, time) and the
cancellation check BEFORE it starts. Untrusted text travels only inside per-call isolation
boundaries; the model has no tools. Isolation is not anonymisation: the target's free text (node
names and codes) and the MAP summaries forwarded into REDUCE pass the same privacy boundary as the
evidence excerpts before any model-port call, while canonical node ids stay intact for deterministic
validation and the target itself is never mutated. The result is persisted by the caller through the
PC-2b.2 store.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final
from uuid import UUID, uuid4

from src.core.ai.structured_output import LLMSchemaError, parse_llm_json
from src.core.ai.untrusted_content import UntrustedBlock, UntrustedContentIsolation
from src.wbs.intelligence.contracts.evidence import EvidenceManifest, InputClass
from src.wbs.intelligence.contracts.proposal import (
    LOCAL_LABEL,
    PROPOSAL_CONTRACT_VERSION,
    ModelResponseEnvelope,
    ProposalItem,
)
from src.wbs.intelligence.contracts.qualification import (
    NOT_EVALUATED_SUMMARY,
    AvailabilityContext,
    DimensionResult,
    NodeFinding,
    NotEvaluatedReason,
    QualificationDimension,
    QualificationMethod,
    QualificationReport,
    QualificationStatus,
    availability,
)
from src.wbs.intelligence.contracts.run import IntelligenceMode, RunOutcome, RunScope
from src.wbs.intelligence.profiles.catalog import ResolvedProfileSet
from src.wbs.intelligence.qualification.deterministic import QualifierNode, qualify
from src.wbs.intelligence.reviewer.clusters import Cluster, partition
from src.wbs.intelligence.reviewer.limits import (
    CHARS_PER_TOKEN,
    EXCERPT_OVERHEAD_CHARS,
    CallBudget,
    ReviewLimits,
    StopReason,
    estimate_tokens,
)
from src.wbs.intelligence.reviewer.model_port import (
    ModelCallRequest,
    ModelTransientError,
    ReviewTask,
    WBSReviewerModelPort,
    require_offline_adapter,
)
from src.wbs.intelligence.reviewer.privacy import Anonymizer, default_anonymizer
from src.wbs.intelligence.reviewer.prompts import template_ref, template_text
from src.wbs.intelligence.validation.output_validator import (
    ValidationContext,
    ValidationReport,
    validate_model_output,
)
from src.wbs.intelligence.validation.simulation import TargetSnapshot

ORCHESTRATION_VERSION: Final = "wbs-ai-reviewer/v1"
REVIEW_MODES: Final = frozenset({IntelligenceMode.IMPORT_REVIEW, IntelligenceMode.REVIEW_OPTIMIZE})
_LABEL = re.compile(LOCAL_LABEL)
_SEVERITY: Final = {QualificationStatus.SUPPORTED: 0, QualificationStatus.AMBIGUOUS: 1,
                    QualificationStatus.WARNING: 2, QualificationStatus.GAP: 3}
_BLOCK_KIND: Final = {
    InputClass.TRUSTED_PROJECT_EVIDENCE: "trusted_evidence",
    InputClass.PROPOSED_EVIDENCE: "proposed_evidence",
    InputClass.ADVISORY_EVIDENCE: "advisory_evidence",
    InputClass.HUMAN_PROVIDED_IMPORT: "imported_structure",
    InputClass.CURRENT_APPROVED_WBS: "approved_wbs",
    InputClass.USER_CONTEXT: "user_context",
}

Cancelled = Callable[[], bool | Awaitable[bool]]

# Per-call input budget (characters): every MAP and the REDUCE fit by construction. Evidence takes
# ``EVIDENCE_SHARE`` (limits.py), the target outline 25%, REDUCE's MAP summaries 15%; the rest is the
# template, the isolation preamble and markers.
_OUTLINE_SHARE: Final = 0.25
_SUMMARY_SHARE: Final = 0.15
_NAME_CHARS: Final = 200
_CODE_CHARS: Final = 64
_SUMMARY_CHARS: Final = 300
_SAFE_FAILURE = re.compile(r"^(\d+ of \d+ items refused \(over \d+%\)|a dimension or item ref appears twice)$")


def _safe_failure(message: str | None) -> str:
    """A persisted failure reason never carries model text: only known, content-free messages pass."""
    return message if message and _SAFE_FAILURE.match(message) else "the assembled review failed validation"


class PipelineStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ReviewInputs:
    scope: RunScope
    mode: IntelligenceMode
    target: TargetSnapshot
    manifest: EvidenceManifest
    profiles: ResolvedProfileSet
    has_trusted_contract: bool
    has_trusted_scope_evidence: bool
    run_id: UUID
    limits: ReviewLimits = field(default_factory=ReviewLimits)
    anonymize: Anonymizer = default_anonymizer  # the privacy boundary of every model-visible text


@dataclass(frozen=True)
class CallRecord:
    call_index: int
    task: ReviewTask
    cluster_id: str | None
    attempt: int
    status: str  # OK / TRANSIENT_ERROR / PERMANENT_ERROR / OVER_LIMIT / INPUT_TOO_LARGE
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micro_usd: int = 0


@dataclass(frozen=True)
class UsageSummary:
    calls: int
    retries: int
    input_tokens: int
    output_tokens: int
    cost_micro_usd: int
    elapsed_ms: int


@dataclass(frozen=True)
class PipelineResult:
    status: PipelineStatus
    outcome: RunOutcome | None
    qualification: QualificationReport | None
    findings: tuple[NodeFinding, ...]
    proposals: tuple[ProposalItem, ...]
    finding_refs: Mapping[UUID, str]
    uncovered: tuple[str, ...]
    report: ValidationReport
    calls: tuple[CallRecord, ...]
    usage: UsageSummary
    stop_reason: StopReason | None
    failure_reason: str | None
    availability: AvailabilityContext


# ============================================================================ reconciliation
def _ai_not_evaluated(dim: QualificationDimension, reason: NotEvaluatedReason) -> DimensionResult:
    return DimensionResult(dimension=dim, status=QualificationStatus.NOT_EVALUATED, method=QualificationMethod.AI,
                           summary=NOT_EVALUATED_SUMMARY[reason], reason_code=reason)


def reconcile_qualification(deterministic: QualificationReport, ai: QualificationReport,
                            ctx: AvailabilityContext) -> QualificationReport:
    """One result per dimension: AI may add severity; it never softens a deterministic result."""
    matrix = availability(ctx)
    results = []
    for dim in QualificationDimension:
        det, model = deterministic.get(dim), ai.get(dim)
        reason = matrix[dim]
        if reason is not None:  # unavailable in THIS run: never evaluated, whatever anyone claims
            chosen = model if model.status is QualificationStatus.NOT_EVALUATED else _ai_not_evaluated(dim, reason)
        elif det.status is QualificationStatus.NOT_EVALUATED:
            chosen = model
        elif model.status is QualificationStatus.NOT_EVALUATED:
            chosen = det
        else:
            chosen = model if _SEVERITY[model.status] > _SEVERITY[det.status] else det
        results.append(chosen)
    return QualificationReport(results=tuple(results))


def _abstention_report(ctx: AvailabilityContext) -> QualificationReport:
    matrix = availability(ctx)
    return QualificationReport(results=tuple(
        _ai_not_evaluated(dim, matrix[dim] or NotEvaluatedReason.INSUFFICIENT_EVIDENCE) for dim in QualificationDimension))


# ============================================================================ map item handling
class _OutOfBounds(ValueError):
    pass


def _prefixed(cluster_id: str, value: str) -> str:
    result = f"{cluster_id}-{value}"
    if not _LABEL.fullmatch(result):
        raise _OutOfBounds(f"{value!r} cannot be namespaced to {cluster_id}")
    return result


def _prefix_ref(ref: Any, cluster_id: str) -> Any:
    if isinstance(ref, dict) and ref.get("label") is not None:
        return {**ref, "label": _prefixed(cluster_id, ref["label"])}
    return ref


def _node_refs(item: Mapping[str, Any]) -> list[str]:
    refs = [r for r in (item.get("node"), item.get("parent")) if isinstance(r, dict)]
    refs += [r for r in item.get("sources", []) if isinstance(r, dict)]
    ids = [str(r["node_id"]) for r in refs if r.get("node_id") is not None]
    return ids + [key for key in item.get("child_targets", {}) if not str(key).startswith("label:")]


def _namespace_proposal(item: dict[str, Any], cluster_id: str) -> dict[str, Any]:
    item = dict(item)
    item["ref"] = _prefixed(cluster_id, item["ref"])
    if item.get("creates_label"):
        item["creates_label"] = _prefixed(cluster_id, item["creates_label"])
    for name in ("node", "parent"):
        if name in item:
            item[name] = _prefix_ref(item[name], cluster_id)
    if "sources" in item:
        item["sources"] = [_prefix_ref(ref, cluster_id) for ref in item["sources"]]
    if "split_targets" in item:
        item["split_targets"] = [{**t, "label": _prefixed(cluster_id, t["label"])} for t in item["split_targets"]]
    if "child_targets" in item:
        item["child_targets"] = {
            (f"label:{_prefixed(cluster_id, key.removeprefix('label:'))}" if key.startswith("label:") else key): value
            for key, value in item["child_targets"].items()}
    if "depends_on" in item:
        item["depends_on"] = [_prefixed(cluster_id, ref) for ref in item["depends_on"]]
    if "addresses_findings" in item:
        item["addresses_findings"] = [_prefixed(cluster_id, ref) for ref in item["addresses_findings"]]
    return item


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split()).casefold()


# ============================================================================ the run
class _Review:
    def __init__(self, inputs: ReviewInputs, model: WBSReviewerModelPort, cancelled: Cancelled | None,
                 clock: Callable[[], float], isolation: UntrustedContentIsolation, mint: Callable[[], UUID]) -> None:
        self.inputs, self.model, self._cancelled, self.isolation, self.mint = inputs, model, cancelled, isolation, mint
        self.limits = inputs.limits
        self.budget = CallBudget(self.limits, clock)
        self.records: list[CallRecord] = []
        self.report = ValidationReport()
        self.stop: StopReason | None = None
        self.pre_rejected: set[str] = set()  # refs refused before validation (they count toward the ratio)
        self.map_items_total = 0
        self.shown = self._select_evidence()  # the excerpts every call carries (bounded per call)
        # citations, availability and the deterministic evidence count use ONLY what the model was shown
        self.visible = EvidenceManifest(tenant_id=inputs.manifest.tenant_id, project_id=inputs.manifest.project_id,
                                        items=tuple(self.shown))
        trusted = [i for i in self.shown if i.input_class is InputClass.TRUSTED_PROJECT_EVIDENCE]
        has_scope = inputs.has_trusted_scope_evidence and bool(trusted)
        self.ctx = AvailabilityContext(has_trusted_contract=inputs.has_trusted_contract and has_scope,
                                       has_trusted_scope_evidence=has_scope, ai_qualification_run=True,
                                       target_is_empty=not inputs.target.nodes)
        self.deterministic = qualify(
            [QualifierNode(node_id=n.node_id, parent_id=n.parent_id, sort_order=n.sort_order, code=n.code, name=n.name,
                           decomposition_kind=n.decomposition_kind, control_level=n.control_level,
                           dictionary=n.dictionary) for n in inputs.target.nodes],
            profiles=inputs.profiles, evidence_ref_count=len(trusted), mint=mint)

    # ------------------------------------------------------------------ results
    def _usage(self) -> UsageSummary:
        b = self.budget
        return UsageSummary(calls=b.calls, retries=b.retries, input_tokens=b.input_tokens, output_tokens=b.output_tokens,
                            cost_micro_usd=b.cost_micro_usd, elapsed_ms=b.elapsed_ms)

    def _result(self, status: PipelineStatus, *, outcome: RunOutcome | None = None,
                qualification: QualificationReport | None = None, findings: Sequence[NodeFinding] = (),
                proposals: Sequence[ProposalItem] = (), finding_refs: Mapping[UUID, str] | None = None,
                uncovered: Sequence[str] = (), failure: str | None = None) -> PipelineResult:
        return PipelineResult(status=status, outcome=outcome, qualification=qualification, findings=tuple(findings),
                              proposals=tuple(proposals), finding_refs=dict(finding_refs or {}),
                              uncovered=tuple(uncovered), report=self.report, calls=tuple(self.records),
                              usage=self._usage(), stop_reason=self.stop, failure_reason=failure,
                              availability=self.ctx)

    def _failed(self, reason: str) -> PipelineResult:
        return self._result(PipelineStatus.FAILED, outcome=RunOutcome.FAILED, failure=reason[:2000])

    def _cancelled_result(self) -> PipelineResult:
        self.stop = StopReason.CANCELLED
        return self._result(PipelineStatus.CANCELLED, outcome=RunOutcome.CANCELLED)

    async def _is_cancelled(self) -> bool:
        if self._cancelled is None:
            return False
        value = self._cancelled()
        if inspect.isawaitable(value):
            value = await value
        return bool(value)

    # ------------------------------------------------------------------ prompts (bounded per call)
    def _chars(self, share: float) -> int:
        return int(self.limits.max_input_tokens_per_call * CHARS_PER_TOKEN * share)

    def _select_evidence(self) -> list[Any]:
        """Excerpts in manifest (class-priority) order while they fit the per-call evidence budget."""
        budget, used, shown = self.limits.evidence_chars, 0, []
        for item in self.inputs.manifest.items:
            size = len(item.model_visible.text) + EXCERPT_OVERHEAD_CHARS
            if used + size > budget:
                continue
            used += size
            shown.append(item)
        omitted = len(self.inputs.manifest.items) - len(shown)
        if omitted:
            self.report.coerced.append(("evidence", f"{omitted} excerpt(s) beyond the per-call evidence budget"))
        return shown

    def _evidence_blocks(self) -> list[UntrustedBlock]:
        return [UntrustedBlock(block_id=item.excerpt_id, kind=_BLOCK_KIND[item.input_class],
                               text=item.model_visible.text) for item in self.shown]

    def _private(self, value: str | None, cap: int) -> str | None:
        return None if value is None else self.inputs.anonymize(value)[:cap]

    def _outline(self, node_ids: Sequence[UUID]) -> tuple[str, int]:
        """The target as the model sees it (a copy): ids verbatim, free text anonymised and capped, the
        whole outline bounded by the per-call outline budget (omitted nodes are counted, never hidden)."""
        by_id = {n.node_id: n for n in self.inputs.target.nodes}
        budget, used, lines = self._chars(_OUTLINE_SHARE), 0, []
        for node_id in node_ids:
            node = by_id[node_id]
            line = json.dumps({
                "node_id": str(node.node_id), "parent_id": None if node.parent_id is None else str(node.parent_id),
                "code": self._private(node.code, _CODE_CHARS), "name": self._private(node.name, _NAME_CHARS),
                "decomposition_kind": self._private(node.decomposition_kind, _CODE_CHARS),
                "control_level": node.control_level}, ensure_ascii=False)
            if used + len(line) + 1 > budget:
                break
            used += len(line) + 1
            lines.append(line)
        omitted = len(node_ids) - len(lines)
        if omitted:
            lines.append(json.dumps({"omitted_nodes": omitted}))
        return "\n".join(lines), omitted

    def _summaries(self, merged: Sequence[Mapping[str, Any]]) -> tuple[str, int]:
        budget, used, summary = self._chars(_SUMMARY_SHARE), 2, []
        for f in merged:
            entry = {"ref": f["ref"], "dimension": f["dimension"], "status": f["status"],
                     "summary": self._private(f["summary"], _SUMMARY_CHARS), "node_ids": f.get("node_ids", [])}
            size = len(json.dumps(entry, ensure_ascii=False)) + 1
            if used + size > budget:
                break
            used += size
            summary.append(entry)
        omitted = len(merged) - len(summary)
        if omitted:
            summary.append({"omitted_findings": omitted})
        return json.dumps(summary, ensure_ascii=False), omitted

    def _prompt(self, task: ReviewTask, cluster: Cluster | None, merged: Sequence[Mapping[str, Any]]
                ) -> tuple[str, str]:
        blocks = self._evidence_blocks()
        if cluster is not None:
            blocks.append(UntrustedBlock(block_id=f"target_{cluster.cluster_id}", kind="wbs_target",
                                         text=self._outline(cluster.node_ids)[0]))
        else:
            blocks.append(UntrustedBlock(block_id="target_all", kind="wbs_target",
                                         text=self._outline([n.node_id for n in self.inputs.target.nodes])[0]))
            blocks.append(UntrustedBlock(block_id="map_results", kind="map_results",
                                         text=self._summaries(merged)[0]))
        isolated = self.isolation.isolate(blocks)
        return f"{template_text(task)}\n\n{isolated.system_preamble}", isolated.user_content

    # ------------------------------------------------------------------ one bounded call (with retries)
    async def _call(self, task: ReviewTask, cluster: Cluster | None, *, reserve: int,
                    merged: Sequence[Mapping[str, Any]] = ()) -> tuple[str | None, StopReason | None, str]:
        """(raw response or None, stop reason or None, status of the last attempt)."""
        system, content = self._prompt(task, cluster, merged)
        estimate = estimate_tokens(system, content)
        cluster_id = None if cluster is None else cluster.cluster_id
        if estimate > self.limits.max_input_tokens_per_call:
            self.records.append(CallRecord(0, task, cluster_id, 0, "INPUT_TOO_LARGE"))  # 0: never sent
            return None, None, "INPUT_TOO_LARGE"
        status = "NOT_STARTED"
        for attempt in range(self.limits.max_retries + 1):
            if await self._is_cancelled():
                return None, StopReason.CANCELLED, status
            stop = self.budget.admit(estimate, reserve_calls=reserve)
            if stop is not None:
                return None, stop, status
            self.budget.calls += 1
            if attempt:
                self.budget.retries += 1
            request = ModelCallRequest(
                task=task, tenant_id=self.inputs.scope.tenant_id, project_id=self.inputs.scope.project_id,
                run_id=self.inputs.run_id, call_index=self.budget.calls, attempt=attempt, cluster_id=cluster_id,
                template=template_ref(task), model=self.model.fingerprint, system=system, content=content,
                excerpt_ids=tuple(item.excerpt_id for item in self.shown),
                max_input_tokens=self.limits.max_input_tokens_per_call,
                max_output_tokens=self.limits.max_output_tokens_per_call)
            try:  # a hung call is bounded by the remaining time budget
                response = await asyncio.wait_for(self.model.complete(request),
                                                  timeout=max(self.budget.remaining_ms, 1) / 1000)
            except TimeoutError:
                self.budget.charge_failed(estimate)
                if self.budget.remaining_ms > 0:  # the adapter's own timeout, not the run's: transient
                    status = "TRANSIENT_ERROR"
                    self.records.append(CallRecord(self.budget.calls, task, cluster_id, attempt, status))
                    continue
                self.records.append(CallRecord(self.budget.calls, task, cluster_id, attempt, "TIMEOUT"))
                return None, StopReason.TIME_CAP, "TIMEOUT"
            except ModelTransientError:
                self.budget.charge_failed(estimate)
                status = "TRANSIENT_ERROR"
                self.records.append(CallRecord(self.budget.calls, task, cluster_id, attempt, status))
                continue
            except Exception:  # noqa: BLE001 - any other model failure is permanent; its text is never logged
                self.budget.charge_failed(estimate)
                self.records.append(CallRecord(self.budget.calls, task, cluster_id, attempt, "PERMANENT_ERROR"))
                return None, None, "PERMANENT_ERROR"
            usage = response.usage
            within = self.budget.charge(usage)
            within = within and estimate_tokens(response.raw) <= self.limits.max_output_tokens_per_call
            status = "OK" if within else "OVER_LIMIT"
            self.records.append(CallRecord(self.budget.calls, task, cluster_id, attempt, status, usage.input_tokens,
                                           usage.output_tokens, usage.cost_micro_usd))
            return (response.raw if within else None), None, status
        return None, None, status

    # ------------------------------------------------------------------ MAP / REDUCE parsing
    def _parse(self, raw: str) -> ModelResponseEnvelope | None:
        try:
            return parse_llm_json(raw, ModelResponseEnvelope)
        except (LLMSchemaError, ValueError, RecursionError):  # malformed output never escapes the run
            return None

    def _refuse(self, ref: str, reason: str) -> None:
        self.report.rejected.append((ref, reason))
        self.pre_rejected.add(ref)

    def _map_items(self, raw: str, cluster: Cluster) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
        envelope = self._parse(raw)
        if envelope is None:
            return None
        cid, members = cluster.cluster_id, {str(n) for n in cluster.node_ids}
        if envelope.qualification:
            self.report.coerced.append((cid, "a MAP response carries no tree-level qualification: ignored"))
        self.map_items_total += len(envelope.findings) + len(envelope.proposals)
        seen: set[str] = set()
        findings, proposals = [], []
        for finding in envelope.findings:
            body = finding.model_dump(mode="json", exclude_unset=True)
            try:
                if finding.ref in seen:
                    raise _OutOfBounds("the ref appears twice in this MAP response")
                seen.add(finding.ref)
                if not {str(n) for n in finding.node_ids} <= members:
                    raise _OutOfBounds("a MAP finding names nodes outside its cluster")
                body["ref"] = _prefixed(cid, finding.ref)
            except _OutOfBounds as exc:
                self._refuse(f"{cid}-{finding.ref}", str(exc))
                continue
            findings.append(body)
        items = envelope.proposals
        if envelope.outcome == "INSUFFICIENT_EVIDENCE" and items:
            for p in items:
                self._refuse(f"{cid}-{p.ref}", "an INSUFFICIENT_EVIDENCE MAP carries no proposals")
            items = ()
        for proposal in items:
            body = proposal.model_dump(mode="json", exclude_unset=True)
            try:
                if proposal.ref in seen:
                    raise _OutOfBounds("the ref appears twice in this MAP response")
                seen.add(proposal.ref)
                if not set(_node_refs(body)) <= members:
                    raise _OutOfBounds("a MAP proposal names nodes outside its cluster")
                proposals.append(_namespace_proposal(body, cid))
            except _OutOfBounds as exc:
                self._refuse(f"{cid}-{proposal.ref}", str(exc))
        return findings, proposals

    def _reduce_claims(self, raw: str) -> list[dict[str, Any]] | None:
        envelope = self._parse(raw)
        if envelope is None:
            return None
        if envelope.findings or envelope.proposals:
            self.report.coerced.append(("reduce", "findings and proposals come from MAP calls only: ignored"))
        return [claim.model_dump(mode="json", exclude_unset=True) for claim in envelope.qualification]

    def _dedupe(self, findings: list[dict[str, Any]], proposals: list[dict[str, Any]]
                ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        seen: dict[Any, str] = {}
        unique_findings = []
        for finding in findings:
            key = (finding["dimension"], tuple(sorted(finding.get("node_ids", []))), _normal(finding["summary"]))
            if key in seen:
                self.report.rejected.append((finding["ref"], f"duplicate of {seen[key]}"))
                continue
            seen[key] = finding["ref"]
            unique_findings.append(finding)
        seen_p: dict[str, str] = {}
        unique_proposals = []
        volatile = {"ref", "rationale", "evidence", "confidence_pct", "assumptions", "ambiguity_flags",
                    "addresses_findings", "depends_on", "profile_rule_refs", "creates_label", "split_targets"}
        for proposal in proposals:
            signature = json.dumps({k: v for k, v in proposal.items() if k not in volatile}, sort_keys=True)
            if proposal.get("operation") not in {"ADD_NODE", "MERGE_NODES", "SPLIT_NODE"} and signature in seen_p:
                self.report.rejected.append((proposal["ref"], f"duplicate of {seen_p[signature]}"))
                continue
            seen_p.setdefault(signature, proposal["ref"])
            unique_proposals.append(proposal)
        return unique_findings, unique_proposals

    # ------------------------------------------------------------------ the workflow
    async def execute(self) -> PipelineResult:
        try:
            return await self._execute()
        except Exception:  # noqa: BLE001 - never escape the run: fail it, keep its usage, log no content
            return self._failed("the review pipeline raised an unexpected error")

    def _ratio_failure(self, validated_report: ValidationReport, max_pct: int) -> str | None:
        """The rejection-ratio gate over EVERY item the MAP calls returned, including pre-validation refusals."""
        refused = (self.pre_rejected | {ref for ref, _ in validated_report.rejected}
                   | {ref for ref, _ in validated_report.dropped_dependants})
        total = self.map_items_total
        if total and len(refused) * 100 > max_pct * total:
            return f"{len(refused)} of {total} items refused (over {max_pct}%)"
        return None

    async def _execute(self) -> PipelineResult:
        if not self.ctx.has_trusted_scope_evidence or self.ctx.target_is_empty:
            # sufficiency gate: abstain with zero model calls (no PASS by absence, no fabricated evidence)
            qualification = reconcile_qualification(self.deterministic.report, _abstention_report(self.ctx), self.ctx)
            return self._result(PipelineStatus.COMPLETED, outcome=RunOutcome.INSUFFICIENT_EVIDENCE,
                                qualification=qualification, findings=self.deterministic.findings)
        clusters = partition(self.inputs.target, max_nodes=self.limits.max_cluster_nodes)
        findings: list[dict[str, Any]] = []
        proposals: list[dict[str, Any]] = []
        uncovered: list[str] = []
        covered = failed = 0
        for cluster in clusters:
            if self.stop is not None:
                uncovered.append(cluster.cluster_id)
                continue
            raw, stop, _ = await self._call(ReviewTask.MAP, cluster, reserve=1)
            if stop is StopReason.CANCELLED:
                return self._cancelled_result()
            if stop is not None:
                self.stop = stop
                uncovered.append(cluster.cluster_id)
                continue
            parsed = None if raw is None else self._map_items(raw, cluster)
            if parsed is None:
                failed += 1
                uncovered.append(cluster.cluster_id)
                continue
            covered += 1
            findings += parsed[0]
            proposals += parsed[1]
            if self._outline(cluster.node_ids)[1]:  # the model saw part of this cluster: never COMPLETE
                uncovered.append(cluster.cluster_id)
        if covered == 0 and failed:
            return self._failed("no MAP call produced a valid response")
        findings, proposals = self._dedupe(findings, proposals)

        if await self._is_cancelled():
            return self._cancelled_result()
        if len(self.shown) < len(self.inputs.manifest.items):
            uncovered.append("evidence")  # some excerpts were never shown: no tree-level pass by absence
        claims: list[dict[str, Any]] | None = None
        omitted_nodes = self._outline([n.node_id for n in self.inputs.target.nodes])[1]
        if omitted_nodes:  # a tree-level qualification over part of the tree would be a pass by absence
            self.report.coerced.append(("reduce", f"{omitted_nodes} node(s) beyond one call's outline budget: "
                                                  "tree-level qualification not run"))
            raw, stop, status = None, None, "OUTLINE_TOO_LARGE"
        else:
            if self._summaries(findings)[1]:
                uncovered.append("map_results")
            raw, stop, status = await self._call(ReviewTask.REDUCE, None, reserve=0, merged=findings)
        if stop is StopReason.CANCELLED:
            return self._cancelled_result()
        if stop is not None or status in {"INPUT_TOO_LARGE", "OUTLINE_TOO_LARGE"}:
            self.stop = self.stop or stop
            uncovered.append("reduce")  # the tree-level cross-check did not run: partial, never failed
        elif raw is None:
            return self._failed("the REDUCE call failed")
        else:
            claims = self._reduce_claims(raw)
            if claims is None:
                return self._failed("the REDUCE response is not a valid wbs-proposal/v1 envelope")
        if claims is None:  # the tree-level evidence cross-check never ran: say so, never assume
            reason = NotEvaluatedReason.AI_QUALIFICATION_NOT_RUN
            claims = [{"dimension": dim.value, "status": "NOT_EVALUATED", "summary": NOT_EVALUATED_SUMMARY[reason],
                       "reason_code": reason.value} for dim in QualificationDimension]

        envelope = {"contract_version": PROPOSAL_CONTRACT_VERSION,
                    "outcome": "PARTIAL_PROPOSAL" if uncovered else "COMPLETE",
                    "qualification": claims, "findings": findings, "proposals": proposals, "uncovered": uncovered}
        context = ValidationContext(scope=self.inputs.scope, target=self.inputs.target, manifest=self.visible,
                                    profiles=self.inputs.profiles, availability=self.ctx)
        validated = validate_model_output(json.dumps(envelope), context, mint=self.mint)
        self.report.rejected += validated.report.rejected
        self.report.dropped_dependants += validated.report.dropped_dependants
        self.report.coerced += validated.report.coerced
        if validated.outcome is RunOutcome.FAILED:
            self.report.envelope_error = validated.report.envelope_error
            return self._failed(_safe_failure(validated.report.envelope_error))
        ratio = self._ratio_failure(validated.report, context.max_rejected_pct)
        if ratio is not None:
            self.report.envelope_error = ratio
            return self._failed(ratio)
        qualification = reconcile_qualification(self.deterministic.report, validated.qualification, self.ctx)
        return self._result(PipelineStatus.COMPLETED, outcome=validated.outcome, qualification=qualification,
                            findings=(*self.deterministic.findings, *validated.findings),
                            proposals=validated.proposals, finding_refs=validated.finding_refs, uncovered=uncovered)


async def run_review_pipeline(
    inputs: ReviewInputs,
    model: WBSReviewerModelPort,
    *,
    cancelled: Cancelled | None = None,
    clock: Callable[[], float] = time.monotonic,
    isolation: UntrustedContentIsolation | None = None,
    mint: Callable[[], UUID] = uuid4,
) -> PipelineResult:
    """Review one exact target offline. Refuses live adapters, GENERATE and cross-scope inputs."""
    require_offline_adapter(model)
    if inputs.mode not in REVIEW_MODES:
        raise ValueError(f"{inputs.mode.value} is not a review (generation is PC-2b.5)")
    if (inputs.manifest.tenant_id, inputs.manifest.project_id) != (inputs.scope.tenant_id, inputs.scope.project_id):
        raise ValueError("the evidence manifest belongs to another tenant or project")
    if inputs.target.project_id != inputs.scope.project_id:
        raise ValueError("the review target belongs to another project")
    review = _Review(inputs, model, cancelled, clock, isolation or UntrustedContentIsolation(), mint)
    return await review.execute()


__all__ = [
    "ORCHESTRATION_VERSION",
    "REVIEW_MODES",
    "CallRecord",
    "PipelineResult",
    "PipelineStatus",
    "ReviewInputs",
    "UsageSummary",
    "reconcile_qualification",
    "run_review_pipeline",
]
