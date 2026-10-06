-- PC-2a.1 (#895, ADR-029): WBS governance foundation (change sets, candidate trees, baselines).
-- Mirror of apps/api/alembic/versions/20261006_0001_pc2a1_wbs_governance_foundation.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

ALTER TABLE public.projects ADD CONSTRAINT uq_projects_tenant_id UNIQUE (tenant_id, id);

ALTER TABLE public.wbs_nodes ADD COLUMN control_level text NOT NULL DEFAULT 'none', ADD COLUMN decomposition_kind text, ADD COLUMN dictionary jsonb, ADD CONSTRAINT ck_wbs_nodes_control_level CHECK (control_level IN ('none', 'control_account', 'work_package', 'planning_package')), ADD CONSTRAINT ck_wbs_nodes_decomposition_kind CHECK (decomposition_kind IS NULL OR (decomposition_kind ~ '^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$' AND (split_part(decomposition_kind, ':', 1) <> 'core' OR split_part(decomposition_kind, ':', 2) IN ('area', 'system', 'subsystem', 'discipline', 'deliverable', 'component', 'capability', 'phase', 'package', 'other')))), ADD CONSTRAINT ck_wbs_nodes_dictionary CHECK (dictionary IS NULL OR (jsonb_typeof(dictionary) = 'object' AND coalesce(dictionary ->> 'schema_version', '') = 'wbs-dictionary/v1'));

CREATE TABLE public.wbs_change_sets (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    base_baseline_id uuid,
    origin text NOT NULL,
    entry_mode text NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT',
    revision integer NOT NULL DEFAULT 1,
    title text NOT NULL,
    description text,
    profile_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by uuid NOT NULL,
    created_by_kind text NOT NULL,
    submitted_revision integer,
    submitted_digest text,
    submitted_by uuid,
    submitted_at timestamptz,
    decided_by uuid,
    decided_at timestamptz,
    decision_reason text,
    decided_self_approval boolean,
    closed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_wbs_change_sets_tenant_project_id UNIQUE (tenant_id, project_id, id),
    CONSTRAINT fk_wbs_change_sets_project FOREIGN KEY (tenant_id, project_id)
        REFERENCES public.projects (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT ck_wbs_change_sets_origin CHECK (origin IN ('manual', 'ai', 'import')),
    CONSTRAINT ck_wbs_change_sets_entry_mode CHECK (entry_mode IN ('GENERATE', 'IMPORT_REVIEW', 'CHANGE_BASELINE')),
    CONSTRAINT ck_wbs_change_sets_change_baseline_has_base CHECK (entry_mode <> 'CHANGE_BASELINE' OR base_baseline_id IS NOT NULL),
    CONSTRAINT ck_wbs_change_sets_status CHECK (status IN ('DRAFT', 'SUBMITTED', 'APPLIED', 'REJECTED', 'WITHDRAWN', 'STALE')),
    CONSTRAINT ck_wbs_change_sets_revision CHECK (revision >= 1),
    CONSTRAINT ck_wbs_change_sets_title CHECK (length(btrim(title)) BETWEEN 1 AND 300),
    CONSTRAINT ck_wbs_change_sets_refs CHECK (jsonb_typeof(profile_refs) = 'array' AND jsonb_typeof(evidence_refs) = 'array'),
    CONSTRAINT ck_wbs_change_sets_created_by_kind CHECK (created_by_kind IN ('human', 'ai', 'service')),
    CONSTRAINT ck_wbs_change_sets_submission_fields CHECK (num_nonnulls(submitted_revision, submitted_digest, submitted_by, submitted_at) IN (0, 4)),
    CONSTRAINT ck_wbs_change_sets_submitted_digest CHECK (submitted_digest IS NULL OR submitted_digest ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT ck_wbs_change_sets_submitted_states CHECK (status NOT IN ('SUBMITTED', 'APPLIED', 'REJECTED') OR (submitted_digest IS NOT NULL AND submitted_revision = revision)),
    CONSTRAINT ck_wbs_change_sets_draft_unsubmitted CHECK (status <> 'DRAFT' OR submitted_digest IS NULL),
    CONSTRAINT ck_wbs_change_sets_decision_fields CHECK (num_nonnulls(decided_by, decided_at, decided_self_approval) IN (0, 3)),
    CONSTRAINT ck_wbs_change_sets_decided_states CHECK ((status IN ('APPLIED', 'REJECTED')) = (decided_by IS NOT NULL)),
    CONSTRAINT ck_wbs_change_sets_self_approval CHECK (decided_by IS NULL OR decided_self_approval = (decided_by = submitted_by)),
    CONSTRAINT ck_wbs_change_sets_rejection_reason CHECK (status <> 'REJECTED' OR length(btrim(coalesce(decision_reason, ''))) > 0),
    CONSTRAINT ck_wbs_change_sets_closed CHECK ((status IN ('APPLIED', 'REJECTED', 'WITHDRAWN', 'STALE')) = (closed_at IS NOT NULL))
);

CREATE TABLE public.wbs_change_set_nodes (
    change_set_id uuid NOT NULL,
    node_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    parent_id uuid,
    sort_order integer NOT NULL,
    code text,
    name text NOT NULL,
    control_level text NOT NULL DEFAULT 'none',
    decomposition_kind text,
    dictionary jsonb,
    origin_kind text NOT NULL,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_wbs_change_set_nodes PRIMARY KEY (change_set_id, node_id),
    CONSTRAINT fk_wbs_change_set_nodes_change_set FOREIGN KEY (tenant_id, project_id, change_set_id)
        REFERENCES public.wbs_change_sets (tenant_id, project_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_wbs_change_set_nodes_parent FOREIGN KEY (change_set_id, parent_id)
        REFERENCES public.wbs_change_set_nodes (change_set_id, node_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT uq_wbs_change_set_nodes_sibling_order UNIQUE NULLS NOT DISTINCT (change_set_id, parent_id, sort_order)
        DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_wbs_change_set_nodes_not_own_parent CHECK (parent_id IS NULL OR parent_id <> node_id),
    CONSTRAINT ck_wbs_change_set_nodes_sort_order CHECK (sort_order >= 1),
    CONSTRAINT ck_wbs_change_set_nodes_code CHECK (code IS NULL OR length(btrim(code)) BETWEEN 1 AND 50),
    CONSTRAINT ck_wbs_change_set_nodes_name CHECK (length(btrim(name)) BETWEEN 1 AND 255),
    CONSTRAINT ck_wbs_change_set_nodes_origin_kind CHECK (origin_kind IN ('existing', 'minted', 'adopted_legacy')),
    CONSTRAINT ck_wbs_change_set_nodes_provenance CHECK (jsonb_typeof(provenance) = 'object'),
    CONSTRAINT ck_wbs_change_set_nodes_control_level CHECK (control_level IN ('none', 'control_account', 'work_package', 'planning_package')),
    CONSTRAINT ck_wbs_change_set_nodes_decomposition_kind CHECK (decomposition_kind IS NULL OR (
        decomposition_kind ~ '^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$'
        AND (split_part(decomposition_kind, ':', 1) <> 'core' OR split_part(decomposition_kind, ':', 2) IN ('area', 'system', 'subsystem', 'discipline', 'deliverable', 'component', 'capability', 'phase', 'package', 'other')))),
    CONSTRAINT ck_wbs_change_set_nodes_dictionary CHECK (dictionary IS NULL OR (
        jsonb_typeof(dictionary) = 'object' AND coalesce(dictionary ->> 'schema_version', '') = 'wbs-dictionary/v1'))
);

CREATE TABLE public.wbs_change_set_lineage (
    change_set_id uuid NOT NULL,
    kind text NOT NULL,
    source_node_id uuid NOT NULL,
    target_node_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_wbs_change_set_lineage PRIMARY KEY (change_set_id, kind, source_node_id, target_node_id),
    CONSTRAINT fk_wbs_change_set_lineage_change_set FOREIGN KEY (tenant_id, project_id, change_set_id)
        REFERENCES public.wbs_change_sets (tenant_id, project_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_wbs_change_set_lineage_target FOREIGN KEY (change_set_id, target_node_id)
        REFERENCES public.wbs_change_set_nodes (change_set_id, node_id) ON DELETE CASCADE,
    CONSTRAINT ck_wbs_change_set_lineage_kind CHECK (kind IN ('SPLIT', 'MERGE', 'SUPERSEDES')),
    CONSTRAINT ck_wbs_change_set_lineage_distinct CHECK (source_node_id <> target_node_id)
);

CREATE TABLE public.wbs_baselines (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    baseline_no integer NOT NULL,
    parent_baseline_id uuid,
    source_change_set_id uuid NOT NULL,
    tree_digest text NOT NULL,
    change_set_digest text NOT NULL,
    node_count integer NOT NULL,
    approved_by uuid NOT NULL,
    approved_by_kind text NOT NULL,
    self_approved boolean NOT NULL DEFAULT false,
    profile_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    applied_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_wbs_baselines_tenant_project_id UNIQUE (tenant_id, project_id, id),
    CONSTRAINT uq_wbs_baselines_project_no UNIQUE (project_id, baseline_no),
    CONSTRAINT uq_wbs_baselines_linear_history UNIQUE NULLS NOT DISTINCT (project_id, parent_baseline_id),
    CONSTRAINT uq_wbs_baselines_source_change_set UNIQUE (source_change_set_id),
    CONSTRAINT fk_wbs_baselines_project FOREIGN KEY (tenant_id, project_id)
        REFERENCES public.projects (tenant_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_wbs_baselines_parent FOREIGN KEY (tenant_id, project_id, parent_baseline_id)
        REFERENCES public.wbs_baselines (tenant_id, project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_wbs_baselines_source_change_set FOREIGN KEY (tenant_id, project_id, source_change_set_id)
        REFERENCES public.wbs_change_sets (tenant_id, project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_wbs_baselines_baseline_no CHECK (baseline_no >= 1),
    CONSTRAINT ck_wbs_baselines_first CHECK ((parent_baseline_id IS NULL) = (baseline_no = 1)),
    CONSTRAINT ck_wbs_baselines_digests CHECK (tree_digest ~ '^sha256:[0-9a-f]{64}$' AND change_set_digest ~ '^sha256:[0-9a-f]{64}$'),
    CONSTRAINT ck_wbs_baselines_node_count CHECK (node_count >= 0),
    CONSTRAINT ck_wbs_baselines_human_approver CHECK (approved_by_kind = 'human'),
    CONSTRAINT ck_wbs_baselines_profile_refs CHECK (jsonb_typeof(profile_refs) = 'array')
);

CREATE TABLE public.wbs_baseline_nodes (
    baseline_id uuid NOT NULL,
    node_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    parent_id uuid,
    sort_order integer NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    control_level text NOT NULL DEFAULT 'none',
    decomposition_kind text,
    dictionary jsonb,
    CONSTRAINT pk_wbs_baseline_nodes PRIMARY KEY (baseline_id, node_id),
    CONSTRAINT fk_wbs_baseline_nodes_baseline FOREIGN KEY (tenant_id, project_id, baseline_id)
        REFERENCES public.wbs_baselines (tenant_id, project_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_wbs_baseline_nodes_parent FOREIGN KEY (baseline_id, parent_id)
        REFERENCES public.wbs_baseline_nodes (baseline_id, node_id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT uq_wbs_baseline_nodes_sibling_order UNIQUE NULLS NOT DISTINCT (baseline_id, parent_id, sort_order),
    CONSTRAINT uq_wbs_baseline_nodes_code UNIQUE (baseline_id, code),
    CONSTRAINT ck_wbs_baseline_nodes_not_own_parent CHECK (parent_id IS NULL OR parent_id <> node_id),
    CONSTRAINT ck_wbs_baseline_nodes_sort_order CHECK (sort_order >= 1),
    CONSTRAINT ck_wbs_baseline_nodes_code CHECK (length(btrim(code)) BETWEEN 1 AND 50),
    CONSTRAINT ck_wbs_baseline_nodes_name CHECK (length(btrim(name)) BETWEEN 1 AND 255),
    CONSTRAINT ck_wbs_baseline_nodes_control_level CHECK (control_level IN ('none', 'control_account', 'work_package', 'planning_package')),
    CONSTRAINT ck_wbs_baseline_nodes_decomposition_kind CHECK (decomposition_kind IS NULL OR (
        decomposition_kind ~ '^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$'
        AND (split_part(decomposition_kind, ':', 1) <> 'core' OR split_part(decomposition_kind, ':', 2) IN ('area', 'system', 'subsystem', 'discipline', 'deliverable', 'component', 'capability', 'phase', 'package', 'other')))),
    CONSTRAINT ck_wbs_baseline_nodes_dictionary CHECK (dictionary IS NULL OR (
        jsonb_typeof(dictionary) = 'object' AND coalesce(dictionary ->> 'schema_version', '') = 'wbs-dictionary/v1'))
);

ALTER TABLE public.wbs_change_sets ADD CONSTRAINT fk_wbs_change_sets_base_baseline FOREIGN KEY (tenant_id, project_id, base_baseline_id) REFERENCES public.wbs_baselines (tenant_id, project_id, id) ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

CREATE UNIQUE INDEX uq_wbs_change_sets_one_application ON public.wbs_change_sets (project_id, base_baseline_id) NULLS NOT DISTINCT WHERE status = 'APPLIED';

CREATE INDEX ix_wbs_change_sets_project_status ON public.wbs_change_sets (tenant_id, project_id, status);

CREATE INDEX ix_wbs_change_set_lineage_target ON public.wbs_change_set_lineage (change_set_id, target_node_id);

CREATE INDEX ix_wbs_baselines_project_applied ON public.wbs_baselines (project_id, applied_at);

CREATE INDEX ix_wbs_baseline_nodes_node_id ON public.wbs_baseline_nodes (node_id);

CREATE OR REPLACE FUNCTION public.wbs_governance_require_user_role(p_tenant uuid, p_user uuid, p_roles text[], p_action text)
RETURNS void
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_role text;
BEGIN
    SELECT u.role::text INTO v_role FROM public.users u
     WHERE u.id = p_user AND u.tenant_id = p_tenant AND u.is_active;
    IF v_role IS NULL OR NOT (v_role = ANY (p_roles)) THEN
        RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
            MESSAGE = 'WBS governance: ' || p_action || ' requires an active human '
                      || array_to_string(p_roles, ' or ') || ' of the tenant';
    END IF;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_governance_requires_distinct_approver(p_tenant uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
    SELECT COALESCE((SELECT t.settings #>> '{wbs_governance,require_distinct_approver}'
                       FROM public.tenants t WHERE t.id = p_tenant), 'true') <> 'false'
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_change_sets_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_transition text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.projects p WHERE p.id = OLD.project_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
                MESSAGE = 'WBS change sets are governance history: withdraw instead of deleting';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'DRAFT' OR NEW.revision <> 1 THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'a WBS change set starts as DRAFT revision 1';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status IN ('APPLIED', 'REJECTED', 'WITHDRAWN', 'STALE') THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS change set is ' || OLD.status || ' and immutable';
    END IF;
    IF NEW.id <> OLD.id OR NEW.tenant_id <> OLD.tenant_id OR NEW.project_id <> OLD.project_id
       OR NEW.base_baseline_id IS DISTINCT FROM OLD.base_baseline_id OR NEW.origin <> OLD.origin
       OR NEW.entry_mode <> OLD.entry_mode OR NEW.created_by <> OLD.created_by
       OR NEW.created_by_kind <> OLD.created_by_kind OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS change set identity, base and origin are immutable';
    END IF;
    IF NEW.revision < OLD.revision OR NEW.revision > OLD.revision + 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a WBS change set revision only moves forward by one';
    END IF;
    v_transition := OLD.status || '>' || NEW.status;
    IF OLD.status = 'SUBMITTED' AND NEW.status <> 'DRAFT' AND (
           NEW.revision <> OLD.revision OR NEW.submitted_digest IS DISTINCT FROM OLD.submitted_digest
           OR NEW.submitted_revision IS DISTINCT FROM OLD.submitted_revision
           OR NEW.submitted_by IS DISTINCT FROM OLD.submitted_by
           OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at
           OR NEW.profile_refs <> OLD.profile_refs OR NEW.evidence_refs <> OLD.evidence_refs
           OR NEW.title <> OLD.title OR NEW.description IS DISTINCT FROM OLD.description) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'a SUBMITTED WBS change set is frozen: reopen it to edit';
    END IF;
    IF NEW.status <> OLD.status AND v_transition NOT IN (
           'DRAFT>SUBMITTED', 'SUBMITTED>APPLIED', 'SUBMITTED>REJECTED', 'DRAFT>WITHDRAWN',
           'SUBMITTED>WITHDRAWN', 'SUBMITTED>DRAFT', 'DRAFT>STALE', 'SUBMITTED>STALE') THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'WBS change set cannot move ' || v_transition;
    END IF;
    IF v_transition = 'DRAFT>SUBMITTED' THEN
        IF NEW.revision <> OLD.revision THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'submit freezes the current revision';
        END IF;
        PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.submitted_by, ARRAY['admin', 'user'], 'submit');
    ELSIF v_transition = 'SUBMITTED>DRAFT' AND NEW.revision <> OLD.revision + 1 THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'reopening a WBS change set starts a new revision';
    ELSIF v_transition IN ('SUBMITTED>APPLIED', 'SUBMITTED>REJECTED') THEN
        PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.decided_by, ARRAY['admin'], 'approve or reject');
        IF NEW.decided_by = NEW.submitted_by AND public.wbs_governance_requires_distinct_approver(NEW.tenant_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
                MESSAGE = 'the WBS approver must differ from the submitter (separation of duties)';
        END IF;
        IF v_transition = 'SUBMITTED>APPLIED' AND NOT EXISTS (
               SELECT 1 FROM public.wbs_baselines b
                WHERE b.source_change_set_id = NEW.id AND b.change_set_digest = NEW.submitted_digest
                  AND b.approved_by = NEW.decided_by
                  AND b.parent_baseline_id IS NOT DISTINCT FROM NEW.base_baseline_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'APPLIED requires the baseline created from this exact submitted digest';
        END IF;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_change_set_nodes_guard()
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
            MESSAGE = 'candidate WBS nodes are editable only while the change set is DRAFT';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.change_set_id <> OLD.change_set_id OR NEW.node_id <> OLD.node_id
           OR NEW.origin_kind <> OLD.origin_kind OR NEW.tenant_id <> OLD.tenant_id OR NEW.project_id <> OLD.project_id) THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'a candidate node keeps its identity: remove and add instead';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.origin_kind = 'existing' THEN
            IF v_base IS NULL OR NOT EXISTS (
                   SELECT 1 FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = v_base AND bn.node_id = NEW.node_id) THEN
                RAISE EXCEPTION USING ERRCODE = 'check_violation',
                    MESSAGE = 'an existing candidate node must reuse an id of the base baseline';
            END IF;
        ELSIF NEW.origin_kind = 'adopted_legacy' THEN
            IF v_base IS NOT NULL OR NOT EXISTS (
                   SELECT 1 FROM public.wbs_nodes w WHERE w.id = NEW.node_id AND w.project_id = v_project) THEN
                RAISE EXCEPTION USING ERRCODE = 'check_violation',
                    MESSAGE = 'only a first baseline may adopt a live legacy id of the same project';
            END IF;
        ELSIF EXISTS (SELECT 1 FROM public.wbs_baseline_nodes bn WHERE bn.node_id = NEW.node_id)
              OR EXISTS (SELECT 1 FROM public.wbs_nodes w WHERE w.id = NEW.node_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'unique_violation',
                MESSAGE = 'a minted WBS id must be new: baseline, retired and live ids are never reused';
        END IF;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_change_set_lineage_guard()
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
            MESSAGE = 'lineage edges are immutable: remove and add instead';
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
        -- A DRAFT candidate node deletion may cascade here; anything else is frozen.
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation',
            MESSAGE = 'WBS lineage is editable only while the change set is DRAFT';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.wbs_change_set_nodes n
                    WHERE n.change_set_id = NEW.change_set_id AND n.node_id = NEW.target_node_id
                      AND n.origin_kind = 'minted') THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a lineage target must be a minted identity of the same change set';
    END IF;
    IF (v_base IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = v_base AND bn.node_id = NEW.source_node_id))
       OR (v_base IS NULL AND NOT EXISTS (
            SELECT 1 FROM public.wbs_nodes w WHERE w.id = NEW.source_node_id AND w.project_id = v_project)) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a lineage source must be an identity of the base baseline (or a legacy live node for a first baseline)';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_baselines_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_cs public.wbs_change_sets;
    v_parent_no integer;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation', MESSAGE = 'WBS baselines are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.projects p WHERE p.id = OLD.project_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation', MESSAGE = 'WBS baselines are immutable';
        END IF;
        RETURN OLD;
    END IF;
    SELECT * INTO v_cs FROM public.wbs_change_sets cs WHERE cs.id = NEW.source_change_set_id;
    IF NOT FOUND OR v_cs.project_id <> NEW.project_id OR v_cs.tenant_id <> NEW.tenant_id THEN
        RAISE EXCEPTION USING ERRCODE = 'foreign_key_violation',
            MESSAGE = 'a WBS baseline needs a change set of the same project';
    END IF;
    IF v_cs.status <> 'SUBMITTED' THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'only a SUBMITTED change set can become a baseline';
    END IF;
    IF v_cs.submitted_digest <> NEW.change_set_digest THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'the baseline digest differs from the submitted change-set digest';
    END IF;
    IF v_cs.base_baseline_id IS DISTINCT FROM NEW.parent_baseline_id THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'the change set was proposed against a different (stale) base baseline';
    END IF;
    IF NEW.parent_baseline_id IS NULL THEN
        IF EXISTS (SELECT 1 FROM public.wbs_baselines b WHERE b.project_id = NEW.project_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'unique_violation',
                MESSAGE = 'this project already has an approved first baseline';
        END IF;
    ELSE
        SELECT b.baseline_no INTO v_parent_no FROM public.wbs_baselines b
         WHERE b.id = NEW.parent_baseline_id AND b.project_id = NEW.project_id;
        IF v_parent_no IS NULL OR NEW.baseline_no <> v_parent_no + 1 OR EXISTS (
               SELECT 1 FROM public.wbs_baselines b WHERE b.project_id = NEW.project_id AND b.baseline_no > v_parent_no) THEN
            RAISE EXCEPTION USING ERRCODE = 'check_violation',
                MESSAGE = 'a baseline must directly follow the current baseline of its project';
        END IF;
    END IF;
    PERFORM public.wbs_governance_require_user_role(NEW.tenant_id, NEW.approved_by, ARRAY['admin'], 'approval');
    IF NEW.self_approved <> (NEW.approved_by = v_cs.submitted_by) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'self_approved must record whether the approver is the submitter';
    END IF;
    IF NEW.self_approved AND public.wbs_governance_requires_distinct_approver(NEW.tenant_id) THEN
        RAISE EXCEPTION USING ERRCODE = 'insufficient_privilege',
            MESSAGE = 'the WBS approver must differ from the submitter (separation of duties)';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_baselines_commit_check()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.wbs_baselines b WHERE b.id = NEW.id) THEN
        RETURN NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.wbs_change_sets cs
                    WHERE cs.id = NEW.source_change_set_id AND cs.status = 'APPLIED'
                      AND cs.decided_by = NEW.approved_by) THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a WBS baseline commits only with its change set APPLIED by the same approver';
    END IF;
    IF (SELECT count(*) FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = NEW.id) <> NEW.node_count THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'the WBS baseline snapshot does not hold exactly node_count nodes';
    END IF;
    RETURN NULL;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_baseline_nodes_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING ERRCODE = 'restrict_violation', MESSAGE = 'WBS baseline nodes are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM public.wbs_baselines b WHERE b.id = OLD.baseline_id) THEN
            RAISE EXCEPTION USING ERRCODE = 'restrict_violation', MESSAGE = 'WBS baseline nodes are immutable';
        END IF;
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_baseline_nodes_commit_check()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_expected integer;
    v_same_write boolean;
BEGIN
    SELECT b.node_count, (b.xmin = bn.xmin) INTO v_expected, v_same_write
      FROM public.wbs_baselines b
      JOIN public.wbs_baseline_nodes bn ON bn.baseline_id = b.id AND bn.node_id = NEW.node_id
     WHERE b.id = NEW.baseline_id;
    IF v_expected IS NULL OR v_same_write THEN
        RETURN NULL;
    END IF;
    IF (SELECT count(*) FROM public.wbs_baseline_nodes bn WHERE bn.baseline_id = NEW.baseline_id) <> v_expected THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation',
            MESSAGE = 'a committed WBS baseline snapshot cannot gain or lose nodes';
    END IF;
    RETURN NULL;
END
$fn$;

CREATE OR REPLACE FUNCTION public.wbs_governance_parent_cycle_check()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $fn$
DECLARE
    v_cycle boolean;
BEGIN
    IF TG_TABLE_NAME = 'wbs_change_set_nodes' THEN
        WITH RECURSIVE up (node_id, parent_id) AS (
            SELECT n.node_id, n.parent_id FROM public.wbs_change_set_nodes n
             WHERE n.change_set_id = NEW.change_set_id AND n.node_id = NEW.node_id
            UNION ALL
            SELECT p.node_id, p.parent_id FROM public.wbs_change_set_nodes p
              JOIN up ON p.node_id = up.parent_id
             WHERE p.change_set_id = NEW.change_set_id
        ) CYCLE node_id SET is_cycle USING walked
        SELECT bool_or(is_cycle) INTO v_cycle FROM up;
    ELSE
        WITH RECURSIVE up (node_id, parent_id) AS (
            SELECT n.node_id, n.parent_id FROM public.wbs_baseline_nodes n
             WHERE n.baseline_id = NEW.baseline_id AND n.node_id = NEW.node_id
            UNION ALL
            SELECT p.node_id, p.parent_id FROM public.wbs_baseline_nodes p
              JOIN up ON p.node_id = up.parent_id
             WHERE p.baseline_id = NEW.baseline_id
        ) CYCLE node_id SET is_cycle USING walked
        SELECT bool_or(is_cycle) INTO v_cycle FROM up;
    END IF;
    IF v_cycle THEN
        RAISE EXCEPTION USING ERRCODE = 'check_violation', MESSAGE = 'WBS parent cycle';
    END IF;
    RETURN NULL;
END
$fn$;

REVOKE ALL ON FUNCTION public.wbs_governance_require_user_role(uuid, uuid, text[], text) FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_governance_requires_distinct_approver(uuid) FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_change_sets_guard() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_change_set_nodes_guard() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_change_set_lineage_guard() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_baselines_guard() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_baselines_commit_check() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_baseline_nodes_guard() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_baseline_nodes_commit_check() FROM PUBLIC;

REVOKE ALL ON FUNCTION public.wbs_governance_parent_cycle_check() FROM PUBLIC;

CREATE TRIGGER trg_wbs_change_sets_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_change_sets FOR EACH ROW EXECUTE FUNCTION public.wbs_change_sets_guard();

CREATE TRIGGER trg_wbs_change_set_nodes_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_change_set_nodes FOR EACH ROW EXECUTE FUNCTION public.wbs_change_set_nodes_guard();

CREATE CONSTRAINT TRIGGER trg_wbs_change_set_nodes_cycle AFTER INSERT OR UPDATE OF parent_id ON public.wbs_change_set_nodes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_governance_parent_cycle_check();

CREATE TRIGGER trg_wbs_change_set_lineage_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_change_set_lineage FOR EACH ROW EXECUTE FUNCTION public.wbs_change_set_lineage_guard();

CREATE TRIGGER trg_wbs_baselines_guard BEFORE INSERT OR UPDATE OR DELETE ON public.wbs_baselines FOR EACH ROW EXECUTE FUNCTION public.wbs_baselines_guard();

CREATE CONSTRAINT TRIGGER trg_wbs_baselines_commit_check AFTER INSERT ON public.wbs_baselines DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_baselines_commit_check();

CREATE TRIGGER trg_wbs_baseline_nodes_guard BEFORE UPDATE OR DELETE ON public.wbs_baseline_nodes FOR EACH ROW EXECUTE FUNCTION public.wbs_baseline_nodes_guard();

CREATE CONSTRAINT TRIGGER trg_wbs_baseline_nodes_commit_check AFTER INSERT ON public.wbs_baseline_nodes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_baseline_nodes_commit_check();

CREATE CONSTRAINT TRIGGER trg_wbs_baseline_nodes_cycle AFTER INSERT ON public.wbs_baseline_nodes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.wbs_governance_parent_cycle_check();

ALTER TABLE public.wbs_change_sets ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.wbs_change_sets FORCE ROW LEVEL SECURITY;

CREATE POLICY wbs_change_sets_tenant_select ON public.wbs_change_sets FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_sets_tenant_insert ON public.wbs_change_sets FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_sets_tenant_update ON public.wbs_change_sets FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_sets_tenant_delete ON public.wbs_change_sets FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

ALTER TABLE public.wbs_change_set_nodes ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.wbs_change_set_nodes FORCE ROW LEVEL SECURITY;

CREATE POLICY wbs_change_set_nodes_tenant_select ON public.wbs_change_set_nodes FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_nodes_tenant_insert ON public.wbs_change_set_nodes FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_nodes_tenant_update ON public.wbs_change_set_nodes FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_nodes_tenant_delete ON public.wbs_change_set_nodes FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

ALTER TABLE public.wbs_change_set_lineage ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.wbs_change_set_lineage FORCE ROW LEVEL SECURITY;

CREATE POLICY wbs_change_set_lineage_tenant_select ON public.wbs_change_set_lineage FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_lineage_tenant_insert ON public.wbs_change_set_lineage FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_lineage_tenant_update ON public.wbs_change_set_lineage FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_change_set_lineage_tenant_delete ON public.wbs_change_set_lineage FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

ALTER TABLE public.wbs_baselines ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.wbs_baselines FORCE ROW LEVEL SECURITY;

CREATE POLICY wbs_baselines_tenant_select ON public.wbs_baselines FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_baselines_tenant_insert ON public.wbs_baselines FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_baselines_tenant_update ON public.wbs_baselines FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_baselines_tenant_delete ON public.wbs_baselines FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

ALTER TABLE public.wbs_baseline_nodes ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.wbs_baseline_nodes FORCE ROW LEVEL SECURITY;

CREATE POLICY wbs_baseline_nodes_tenant_select ON public.wbs_baseline_nodes FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_baseline_nodes_tenant_insert ON public.wbs_baseline_nodes FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_baseline_nodes_tenant_update ON public.wbs_baseline_nodes FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY wbs_baseline_nodes_tenant_delete ON public.wbs_baseline_nodes FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DO $do$
DECLARE
    v_role text;
BEGIN
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname = v_role) THEN
            EXECUTE 'REVOKE ALL ON TABLE public.wbs_change_sets, public.wbs_change_set_nodes, '
                 || 'public.wbs_change_set_lineage, public.wbs_baselines, public.wbs_baseline_nodes FROM '
                 || quote_ident(v_role);
            -- Supabase default privileges grant EXECUTE on new public functions to these roles.
            EXECUTE 'REVOKE ALL ON FUNCTION public.wbs_governance_require_user_role(uuid, uuid, text[], text), public.wbs_governance_requires_distinct_approver(uuid), public.wbs_change_sets_guard(), public.wbs_change_set_nodes_guard(), public.wbs_change_set_lineage_guard(), public.wbs_baselines_guard(), public.wbs_baselines_commit_check(), public.wbs_baseline_nodes_guard(), public.wbs_baseline_nodes_commit_check(), public.wbs_governance_parent_cycle_check() FROM ' || quote_ident(v_role);
        END IF;
    END LOOP;
END
$do$;
