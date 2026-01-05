"""Initial migration - Tenants, Users, Projects

Revision ID: 20260104_0000
Revises:
Create Date: 2026-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260104_0000'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUM types
    op.execute("CREATE TYPE subscriptionplan AS ENUM ('free', 'starter', 'professional', 'enterprise')")
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'user', 'viewer', 'api')")
    op.execute("CREATE TYPE projectstatus AS ENUM ('draft', 'active', 'completed', 'archived')")
    op.execute("CREATE TYPE projecttype AS ENUM ('construction', 'engineering', 'industrial', 'infrastructure', 'other')")

    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('subscription_plan', postgresql.ENUM('free', 'starter', 'professional', 'enterprise', name='subscriptionplan', create_type=False), nullable=False),
        sa.Column('subscription_status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('subscription_started_at', sa.DateTime(), nullable=True),
        sa.Column('subscription_expires_at', sa.DateTime(), nullable=True),
        sa.Column('ai_budget_monthly', sa.Float(), nullable=False, server_default='50.0'),
        sa.Column('ai_spend_current', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ai_spend_last_reset', sa.DateTime(), nullable=True),
        sa.Column('max_projects', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('max_users', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_storage_gb', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_tenants_created', 'tenants', ['created_at'])
    op.create_index('ix_tenants_subscription', 'tenants', ['subscription_plan', 'subscription_status'])

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=True),
        sa.Column('oauth_provider', sa.String(length=50), nullable=True),
        sa.Column('oauth_id', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('role', postgresql.ENUM('admin', 'user', 'viewer', 'api', name='userrole', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_verified_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('last_activity', sa.DateTime(), nullable=True),
        sa.Column('login_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_last_login', 'users', ['last_login'])
    op.create_index('ix_users_tenant_email', 'users', ['tenant_id', 'email'])
    op.create_index('ix_users_tenant_role', 'users', ['tenant_id', 'role'])

    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('project_type', postgresql.ENUM('construction', 'engineering', 'industrial', 'infrastructure', 'other', name='projecttype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('draft', 'active', 'completed', 'archived', name='projectstatus', create_type=False), nullable=False),
        sa.Column('estimated_budget', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='EUR'),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('coherence_score', sa.Integer(), nullable=True),
        sa.Column('last_analysis_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('coherence_score >= 0 AND coherence_score <= 100', name='ck_projects_coherence_score')
    )
    op.create_index('ix_projects_tenant_created', 'projects', ['tenant_id', 'created_at'])
    op.create_index('ix_projects_tenant_status', 'projects', ['tenant_id', 'status'])

    # Enable Row Level Security (commented out - uncomment when using Supabase)
    # op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    # op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    # op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Drop tables
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('tenants')

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS projecttype")
    op.execute("DROP TYPE IF EXISTS projectstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS subscriptionplan")
