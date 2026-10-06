-- #909 / #686: remove obsolete document-level clause-code uniqueness.
-- Mirror of apps/api/alembic/versions/20261006_0003_drop_legacy_clause_code_unique.py (rendered from UPGRADE_STATEMENTS; do not edit by hand).

ALTER TABLE public.clauses DROP CONSTRAINT IF EXISTS clauses_project_document_code_unique;
