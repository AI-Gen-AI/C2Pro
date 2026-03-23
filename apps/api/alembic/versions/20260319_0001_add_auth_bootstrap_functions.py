"""Add auth bootstrap lookup functions

Revision ID: 20260319_0001
Revises: 20260318_0002
Create Date: 2026-03-19 09:20:00.000000

TS-E2E-SEC-TNT-001
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0001"
down_revision: str | None = "20260318_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create narrowly scoped auth bootstrap lookup functions."""
    op.execute(
        """
        CREATE SCHEMA IF NOT EXISTS auth_bootstrap;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_tenant_by_id(p_tenant_id uuid)
        RETURNS TABLE (
            tenant_id uuid,
            is_active boolean,
            clerk_org_id text,
            tenant_name text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT t.id, t.is_active, t.clerk_org_id, t.name
            FROM public.tenants AS t
            WHERE t.id = p_tenant_id
            LIMIT 1;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_tenant_by_clerk_org_id(p_clerk_org_id text)
        RETURNS TABLE (
            tenant_id uuid,
            is_active boolean,
            clerk_org_id text,
            tenant_name text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT t.id, t.is_active, t.clerk_org_id, t.name
            FROM public.tenants AS t
            WHERE t.clerk_org_id = p_clerk_org_id
            LIMIT 1;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_personal_tenant_by_name(p_tenant_name text)
        RETURNS TABLE (
            tenant_id uuid,
            is_active boolean,
            clerk_org_id text,
            tenant_name text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT t.id, t.is_active, t.clerk_org_id, t.name
            FROM public.tenants AS t
            WHERE t.name = p_tenant_name
            LIMIT 1;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_user_by_email(p_email text)
        RETURNS TABLE (
            user_id uuid,
            tenant_id uuid,
            email text,
            is_active boolean,
            hashed_password text,
            role text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT u.id, u.tenant_id, u.email, u.is_active, u.hashed_password, u.role::text
            FROM public.users AS u
            WHERE u.email = p_email
            LIMIT 1;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_user_by_clerk_user_id(p_clerk_user_id text)
        RETURNS TABLE (
            user_id uuid,
            tenant_id uuid,
            email text,
            is_active boolean,
            hashed_password text,
            role text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT u.id, u.tenant_id, u.email, u.is_active, u.hashed_password, u.role::text
            FROM public.users AS u
            WHERE u.clerk_user_id = p_clerk_user_id
            LIMIT 1;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_bootstrap.create_tenant(
            p_tenant_name text,
            p_tenant_slug text,
            p_clerk_org_id text DEFAULT NULL
        )
        RETURNS TABLE (
            tenant_id uuid,
            is_active boolean,
            clerk_org_id text,
            tenant_name text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            INSERT INTO public.tenants (
                name, slug, clerk_org_id, subscription_plan, subscription_status,
                subscription_started_at, ai_budget_monthly, ai_spend_current,
                ai_spend_last_reset, max_projects, max_users, max_storage_gb,
                settings, is_active
            )
            VALUES (
                p_tenant_name,
                p_tenant_slug,
                p_clerk_org_id,
                'free',
                'active',
                now(),
                50.0,
                0.0,
                now(),
                5,
                3,
                10,
                '{}'::jsonb,
                true
            )
            RETURNING id, is_active, clerk_org_id, name;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_bootstrap.create_user(
            p_tenant_id uuid,
            p_email text,
            p_hashed_password text,
            p_first_name text,
            p_last_name text,
            p_role text DEFAULT 'user',
            p_clerk_user_id text DEFAULT NULL
        )
        RETURNS TABLE (
            user_id uuid,
            tenant_id uuid,
            email text,
            is_active boolean,
            hashed_password text,
            role text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            INSERT INTO public.users (
                tenant_id, email, hashed_password, clerk_user_id,
                first_name, last_name, role, is_active, is_verified, preferences
            )
            VALUES (
                p_tenant_id,
                p_email,
                p_hashed_password,
                p_clerk_user_id,
                p_first_name,
                p_last_name,
                p_role::userrole,
                true,
                false,
                '{}'::jsonb
            )
            RETURNING id, tenant_id, email, is_active, hashed_password, role::text;
        $$;
        """
    )

    op.execute("REVOKE ALL ON SCHEMA auth_bootstrap FROM PUBLIC;")
    op.execute("REVOKE ALL ON FUNCTION auth_bootstrap.create_tenant(text, text, text) FROM PUBLIC;")
    op.execute(
        "REVOKE ALL ON FUNCTION auth_bootstrap.create_user(uuid, text, text, text, text, text, text) FROM PUBLIC;"
    )
    op.execute("REVOKE ALL ON FUNCTION auth_bootstrap.lookup_tenant_by_id(uuid) FROM PUBLIC;")
    op.execute(
        "REVOKE ALL ON FUNCTION auth_bootstrap.lookup_tenant_by_clerk_org_id(text) FROM PUBLIC;"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION auth_bootstrap.lookup_personal_tenant_by_name(text) FROM PUBLIC;"
    )
    op.execute("REVOKE ALL ON FUNCTION auth_bootstrap.lookup_user_by_email(text) FROM PUBLIC;")
    op.execute(
        "REVOKE ALL ON FUNCTION auth_bootstrap.lookup_user_by_clerk_user_id(text) FROM PUBLIC;"
    )


def downgrade() -> None:
    """Drop auth bootstrap lookup functions."""
    op.execute("DROP FUNCTION IF EXISTS auth_bootstrap.create_user(uuid, text, text, text, text, text, text);")
    op.execute("DROP FUNCTION IF EXISTS auth_bootstrap.create_tenant(text, text, text);")
    op.execute("DROP FUNCTION IF EXISTS auth_bootstrap.lookup_user_by_clerk_user_id(text);")
    op.execute("DROP FUNCTION IF EXISTS auth_bootstrap.lookup_user_by_email(text);")
    op.execute("DROP FUNCTION IF EXISTS auth_bootstrap.lookup_personal_tenant_by_name(text);")
    op.execute("DROP FUNCTION IF EXISTS auth_bootstrap.lookup_tenant_by_clerk_org_id(text);")
    op.execute("DROP FUNCTION IF EXISTS auth_bootstrap.lookup_tenant_by_id(uuid);")
    op.execute("DROP SCHEMA IF EXISTS auth_bootstrap;")
