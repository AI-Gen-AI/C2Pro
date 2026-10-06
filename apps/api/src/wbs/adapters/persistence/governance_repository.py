"""WBS governance persistence (PC-2a.1 #895, ADR-029).

Reads for the authority resolver and the governance read API, plus the DRAFT-side
operations a change set needs (create, edit the candidate tree, lineage, submit, reopen,
withdraw, stale). HTTP exposure of the drafting operations, approve = apply, and reader
enforcement are PC-2a.2 (#896) / PC-2a.3 (#897): this module deliberately has NO operation
that creates a baseline or mutates the live ``wbs_nodes`` tree.

Every query is scoped by tenant AND project in the application: the API connects as the
table owner (BYPASSRLS), so RLS is defence in depth, not the primary filter. The database
re-enforces the governance invariants with constraints and triggers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineNodeORM,
    WBSBaselineORM,
    WBSChangeSetLineageORM,
    WBSChangeSetNodeORM,
    WBSChangeSetORM,
)
from src.wbs.adapters.persistence.models import WBSNodeORM
from src.wbs.domain.digest import (
    DigestNode,
    LineageEdge,
    change_set_digest,
    normalize_dictionary,
    normalize_profile_ref,
    tree_digest,
)
from src.wbs.domain.governance import (
    OPEN_STATUSES,
    ActorKind,
    BaselineRef,
    CandidateNode,
    CandidateOriginKind,
    ChangeSetOrigin,
    ChangeSetStatus,
    EntryMode,
    GovernanceRuleError,
    LineageKind,
    WBSAuthority,
    can_author,
    can_withdraw_or_reopen,
    require_transition,
    resolve_authority,
    validate_control_level,
    validate_decomposition_kind,
    validate_for_submit,
)


class ChangeSetNotFoundError(LookupError):
    """No change set with this id in the tenant's project."""


class RevisionConflictError(GovernanceRuleError):
    """The change set is no longer the DRAFT revision the caller edited (optimistic lock)."""


@dataclass(frozen=True)
class Actor:
    """The session identity performing a governance operation (never client-supplied)."""

    user_id: UUID
    kind: ActorKind
    role: str | None


@dataclass(frozen=True)
class ChangeSetDetail:
    change_set: WBSChangeSetORM
    nodes: list[WBSChangeSetNodeORM] = field(default_factory=list)
    lineage: list[WBSChangeSetLineageORM] = field(default_factory=list)


@dataclass(frozen=True)
class BaselineDetail:
    baseline: WBSBaselineORM
    nodes: list[WBSBaselineNodeORM]

    @property
    def recomputed_tree_digest(self) -> str:
        return tree_digest(self.baseline.project_id, (baseline_digest_node(node) for node in self.nodes))


def candidate_digest_node(node: WBSChangeSetNodeORM) -> DigestNode:
    return DigestNode(
        node_id=node.node_id,
        parent_id=node.parent_id,
        sort_order=node.sort_order,
        code=node.code,
        name=node.name,
        decomposition_kind=node.decomposition_kind,
        control_level=node.control_level,
        dictionary=node.dictionary,
    )


def baseline_digest_node(node: WBSBaselineNodeORM) -> DigestNode:
    return DigestNode(
        node_id=node.node_id,
        parent_id=node.parent_id,
        sort_order=node.sort_order,
        code=node.code,
        name=node.name,
        decomposition_kind=node.decomposition_kind,
        control_level=node.control_level,
        dictionary=node.dictionary,
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _require_proposer_or_admin(change_set: WBSChangeSetORM, actor: Actor, action: str) -> None:
    proposers = (change_set.created_by, change_set.submitted_by)
    if not can_withdraw_or_reopen(actor.kind, actor.role, actor.user_id, proposers=proposers):
        raise GovernanceRuleError(f"only the proposer or a human admin can {action} a WBS change set")


def _governed_dictionary(dictionary: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return None if dictionary is None else normalize_dictionary(dictionary)


class WBSGovernanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ authority
    async def current_baseline(self, project_id: UUID, tenant_id: UUID) -> WBSBaselineORM | None:
        result = await self.session.execute(
            select(WBSBaselineORM)
            .where(WBSBaselineORM.project_id == project_id, WBSBaselineORM.tenant_id == tenant_id)
            .order_by(WBSBaselineORM.baseline_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def authority(self, project_id: UUID, tenant_id: UUID) -> WBSAuthority:
        """The single canonical, DERIVED authority of a project's WBS."""
        baseline = await self.current_baseline(project_id, tenant_id)
        live = await self.session.scalar(
            select(func.count())
            .select_from(WBSNodeORM)
            .where(WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id)
        )
        open_sets = await self.session.scalar(
            select(func.count())
            .select_from(WBSChangeSetORM)
            .where(
                WBSChangeSetORM.project_id == project_id,
                WBSChangeSetORM.tenant_id == tenant_id,
                WBSChangeSetORM.status.in_([status.value for status in OPEN_STATUSES]),
            )
        )
        ref = (
            BaselineRef(
                baseline_id=baseline.id,
                baseline_no=baseline.baseline_no,
                tree_digest=baseline.tree_digest,
                applied_at=baseline.applied_at,
            )
            if baseline is not None
            else None
        )
        return resolve_authority(current_baseline=ref, live_node_count=int(live or 0), open_change_sets=int(open_sets or 0))

    # ------------------------------------------------------------------ change-set reads
    async def list_change_sets(
        self, project_id: UUID, tenant_id: UUID, statuses: Iterable[ChangeSetStatus] | None = None
    ) -> list[WBSChangeSetORM]:
        query = select(WBSChangeSetORM).where(
            WBSChangeSetORM.project_id == project_id, WBSChangeSetORM.tenant_id == tenant_id
        )
        if statuses is not None:
            query = query.where(WBSChangeSetORM.status.in_([ChangeSetStatus(s).value for s in statuses]))
        result = await self.session.execute(query.order_by(WBSChangeSetORM.created_at.desc(), WBSChangeSetORM.id))
        return list(result.scalars().all())

    async def get_change_set(self, change_set_id: UUID, project_id: UUID, tenant_id: UUID) -> ChangeSetDetail | None:
        change_set = await self.session.scalar(
            select(WBSChangeSetORM)
            .where(
                WBSChangeSetORM.id == change_set_id,
                WBSChangeSetORM.project_id == project_id,
                WBSChangeSetORM.tenant_id == tenant_id,
            )
            .execution_options(populate_existing=True)
        )
        if change_set is None:
            return None
        nodes = await self.session.execute(
            select(WBSChangeSetNodeORM)
            .where(WBSChangeSetNodeORM.change_set_id == change_set_id, WBSChangeSetNodeORM.tenant_id == tenant_id)
            .order_by(WBSChangeSetNodeORM.parent_id.nulls_first(), WBSChangeSetNodeORM.sort_order)
            .execution_options(populate_existing=True)
        )
        lineage = await self.session.execute(
            select(WBSChangeSetLineageORM)
            .where(WBSChangeSetLineageORM.change_set_id == change_set_id, WBSChangeSetLineageORM.tenant_id == tenant_id)
            .order_by(WBSChangeSetLineageORM.kind, WBSChangeSetLineageORM.source_node_id)
            .execution_options(populate_existing=True)
        )
        return ChangeSetDetail(change_set, list(nodes.scalars().all()), list(lineage.scalars().all()))

    def compute_change_set_digest(self, detail: ChangeSetDetail, revision: int) -> str:
        change_set = detail.change_set
        return change_set_digest(
            project_id=change_set.project_id,
            change_set_id=change_set.id,
            base_baseline_id=change_set.base_baseline_id,
            submitted_revision=revision,
            nodes=[candidate_digest_node(node) for node in detail.nodes],
            lineage=[LineageEdge(edge.kind, edge.source_node_id, edge.target_node_id) for edge in detail.lineage],
            profile_refs=list(change_set.profile_refs or []),
            evidence_refs=list(change_set.evidence_refs or []),
        )

    # ------------------------------------------------------------------ baseline reads
    async def list_baselines(self, project_id: UUID, tenant_id: UUID) -> list[WBSBaselineORM]:
        result = await self.session.execute(
            select(WBSBaselineORM)
            .where(WBSBaselineORM.project_id == project_id, WBSBaselineORM.tenant_id == tenant_id)
            .order_by(WBSBaselineORM.baseline_no)
        )
        return list(result.scalars().all())

    async def _baseline_detail(self, baseline: WBSBaselineORM | None) -> BaselineDetail | None:
        if baseline is None:
            return None
        nodes = await self.session.execute(
            select(WBSBaselineNodeORM)
            .where(WBSBaselineNodeORM.baseline_id == baseline.id, WBSBaselineNodeORM.tenant_id == baseline.tenant_id)
            .order_by(WBSBaselineNodeORM.parent_id.nulls_first(), WBSBaselineNodeORM.sort_order)
        )
        return BaselineDetail(baseline, list(nodes.scalars().all()))

    async def get_baseline(self, project_id: UUID, tenant_id: UUID, baseline_no: int) -> BaselineDetail | None:
        baseline = await self.session.scalar(
            select(WBSBaselineORM).where(
                WBSBaselineORM.project_id == project_id,
                WBSBaselineORM.tenant_id == tenant_id,
                WBSBaselineORM.baseline_no == baseline_no,
            )
        )
        return await self._baseline_detail(baseline)

    async def baseline_as_of(self, project_id: UUID, tenant_id: UUID, at: datetime) -> BaselineDetail | None:
        """The approved WBS in force at time ``at``, from immutable history only."""
        baseline = await self.session.scalar(
            select(WBSBaselineORM)
            .where(
                WBSBaselineORM.project_id == project_id,
                WBSBaselineORM.tenant_id == tenant_id,
                WBSBaselineORM.applied_at <= at,
            )
            .order_by(WBSBaselineORM.baseline_no.desc())
            .limit(1)
        )
        return await self._baseline_detail(baseline)

    # ------------------------------------------------------------------ drafting
    async def create_change_set(
        self,
        *,
        project_id: UUID,
        tenant_id: UUID,
        actor: Actor,
        title: str,
        origin: ChangeSetOrigin = ChangeSetOrigin.MANUAL,
        entry_mode: EntryMode | None = None,
        description: str | None = None,
        profile_refs: Sequence[Mapping[str, str]] = (),
        evidence_refs: Sequence[str] = (),
    ) -> WBSChangeSetORM:
        """A new DRAFT against the CURRENT baseline (or none: a first-baseline proposal).

        AI/service actors may only create ``origin=ai`` drafts; they never submit or decide.
        """
        if actor.kind is ActorKind.HUMAN:
            if not can_author(actor.kind, actor.role):
                raise GovernanceRuleError("only a human user or admin can draft a WBS change set")
        elif ChangeSetOrigin(origin) is not ChangeSetOrigin.AI:
            raise GovernanceRuleError("an AI or service actor can only draft origin=ai change sets")
        base = await self.current_baseline(project_id, tenant_id)
        mode = EntryMode(entry_mode) if entry_mode else (
            EntryMode.CHANGE_BASELINE if base is not None else EntryMode.GENERATE
        )
        change_set = WBSChangeSetORM(
            id=uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            base_baseline_id=base.id if base is not None else None,
            origin=ChangeSetOrigin(origin).value,
            entry_mode=mode.value,
            status=ChangeSetStatus.DRAFT.value,
            revision=1,
            title=title,
            description=description,
            profile_refs=[normalize_profile_ref(ref) for ref in profile_refs],
            evidence_refs=list(evidence_refs),
            created_by=actor.user_id,
            created_by_kind=actor.kind.value,
        )
        self.session.add(change_set)
        await self.session.flush()
        return change_set

    async def _bump_draft_revision(self, change_set_id: UUID, tenant_id: UUID, expected_revision: int) -> WBSChangeSetORM:
        """Every candidate edit advances the DRAFT revision exactly once (and row-locks it)."""
        result = await self.session.execute(
            update(WBSChangeSetORM)
            .where(
                WBSChangeSetORM.id == change_set_id,
                WBSChangeSetORM.tenant_id == tenant_id,
                WBSChangeSetORM.status == ChangeSetStatus.DRAFT.value,
                WBSChangeSetORM.revision == expected_revision,
            )
            .values(revision=WBSChangeSetORM.revision + 1)
            .returning(WBSChangeSetORM.id)
            .execution_options(synchronize_session=False)
        )
        if result.scalar_one_or_none() is None:
            await self._raise_not_editable(change_set_id, tenant_id)
        change_set = await self.session.get(WBSChangeSetORM, change_set_id, populate_existing=True)
        assert change_set is not None
        return change_set

    async def _raise_not_editable(self, change_set_id: UUID, tenant_id: UUID) -> None:
        current = await self.session.scalar(
            select(WBSChangeSetORM).where(WBSChangeSetORM.id == change_set_id, WBSChangeSetORM.tenant_id == tenant_id)
        )
        if current is None:
            raise ChangeSetNotFoundError(str(change_set_id))
        if current.status != ChangeSetStatus.DRAFT.value:
            raise GovernanceRuleError(f"WBS change set is {current.status}: only a DRAFT can be edited")
        raise RevisionConflictError(f"WBS change set is at revision {current.revision}, not the one edited")

    async def add_node(
        self,
        change_set_id: UUID,
        tenant_id: UUID,
        *,
        expected_revision: int,
        name: str,
        sort_order: int,
        parent_id: UUID | None = None,
        code: str | None = None,
        keep_node_id: UUID | None = None,
        control_level: str = "none",
        decomposition_kind: str | None = None,
        dictionary: Mapping[str, Any] | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> UUID:
        """Add a candidate node. Without ``keep_node_id`` the SERVER mints the identity.

        ``keep_node_id`` keeps an existing canonical id: from the base baseline, or -- for a
        first baseline only -- an explicitly adopted legacy live node. The database refuses
        anything else, including any attempt to reuse a retired id.
        """
        change_set = await self._bump_draft_revision(change_set_id, tenant_id, expected_revision)
        validate_control_level(control_level)
        validate_decomposition_kind(decomposition_kind)
        if keep_node_id is None:
            node_id, origin_kind = uuid4(), CandidateOriginKind.MINTED
        else:
            node_id = keep_node_id
            origin_kind = (
                CandidateOriginKind.EXISTING
                if change_set.base_baseline_id is not None
                else CandidateOriginKind.ADOPTED_LEGACY
            )
        self.session.add(
            WBSChangeSetNodeORM(
                change_set_id=change_set_id,
                node_id=node_id,
                tenant_id=tenant_id,
                project_id=change_set.project_id,
                parent_id=parent_id,
                sort_order=sort_order,
                code=code,
                name=name,
                control_level=control_level,
                decomposition_kind=decomposition_kind,
                dictionary=_governed_dictionary(dictionary),
                origin_kind=origin_kind.value,
                provenance=dict(provenance or {}),
            )
        )
        await self.session.flush()
        return node_id

    async def update_node(
        self,
        change_set_id: UUID,
        node_id: UUID,
        tenant_id: UUID,
        *,
        expected_revision: int,
        **changes: Any,
    ) -> None:
        """Rename / recode / move / reorder / re-describe a candidate node (identity is kept)."""
        allowed = {"parent_id", "sort_order", "code", "name", "control_level", "decomposition_kind", "dictionary"}
        unknown = set(changes) - allowed
        if unknown:
            raise GovernanceRuleError(f"candidate node fields {sorted(unknown)} cannot be edited")
        await self._bump_draft_revision(change_set_id, tenant_id, expected_revision)
        if "control_level" in changes:
            validate_control_level(changes["control_level"])
        if "decomposition_kind" in changes:
            validate_decomposition_kind(changes["decomposition_kind"])
        if "dictionary" in changes:
            changes["dictionary"] = _governed_dictionary(changes["dictionary"])
        result = await self.session.execute(
            update(WBSChangeSetNodeORM)
            .where(
                WBSChangeSetNodeORM.change_set_id == change_set_id,
                WBSChangeSetNodeORM.node_id == node_id,
                WBSChangeSetNodeORM.tenant_id == tenant_id,
            )
            .values(**changes)
            .returning(WBSChangeSetNodeORM.node_id)
            .execution_options(synchronize_session=False)
        )
        if result.scalar_one_or_none() is None:
            raise GovernanceRuleError(f"candidate node {node_id} is not in this change set")

    async def remove_node(self, change_set_id: UUID, node_id: UUID, tenant_id: UUID, *, expected_revision: int) -> None:
        """Remove a candidate node. A node with candidate children is never removed silently."""
        await self._bump_draft_revision(change_set_id, tenant_id, expected_revision)
        children = await self.session.scalar(
            select(func.count())
            .select_from(WBSChangeSetNodeORM)
            .where(WBSChangeSetNodeORM.change_set_id == change_set_id, WBSChangeSetNodeORM.parent_id == node_id)
        )
        if children:
            raise GovernanceRuleError("remove or move the children of a candidate node before removing it")
        await self.session.execute(
            delete(WBSChangeSetNodeORM).where(
                WBSChangeSetNodeORM.change_set_id == change_set_id,
                WBSChangeSetNodeORM.node_id == node_id,
                WBSChangeSetNodeORM.tenant_id == tenant_id,
            )
        )
        await self.session.flush()

    async def add_lineage(
        self,
        change_set_id: UUID,
        tenant_id: UUID,
        *,
        expected_revision: int,
        kind: LineageKind,
        source_node_id: UUID,
        target_node_id: UUID,
    ) -> None:
        change_set = await self._bump_draft_revision(change_set_id, tenant_id, expected_revision)
        self.session.add(
            WBSChangeSetLineageORM(
                change_set_id=change_set_id,
                kind=LineageKind(kind).value,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                tenant_id=tenant_id,
                project_id=change_set.project_id,
            )
        )
        await self.session.flush()

    async def remove_lineage(
        self,
        change_set_id: UUID,
        tenant_id: UUID,
        *,
        expected_revision: int,
        kind: LineageKind,
        source_node_id: UUID,
        target_node_id: UUID,
    ) -> None:
        await self._bump_draft_revision(change_set_id, tenant_id, expected_revision)
        await self.session.execute(
            delete(WBSChangeSetLineageORM).where(
                WBSChangeSetLineageORM.change_set_id == change_set_id,
                WBSChangeSetLineageORM.tenant_id == tenant_id,
                WBSChangeSetLineageORM.kind == LineageKind(kind).value,
                WBSChangeSetLineageORM.source_node_id == source_node_id,
                WBSChangeSetLineageORM.target_node_id == target_node_id,
            )
        )

    # ------------------------------------------------------------------ lifecycle
    async def _locked(self, change_set_id: UUID, tenant_id: UUID) -> WBSChangeSetORM:
        change_set = await self.session.scalar(
            select(WBSChangeSetORM)
            .where(WBSChangeSetORM.id == change_set_id, WBSChangeSetORM.tenant_id == tenant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if change_set is None:
            raise ChangeSetNotFoundError(str(change_set_id))
        return change_set

    async def submit(self, change_set_id: UUID, tenant_id: UUID, *, expected_revision: int, actor: Actor) -> str:
        """Validate the candidate and freeze its digest. Returns the submitted digest."""
        if not can_author(actor.kind, actor.role):
            raise GovernanceRuleError("only a human user or admin can submit a WBS change set (never AI)")
        change_set = await self._locked(change_set_id, tenant_id)
        require_transition(ChangeSetStatus(change_set.status), ChangeSetStatus.SUBMITTED)
        if change_set.revision != expected_revision:
            raise RevisionConflictError(f"WBS change set is at revision {change_set.revision}")
        detail = await self.get_change_set(change_set_id, change_set.project_id, tenant_id)
        assert detail is not None
        violations = validate_for_submit(
            [
                CandidateNode(
                    node_id=node.node_id,
                    parent_id=node.parent_id,
                    sort_order=node.sort_order,
                    code=node.code,
                    name=node.name,
                    decomposition_kind=node.decomposition_kind,
                    control_level=node.control_level,
                    dictionary=node.dictionary,
                    origin_kind=node.origin_kind,
                )
                for node in detail.nodes
            ],
            [LineageEdge(edge.kind, edge.source_node_id, edge.target_node_id) for edge in detail.lineage],
        )
        if violations:
            raise GovernanceRuleError("WBS change set cannot be submitted: " + "; ".join(violations))
        digest = self.compute_change_set_digest(detail, change_set.revision)
        change_set.status = ChangeSetStatus.SUBMITTED.value
        change_set.submitted_revision = change_set.revision
        change_set.submitted_digest = digest
        change_set.submitted_by = actor.user_id
        change_set.submitted_at = _now()
        await self.session.flush()
        return digest

    async def reopen(self, change_set_id: UUID, tenant_id: UUID, *, actor: Actor) -> int:
        """SUBMITTED -> DRAFT: a new revision; the submitted digest is invalidated."""
        change_set = await self._locked(change_set_id, tenant_id)
        _require_proposer_or_admin(change_set, actor, "reopen")
        require_transition(ChangeSetStatus(change_set.status), ChangeSetStatus.DRAFT)
        change_set.status = ChangeSetStatus.DRAFT.value
        change_set.revision = change_set.revision + 1
        change_set.submitted_revision = None
        change_set.submitted_digest = None
        change_set.submitted_by = None
        change_set.submitted_at = None
        await self.session.flush()
        return change_set.revision

    async def withdraw(self, change_set_id: UUID, tenant_id: UUID, *, actor: Actor) -> None:
        change_set = await self._locked(change_set_id, tenant_id)
        _require_proposer_or_admin(change_set, actor, "withdraw")
        require_transition(ChangeSetStatus(change_set.status), ChangeSetStatus.WITHDRAWN)
        change_set.status = ChangeSetStatus.WITHDRAWN.value
        change_set.closed_at = _now()
        await self.session.flush()

    async def mark_stale(self, change_set_id: UUID, tenant_id: UUID) -> None:
        """The base is no longer the current baseline (a rebase is a NEW draft, PC-2a.2)."""
        change_set = await self._locked(change_set_id, tenant_id)
        require_transition(ChangeSetStatus(change_set.status), ChangeSetStatus.STALE)
        current = await self.current_baseline(change_set.project_id, tenant_id)
        current_id = current.id if current is not None else None
        if current_id == change_set.base_baseline_id:
            raise GovernanceRuleError("the change set's base is still the current baseline")
        change_set.status = ChangeSetStatus.STALE.value
        change_set.closed_at = _now()
        await self.session.flush()


__all__ = [
    "Actor",
    "BaselineDetail",
    "ChangeSetDetail",
    "ChangeSetNotFoundError",
    "RevisionConflictError",
    "WBSGovernanceRepository",
    "baseline_digest_node",
    "candidate_digest_node",
]
