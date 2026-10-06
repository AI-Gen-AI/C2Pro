-- PC-2a.2 (#896, ADR-029): governed WBS apply -- explicit retirements and the live-write guard.
-- Mirror of apps/api/alembic/versions/20261006_0002_pc2a2_wbs_governed_apply.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

CREATE TABLE public.wbs_change_set_retirements (
    change_set_id uuid NOT NULL,
    node_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    disposition text NOT NULL,
    source text NOT NULL,
    snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_wbs_change_set_retirements PRIMARY KEY (change_set_id, node_id),
    CONSTRAINT fk_wbs_change_set_retirements_change_set FOREIGN KEY (tenant_id, project_id, change_set_id)
        REFERENCES public.wbs_change_sets (tenant_id, project_id, id) ON DELETE CASCADE,
    CONSTRAINT ck_wbs_change_set_retirements_disposition CHECK (
        disposition IN ('REMOVED', 'SPLIT', 'MERGED', 'SUPERSEDED', 'RETIRED_ON_BASELINE')),
    CONSTRAINT ck_wbs_change_set_retirements_source CHECK (source IN ('baseline', 'legacy')),
    CONSTRAINT ck_wbs_change_set_retirements_legacy_disposition CHECK (
        disposition <> 'RETIRED_ON_BASELINE' OR source = 'legacy'),
    CONSTRAINT ck_wbs_change_set_retirements_snapshot CHECK (jsonb_typeof(snapshot) = 'object')
);

CREATE INDEX ix_wbs_change_set_retirements_tenant_project ON public.wbs_change_set_retirements (tenant_id, project_id);

CREATE INDEX ix_wbs_change_set_retirements_node ON public.wbs_change_set_retirements (node_id);

CREATE OR REPLACE FUNCTION public.wbs_change_set_retirements_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_status text;
    v_base uuid;
    v_project uuid;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS retirements are immutable: remove and add instead';
    END IF;
    SELECT cs.status, cs.base_baseline_id, cs.project_id INTO v_status, v_base, v_project
      FROM public.wbs_change_sets cs
     WHERE cs.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.change_set_id ELSE NEW.change_set_id END;
    IF NOT FOUND THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION USING ERRCODE = 'foreign_key_violation', MESSAGE = 'unknown WBS change set';
    END IF;
    IF v_status <> 'DRAFT' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS retirements are editable only while the change set is DRAFT';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF NEW.source = 'baseline' THEN
        IF v_base IS NULL OR NOT EXISTS (
               SELECT 1 FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = v_base AND bn.node_id = NEW.node_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'a baseline retirement must name an identity of the base baseline';
        END IF;
    ELSIF v_base IS NOT NULL OR NOT EXISTS (
              SELECT 1 FROM public.wbs_nodes w WHERE w.id = NEW.node_id AND w.project_id = v_project) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'only a first baseline retires live legacy rows of the same project';
    END IF;
    IF EXISTS (SELECT 1 FROM public.wbs_change_set_nodes n
                WHERE n.change_set_id = NEW.change_set_id AND n.node_id = NEW.node_id) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a retired WBS identity cannot stay in the candidate';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_nodes_governed_write_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_apply text;
    v_projects uuid[];
    v_tenants uuid[];
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.id, NEW.tenant_id, NEW.project_id, NEW.parent_id, NEW.sort_order, NEW.code,
                             NEW.name, NEW.control_level, NEW.decomposition_kind, NEW.dictionary)
                    IS NOT DISTINCT FROM (OLD.id, OLD.tenant_id, OLD.project_id, OLD.parent_id, OLD.sort_order,
                             OLD.code, OLD.name, OLD.control_level, OLD.decomposition_kind, OLD.dictionary) THEN
        RETURN NEW;  -- non-governed attributes (dates, budget, description, metadata, caches)
    END IF;
    -- A project or tenant being deleted takes its WBS with it: the FK cascade runs after its row is gone.
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
       AND (NOT EXISTS (SELECT 1 FROM public.projects p WHERE p.id = OLD.project_id)
            OR NOT EXISTS (SELECT 1 FROM public.tenants t WHERE t.id = OLD.tenant_id)) THEN
        RETURN OLD;
    END IF;
    -- Governed live WBS content (identity, ownership, hierarchy, order, code, name, control level,
    -- decomposition, dictionary) changes ONLY inside a governed approve = apply, in every authority
    -- state (NO_WBS, LEGACY_UNGOVERNED, APPROVED_BASELINE). The apply correlation must name a
    -- SUBMITTED change set of the row's tenant and project for which THIS transaction already
    -- inserted the baseline, chained to that change set's base. A committed baseline always
    -- belongs to an APPLIED change set (deferred commit check), so neither the session setting
    -- alone nor another transaction's baseline opens this gate. Rows hidden by the writer's RLS
    -- context (missing or foreign app.current_tenant) are simply not found: fail closed.
    v_apply := current_setting('c2pro.wbs_governed_apply', true);
    v_projects := CASE TG_OP WHEN 'INSERT' THEN ARRAY[NEW.project_id] WHEN 'DELETE' THEN ARRAY[OLD.project_id]
                  ELSE ARRAY[OLD.project_id, NEW.project_id] END;
    v_tenants := CASE TG_OP WHEN 'INSERT' THEN ARRAY[NEW.tenant_id] WHEN 'DELETE' THEN ARRAY[OLD.tenant_id]
                 ELSE ARRAY[OLD.tenant_id, NEW.tenant_id] END;
    FOR i IN 1 .. array_length(v_projects, 1) LOOP
        IF v_apply IS NULL
           OR v_apply !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           OR NOT EXISTS (
               SELECT 1
                 FROM public.wbs_change_sets cs
                 JOIN public.wbs_baselines b ON b.source_change_set_id = cs.id
                WHERE cs.id = v_apply::uuid
                  AND cs.project_id = v_projects[i] AND cs.tenant_id = v_tenants[i]
                  AND cs.status = 'SUBMITTED'
                  AND b.project_id = cs.project_id AND b.tenant_id = cs.tenant_id
                  AND b.parent_baseline_id IS NOT DISTINCT FROM cs.base_baseline_id
                  AND b.xmin = pg_current_xact_id()::xid) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'WBS_GOVERNANCE_REQUIRED: canonical WBS scope is governed through a WBS change set '
                          '(create or edit a candidate, submit it, approve = apply)';
        END IF;
    END LOOP;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END
$fn$;

REVOKE ALL ON FUNCTION public.wbs_change_set_retirements_guard() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_nodes_governed_write_guard() FROM PUBLIC;

CREATE TRIGGER trg_wbs_change_set_retirements_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_change_set_retirements FOR EACH ROW EXECUTE FUNCTION public.wbs_change_set_retirements_guard();

CREATE TRIGGER trg_wbs_nodes_governed_write_guard BEFORE INSERT OR DELETE OR UPDATE OF id, tenant_id, project_id, parent_id, sort_order, code, name, control_level, decomposition_kind, dictionary ON public.wbs_nodes FOR EACH ROW EXECUTE FUNCTION public.wbs_nodes_governed_write_guard();

ALTER TABLE public.wbs_change_set_retirements ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.wbs_change_set_retirements FORCE ROW LEVEL SECURITY;

CREATE POLICY wbs_change_set_retirements_tenant_select ON public.wbs_change_set_retirements FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_retirements_tenant_insert ON public.wbs_change_set_retirements FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_retirements_tenant_update ON public.wbs_change_set_retirements FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_retirements_tenant_delete ON public.wbs_change_set_retirements FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DO $do$
DECLARE
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = v_role) THEN
            EXECUTE 'REVOKE ALL ON TABLE public.wbs_change_set_retirements FROM ' || quote_ident(v_role);
            -- Supabase default privileges grant EXECUTE on new public functions to these roles.
            EXECUTE 'REVOKE ALL ON FUNCTION public.wbs_change_set_retirements_guard(), public.wbs_nodes_governed_write_guard() FROM ' || quote_ident(v_role);
        END IF;
    END LOOP;
END
$do$;
