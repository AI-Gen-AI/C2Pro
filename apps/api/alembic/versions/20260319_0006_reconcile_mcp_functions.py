"""Reconcile MCP function surface

Revision ID: 20260319_0006
Revises: 20260319_0005
Create Date: 2026-03-19 14:10:00.000000

TS-DB-MIG-REC-005
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0006"
down_revision: str | None = "20260319_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adopt the full MCP allowlisted function surface into Alembic."""
    op.execute("DROP FUNCTION IF EXISTS public.fn_get_clause_by_id(uuid, uuid);")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_get_clause_by_id(
            p_tenant_id uuid,
            p_clause_id uuid
        )
        RETURNS TABLE(
            id uuid,
            project_id uuid,
            document_id uuid,
            clause_code varchar,
            clause_type text,
            title varchar,
            full_text text,
            extraction_confidence double precision,
            manually_verified boolean,
            created_at timestamp without time zone
        )
        LANGUAGE sql
        STABLE
        AS $$
            SELECT
                c.id,
                c.project_id,
                c.document_id,
                c.clause_code,
                c.clause_type::text,
                c.title,
                c.full_text,
                c.extraction_confidence,
                c.manually_verified,
                c.created_at
            FROM clauses AS c
            JOIN projects AS p ON p.id = c.project_id
            WHERE p.tenant_id = p_tenant_id
              AND c.id = p_clause_id
        $$;
        """
    )

    op.execute("DROP FUNCTION IF EXISTS public.fn_get_stakeholder_by_id(uuid, uuid);")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_get_stakeholder_by_id(
            p_tenant_id uuid,
            p_stakeholder_id uuid
        )
        RETURNS TABLE(
            id uuid,
            project_id uuid,
            name varchar,
            role varchar,
            organization varchar,
            department varchar,
            quadrant text,
            email varchar,
            approval_status text,
            created_at timestamp without time zone
        )
        LANGUAGE plpgsql
        STABLE
        AS $$
        DECLARE
            approval_expr text;
        BEGIN
            approval_expr := CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'stakeholders'
                      AND column_name = 'approval_status'
                )
                THEN 's.approval_status::text'
                ELSE 'NULL::text'
            END;

            RETURN QUERY EXECUTE format(
                $sql$
                SELECT
                    s.id,
                    s.project_id,
                    s.name,
                    s.role,
                    s.organization,
                    s.department,
                    s.quadrant::text,
                    s.email,
                    %s AS approval_status,
                    s.created_at::timestamp without time zone
                FROM stakeholders AS s
                JOIN projects AS p ON p.id = s.project_id
                WHERE p.tenant_id = $1
                  AND s.id = $2
                $sql$,
                approval_expr
            )
            USING p_tenant_id, p_stakeholder_id;
        END
        $$;
        """
    )

    op.execute(
        "DROP FUNCTION IF EXISTS public.fn_get_neighbors(uuid, uuid);"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_get_neighbors(
            p_tenant_id uuid,
            p_node_id uuid
        )
        RETURNS TABLE(
            edge_id uuid,
            project_id uuid,
            node_id uuid,
            entity_type varchar,
            entity_id uuid,
            label varchar,
            node_properties jsonb,
            relationship_type varchar,
            edge_properties jsonb,
            confidence numeric,
            direction text
        )
        LANGUAGE plpgsql
        STABLE
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'knowledge_graph_nodes'
            ) OR NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'knowledge_graph_edges'
            ) THEN
                RETURN;
            END IF;

            RETURN QUERY
            SELECT
                e.id AS edge_id,
                e.project_id,
                neighbor.id AS node_id,
                neighbor.entity_type,
                neighbor.entity_id,
                neighbor.label,
                neighbor.properties AS node_properties,
                e.relationship_type,
                e.properties AS edge_properties,
                e.confidence,
                'outgoing'::text AS direction
            FROM knowledge_graph_edges AS e
            JOIN knowledge_graph_nodes AS neighbor ON neighbor.id = e.target_node_id
            JOIN projects AS p ON p.id = e.project_id
            WHERE p.tenant_id = p_tenant_id
              AND e.source_node_id = p_node_id

            UNION ALL

            SELECT
                e.id AS edge_id,
                e.project_id,
                neighbor.id AS node_id,
                neighbor.entity_type,
                neighbor.entity_id,
                neighbor.label,
                neighbor.properties AS node_properties,
                e.relationship_type,
                e.properties AS edge_properties,
                e.confidence,
                'incoming'::text AS direction
            FROM knowledge_graph_edges AS e
            JOIN knowledge_graph_nodes AS neighbor ON neighbor.id = e.source_node_id
            JOIN projects AS p ON p.id = e.project_id
            WHERE p.tenant_id = p_tenant_id
              AND e.target_node_id = p_node_id
            ORDER BY direction, node_id;
        END
        $$;
        """
    )

    op.execute(
        "DROP FUNCTION IF EXISTS public.fn_find_path(uuid, uuid, uuid, integer);"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_find_path(
            p_tenant_id uuid,
            p_source_node_id uuid,
            p_target_node_id uuid,
            p_max_depth integer DEFAULT 6
        )
        RETURNS TABLE(
            path_nodes uuid[],
            path_labels text[],
            path_edge_types text[],
            hop_count integer
        )
        LANGUAGE plpgsql
        STABLE
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'knowledge_graph_nodes'
            ) OR NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'knowledge_graph_edges'
            ) THEN
                RETURN;
            END IF;

            RETURN QUERY
            WITH RECURSIVE search AS (
                SELECT
                    n.id AS node_id,
                    ARRAY[n.id]::uuid[] AS path_nodes,
                    ARRAY[]::text[] AS path_edge_types,
                    0 AS depth
                FROM knowledge_graph_nodes AS n
                JOIN projects AS p ON p.id = n.project_id
                WHERE p.tenant_id = p_tenant_id
                  AND n.id = p_source_node_id

                UNION ALL

                SELECT
                    candidate.next_node_id,
                    search.path_nodes || candidate.next_node_id,
                    search.path_edge_types || candidate.relationship_type,
                    search.depth + 1
                FROM search
                JOIN LATERAL (
                    SELECT
                        CASE
                            WHEN e.source_node_id = search.node_id THEN e.target_node_id
                            ELSE e.source_node_id
                        END AS next_node_id,
                        e.relationship_type::text AS relationship_type
                    FROM knowledge_graph_edges AS e
                    JOIN projects AS p ON p.id = e.project_id
                    WHERE p.tenant_id = p_tenant_id
                      AND (e.source_node_id = search.node_id OR e.target_node_id = search.node_id)
                ) AS candidate ON TRUE
                WHERE search.depth < GREATEST(COALESCE(p_max_depth, 6), 0)
                  AND NOT (candidate.next_node_id = ANY(search.path_nodes))
            ),
            best_path AS (
                SELECT
                    search.path_nodes AS best_nodes,
                    search.path_edge_types AS best_edge_types
                FROM search
                WHERE search.node_id = p_target_node_id
                ORDER BY cardinality(search.path_nodes)
                LIMIT 1
            )
            SELECT
                bp.best_nodes,
                ARRAY(
                    SELECT COALESCE(n.label, n.entity_type || ':' || n.entity_id::text)
                    FROM unnest(bp.best_nodes) WITH ORDINALITY AS u(node_id, ord)
                    JOIN knowledge_graph_nodes AS n ON n.id = u.node_id
                    ORDER BY u.ord
                )::text[] AS path_labels,
                bp.best_edge_types,
                GREATEST(cardinality(bp.best_nodes) - 1, 0) AS hop_count
            FROM best_path AS bp;
        END
        $$;
        """
    )

    op.execute(
        "DROP FUNCTION IF EXISTS public.fn_get_subgraph(uuid, uuid, uuid, integer);"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_get_subgraph(
            p_tenant_id uuid,
            p_project_id uuid,
            p_root_node_id uuid DEFAULT NULL,
            p_max_depth integer DEFAULT 2
        )
        RETURNS TABLE(
            depth integer,
            edge_id uuid,
            project_id uuid,
            source_node_id uuid,
            source_label varchar,
            source_entity_type varchar,
            target_node_id uuid,
            target_label varchar,
            target_entity_type varchar,
            relationship_type varchar,
            edge_properties jsonb,
            confidence numeric
        )
        LANGUAGE plpgsql
        STABLE
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'knowledge_graph_nodes'
            ) OR NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'knowledge_graph_edges'
            ) THEN
                RETURN;
            END IF;

            RETURN QUERY
            WITH RECURSIVE project_scope AS (
                SELECT p.id
                FROM projects AS p
                WHERE p.id = p_project_id
                  AND p.tenant_id = p_tenant_id
            ),
            reachable AS (
                SELECT
                    p_root_node_id AS node_id,
                    0 AS walk_depth,
                    ARRAY[p_root_node_id]::uuid[] AS path_nodes
                FROM project_scope
                WHERE p_root_node_id IS NOT NULL

                UNION ALL

                SELECT
                    CASE
                        WHEN e.source_node_id = reachable.node_id THEN e.target_node_id
                        ELSE e.source_node_id
                    END AS node_id,
                    reachable.walk_depth + 1,
                    reachable.path_nodes || CASE
                        WHEN e.source_node_id = reachable.node_id THEN e.target_node_id
                        ELSE e.source_node_id
                    END
                FROM reachable
                JOIN knowledge_graph_edges AS e ON e.project_id = p_project_id
                WHERE (e.source_node_id = reachable.node_id OR e.target_node_id = reachable.node_id)
                  AND reachable.walk_depth < GREATEST(COALESCE(p_max_depth, 2), 0)
                  AND NOT (
                      CASE
                          WHEN e.source_node_id = reachable.node_id THEN e.target_node_id
                          ELSE e.source_node_id
                      END = ANY(reachable.path_nodes)
                  )
            ),
            visited AS (
                SELECT
                    node_id,
                    MIN(walk_depth) AS node_depth
                FROM reachable
                GROUP BY node_id
            )
            SELECT
                COALESCE(vs.node_depth, vt.node_depth, 1) AS depth,
                e.id AS edge_id,
                e.project_id,
                e.source_node_id,
                source_node.label AS source_label,
                source_node.entity_type AS source_entity_type,
                e.target_node_id,
                target_node.label AS target_label,
                target_node.entity_type AS target_entity_type,
                e.relationship_type,
                e.properties AS edge_properties,
                e.confidence
            FROM project_scope AS ps
            JOIN knowledge_graph_edges AS e ON e.project_id = ps.id
            JOIN knowledge_graph_nodes AS source_node ON source_node.id = e.source_node_id
            JOIN knowledge_graph_nodes AS target_node ON target_node.id = e.target_node_id
            LEFT JOIN visited AS vs ON vs.node_id = e.source_node_id
            LEFT JOIN visited AS vt ON vt.node_id = e.target_node_id
            WHERE (
                p_root_node_id IS NULL
                OR (vs.node_id IS NOT NULL AND vt.node_id IS NOT NULL)
            )
            ORDER BY COALESCE(vs.node_depth, vt.node_depth, 1), e.id;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Remove the MCP function surface adopted by this revision."""
    op.execute("DROP FUNCTION IF EXISTS public.fn_get_subgraph(uuid, uuid, uuid, integer);")
    op.execute("DROP FUNCTION IF EXISTS public.fn_find_path(uuid, uuid, uuid, integer);")
    op.execute("DROP FUNCTION IF EXISTS public.fn_get_neighbors(uuid, uuid);")
    op.execute("DROP FUNCTION IF EXISTS public.fn_get_stakeholder_by_id(uuid, uuid);")
    op.execute("DROP FUNCTION IF EXISTS public.fn_get_clause_by_id(uuid, uuid);")
