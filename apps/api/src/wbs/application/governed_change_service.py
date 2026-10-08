"""Governed WBS edit / submit / approve = apply (PC-2a.2 #896, ADR-029).

The ONLY path that creates an approved WBS baseline and the ONLY writer of governed live
``wbs_nodes`` content, in every authority state (NO_WBS, LEGACY_UNGOVERNED, APPROVED_BASELINE):

    DRAFT candidate -> human edit commands -> validate -> SUBMIT (digest frozen)
      -> human admin APPROVE = APPLY (one transaction) -> Baseline #N -> canonical live WBS

* Every DRAFT command takes ``expected_revision`` and advances it by exactly one (optimistic
  lock): a stale edit is ``CHANGE_SET_REVISION_CONFLICT``, never last-write-wins.
* Identity: ADD mints; UPDATE / RECODE / MOVE / REORDER keep the id; SPLIT and MERGE retire
  their sources and mint their targets with explicit lineage; REMOVE records a disposition.
  Retired ids are never reused (database guard).
* A first baseline never auto-adopts legacy rows: ADOPT_LEGACY_NODE is explicit, and every
  legacy row the candidate does not adopt is recorded at submit as RETIRED_ON_BASELINE with a
  snapshot of the row. Apply refuses if the legacy rows changed after submission.
* Approve = apply: project lock, compare-and-set (status, revision, digest), human admin,
  separation of duties, current base, digest recomputation, full re-validation, the immutable
  baseline row (the database authority the ``wbs_nodes`` guard checks), live materialization
  proven equal to it, APPLIED, competing change sets STALE, ProjectEvent --
  all in one transaction. Any failure leaves the live WBS, baselines and the change set as they
  were. The ProjectSnapshot is enqueued only after commit (fail-open, never baseline authority).
* Actor identity always comes from the authenticated session; AI, service and ``api``
  principals never submit, decide or approve. Origin never grants authority.

Nothing here touches Schedule, Budget, BOM, RACI or procurement: alignment is future work.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import Tenant
from src.core.exceptions import C2ProException
from src.core.json_types import JsonDict
from src.core.tenants.types import require_tenant_id
from src.procurement.adapters.persistence.wbs_repository import (
    SQLAlchemyWBSRepository,
    WBSLiveTreeDivergedError,
)
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.domain.project_snapshot import SnapshotTrigger
from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineNodeORM,
    WBSBaselineORM,
    WBSChangeSetLineageORM,
    WBSChangeSetNodeORM,
    WBSChangeSetORM,
    WBSChangeSetRetirementORM,
)
from src.wbs.adapters.persistence.governance_repository import (
    Actor,
    ChangeSetDetail,
    ChangeSetNotFoundError,
    RevisionConflictError,
    WBSGovernanceRepository,
    candidate_digest_node,
)
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.domain.digest import (
    DigestNode,
    LineageEdge,
    normalize_dictionary,
    normalize_profile_ref,
    tree_digest,
)
from src.wbs.domain.governance import (
    CandidateNode,
    CandidateOriginKind,
    ChangeSetOrigin,
    ChangeSetStatus,
    EntryMode,
    GovernanceRuleError,
    LineageKind,
    can_author,
    can_decide,
    can_withdraw_or_reopen,
    require_distinct_approver,
    self_approval,
    validate_control_level,
    validate_decomposition_kind,
)
from src.wbs.domain.governed_change import (
    Retirement,
    RetirementDisposition,
    RetirementSource,
    normalize_evidence_refs,
    validate_governed_submission,
)
from src.wbs.intelligence.profiles.catalog import ProfileCompositionError, default_catalog

logger = structlog.get_logger(__name__)

# Correlation only: names the change set being applied. It authorizes nothing by itself -- the
# wbs_nodes guard also requires this transaction's uncommitted baseline row for that change set.
APPLY_SETTING: Final = "c2pro.wbs_governed_apply"
EVENT_SUBMITTED: Final = "wbs.change.submitted"
EVENT_REJECTED: Final = "wbs.change.rejected"
EVENT_APPLIED: Final = "wbs.baseline.applied"
REBASED_FROM_PREFIX: Final = "wbs-change-set:"
_EDITABLE_FIELDS = frozenset({"name", "dictionary", "decomposition_kind", "control_level"})
_MAX_CODE = 50
_MAX_NAME = 255


# ============================================================================ errors (HTTP-shaped)
class WBSGovernanceForbiddenError(C2ProException):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="WBS_GOVERNANCE_FORBIDDEN", status_code=403)


class WBSChangeSetNotFoundError(C2ProException):
    def __init__(self, change_set_id: UUID) -> None:
        super().__init__(message="WBS change set not found", code="WBS_CHANGE_SET_NOT_FOUND", status_code=404,
                         details={"change_set_id": str(change_set_id)})


class WBSProjectNotFoundError(C2ProException):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(message="Project not found", code="PROJECT_NOT_FOUND", status_code=404,
                         details={"project_id": str(project_id)})


class ChangeSetRevisionConflictError(C2ProException):
    def __init__(self, message: str, current_revision: int | None = None) -> None:
        super().__init__(message=message, code="CHANGE_SET_REVISION_CONFLICT", status_code=409,
                         details={"current_revision": current_revision})


class ChangeSetStateError(C2ProException):
    def __init__(self, message: str, status: str) -> None:
        super().__init__(message=message, code="CHANGE_SET_INVALID_STATE", status_code=409, details={"status": status})


class ChangeSetStaleError(C2ProException):
    def __init__(self, change_set_id: UUID) -> None:
        super().__init__(
            message="The change set was proposed against a baseline that is no longer current: rebase it into a new draft",
            code="CHANGE_SET_STALE", status_code=409, details={"change_set_id": str(change_set_id)},
        )


class ChangeSetDigestMismatchError(C2ProException):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CHANGE_SET_DIGEST_MISMATCH", status_code=409)


class LegacyWBSChangedError(C2ProException):
    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"The legacy WBS changed since the change set was submitted ({detail}): reopen and resubmit it",
            code="LEGACY_WBS_CHANGED_SINCE_SUBMISSION", status_code=409,
        )


class RetiredNodesLinkedError(C2ProException):
    def __init__(self, raci_links: int, bom_links: int) -> None:
        super().__init__(
            message=(f"Retired WBS nodes still carry {raci_links} RACI assignment(s) and {bom_links} BOM link(s): "
                     "reassign them before applying (links are never re-pointed automatically)"),
            code="WBS_NODE_HAS_LINKS", status_code=409, details={"raci_links": raci_links, "bom_links": bom_links},
        )


class WBSChangeSetInvalidError(C2ProException):
    def __init__(self, message: str, violations: Sequence[str] = ()) -> None:
        super().__init__(message=message, code="WBS_CHANGE_SET_INVALID", status_code=422,
                         details={"violations": list(violations)})


# ============================================================================ commands
_UNSET: Any = object()


@dataclass(frozen=True)
class NodeSpec:
    """Content of a new candidate node (its id is always minted by the server)."""

    name: str
    code: str | None = None
    control_level: str = "none"
    decomposition_kind: str | None = None
    dictionary: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class AddNode:
    spec: NodeSpec
    parent_id: UUID | None = None
    position: int | None = None


@dataclass(frozen=True)
class UpdateNode:
    """Rename / re-describe (dictionary) / reclassify -- same identity."""

    node_id: UUID
    changes: Mapping[str, Any]


@dataclass(frozen=True)
class RecodeNode:
    node_id: UUID
    code: str


@dataclass(frozen=True)
class MoveNode:
    node_id: UUID
    parent_id: UUID | None
    position: int | None = None


@dataclass(frozen=True)
class ReorderNode:
    node_id: UUID
    position: int


@dataclass(frozen=True)
class RemoveNode:
    node_id: UUID


@dataclass(frozen=True)
class SplitNode:
    """One source -> N >= 2 minted targets; every candidate child must be assigned to a target."""

    source_id: UUID
    targets: Sequence[NodeSpec]
    child_targets: Mapping[UUID, int] = field(default_factory=dict)


@dataclass(frozen=True)
class MergeNodes:
    """N >= 2 sources -> one minted target placed at the first source (unless told otherwise)."""

    source_ids: Sequence[UUID]
    target: NodeSpec
    parent_id: Any = _UNSET
    position: int | None = None


@dataclass(frozen=True)
class AdoptLegacyNode:
    """First baseline only: keep this exact live legacy id in the candidate."""

    legacy_node_id: UUID
    parent_id: UUID | None = None
    position: int | None = None


EditCommand = AddNode | UpdateNode | RecodeNode | MoveNode | ReorderNode | RemoveNode | SplitNode | MergeNodes | AdoptLegacyNode


@dataclass(frozen=True)
class CommandResult:
    revision: int
    node_ids: list[UUID]


@dataclass(frozen=True)
class ApplyResult:
    change_set_id: UUID
    baseline_id: UUID
    baseline_no: int
    tree_digest: str
    change_set_digest: str
    self_approved: bool
    event_id: UUID
    retired: list[dict[str, str]]
    stale_change_set_ids: list[UUID]
    applied_at: datetime


# ============================================================================ helpers
def _nfc_code(code: str | None) -> str | None:
    if code is None:
        return None
    if not isinstance(code, str) or not code.strip():
        raise GovernanceRuleError("a WBS code must be a non-empty string")
    code = unicodedata.normalize("NFC", code.strip())
    if len(code) > _MAX_CODE:
        raise GovernanceRuleError(f"a WBS code is at most {_MAX_CODE} characters")
    return code


def _name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise GovernanceRuleError("a WBS node needs a name")
    if len(name.strip()) > _MAX_NAME:
        raise GovernanceRuleError(f"a WBS name is at most {_MAX_NAME} characters")
    return name.strip()


def _validated_spec(spec: NodeSpec) -> NodeSpec:
    validate_control_level(spec.control_level)
    validate_decomposition_kind(spec.decomposition_kind)
    return NodeSpec(
        name=_name(spec.name),
        code=_nfc_code(spec.code),
        control_level=spec.control_level,
        decomposition_kind=spec.decomposition_kind,
        dictionary=None if spec.dictionary is None else normalize_dictionary(spec.dictionary),
    )


def _candidate(node: WBSChangeSetNodeORM) -> CandidateNode:
    return CandidateNode(
        node_id=node.node_id, parent_id=node.parent_id, sort_order=node.sort_order, code=node.code, name=node.name,
        decomposition_kind=node.decomposition_kind, control_level=node.control_level, dictionary=node.dictionary,
        origin_kind=node.origin_kind,
    )


def _naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class WBSGovernedChangeService:
    """Governed WBS workflow over one transactional session (the caller commits)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WBSGovernanceRepository(session)
        self.live = SQLAlchemyWBSRepository(session)

    # ------------------------------------------------------------------ scoping
    async def _require_project(self, project_id: UUID, tenant_id: UUID, *, lock: bool = False) -> None:
        query = select(ProjectORM.id).where(ProjectORM.id == project_id, ProjectORM.tenant_id == tenant_id)
        if lock:
            query = query.with_for_update()
        if await self.session.scalar(query) is None:
            raise WBSProjectNotFoundError(project_id)

    async def _scoped(self, change_set_id: UUID, project_id: UUID, tenant_id: UUID, *, lock: bool = False) -> WBSChangeSetORM:
        query = (
            select(WBSChangeSetORM)
            .where(
                WBSChangeSetORM.id == change_set_id,
                WBSChangeSetORM.project_id == project_id,
                WBSChangeSetORM.tenant_id == tenant_id,
            )
            .execution_options(populate_existing=True)
        )
        if lock:
            query = query.with_for_update()
        change_set = await self.session.scalar(query)
        if change_set is None:
            raise WBSChangeSetNotFoundError(change_set_id)
        return change_set

    async def change_set(self, change_set_id: UUID, project_id: UUID, tenant_id: UUID) -> WBSChangeSetORM:
        """The change set, scoped to its tenant AND project (404 otherwise)."""
        return await self._scoped(change_set_id, project_id, tenant_id)

    async def _detail(self, change_set: WBSChangeSetORM) -> ChangeSetDetail:
        detail = await self.repo.get_change_set(change_set.id, change_set.project_id, change_set.tenant_id)
        if detail is None:  # pragma: no cover - scoped above
            raise WBSChangeSetNotFoundError(change_set.id)
        return detail

    async def _tenant_requires_distinct_approver(self, tenant_id: UUID) -> bool:
        settings = await self.session.scalar(select(Tenant.settings).where(Tenant.id == tenant_id))
        return require_distinct_approver(settings)

    async def _lock_live_rows(self, project_id: UUID, tenant_id: UUID) -> frozenset[UUID]:
        rows = await self.session.execute(
            select(WBSNodeORM.id)
            .where(WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id)
            .order_by(WBSNodeORM.id)
            .with_for_update()
        )
        return frozenset(row.id for row in rows)

    async def _legacy_ids(self, project_id: UUID, tenant_id: UUID) -> frozenset[UUID]:
        rows = await self.session.execute(
            select(WBSNodeORM.id).where(WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id)
        )
        return frozenset(row.id for row in rows)

    async def _base_ids(self, base_baseline_id: UUID) -> frozenset[UUID]:
        rows = await self.session.execute(
            select(WBSBaselineNodeORM.node_id).where(WBSBaselineNodeORM.baseline_id == base_baseline_id)
        )
        return frozenset(row.node_id for row in rows)

    async def _live_snapshot(self, node_id: UUID) -> dict[str, Any] | None:
        row = await self.session.execute(
            text("SELECT to_jsonb(w) AS snapshot FROM wbs_nodes w WHERE w.id = :id").columns(snapshot=JSONB),
            {"id": node_id},
        )
        value = row.scalar_one_or_none()
        return dict(value) if value is not None else None

    async def _baseline_snapshot(self, baseline_id: UUID, node_id: UUID) -> dict[str, Any]:
        node = await self.session.scalar(
            select(WBSBaselineNodeORM).where(
                WBSBaselineNodeORM.baseline_id == baseline_id, WBSBaselineNodeORM.node_id == node_id
            )
        )
        if node is None:
            raise GovernanceRuleError(f"{node_id} is not an identity of the base baseline")
        return {
            "baseline_id": str(baseline_id), "node_id": str(node.node_id),
            "parent_id": str(node.parent_id) if node.parent_id else None, "sort_order": node.sort_order,
            "code": node.code, "name": node.name, "control_level": node.control_level,
            "decomposition_kind": node.decomposition_kind, "dictionary": node.dictionary,
        }

    async def _event(self, *, project_id: UUID, tenant_id: UUID, event_type: str, payload: JsonDict, actor: Actor) -> UUID:
        now = _naive_now()
        event = ProjectEvent(
            event_id=uuid4(), project_id=project_id, tenant_id=require_tenant_id(tenant_id), event_type=event_type,
            payload=payload, actor=f"user:{actor.user_id}", occurred_at=now, created_at=now,
        )
        await SqlAlchemyProjectEventRepository(self.session).append(event)
        return event.event_id

    # ------------------------------------------------------------------ candidate state
    async def _nodes(self, change_set_id: UUID) -> dict[UUID, WBSChangeSetNodeORM]:
        rows = await self.session.execute(
            select(WBSChangeSetNodeORM)
            .where(WBSChangeSetNodeORM.change_set_id == change_set_id)
            .execution_options(populate_existing=True)
        )
        return {row.node_id: row for row in rows.scalars()}

    async def _retired_ids(self, change_set_id: UUID) -> set[UUID]:
        rows = await self.session.execute(
            select(WBSChangeSetRetirementORM.node_id).where(WBSChangeSetRetirementORM.change_set_id == change_set_id)
        )
        return {row.node_id for row in rows}

    @staticmethod
    def _subtree(nodes: Mapping[UUID, WBSChangeSetNodeORM], root: UUID) -> set[UUID]:
        collected, stack = set(), [root]
        while stack:
            current = stack.pop()
            if current in collected:
                continue
            collected.add(current)
            stack.extend(n.node_id for n in nodes.values() if n.parent_id == current)
        return collected

    @staticmethod
    def _place(
        nodes: Mapping[UUID, WBSChangeSetNodeORM], parent_id: UUID | None, placed: Sequence[UUID], position: int | None
    ) -> None:
        """Insert ``placed`` (in order) at 1-based ``position`` under ``parent_id`` and renumber 1..n."""
        if position is not None and position < 1:
            raise GovernanceRuleError("a sibling position starts at 1")
        siblings = sorted(
            (n for n in nodes.values() if n.parent_id == parent_id and n.node_id not in placed),
            key=lambda n: (n.sort_order, str(n.node_id)),
        )
        index = len(siblings) if position is None else min(position - 1, len(siblings))
        ordered = [n.node_id for n in siblings[:index]] + list(placed) + [n.node_id for n in siblings[index:]]
        for order, node_id in enumerate(ordered, start=1):
            node = nodes[node_id]
            node.parent_id = parent_id
            if node.sort_order != order:
                node.sort_order = order

    @staticmethod
    def _renumber(nodes: Mapping[UUID, WBSChangeSetNodeORM], parent_id: UUID | None) -> None:
        siblings = sorted((n for n in nodes.values() if n.parent_id == parent_id), key=lambda n: (n.sort_order, str(n.node_id)))
        for order, node in enumerate(siblings, start=1):
            if node.sort_order != order:
                node.sort_order = order

    def _new_node(self, change_set: WBSChangeSetORM, spec: NodeSpec, *, node_id: UUID, origin_kind: CandidateOriginKind,
                  parent_id: UUID | None, sort_order: int, provenance: Mapping[str, Any]) -> WBSChangeSetNodeORM:
        node = WBSChangeSetNodeORM(
            change_set_id=change_set.id, node_id=node_id, tenant_id=change_set.tenant_id, project_id=change_set.project_id,
            parent_id=parent_id, sort_order=sort_order, code=spec.code, name=spec.name, control_level=spec.control_level,
            decomposition_kind=spec.decomposition_kind,
            dictionary=None if spec.dictionary is None else dict(spec.dictionary),
            origin_kind=origin_kind.value, provenance=dict(provenance),
        )
        self.session.add(node)
        return node

    async def _retire(self, change_set: WBSChangeSetORM, node_id: UUID, disposition: RetirementDisposition,
                      source_kind: CandidateOriginKind | None) -> None:
        """Record why ``node_id`` leaves the WBS (base identity, or legacy row for a first baseline)."""
        if change_set.base_baseline_id is not None:
            snapshot = await self._baseline_snapshot(change_set.base_baseline_id, node_id)
            source = RetirementSource.BASELINE
        else:
            live = await self._live_snapshot(node_id)
            if live is None or live.get("project_id") != str(change_set.project_id):
                raise GovernanceRuleError(f"{node_id} is not a legacy live row of this project")
            snapshot, source = live, RetirementSource.LEGACY
        if source_kind is CandidateOriginKind.MINTED:  # pragma: no cover - callers never retire minted ids
            raise GovernanceRuleError("a minted candidate node is dropped, not retired")
        self.session.add(WBSChangeSetRetirementORM(
            change_set_id=change_set.id, node_id=node_id, tenant_id=change_set.tenant_id,
            project_id=change_set.project_id, disposition=disposition.value, source=source.value, snapshot=snapshot,
        ))

    # ------------------------------------------------------------------ create / rebase
    async def create_change_set(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        title: str,
        description: str | None = None,
        entry_mode: EntryMode | None = None,
        origin: ChangeSetOrigin = ChangeSetOrigin.MANUAL,
        evidence_refs: Sequence[str] = (),
        profile_refs: Sequence[Mapping[str, str]] = (),
        source_import_id: UUID | None = None,
    ) -> WBSChangeSetORM:
        """A new DRAFT against the current baseline; a CHANGE_BASELINE draft starts as that baseline.

        ``source_import_id`` (PC-2b.3) is set only by the WBS import service for an IMPORT_REVIEW
        draft: provenance of the draft, never content and never authority.
        """
        if not can_author(actor.kind, actor.role):
            raise WBSGovernanceForbiddenError("only a human user or admin can open a governed WBS change set")
        # The project lock orders this against an approval: the base is read after it commits, or the
        # approval sees (and stales) this draft.
        await self._require_project(project_id, tenant_id, lock=True)
        try:
            refs = normalize_evidence_refs(evidence_refs)
            pins = [normalize_profile_ref(ref) for ref in profile_refs]
            change_set = await self.repo.create_change_set(
                project_id=project_id, tenant_id=tenant_id, actor=actor, title=title, origin=origin,
                entry_mode=entry_mode, description=description, profile_refs=pins, evidence_refs=refs,
                source_import_id=source_import_id,
            )
        except (GovernanceRuleError, TypeError, ValueError) as exc:
            raise WBSChangeSetInvalidError(str(exc)) from exc
        if change_set.base_baseline_id is not None:
            base_nodes = await self.session.execute(
                select(WBSBaselineNodeORM).where(WBSBaselineNodeORM.baseline_id == change_set.base_baseline_id)
            )
            for base in base_nodes.scalars():
                self.session.add(WBSChangeSetNodeORM(
                    change_set_id=change_set.id, node_id=base.node_id, tenant_id=tenant_id, project_id=project_id,
                    parent_id=base.parent_id, sort_order=base.sort_order, code=base.code, name=base.name,
                    control_level=base.control_level, decomposition_kind=base.decomposition_kind,
                    dictionary=base.dictionary, origin_kind=CandidateOriginKind.EXISTING.value,
                    provenance={"seeded_from_baseline": str(change_set.base_baseline_id)},
                ))
            await self.session.flush()
        return change_set

    async def rebase(self, *, project_id: UUID, change_set_id: UUID, tenant_id: UUID, actor: Actor) -> WBSChangeSetORM:
        """STALE -> a NEW draft seeded from the latest baseline; the STALE record stays untouched."""
        await self._require_project(project_id, tenant_id, lock=True)  # project before change set, as approve
        stale = await self._scoped(change_set_id, project_id, tenant_id, lock=True)
        if stale.status != ChangeSetStatus.STALE.value:
            raise ChangeSetStateError("only a STALE change set is rebased", stale.status)
        if not can_withdraw_or_reopen(actor.kind, actor.role, actor.user_id, proposers=(stale.created_by, stale.submitted_by)):
            raise WBSGovernanceForbiddenError("only the proposer or a human admin can rebase a WBS change set")
        return await self.create_change_set(
            project_id=project_id, tenant_id=tenant_id, actor=actor, title=stale.title, description=stale.description,
            origin=ChangeSetOrigin(stale.origin),
            evidence_refs=[*(stale.evidence_refs or []), f"{REBASED_FROM_PREFIX}{stale.id}"],
            profile_refs=list(stale.profile_refs or []),
        )

    # ------------------------------------------------------------------ DRAFT edit commands
    async def execute(
        self,
        *,
        project_id: UUID,
        change_set_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        expected_revision: int,
        command: EditCommand,
        provenance: Mapping[str, Any] | None = None,
    ) -> CommandResult:
        """One typed edit of a DRAFT, as a human author, under the expected revision.

        ``provenance`` (PC-2b.2) is appended to the ``intelligence`` list of the candidate nodes the
        command created or kept (never to their content): it records which intelligence item a
        human applied. It authorizes nothing and is excluded from every digest.
        """
        if not can_author(actor.kind, actor.role):
            raise WBSGovernanceForbiddenError("only a human user or admin can edit a WBS change set")
        await self._scoped(change_set_id, project_id, tenant_id)
        try:
            change_set = await self.repo.bump_revision(change_set_id, tenant_id, expected_revision)
        except RevisionConflictError as exc:
            current = await self._scoped(change_set_id, project_id, tenant_id)
            raise ChangeSetRevisionConflictError(str(exc), current.revision) from exc
        except ChangeSetNotFoundError as exc:  # pragma: no cover - scoped above
            raise WBSChangeSetNotFoundError(change_set_id) from exc
        except GovernanceRuleError as exc:
            current = await self._scoped(change_set_id, project_id, tenant_id)
            raise ChangeSetStateError(str(exc), current.status) from exc
        try:
            node_ids = await self._dispatch(change_set, command)
            await self.session.flush()
        except (GovernanceRuleError, TypeError, ValueError) as exc:
            raise WBSChangeSetInvalidError(str(exc)) from exc
        if provenance:
            await self._record_provenance(change_set.id, node_ids, provenance)
        return CommandResult(revision=change_set.revision, node_ids=node_ids)

    async def execute_add_sequence(
        self,
        *,
        project_id: UUID,
        change_set_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        expected_revision: int,
        steps: Sequence[Callable[[Sequence[UUID]], tuple[AddNode, Mapping[str, Any]]]],
    ) -> CommandResult:
        """An ordered sequence of governed ADD_NODE commands as ONE revision of a DRAFT (all or nothing).

        PC-2b.3 materializes an import through the same command dispatch as a single ADD_NODE: each
        ``step`` receives the ids minted so far (in step order) and returns its ``AddNode`` and the
        provenance entry recorded on the minted node under ``provenance["import"]`` (never content,
        excluded from every digest). Any invalid step raises and the caller's transaction rolls back.
        """
        if not can_author(actor.kind, actor.role):
            raise WBSGovernanceForbiddenError("only a human user or admin can edit a WBS change set")
        await self._scoped(change_set_id, project_id, tenant_id)
        try:
            change_set = await self.repo.bump_revision(change_set_id, tenant_id, expected_revision)
        except RevisionConflictError as exc:
            current = await self._scoped(change_set_id, project_id, tenant_id)
            raise ChangeSetRevisionConflictError(str(exc), current.revision) from exc
        except GovernanceRuleError as exc:
            current = await self._scoped(change_set_id, project_id, tenant_id)
            raise ChangeSetStateError(str(exc), current.status) from exc
        nodes = await self._nodes(change_set.id)
        minted: list[UUID] = []
        try:
            for step in steps:
                command, provenance = step(tuple(minted))
                if not isinstance(command, AddNode):
                    raise GovernanceRuleError("an add sequence contains ADD_NODE commands only")
                [node_id] = await self._dispatch(change_set, command, preloaded=nodes)
                nodes[node_id].provenance = {**nodes[node_id].provenance, "import": dict(provenance)}
                minted.append(node_id)
            await self.session.flush()
        except (GovernanceRuleError, TypeError, ValueError) as exc:
            raise WBSChangeSetInvalidError(str(exc)) from exc
        return CommandResult(revision=change_set.revision, node_ids=minted)

    async def _record_provenance(self, change_set_id: UUID, node_ids: Sequence[UUID], entry: Mapping[str, Any]) -> None:
        rows = await self.session.execute(
            select(WBSChangeSetNodeORM).where(
                WBSChangeSetNodeORM.change_set_id == change_set_id, WBSChangeSetNodeORM.node_id.in_(list(node_ids)))
        )
        for node in rows.scalars():
            current = dict(node.provenance or {})
            current["intelligence"] = [*current.get("intelligence", []), dict(entry)]
            node.provenance = current
        await self.session.flush()

    async def _dispatch(self, change_set: WBSChangeSetORM, command: EditCommand, *,
                        preloaded: dict[UUID, WBSChangeSetNodeORM] | None = None) -> list[UUID]:
        nodes = preloaded if preloaded is not None else await self._nodes(change_set.id)

        def node(node_id: UUID) -> WBSChangeSetNodeORM:
            found = nodes.get(node_id)
            if found is None:
                raise GovernanceRuleError(f"candidate node {node_id} is not in this change set")
            return found

        def parent(parent_id: UUID | None) -> UUID | None:
            if parent_id is not None:
                node(parent_id)
            return parent_id

        if isinstance(command, AddNode):
            spec = _validated_spec(command.spec)
            parent_id = parent(command.parent_id)
            new_id = uuid4()
            nodes[new_id] = self._new_node(change_set, spec, node_id=new_id, origin_kind=CandidateOriginKind.MINTED,
                                           parent_id=parent_id, sort_order=len(nodes) + 1, provenance={"command": "ADD_NODE"})
            self._place(nodes, parent_id, [new_id], command.position)
            return [new_id]

        if isinstance(command, UpdateNode):
            target = node(command.node_id)
            unknown = set(command.changes) - _EDITABLE_FIELDS
            if unknown or not command.changes:
                raise GovernanceRuleError(
                    f"UPDATE_NODE edits {sorted(_EDITABLE_FIELDS)}; use RECODE / MOVE / REORDER for the rest"
                    + (f" (not {sorted(unknown)})" if unknown else ""))
            changes = dict(command.changes)
            if "name" in changes:
                target.name = _name(changes["name"])
            if "control_level" in changes:
                target.control_level = validate_control_level(changes["control_level"]).value
            if "decomposition_kind" in changes:
                target.decomposition_kind = validate_decomposition_kind(changes["decomposition_kind"])
            if "dictionary" in changes:
                target.dictionary = None if changes["dictionary"] is None else normalize_dictionary(changes["dictionary"])
            return [target.node_id]

        if isinstance(command, RecodeNode):
            target = node(command.node_id)
            target.code = _nfc_code(command.code)
            return [target.node_id]

        if isinstance(command, MoveNode):
            target = node(command.node_id)
            new_parent = parent(command.parent_id)
            if new_parent is not None and new_parent in self._subtree(nodes, target.node_id):
                raise GovernanceRuleError("a WBS node cannot move under itself or its descendants")
            old_parent = target.parent_id
            self._place(nodes, new_parent, [target.node_id], command.position)
            if old_parent != new_parent:
                self._renumber(nodes, old_parent)
            return [target.node_id]

        if isinstance(command, ReorderNode):
            target = node(command.node_id)
            self._place(nodes, target.parent_id, [target.node_id], command.position)
            return [target.node_id]

        if isinstance(command, RemoveNode):
            return await self._remove(change_set, nodes, command.node_id)

        if isinstance(command, SplitNode):
            return await self._split(change_set, nodes, command)

        if isinstance(command, MergeNodes):
            return await self._merge(change_set, nodes, command)

        if isinstance(command, AdoptLegacyNode):
            return await self._adopt(change_set, nodes, command)

        raise GovernanceRuleError(f"unknown WBS edit command {type(command).__name__}")  # pragma: no cover

    async def _remove(self, change_set: WBSChangeSetORM, nodes: dict[UUID, WBSChangeSetNodeORM], node_id: UUID) -> list[UUID]:
        target = nodes.get(node_id)
        if target is None:
            # Explicitly retiring a legacy row that was never adopted (first baseline only).
            if change_set.base_baseline_id is not None or node_id in await self._retired_ids(change_set.id):
                raise GovernanceRuleError(f"candidate node {node_id} is not in this change set")
            await self._retire(change_set, node_id, RetirementDisposition.REMOVED, None)
            return [node_id]
        if any(n.parent_id == node_id for n in nodes.values()):
            raise GovernanceRuleError("remove or move the children of a WBS node before removing it")
        parent_id = target.parent_id
        await self.session.delete(target)
        await self.session.flush()
        del nodes[node_id]
        self._renumber(nodes, parent_id)
        if target.origin_kind != CandidateOriginKind.MINTED.value:
            await self._retire(change_set, node_id, RetirementDisposition.REMOVED, CandidateOriginKind(target.origin_kind))
        return [node_id]

    async def _split(self, change_set: WBSChangeSetORM, nodes: dict[UUID, WBSChangeSetNodeORM], command: SplitNode) -> list[UUID]:
        source = nodes.get(command.source_id)
        if source is None:
            raise GovernanceRuleError(f"candidate node {command.source_id} is not in this change set")
        if source.origin_kind == CandidateOriginKind.MINTED.value:
            raise GovernanceRuleError("a minted node has no approved identity to split: edit it instead")
        if len(command.targets) < 2:
            raise GovernanceRuleError("a split needs at least two targets")
        specs = [_validated_spec(spec) for spec in command.targets]
        children = sorted((n for n in nodes.values() if n.parent_id == source.node_id), key=lambda n: n.sort_order)
        assignment = dict(command.child_targets)
        unassigned = [c.node_id for c in children if c.node_id not in assignment]
        if unassigned or set(assignment) - {c.node_id for c in children}:
            raise GovernanceRuleError("ambiguous split: assign every child of the source (and only those) to a target")
        if any(not 0 <= index < len(specs) for index in assignment.values()):
            raise GovernanceRuleError("a split child is assigned to a target that does not exist")
        parent_id, position = source.parent_id, source.sort_order
        target_ids = [uuid4() for _ in specs]
        for target_id, spec in zip(target_ids, specs, strict=True):
            nodes[target_id] = self._new_node(
                change_set, spec, node_id=target_id, origin_kind=CandidateOriginKind.MINTED, parent_id=parent_id,
                sort_order=len(nodes) + 1, provenance={"command": "SPLIT_NODE", "source_node_id": str(source.node_id)})
        await self.session.flush()
        for child in children:  # keep the children's relative order under their new parent
            self._place(nodes, target_ids[assignment[child.node_id]], [child.node_id], None)
        await self.session.delete(source)
        await self.session.flush()
        del nodes[source.node_id]
        self._place(nodes, parent_id, target_ids, position)
        await self._retire(change_set, source.node_id, RetirementDisposition.SPLIT, CandidateOriginKind(source.origin_kind))
        for target_id in target_ids:
            self.session.add(WBSChangeSetLineageORM(
                change_set_id=change_set.id, kind=LineageKind.SPLIT.value, source_node_id=source.node_id,
                target_node_id=target_id, tenant_id=change_set.tenant_id, project_id=change_set.project_id))
        return target_ids

    async def _merge(self, change_set: WBSChangeSetORM, nodes: dict[UUID, WBSChangeSetNodeORM], command: MergeNodes) -> list[UUID]:
        source_ids = list(dict.fromkeys(command.source_ids))
        if len(source_ids) < 2:
            raise GovernanceRuleError("a merge needs at least two distinct sources")
        sources = []
        for source_id in source_ids:
            source = nodes.get(source_id)
            if source is None:
                raise GovernanceRuleError(f"candidate node {source_id} is not in this change set")
            if source.origin_kind == CandidateOriginKind.MINTED.value:
                raise GovernanceRuleError("a minted node has no approved identity to merge: edit it instead")
            sources.append(source)
        subtrees = {s.node_id: self._subtree(nodes, s.node_id) for s in sources}
        for source in sources:
            if any(source.node_id in subtrees[other] for other in subtrees if other != source.node_id):
                raise GovernanceRuleError("merge sources cannot contain one another")
        first = sources[0]
        parent_id = first.parent_id if command.parent_id is _UNSET else command.parent_id
        if parent_id is not None:
            if parent_id not in nodes:
                raise GovernanceRuleError(f"candidate node {parent_id} is not in this change set")
            if any(parent_id in subtree for subtree in subtrees.values()):
                raise GovernanceRuleError("a merged node cannot be placed inside one of its sources")
        position = command.position if command.position is not None else (
            first.sort_order if parent_id == first.parent_id else None)
        spec = _validated_spec(command.target)
        target_id = uuid4()
        nodes[target_id] = self._new_node(
            change_set, spec, node_id=target_id, origin_kind=CandidateOriginKind.MINTED, parent_id=parent_id,
            sort_order=len(nodes) + 1,
            provenance={"command": "MERGE_NODES", "source_node_ids": [str(s) for s in source_ids]})
        await self.session.flush()
        children = [c for s in sources for c in sorted(
            (n for n in nodes.values() if n.parent_id == s.node_id), key=lambda n: n.sort_order)]
        for child in children:  # the merged node takes over the sources' children, in order
            self._place(nodes, target_id, [child.node_id], None)
        old_parents = {s.parent_id for s in sources}
        for source in sources:
            await self.session.delete(source)
            del nodes[source.node_id]
        await self.session.flush()
        self._place(nodes, parent_id, [target_id], position)
        for old_parent in old_parents - {parent_id}:
            self._renumber(nodes, old_parent)
        for source in sources:
            await self._retire(change_set, source.node_id, RetirementDisposition.MERGED,
                               CandidateOriginKind(source.origin_kind))
            self.session.add(WBSChangeSetLineageORM(
                change_set_id=change_set.id, kind=LineageKind.MERGE.value, source_node_id=source.node_id,
                target_node_id=target_id, tenant_id=change_set.tenant_id, project_id=change_set.project_id))
        return [target_id]

    async def _adopt(self, change_set: WBSChangeSetORM, nodes: dict[UUID, WBSChangeSetNodeORM], command: AdoptLegacyNode) -> list[UUID]:
        if change_set.base_baseline_id is not None:
            raise GovernanceRuleError("only a first baseline adopts legacy rows")
        if command.legacy_node_id in nodes:
            raise GovernanceRuleError("this legacy row is already in the candidate")
        if command.legacy_node_id in await self._retired_ids(change_set.id):
            raise GovernanceRuleError("this legacy row is already retired in this change set")
        live = await self.session.scalar(
            select(WBSNodeORM).where(
                WBSNodeORM.id == command.legacy_node_id,
                WBSNodeORM.project_id == change_set.project_id,
                WBSNodeORM.tenant_id == change_set.tenant_id,
            )
        )
        if live is None:
            raise GovernanceRuleError(f"{command.legacy_node_id} is not a legacy live row of this project")
        parent_id = command.parent_id
        if parent_id is not None and parent_id not in nodes:
            raise GovernanceRuleError(f"candidate node {parent_id} is not in this change set")
        spec = NodeSpec(name=live.name, code=_nfc_code(live.code), control_level=live.control_level,
                        decomposition_kind=live.decomposition_kind, dictionary=live.dictionary)
        nodes[live.id] = self._new_node(
            change_set, spec, node_id=live.id, origin_kind=CandidateOriginKind.ADOPTED_LEGACY, parent_id=parent_id,
            sort_order=len(nodes) + 1, provenance={"command": "ADOPT_LEGACY_NODE"})
        self._place(nodes, parent_id, [live.id], command.position)
        return [live.id]

    # ------------------------------------------------------------------ validation
    async def _violations(self, detail: ChangeSetDetail, *, legacy_complete: bool) -> list[str]:
        change_set = detail.change_set
        base_ids = None if change_set.base_baseline_id is None else await self._base_ids(change_set.base_baseline_id)
        legacy_ids = (
            await self._legacy_ids(change_set.project_id, change_set.tenant_id) if base_ids is None else frozenset()
        )
        # PC-2b.1 (ADR-029 section 9): pins resolve against the locked profile catalog; a
        # non-core decomposition_kind must belong to a pinned profile that declares the term.
        profile_terms: dict[str, frozenset[str]] = {}
        pin_violations: list[str] = []
        if change_set.profile_refs:
            try:
                profile_terms = default_catalog().resolve(change_set.profile_refs).terms_by_namespace()
            except ProfileCompositionError as exc:
                pin_violations.append(f"invalid profile pin: {exc}")
        violations = pin_violations + validate_governed_submission(
            [_candidate(node) for node in detail.nodes],
            [LineageEdge(edge.kind, edge.source_node_id, edge.target_node_id) for edge in detail.lineage],
            [Retirement(r.node_id, r.disposition, r.source) for r in detail.retirements],
            base_node_ids=base_ids,
            legacy_node_ids=legacy_ids,
            legacy_complete=legacy_complete,
            profile_refs=list(change_set.profile_refs or []),
            profile_terms=profile_terms,
        )
        try:
            normalize_evidence_refs(change_set.evidence_refs or [])
        except GovernanceRuleError as exc:
            violations.append(str(exc))
        minted = [node.node_id for node in detail.nodes if node.origin_kind == CandidateOriginKind.MINTED.value]
        if minted:
            reused = set((await self.session.execute(
                select(WBSBaselineNodeORM.node_id).where(WBSBaselineNodeORM.node_id.in_(minted)))).scalars())
            reused |= set((await self.session.execute(
                select(WBSNodeORM.id).where(WBSNodeORM.id.in_(minted)))).scalars())
            violations += [f"{node_id}: a minted id was already used" for node_id in sorted(reused, key=str)]
        return violations

    # ------------------------------------------------------------------ lifecycle
    async def submit(
        self, *, project_id: UUID, change_set_id: UUID, tenant_id: UUID, actor: Actor, expected_revision: int
    ) -> str:
        """Validate the whole candidate, record the legacy dispositions and freeze the digest."""
        if not can_author(actor.kind, actor.role):
            raise WBSGovernanceForbiddenError("only a human user or admin can submit a WBS change set (never AI)")
        await self._require_project(project_id, tenant_id, lock=True)
        change_set = await self._scoped(change_set_id, project_id, tenant_id, lock=True)
        if change_set.status != ChangeSetStatus.DRAFT.value:
            raise ChangeSetStateError(f"a {change_set.status} change set cannot be submitted", change_set.status)
        if change_set.revision != expected_revision:
            raise ChangeSetRevisionConflictError(f"WBS change set is at revision {change_set.revision}", change_set.revision)
        current = await self.repo.current_baseline(project_id, tenant_id)
        if (current.id if current else None) != change_set.base_baseline_id:
            raise ChangeSetStaleError(change_set.id)
        detail = await self._detail(change_set)
        violations = await self._violations(detail, legacy_complete=False)
        if violations:
            raise WBSChangeSetInvalidError("the WBS change set cannot be submitted", violations)
        if change_set.base_baseline_id is None:
            accounted = {node.node_id for node in detail.nodes} | {r.node_id for r in detail.retirements}
            for legacy_id in sorted(await self._legacy_ids(project_id, tenant_id) - accounted, key=str):
                await self._retire(change_set, legacy_id, RetirementDisposition.RETIRED_ON_BASELINE, None)
            await self.session.flush()
            detail = await self._detail(change_set)
        digest = self.repo.compute_change_set_digest(detail, change_set.revision)
        change_set.status = ChangeSetStatus.SUBMITTED.value
        change_set.submitted_revision = change_set.revision
        change_set.submitted_digest = digest
        change_set.submitted_by = actor.user_id
        change_set.submitted_at = datetime.now(UTC)
        await self.session.flush()
        await self._event(
            project_id=project_id, tenant_id=tenant_id, event_type=EVENT_SUBMITTED, actor=actor,
            payload={
                "change_set_id": str(change_set.id), "base_baseline_id": _str(change_set.base_baseline_id),
                "submitted_revision": change_set.revision, "change_set_digest": digest,
                "node_count": len(detail.nodes), "retired_count": len(detail.retirements),
                "origin": change_set.origin, "entry_mode": change_set.entry_mode,
            },
        )
        return digest

    async def reopen(self, *, project_id: UUID, change_set_id: UUID, tenant_id: UUID, actor: Actor) -> int:
        """SUBMITTED -> DRAFT (proposer or admin): new revision, digest and auto-dispositions cleared."""
        await self._scoped(change_set_id, project_id, tenant_id)
        try:
            revision = await self.repo.reopen(change_set_id, tenant_id, actor=actor)
        except GovernanceRuleError as exc:
            current = await self._scoped(change_set_id, project_id, tenant_id)
            if current.status == ChangeSetStatus.SUBMITTED.value:
                raise WBSGovernanceForbiddenError(str(exc)) from exc
            raise ChangeSetStateError(str(exc), current.status) from exc
        await self.session.execute(
            delete(WBSChangeSetRetirementORM).where(
                WBSChangeSetRetirementORM.change_set_id == change_set_id,
                WBSChangeSetRetirementORM.disposition == RetirementDisposition.RETIRED_ON_BASELINE.value,
            )
        )
        return revision

    async def withdraw(self, *, project_id: UUID, change_set_id: UUID, tenant_id: UUID, actor: Actor) -> None:
        """DRAFT | SUBMITTED -> WITHDRAWN (proposer or admin). Terminal; history is kept."""
        current = await self._scoped(change_set_id, project_id, tenant_id)
        if current.status not in (ChangeSetStatus.DRAFT.value, ChangeSetStatus.SUBMITTED.value):
            raise ChangeSetStateError(f"a {current.status} change set cannot be withdrawn", current.status)
        try:
            await self.repo.withdraw(change_set_id, tenant_id, actor=actor)
        except GovernanceRuleError as exc:
            raise WBSGovernanceForbiddenError(str(exc)) from exc

    async def _decision_target(
        self, *, project_id: UUID, change_set_id: UUID, tenant_id: UUID, actor: Actor, expected_revision: int,
        expected_digest: str, action: str,
    ) -> tuple[WBSChangeSetORM, bool]:
        if not can_decide(actor.kind, actor.role):
            raise WBSGovernanceForbiddenError(f"{action} requires a human admin (never AI, api or service)")
        # FOR UPDATE until commit: the live-write guard takes KEY SHARE on this row, so a racing
        # live write waits for an apply and then sees its baseline.
        await self._require_project(project_id, tenant_id, lock=True)
        change_set = await self._scoped(change_set_id, project_id, tenant_id, lock=True)
        if change_set.status == ChangeSetStatus.STALE.value:
            raise ChangeSetStaleError(change_set.id)
        if change_set.status != ChangeSetStatus.SUBMITTED.value:
            raise ChangeSetStateError(f"a {change_set.status} change set cannot be decided", change_set.status)
        if change_set.revision != expected_revision or change_set.submitted_revision != expected_revision:
            raise ChangeSetRevisionConflictError(
                f"the reviewed revision {expected_revision} is not the submitted revision {change_set.submitted_revision}",
                change_set.revision)
        if change_set.submitted_digest != expected_digest:
            raise ChangeSetDigestMismatchError("the reviewed digest is not the submitted digest")
        assert change_set.submitted_by is not None
        try:
            self_approved = self_approval(
                submitter=change_set.submitted_by, approver=actor.user_id,
                require_distinct_approver=await self._tenant_requires_distinct_approver(tenant_id))
        except GovernanceRuleError as exc:
            raise WBSGovernanceForbiddenError(str(exc)) from exc
        return change_set, self_approved

    async def reject(
        self, *, project_id: UUID, change_set_id: UUID, tenant_id: UUID, actor: Actor, expected_revision: int,
        expected_digest: str, reason: str,
    ) -> None:
        """SUBMITTED -> REJECTED by a human admin with a reason. Immutable history; never applies."""
        if not isinstance(reason, str) or not reason.strip():
            raise WBSChangeSetInvalidError("a rejection needs a reason")
        change_set, self_approved = await self._decision_target(
            project_id=project_id, change_set_id=change_set_id, tenant_id=tenant_id, actor=actor,
            expected_revision=expected_revision, expected_digest=expected_digest, action="reject")
        now = datetime.now(UTC)
        change_set.status = ChangeSetStatus.REJECTED.value
        change_set.decided_by = actor.user_id
        change_set.decided_at = now
        change_set.decided_self_approval = self_approved
        change_set.decision_reason = reason.strip()
        change_set.closed_at = now
        await self.session.flush()
        await self._event(
            project_id=project_id, tenant_id=tenant_id, event_type=EVENT_REJECTED, actor=actor,
            payload={"change_set_id": str(change_set.id), "change_set_digest": change_set.submitted_digest,
                     "submitted_revision": change_set.submitted_revision, "reason": reason.strip(),
                     "self_decided": self_approved},
        )

    async def approve(
        self, *, project_id: UUID, change_set_id: UUID, tenant_id: UUID, actor: Actor, expected_revision: int,
        expected_digest: str,
    ) -> ApplyResult:
        """Approve = apply, in the caller's transaction. Any exception must roll it back."""
        change_set, self_approved = await self._decision_target(
            project_id=project_id, change_set_id=change_set_id, tenant_id=tenant_id, actor=actor,
            expected_revision=expected_revision, expected_digest=expected_digest, action="approve")
        current = await self.repo.current_baseline(project_id, tenant_id)
        if (current.id if current else None) != change_set.base_baseline_id:
            raise ChangeSetStaleError(change_set.id)
        detail = await self._detail(change_set)
        assert change_set.submitted_revision is not None and change_set.submitted_digest is not None
        if self.repo.compute_change_set_digest(detail, change_set.submitted_revision) != change_set.submitted_digest:
            raise ChangeSetDigestMismatchError("the candidate no longer hashes to the submitted digest")
        candidate_ids = {node.node_id for node in detail.nodes}
        retired_ids = {r.node_id for r in detail.retirements}
        # Lock every live row first: an in-flight (non-governed) edit commits before the checks
        # below read what this apply is about to replace, never after them.
        live_ids = await self._lock_live_rows(project_id, tenant_id)
        if change_set.base_baseline_id is None:
            # The legacy rows the reviewer saw dispositioned must be exactly the live ones, unchanged.
            adopted = {n.node_id for n in detail.nodes if n.origin_kind == CandidateOriginKind.ADOPTED_LEGACY.value}
            if live_ids != adopted | retired_ids:
                raise LegacyWBSChangedError("legacy rows were added or removed")
            for retirement in detail.retirements:
                if await self._live_snapshot(retirement.node_id) != retirement.snapshot:
                    raise LegacyWBSChangedError(f"legacy row {retirement.node_id} was edited")
        elif live_ids != await self._base_ids(change_set.base_baseline_id):
            raise WBSLiveTreeDivergedError(project_id, "the live WBS is not the base baseline")
        violations = await self._violations(detail, legacy_complete=True)
        if violations:
            raise WBSChangeSetInvalidError("the WBS change set is no longer valid", violations)
        raci, bom = await self.live.linked_node_counts(retired_ids)
        if raci or bom:
            raise RetiredNodesLinkedError(raci, bom)

        digest_nodes = [candidate_digest_node(node) for node in detail.nodes]
        approved_tree_digest = tree_digest(project_id, digest_nodes)
        now = datetime.now(UTC)
        # The authority row comes FIRST: the wbs_nodes guard admits live writes only in the
        # transaction that holds the uncommitted baseline of this SUBMITTED change set (chained
        # to its base); the setting below is merely the correlation that names it.
        baseline = WBSBaselineORM(
            id=uuid4(), tenant_id=tenant_id, project_id=project_id,
            baseline_no=(current.baseline_no if current else 0) + 1, parent_baseline_id=change_set.base_baseline_id,
            source_change_set_id=change_set.id, tree_digest=approved_tree_digest,
            change_set_digest=change_set.submitted_digest, node_count=len(detail.nodes), approved_by=actor.user_id,
            approved_by_kind="human", self_approved=self_approved, profile_refs=list(change_set.profile_refs or []),
            applied_at=now,
        )
        self.session.add(baseline)
        await self.session.flush()
        await self.session.execute(text("SELECT set_config(:name, :value, true)"),
                                   {"name": APPLY_SETTING, "value": str(change_set.id)})
        await self.live.apply_governed_tree(project_id, tenant_id, nodes=digest_nodes, retired_ids=retired_ids)
        live_rows = (await self.session.execute(
            select(WBSNodeORM)
            .where(WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id)
            .execution_options(populate_existing=True)
        )).scalars().all()
        live_digest = tree_digest(project_id, [
            DigestNode(row.id, row.parent_id, row.sort_order, row.code, row.name, row.decomposition_kind,
                       row.control_level, row.dictionary) for row in live_rows])
        if live_digest != approved_tree_digest or {row.id for row in live_rows} != candidate_ids:
            raise WBSLiveTreeDivergedError(project_id, "the materialized live WBS differs from the approved tree")

        for node in detail.nodes:
            self.session.add(WBSBaselineNodeORM(
                baseline_id=baseline.id, node_id=node.node_id, tenant_id=tenant_id, project_id=project_id,
                parent_id=node.parent_id, sort_order=node.sort_order, code=node.code, name=node.name,
                control_level=node.control_level, decomposition_kind=node.decomposition_kind, dictionary=node.dictionary,
            ))
        await self.session.flush()
        change_set.status = ChangeSetStatus.APPLIED.value
        change_set.decided_by = actor.user_id
        change_set.decided_at = now
        change_set.decided_self_approval = self_approved
        change_set.closed_at = now
        await self.session.flush()
        stale_ids = list((await self.session.execute(
            update(WBSChangeSetORM)
            .where(
                WBSChangeSetORM.project_id == project_id,
                WBSChangeSetORM.tenant_id == tenant_id,
                WBSChangeSetORM.id != change_set.id,
                WBSChangeSetORM.status.in_([ChangeSetStatus.DRAFT.value, ChangeSetStatus.SUBMITTED.value]),
            )
            .values(status=ChangeSetStatus.STALE.value, closed_at=now)
            .returning(WBSChangeSetORM.id)
            .execution_options(synchronize_session=False)
        )).scalars())
        retired = [
            {"node_id": str(r.node_id), "disposition": r.disposition, "source": r.source}
            for r in sorted(detail.retirements, key=lambda r: str(r.node_id))
        ]
        event_id = await self._event(
            project_id=project_id, tenant_id=tenant_id, event_type=EVENT_APPLIED, actor=actor,
            payload={
                "tenant_id": str(tenant_id), "project_id": str(project_id), "change_set_id": str(change_set.id),
                "base_baseline_id": _str(change_set.base_baseline_id), "baseline_id": str(baseline.id),
                "baseline_no": baseline.baseline_no, "tree_digest": approved_tree_digest,
                "change_set_digest": change_set.submitted_digest, "approved_by": str(actor.user_id),
                "self_approved": self_approved, "evidence_refs": list(change_set.evidence_refs or []),
                "profile_refs": list(change_set.profile_refs or []), "applied_at": now.isoformat(),
                "node_count": len(detail.nodes), "retired": retired,
                "stale_change_set_ids": [str(i) for i in sorted(stale_ids, key=str)],
            },
        )
        return ApplyResult(
            change_set_id=change_set.id, baseline_id=baseline.id, baseline_no=baseline.baseline_no,
            tree_digest=approved_tree_digest, change_set_digest=change_set.submitted_digest,
            self_approved=self_approved, event_id=event_id, retired=retired, stale_change_set_ids=stale_ids,
            applied_at=now,
        )


def enqueue_baseline_snapshot(*, project_id: UUID, tenant_id: UUID, result: ApplyResult) -> bool:
    """AFTER commit: a ProjectSnapshot (downstream projection, never baseline authority).

    Fail-open: a dispatch failure never undoes an already valid baseline; the daily snapshot job
    still covers the project.
    """
    from src.temporal.application.project_snapshot_trigger import enqueue_project_snapshot

    try:
        enqueue_project_snapshot(
            project_id=project_id, tenant_id=require_tenant_id(tenant_id), trigger=SnapshotTrigger.BASELINE_CHANGED,
            source_event_id=result.event_id,
        )
    except Exception:  # noqa: BLE001 - snapshot dispatch must not affect an applied baseline.
        logger.warning("wbs_baseline_snapshot_enqueue_failed", project_id=str(project_id),
                       baseline_id=str(result.baseline_id), event_id=str(result.event_id), exc_info=True)
        return False
    return True


def _str(value: UUID | None) -> str | None:
    return None if value is None else str(value)


__all__ = [
    "APPLY_SETTING",
    "EVENT_APPLIED",
    "EVENT_REJECTED",
    "EVENT_SUBMITTED",
    "AddNode",
    "AdoptLegacyNode",
    "ApplyResult",
    "ChangeSetDigestMismatchError",
    "ChangeSetRevisionConflictError",
    "ChangeSetStaleError",
    "ChangeSetStateError",
    "CommandResult",
    "EditCommand",
    "LegacyWBSChangedError",
    "MergeNodes",
    "MoveNode",
    "NodeSpec",
    "RecodeNode",
    "RemoveNode",
    "ReorderNode",
    "RetiredNodesLinkedError",
    "SplitNode",
    "UpdateNode",
    "WBSChangeSetInvalidError",
    "WBSChangeSetNotFoundError",
    "WBSGovernanceForbiddenError",
    "WBSGovernedChangeService",
    "WBSProjectNotFoundError",
    "enqueue_baseline_snapshot",
]
