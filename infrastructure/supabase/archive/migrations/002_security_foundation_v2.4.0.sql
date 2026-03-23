-- =====================================================
-- C2Pro Database Migration - v2.4.0 Security Foundation
-- =====================================================
-- DESCRIPCIÓN: Migración completa para HARDENING & CTO-READY
-- - Corrige UNIQUE constraint en users (tenant_id, email)
-- - Crea tabla CLAUSES para trazabilidad legal
-- - Implementa RLS completo en 18 tablas
-- - Agrega FKs clause_id en entidades dependientes
-- - Configura índices y constraints de seguridad
--
-- VERSIÓN: 2.4.0
-- FECHA: 2026-01-05
-- AUTOR: Sistema C2Pro
-- CRITICIDAD: BLOQUEANTE para producción
-- =====================================================

-- Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Para búsquedas de texto

-- Asegurar columnas esperadas en projects para vistas posteriores
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS coherence_score INTEGER;

-- =====================================================
-- SECCIÓN 1: CORRECCIONES DE SEGURIDAD CRÍTICAS
-- =====================================================

-- 1.1 Corregir constraint UNIQUE en users
-- ROADMAP §5.2: UNIQUE(tenant_id, email) para soporte B2B enterprise
DO $$
BEGIN
    -- Eliminar constraint único global en email si existe
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'users_email_key'
    ) THEN
        ALTER TABLE users DROP CONSTRAINT users_email_key;
    END IF;

    -- Agregar constraint único compuesto (tenant_id, email)
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'users_tenant_email_unique'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_tenant_email_unique
            UNIQUE (tenant_id, email);
    END IF;
END $$;

-- =====================================================
-- SECCIÓN 2: DROP TABLAS EXISTENTES PARA RECREAR
-- =====================================================
-- Drop tablas que serán recreadas con esquemas mejorados
-- CASCADE eliminará también las dependencias (FKs, índices, políticas RLS)

DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS knowledge_graph_edges CASCADE;
DROP TABLE IF EXISTS knowledge_graph_nodes CASCADE;
DROP TABLE IF EXISTS procurement_plan_snapshots CASCADE;
DROP TABLE IF EXISTS bom_revisions CASCADE;
DROP TABLE IF EXISTS stakeholder_alerts CASCADE;
DROP TABLE IF EXISTS stakeholder_wbs_raci CASCADE;
DROP TABLE IF EXISTS bom_items CASCADE;
DROP TABLE IF EXISTS wbs_items CASCADE;
DROP TABLE IF EXISTS stakeholders CASCADE;
DROP TABLE IF EXISTS ai_usage_logs CASCADE;
DROP TABLE IF EXISTS project_alerts CASCADE;  -- Renombrado a alerts
DROP TABLE IF EXISTS project_analysis CASCADE;  -- Renombrado a analyses
DROP TABLE IF EXISTS document_extractions CASCADE;  -- Renombrado a extractions
DROP TABLE IF EXISTS clauses CASCADE;
-- documents se mantiene pero se modifica schema

-- =====================================================
-- SECCIÓN 3: TABLA CLAUSES (NUEVA - CRÍTICA)
-- =====================================================
-- ROADMAP §5.3: Entidad propia para trazabilidad legal

CREATE TABLE clauses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Identificación
    clause_code VARCHAR(50) NOT NULL,  -- "4.2.1", "Anexo III.2"
    clause_type VARCHAR(50),  -- "penalty", "milestone", "responsibility", "payment"
    title VARCHAR(255),

    -- Contenido
    full_text TEXT,
    text_start_offset INTEGER,  -- Para evitar duplicar texto
    text_end_offset INTEGER,

    -- Extracción
    extracted_entities JSONB DEFAULT '{}',  -- stakeholders, dates, amounts encontrados
    extraction_confidence NUMERIC(3,2),
    extraction_model VARCHAR(50),

    -- Auditoría
    manually_verified BOOLEAN DEFAULT FALSE,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraint único por proyecto/documento/código
    CONSTRAINT clauses_project_document_code_unique
        UNIQUE(project_id, document_id, clause_code)
);

-- Índices para clauses
CREATE INDEX IF NOT EXISTS idx_clauses_project ON clauses(project_id);
CREATE INDEX IF NOT EXISTS idx_clauses_document ON clauses(document_id);
CREATE INDEX IF NOT EXISTS idx_clauses_type ON clauses(clause_type);
CREATE INDEX IF NOT EXISTS idx_clauses_code ON clauses(clause_code);
CREATE INDEX IF NOT EXISTS idx_clauses_verified ON clauses(manually_verified, verified_at);

-- =====================================================
-- SECCIÓN 3: TABLAS CORE (si no existen)
-- =====================================================

-- 3.1 Documents
-- Recrear tabla documents con schema mejorado
DROP TABLE IF EXISTS documents CASCADE;

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Classification
    document_type VARCHAR(50) NOT NULL,  -- contract, schedule, budget
    filename VARCHAR(255) NOT NULL,
    file_format VARCHAR(10),  -- pdf, xlsx, bc3, p6, mpp

    -- Storage
    storage_url TEXT NOT NULL,
    storage_encrypted BOOLEAN DEFAULT TRUE,
    file_size_bytes BIGINT,

    -- Processing
    upload_status VARCHAR(50) DEFAULT 'uploaded',  -- uploaded, parsing, parsed, error
    parsed_at TIMESTAMPTZ,
    parsing_error TEXT,

    -- Retention (ROADMAP §6.1)
    retention_until TIMESTAMPTZ,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Audit
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(upload_status);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);

-- 3.2 Extractions
CREATE TABLE extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    extraction_type VARCHAR(50),  -- contract_metadata, milestones, budget_items
    data_json JSONB NOT NULL,
    confidence_score NUMERIC(3,2),

    -- AI tracking
    model_version VARCHAR(50),
    tokens_used INTEGER,
    cost_usd NUMERIC(10,4),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extractions_document ON extractions(document_id);
CREATE INDEX IF NOT EXISTS idx_extractions_type ON extractions(extraction_type);

-- 3.3 Analyses
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    analysis_type VARCHAR(50) DEFAULT 'coherence',
    status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, error
    result_json JSONB,

    -- Coherence Score (ROADMAP §12)
    coherence_score INTEGER CHECK (coherence_score BETWEEN 0 AND 100),
    coherence_breakdown JSONB,  -- Detalle por regla

    -- Alerts
    alerts_count INTEGER DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analyses_project ON analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC);

-- 3.4 Alerts (CON FK A CLAUSES)
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id) ON DELETE CASCADE,

    -- Classification
    severity VARCHAR(20) NOT NULL,  -- critical, high, medium, low
    type VARCHAR(50),
    rule_id VARCHAR(20),  -- Referencia a regla de coherencia

    -- Content
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    suggested_action TEXT,

    -- TRAZABILIDAD LEGAL (ROADMAP §5.3)
    source_clause_id UUID REFERENCES clauses(id),  -- FK a cláusula origen
    affected_document_ids UUID[] DEFAULT '{}',
    affected_wbs_ids UUID[] DEFAULT '{}',
    affected_bom_ids UUID[] DEFAULT '{}',
    evidence_json JSONB,  -- Evidencia estructurada

    -- Estado
    status VARCHAR(50) DEFAULT 'open',  -- open, acknowledged, resolved, dismissed
    requires_human_review BOOLEAN DEFAULT FALSE,

    -- Resolution
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    resolution_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_project ON alerts(project_id);
CREATE INDEX IF NOT EXISTS idx_alerts_analysis ON alerts(analysis_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_clause ON alerts(source_clause_id);  -- NUEVO
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);

-- 3.5 AI Usage Logs (ROADMAP §6.2)
CREATE TABLE ai_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id),
    user_id UUID REFERENCES users(id),

    -- Modelo y operación
    model VARCHAR(50),
    operation VARCHAR(100),
    prompt_version VARCHAR(50),

    -- Tokens y coste
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,4),

    -- Hashes para auditoría y cache (ROADMAP §6.2)
    input_hash VARCHAR(64),  -- SHA-256
    output_hash VARCHAR(64),

    -- Metadatos
    latency_ms INTEGER,
    cached BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_logs_tenant ON ai_usage_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_logs_project ON ai_usage_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_ai_logs_created ON ai_usage_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_logs_input_hash ON ai_usage_logs(input_hash);  -- Para cache

-- =====================================================
-- SECCIÓN 4: STAKEHOLDER INTELLIGENCE
-- =====================================================

-- 4.1 Stakeholders (CON FK A CLAUSES)
CREATE TABLE stakeholders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Identificación
    name VARCHAR(255),
    role VARCHAR(100),
    organization VARCHAR(255),
    department VARCHAR(100),

    -- Clasificación
    power_level VARCHAR(20) DEFAULT 'medium',  -- low, medium, high
    interest_level VARCHAR(20) DEFAULT 'medium',
    quadrant VARCHAR(50),  -- key_player, keep_satisfied, keep_informed, monitor

    -- Contacto
    email VARCHAR(255),
    phone VARCHAR(50),

    -- TRAZABILIDAD LEGAL (ROADMAP §4.5)
    source_clause_id UUID REFERENCES clauses(id),  -- FK a cláusula que lo menciona

    -- Extracción
    extraction_confidence NUMERIC(3,2),
    extracted_from_document_id UUID REFERENCES documents(id),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stakeholders_project ON stakeholders(project_id);
CREATE INDEX IF NOT EXISTS idx_stakeholders_quadrant ON stakeholders(quadrant);
CREATE INDEX IF NOT EXISTS idx_stakeholders_clause ON stakeholders(source_clause_id);  -- NUEVO
CREATE INDEX IF NOT EXISTS idx_stakeholders_email ON stakeholders(email);

-- 4.2 WBS Items (CON FK A CLAUSES)
CREATE TABLE wbs_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES wbs_items(id) ON DELETE CASCADE,  -- Para jerarquía

    -- Identificación
    wbs_code VARCHAR(50) NOT NULL,  -- "1.2.3.4"
    name VARCHAR(255) NOT NULL,
    description TEXT,
    level INTEGER NOT NULL,  -- Nivel en jerarquía (1 = raíz)

    -- Clasificación
    item_type VARCHAR(50),  -- deliverable, work_package, activity

    -- Financial
    budget_allocated NUMERIC(12,2),
    budget_spent NUMERIC(12,2) DEFAULT 0,

    -- Schedule
    planned_start TIMESTAMPTZ,
    planned_end TIMESTAMPTZ,
    actual_start TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,

    -- TRAZABILIDAD LEGAL (ROADMAP §4.2)
    funded_by_clause_id UUID REFERENCES clauses(id),  -- Cláusula que financia

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT wbs_items_project_code_unique UNIQUE(project_id, wbs_code)
);

CREATE INDEX IF NOT EXISTS idx_wbs_items_project ON wbs_items(project_id);
CREATE INDEX IF NOT EXISTS idx_wbs_items_parent ON wbs_items(parent_id);
CREATE INDEX IF NOT EXISTS idx_wbs_items_code ON wbs_items(wbs_code);
CREATE INDEX IF NOT EXISTS idx_wbs_items_clause ON wbs_items(funded_by_clause_id);  -- NUEVO

-- 4.3 BOM Items (CON FK A CLAUSES)
CREATE TABLE bom_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    wbs_item_id UUID REFERENCES wbs_items(id) ON DELETE CASCADE,

    -- Identificación
    item_code VARCHAR(50),
    item_name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),  -- material, equipment, service

    -- Quantity
    quantity NUMERIC(12,3) NOT NULL,
    unit VARCHAR(20),  -- kg, m3, m2, units

    -- Pricing
    unit_price NUMERIC(12,2),
    total_price NUMERIC(12,2),
    currency VARCHAR(3) DEFAULT 'EUR',

    -- Procurement
    supplier VARCHAR(255),
    lead_time_days INTEGER,
    incoterm VARCHAR(20),  -- EXW, FOB, CIF, etc.

    -- TRAZABILIDAD LEGAL (ROADMAP §4.2)
    contract_clause_id UUID REFERENCES clauses(id),  -- Cláusula contractual

    -- Status
    procurement_status VARCHAR(50) DEFAULT 'pending',  -- pending, ordered, delivered

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bom_items_project ON bom_items(project_id);
CREATE INDEX IF NOT EXISTS idx_bom_items_wbs ON bom_items(wbs_item_id);
CREATE INDEX IF NOT EXISTS idx_bom_items_category ON bom_items(category);
CREATE INDEX IF NOT EXISTS idx_bom_items_clause ON bom_items(contract_clause_id);  -- NUEVO
CREATE INDEX IF NOT EXISTS idx_bom_items_status ON bom_items(procurement_status);

-- 4.4 Stakeholder WBS RACI
CREATE TABLE stakeholder_wbs_raci (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stakeholder_id UUID NOT NULL REFERENCES stakeholders(id) ON DELETE CASCADE,
    wbs_item_id UUID NOT NULL REFERENCES wbs_items(id) ON DELETE CASCADE,

    raci_role VARCHAR(20) NOT NULL,  -- R, A, C, I

    -- Metadata
    generated_automatically BOOLEAN DEFAULT TRUE,
    manually_verified BOOLEAN DEFAULT FALSE,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT stakeholder_wbs_raci_unique
        UNIQUE(stakeholder_id, wbs_item_id, raci_role)
);

CREATE INDEX IF NOT EXISTS idx_raci_stakeholder ON stakeholder_wbs_raci(stakeholder_id);
CREATE INDEX IF NOT EXISTS idx_raci_wbs ON stakeholder_wbs_raci(wbs_item_id);
CREATE INDEX IF NOT EXISTS idx_raci_role ON stakeholder_wbs_raci(raci_role);

-- 4.5 Stakeholder Alerts
CREATE TABLE stakeholder_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stakeholder_id UUID NOT NULL REFERENCES stakeholders(id) ON DELETE CASCADE,
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,

    -- Notification
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMPTZ,
    notification_method VARCHAR(50),  -- email, sms, webhook

    -- Status
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stakeholder_alerts_stakeholder ON stakeholder_alerts(stakeholder_id);
CREATE INDEX IF NOT EXISTS idx_stakeholder_alerts_alert ON stakeholder_alerts(alert_id);

-- =====================================================
-- SECCIÓN 5: PROCUREMENT (FASE 2)
-- =====================================================

-- 5.1 BOM Revisions (versionado)
CREATE TABLE bom_revisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    bom_item_id UUID NOT NULL REFERENCES bom_items(id) ON DELETE CASCADE,

    revision_number INTEGER NOT NULL,

    -- Snapshot de cambios
    changes_json JSONB NOT NULL,

    -- Metadata
    changed_by UUID REFERENCES users(id),
    change_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT bom_revisions_item_number_unique
        UNIQUE(bom_item_id, revision_number)
);

CREATE INDEX IF NOT EXISTS idx_bom_revisions_item ON bom_revisions(bom_item_id);
CREATE INDEX IF NOT EXISTS idx_bom_revisions_created ON bom_revisions(created_at DESC);

-- 5.2 Procurement Plan Snapshots
CREATE TABLE procurement_plan_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    snapshot_name VARCHAR(255) NOT NULL,
    snapshot_data JSONB NOT NULL,

    -- Metadata
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_procurement_snapshots_project ON procurement_plan_snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_procurement_snapshots_created ON procurement_plan_snapshots(created_at DESC);

-- =====================================================
-- SECCIÓN 6: KNOWLEDGE GRAPH (ROADMAP §4.6)
-- =====================================================

-- 6.1 Knowledge Graph Nodes (CON INTEGRIDAD REFERENCIAL)
CREATE TABLE knowledge_graph_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    entity_type VARCHAR(50) NOT NULL,  -- contract, clause, milestone, stakeholder, etc.
    entity_id UUID NOT NULL,  -- ID de la entidad real
    label VARCHAR(255),

    properties JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT kg_nodes_project_entity_unique
        UNIQUE(project_id, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_kg_nodes_project ON knowledge_graph_nodes(project_id);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON knowledge_graph_nodes(entity_type);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_entity ON knowledge_graph_nodes(entity_id);

-- 6.2 Knowledge Graph Edges (CON FKs A NODES)
CREATE TABLE knowledge_graph_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    source_node_id UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,

    relationship_type VARCHAR(100) NOT NULL,  -- CONTAINS, REQUIRES, DEPENDS_ON, etc.
    properties JSONB DEFAULT '{}',
    confidence NUMERIC(3,2) DEFAULT 1.0,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT kg_edges_unique
        UNIQUE(project_id, source_node_id, target_node_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_kg_edges_project ON knowledge_graph_edges(project_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_source ON knowledge_graph_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_target ON knowledge_graph_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_rel ON knowledge_graph_edges(relationship_type);

-- =====================================================
-- SECCIÓN 7: AUDIT LOGGING (ROADMAP §6.5)
-- =====================================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),

    -- Acción
    action VARCHAR(100) NOT NULL,  -- create_project, update_alert, delete_document
    resource_type VARCHAR(50),
    resource_id UUID,

    -- Contexto
    ip_address INET,
    user_agent TEXT,

    -- Datos
    old_values JSONB,
    new_values JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(created_at DESC);

-- =====================================================
-- SECCIÓN 8: ROW LEVEL SECURITY (RLS) - 18 TABLAS
-- =====================================================
-- ROADMAP §6.1: RLS completo en todas las tablas con tenant/project
-- CTO GATE 1: Multi-tenant Isolation
-- NOTA: auth.jwt() y auth.uid() ya existen en Supabase, no es necesario crearlas

-- 8.1 Tenants (self-only)
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_self_only ON tenants;
CREATE POLICY tenant_self_only ON tenants
    FOR ALL
    USING (id = (auth.jwt() ->> 'tenant_id')::uuid);

-- 8.2 Users (by tenant_id) - CON CAST UUID
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_users ON users;
CREATE POLICY tenant_isolation_users ON users
    FOR ALL
    USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- 8.3 Projects (by tenant_id) - CON CAST UUID
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_projects ON projects;
CREATE POLICY tenant_isolation_projects ON projects
    FOR ALL
    USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- 8.4 Documents (via project→tenant) - CON CAST UUID
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_documents ON documents;
CREATE POLICY tenant_isolation_documents ON documents
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.5 Clauses (via project→tenant) - NUEVO - CON CAST UUID
ALTER TABLE clauses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_clauses ON clauses;
CREATE POLICY tenant_isolation_clauses ON clauses
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.6 Extractions (via document→project→tenant) - CON CAST UUID
ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_extractions ON extractions;
CREATE POLICY tenant_isolation_extractions ON extractions
    FOR ALL
    USING (
        document_id IN (
            SELECT d.id FROM documents d
            JOIN projects p ON d.project_id = p.id
            WHERE p.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.7 Analyses (via project→tenant) - CON CAST UUID
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_analyses ON analyses;
CREATE POLICY tenant_isolation_analyses ON analyses
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.8 Alerts (via project→tenant) - CON CAST UUID
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_alerts ON alerts;
CREATE POLICY tenant_isolation_alerts ON alerts
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.9 AI Usage Logs (by tenant_id) - CON CAST UUID
ALTER TABLE ai_usage_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_ai_logs ON ai_usage_logs;
CREATE POLICY tenant_isolation_ai_logs ON ai_usage_logs
    FOR ALL
    USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- 8.10 Stakeholders (via project→tenant) - CON CAST UUID
ALTER TABLE stakeholders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_stakeholders ON stakeholders;
CREATE POLICY tenant_isolation_stakeholders ON stakeholders
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.11 WBS Items (via project→tenant) - CON CAST UUID
ALTER TABLE wbs_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_wbs_items ON wbs_items;
CREATE POLICY tenant_isolation_wbs_items ON wbs_items
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.12 BOM Items (via project→tenant) - CON CAST UUID
ALTER TABLE bom_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_bom_items ON bom_items;
CREATE POLICY tenant_isolation_bom_items ON bom_items
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.13 Stakeholder WBS RACI (via project→tenant) - CON CAST UUID
ALTER TABLE stakeholder_wbs_raci ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_raci ON stakeholder_wbs_raci;
CREATE POLICY tenant_isolation_raci ON stakeholder_wbs_raci
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.14 Stakeholder Alerts (via project→tenant) - CON CAST UUID
ALTER TABLE stakeholder_alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_stakeholder_alerts ON stakeholder_alerts;
CREATE POLICY tenant_isolation_stakeholder_alerts ON stakeholder_alerts
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.15 BOM Revisions (via project→tenant) - CON CAST UUID
ALTER TABLE bom_revisions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_bom_revisions ON bom_revisions;
CREATE POLICY tenant_isolation_bom_revisions ON bom_revisions
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.16 Procurement Snapshots (via project→tenant) - CON CAST UUID
ALTER TABLE procurement_plan_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_procurement_snapshots ON procurement_plan_snapshots;
CREATE POLICY tenant_isolation_procurement_snapshots ON procurement_plan_snapshots
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.17 Knowledge Graph Nodes (via project→tenant) - CON CAST UUID
ALTER TABLE knowledge_graph_nodes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_kg_nodes ON knowledge_graph_nodes;
CREATE POLICY tenant_isolation_kg_nodes ON knowledge_graph_nodes
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.18 Knowledge Graph Edges (via project→tenant) - CON CAST UUID
ALTER TABLE knowledge_graph_edges ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_kg_edges ON knowledge_graph_edges;
CREATE POLICY tenant_isolation_kg_edges ON knowledge_graph_edges
    FOR ALL
    USING (
        project_id IN (
            SELECT id FROM projects
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- 8.19 Audit Logs (by tenant_id) - CON CAST UUID
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs;
CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    FOR ALL
    USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- =====================================================
-- SECCIÓN 9: VISTAS PARA MCP SERVER (ROADMAP §4.4)
-- =====================================================
-- Vistas predefinidas para MCP allowlist

CREATE OR REPLACE VIEW v_project_summary AS
SELECT
    p.id,
    p.tenant_id,
    p.name,
    p.status,
    p.coherence_score,
    COUNT(DISTINCT d.id) as document_count,
    COUNT(DISTINCT a.id) as alert_count,
    COUNT(DISTINCT s.id) as stakeholder_count,
    p.created_at,
    p.updated_at
FROM projects p
LEFT JOIN documents d ON d.project_id = p.id
LEFT JOIN alerts a ON a.project_id = p.id AND a.status = 'open'
LEFT JOIN stakeholders s ON s.project_id = p.id
GROUP BY p.id;

CREATE OR REPLACE VIEW v_project_alerts AS
SELECT
    a.id,
    a.project_id,
    p.tenant_id,
    a.severity,
    a.type,
    a.title,
    a.message,
    a.status,
    a.source_clause_id,
    c.clause_code,
    c.title as clause_title,
    a.created_at
FROM alerts a
JOIN projects p ON p.id = a.project_id
LEFT JOIN clauses c ON c.id = a.source_clause_id
WHERE a.status = 'open';

CREATE OR REPLACE VIEW v_project_clauses AS
SELECT
    c.id,
    c.project_id,
    p.tenant_id,
    c.clause_code,
    c.clause_type,
    c.title,
    c.full_text,
    c.manually_verified,
    c.created_at
FROM clauses c
JOIN projects p ON p.id = c.project_id;

CREATE OR REPLACE VIEW v_project_stakeholders AS
SELECT
    s.id,
    s.project_id,
    p.tenant_id,
    s.name,
    s.role,
    s.organization,
    s.quadrant,
    s.source_clause_id,
    c.clause_code,
    s.created_at
FROM stakeholders s
JOIN projects p ON p.id = s.project_id
LEFT JOIN clauses c ON c.id = s.source_clause_id;

-- =====================================================
-- SECCIÓN 10: FUNCIONES DE UTILIDAD
-- =====================================================

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para updated_at
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['projects', 'documents', 'clauses', 'analyses',
                              'alerts', 'stakeholders', 'wbs_items', 'bom_items']
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%I_updated_at ON %I;
            CREATE TRIGGER update_%I_updated_at
                BEFORE UPDATE ON %I
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        ', t, t, t, t);
    END LOOP;
END $$;

-- =====================================================
-- VERIFICACIÓN FINAL
-- =====================================================

DO $$
DECLARE
    rls_count INTEGER;
    table_count INTEGER;
BEGIN
    -- Contar tablas con RLS habilitado
    SELECT COUNT(*) INTO rls_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relrowsecurity = true
    AND n.nspname = 'public';

    RAISE NOTICE 'Tablas con RLS habilitado: %', rls_count;

    IF rls_count < 18 THEN
        RAISE WARNING 'ATENCIÓN: Se esperaban 18 tablas con RLS, solo % habilitadas', rls_count;
    ELSE
        RAISE NOTICE '✓ CTO GATE 1 PASSED: RLS habilitado en % tablas', rls_count;
    END IF;

    -- Verificar constraint unique en users
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'users_tenant_email_unique'
    ) THEN
        RAISE NOTICE '✓ CTO GATE 2 PASSED: UNIQUE(tenant_id, email) en users';
    ELSE
        RAISE WARNING 'ATENCIÓN: Constraint users_tenant_email_unique no existe';
    END IF;

    -- Verificar tabla clauses
    IF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE tablename = 'clauses'
    ) THEN
        RAISE NOTICE '✓ CTO GATE 4 PASSED: Tabla clauses creada';
    ELSE
        RAISE WARNING 'ATENCIÓN: Tabla clauses no existe';
    END IF;
END $$;

-- =====================================================
-- FIN DE MIGRACIÓN v2.4.0
-- =====================================================
