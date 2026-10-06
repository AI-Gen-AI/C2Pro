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
    v_project uuid;
    v_current uuid;
    v_apply text;
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.id, NEW.tenant_id, NEW.project_id, NEW.parent_id, NEW.sort_order, NEW.code,
                             NEW.name, NEW.control_level, NEW.decomposition_kind, NEW.dictionary)
                    IS NOT DISTINCT FROM (OLD.id, OLD.tenant_id, OLD.project_id, OLD.parent_id, OLD.sort_order,
                             OLD.code, OLD.name, OLD.control_level, OLD.decomposition_kind, OLD.dictionary) THEN
        RETURN NEW;
    END IF;
    FOREACH v_project IN ARRAY CASE
            WHEN TG_OP = 'INSERT' THEN ARRAY[NEW.project_id]
            WHEN TG_OP = 'DELETE' THEN ARRAY[OLD.project_id]
            ELSE ARRAY[OLD.project_id, NEW.project_id] END LOOP
        -- A project being deleted takes its WBS with it (cascade).
        CONTINUE WHEN NOT EXISTS (SELECT 1 FROM public.projects p WHERE p.id = v_project);
        SELECT b.id INTO v_current FROM public.wbs_baselines b
         WHERE b.project_id = v_project ORDER BY b.baseline_no DESC LIMIT 1;
        CONTINUE WHEN v_current IS NULL;  -- no approved baseline: LEGACY_UNGOVERNED / NO_WBS
        v_apply := NULLIF(current_setting('c2pro.wbs_governed_apply', true), '');
        IF v_apply IS NULL OR NOT EXISTS (
               SELECT 1 FROM public.wbs_change_sets cs
                WHERE cs.id::text = v_apply AND cs.project_id = v_project AND cs.status = 'SUBMITTED'
                  AND cs.base_baseline_id = v_current) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'the WBS of this project is governed by an approved baseline: change it through a WBS change set';
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
