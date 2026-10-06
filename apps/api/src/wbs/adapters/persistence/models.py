"""
C2Pro - WBS Persistence Models

SQLAlchemy ORM models for WBS (Work Breakdown Structure) with nested set model.

Refers to Suite ID: TS-INT-DB-WBS-001.
TASK-BCK-029: WBS API Endpoint with nested set model
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DDL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.wbs.adapters.persistence.governance_ddl import (
    CONTROL_LEVEL_CHECK,
    DECOMPOSITION_KIND_CHECK,
    DICTIONARY_CHECK,
)
from src.wbs.domain.enums import WBSNodeStatus, WBSNodeType

if TYPE_CHECKING:
    from src.projects.adapters.persistence.models import ProjectORM

# sqlalchemy.DDL is untyped; same pattern as src/temporal/adapters/persistence/models.py.
_DDL: Any = DDL


class WBSNodeORM(Base):
    """
    WBS Node ORM model using Nested Set Model.

    Nested Set Model provides efficient tree operations:
    - All descendants: WHERE lft > node.lft AND rgt < node.rgt
    - All ancestors: WHERE lft < node.lft AND rgt > node.rgt
    - Leaf nodes: WHERE rgt = lft + 1
    - Subtree size: (rgt - lft - 1) / 2

    RLS Policy: wbs_nodes_tenant_isolation (filter by tenant_id)
    """

    __tablename__ = "wbs_nodes"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # PC-1R / ADR-029: the project is the implicit root (top-level branches have no parent).
    # The parent must be in the same tenant AND project (composite FK in __table_args__), and
    # deleting a parent never silently re-roots its children (ON DELETE NO ACTION).
    parent_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    # Hierarchy authority is (parent_id, sort_order); lft/rgt/depth are derived caches.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Node identity (unbounded, like the procurement WBS rows migrated into this table by ADR-025)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nested Set Model fields
    lft: Mapped[int] = mapped_column(Integer, nullable=False)
    rgt: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Node classification
    node_type: Mapped[WBSNodeType] = mapped_column(
        SQLEnum(WBSNodeType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default="work_package",
    )
    status: Mapped[WBSNodeStatus] = mapped_column(
        SQLEnum(WBSNodeStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default="not_started",
    )

    # Scheduling
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Budget (18,2: same precision as procurement budgets, see 20260627_0001)
    budget_allocated: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    budget_spent: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")

    # Evidence lineage and optimistic locking (ADR-025: the canonical WBS carries what WBS
    # consumers previously read from procurement_wbs_items)
    source_clause_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    # Provenance only: deleting the document never deletes WBS scope (PC-1R).
    source_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)

    # Metadata
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    # Governed node semantics (PC-2a.1, ADR-029). control_level is vocabulary only;
    # decomposition_kind is namespace:term; dictionary is descriptive wbs-dictionary/v1.
    control_level: Mapped[str] = mapped_column(Text, nullable=False, server_default="none")
    decomposition_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    dictionary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )

    # Timestamps
    @staticmethod
    def _utcnow_naive() -> datetime:
        """Return UTC now normalized to a naive timestamp for legacy TIMESTAMP columns."""
        return datetime.now(UTC).replace(tzinfo=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )

    # Relationships
    project: Mapped["ProjectORM"] = relationship(
        "ProjectORM", foreign_keys=[project_id], lazy="select"
    )
    parent: Mapped["WBSNodeORM"] = relationship(
        "WBSNodeORM",
        primaryjoin="WBSNodeORM.parent_id == WBSNodeORM.id",
        remote_side=[id],
        foreign_keys=[parent_id],
        lazy="select",
        viewonly=True,
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_wbs_nodes_project_id", "project_id"),
        Index("ix_wbs_nodes_tenant_id", "tenant_id"),
        Index("ix_wbs_nodes_parent_id", "parent_id"),
        Index("ix_wbs_nodes_lft", "lft"),
        Index("ix_wbs_nodes_rgt", "rgt"),
        Index("ix_wbs_nodes_depth", "depth"),
        Index("ix_wbs_nodes_status", "status"),
        Index("ix_wbs_nodes_node_type", "node_type"),
        Index("ix_wbs_nodes_project_source_document", "project_id", "source_document_id"),
        Index(
            "ix_wbs_nodes_project_lft_rgt", "project_id", "lft", "rgt"
        ),  # Composite for tree queries
        # Code is display data (ADR-029): unique per project, deferred so swaps fit one transaction.
        UniqueConstraint(
            "project_id", "code", name="uq_wbs_nodes_project_code", deferrable=True, initially="DEFERRED"
        ),
        UniqueConstraint(
            "project_id",
            "parent_id",
            "sort_order",
            name="uq_wbs_nodes_sibling_order",
            deferrable=True,
            initially="DEFERRED",
            postgresql_nulls_not_distinct=True,
        ),
        UniqueConstraint("tenant_id", "project_id", "id", name="uq_wbs_nodes_tenant_project_id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id", "parent_id"],
            ["wbs_nodes.tenant_id", "wbs_nodes.project_id", "wbs_nodes.id"],
            name="fk_wbs_nodes_parent_same_project",
            ondelete="NO ACTION",
            # Checked at commit: cascaded project/tenant deletes run as separate statements.
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("lft < rgt", name="ck_wbs_nodes_lft_lt_rgt"),
        CheckConstraint("lft > 0", name="ck_wbs_nodes_lft_positive"),
        CheckConstraint("depth >= 0", name="ck_wbs_nodes_depth_non_negative"),
        CheckConstraint("budget_spent >= 0", name="ck_wbs_nodes_budget_spent_non_negative"),
        CheckConstraint(CONTROL_LEVEL_CHECK, name="ck_wbs_nodes_control_level"),
        CheckConstraint(DECOMPOSITION_KIND_CHECK, name="ck_wbs_nodes_decomposition_kind"),
        CheckConstraint(DICTIONARY_CHECK, name="ck_wbs_nodes_dictionary"),
        {"info": {"rls_policy": "wbs_nodes_tenant_isolation"}},
    )

    def __repr__(self) -> str:
        return f"<WBSNodeORM(id={self.id}, code='{self.code}', name='{self.name}')>"

    @property
    def is_root(self) -> bool:
        """Check if this is a root node."""
        return self.parent_id is None and self.depth == 0

    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (no children)."""
        return self.rgt == self.lft + 1

    @property
    def children_count_estimate(self) -> int:
        """Estimate number of nodes in subtree."""
        return (self.rgt - self.lft - 1) // 2

    @property
    def is_top_level(self) -> bool:
        """A depth-0 branch directly under the implicit project root (ADR-029)."""
        return self.parent_id is None


# PC-1R (ADR-029): depth/lft/rgt are derived caches, so their integrity is checked at COMMIT by a
# deferred constraint trigger -- a plain CHECK is not deferrable and rejects legitimate
# two-statement structural writes. The same SQL ships in Alembic 20261005_0003 (parity tested);
# this copy installs it on create_all-built schemas.
HIERARCHY_CACHE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.wbs_nodes_verify_hierarchy_cache()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    node public.wbs_nodes%ROWTYPE;
    parent_depth integer;
BEGIN
    -- Deferred: judge the row as it stands at commit, not as it was when queued.
    SELECT * INTO node FROM public.wbs_nodes WHERE id = NEW.id;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    IF node.parent_id IS NULL THEN
        IF node.depth <> 0 THEN
            RAISE EXCEPTION 'wbs_nodes hierarchy cache: top-level node % must have depth 0, has %',
                node.id, node.depth USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    ELSE
        SELECT depth INTO parent_depth FROM public.wbs_nodes WHERE id = node.parent_id;
        IF parent_depth IS NULL OR node.depth <> parent_depth + 1 THEN
            RAISE EXCEPTION 'wbs_nodes hierarchy cache: node % depth % is not parent depth % + 1',
                node.id, node.depth, parent_depth USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.wbs_nodes child WHERE child.parent_id = node.id AND child.depth <> node.depth + 1
    ) THEN
        RAISE EXCEPTION 'wbs_nodes hierarchy cache: children of % are not at depth %',
            node.id, node.depth + 1 USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END
$fn$
"""

HIERARCHY_CACHE_TRIGGER_SQL = (
    "CREATE CONSTRAINT TRIGGER trg_wbs_nodes_hierarchy_cache "
    "AFTER INSERT OR UPDATE OF parent_id, depth, project_id, tenant_id ON public.wbs_nodes "
    "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_nodes_verify_hierarchy_cache()"
)

for _statement in (
    HIERARCHY_CACHE_FUNCTION_SQL,
    "REVOKE ALL ON FUNCTION public.wbs_nodes_verify_hierarchy_cache() FROM PUBLIC",
    "DROP TRIGGER IF EXISTS trg_wbs_nodes_hierarchy_cache ON public.wbs_nodes",
    HIERARCHY_CACHE_TRIGGER_SQL,
):
    # DDL() treats '%' as a format marker; the plpgsql uses %ROWTYPE and RAISE '%' placeholders.
    event.listen(
        WBSNodeORM.__table__,
        "after_create",
        _DDL(_statement.replace("%", "%%")).execute_if(dialect="postgresql"),
    )
