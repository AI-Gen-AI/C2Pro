"""Conform public.alerts.severity from character varying to the alertseverity enum.

Revision ID: 20260824_0001
Revises: 20260814_0002
Create Date: 2026-08-24

TASK-P0a-004 — schema conformance.

Out-of-band production schema drift: the canonical schema (20260315_0002 +
the ORM ``Alert.severity = mapped_column(SQLEnum(AlertSeverity, ...))``) defines
``public.alerts.severity`` as the ``alertseverity`` enum, but production drifted
to ``character varying(20)``. The ORM casts filters to ``::alertseverity``, so on
the drifted column every severity comparison raised
``operator does not exist: character varying = alertseverity`` (HTTP 500). PR
#558 shipped a *runtime* tolerance (compare the column AS TEXT); this migration
removes the drift itself so the column matches the ORM contract.

Direction: ``varchar(20) -> public.alertseverity``.

Guarded / idempotent by design:
  * No-op when the column is already ``alertseverity`` (fresh/CI databases and
    re-runs land here — this is the *normal* path; only drifted prod converts).
  * Converts only from the expected ``character varying`` state; any other type
    raises rather than guessing.
  * Requires the ``alertseverity`` enum to exist first.
  * Rejects NULL or non-label values BEFORE altering — combined with the single
    migration transaction this guarantees no partial mutation.
  * ``lock_timeout`` is bounded so the ALTER fails/rolls back rather than waiting
    on a long-held lock.
  * ``NOT NULL`` and the (absent) default are preserved; ``ix_alerts_severity``
    is rebuilt automatically by ``ALTER COLUMN ... TYPE``.

Blocking dependency ``public.v_project_alerts`` (a ``security_invoker`` RLS view
that projects ``a.severity``) is captured (definition + owner + grants), dropped,
and recreated with its owner, grants and ``security_invoker = true`` restored.
Grants are re-applied exactly as captured so this schema change never silently
tightens (or loosens) the view's privileges.

Reversible: ``downgrade`` restores ``character varying(20)`` symmetrically.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0001"
down_revision: str | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# varchar(20) -> public.alertseverity, preserving the dependent view contract.
_UPGRADE_SQL = """
DO $$
DECLARE
    v_udt      text;
    v_bad      text;
    v_viewdef  text;
    v_owner    text;
    v_grants   jsonb := '[]'::jsonb;
    v_has_view boolean := false;
    g          jsonb;
BEGIN
    -- Fail fast instead of blocking prod writers on a long-held lock.
    PERFORM set_config('lock_timeout', '5000', true);

    -- The target enum must already exist (created in 20260315_0002).
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alertseverity') THEN
        RAISE EXCEPTION 'alertseverity enum type is missing; cannot conform alerts.severity';
    END IF;

    SELECT udt_name INTO v_udt
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity';

    IF v_udt IS NULL THEN
        RAISE EXCEPTION 'public.alerts.severity column not found';
    ELSIF v_udt = 'alertseverity' THEN
        RAISE NOTICE 'alerts.severity already conforms to alertseverity; no-op';
        RETURN;
    ELSIF v_udt <> 'varchar' THEN
        RAISE EXCEPTION
            'alerts.severity has unexpected type %; expected character varying or alertseverity', v_udt;
    END IF;

    -- Reject NULL / unconvertible values BEFORE any DDL (no partial mutation).
    IF EXISTS (SELECT 1 FROM public.alerts WHERE severity IS NULL) THEN
        RAISE EXCEPTION 'alerts.severity contains NULL values; cannot cast to a NOT NULL enum';
    END IF;
    SELECT string_agg(DISTINCT severity::text, ', ')
      INTO v_bad
      FROM public.alerts
     WHERE severity::text NOT IN ('critical', 'high', 'medium', 'low');
    IF v_bad IS NOT NULL THEN
        RAISE EXCEPTION 'alerts.severity has values outside alertseverity labels: %', v_bad;
    END IF;

    -- Capture the dependent security_invoker view's full contract before dropping it.
    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = 'v_project_alerts' AND c.relkind = 'v'
    ) THEN
        v_has_view := true;
        SELECT pg_get_viewdef('public.v_project_alerts'::regclass, true) INTO v_viewdef;
        SELECT pg_get_userbyid(c.relowner) INTO v_owner
          FROM pg_class c WHERE c.oid = 'public.v_project_alerts'::regclass;
        SELECT COALESCE(
                   jsonb_agg(jsonb_build_object(
                       'grantee', grantee, 'priv', privilege_type, 'grantable', is_grantable)),
                   '[]'::jsonb)
          INTO v_grants
          FROM information_schema.role_table_grants
         WHERE table_schema = 'public' AND table_name = 'v_project_alerts';
        DROP VIEW public.v_project_alerts;
    END IF;

    -- Conform the column. NOT NULL is preserved by ALTER TYPE; DROP DEFAULT keeps
    -- the no-default semantics (no-op when no default exists). ix_alerts_severity
    -- is rebuilt automatically.
    ALTER TABLE public.alerts ALTER COLUMN severity DROP DEFAULT;
    ALTER TABLE public.alerts
        ALTER COLUMN severity TYPE public.alertseverity
        USING severity::text::public.alertseverity;

    -- Recreate the view and restore owner, grants and security_invoker.
    IF v_has_view THEN
        EXECUTE 'CREATE VIEW public.v_project_alerts AS ' || v_viewdef;
        IF v_owner IS NOT NULL THEN
            EXECUTE format('ALTER VIEW public.v_project_alerts OWNER TO %I', v_owner);
        END IF;
        -- v_project_alerts is definitionally a tenant-scoped RLS view: always
        -- security_invoker so it never runs with the owner's privileges.
        EXECUTE 'ALTER VIEW public.v_project_alerts SET (security_invoker = true)';
        FOR g IN SELECT value FROM jsonb_array_elements(v_grants) LOOP
            EXECUTE format('GRANT %s ON public.v_project_alerts TO %s%s',
                g->>'priv',
                CASE WHEN g->>'grantee' = 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(g->>'grantee') END,
                CASE WHEN g->>'grantable' = 'YES' THEN ' WITH GRANT OPTION' ELSE '' END);
        END LOOP;
    END IF;
END $$;
"""


# public.alertseverity -> varchar(20), symmetric restore of the view contract.
_DOWNGRADE_SQL = """
DO $$
DECLARE
    v_udt      text;
    v_viewdef  text;
    v_owner    text;
    v_grants   jsonb := '[]'::jsonb;
    v_has_view boolean := false;
    g          jsonb;
BEGIN
    PERFORM set_config('lock_timeout', '5000', true);

    SELECT udt_name INTO v_udt
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity';

    IF v_udt IS NULL THEN
        RAISE EXCEPTION 'public.alerts.severity column not found';
    ELSIF v_udt = 'varchar' THEN
        RAISE NOTICE 'alerts.severity already character varying; no-op';
        RETURN;
    ELSIF v_udt <> 'alertseverity' THEN
        RAISE EXCEPTION
            'alerts.severity has unexpected type %; expected alertseverity or character varying', v_udt;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = 'v_project_alerts' AND c.relkind = 'v'
    ) THEN
        v_has_view := true;
        SELECT pg_get_viewdef('public.v_project_alerts'::regclass, true) INTO v_viewdef;
        SELECT pg_get_userbyid(c.relowner) INTO v_owner
          FROM pg_class c WHERE c.oid = 'public.v_project_alerts'::regclass;
        SELECT COALESCE(
                   jsonb_agg(jsonb_build_object(
                       'grantee', grantee, 'priv', privilege_type, 'grantable', is_grantable)),
                   '[]'::jsonb)
          INTO v_grants
          FROM information_schema.role_table_grants
         WHERE table_schema = 'public' AND table_name = 'v_project_alerts';
        DROP VIEW public.v_project_alerts;
    END IF;

    ALTER TABLE public.alerts ALTER COLUMN severity DROP DEFAULT;
    ALTER TABLE public.alerts
        ALTER COLUMN severity TYPE varchar(20)
        USING severity::text;

    IF v_has_view THEN
        EXECUTE 'CREATE VIEW public.v_project_alerts AS ' || v_viewdef;
        IF v_owner IS NOT NULL THEN
            EXECUTE format('ALTER VIEW public.v_project_alerts OWNER TO %I', v_owner);
        END IF;
        EXECUTE 'ALTER VIEW public.v_project_alerts SET (security_invoker = true)';
        FOR g IN SELECT value FROM jsonb_array_elements(v_grants) LOOP
            EXECUTE format('GRANT %s ON public.v_project_alerts TO %s%s',
                g->>'priv',
                CASE WHEN g->>'grantee' = 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(g->>'grantee') END,
                CASE WHEN g->>'grantable' = 'YES' THEN ' WITH GRANT OPTION' ELSE '' END);
        END LOOP;
    END IF;
END $$;
"""


def upgrade() -> None:
    op.get_bind().execute(sa.text(_UPGRADE_SQL))


def downgrade() -> None:
    op.get_bind().execute(sa.text(_DOWNGRADE_SQL))
