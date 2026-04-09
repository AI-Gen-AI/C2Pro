"""Add wbs_nodes table with nested set model

Revision ID: 20260406_0001_add_wbs_nodes_table
Revises: 20260406_0004_add_alert_type_discriminator
Create Date: 2026-04-06 15:00:00.000000

TASK-BCK-029: WBS API Endpoint with nested set model

Creates wbs_nodes table with nested set model for efficient tree operations:
- lft/rgt: Left and right boundaries for subtree queries
- depth: Tree level for hierarchy traversal
- parent_id: Direct parent reference for convenience

Tree operation examples:
- All descendants: WHERE lft > node.lft AND rgt < node.rgt
- All ancestors: WHERE lft < node.lft AND rgt > node.rgt
- Leaf nodes: WHERE rgt = lft + 1
- Immediate children: WHERE parent_id = node.id
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260406_0001_add_wbs_nodes_table'
down_revision = '20260406_0004_add_alert_type_discriminator'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM types
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'wbsnodetype') THEN
                CREATE TYPE wbsnodetype AS ENUM ('deliverable', 'work_package', 'activity', 'milestone');
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'wbsnodestatus') THEN
                CREATE TYPE wbsnodestatus AS ENUM ('not_started', 'in_progress', 'completed', 'on_hold', 'cancelled');
            END IF;
        END
        $$;
        """
    )

    # Create wbs_nodes table
    op.create_table(
        "wbs_nodes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),

        # Node identity
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),

        # Nested Set Model fields
        sa.Column("lft", sa.Integer(), nullable=False),
        sa.Column("rgt", sa.Integer(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),

        # Node classification
        sa.Column(
            "node_type",
            postgresql.ENUM(
                "deliverable", "work_package", "activity", "milestone",
                name="wbsnodetype",
                create_type=False,
            ),
            nullable=False,
            server_default="work_package",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "not_started", "in_progress", "completed", "on_hold", "cancelled",
                name="wbsnodestatus",
                create_type=False,
            ),
            nullable=False,
            server_default="not_started",
        ),

        # Scheduling
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),

        # Budget
        sa.Column("budget_allocated", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("budget_spent", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),

        # Metadata
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),

        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),

        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["wbs_nodes.id"], ondelete="SET NULL"),
        sa.CheckConstraint("lft < rgt", name="ck_wbs_nodes_lft_lt_rgt"),
        sa.CheckConstraint("lft > 0", name="ck_wbs_nodes_lft_positive"),
        sa.CheckConstraint("depth >= 0", name="ck_wbs_nodes_depth_non_negative"),
        sa.CheckConstraint("budget_spent >= 0", name="ck_wbs_nodes_budget_spent_non_negative"),
        sa.UniqueConstraint("project_id", "code", name="uq_wbs_nodes_project_code"),
    )

    # Create indexes for efficient tree queries
    op.create_index("ix_wbs_nodes_project_id", "wbs_nodes", ["project_id"])
    op.create_index("ix_wbs_nodes_tenant_id", "wbs_nodes", ["tenant_id"])
    op.create_index("ix_wbs_nodes_parent_id", "wbs_nodes", ["parent_id"])
    op.create_index("ix_wbs_nodes_lft", "wbs_nodes", ["lft"])
    op.create_index("ix_wbs_nodes_rgt", "wbs_nodes", ["rgt"])
    op.create_index("ix_wbs_nodes_depth", "wbs_nodes", ["depth"])
    op.create_index("ix_wbs_nodes_status", "wbs_nodes", ["status"])
    op.create_index("ix_wbs_nodes_node_type", "wbs_nodes", ["node_type"])

    # Composite index for tree traversal queries
    op.create_index(
        "ix_wbs_nodes_project_lft_rgt",
        "wbs_nodes",
        ["project_id", "lft", "rgt"],
    )

    # Enable RLS on wbs_nodes table
    op.execute(
        """
        ALTER TABLE wbs_nodes ENABLE ROW LEVEL SECURITY;
        """
    )

    # Create RLS policy for tenant isolation
    op.execute(
        """
        DROP POLICY IF EXISTS wbs_nodes_tenant_isolation ON wbs_nodes;

        CREATE POLICY wbs_nodes_tenant_isolation
        ON wbs_nodes
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::uuid);
        """
    )


def downgrade() -> None:
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS wbs_nodes_tenant_isolation ON wbs_nodes;")

    # Drop indexes
    op.drop_index("ix_wbs_nodes_project_lft_rgt", table_name="wbs_nodes")
    op.drop_index("ix_wbs_nodes_node_type", table_name="wbs_nodes")
    op.drop_index("ix_wbs_nodes_status", table_name="wbs_nodes")
    op.drop_index("ix_wbs_nodes_depth", table_name="wbs_nodes")
    op.drop_index("ix_wbs_nodes_rgt", table_name="wbs_nodes")
    op.drop_index("ix_wbs_nodes_lft", table_name="wbs_nodes")
    op.drop_index("ix_wbs_nodes_parent_id", table_name="wbs_nodes")
    op.drop_index("ix_wbs_nodes_tenant_id", table_name="wbs_nodes")
    op.drop_index("ix_wbs_nodes_project_id", table_name="wbs_nodes")

    # Drop table
    op.drop_table("wbs_nodes")

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS wbsnodestatus;")
    op.execute("DROP TYPE IF EXISTS wbsnodetype;")
