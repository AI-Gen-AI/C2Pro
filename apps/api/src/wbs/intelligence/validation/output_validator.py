"""Structured-output validation of WBS intelligence model responses (fail closed).

LLM output is never trusted because it parses as JSON. Before anything could enter a proposal
store, every response passes, in order:

1. ``parse_llm_json`` into the strict ``wbs-proposal/v1`` envelope (unknown / governance-like
   fields refused); duplicate refs or dimensions fail the whole envelope;
2. qualification: every dimension exactly once; the server availability matrix overrides the
   model; a claim without verified trusted evidence never stands (no pass by absence);
3. evidence: cited excerpts must be in the run manifest; DIRECT quotes must be found in the
   model-visible text; authority and canonical source come from the manifest, never the model;
4. proposals: only snapshot ids or local labels (an invented canonical id rejects the item),
   allowed operations, pinned profile namespaces and declared terms, dictionary v1, resolvable
   profile rules and findings, an acyclic dependency graph, and a simulated application on the
   exact target that keeps the tree valid. A rejected item takes its dependants with it.

Item-level rejections are recorded in the validation report. An invalid envelope, or more
rejections than the configured ratio, fails the run. Ids are minted by C2Pro, never the model.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from src.core.ai.structured_output import LLMSchemaError, parse_llm_json
from src.evidence.domain.models import VerificationStatus
from src.wbs.intelligence.contracts.evidence import (
    EvidenceAuthority,
    EvidenceBasis,
    EvidenceItem,
    EvidenceManifest,
    InputClass,
    ModelEvidenceCitation,
    ProfileRuleRef,
)
from src.wbs.intelligence.contracts.proposal import (
    DESTRUCTIVE_OPERATIONS,
    ModelDimensionResult,
    ModelFinding,
    ModelProposalItem,
    ModelResponseEnvelope,
    ProposalItem,
    ProposalOperation,
    TargetRef,
    confidence_band,
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
from src.wbs.intelligence.contracts.run import RunOutcome, RunScope
from src.wbs.intelligence.profiles.catalog import ResolvedProfileSet
from src.wbs.intelligence.validation.simulation import (
    SimulatedTree,
    SimulationError,
    TargetSnapshot,
    label_key,
)

_DOCUMENT_CLASSES = frozenset({InputClass.TRUSTED_PROJECT_EVIDENCE, InputClass.PROPOSED_EVIDENCE,
                               InputClass.ADVISORY_EVIDENCE})
_STRUCTURE_CLASSES = frozenset({InputClass.HUMAN_PROVIDED_IMPORT, InputClass.CURRENT_APPROVED_WBS})
_SPACES = re.compile(r"\s+")


class ItemRejected(ValueError):
    """One finding or proposal item fails validation (it is dropped, never repaired)."""


@dataclass(frozen=True)
class ValidationContext:
    """Everything a validation may consult -- explicitly scoped to one tenant and project."""

    scope: RunScope
    target: TargetSnapshot | None
    manifest: EvidenceManifest
    profiles: ResolvedProfileSet
    availability: AvailabilityContext
    max_rejected_pct: int = 50

    def __post_init__(self) -> None:
        if (self.manifest.tenant_id, self.manifest.project_id) != (self.scope.tenant_id, self.scope.project_id):
            raise ValueError("the evidence manifest belongs to another tenant or project")
        if self.target is not None and self.target.project_id != self.scope.project_id:
            raise ValueError("the target snapshot belongs to another project")


@dataclass
class ValidationReport:
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (ref, reason)
    dropped_dependants: list[tuple[str, str]] = field(default_factory=list)  # (ref, prerequisite ref)
    coerced: list[tuple[str, str]] = field(default_factory=list)  # (dimension, reason)
    envelope_error: str | None = None


@dataclass(frozen=True)
class ValidatedOutput:
    outcome: RunOutcome
    qualification: QualificationReport
    findings: tuple[NodeFinding, ...]
    proposals: tuple[ProposalItem, ...]
    uncovered: tuple[str, ...]
    report: ValidationReport


# ============================================================================ evidence
def _normalise(text: str) -> str:
    return _SPACES.sub(" ", unicodedata.normalize("NFC", text)).strip().casefold()


def _rule_ref(rule: str, profiles: ResolvedProfileSet) -> ProfileRuleRef:
    profile_id, _, rule_id = rule.partition(":")
    for ref, _heuristic in profiles.heuristics():
        if ref.profile_id == profile_id and ref.rule_id == rule_id:
            return ProfileRuleRef(profile_id=ref.profile_id, profile_version=ref.profile_version,
                                  profile_digest=ref.profile_digest, rule_id=ref.rule_id)
    raise ItemRejected(f"profile rule {rule!r} is not a rule of a pinned profile")


def verify_citation(citation: ModelEvidenceCitation, ctx: ValidationContext) -> EvidenceItem:
    basis = EvidenceBasis(citation.basis)
    if basis is EvidenceBasis.PROFILE_HEURISTIC:
        if citation.profile_rule is None or citation.excerpt_id is not None or citation.quote is not None:
            raise ItemRejected("a profile heuristic cites a pinned profile rule only")
        return EvidenceItem(basis=basis, authority=None, verification=VerificationStatus.UNCERTAIN,
                            profile_rule=_rule_ref(citation.profile_rule, ctx.profiles))
    if citation.excerpt_id is None:
        raise ItemRejected(f"{basis.value} evidence cites a manifest excerpt")
    item = ctx.manifest.get(citation.excerpt_id)
    if item is None:
        raise ItemRejected(f"excerpt {citation.excerpt_id} is outside the run's evidence manifest")
    expected = (
        {InputClass.USER_CONTEXT} if basis is EvidenceBasis.USER_CONTEXT
        else _STRUCTURE_CLASSES if basis is EvidenceBasis.IMPORTED_STRUCTURE
        else _DOCUMENT_CLASSES
    )
    if item.input_class not in expected:
        raise ItemRejected(f"{basis.value} evidence cannot cite a {item.input_class.value} excerpt")
    verified = citation.quote is not None and _normalise(citation.quote) in _normalise(item.model_visible.text)
    if citation.quote is not None and not verified:
        raise ItemRejected(f"the quote is not in excerpt {citation.excerpt_id}")
    if basis is EvidenceBasis.DIRECT and not verified:
        raise ItemRejected("DIRECT evidence needs a quote located in the cited excerpt")
    return EvidenceItem(
        basis=basis, authority=item.authority, excerpt_id=item.excerpt_id, canonical_source=item.canonical_source,
        model_quote=citation.quote, quote_scope="MODEL_VISIBLE_TEXT" if citation.quote is not None else None,
        verification=VerificationStatus.VERIFIED if verified else VerificationStatus.UNCERTAIN,
    )


def _verify_all(citations: Iterable[ModelEvidenceCitation], ctx: ValidationContext) -> tuple[EvidenceItem, ...]:
    return tuple(verify_citation(citation, ctx) for citation in citations)


def _trusted(evidence: Sequence[EvidenceItem]) -> bool:
    return any(item.authority is EvidenceAuthority.TRUSTED for item in evidence)


def _known_nodes(node_ids: Iterable[UUID], ctx: ValidationContext) -> tuple[UUID, ...]:
    known = ctx.target.ids() if ctx.target else frozenset()
    ids = tuple(node_ids)
    unknown = [node_id for node_id in ids if node_id not in known]
    if unknown:
        raise ItemRejected(f"invented canonical id(s) {[str(u) for u in unknown]} are not in the target")
    return ids


# ============================================================================ qualification
def _not_evaluated(dim: QualificationDimension, reason: NotEvaluatedReason, summary: str) -> DimensionResult:
    return DimensionResult(dimension=dim, status=QualificationStatus.NOT_EVALUATED, method=QualificationMethod.AI,
                           summary=summary, reason_code=reason)


def _qualification(claims: Sequence[ModelDimensionResult], ctx: ValidationContext,
                   report: ValidationReport) -> QualificationReport:
    matrix = availability(ctx.availability)
    by_dim = {claim.dimension: claim for claim in claims}
    results = []
    for dim in QualificationDimension:
        claim, unavailable = by_dim.get(dim), matrix[dim]
        if unavailable is not None:
            if claim is not None and claim.status is not QualificationStatus.NOT_EVALUATED:
                report.coerced.append((dim.value, f"unavailable ({unavailable.value}); model claimed {claim.status.value}"))
            results.append(_not_evaluated(dim, unavailable, NOT_EVALUATED_SUMMARY[unavailable]))
            continue
        if claim is None:
            report.coerced.append((dim.value, "not reported by the model"))
            results.append(_not_evaluated(dim, NotEvaluatedReason.NOT_REPORTED,
                                          NOT_EVALUATED_SUMMARY[NotEvaluatedReason.NOT_REPORTED]))
            continue
        if claim.status is QualificationStatus.NOT_EVALUATED:
            results.append(_not_evaluated(dim, claim.reason_code or NotEvaluatedReason.INSUFFICIENT_EVIDENCE,
                                          claim.summary))
            continue
        try:
            evidence = _verify_all(claim.evidence, ctx)
            node_ids = _known_nodes(claim.node_ids, ctx)
            rules = tuple(_rule_ref(rule, ctx.profiles) for rule in claim.profile_rule_refs)
        except ItemRejected as exc:
            report.coerced.append((dim.value, f"claim refused: {exc}"))
            results.append(_not_evaluated(dim, NotEvaluatedReason.INSUFFICIENT_EVIDENCE, "Claim refused"))
            continue
        status = claim.status
        if status in {QualificationStatus.SUPPORTED, QualificationStatus.GAP} and not _trusted(evidence):
            if not evidence:
                report.coerced.append((dim.value, f"{status.value} without evidence (no pass by absence)"))
                results.append(_not_evaluated(dim, NotEvaluatedReason.INSUFFICIENT_EVIDENCE, claim.summary))
                continue
            report.coerced.append((dim.value, f"{status.value} without trusted evidence downgraded to WARNING"))
            status = QualificationStatus.WARNING
        results.append(DimensionResult(dimension=dim, status=status, method=QualificationMethod.AI,
                                       summary=claim.summary, evidence=evidence,
                                       confidence_pct=claim.confidence_pct, profile_rule_refs=rules,
                                       node_ids=node_ids))
    return QualificationReport(results=tuple(results))


def _findings(claims: Sequence[ModelFinding], ctx: ValidationContext, report: ValidationReport,
              mint: Callable[[], UUID]) -> tuple[list[NodeFinding], dict[str, UUID]]:
    matrix = availability(ctx.availability)
    accepted, ids = [], {}
    for claim in claims:
        try:
            if matrix[claim.dimension] is not None:
                raise ItemRejected(f"dimension {claim.dimension.value} is not available "
                                   f"({matrix[claim.dimension].value})")  # type: ignore[union-attr]
            evidence = _verify_all(claim.evidence, ctx)
            node_ids = _known_nodes(claim.node_ids, ctx)
            rules = tuple(_rule_ref(rule, ctx.profiles) for rule in claim.profile_rule_refs)
        except ItemRejected as exc:
            report.rejected.append((claim.ref, str(exc)))
            continue
        status = QualificationStatus(claim.status)
        if status is QualificationStatus.GAP and not _trusted(evidence):
            report.coerced.append((claim.ref, "GAP without trusted evidence downgraded to WARNING"))
            status = QualificationStatus.WARNING
        finding = NodeFinding(finding_id=mint(), dimension=claim.dimension, status=status,
                              method=QualificationMethod.AI, summary=claim.summary, node_ids=node_ids,
                              evidence=evidence, confidence_pct=claim.confidence_pct, profile_rule_refs=rules)
        ids[claim.ref] = finding.finding_id
        accepted.append(finding)
    return accepted, ids


# ============================================================================ proposals
_SHAPE: dict[ProposalOperation, tuple[set[str], set[str]]] = {
    # operation: (required fields, allowed optional fields) beyond the common ones
    ProposalOperation.ADD_NODE: ({"creates_label", "spec"}, {"parent", "position"}),
    ProposalOperation.UPDATE_NODE: ({"node", "changes"}, set()),
    ProposalOperation.RECODE_NODE: ({"node", "code"}, set()),
    ProposalOperation.MOVE_NODE: ({"node"}, {"parent", "position"}),
    ProposalOperation.REORDER_NODE: ({"node", "position"}, set()),
    ProposalOperation.REMOVE_NODE: ({"node"}, set()),
    ProposalOperation.SPLIT_NODE: ({"node", "split_targets"}, {"child_targets"}),
    ProposalOperation.MERGE_NODES: ({"sources", "creates_label", "spec"}, {"parent", "position"}),
}
_OPERATION_FIELDS = {"node", "sources", "parent", "position", "creates_label", "spec", "changes", "code",
                     "split_targets", "child_targets"}


def _refs(item: ModelProposalItem) -> list[TargetRef]:
    refs = [ref for ref in (item.node, item.parent) if ref is not None]
    return refs + list(item.sources)


def _created(item: ModelProposalItem) -> list[str]:
    labels = [item.creates_label] if item.creates_label else []
    return labels + [target.label for target in item.split_targets]


def _check_shape(item: ModelProposalItem, ctx: ValidationContext) -> None:
    present = {name for name in _OPERATION_FIELDS if getattr(item, name) not in (None, (), {})}
    required, optional = _SHAPE[item.operation]
    missing, extra = required - present, present - required - optional
    if missing or extra:
        raise ItemRejected(f"{item.operation.value} needs {sorted(required)}"
                           + (f"; missing {sorted(missing)}" if missing else "")
                           + (f"; not allowed {sorted(extra)}" if extra else ""))
    snapshot_ids = [ref.node_id for ref in _refs(item) if ref.node_id is not None]
    for child in item.child_targets:
        try:
            snapshot_ids.append(UUID(child))
        except ValueError as exc:
            if not child.startswith("label:"):
                raise ItemRejected(f"child_targets key {child!r} is neither a node id nor a label") from exc
    _known_nodes(snapshot_ids, ctx)


def _graph(items: Sequence[ModelProposalItem], report: ValidationReport) -> tuple[dict[str, set[str]], set[str]]:
    """Prerequisites per item ref (explicit + through labels); refs rejected while building it."""
    creator: dict[str, str] = {}
    rejected: set[str] = set()
    for item in items:
        for label in _created(item):
            if label in creator:
                rejected.add(item.ref)
                report.rejected.append((item.ref, f"label {label!r} is already created by {creator[label]}"))
            else:
                creator[label] = item.ref
    refs = {item.ref for item in items}
    graph: dict[str, set[str]] = {}
    for item in items:
        deps = set(item.depends_on)
        unknown = deps - refs
        if unknown:
            rejected.add(item.ref)
            report.rejected.append((item.ref, f"depends on unknown item(s) {sorted(unknown)}"))
        used = [ref.label for ref in _refs(item) if ref.label is not None]
        used += [key.removeprefix("label:") for key in item.child_targets if key.startswith("label:")]
        for label in used:
            if label not in creator:
                rejected.add(item.ref)
                report.rejected.append((item.ref, f"label {label!r} is created by no item"))
            elif creator[label] != item.ref:
                deps.add(creator[label])
        graph[item.ref] = deps & refs
    return graph, rejected


def _topological(graph: dict[str, set[str]], report: ValidationReport, rejected: set[str]) -> list[str]:
    order: list[str] = []
    state: dict[str, str] = {}

    def visit(ref: str, path: list[str]) -> None:
        if state.get(ref) == "done":
            return
        if state.get(ref) == "active":
            cycle = path[path.index(ref):]
            for member in cycle:
                if member not in rejected:
                    rejected.add(member)
                    report.rejected.append((member, f"dependency cycle {' -> '.join(cycle + [ref])}"))
            return
        state[ref] = "active"
        for dep in sorted(graph[ref]):
            visit(dep, path + [ref])
        state[ref] = "done"
        order.append(ref)

    for ref in sorted(graph):
        visit(ref, [])
    return order


def _proposals(items: Sequence[ModelProposalItem], ctx: ValidationContext, report: ValidationReport,
               finding_ids: dict[str, UUID], mint: Callable[[], UUID]) -> list[ProposalItem]:
    by_ref = {item.ref: item for item in items}
    graph, rejected = _graph(items, report)
    order = _topological(graph, report, rejected)
    tree = SimulatedTree.of(ctx.target, ctx.profiles.terms_by_namespace())
    fingerprints = ctx.target.fingerprints() if ctx.target else {}
    verified: dict[str, tuple[tuple[EvidenceItem, ...], tuple[ProfileRuleRef, ...], tuple[UUID, ...]]] = {}
    item_ids = {ref: mint() for ref in by_ref}
    accepted: list[str] = []
    for ref in order:
        item = by_ref[ref]
        if ref in rejected:
            continue
        blocker = next((dep for dep in sorted(graph[ref]) if dep in rejected), None)
        if blocker is not None:
            rejected.add(ref)
            report.dropped_dependants.append((ref, blocker))
            continue
        try:
            _check_shape(item, ctx)
            evidence = _verify_all(item.evidence, ctx)
            rules = tuple(_rule_ref(rule, ctx.profiles) for rule in item.profile_rule_refs)
            unknown = [f for f in item.addresses_findings if f not in finding_ids]
            if unknown:
                raise ItemRejected(f"addresses unknown finding(s) {unknown}")
            candidate = tree.copy()
            candidate.apply(item)
        except (ItemRejected, SimulationError) as exc:
            rejected.add(ref)
            report.rejected.append((ref, str(exc)))
            continue
        tree = candidate
        verified[ref] = (evidence, rules, tuple(finding_ids[f] for f in item.addresses_findings))
        accepted.append(ref)

    stored = []
    for ref in accepted:
        item = by_ref[ref]
        evidence, rules, addressed = verified[ref]
        affected = tuple(dict.fromkeys(
            [r.node_id for r in _refs(item) if r.node_id is not None]
            + [UUID(k) for k in item.child_targets if not k.startswith("label:")]))
        payload: dict[str, Any] = item.model_dump(
            mode="json", include=_OPERATION_FIELDS, exclude_none=True, exclude_defaults=True)
        stored.append(ProposalItem(
            item_id=item_ids[ref], ref=ref, operation=item.operation, payload=payload, affected_node_ids=affected,
            target_fingerprints={str(node_id): fingerprints[node_id] for node_id in affected},
            creates_labels=tuple(_created(item)),
            uses_labels=tuple(r.label for r in _refs(item) if r.label is not None),
            depends_on=tuple(item_ids[dep] for dep in sorted(graph[ref])), rationale=item.rationale,
            evidence=evidence, confidence_pct=item.confidence_pct, confidence=confidence_band(item.confidence_pct),
            assumptions=item.assumptions, ambiguity_flags=item.ambiguity_flags, profile_rule_refs=rules,
            addresses_finding_ids=addressed, destructive=item.operation in DESTRUCTIVE_OPERATIONS,
        ))
    return stored


def _failed(report: ValidationReport) -> ValidatedOutput:
    results = tuple(_not_evaluated(dim, NotEvaluatedReason.NOT_REPORTED, "Run failed validation")
                    for dim in QualificationDimension)
    return ValidatedOutput(outcome=RunOutcome.FAILED, qualification=QualificationReport(results=results),
                           findings=(), proposals=(), uncovered=(), report=report)


def validate_model_output(raw: str, ctx: ValidationContext, *, mint: Callable[[], UUID] = uuid4) -> ValidatedOutput:
    """Validate one raw model response against the run context. Never repairs, never trusts."""
    report = ValidationReport()
    try:
        envelope = parse_llm_json(raw, ModelResponseEnvelope)
    except LLMSchemaError as exc:
        report.envelope_error = str(exc)
        return _failed(report)
    dims = [claim.dimension for claim in envelope.qualification]
    refs = [f.ref for f in envelope.findings] + [p.ref for p in envelope.proposals]
    if len(set(dims)) != len(dims) or len(set(refs)) != len(refs):
        report.envelope_error = "a dimension or item ref appears twice"
        return _failed(report)
    qualification = _qualification(envelope.qualification, ctx, report)
    findings, finding_ids = _findings(envelope.findings, ctx, report, mint)
    proposals_in = envelope.proposals
    if envelope.outcome == "INSUFFICIENT_EVIDENCE" and proposals_in:
        report.rejected += [(p.ref, "an INSUFFICIENT_EVIDENCE outcome carries no proposals") for p in proposals_in]
        proposals_in = ()
    proposals = _proposals(proposals_in, ctx, report, finding_ids, mint)

    total = len(envelope.findings) + len(envelope.proposals)
    refused = len(report.rejected) + len(report.dropped_dependants)
    if total and refused * 100 > ctx.max_rejected_pct * total:
        report.envelope_error = f"{refused} of {total} items refused (over {ctx.max_rejected_pct}%)"
        return _failed(report)
    return ValidatedOutput(outcome=RunOutcome(envelope.outcome), qualification=qualification,
                           findings=tuple(findings), proposals=tuple(proposals),
                           uncovered=envelope.uncovered, report=report)


__all__ = [
    "ItemRejected",
    "ValidatedOutput",
    "ValidationContext",
    "ValidationReport",
    "label_key",
    "validate_model_output",
    "verify_citation",
]
