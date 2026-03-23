-- TS-DB-MIG-REC-007
-- Drop redundant index duplicates after reconciliation

-- Keep the normalized `ix_*` family (or stronger unique index) where an older
-- `idx_*` path duplicates the same access pattern.

DROP INDEX IF EXISTS public.idx_ai_logs_project;
DROP INDEX IF EXISTS public.idx_ai_logs_tenant;

DROP INDEX IF EXISTS public.idx_alerts_analysis;
DROP INDEX IF EXISTS public.idx_alerts_project;
DROP INDEX IF EXISTS public.idx_alerts_severity;
DROP INDEX IF EXISTS public.idx_alerts_status;
DROP INDEX IF EXISTS public.idx_alerts_clause;

DROP INDEX IF EXISTS public.idx_analyses_project;
DROP INDEX IF EXISTS public.idx_analyses_status;

DROP INDEX IF EXISTS public.idx_audit_resource;
DROP INDEX IF EXISTS public.idx_audit_tenant;
DROP INDEX IF EXISTS public.idx_audit_user;

DROP INDEX IF EXISTS public.idx_extractions_document;
DROP INDEX IF EXISTS public.idx_extractions_type;

DROP INDEX IF EXISTS public.idx_raci_stakeholder;
DROP INDEX IF EXISTS public.idx_raci_wbs;

DROP INDEX IF EXISTS public.idx_stakeholders_project;
DROP INDEX IF EXISTS public.idx_stakeholders_quadrant;
DROP INDEX IF EXISTS public.idx_stakeholders_clause;

DROP INDEX IF EXISTS public.idx_users_clerk_user_id;
