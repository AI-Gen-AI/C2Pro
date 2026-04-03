-- =====================================================
-- TASK-1490: Composite Indexes for Tenant-Scoped Queries
-- Run this in Supabase SQL Editor
-- =====================================================

-- Documents: tenant + status for filtering
CREATE INDEX IF NOT EXISTS ix_documents_tenant_status
ON documents(project_id, upload_status);

-- Documents: tenant + type for filtering  
CREATE INDEX IF NOT EXISTS ix_documents_tenant_type
ON documents(project_id, document_type);

-- Documents: tenant + created_at for sorting
CREATE INDEX IF NOT EXISTS ix_documents_tenant_created
ON documents(project_id, created_at);

-- Clauses: tenant + project + type for filtering
CREATE INDEX IF NOT EXISTS ix_clauses_tenant_project_type
ON clauses(project_id, clause_type);

-- Clauses: tenant + project + code for lookups
CREATE INDEX IF NOT EXISTS ix_clauses_tenant_project_code
ON clauses(project_id, clause_code);

-- Clauses: tenant + project + verification status
CREATE INDEX IF NOT EXISTS ix_clauses_tenant_verified
ON clauses(project_id, manually_verified, verified_at);

-- Verify indexes created
SELECT indexname FROM pg_indexes 
WHERE schemaname = 'public' 
AND indexname LIKE 'ix_documents_%' OR indexname LIKE 'ix_clauses_%'
ORDER BY indexname;