"""S5-01: explicit, revocable, append-only per-project HITL review grants.

Revision ID: 20261101_0001
Revises: 20261022_0001

WHAT THIS ADDS (additive only)
------------------------------
* ``project_review_grants``: one row per explicit grant of ONE capability (``READ_REVIEW``, ``REVIEW_FINDING`` or
  ``APPROVE_CANDIDATE``) on ONE project to ONE user. No capability implies another. History is kept: a grant is never
  edited or deleted, only revoked once (who, when, why).
* Principal = ``users.id`` (stable per Clerk user across organizations) scoped by ``tenant_id``. There is deliberately
  NO composite key ``(tenant_id, user_id) -> users (tenant_id, id)``: ``get_current_user`` reassigns ``users.tenant_id``
  when the Clerk organization changes and that key would make the sign-in fail for any granted user. Membership is
  proved at CHECK time (``users.tenant_id = grant.tenant_id``), so a grant of tenant A is never a grant of tenant B.
* Two governed writer functions (``project_review_grant_create`` / ``project_review_grant_revoke``) that write the grant
  AND its ``project_events`` audit event in ONE transaction. A guard trigger refuses any write that does not come from
  them, refuses DELETE always, and re-validates the actors in the database (defence in depth).
* Forced row-level security (tenant context) and ``REVOKE`` of every privilege from PUBLIC / anon / authenticated.
* Existing tenants are marked ``hitl_project_authorization.mode = 'off'`` (``transitional``) so nothing changes for them
  until an operator promotes them; a tenant WITHOUT the setting is treated as ``enforce`` (fail closed).

NOT IN THIS MIGRATION: no grant is created (no bootstrap, no backfill), no role is created or granted EXECUTE, no
production behaviour is switched on. ``EXECUTE`` on the writer functions belongs to the runtime principal the
deployment designates (owner bootstrap), like the other capability roles in this repo.
"""
from __future__ import annotations

from alembic import op

revision = "20261101_0001"
down_revision = "20261022_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261101000100_s5_project_review_grants.sql"

_TENANT_CTX = "NULLIF(current_setting('app.current_tenant', true), '')::uuid"
_WRITER_GUC = "app.project_review_grants_writer"

UPGRADE_STATEMENTS: tuple[str, ...] = (
    """CREATE TABLE public.project_review_grants (
    grant_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    user_id uuid NOT NULL,
    permission varchar(20) NOT NULL,
    granted_by uuid NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    grant_reason text NOT NULL,
    self_grant_exception boolean NOT NULL DEFAULT false,
    exception_reason text,
    revoked_by uuid,
    revoked_at timestamptz,
    revoke_reason text,
    CONSTRAINT fk_prg_project FOREIGN KEY (tenant_id, project_id)
        REFERENCES public.projects (tenant_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_prg_user FOREIGN KEY (user_id) REFERENCES public.users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_prg_granter FOREIGN KEY (granted_by) REFERENCES public.users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_prg_revoker FOREIGN KEY (revoked_by) REFERENCES public.users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_prg_permission CHECK (permission IN ('READ_REVIEW', 'REVIEW_FINDING', 'APPROVE_CANDIDATE')),
    CONSTRAINT ck_prg_reason CHECK (length(btrim(grant_reason)) > 0),
    CONSTRAINT ck_prg_exception CHECK (
        (self_grant_exception AND length(btrim(coalesce(exception_reason, ''))) > 0)
        OR (NOT self_grant_exception AND exception_reason IS NULL)),
    CONSTRAINT ck_prg_revocation CHECK (
        (revoked_at IS NULL AND revoked_by IS NULL AND revoke_reason IS NULL)
        OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL
            AND length(btrim(coalesce(revoke_reason, ''))) > 0 AND revoked_at >= granted_at))
)""",
    "CREATE UNIQUE INDEX uq_prg_active ON public.project_review_grants (tenant_id, project_id, user_id, permission) WHERE revoked_at IS NULL",
    "CREATE INDEX ix_prg_lookup ON public.project_review_grants (tenant_id, user_id, project_id) WHERE revoked_at IS NULL",
    f"""CREATE FUNCTION public.project_review_grants_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_ctx uuid := {_TENANT_CTX};
    v_exception jsonb;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'project review grants are append-only';
    END IF;
    IF coalesce(current_setting('{_WRITER_GUC}', true), '') <> 'fn' THEN
        RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
            MESSAGE = 'project review grants are written only by the governed functions';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF v_ctx IS DISTINCT FROM NEW.tenant_id THEN
            RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
                MESSAGE = 'a grant must be written inside its own tenant context';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM public.users u
                        WHERE u.id = NEW.user_id AND u.tenant_id = NEW.tenant_id AND u.is_active) THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'the grantee must be an active member of the tenant';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM public.users u
                        WHERE u.id = NEW.granted_by AND u.tenant_id = NEW.tenant_id AND u.is_active
                          AND u.role::text = 'admin') THEN
            RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
                MESSAGE = 'only an active ADMIN of the tenant administers grants';
        END IF;
        IF NEW.granted_by = NEW.user_id THEN
            SELECT t.settings #> '{{hitl_project_authorization,single_person_exception}}'
              INTO v_exception FROM public.tenants t WHERE t.id = NEW.tenant_id;
            IF NOT (NEW.self_grant_exception
                    AND coalesce(v_exception ->> 'enabled', 'false') = 'true'
                    AND length(btrim(coalesce(v_exception ->> 'reason', ''))) > 0
                    AND length(btrim(coalesce(v_exception ->> 'granted_by', ''))) > 0
                    AND length(btrim(coalesce(v_exception ->> 'granted_at', ''))) > 0) THEN
                RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
                    MESSAGE = 'a grant cannot be self-granted without the audited single-person exception';
            END IF;
        ELSIF NEW.self_grant_exception THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'the exception marks only a self-grant';
        END IF;
        IF NEW.revoked_at IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation', MESSAGE = 'a grant is created active';
        END IF;
        RETURN NEW;
    END IF;

    -- UPDATE: the only legal one is the single revocation of an active grant, by an ADMIN of the same tenant
    IF OLD.revoked_at IS NOT NULL
       OR (NEW.grant_id, NEW.tenant_id, NEW.project_id, NEW.user_id, NEW.permission, NEW.granted_by,
           NEW.granted_at, NEW.grant_reason, NEW.self_grant_exception, NEW.exception_reason)
          IS DISTINCT FROM
          (OLD.grant_id, OLD.tenant_id, OLD.project_id, OLD.user_id, OLD.permission, OLD.granted_by,
           OLD.granted_at, OLD.grant_reason, OLD.self_grant_exception, OLD.exception_reason) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'a grant can only be revoked, once';
    END IF;
    IF v_ctx IS DISTINCT FROM OLD.tenant_id THEN
        RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
            MESSAGE = 'a grant must be revoked inside its own tenant context';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.users u
                    WHERE u.id = NEW.revoked_by AND u.tenant_id = OLD.tenant_id AND u.is_active
                      AND u.role::text = 'admin') THEN
        RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
            MESSAGE = 'only an active ADMIN of the tenant revokes grants';
    END IF;
    RETURN NEW;
END
$fn$""",
    "CREATE TRIGGER trg_project_review_grants_guard BEFORE INSERT OR UPDATE OR DELETE ON public.project_review_grants FOR EACH ROW EXECUTE FUNCTION public.project_review_grants_guard()",
    f"""CREATE FUNCTION public.project_review_grant_create(
    p_tenant_id uuid, p_project_id uuid, p_user_id uuid, p_permission text,
    p_granted_by uuid, p_reason text, p_exception_reason text DEFAULT NULL)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_grant uuid := gen_random_uuid();
BEGIN
    PERFORM set_config('{_WRITER_GUC}', 'fn', true);
    INSERT INTO public.project_review_grants
        (grant_id, tenant_id, project_id, user_id, permission, granted_by, grant_reason,
         self_grant_exception, exception_reason)
    VALUES (v_grant, p_tenant_id, p_project_id, p_user_id, p_permission, p_granted_by, p_reason,
            p_exception_reason IS NOT NULL, p_exception_reason);
    INSERT INTO public.project_events (event_id, project_id, tenant_id, event_type, payload, actor, evidence_refs, occurred_at, created_at)
    VALUES (gen_random_uuid(), p_project_id, p_tenant_id, 'hitl.project_grant_created',
            jsonb_build_object('grant_id', v_grant, 'user_id', p_user_id, 'permission', p_permission,
                               'granted_by', p_granted_by, 'reason', p_reason,
                               'self_grant_exception', p_exception_reason IS NOT NULL,
                               'exception_reason', p_exception_reason),
            p_granted_by::text, '[]'::jsonb, (now() AT TIME ZONE 'utc'), (now() AT TIME ZONE 'utc'));
    PERFORM set_config('{_WRITER_GUC}', '', true);
    RETURN v_grant;
END
$fn$""",
    f"""CREATE FUNCTION public.project_review_grant_revoke(
    p_tenant_id uuid, p_grant_id uuid, p_revoked_by uuid, p_reason text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_row public.project_review_grants%ROWTYPE;
BEGIN
    PERFORM set_config('{_WRITER_GUC}', 'fn', true);
    SELECT * INTO v_row FROM public.project_review_grants
     WHERE grant_id = p_grant_id AND tenant_id = p_tenant_id FOR UPDATE;
    IF NOT FOUND OR v_row.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'no_data_found',
            MESSAGE = 'the grant does not exist or is already revoked';
    END IF;
    UPDATE public.project_review_grants
       SET revoked_by = p_revoked_by, revoked_at = clock_timestamp(), revoke_reason = p_reason
     WHERE grant_id = p_grant_id;
    INSERT INTO public.project_events (event_id, project_id, tenant_id, event_type, payload, actor, evidence_refs, occurred_at, created_at)
    VALUES (gen_random_uuid(), v_row.project_id, p_tenant_id, 'hitl.project_grant_revoked',
            jsonb_build_object('grant_id', p_grant_id, 'user_id', v_row.user_id, 'permission', v_row.permission,
                               'revoked_by', p_revoked_by, 'reason', p_reason),
            p_revoked_by::text, '[]'::jsonb, (now() AT TIME ZONE 'utc'), (now() AT TIME ZONE 'utc'));
    PERFORM set_config('{_WRITER_GUC}', '', true);
END
$fn$""",
    "ALTER TABLE public.project_review_grants ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.project_review_grants FORCE ROW LEVEL SECURITY",
    f"CREATE POLICY project_review_grants_select ON public.project_review_grants FOR SELECT USING (tenant_id = {_TENANT_CTX})",
    f"CREATE POLICY project_review_grants_insert ON public.project_review_grants FOR INSERT WITH CHECK (tenant_id = {_TENANT_CTX})",
    f"CREATE POLICY project_review_grants_update ON public.project_review_grants FOR UPDATE USING (tenant_id = {_TENANT_CTX}) WITH CHECK (tenant_id = {_TENANT_CTX})",
    "REVOKE ALL ON TABLE public.project_review_grants FROM PUBLIC",
    "REVOKE ALL ON FUNCTION public.project_review_grants_guard() FROM PUBLIC",
    "REVOKE ALL ON FUNCTION public.project_review_grant_create(uuid, uuid, uuid, text, uuid, text, text) FROM PUBLIC",
    "REVOKE ALL ON FUNCTION public.project_review_grant_revoke(uuid, uuid, uuid, text) FROM PUBLIC",
    """DO $do$
DECLARE v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_role) THEN
            EXECUTE 'REVOKE ALL ON TABLE public.project_review_grants FROM ' || quote_ident(v_role);
            EXECUTE 'REVOKE ALL ON FUNCTION public.project_review_grants_guard() FROM ' || quote_ident(v_role);
            EXECUTE 'REVOKE ALL ON FUNCTION public.project_review_grant_create(uuid, uuid, uuid, text, uuid, text, text) FROM ' || quote_ident(v_role);
            EXECUTE 'REVOKE ALL ON FUNCTION public.project_review_grant_revoke(uuid, uuid, uuid, text) FROM ' || quote_ident(v_role);
        END IF;
    END LOOP;
END
$do$""",
    # Existing tenants keep today's behaviour until an operator promotes them; a tenant WITHOUT this setting is ENFORCE.
    """UPDATE public.tenants
   SET settings = jsonb_set(coalesce(settings, '{}'::jsonb), '{hitl_project_authorization}',
       jsonb_build_object('mode', 'off', 'transitional', true,
                          'reason', 'tenant existed before S5-01: project authorization not yet enforced',
                          'marked_by', 'alembic 20261101_0001'), true)
 WHERE NOT (coalesce(settings, '{}'::jsonb) ? 'hitl_project_authorization')""",
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "UPDATE public.tenants SET settings = settings #- '{hitl_project_authorization}' WHERE settings #>> '{hitl_project_authorization,marked_by}' = 'alembic 20261101_0001'",
    "DROP FUNCTION public.project_review_grant_revoke(uuid, uuid, uuid, text)",
    "DROP FUNCTION public.project_review_grant_create(uuid, uuid, uuid, text, uuid, text, text)",
    "DROP TABLE public.project_review_grants",
    "DROP FUNCTION public.project_review_grants_guard()",
)


def supabase_sql() -> str:
    header = (
        "-- S5-01: explicit, revocable, append-only per-project HITL review grants (stable principal users.id).\n"
        "-- Mirror of apps/api/alembic/versions/20261101_0001_s5_project_review_grants.py.\n"
    )
    return header + "\n" + "\n\n".join(s.strip() + ";" for s in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
