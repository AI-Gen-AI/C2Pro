-- #1054: bind the production acceptance read role to one tenant and project.
-- Mirror of apps/api/alembic/versions/20261022_0001_pq1054_acceptance_tenant_binding.py.

SET LOCAL lock_timeout = '5s';

CREATE SCHEMA IF NOT EXISTS c2pro_security;

REVOKE ALL ON SCHEMA c2pro_security FROM PUBLIC;

CREATE TABLE IF NOT EXISTS c2pro_security.acceptance_tenant_binding (
    role_name name PRIMARY KEY
        CHECK (role_name = 'c2pro_prod_acceptance_ro'),
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL
        CHECK (project_id = 'e7c6031f-cd9e-4642-a5ea-35a0207ceaeb'::uuid),
    bound_at timestamptz NOT NULL DEFAULT now(),
    bound_by text NOT NULL CHECK (length(bound_by) > 0)
);

REVOKE ALL ON TABLE c2pro_security.acceptance_tenant_binding FROM PUBLIC;

DO $pq1054$
DECLARE
    scoped record;
    relation_oid oid;
    role_oid oid;
    anchored_tenant text := '(SELECT b.tenant_id FROM '
        'c2pro_security.acceptance_tenant_binding b '
        'WHERE b.role_name = ''c2pro_prod_acceptance_ro'')';
    anchored_project text := '(SELECT b.project_id FROM '
        'c2pro_security.acceptance_tenant_binding b '
        'WHERE b.role_name = ''c2pro_prod_acceptance_ro'')';
    predicate text;
    required_columns name[];
    offenders text;
BEGIN
    -- Ephemeral CI databases deliberately omit the protected account.
    SELECT oid INTO role_oid
      FROM pg_catalog.pg_roles
     WHERE rolname = 'c2pro_prod_acceptance_ro';
    IF role_oid IS NULL THEN
        RETURN;
    END IF;

    -- Remove only the implicit PUBLIC EXECUTE grant on the application RLS
    -- helper. Supabase's explicit anon/authenticated/service_role grants remain.
    -- The read-only acceptance login must not call any SECURITY DEFINER helper.
    IF to_regprocedure('public.is_project_member(uuid)') IS NOT NULL THEN
        EXECUTE 'REVOKE EXECUTE ON FUNCTION public.is_project_member(uuid) FROM PUBLIC';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles
         WHERE oid = role_oid
           AND rolcanlogin
           AND NOT rolsuper
           AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'PQ1054_READONLY_ROLE_GUARD_FAILED';
    END IF;

    -- RESTRICTIVE policies TO this role also bind every role that inherits
    -- its privileges. Refuse an RLS-subject inheriting member rather than
    -- silently confining (or exposing) an unrelated principal. A creator's
    -- ADMIN-only membership (PG16+, INHERIT FALSE) does not inherit and passes.
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS member
         WHERE member.oid <> role_oid
           AND NOT member.rolsuper
           AND NOT member.rolbypassrls
           AND pg_catalog.pg_has_role(member.oid, role_oid, 'USAGE')
    ) THEN
        RAISE EXCEPTION 'PQ1054_READONLY_ROLE_MEMBERSHIP_GUARD_FAILED';
    END IF;

    -- The other direction: after SET ROLE to a role this login belongs to,
    -- the policies bound TO this role no longer apply and the caller-set
    -- tenant GUC alone decides. Refuse every such parent role, whether its
    -- privileges are inherited or reachable only with SET ROLE.
    SELECT string_agg(parent.rolname, ', ' ORDER BY parent.rolname)
      INTO offenders
      FROM pg_catalog.pg_roles AS parent
     WHERE parent.oid <> role_oid
       AND pg_catalog.pg_has_role(role_oid, parent.oid, 'MEMBER');
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'PQ1054_READONLY_ROLE_PARENT_ROLE_GUARD_FAILED: %', offenders;
    END IF;

    -- An owner bypasses non-FORCE RLS entirely.
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class WHERE relowner = role_oid
    ) THEN
        RAISE EXCEPTION 'PQ1054_READONLY_ROLE_OWNS_RELATION';
    END IF;

    EXECUTE 'GRANT USAGE ON SCHEMA c2pro_security TO c2pro_prod_acceptance_ro';
    EXECUTE 'GRANT SELECT ON TABLE c2pro_security.acceptance_tenant_binding '
            'TO c2pro_prod_acceptance_ro';

    FOR scoped IN
        SELECT v.table_name, v.mode
          FROM (VALUES
            ('tenants', 'tenant_root'),
            ('projects', 'project_root'),
            ('documents', 'tenant_project'),
            ('document_revisions', 'tenant_project'),
            ('document_artifacts', 'tenant_project'),
            ('clauses', 'tenant_project'),
            ('project_events', 'tenant_project'),
            ('analyses', 'tenant_project'),
            ('document_chunks', 'tenant_project'),
            ('project_snapshots', 'tenant_project'),
            ('review_items', 'tenant_project'),
            ('document_processing_operations', 'tenant_document')
          ) AS v(table_name, mode)
    LOOP
        relation_oid := NULL;
        SELECT c.oid
          INTO relation_oid
          FROM pg_catalog.pg_class AS c
          JOIN pg_catalog.pg_namespace AS ns ON ns.oid = c.relnamespace
         WHERE ns.nspname = 'public'
           AND c.relname = scoped.table_name
           AND c.relkind IN ('r', 'p')
           AND c.relrowsecurity;

        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'PQ1054_REQUIRED_RLS_TABLE_GUARD_FAILED: %',
                scoped.table_name;
        END IF;

        required_columns := CASE scoped.mode
            WHEN 'tenant_root' THEN ARRAY['id']
            WHEN 'project_root' THEN ARRAY['id', 'tenant_id']
            WHEN 'tenant_project' THEN ARRAY['tenant_id', 'project_id']
            ELSE ARRAY['tenant_id', 'document_id']
        END;
        IF (
            SELECT count(*)
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
               AND attname = ANY (required_columns)
        ) <> cardinality(required_columns) THEN
            RAISE EXCEPTION 'PQ1054_REQUIRED_COLUMN_GUARD_FAILED: %',
                scoped.table_name;
        END IF;

        IF scoped.mode = 'tenant_root' THEN
            predicate := format('id = %s', anchored_tenant);
        ELSIF scoped.mode = 'project_root' THEN
            predicate := format(
                'id = %s AND tenant_id = %s', anchored_project, anchored_tenant
            );
        ELSIF scoped.mode = 'tenant_project' THEN
            predicate := format(
                'tenant_id = %s AND project_id = %s',
                anchored_tenant, anchored_project
            );
        ELSE
            predicate := format(
                'tenant_id = %s AND document_id IN (SELECT d.id FROM '
                'public.documents d WHERE d.project_id = %s)',
                anchored_tenant, anchored_project
            );
        END IF;

        EXECUTE format(
            'CREATE POLICY %I ON public.%I AS RESTRICTIVE FOR SELECT TO %I '
            'USING (%s)',
            'pq1054_acceptance_tenant_bound',
            scoped.table_name,
            'c2pro_prod_acceptance_ro',
            predicate
        );
    END LOOP;

    -- Post-condition: every relation the role can read, by table or column
    -- grant and directly or by inheritance, must be one of the approved
    -- relations under its approved RESTRICTIVE read policy for this role:
    -- this binding on the 12 tenant relations, #1053's project pin on the 9
    -- project-only tables. Any other restrictive policy (USING (true), say)
    -- binds nothing. Definer-rights views, materialized views and foreign
    -- tables bypass the caller's RLS.
    SELECT string_agg(format('%I.%I', ns.nspname, c.relname), ', ')
      INTO offenders
      FROM pg_catalog.pg_class AS c
      JOIN pg_catalog.pg_namespace AS ns ON ns.oid = c.relnamespace
     WHERE ns.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
       -- SELECT on an object is not executable without schema USAGE.
       AND pg_catalog.has_schema_privilege(role_oid, ns.oid, 'USAGE')
       AND NOT (ns.nspname = 'c2pro_security'
                AND c.relname = 'acceptance_tenant_binding')
       AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND (pg_catalog.has_table_privilege(role_oid, c.oid, 'SELECT')
            OR pg_catalog.has_any_column_privilege(role_oid, c.oid, 'SELECT'))
       AND (c.relkind IN ('v', 'm', 'f')
            OR NOT c.relrowsecurity
            OR NOT EXISTS (
                SELECT 1
                  FROM pg_catalog.pg_policy AS p
                 WHERE p.polrelid = c.oid
                   AND NOT p.polpermissive
                   AND p.polcmd IN ('r', '*')
                   AND role_oid = ANY (p.polroles)
                   AND ns.nspname = 'public'
                   AND ((p.polname = 'pq1054_acceptance_tenant_bound'
                         AND c.relname = ANY (ARRAY[
                             'tenants', 'projects', 'documents',
                             'document_revisions', 'document_artifacts',
                             'clauses', 'project_events', 'analyses',
                             'document_chunks', 'project_snapshots',
                             'review_items', 'document_processing_operations'
                         ]::name[]))
                        OR (p.polname = 'pq939_acceptance_project_readonly'
                            AND c.relname = ANY (ARRAY[
                                'extractions', 'procurement_bom_items',
                                'procurement_budget_items',
                                'procurement_wbs_items', 'bom_revisions',
                                'knowledge_graph_edges', 'knowledge_graph_nodes',
                                'procurement_plan_snapshots', 'stakeholder_alerts'
                            ]::name[])))));
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'PQ1054_UNBOUND_READABLE_RELATIONS: %', offenders;
    END IF;

    -- RLS never binds a SECURITY DEFINER function: it reads with its owner's
    -- rights. The role must not be able to call one outside the catalog.
    SELECT string_agg(
               format('%I.%I(%s)', ns.nspname, p.proname,
                      pg_catalog.pg_get_function_identity_arguments(p.oid)),
               ', ')
      INTO offenders
      FROM pg_catalog.pg_proc AS p
      JOIN pg_catalog.pg_namespace AS ns ON ns.oid = p.pronamespace
     WHERE p.prosecdef
       -- event_trigger functions cannot be called directly by this role.
       AND p.prorettype <> 'event_trigger'::regtype
       AND ns.nspname NOT IN ('pg_catalog', 'information_schema')
       AND pg_catalog.has_function_privilege(role_oid, p.oid, 'EXECUTE')
       AND pg_catalog.has_schema_privilege(role_oid, ns.oid, 'USAGE');
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'PQ1054_SECURITY_DEFINER_EXECUTABLE: %', offenders;
    END IF;

    -- The post-condition holds only for relations that exist today. A default
    -- privilege granting SELECT to the role (directly, via PUBLIC or an
    -- inherited role) would make every future table readable unbound.
    SELECT string_agg(
               DISTINCT format('%s:%s', coalesce(ns.nspname, '*'),
                               pg_catalog.pg_get_userbyid(d.defaclrole)),
               ', ')
      INTO offenders
      FROM pg_catalog.pg_default_acl AS d
      LEFT JOIN pg_catalog.pg_namespace AS ns ON ns.oid = d.defaclnamespace
     CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) AS acl
     WHERE d.defaclobjtype = 'r'
       AND acl.privilege_type = 'SELECT'
       AND (acl.grantee = 0
            OR pg_catalog.pg_has_role(role_oid, acl.grantee, 'USAGE'));
    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION 'PQ1054_DEFAULT_PRIVILEGES_WIDEN_ROLE: %', offenders;
    END IF;
END
$pq1054$;
