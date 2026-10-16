-- #939: minimal row-membership read grants for the protected tenant snapshot.
-- Mirror of apps/api/alembic/versions/20261017_0001_pq939_readonly_snapshot_column_grants.py.

DO $pq939$
DECLARE
    scoped record;
    relation_oid oid;
BEGIN
    -- Ephemeral CI migration databases deliberately omit the protected
    -- production acceptance account. Absence grants nothing; real G0
    -- qualification separately requires this role and its table visibility.
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'c2pro_prod_acceptance_ro'
    ) THEN
        RETURN;
    END IF;

    -- A present account must be a strictly unprivileged login, or abort.
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles
         WHERE rolname = 'c2pro_prod_acceptance_ro'
           AND rolcanlogin
           AND NOT rolsuper
           AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'PQ939_READONLY_ROLE_GUARD_FAILED';
    END IF;

    FOR scoped IN
        SELECT v.table_name
          FROM (VALUES
            ('extractions'),
            ('procurement_bom_items'),
            ('procurement_budget_items'),
            ('procurement_wbs_items'),
            ('bom_revisions'),
            ('knowledge_graph_edges'),
            ('knowledge_graph_nodes'),
            ('procurement_plan_snapshots'),
            ('stakeholder_alerts')
          ) AS v(table_name)
    LOOP
        SELECT c.oid
          INTO relation_oid
          FROM pg_catalog.pg_class AS c
          JOIN pg_catalog.pg_namespace AS ns ON ns.oid = c.relnamespace
         WHERE ns.nspname = 'public'
           AND c.relname = scoped.table_name
           AND c.relkind IN ('r', 'p')
           AND c.relrowsecurity
           AND c.relforcerowsecurity;

        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'PQ939_REQUIRED_RLS_TABLE_GUARD_FAILED';
        END IF;

        IF (
            SELECT count(*)
              FROM pg_catalog.pg_attribute
             WHERE attrelid = relation_oid
               AND attnum > 0
               AND NOT attisdropped
               AND attname IN ('id', 'project_id')
        ) <> 2 THEN
            RAISE EXCEPTION 'PQ939_REQUIRED_COLUMN_GUARD_FAILED';
        END IF;

        IF NOT EXISTS (
            SELECT 1
              FROM pg_catalog.pg_policy p
             WHERE p.polrelid = relation_oid
               AND p.polcmd IN ('*', 'r')
               AND pg_catalog.pg_get_expr(p.polqual, p.polrelid)
                   LIKE '%app.current_tenant%'
               AND pg_catalog.pg_get_expr(p.polqual, p.polrelid)
                   LIKE '%projects%'
        ) THEN
            RAISE EXCEPTION 'PQ939_TENANT_POLICY_GUARD_FAILED';
        END IF;

        IF pg_catalog.has_table_privilege(
                'c2pro_prod_acceptance_ro', relation_oid, 'SELECT'
           )
           OR pg_catalog.has_table_privilege(
                'c2pro_prod_acceptance_ro', relation_oid, 'INSERT,UPDATE,DELETE'
           ) THEN
            RAISE EXCEPTION 'PQ939_UNEXPECTED_TABLE_PRIVILEGES';
        END IF;

        -- A custom app.current_tenant GUC alone is caller-settable.
        -- This role alone is further confined to the single approved
        -- synthetic project even if the tenant GUC is manipulated.
        -- RESTRICTIVE policies compose with the existing permissive RLS.
        EXECUTE format(
            'CREATE POLICY %I ON public.%I AS RESTRICTIVE '
            'FOR SELECT TO %I USING '
            '(project_id = %L::uuid)',
            'pq939_acceptance_project_readonly',
            scoped.table_name,
            'c2pro_prod_acceptance_ro',
            'e7c6031f-cd9e-4642-a5ea-35a0207ceaeb'
        );

        EXECUTE format(
            'GRANT SELECT (id, project_id) ON TABLE public.%I TO %I',
            scoped.table_name, 'c2pro_prod_acceptance_ro'
        );
    END LOOP;
END
$pq939$;
