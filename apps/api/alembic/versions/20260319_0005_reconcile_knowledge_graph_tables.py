"""Reconcile knowledge graph tables

Revision ID: 20260319_0005
Revises: 20260319_0004
Create Date: 2026-03-19 13:05:00.000000

TS-DB-MIG-REC-004
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0005"
down_revision: str | None = "20260319_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adopt SQL-runner-only knowledge graph tables into Alembic."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            entity_type VARCHAR(50) NOT NULL,
            entity_id UUID NOT NULL,
            label VARCHAR(255),
            properties JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT kg_nodes_project_entity_unique UNIQUE (project_id, entity_type, entity_id)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source_node_id UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
            target_node_id UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
            relationship_type VARCHAR(100) NOT NULL,
            properties JSONB DEFAULT '{}'::jsonb,
            confidence NUMERIC(3,2) DEFAULT 1.0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT kg_edges_unique UNIQUE (
                project_id,
                source_node_id,
                target_node_id,
                relationship_type
            )
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_project ON knowledge_graph_nodes(project_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON knowledge_graph_nodes(entity_type);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_entity ON knowledge_graph_nodes(entity_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kg_edges_project ON knowledge_graph_edges(project_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON knowledge_graph_edges(source_node_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON knowledge_graph_edges(target_node_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kg_edges_rel ON knowledge_graph_edges(relationship_type);
        """
    )

    op.execute("ALTER TABLE knowledge_graph_nodes ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE knowledge_graph_edges ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE knowledge_graph_nodes FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE knowledge_graph_edges FORCE ROW LEVEL SECURITY;")

    project_guard = """
        project_id IN (
            SELECT id
            FROM projects
            WHERE tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
    """

    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_kg_nodes ON knowledge_graph_nodes;
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_kg_nodes
            ON knowledge_graph_nodes
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_kg_edges ON knowledge_graph_edges;
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_kg_edges
            ON knowledge_graph_edges
            FOR ALL
            USING ({project_guard})
            WITH CHECK ({project_guard});
        """
    )


def downgrade() -> None:
    """Remove knowledge graph tables adopted by this revision."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation_kg_edges ON knowledge_graph_edges;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_kg_nodes ON knowledge_graph_nodes;")
    op.execute("DROP TABLE IF EXISTS knowledge_graph_edges;")
    op.execute("DROP TABLE IF EXISTS knowledge_graph_nodes;")
