-- Initial schema for C2Pro

-- Enable pgcrypto extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgaudit";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- TENANTS
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- USERS
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user', -- e.g., 'admin', 'user'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- PROJECTS
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    project_type VARCHAR(50), -- e.g., 'building_construction', 'civil_engineering'
    status VARCHAR(50) DEFAULT 'draft', -- e.g., 'draft', 'in_progress', 'completed'
    coherence_score INTEGER,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT projects_coherence_score_check CHECK ((coherence_score >= 0 AND coherence_score <= 100))
);

-- DOCUMENTS
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL, -- e.g., 'contract', 'schedule', 'budget'
    file_name VARCHAR(255) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    upload_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'uploading', 'completed', 'failed'
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- CLAUSES (Extracted from Contracts)
CREATE TABLE clauses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    clause_number VARCHAR(50), -- e.g., "14.2.a"
    text TEXT NOT NULL,
    topic VARCHAR(100), -- e.g., "Penalties", "Deadlines"
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_clauses_document_id ON clauses(document_id);

-- DOCUMENT_EXTRACTIONS (Raw AI model outputs)
CREATE TABLE document_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    model_version VARCHAR(50), -- e.g., "claude-sonnet-3.5-20240229"
    extraction_type VARCHAR(50), -- e.g., 'clauses', 'dates', 'budget_items'
    data JSONB,
    tokens_used INTEGER,
    confidence_score REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- PROJECT_ANALYSIS
CREATE TABLE project_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) DEFAULT 'coherence',
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    summary JSONB,
    coherence_score INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- PROJECT_ALERTS
CREATE TABLE project_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES project_analysis(id),
    clause_id UUID REFERENCES clauses(id) NULL,
    rule_id VARCHAR(50),
    severity VARCHAR(20),
    title VARCHAR(255),
    message TEXT,
    affected_references JSONB, -- Can store references to document pages, clauses, budget items
    status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id)
);

-- WBS_ITEMS (Work Breakdown Structure)
CREATE TABLE wbs_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES wbs_items(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    level INTEGER,
    start_date DATE,
    end_date DATE,
    cost DECIMAL(15, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- BOM_ITEMS (Bill of Materials)
CREATE TABLE bom_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    wbs_item_id UUID REFERENCES wbs_items(id),
    item_code VARCHAR(100),
    item_name VARCHAR(255) NOT NULL,
    description TEXT,
    quantity DECIMAL(15, 3),
    unit VARCHAR(50),
    unit_price DECIMAL(15, 2),
    total_price DECIMAL(15, 2),
    supplier VARCHAR(255),
    lead_time_days INTEGER,
    required_on_site_date DATE,
    contract_clause_id UUID REFERENCES clauses(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS for all tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE clauses ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE wbs_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE bom_items ENABLE ROW LEVEL SECURITY;

-- Policies for tenants
CREATE POLICY "Allow individual tenant access" ON tenants FOR SELECT USING (id = (auth.jwt() ->> 'tenant_id')::UUID);

-- Policies for users
CREATE POLICY "Allow users to see themselves" ON users FOR SELECT USING (id = auth.uid());
CREATE POLICY "Allow admins to see all users in their tenant" ON users FOR SELECT
    USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID AND (SELECT role FROM users WHERE id = auth.uid()) = 'admin');

-- Helper function to check project membership
CREATE OR REPLACE FUNCTION is_project_member(p_project_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM projects
        WHERE id = p_project_id AND tenant_id = (auth.jwt() ->> 'tenant_id')::UUID
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Policies for project-related tables
CREATE POLICY "Allow members to access their projects" ON projects FOR ALL
    USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID);

CREATE POLICY "Allow members to access project documents" ON documents FOR ALL
    USING (is_project_member(project_id));

CREATE POLICY "Allow members to access project clauses" ON clauses FOR ALL
    USING (EXISTS (SELECT 1 FROM documents d WHERE d.id = clauses.document_id AND is_project_member(d.project_id)));

CREATE POLICY "Allow members to access document extractions" ON document_extractions FOR ALL
    USING (is_project_member((SELECT project_id FROM documents WHERE id = document_extractions.document_id)));

CREATE POLICY "Allow members to access project analysis" ON project_analysis FOR ALL
    USING (is_project_member(project_id));

CREATE POLICY "Allow members to access project alerts" ON project_alerts FOR ALL
    USING (is_project_member(project_id));

CREATE POLICY "Allow members to access wbs items" ON wbs_items FOR ALL
    USING (is_project_member(project_id));

CREATE POLICY "Allow members to access bom items" ON bom_items FOR ALL
    USING (is_project_member(project_id));

-- Indexes for performance
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_projects_tenant_id ON projects(tenant_id);
CREATE INDEX idx_documents_project_id ON documents(project_id);
CREATE INDEX idx_document_extractions_document_id ON document_extractions(document_id);
CREATE INDEX idx_project_analysis_project_id ON project_analysis(project_id);
CREATE INDEX idx_project_alerts_project_id ON project_alerts(project_id);
CREATE INDEX idx_wbs_items_project_id ON wbs_items(project_id);
CREATE INDEX idx_bom_items_project_id ON bom_items(project_id);
