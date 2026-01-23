-- CE-S4-014: Additional Performance Indexes
-- This migration adds several indexes to improve search performance and optimize
-- common filtering operations.

-- 1. Enable Trigram extension for efficient text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. GIN Indexes for Full-Text Search
-- These indexes allow for fast "ILIKE '%...%'" style queries, which are
-- essential for global search bars.

CREATE INDEX IF NOT EXISTS idx_projects_title_trgm ON projects USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_filename_trgm ON documents USING gin (filename gin_trgm_ops);

-- 3. B-Tree Indexes for Foreign Keys
-- PostgreSQL does not automatically index foreign key columns. Adding them is
-- crucial to prevent table locking issues during cascading updates or deletes
-- and to speed up JOINs.

CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents (project_id);
CREATE INDEX IF NOT EXISTS idx_alerts_project_id ON alerts (project_id);
CREATE INDEX IF NOT EXISTS idx_wbs_items_project_id ON wbs_items (project_id);

-- 4. Index for Task Status Polling
-- The 'documents' table is frequently polled by workers to find tasks that
-- are 'processing' or 'pending'. This index significantly speeds up that query.

CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);
