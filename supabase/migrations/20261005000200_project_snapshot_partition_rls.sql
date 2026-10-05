-- #870: repair RLS on snapshot partition leaves created after P0-SEC-A.
-- Mirror of apps/api/alembic/versions/20261005_0002_project_snapshot_partition_rls.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

ALTER TABLE IF EXISTS public.project_snapshots_2026_10 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.project_snapshots_2026_11 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.project_snapshots_2026_12 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.project_snapshots_default ENABLE ROW LEVEL SECURITY;
