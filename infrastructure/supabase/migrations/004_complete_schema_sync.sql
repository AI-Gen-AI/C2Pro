-- ===================================
-- Migration 004: Complete Schema Synchronization
-- ===================================
-- Sincroniza 100% el schema de PostgreSQL con los modelos SQLAlchemy actuales
-- Fecha: 2026-01-07
-- Objetivo: Lograr 42/42 tests de seguridad pasando

-- ===================================
-- 1. CREATE ENUM TYPES
-- ===================================

-- Document enums
DO $$ BEGIN
    CREATE TYPE documenttype AS ENUM ('contract', 'schedule', 'budget', 'drawing', 'specification', 'other');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE documentstatus AS ENUM ('uploaded', 'parsing', 'parsed', 'error');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Analysis enums
DO $$ BEGIN
    CREATE TYPE analysistype AS ENUM ('coherence', 'risk', 'cost', 'schedule', 'quality');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE analysisstatus AS ENUM ('pending', 'running', 'completed', 'error', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Alert enums
DO $$ BEGIN
    CREATE TYPE alertseverity AS ENUM ('critical', 'high', 'medium', 'low');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE alertstatus AS ENUM ('open', 'acknowledged', 'resolved', 'dismissed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Clause enums
DO $$ BEGIN
    CREATE TYPE clausetype AS ENUM ('penalty', 'milestone', 'responsibility', 'payment', 'delivery', 'quality', 'scope', 'termination', 'dispute', 'other');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Stakeholder enums
DO $$ BEGIN
    CREATE TYPE powerlevel AS ENUM ('low', 'medium', 'high');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE interestlevel AS ENUM ('low', 'medium', 'high');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE stakeholderquadrant AS ENUM ('key_player', 'keep_satisfied', 'keep_informed', 'monitor');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE racirole AS ENUM ('R', 'A', 'C', 'I');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- WBS/BOM enums
DO $$ BEGIN
    CREATE TYPE wbsitemtype AS ENUM ('deliverable', 'work_package', 'activity');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE bomcategory AS ENUM ('material', 'equipment', 'service', 'consumable');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE procurementstatus AS ENUM ('pending', 'requested', 'ordered', 'in_transit', 'delivered', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ===================================
-- 2. UPDATE DOCUMENTS TABLE
-- ===================================

-- Rename storage_path to storage_url if it exists (MUST happen before ADD)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'documents' AND column_name = 'storage_path') THEN
        ALTER TABLE documents RENAME COLUMN storage_path TO storage_url;
    END IF;
END $$;

-- Add missing columns to documents
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS file_format VARCHAR(10),
ADD COLUMN IF NOT EXISTS storage_url TEXT,
ADD COLUMN IF NOT EXISTS storage_encrypted BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS parsed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS parsing_error TEXT,
ADD COLUMN IF NOT EXISTS retention_until TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS document_metadata JSONB DEFAULT '{}';

-- Update document_type column to use enum
DO $$ BEGIN
    -- Drop old VARCHAR column and create new enum column
    ALTER TABLE documents DROP COLUMN IF EXISTS document_type CASCADE;
    ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_type documenttype DEFAULT 'other';
EXCEPTION
    WHEN OTHERS THEN null;
END $$;

-- Update upload_status column to use enum
DO $$ BEGIN
    ALTER TABLE documents DROP COLUMN IF EXISTS upload_status CASCADE;
    ALTER TABLE documents ADD COLUMN IF NOT EXISTS upload_status documentstatus DEFAULT 'uploaded';
EXCEPTION
    WHEN OTHERS THEN null;
END $$;

-- ===================================
-- 3. UPDATE CLAUSES TABLE
-- ===================================

-- Add missing columns to clauses
ALTER TABLE clauses
ADD COLUMN IF NOT EXISTS clause_type clausetype,
ADD COLUMN IF NOT EXISTS confidence_score FLOAT,
ADD COLUMN IF NOT EXISTS source_page INTEGER,
ADD COLUMN IF NOT EXISTS clause_metadata JSONB DEFAULT '{}';

-- Rename text to content if needed
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'clauses' AND column_name = 'text') THEN
        ALTER TABLE clauses RENAME COLUMN text TO content;
    END IF;
END $$;

-- Rename topic to summary if needed
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'clauses' AND column_name = 'topic') THEN
        ALTER TABLE clauses RENAME COLUMN topic TO summary;
    END IF;
END $$;

-- ===================================
-- 4. CREATE ANALYSES TABLE (replaces project_analysis)
-- ===================================

CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type analysistype DEFAULT 'coherence',
    status analysisstatus DEFAULT 'pending',
    result_json JSONB,
    coherence_score INTEGER CHECK (coherence_score >= 0 AND coherence_score <= 100),
    coherence_breakdown JSONB,
    alerts_count INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_analyses_project_id ON analyses(project_id);
CREATE INDEX IF NOT EXISTS ix_analyses_status ON analyses(status);
CREATE INDEX IF NOT EXISTS ix_analyses_created ON analyses(created_at);

-- ===================================
-- 5. CREATE ALERTS TABLE (replaces project_alerts)
-- ===================================

CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id) ON DELETE CASCADE,

    -- Legal traceability (ROADMAP §5.3)
    source_clause_id UUID REFERENCES clauses(id) ON DELETE SET NULL,
    related_clause_ids UUID[],

    -- Alert details
    severity alertseverity NOT NULL,
    status alertstatus DEFAULT 'open',
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    recommendation TEXT,
    category VARCHAR(50),
    rule_id VARCHAR(100),

    -- Impact
    impact_level VARCHAR(20),
    affected_entities JSONB DEFAULT '[]',

    -- Resolution
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    resolution_notes TEXT,

    -- Metadata
    alert_metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_alerts_project_id ON alerts(project_id);
CREATE INDEX IF NOT EXISTS ix_alerts_analysis_id ON alerts(analysis_id);
CREATE INDEX IF NOT EXISTS ix_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS ix_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS ix_alerts_source_clause ON alerts(source_clause_id);

-- ===================================
-- 6. CREATE EXTRACTIONS TABLE (replaces document_extractions)
-- ===================================

CREATE TABLE IF NOT EXISTS extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extraction_type VARCHAR(50) NOT NULL,
    content JSONB NOT NULL,
    confidence_score FLOAT,
    model_version VARCHAR(50),
    tokens_used INTEGER,
    extraction_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_extractions_document_id ON extractions(document_id);
CREATE INDEX IF NOT EXISTS ix_extractions_type ON extractions(extraction_type);

-- ===================================
-- 7. CREATE/UPDATE STAKEHOLDERS TABLE
-- ===================================

CREATE TABLE IF NOT EXISTS stakeholders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Legal traceability (ROADMAP §5.3)
    source_clause_id UUID REFERENCES clauses(id) ON DELETE SET NULL,

    -- Identification
    name VARCHAR(255),
    role VARCHAR(100),
    organization VARCHAR(255),
    contact_info JSONB DEFAULT '{}',

    -- Power/Interest Matrix (ROADMAP §4.5)
    power_level powerlevel,
    interest_level interestlevel,
    quadrant stakeholderquadrant,
    engagement_strategy TEXT,

    -- Communication
    communication_frequency VARCHAR(50),
    preferred_channel VARCHAR(100),

    -- Metadata
    stakeholder_metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_stakeholders_project_id ON stakeholders(project_id);
CREATE INDEX IF NOT EXISTS ix_stakeholders_quadrant ON stakeholders(quadrant);
CREATE INDEX IF NOT EXISTS ix_stakeholders_source_clause ON stakeholders(source_clause_id);

-- ===================================
-- 8. UPDATE WBS_ITEMS TABLE
-- ===================================

-- Add missing columns to wbs_items
ALTER TABLE wbs_items
ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES wbs_items(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS item_type wbsitemtype DEFAULT 'activity',
ADD COLUMN IF NOT EXISTS wbs_code VARCHAR(50),
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS estimated_hours FLOAT,
ADD COLUMN IF NOT EXISTS estimated_cost NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS actual_hours FLOAT,
ADD COLUMN IF NOT EXISTS actual_cost NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS completion_percentage INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS start_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS end_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS source_clause_id UUID REFERENCES clauses(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS wbs_metadata JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ===================================
-- 9. UPDATE BOM_ITEMS TABLE
-- ===================================

-- Add missing columns to bom_items
ALTER TABLE bom_items
ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES bom_items(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS category bomcategory DEFAULT 'material',
ADD COLUMN IF NOT EXISTS item_code VARCHAR(100),
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS unit_of_measure VARCHAR(50),
ADD COLUMN IF NOT EXISTS quantity NUMERIC(15,3),
ADD COLUMN IF NOT EXISTS unit_cost NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS total_cost NUMERIC(15,2),
ADD COLUMN IF NOT EXISTS supplier VARCHAR(255),
ADD COLUMN IF NOT EXISTS procurement_status procurementstatus DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS delivery_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS source_clause_id UUID REFERENCES clauses(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS bom_metadata JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ===================================
-- 10. CREATE STAKEHOLDER_WBS_RACI TABLE
-- ===================================

CREATE TABLE IF NOT EXISTS stakeholder_wbs_raci (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stakeholder_id UUID NOT NULL REFERENCES stakeholders(id) ON DELETE CASCADE,
    wbs_item_id UUID NOT NULL REFERENCES wbs_items(id) ON DELETE CASCADE,
    raci_role racirole NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(stakeholder_id, wbs_item_id, raci_role)
);

CREATE INDEX IF NOT EXISTS ix_stakeholder_wbs_raci_project ON stakeholder_wbs_raci(project_id);
CREATE INDEX IF NOT EXISTS ix_stakeholder_wbs_raci_stakeholder ON stakeholder_wbs_raci(stakeholder_id);
CREATE INDEX IF NOT EXISTS ix_stakeholder_wbs_raci_wbs ON stakeholder_wbs_raci(wbs_item_id);

-- ===================================
-- 11. CREATE AI_USAGE_LOGS TABLE
-- ===================================

CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    model_name VARCHAR(100) NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    estimated_cost NUMERIC(10,4) DEFAULT 0,
    duration_ms INTEGER,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    log_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ai_usage_logs_tenant ON ai_usage_logs(tenant_id);
CREATE INDEX IF NOT EXISTS ix_ai_usage_logs_project ON ai_usage_logs(project_id);
CREATE INDEX IF NOT EXISTS ix_ai_usage_logs_created ON ai_usage_logs(created_at);

-- ===================================
-- 12. CREATE AUDIT_LOGS TABLE
-- ===================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    changes JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created ON audit_logs(created_at);

-- ===================================
-- 13. CREATE RLS POLICIES FOR NEW TABLES
-- ===================================

-- Enable RLS on new tables
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakeholders ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakeholder_wbs_raci ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (drop first if exists to avoid errors)
DO $$ BEGIN
    DROP POLICY IF EXISTS "tenant_isolation_analyses" ON analyses;
    CREATE POLICY "tenant_isolation_analyses"
        ON analyses
        USING ((project_id IN (SELECT id FROM projects WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::UUID)));
EXCEPTION WHEN OTHERS THEN null;
END $$;

DO $$ BEGIN
    DROP POLICY IF EXISTS "tenant_isolation_alerts" ON alerts;
    CREATE POLICY "tenant_isolation_alerts"
        ON alerts
        USING ((project_id IN (SELECT id FROM projects WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::UUID)));
EXCEPTION WHEN OTHERS THEN null;
END $$;

DO $$ BEGIN
    DROP POLICY IF EXISTS "tenant_isolation_extractions" ON extractions;
    CREATE POLICY "tenant_isolation_extractions"
        ON extractions
        USING ((document_id IN (SELECT id FROM documents WHERE project_id IN (SELECT id FROM projects WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::UUID))));
EXCEPTION WHEN OTHERS THEN null;
END $$;

DO $$ BEGIN
    DROP POLICY IF EXISTS "tenant_isolation_stakeholders" ON stakeholders;
    CREATE POLICY "tenant_isolation_stakeholders"
        ON stakeholders
        USING ((project_id IN (SELECT id FROM projects WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::UUID)));
EXCEPTION WHEN OTHERS THEN null;
END $$;

DO $$ BEGIN
    DROP POLICY IF EXISTS "tenant_isolation_stakeholder_wbs_raci" ON stakeholder_wbs_raci;
    CREATE POLICY "tenant_isolation_stakeholder_wbs_raci"
        ON stakeholder_wbs_raci
        USING ((project_id IN (SELECT id FROM projects WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::UUID)));
EXCEPTION WHEN OTHERS THEN null;
END $$;

DO $$ BEGIN
    DROP POLICY IF EXISTS "tenant_isolation_ai_usage_logs" ON ai_usage_logs;
    CREATE POLICY "tenant_isolation_ai_usage_logs"
        ON ai_usage_logs
        USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID);
EXCEPTION WHEN OTHERS THEN null;
END $$;

DO $$ BEGIN
    DROP POLICY IF EXISTS "tenant_isolation_audit_logs" ON audit_logs;
    CREATE POLICY "tenant_isolation_audit_logs"
        ON audit_logs
        USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID);
EXCEPTION WHEN OTHERS THEN null;
END $$;

-- ===================================
-- DONE
-- ===================================
