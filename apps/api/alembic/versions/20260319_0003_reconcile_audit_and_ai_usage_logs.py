"""Reconcile ai_usage_logs and audit_logs into Alembic ownership

Revision ID: 20260319_0003
Revises: 20260319_0002
Create Date: 2026-03-19 10:55:00.000000

TS-DB-MIG-REC-002
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0003"
down_revision: str | None = "20260319_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adopt operational audit and AI usage tables into the Alembic-owned path."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_usage_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
            model_name VARCHAR(100) NOT NULL,
            operation_type VARCHAR(50) NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            estimated_cost NUMERIC(10,4) DEFAULT 0,
            duration_ms INTEGER,
            status VARCHAR(20) DEFAULT 'success',
            error_message TEXT,
            log_metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50) NOT NULL,
            resource_id UUID,
            changes JSONB DEFAULT '{}',
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ai_usage_logs_tenant ON ai_usage_logs(tenant_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ai_usage_logs_project ON ai_usage_logs(project_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ai_usage_logs_created ON ai_usage_logs(created_at);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant ON audit_logs(tenant_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_user ON audit_logs(user_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_resource ON audit_logs(resource_type, resource_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_audit_logs_created ON audit_logs(created_at);
        """
    )

    op.execute(
        """
        ALTER TABLE ai_usage_logs ENABLE ROW LEVEL SECURITY;
        """
    )
    op.execute(
        """
        ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
        """
    )
    op.execute(
        """
        ALTER TABLE ai_usage_logs FORCE ROW LEVEL SECURITY;
        """
    )
    op.execute(
        """
        ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_ai_usage_logs ON ai_usage_logs;
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_ai_usage_logs
            ON ai_usage_logs
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )
    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs;
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_audit_logs
            ON audit_logs
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
        """
    )


def downgrade() -> None:
    """Remove operational tables adopted by this reconciliation revision."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_ai_usage_logs ON ai_usage_logs;")
    op.execute("DROP TABLE IF EXISTS audit_logs;")
    op.execute("DROP TABLE IF EXISTS ai_usage_logs;")
