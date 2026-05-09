"""add_tenant_id_and_enable_rls_hardening

Revision ID: 20260503_0001
Revises: 20260425_0001
Create Date: 2026-05-08 22:10:06.627332

SECURITY HARDENING:
1. Adds missing tenant_id column to clause_embeddings, analyses, and alerts.
2. Enables RLS on clause_embeddings, analyses, alerts, and audit_logs.
3. Implements fail-closed RLS policies for tenant isolation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260503_0001'
down_revision: Union[str, None] = '20260425_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add tenant_id to tables where it is missing
    # clause_embeddings
    op.add_column('clause_embeddings', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    # analyses
    op.add_column('analyses', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    # alerts
    op.add_column('alerts', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    # coherence_results
    op.add_column('coherence_results', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))

    # 2. Populate tenant_id from projects table
    op.execute("""
        UPDATE clause_embeddings ce
        SET tenant_id = p.tenant_id
        FROM projects p
        WHERE ce.project_id = p.id
    """)
    op.execute("""
        UPDATE analyses a
        SET tenant_id = p.tenant_id
        FROM projects p
        WHERE a.project_id = p.id
    """)
    op.execute("""
        UPDATE alerts al
        SET tenant_id = p.tenant_id
        FROM projects p
        WHERE al.project_id = p.id
    """)
    op.execute("""
        UPDATE coherence_results cr
        SET tenant_id = p.tenant_id
        FROM projects p
        WHERE cr.project_id = p.id
    """)

    # 3. Columns stay nullable=True — NOT NULL deferred until all rows confirmed clean.
    # FK constraints to 'tenants' skipped — table managed outside Alembic scope.

    # 4. Add indices
    op.create_index('ix_clause_embeddings_tenant', 'clause_embeddings', ['tenant_id'])
    op.create_index('ix_analyses_tenant', 'analyses', ['tenant_id'])
    op.create_index('ix_alerts_tenant', 'alerts', ['tenant_id'])
    op.create_index('ix_coherence_results_tenant', 'coherence_results', ['tenant_id'])

    # 6. Enable RLS and create fail-closed policies
    tables = ['clause_embeddings', 'analyses', 'alerts', 'audit_logs', 'coherence_results']
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        
        # Drop existing policies if any
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_delete ON {table}")

        # Create new fail-closed policies
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation_select ON {table}
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """)
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation_insert ON {table}
            FOR INSERT
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """)
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation_update ON {table}
            FOR UPDATE
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """)
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation_delete ON {table}
            FOR DELETE
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """)


def downgrade() -> None:
    # Disable RLS
    tables = ['clause_embeddings', 'analyses', 'alerts', 'audit_logs']
    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_delete ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop indices, FKs and columns
    op.drop_index('ix_alerts_tenant', 'alerts')
    op.drop_index('ix_analyses_tenant', 'analyses')
    op.drop_index('ix_clause_embeddings_tenant', 'clause_embeddings')
    
    op.drop_constraint('fk_alerts_tenant', 'alerts', type_='foreignkey')
    op.drop_constraint('fk_analyses_tenant', 'analyses', type_='foreignkey')
    op.drop_constraint('fk_clause_embeddings_tenant', 'clause_embeddings', type_='foreignkey')
    
    op.drop_column('alerts', 'tenant_id')
    op.drop_column('analyses', 'tenant_id')
    op.drop_column('clause_embeddings', 'tenant_id')
