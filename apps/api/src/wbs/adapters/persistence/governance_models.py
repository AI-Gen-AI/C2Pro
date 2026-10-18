"""WBS governance ORM (PC-2a.1 #895, ADR-029): change sets, candidate trees, baselines.

Mirrors Alembic revision ``20261006_0001``: same tables, constraint names and (via
``governance_ddl``) the same trigger functions, so create_all-built test schemas enforce the
same invariants as migrated databases. RLS lives in the migration only (it is proven on a
migrated scratch database with a NOBYPASSRLS probe role).

Nothing in this module approves, applies or mutates the live WBS.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.wbs.adapters.persistence.governance_ddl import (
    CONTROL_LEVEL_CHECK,
    DECOMPOSITION_KIND_CHECK,
    DICTIONARY_CHECK,
    DIGEST_PATTERN_SQL,
    FUNCTION_STATEMENTS,
    TRIGGER_STATEMENTS,
)
from src.wbs.adapters.persistence.governed_apply_ddl import (
    LIVE_WRITE_GUARD_FUNCTION_SQL,
    LIVE_WRITE_TRIGGER_SQL,
    RETIREMENTS_GUARD_FUNCTION_SQL,
    RETIREMENTS_TRIGGER_SQL,
)
from src.wbs.adapters.persistence.import_ddl import (
    CHANGE_SET_SOURCE_IMPORT_GUARD_FUNCTION_SQL,
    CHANGE_SET_SOURCE_IMPORT_TRIGGER_SQL,
    IMPORT_REVIEW_FIRST_BASELINE_CHECK,
    SOURCE_IMPORT_CHECK,
)
from src.wbs.adapters.persistence.import_models import WBSImportSourceORM  # noqa: F401 - FK target

# sqlalchemy.DDL is untyped; same pattern as src/wbs/adapters/persistence/models.py.
_DDL: Any = DDL

_UUID = PGUUID(as_uuid=True)
_TS = DateTime(timezone=True)
# Python None must be SQL NULL (not JSON null), or the dictionary CHECK rightly rejects it.
_NULLABLE_JSONB = JSONB(none_as_null=True)


def _content_checks(prefix: str) -> tuple[CheckConstraint, ...]:
    return (
        CheckConstraint(CONTROL_LEVEL_CHECK, name=f"ck_{prefix}_control_level"),
        CheckConstraint(DECOMPOSITION_KIND_CHECK, name=f"ck_{prefix}_decomposition_kind"),
        CheckConstraint(DICTIONARY_CHECK, name=f"ck_{prefix}_dictionary"),
    )


class WBSChangeSetORM(Base):
    """One governed proposal against a base baseline (NULL base = first baseline)."""

    __tablename__ = "wbs_change_sets"

    id: Mapped[UUID] = mapped_column(_UUID, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    base_baseline_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    entry_mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="DRAFT")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    evidence_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_by: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    created_by_kind: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(_TS, nullable=True)
    decided_by: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(_TS, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_self_approval: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(_TS, nullable=True)
    created_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())
    # PC-2b.3 (#922): provenance link of an IMPORT_REVIEW draft; outside every digest, immutable.
    source_import_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "id", name="uq_wbs_change_sets_tenant_project_id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["projects.tenant_id", "projects.id"],
            name="fk_wbs_change_sets_project", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "base_baseline_id"],
            ["wbs_baselines.tenant_id", "wbs_baselines.project_id", "wbs_baselines.id"],
            name="fk_wbs_change_sets_base_baseline", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
        CheckConstraint("origin IN ('manual', 'ai', 'import')", name="ck_wbs_change_sets_origin"),
        CheckConstraint(
            "entry_mode IN ('GENERATE', 'IMPORT_REVIEW', 'CHANGE_BASELINE')", name="ck_wbs_change_sets_entry_mode"
        ),
        CheckConstraint(
            "entry_mode <> 'CHANGE_BASELINE' OR base_baseline_id IS NOT NULL",
            name="ck_wbs_change_sets_change_baseline_has_base",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'APPLIED', 'REJECTED', 'WITHDRAWN', 'STALE')",
            name="ck_wbs_change_sets_status",
        ),
        CheckConstraint("revision >= 1", name="ck_wbs_change_sets_revision"),
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 300", name="ck_wbs_change_sets_title"),
        CheckConstraint(
            "jsonb_typeof(profile_refs) = 'array' AND jsonb_typeof(evidence_refs) = 'array'",
            name="ck_wbs_change_sets_refs",
        ),
        CheckConstraint("created_by_kind IN ('human', 'ai', 'service')", name="ck_wbs_change_sets_created_by_kind"),
        CheckConstraint(
            "num_nonnulls(submitted_revision, submitted_digest, submitted_by, submitted_at) IN (0, 4)",
            name="ck_wbs_change_sets_submission_fields",
        ),
        CheckConstraint(
            f"submitted_digest IS NULL OR submitted_digest ~ {DIGEST_PATTERN_SQL}",
            name="ck_wbs_change_sets_submitted_digest",
        ),
        CheckConstraint(
            "status NOT IN ('SUBMITTED', 'APPLIED', 'REJECTED') "
            "OR (submitted_digest IS NOT NULL AND submitted_revision = revision)",
            name="ck_wbs_change_sets_submitted_states",
        ),
        CheckConstraint("status <> 'DRAFT' OR submitted_digest IS NULL", name="ck_wbs_change_sets_draft_unsubmitted"),
        CheckConstraint(
            "num_nonnulls(decided_by, decided_at, decided_self_approval) IN (0, 3)",
            name="ck_wbs_change_sets_decision_fields",
        ),
        CheckConstraint(
            "(status IN ('APPLIED', 'REJECTED')) = (decided_by IS NOT NULL)", name="ck_wbs_change_sets_decided_states"
        ),
        CheckConstraint(
            "decided_by IS NULL OR decided_self_approval = (decided_by = submitted_by)",
            name="ck_wbs_change_sets_self_approval",
        ),
        CheckConstraint(
            "status <> 'REJECTED' OR length(btrim(coalesce(decision_reason, ''))) > 0",
            name="ck_wbs_change_sets_rejection_reason",
        ),
        CheckConstraint(
            "(status IN ('APPLIED', 'REJECTED', 'WITHDRAWN', 'STALE')) = (closed_at IS NOT NULL)",
            name="ck_wbs_change_sets_closed",
        ),
        Index(
            "uq_wbs_change_sets_one_application", "project_id", "base_baseline_id", unique=True,
            postgresql_where=text("status = 'APPLIED'"), postgresql_nulls_not_distinct=True,
        ),
        Index("ix_wbs_change_sets_project_status", "tenant_id", "project_id", "status"),
        # PC-2b.3 (#922, revision 20261007_0003): an IMPORT_REVIEW draft names its exact import source.
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "source_import_id"],
            ["wbs_import_sources.tenant_id", "wbs_import_sources.project_id", "wbs_import_sources.id"],
            name="fk_wbs_change_sets_source_import", ondelete="NO ACTION",
        ),
        CheckConstraint(SOURCE_IMPORT_CHECK, name="ck_wbs_change_sets_source_import"),
        CheckConstraint(IMPORT_REVIEW_FIRST_BASELINE_CHECK, name="ck_wbs_change_sets_import_review_first_baseline"),
        Index("ix_wbs_change_sets_source_import", "source_import_id",
              postgresql_where=text("source_import_id IS NOT NULL")),
    )


class WBSChangeSetNodeORM(Base):
    """A candidate-tree node: never live WBS, never a downstream link target."""

    __tablename__ = "wbs_change_set_nodes"

    change_set_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    node_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    control_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="none")
    decomposition_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    dictionary: Mapped[dict[str, Any] | None] = mapped_column(_NULLABLE_JSONB, nullable=True)
    origin_kind: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("change_set_id", "node_id", name="pk_wbs_change_set_nodes"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "change_set_id"],
            ["wbs_change_sets.tenant_id", "wbs_change_sets.project_id", "wbs_change_sets.id"],
            name="fk_wbs_change_set_nodes_change_set", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["change_set_id", "parent_id"],
            ["wbs_change_set_nodes.change_set_id", "wbs_change_set_nodes.node_id"],
            name="fk_wbs_change_set_nodes_parent", ondelete="NO ACTION", deferrable=True, initially="DEFERRED",
        ),
        UniqueConstraint(
            "change_set_id", "parent_id", "sort_order", name="uq_wbs_change_set_nodes_sibling_order",
            deferrable=True, initially="DEFERRED", postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("parent_id IS NULL OR parent_id <> node_id", name="ck_wbs_change_set_nodes_not_own_parent"),
        CheckConstraint("sort_order >= 1", name="ck_wbs_change_set_nodes_sort_order"),
        CheckConstraint("code IS NULL OR length(btrim(code)) BETWEEN 1 AND 50", name="ck_wbs_change_set_nodes_code"),
        CheckConstraint("length(btrim(name)) BETWEEN 1 AND 255", name="ck_wbs_change_set_nodes_name"),
        CheckConstraint(
            "origin_kind IN ('existing', 'minted', 'adopted_legacy')", name="ck_wbs_change_set_nodes_origin_kind"
        ),
        CheckConstraint("jsonb_typeof(provenance) = 'object'", name="ck_wbs_change_set_nodes_provenance"),
        *_content_checks("wbs_change_set_nodes"),
    )


class WBSChangeSetLineageORM(Base):
    """SPLIT / MERGE / SUPERSEDES from base identities to minted candidate identities."""

    __tablename__ = "wbs_change_set_lineage"

    change_set_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_node_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    target_node_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint(
            "change_set_id", "kind", "source_node_id", "target_node_id", name="pk_wbs_change_set_lineage"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "change_set_id"],
            ["wbs_change_sets.tenant_id", "wbs_change_sets.project_id", "wbs_change_sets.id"],
            name="fk_wbs_change_set_lineage_change_set", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["change_set_id", "target_node_id"],
            ["wbs_change_set_nodes.change_set_id", "wbs_change_set_nodes.node_id"],
            name="fk_wbs_change_set_lineage_target", ondelete="CASCADE",
        ),
        CheckConstraint("kind IN ('SPLIT', 'MERGE', 'SUPERSEDES')", name="ck_wbs_change_set_lineage_kind"),
        CheckConstraint("source_node_id <> target_node_id", name="ck_wbs_change_set_lineage_distinct"),
        Index("ix_wbs_change_set_lineage_target", "change_set_id", "target_node_id"),
    )


class WBSBaselineORM(Base):
    """An immutable approved WBS baseline (created only by a governed apply, PC-2a.2)."""

    __tablename__ = "wbs_baselines"

    id: Mapped[UUID] = mapped_column(_UUID, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    baseline_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_baseline_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    source_change_set_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    tree_digest: Mapped[str] = mapped_column(Text, nullable=False)
    change_set_digest: Mapped[str] = mapped_column(Text, nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    approved_by_kind: Mapped[str] = mapped_column(Text, nullable=False)
    self_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    profile_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    applied_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "id", name="uq_wbs_baselines_tenant_project_id"),
        UniqueConstraint("project_id", "baseline_no", name="uq_wbs_baselines_project_no"),
        UniqueConstraint(
            "project_id", "parent_baseline_id", name="uq_wbs_baselines_linear_history",
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint("source_change_set_id", name="uq_wbs_baselines_source_change_set"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["projects.tenant_id", "projects.id"],
            name="fk_wbs_baselines_project", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "parent_baseline_id"],
            ["wbs_baselines.tenant_id", "wbs_baselines.project_id", "wbs_baselines.id"],
            name="fk_wbs_baselines_parent", ondelete="NO ACTION", deferrable=True, initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "source_change_set_id"],
            ["wbs_change_sets.tenant_id", "wbs_change_sets.project_id", "wbs_change_sets.id"],
            name="fk_wbs_baselines_source_change_set", ondelete="NO ACTION", deferrable=True, initially="DEFERRED",
        ),
        CheckConstraint("baseline_no >= 1", name="ck_wbs_baselines_baseline_no"),
        CheckConstraint("(parent_baseline_id IS NULL) = (baseline_no = 1)", name="ck_wbs_baselines_first"),
        CheckConstraint(
            f"tree_digest ~ {DIGEST_PATTERN_SQL} AND change_set_digest ~ {DIGEST_PATTERN_SQL}",
            name="ck_wbs_baselines_digests",
        ),
        CheckConstraint("node_count >= 0", name="ck_wbs_baselines_node_count"),
        CheckConstraint("approved_by_kind = 'human'", name="ck_wbs_baselines_human_approver"),
        CheckConstraint("jsonb_typeof(profile_refs) = 'array'", name="ck_wbs_baselines_profile_refs"),
        Index("ix_wbs_baselines_project_applied", "project_id", "applied_at"),
    )


class WBSBaselineNodeORM(Base):
    """One node of an immutable baseline snapshot (no dates, cost, progress or caches)."""

    __tablename__ = "wbs_baseline_nodes"

    baseline_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    node_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    control_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="none")
    decomposition_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    dictionary: Mapped[dict[str, Any] | None] = mapped_column(_NULLABLE_JSONB, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("baseline_id", "node_id", name="pk_wbs_baseline_nodes"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "baseline_id"],
            ["wbs_baselines.tenant_id", "wbs_baselines.project_id", "wbs_baselines.id"],
            name="fk_wbs_baseline_nodes_baseline", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["baseline_id", "parent_id"],
            ["wbs_baseline_nodes.baseline_id", "wbs_baseline_nodes.node_id"],
            name="fk_wbs_baseline_nodes_parent", ondelete="NO ACTION", deferrable=True, initially="DEFERRED",
        ),
        UniqueConstraint(
            "baseline_id", "parent_id", "sort_order", name="uq_wbs_baseline_nodes_sibling_order",
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint("baseline_id", "code", name="uq_wbs_baseline_nodes_code"),
        CheckConstraint("parent_id IS NULL OR parent_id <> node_id", name="ck_wbs_baseline_nodes_not_own_parent"),
        CheckConstraint("sort_order >= 1", name="ck_wbs_baseline_nodes_sort_order"),
        CheckConstraint("length(btrim(code)) BETWEEN 1 AND 50", name="ck_wbs_baseline_nodes_code"),
        CheckConstraint("length(btrim(name)) BETWEEN 1 AND 255", name="ck_wbs_baseline_nodes_name"),
        *_content_checks("wbs_baseline_nodes"),
        Index("ix_wbs_baseline_nodes_node_id", "node_id"),
    )


class WBSChangeSetRetirementORM(Base):
    """An identity that leaves the WBS through a change set, with its disposition (PC-2a.2).

    Base-baseline identities, or -- for a first baseline only -- legacy live rows the reviewed
    candidate does not adopt. ``snapshot`` keeps what the retired node was. Editable only
    while the change set is DRAFT; never updated (database guard, revision 20261006_0002).
    """

    __tablename__ = "wbs_change_set_retirements"

    change_set_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    node_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    disposition: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("change_set_id", "node_id", name="pk_wbs_change_set_retirements"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "change_set_id"],
            ["wbs_change_sets.tenant_id", "wbs_change_sets.project_id", "wbs_change_sets.id"],
            name="fk_wbs_change_set_retirements_change_set", ondelete="CASCADE",
        ),
        CheckConstraint(
            "disposition IN ('REMOVED', 'SPLIT', 'MERGED', 'SUPERSEDED', 'RETIRED_ON_BASELINE')",
            name="ck_wbs_change_set_retirements_disposition",
        ),
        CheckConstraint("source IN ('baseline', 'legacy')", name="ck_wbs_change_set_retirements_source"),
        CheckConstraint(
            "disposition <> 'RETIRED_ON_BASELINE' OR source = 'legacy'",
            name="ck_wbs_change_set_retirements_legacy_disposition",
        ),
        CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="ck_wbs_change_set_retirements_snapshot"),
        Index("ix_wbs_change_set_retirements_tenant_project", "tenant_id", "project_id"),
        Index("ix_wbs_change_set_retirements_node", "node_id"),
    )


def _install(table: Any, statements: tuple[str, ...]) -> None:
    for statement in statements:
        event.listen(table, "after_create", _DDL(statement).execute_if(dialect="postgresql"))


# Functions are late-bound plpgsql, so they can be created with the first governance table;
# each trigger is created once its own table exists.
_install(WBSChangeSetORM.__table__, FUNCTION_STATEMENTS)
# PC-2b.3 (revision 20261007_0003): the import-source link guard on wbs_change_sets.
_install(WBSChangeSetORM.__table__, (CHANGE_SET_SOURCE_IMPORT_GUARD_FUNCTION_SQL, CHANGE_SET_SOURCE_IMPORT_TRIGGER_SQL))
for _model in (WBSChangeSetORM, WBSChangeSetNodeORM, WBSChangeSetLineageORM, WBSBaselineORM, WBSBaselineNodeORM):
    _install(
        _model.__table__,
        tuple(t for t in TRIGGER_STATEMENTS if f" ON public.{_model.__tablename__} " in t),
    )

# PC-2a.2 (revision 20261006_0002): the retirement guard with its table; the live-write guard on
# wbs_nodes once BOTH wbs_nodes and the governance tables it reads exist (create_all may build
# them in any order, and subset test schemas may build wbs_nodes alone).
_install(WBSChangeSetRetirementORM.__table__, (RETIREMENTS_GUARD_FUNCTION_SQL, RETIREMENTS_TRIGGER_SQL))


@event.listens_for(Base.metadata, "after_create")
def _install_live_write_guard(_target: Any, connection: Any, **_kw: Any) -> None:
    if connection.dialect.name != "postgresql":
        return
    ready = connection.execute(text(
        "SELECT to_regclass('public.wbs_nodes') IS NOT NULL AND to_regclass('public.wbs_baselines') IS NOT NULL "
        "AND to_regclass('public.wbs_change_sets') IS NOT NULL"
    )).scalar()
    if not ready:
        return
    installed = connection.execute(text(
        "SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_wbs_nodes_governed_write_guard' "
        "AND tgrelid = 'public.wbs_nodes'::regclass)"
    )).scalar()
    if not installed:
        connection.execute(_DDL(LIVE_WRITE_GUARD_FUNCTION_SQL))
        connection.execute(_DDL(LIVE_WRITE_TRIGGER_SQL))


__all__ = [
    "WBSBaselineNodeORM",
    "WBSBaselineORM",
    "WBSChangeSetLineageORM",
    "WBSChangeSetNodeORM",
    "WBSChangeSetORM",
    "WBSChangeSetRetirementORM",
]
