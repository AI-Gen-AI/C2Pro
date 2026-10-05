-- #870: enforce RLS on every existing project_snapshots partition leaf.
-- Mirror of apps/api/alembic/versions/20261005_0002_project_snapshot_partition_rls.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

DO $$
DECLARE
    child record;
BEGIN
    FOR child IN
        SELECT child_ns.nspname AS schema_name, child.relname AS table_name
        FROM pg_inherits
        JOIN pg_class parent ON parent.oid = pg_inherits.inhparent
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        JOIN pg_class child ON child.oid = pg_inherits.inhrelid
        JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
        WHERE parent_ns.nspname = 'public'
          AND parent.relname = 'project_snapshots'
    LOOP
        EXECUTE 'ALTER TABLE '
            || quote_ident(child.schema_name)
            || '.'
            || quote_ident(child.table_name)
            || ' ENABLE ROW LEVEL SECURITY';
    END LOOP;
END $$;
