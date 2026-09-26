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
  * No-op when the column is already ``public.alertseverity`` (fresh/CI databases
    and re-runs land here — this is the *normal* path; only drifted prod converts).
  * Converts ONLY from the exact diagnosed drift shape: ``character varying`` of
    length 20, ``NOT NULL``, no default. Any other ``varchar`` shape aborts rather
    than normalising an unapproved state; any other type aborts too.
  * Requires the target enum to be ``public.alertseverity`` (schema-qualified via
    pg_type + pg_namespace) with exactly the canonical labels
    ``{critical, high, medium, low}`` — validated before mutation.
  * Rejects NULL or non-label values BEFORE altering — combined with the single
    migration transaction this guarantees no partial mutation.
  * ``lock_timeout`` is bounded so the ALTER fails/rolls back rather than waiting
    on a long-held lock.
  * ``NOT NULL`` and the (absent) default are preserved; ``ix_alerts_severity``
    is rebuilt automatically by ``ALTER COLUMN ... TYPE``.

Blocking dependency ``public.v_project_alerts`` (a ``security_invoker`` RLS view
that projects ``a.severity``) is captured (definition + owner + grants), dropped,
and recreated. Its ACL is restored to EXACTLY the captured set — any privilege
introduced by ``CREATE VIEW`` or by schema default privileges is stripped and the
captured grants re-applied verbatim, then the effective grant set and owner are
verified to match the capture (mismatch raises and rolls back). This preserves
the view's privileges exactly and never silently tightens or loosens them.

Reversible: ``downgrade`` restores ``character varying(20)`` symmetrically with
the same exact view-contract restoration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0001"
down_revision: str | None = "20260814_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Restore public.v_project_alerts to EXACTLY the captured ACL + owner, then verify.
# Shared between upgrade/downgrade; expects the PL/pgSQL variables v_viewdef,
# v_owner and v_grants (jsonb) to already hold the pre-drop capture.
_RESTORE_VIEW_SQL = """
    EXECUTE 'CREATE VIEW public.v_project_alerts AS ' || v_viewdef;
    IF v_owner IS NOT NULL THEN
        EXECUTE format('ALTER VIEW public.v_project_alerts OWNER TO %I', v_owner);
    END IF;
    -- v_project_alerts is definitionally a tenant-scoped RLS view: always
    -- security_invoker so it never runs with the owner's privileges.
    EXECUTE 'ALTER VIEW public.v_project_alerts SET (security_invoker = true)';

    -- Strip whatever CREATE VIEW / schema default privileges introduced (except
    -- the owner's implicit privileges), then re-apply the captured grants exactly.
    FOR r IN
        SELECT DISTINCT grantee
          FROM information_schema.role_table_grants
         WHERE table_schema = 'public' AND table_name = 'v_project_alerts'
    LOOP
        IF r.grantee = 'PUBLIC' THEN
            EXECUTE 'REVOKE ALL ON public.v_project_alerts FROM PUBLIC';
        ELSIF v_owner IS NULL OR r.grantee <> v_owner THEN
            EXECUTE format('REVOKE ALL ON public.v_project_alerts FROM %I', r.grantee);
        END IF;
    END LOOP;
    FOR g IN SELECT value FROM jsonb_array_elements(v_grants) LOOP
        EXECUTE format('GRANT %s ON public.v_project_alerts TO %s%s',
            g->>'priv',
            CASE WHEN g->>'grantee' = 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(g->>'grantee') END,
            CASE WHEN g->>'grantable' = 'YES' THEN ' WITH GRANT OPTION' ELSE '' END);
    END LOOP;

    -- Fail (roll back) unless the effective NON-OWNER grants match the capture
    -- exactly. The owner is compared separately by identity below: an owner always
    -- holds every privilege implicitly, and its ACL representation (implicit
    -- relacl=NULL vs materialised) is not a security-relevant difference, whereas a
    -- non-owner extra (e.g. from schema default privileges) is exactly what must
    -- not survive.
    SELECT string_agg(grantee || '|' || privilege_type || '|' || is_grantable, ','
                      ORDER BY grantee, privilege_type)
      INTO v_grants_after
      FROM information_schema.role_table_grants
     WHERE table_schema = 'public' AND table_name = 'v_project_alerts'
       AND (v_owner IS NULL OR grantee <> v_owner);
    SELECT string_agg((value->>'grantee') || '|' || (value->>'priv') || '|' || (value->>'grantable'), ','
                      ORDER BY (value->>'grantee'), (value->>'priv'))
      INTO v_grants_expected
      FROM jsonb_array_elements(v_grants)
     WHERE (v_owner IS NULL OR (value->>'grantee') <> v_owner);
    IF v_grants_after IS DISTINCT FROM v_grants_expected THEN
        RAISE EXCEPTION 'v_project_alerts non-owner grant set changed on recreate; expected [%] got [%]',
            v_grants_expected, v_grants_after;
    END IF;

    SELECT pg_get_userbyid(relowner) INTO v_owner_after
      FROM pg_class WHERE oid = 'public.v_project_alerts'::regclass;
    IF v_owner_after IS DISTINCT FROM v_owner THEN
        RAISE EXCEPTION 'v_project_alerts owner changed on recreate; expected % got %',
            v_owner, v_owner_after;
    END IF;
"""

_CAPTURE_VIEW_SQL = """
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
"""


# varchar(20) NOT NULL no-default -> public.alertseverity, preserving the view.
_UPGRADE_SQL = f"""
DO $$
DECLARE
    v_udt            text;
    v_udt_schema     text;
    v_len            integer;
    v_nullable       text;
    v_default        text;
    v_labels         text[];
    v_bad            text;
    v_viewdef        text;
    v_owner          text;
    v_owner_after    text;
    v_grants         jsonb := '[]'::jsonb;
    v_grants_after   text;
    v_grants_expected text;
    v_has_view       boolean := false;
    r                record;
    g                jsonb;
BEGIN
    -- Fail fast instead of blocking prod writers on a long-held lock.
    PERFORM set_config('lock_timeout', '5000', true);

    SELECT udt_name, udt_schema, character_maximum_length, is_nullable, column_default
      INTO v_udt, v_udt_schema, v_len, v_nullable, v_default
      FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity';

    IF v_udt IS NULL THEN
        RAISE EXCEPTION 'public.alerts.severity column not found';
    END IF;

    -- Already conformed -> idempotent no-op (fresh/CI databases and re-runs).
    IF v_udt_schema = 'public' AND v_udt = 'alertseverity' THEN
        RAISE NOTICE 'alerts.severity already conforms to public.alertseverity; no-op';
        RETURN;
    END IF;

    -- Convert ONLY from the exact diagnosed drift shape.
    IF v_udt <> 'varchar' THEN
        RAISE EXCEPTION
            'alerts.severity has unexpected type %.%; expected character varying(20) or public.alertseverity',
            v_udt_schema, v_udt;
    END IF;
    IF v_len IS DISTINCT FROM 20 OR v_nullable <> 'NO' OR v_default IS NOT NULL THEN
        RAISE EXCEPTION
            'alerts.severity is character varying but not the diagnosed drift shape '
            '(length=%, is_nullable=%, default=%); expected varchar(20) NOT NULL with no default '
            '- aborting rather than normalising an unapproved state',
            v_len, v_nullable, v_default;
    END IF;

    -- Target enum must be public.alertseverity with exactly the canonical labels.
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'alertseverity' AND t.typtype = 'e'
    ) THEN
        RAISE EXCEPTION 'public.alertseverity enum type is missing; cannot conform alerts.severity';
    END IF;
    SELECT array_agg(e.enumlabel ORDER BY e.enumlabel)
      INTO v_labels
      FROM pg_enum e
      JOIN pg_type t ON t.oid = e.enumtypid
      JOIN pg_namespace n ON n.oid = t.typnamespace
     WHERE n.nspname = 'public' AND t.typname = 'alertseverity';
    IF v_labels IS DISTINCT FROM ARRAY['critical', 'high', 'low', 'medium'] THEN
        RAISE EXCEPTION
            'public.alertseverity labels % differ from the canonical set {{critical,high,medium,low}}',
            v_labels;
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

    -- Capture the dependent security_invoker view's full contract before dropping.
{_CAPTURE_VIEW_SQL}

    -- Conform the column. NOT NULL is preserved by ALTER TYPE; DROP DEFAULT keeps
    -- the no-default semantics. ix_alerts_severity is rebuilt automatically.
    ALTER TABLE public.alerts ALTER COLUMN severity DROP DEFAULT;
    ALTER TABLE public.alerts
        ALTER COLUMN severity TYPE public.alertseverity
        USING severity::text::public.alertseverity;

    IF v_has_view THEN
{_RESTORE_VIEW_SQL}
    END IF;
END $$;
"""


# public.alertseverity -> varchar(20) NOT NULL no-default, symmetric restore.
_DOWNGRADE_SQL = f"""
DO $$
DECLARE
    v_udt            text;
    v_udt_schema     text;
    v_viewdef        text;
    v_owner          text;
    v_owner_after    text;
    v_grants         jsonb := '[]'::jsonb;
    v_grants_after   text;
    v_grants_expected text;
    v_has_view       boolean := false;
    r                record;
    g                jsonb;
BEGIN
    PERFORM set_config('lock_timeout', '5000', true);

    SELECT udt_name, udt_schema INTO v_udt, v_udt_schema
      FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'alerts' AND column_name = 'severity';

    IF v_udt IS NULL THEN
        RAISE EXCEPTION 'public.alerts.severity column not found';
    ELSIF v_udt = 'varchar' THEN
        RAISE NOTICE 'alerts.severity already character varying; no-op';
        RETURN;
    ELSIF NOT (v_udt_schema = 'public' AND v_udt = 'alertseverity') THEN
        RAISE EXCEPTION
            'alerts.severity has unexpected type %.%; expected public.alertseverity or character varying',
            v_udt_schema, v_udt;
    END IF;

{_CAPTURE_VIEW_SQL}

    ALTER TABLE public.alerts ALTER COLUMN severity DROP DEFAULT;
    ALTER TABLE public.alerts
        ALTER COLUMN severity TYPE varchar(20)
        USING severity::text;

    IF v_has_view THEN
{_RESTORE_VIEW_SQL}
    END IF;
END $$;
"""


def upgrade() -> None:
    op.get_bind().execute(sa.text(_UPGRADE_SQL))


def downgrade() -> None:
    op.get_bind().execute(sa.text(_DOWNGRADE_SQL))
