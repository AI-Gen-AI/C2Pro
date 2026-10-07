"""WBS intelligence store ORM (PC-2b.2 #921, ADR-030): runs, immutable items, append-only decisions.

Mirrors Alembic revision ``20261007_0001``: same tables, constraint names and (via
``intelligence_ddl``) the same guard functions, so create_all-built test schemas enforce the same
invariants as migrated databases. RLS lives in the migration only (it is proven on a migrated
scratch database with a NOBYPASSRLS probe role).

Nothing here creates, submits, approves or applies WBS: decisions record what a human chose to do
with a suggestion; the WBS itself changes only through the PC-2a governed commands.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DDL,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
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
from src.wbs.adapters.persistence.governance_ddl import DIGEST_PATTERN_SQL
from src.wbs.adapters.persistence.governance_models import (  # noqa: F401 - FK targets
    WBSBaselineORM,
    WBSChangeSetORM,
)
from src.wbs.adapters.persistence.intelligence_ddl import (
    FUNCTION_STATEMENTS,
    REUSABLE_KEY_INDEX_WHERE,
    TRIGGER_STATEMENTS,
)

_DDL: Any = DDL
_UUID = PGUUID(as_uuid=True)
_TS = DateTime(timezone=True)
_NULLABLE_JSONB = JSONB(none_as_null=True)
_D = DIGEST_PATTERN_SQL
_APPLY = "('APPLY_AS_PROPOSED', 'APPLY_WITH_HUMAN_EDIT')"
_APPLY_FIELDS = ("num_nonnulls(change_set_id, change_set_revision_before, change_set_revision_after, proposal_body_digest, "
                 "applied_commands, applied_commands_digest, label_node_ids)")


def _scoped_fk(columns: list[str], table: str, name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", "project_id", *columns], [f"{table}.tenant_id", f"{table}.project_id", f"{table}.id"],
        name=name, ondelete="NO ACTION", deferrable=True, initially="DEFERRED",
    )


class WBSIntelligenceRunORM(Base):
    """One intelligence run: exact input identity, status, outcome and its qualification report."""

    __tablename__ = "wbs_intelligence_runs"

    id: Mapped[UUID] = mapped_column(_UUID, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    execution_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_change_set_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    target_baseline_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    target_import_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    target_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_change_set_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_base_baseline_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    evidence_set_digest: Mapped[str] = mapped_column(Text, nullable=False)
    profile_refs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    proposal_contract_version: Mapped[str] = mapped_column(Text, nullable=False)
    qualification_vocab_version: Mapped[str] = mapped_column(Text, nullable=False)
    orchestration_version: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    rerun_nonce: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provenance: Mapped[dict[str, Any] | None] = mapped_column(_NULLABLE_JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualification: Mapped[dict[str, Any] | None] = mapped_column(_NULLABLE_JSONB, nullable=True)
    qualification_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    requested_by_kind: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(_TS, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(_TS, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "id", name="uq_wbs_intelligence_runs_tenant_project_id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["projects.tenant_id", "projects.id"],
            name="fk_wbs_intelligence_runs_project", ondelete="CASCADE",
        ),
        _scoped_fk(["target_change_set_id"], "wbs_change_sets", "fk_wbs_intelligence_runs_target_change_set"),
        _scoped_fk(["target_baseline_id"], "wbs_baselines", "fk_wbs_intelligence_runs_target_baseline"),
        _scoped_fk(["target_base_baseline_id"], "wbs_baselines", "fk_wbs_intelligence_runs_target_base_baseline"),
        CheckConstraint("mode IN ('GENERATE', 'IMPORT_REVIEW', 'REVIEW_OPTIMIZE')", name="ck_wbs_intelligence_runs_mode"),
        CheckConstraint("execution_type IN ('DETERMINISTIC', 'AI')", name="ck_wbs_intelligence_runs_execution_type"),
        CheckConstraint(
            "target_kind IN ('NONE', 'IMPORT', 'CANDIDATE', 'BASELINE')", name="ck_wbs_intelligence_runs_target_kind"
        ),
        CheckConstraint(
            "(target_kind = 'NONE' AND num_nonnulls(target_change_set_id, target_baseline_id, target_import_id, "
            "target_digest, target_change_set_revision, target_base_baseline_id) = 0) "
            "OR (target_kind = 'CANDIDATE' AND target_change_set_id IS NOT NULL AND target_digest IS NOT NULL "
            "AND target_change_set_revision IS NOT NULL AND num_nonnulls(target_baseline_id, target_import_id) = 0) "
            "OR (target_kind = 'BASELINE' AND target_baseline_id IS NOT NULL AND target_digest IS NOT NULL "
            "AND num_nonnulls(target_change_set_id, target_import_id, target_change_set_revision) = 0) "
            "OR (target_kind = 'IMPORT' AND target_import_id IS NOT NULL AND target_digest IS NOT NULL "
            "AND num_nonnulls(target_change_set_id, target_baseline_id, target_change_set_revision) = 0)",
            name="ck_wbs_intelligence_runs_target_identity",
        ),
        CheckConstraint(
            "target_change_set_revision IS NULL OR target_change_set_revision >= 1",
            name="ck_wbs_intelligence_runs_target_revision",
        ),
        CheckConstraint(
            f"evidence_set_digest ~ {_D} AND idempotency_key ~ {_D} "
            f"AND (target_digest IS NULL OR target_digest ~ {_D}) "
            f"AND (qualification_digest IS NULL OR qualification_digest ~ {_D})",
            name="ck_wbs_intelligence_runs_digests",
        ),
        CheckConstraint("jsonb_typeof(profile_refs) = 'array'", name="ck_wbs_intelligence_runs_profile_refs"),
        CheckConstraint(
            "length(btrim(proposal_contract_version)) BETWEEN 1 AND 100 "
            "AND length(btrim(qualification_vocab_version)) BETWEEN 1 AND 100 "
            "AND length(btrim(orchestration_version)) BETWEEN 1 AND 100",
            name="ck_wbs_intelligence_runs_versions",
        ),
        CheckConstraint(
            "rerun_nonce IS NULL OR length(btrim(rerun_nonce)) BETWEEN 1 AND 200", name="ck_wbs_intelligence_runs_rerun_nonce"
        ),
        CheckConstraint(
            "(execution_type = 'AI') = (model_provenance IS NOT NULL) "
            "AND (model_provenance IS NULL OR jsonb_typeof(model_provenance) = 'object')",
            name="ck_wbs_intelligence_runs_model_provenance",
        ),
        CheckConstraint(
            "status IN ('REQUESTED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')", name="ck_wbs_intelligence_runs_status"
        ),
        CheckConstraint(
            "(status IN ('REQUESTED', 'RUNNING') AND outcome IS NULL AND completed_at IS NULL) "
            "OR (status = 'COMPLETED' AND outcome IN ('COMPLETE', 'PARTIAL_PROPOSAL', 'INSUFFICIENT_EVIDENCE') "
            "AND qualification IS NOT NULL AND started_at IS NOT NULL AND completed_at IS NOT NULL) "
            "OR (status = 'FAILED' AND outcome = 'FAILED' AND completed_at IS NOT NULL) "
            "OR (status = 'CANCELLED' AND outcome = 'CANCELLED' AND completed_at IS NOT NULL)",
            name="ck_wbs_intelligence_runs_outcome",
        ),
        CheckConstraint("status <> 'RUNNING' OR started_at IS NOT NULL", name="ck_wbs_intelligence_runs_started"),
        CheckConstraint(
            "(qualification IS NULL) = (qualification_digest IS NULL) "
            "AND (qualification IS NULL OR jsonb_typeof(qualification) = 'object')",
            name="ck_wbs_intelligence_runs_qualification",
        ),
        CheckConstraint(
            "failure_reason IS NULL OR (status IN ('FAILED', 'CANCELLED') AND length(btrim(failure_reason)) BETWEEN 1 AND 2000)",
            name="ck_wbs_intelligence_runs_failure_reason",
        ),
        CheckConstraint("requested_by_kind IN ('human', 'service')", name="ck_wbs_intelligence_runs_requested_by_kind"),
        Index(
            "uq_wbs_intelligence_runs_reusable_key", "tenant_id", "idempotency_key", unique=True,
            postgresql_where=text(REUSABLE_KEY_INDEX_WHERE),
        ),
        Index("ix_wbs_intelligence_runs_project", "tenant_id", "project_id", "created_at"),
    )


class WBSIntelligenceItemORM(Base):
    """An immutable FINDING or PROPOSAL of one run (insert-only, while the run is RUNNING)."""

    __tablename__ = "wbs_intelligence_items"

    id: Mapped[UUID] = mapped_column(_UUID, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    run_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    ref: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_version: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    body_digest: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "run_id", "id", "kind", name="uq_wbs_intelligence_items_scope"),
        UniqueConstraint("run_id", "ref", name="uq_wbs_intelligence_items_run_ref"),
        UniqueConstraint("run_id", "ordinal", name="uq_wbs_intelligence_items_run_ordinal"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "run_id"],
            ["wbs_intelligence_runs.tenant_id", "wbs_intelligence_runs.project_id", "wbs_intelligence_runs.id"],
            name="fk_wbs_intelligence_items_run", ondelete="CASCADE",
        ),
        CheckConstraint("kind IN ('FINDING', 'PROPOSAL')", name="ck_wbs_intelligence_items_kind"),
        CheckConstraint("ref ~ '^[a-z][a-z0-9_-]{0,31}$'", name="ck_wbs_intelligence_items_ref"),
        CheckConstraint("ordinal >= 1", name="ck_wbs_intelligence_items_ordinal"),
        CheckConstraint(f"body_digest ~ {_D}", name="ck_wbs_intelligence_items_body_digest"),
        CheckConstraint(
            "jsonb_typeof(body) = 'object' AND ("
            "(kind = 'PROPOSAL' AND contract_version = 'wbs-proposal/v1' "
            "AND operation IN ('ADD_NODE', 'UPDATE_NODE', 'RECODE_NODE', 'MOVE_NODE', 'REORDER_NODE', 'REMOVE_NODE', "
            "'SPLIT_NODE', 'MERGE_NODES') "
            "AND body ?& ARRAY['item_id', 'ref', 'operation', 'payload', 'affected_node_ids', 'target_fingerprints', "
            "'creates_labels', 'uses_labels', 'depends_on', 'rationale', 'evidence', 'confidence_pct', 'destructive'] "
            "AND body ->> 'item_id' = id::text AND body ->> 'ref' = ref AND body ->> 'operation' = operation "
            "AND jsonb_typeof(body -> 'payload') = 'object' AND jsonb_typeof(body -> 'target_fingerprints') = 'object' "
            "AND jsonb_typeof(body -> 'depends_on') = 'array') "
            "OR (kind = 'FINDING' AND contract_version = 'wbs-qualification/v1' AND operation IS NULL "
            "AND body ?& ARRAY['finding_id', 'dimension', 'status', 'method', 'summary'] "
            "AND body ->> 'finding_id' = id::text AND body ->> 'status' IN ('GAP', 'WARNING', 'AMBIGUOUS')))",
            name="ck_wbs_intelligence_items_typed_body",
        ),
    )


class WBSIntelligenceDecisionORM(Base):
    """An append-only human decision about one item (never a WBS approval)."""

    __tablename__ = "wbs_intelligence_decisions"

    id: Mapped[UUID] = mapped_column(_UUID, primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    project_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    run_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    item_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    item_kind: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    batch_id: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    decided_by: Mapped[UUID] = mapped_column(_UUID, nullable=False)
    decided_by_kind: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_set_id: Mapped[UUID | None] = mapped_column(_UUID, nullable=True)
    change_set_revision_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_set_revision_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposal_body_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_commands: Mapped[list[Any] | None] = mapped_column(_NULLABLE_JSONB, nullable=True)
    applied_commands_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    label_node_ids: Mapped[dict[str, Any] | None] = mapped_column(_NULLABLE_JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(_TS, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("item_id", name="uq_wbs_intelligence_decisions_item"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "run_id", "item_id", "item_kind"],
            ["wbs_intelligence_items.tenant_id", "wbs_intelligence_items.project_id", "wbs_intelligence_items.run_id",
             "wbs_intelligence_items.id", "wbs_intelligence_items.kind"],
            name="fk_wbs_intelligence_decisions_item", ondelete="CASCADE",
        ),
        _scoped_fk(["change_set_id"], "wbs_change_sets", "fk_wbs_intelligence_decisions_change_set"),
        CheckConstraint(
            "(item_kind = 'PROPOSAL' AND decision IN ('APPLY_AS_PROPOSED', 'APPLY_WITH_HUMAN_EDIT', 'REJECT')) "
            "OR (item_kind = 'FINDING' AND decision IN ('ACKNOWLEDGE', 'DISMISS', 'NO_CHANGE'))",
            name="ck_wbs_intelligence_decisions_vocabulary",
        ),
        CheckConstraint("decided_by_kind = 'human'", name="ck_wbs_intelligence_decisions_human"),
        CheckConstraint(
            f"(decision IN {_APPLY} AND {_APPLY_FIELDS} = 7 "
            "AND change_set_revision_after > change_set_revision_before AND change_set_revision_before >= 1) "
            f"OR (decision NOT IN {_APPLY} AND {_APPLY_FIELDS} = 0)",
            name="ck_wbs_intelligence_decisions_application",
        ),
        CheckConstraint(
            f"(proposal_body_digest IS NULL OR proposal_body_digest ~ {_D}) "
            f"AND (applied_commands_digest IS NULL OR applied_commands_digest ~ {_D})",
            name="ck_wbs_intelligence_decisions_digests",
        ),
        CheckConstraint(
            "(applied_commands IS NULL OR jsonb_typeof(applied_commands) = 'array') "
            "AND (label_node_ids IS NULL OR jsonb_typeof(label_node_ids) = 'object')",
            name="ck_wbs_intelligence_decisions_payloads",
        ),
        CheckConstraint(
            "reason IS NULL OR length(btrim(reason)) BETWEEN 1 AND 4000", name="ck_wbs_intelligence_decisions_reason"
        ),
        Index("ix_wbs_intelligence_decisions_run", "tenant_id", "project_id", "run_id"),
        Index("ix_wbs_intelligence_decisions_change_set", "change_set_id"),
    )


def _install(table: Any, statements: tuple[str, ...]) -> None:
    for statement in statements:
        event.listen(table, "after_create", _DDL(statement).execute_if(dialect="postgresql"))


# Guard functions are late-bound plpgsql: created with the run table; each trigger with its table.
_install(WBSIntelligenceRunORM.__table__, FUNCTION_STATEMENTS)
for _model in (WBSIntelligenceRunORM, WBSIntelligenceItemORM, WBSIntelligenceDecisionORM):
    _install(_model.__table__, tuple(t for t in TRIGGER_STATEMENTS if f" ON public.{_model.__tablename__} " in t))


__all__ = ["WBSIntelligenceDecisionORM", "WBSIntelligenceItemORM", "WBSIntelligenceRunORM"]
