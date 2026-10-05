-- #870: repair RLS on every attached project_snapshots partition.
-- Mirror of apps/api/alembic/versions/20261005_0002_project_snapshot_partition_rls.py (rendered from UPGRADE_SQL; do not edit by hand).

DO $$
DECLARE
    parent_oid oid;
    rec record;
BEGIN
    SELECT to_regclass('public.project_snapshots') INTO parent_oid;
    IF parent_oid IS NULL THEN
        RETURN;
    END IF;

    FOR rec IN
        WITH RECURSIVE descendants(oid) AS (
            SELECT inhrelid
            FROM pg_inherits
            WHERE inhparent = parent_oid

            UNION ALL

            SELECT child.inhrelid
            FROM pg_inherits child
            JOIN descendants parent_descendant
              ON child.inhparent = parent_descendant.oid
        )
        SELECT child_ns.nspname AS schema_name, child.relname AS table_name
        FROM descendants
        JOIN pg_class child ON child.oid = descendants.oid
        JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
        WHERE child.relkind IN ('r', 'p')
    LOOP
        EXECUTE
            'ALTER TABLE '
            || quote_ident(rec.schema_name)
            || '.'
            || quote_ident(rec.table_name)
            || ' ENABLE ROW LEVEL SECURITY';
    END LOOP;
END $$;
