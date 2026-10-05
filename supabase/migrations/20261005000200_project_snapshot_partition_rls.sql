-- #870: enforce RLS on every existing project_snapshots partition leaf.
-- Mirror of apps/api/alembic/versions/20261005_0002_project_snapshot_partition_rls.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

DO $
DECLARE
    partition_row record;
BEGIN
    FOR partition_row IN
        SELECT child_ns.nspname AS schema_name, child_rel.relname AS table_name
        FROM pg_inherits
        JOIN pg_class parent_rel ON parent_rel.oid = pg_inherits.inhparent
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent_rel.relnamespace
        JOIN pg_class child_rel ON child_rel.oid = pg_inherits.inhrelid
        JOIN pg_namespace child_ns ON child_ns.oid = child_rel.relnamespace
        WHERE parent_ns.nspname = 'public'
          AND parent_rel.relname = 'project_snapshots'
    LOOP
        EXECUTE 'ALTER TABLE '
            || quote_ident(partition_row.schema_name)
            || '.'
            || quote_ident(partition_row.table_name)
            || ' ENABLE ROW LEVEL SECURITY';
    END LOOP;
END $;
