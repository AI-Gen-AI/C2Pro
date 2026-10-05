-- B1: exact Coherence scoring snapshot for disposition-aware rescoring.
-- Mirror of apps/api/alembic/versions/20261005_0001_coherence_scoring_snapshot.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

ALTER TABLE public.coherence_results
    ADD COLUMN scoring_snapshot jsonb NULL;
