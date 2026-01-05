# C2Pro Product Roadmap
**Contract Intelligence Platform - Master Development Plan**

**Versión:** 2.2.0
**Última actualización:** 29 de Diciembre de 2025
**Autor:** Jesús - Strategic Procurement Director
**Clasificación:** CONFIDENCIAL

---

## Índice

1. [Visión y Propuesta de Valor](#1-visión-y-propuesta-de-valor)
2. [Principios Rectores](#2-principios-rectores)
3. [Stack Tecnológico](#3-stack-tecnológico)
4. [Arquitectura del Sistema](#4-arquitectura-del-sistema)
5. [MVP - Fase 1 (12 Semanas)](#5-mvp---fase-1-12-semanas)
6. [Fase 2 - Copiloto de Compras](#6-fase-2---copiloto-de-compras)
7. [Fase 3 - Control de Ejecución](#7-fase-3---control-de-ejecución)
8. [Fase 4 - Futuro (2026+)](#8-fase-4---futuro-2026)
9. [Métricas de Éxito](#9-métricas-de-éxito)
10. [Gestión de Riesgos](#10-gestión-de-riesgos)
11. [Plan de Testing](#11-plan-de-testing)
12. [Plan de Deployment](#12-plan-de-deployment)

---

## 1. Visión y Propuesta de Valor

### 1.1 Visión

> **"Hacer de C2Pro el copiloto de inteligencia contractual que toda empresa de construcción necesita para evitar sobrecostes evitables."**

Empoderar a empresas de construcción, ingeniería e industria con análisis automático de coherencia entre contratos, cronogramas y presupuestos, detectando incoherencias antes de que se conviertan en sobrecostes.

### 1.2 El Problema

El **15-30% de los sobrecostes** en proyectos de construcción e ingeniería se deben a la desconexión entre tres documentos críticos:

- ❌ **Contrato** → Cláusulas, plazos, penalizaciones contractuales
- ❌ **Cronograma** → Actividades, hitos, dependencias temporales
- ❌ **Presupuesto** → Partidas, mediciones, precios unitarios

**Consecuencias:**
- Penalizaciones por incumplimiento de plazos contractuales
- Sobrecostes por partidas presupuestarias no alineadas con el contrato
- Pérdida de oportunidades de revisión de precios
- Falta de trazabilidad entre documentos clave
- Riesgos no identificados hasta que es tarde

### 1.3 Propuesta de Valor Única

> **"C2Pro es el único sistema que cruza automáticamente contrato, cronograma y presupuesto para detectar incoherencias antes de que cuesten dinero."**

| Diferenciador | Beneficio Cuantificable |
|---------------|-------------------------|
| **Auditoría Tridimensional Automática** | Detecta incoherencias en minutos, no días (ahorro de 8-16h/proyecto) |
| **IA Especializada en Construcción** | Entiende cláusulas, plazos y partidas del sector (BC3, FIEBDC) |
| **Coherence Score 0-100** | Indicador único que cuantifica el riesgo del proyecto |
| **Alertas Proactivas** | Previene problemas antes de que ocurran (reducción 15-30% sobrecostes) |
| **De Auditoría a Copiloto** | Genera automáticamente Planes de Compras optimizados |

### 1.4 Mercado Objetivo

| Segmento | Características |
|----------|-----------------|
| **Primario (MVP)** | Empresas medianas (50-250 empleados), facturación 15-100M€, proyectos >500K€, España y LATAM |
| **Secundario (Fase 2)** | Grandes constructoras (>250 empleados), proyectos >5M€, necesidades de integración |
| **Terciario (Fase 3)** | Estudios de ingeniería, promotores inmobiliarios, consultoras de project management |

---

## 2. Principios Rectores

### 2.1 Principios de Producto

1. **User-Centric:** Cada feature debe resolver un dolor real del usuario, validado con entrevistas
2. **AI-First, Not AI-Only:** La IA potencia, pero el usuario decide y valida
3. **Actionable Insights:** No solo detectar problemas, proponer soluciones concretas
4. **Nicho Deep, Not Wide:** Dominar construcción antes de expandir a otros sectores

### 2.2 Principios Técnicos

1. **Simple, Seguro, Suficiente:** Arquitectura optimizada para fundador solo con capacidad de escalar
2. **Monolito Modular:** Un servicio bien estructurado, no microservicios prematuros
3. **Security by Design:** Multi-tenancy con RLS, anonymization de PII, GDPR-compliant desde día 1
4. **Cost-Conscious:** Free tiers + serverless hasta tener revenue recurrente
5. **IA como Core:** Claude API con model routing, budget control y cache inteligente

### 2.3 Principios de Desarrollo

1. **Ship Fast, Learn Faster:** Ciclos de 2 semanas máximo por entregable
2. **Quality Gates:** No pasar de fase sin tests críticos pasando
3. **Document as You Build:** Código autodocumentado + decisiones en ADRs
4. **Progressive Enhancement:** MVP funcional -> optimizar -> features avanzadas

---

## 3. Stack Tecnológico

### 3.1 Stack Completo

| Capa | Tecnología | Versión | Justificación | Alternativa Considerada |
|------|------------|---------|---------------|-------------------------|
| **Frontend** | Next.js | 14+ | SSR, excelente DX, Vercel deploy | Remix (menos maduro) |
| | React | 18+ | Estándar industry, ecosystem | Vue (menos React devs) |
| | Tailwind CSS | 3+ | Utility-first, rapid prototyping | CSS Modules (más código) |
| | shadcn/ui | latest | Componentes accesibles, customizables | MUI (bundle size) |
| | TypeScript | 5+ | Type safety, mejor DX | JavaScript (sin types) |
| **Backend** | FastAPI | 0.104+ | Async, Pydantic v2, OpenAPI auto | Flask (sin async) |
| | Python | 3.11+ | Ecosystem AI/ML, async nativo | Node.js (menos AI libs) |
| | Pydantic | v2 | Validación automática, serialización | Marshmallow (más verboso) |
| **Database** | PostgreSQL | 15+ | ACID, JSON, Full-text search | MongoDB (sin ACID) |
| | Supabase | Managed | RLS nativo, backups, auth incluido | AWS RDS (más complejo) |
| **Cache** | Redis | 7+ | Pub/sub, rate limiting, cache | Memcached (menos features) |
| | Upstash | Serverless | Pay-per-request, sin mínimo | Redis Cloud (mínimo $5) |
| **Storage** | Cloudflare R2 | - | S3-compatible, sin egress fees | AWS S3 (egress caro) |
| **IA** | Claude API | Sonnet 3.5 | Mejor calidad docs largos, 200K ctx | GPT-4 (más caro) |
| | | Haiku | Fast, barato para clasificación | GPT-3.5 (menos capaz) |
| **Observability** | Sentry | Free tier | Error tracking, performance | Rollbar (menos features) |
| | Structlog | latest | Structured logging JSON | Python logging (menos struct) |
| | UptimeRobot | Free tier | Uptime monitoring, alertas | Pingdom (de pago) |
| **Parsers** | PyMuPDF (fitz) | latest | PDF extraction, rápido | PyPDF2 (más lento) |
| | openpyxl | latest | Excel read/write | xlrd (deprecated) |
| | pyfiebdc | latest | BC3 parsing (presupuestos) | Custom parser (más trabajo) |
| **Deployment** | Vercel | Pro | Frontend, edge functions, CDN | Netlify (menos DX) |
| | Railway | Hobby+ | Backend, PostgreSQL addon | Render (menos uptime) |
| **CI/CD** | GitHub Actions | - | Integrado con repo, free tier | GitLab CI (vendor lock) |

### 3.2 Dependencias Clave Python (Backend)

```python
# API Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0

# Database & ORM
supabase==2.3.0
psycopg[binary]==3.1.13
sqlalchemy==2.0.23

# AI & NLP
anthropic==0.8.0
tiktoken==0.5.1

# Document Parsing
PyMuPDF==1.23.8
openpyxl==3.1.2
pyfieldbc==1.1.0  # BC3 Spanish standard

# Utils
python-dotenv==1.0.0
structlog==23.2.0
sentry-sdk==1.38.0
redis==5.0.1

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
httpx==0.25.2
```

### 3.3 Dependencias Clave Frontend

```json
{
  "dependencies": {
    "next": "^14.0.4",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@supabase/supabase-js": "^2.39.0",
    "@tanstack/react-query": "^5.13.4",
    "tailwindcss": "^3.4.0",
    "@radix-ui/react-*": "latest",
    "lucide-react": "^0.294.0",
    "zod": "^3.22.4",
    "react-hook-form": "^7.49.2",
    "recharts": "^2.10.3"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "@types/react": "^18.2.45",
    "eslint": "^8.56.0",
    "prettier": "^3.1.1"
  }
}
```

---

## 4. Arquitectura del Sistema

### 4.1 Diagrama de Arquitectura Completo

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CAPA DE PRESENTACIÓN                            │
│              Next.js 14 + Tailwind + shadcn/ui                      │
│                      (Deploy: Vercel)                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Dashboard │  │Projects  │  │ Upload   │  │ Alerts   │            │
│  │  Page    │  │   List   │  │   Page   │  │  Panel   │            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────────────────┘
                              │ HTTPS / JWT
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CAPA DE APLICACIÓN                              │
│                FastAPI + Pydantic v2 (Railway)                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│  │    Auth    │ │  Projects  │ │ Documents  │ │  Analysis  │       │
│  │ Middleware │ │   Router   │ │   Router   │ │   Router   │       │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    CAPA DE SERVICIOS                       │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │    │
│  │  │  Parser  │ │Anonymizer│ │AI Service│ │Coherence │      │    │
│  │  │ Service  │ │ Service  │ │ (Claude) │ │  Engine  │      │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
          │              │                │              │
          ▼              ▼                ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
    │PostgreSQL│  │  Redis   │  │    R2    │  │  Claude API  │
    │(Supabase)│  │(Upstash) │  │(Cloudflr)│  │  (Anthropic) │
    │          │  │          │  │          │  │              │
    │ - RLS    │  │ - Cache  │  │- Docs    │  │- Sonnet 3.5  │
    │ - Auth   │  │ - Rate   │  │- Files   │  │- Haiku       │
    │ - PITR   │  │   Limit  │  │          │  │              │
    └──────────┘  └──────────┘  └──────────┘  └──────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │               OBSERVABILIDAD & MONITOREO                 │
    │  Sentry (Errors) | Structlog (Logs) | UptimeRobot (Up)  │
    └──────────────────────────────────────────────────────────┘
```

### 4.2 Flujo de Datos - Análisis de Coherencia

```
[Usuario] → Upload Docs (Contract, Schedule, Budget)
    │
    ▼
[Frontend] → POST /api/documents/upload
    │
    ▼
[API Router] → Auth Middleware (valida JWT, extrae tenant_id)
    │
    ▼
[Document Service] → Parser Service (PDF/Excel/BC3)
    │                    ▼
    │               [Extracted Text/Data]
    │                    │
    ▼                    ▼
[Storage R2] ←─────── [Anonymizer Service] → Detecta/reemplaza PII
    │                    │
    │                    ▼
    │               [AI Service] → Claude API (extract clauses/items)
    │                    │
    │                    ▼
    │               [Extraction Results] → Cache Redis
    │                    │
    └─────────┬──────────┘
              ▼
         [Coherence Engine] → Cruza 3 docs
              │
              ▼
         [Alert Generator] → Genera alertas por incoherencias
              │
              ▼
         [Scoring Engine] → Calcula Coherence Score (0-100)
              │
              ▼
         [PostgreSQL] → Guarda Analysis + Alerts
              │
              ▼
         [Frontend] ← GET /api/analysis/{id}
              │
              ▼
         [Usuario] → Ve dashboard con alertas y score
```

### 4.3 Modelo de Datos Completo

```sql
-- TENANTS (Multi-tenancy)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    subscription_plan VARCHAR(50) DEFAULT 'free',
    settings JSONB DEFAULT '{}',
    ai_budget_monthly NUMERIC(10,2) DEFAULT 50.00,
    ai_spend_current NUMERIC(10,2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- USERS
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) DEFAULT 'user', -- admin, user, viewer
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- PROJECTS
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50), -- obra_civil, edificacion, industrial
    status VARCHAR(50) DEFAULT 'draft', -- draft, analyzing, completed, archived
    coherence_score INTEGER CHECK (coherence_score BETWEEN 0 AND 100),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- DOCUMENTS
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- contract, schedule, budget
    filename VARCHAR(255) NOT NULL,
    file_format VARCHAR(10), -- pdf, xlsx, bc3
    storage_url TEXT NOT NULL,
    file_size_bytes BIGINT,
    upload_status VARCHAR(50) DEFAULT 'uploaded', -- uploaded, parsing, parsed, error
    parsed_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- EXTRACTIONS (Datos extraídos por IA)
CREATE TABLE extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extraction_type VARCHAR(50), -- clauses, schedule_items, budget_items
    data_json JSONB NOT NULL,
    confidence_score NUMERIC(3,2), -- 0.00 to 1.00
    model_version VARCHAR(50), -- e.g., "contract_extraction_v1.0"
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ANALYSES (Resultados de análisis de coherencia)
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) DEFAULT 'coherence', -- coherence, risk, compliance
    status VARCHAR(50) DEFAULT 'pending', -- pending, running, completed, failed
    result_json JSONB,
    coherence_score INTEGER CHECK (coherence_score BETWEEN 0 AND 100),
    alerts_count INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ALERTS (Alertas de incoherencias)
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL, -- critical, high, medium, low
    type VARCHAR(50), -- missing_clause, date_mismatch, budget_mismatch
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    affected_documents JSONB, -- IDs de docs afectados
    suggested_action TEXT,
    status VARCHAR(50) DEFAULT 'open', -- open, acknowledged, resolved, false_positive
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI_USAGE_LOGS (Tracking de uso de IA)
CREATE TABLE ai_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id),
    model VARCHAR(50), -- claude-sonnet-3.5, claude-haiku
    operation VARCHAR(100), -- extract_clauses, coherence_analysis
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- WBS (Work Breakdown Structure) - Estructura de Desglose del Trabajo
CREATE TABLE wbs_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES wbs_items(id), -- Para jerarquía
    code VARCHAR(50) NOT NULL, -- e.g., "1.2.3"
    name VARCHAR(255) NOT NULL,
    description TEXT,
    level INTEGER NOT NULL, -- 1 (proyecto), 2 (fase), 3 (entregable), 4 (paquete trabajo)
    type VARCHAR(50), -- phase, deliverable, work_package, task
    schedule_activity_ids JSONB, -- IDs de actividades del cronograma
    budget_item_ids JSONB, -- IDs de partidas presupuestarias
    responsible VARCHAR(255),
    estimated_duration_days INTEGER,
    estimated_cost NUMERIC(12,2),
    is_critical_path BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, code)
);

-- BOM (Bill of Materials) - Lista de Materiales
CREATE TABLE bom_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    wbs_item_id UUID REFERENCES wbs_items(id), -- Vinculado a WBS
    parent_bom_id UUID REFERENCES bom_items(id), -- Para BOM jerárquico
    version_number INTEGER DEFAULT 0, -- 0 = inicial, 1+ = revisiones
    version_status VARCHAR(50) DEFAULT 'current', -- current, superseded, archived

    -- Identificación
    item_code VARCHAR(100), -- Código interno del material
    item_name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100), -- material, equipment, labor, service
    subcategory VARCHAR(100), -- concrete, steel, electrical, plumbing

    -- Cantidades y Precios
    unit VARCHAR(50), -- m3, ton, m2, unit, hour
    quantity NUMERIC(12,3) NOT NULL,
    unit_price NUMERIC(12,2),
    total_price NUMERIC(12,2),

    -- Proveedor y Logística Internacional
    supplier VARCHAR(255),
    origin_country VARCHAR(100), -- e.g., "China", "Germany", "USA"
    destination_country VARCHAR(100), -- e.g., "Spain", "USA"
    incoterm VARCHAR(20), -- EXW, FOB, CIF, DAP, DDP, etc.

    -- Lead Times Desglosados
    production_time_days INTEGER, -- Tiempo fabricación
    transit_time_days INTEGER, -- Tiempo tránsito (marítimo/aéreo/terrestre)
    customs_clearance_days INTEGER DEFAULT 0, -- Tiempo despacho aduanas
    buffer_days INTEGER DEFAULT 7, -- Buffer de seguridad
    total_lead_time_days INTEGER, -- Calculado: producción + tránsito + aduanas + buffer

    -- Fechas
    optimal_order_date DATE, -- Fecha óptima de pedido (calculada)
    actual_order_date DATE, -- Fecha real de pedido
    estimated_arrival_date DATE, -- Fecha estimada llegada
    actual_arrival_date DATE, -- Fecha real llegada
    required_on_site_date DATE, -- Fecha requerida en obra (del WBS)

    -- Estado y Tracking
    status VARCHAR(50) DEFAULT 'planned', -- planned, rfq_sent, ordered, in_production, in_transit, customs, received, installed
    tracking_number VARCHAR(255), -- Número seguimiento logístico
    critical_for_milestone VARCHAR(255), -- Hito crítico que depende de este material

    -- Costes Adicionales (Incoterm)
    freight_cost NUMERIC(12,2), -- Coste flete (si no incluido en precio)
    customs_duties NUMERIC(12,2), -- Aranceles aduaneros
    insurance_cost NUMERIC(12,2), -- Seguro transporte
    total_landed_cost NUMERIC(12,2), -- Coste total desembarcado (landed cost)

    -- Referencias
    budget_item_id UUID, -- Referencia a partida presupuestaria
    contract_clause_ref VARCHAR(255), -- Referencia a cláusula contractual
    specifications JSONB, -- Especificaciones técnicas

    -- Auditoría de Cambios
    change_reason TEXT, -- Razón del cambio (si version_number > 0)
    previous_version_id UUID REFERENCES bom_items(id), -- Referencia a versión anterior
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX idx_bom_project_version ON bom_items(project_id, version_number);
CREATE INDEX idx_bom_status ON bom_items(status);
CREATE INDEX idx_bom_optimal_date ON bom_items(optimal_order_date);

-- BOM_REVISIONS - Historial de Cambios del BOM
CREATE TABLE bom_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL, -- 0, 1, 2, 3...
    revision_name VARCHAR(100), -- "Initial Plan", "Q1 Revision", "Post-tender Update"
    revision_type VARCHAR(50), -- initial, scheduled_review, scope_change, supplier_change, cost_update
    status VARCHAR(50) DEFAULT 'draft', -- draft, approved, active, superseded

    -- Métricas de la Revisión
    total_items_count INTEGER,
    items_added INTEGER DEFAULT 0,
    items_removed INTEGER DEFAULT 0,
    items_modified INTEGER DEFAULT 0,
    total_cost_change NUMERIC(12,2), -- Δ coste vs revisión anterior
    total_leadtime_change_days INTEGER, -- Δ lead time promedio

    -- Razón y Aprobación
    change_summary TEXT, -- Resumen ejecutivo de cambios
    change_reason TEXT, -- Razón detallada
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(project_id, revision_number)
);

-- PROCUREMENT_PLAN_SNAPSHOTS - Snapshots del Plan de Compras
CREATE TABLE procurement_plan_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    bom_revision_id UUID REFERENCES bom_revisions(id),
    snapshot_date TIMESTAMPTZ DEFAULT NOW(),
    snapshot_type VARCHAR(50), -- baseline, monthly_review, milestone_review

    -- Snapshot Data (JSON con el plan completo en ese momento)
    plan_data JSONB NOT NULL, -- Incluye todos los BOM items, fechas, costes

    -- Métricas del Snapshot
    total_planned_cost NUMERIC(12,2),
    total_actual_cost NUMERIC(12,2),
    cost_variance NUMERIC(12,2), -- Actual - Planned
    cost_variance_percentage NUMERIC(5,2), -- (Variance / Planned) * 100

    on_time_deliveries INTEGER,
    late_deliveries INTEGER,
    pending_deliveries INTEGER,
    avg_delay_days NUMERIC(5,1),

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security (RLS) Policies
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_projects ON projects
    FOR ALL USING (tenant_id = auth.jwt() ->> 'tenant_id');

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_documents ON documents
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects WHERE tenant_id = auth.jwt() ->> 'tenant_id'
        )
    );

ALTER TABLE wbs_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_wbs ON wbs_items
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects WHERE tenant_id = auth.jwt() ->> 'tenant_id'
        )
    );

ALTER TABLE bom_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_bom ON bom_items
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects WHERE tenant_id = auth.jwt() ->> 'tenant_id'
        )
    );

ALTER TABLE bom_revisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_bom_revisions ON bom_revisions
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects WHERE tenant_id = auth.jwt() ->> 'tenant_id'
        )
    );

ALTER TABLE procurement_plan_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_snapshots ON procurement_plan_snapshots
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects WHERE tenant_id = auth.jwt() ->> 'tenant_id'
        )
    );

-- Similar RLS for todas las tablas con tenant_id o project_id
```

### 4.4 Diagrama de Relaciones: Documentos → WBS → BOM → Versioning

```
┌──────────────────────────────────────────────────────────────────┐
│                    FLUJO DE GENERACIÓN                           │
└──────────────────────────────────────────────────────────────────┘

DOCUMENTOS ORIGINALES:
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  CONTRATO   │  │ CRONOGRAMA  │  │ PRESUPUESTO │
│             │  │             │  │             │
│ - Hitos     │  │ - Activid.  │  │ - Partidas  │
│ - Plazos    │  │ - Fechas    │  │ - Cantid.   │
│ - Cláusulas │  │ - Duraciones│  │ - Precios   │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
              ┌──────────────────┐
              │   EXTRACCIÓN IA  │
              │   (Claude API)   │
              └────────┬─────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Cláusulas  │ │  Actividad  │ │   Partidas  │
│  Extraídas  │ │  Cronograma │ │Presupuestarias│
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────┼───────────────┘
                       ▼
              ┌──────────────────┐
              │   GENERADOR WBS  │
              │  (Motor Cruce)   │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │    WBS ITEMS     │ ← Estructura jerárquica del proyecto
              │                  │   1. Proyecto
              │  1.1 Fase 1      │   2. Fases
              │    1.1.1 Task A  │   3. Entregables
              │    1.1.2 Task B  │   4. Paquetes de trabajo
              │  1.2 Fase 2      │
              │    ...           │   Vincula:
              └────────┬─────────┘   - Actividades cronograma
                       │             - Partidas presupuesto
                       │             - Hitos contractuales
                       ▼
              ┌──────────────────┐
              │  GENERADOR BOM   │
              │  (Por WBS Item)  │
              │  + INCOTERMS     │
              │  + TRÁNSITOS     │
              └────────┬─────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │      BOM ITEMS (v0)          │ ← VERSIÓN INICIAL (Baseline)
         │      [BASELINE]              │
         │                              │
         │  Material A - FOB China      │   - Incoterm (FOB, CIF, DDP)
         │    → WBS 1.1.1               │   - Origen: China
         │    → Prod: 20d               │   - Destino: Spain
         │    → Transit: 35d (marítimo) │   - Lead time desglosado:
         │    → Customs: 5d             │       * Producción
         │    → Buffer: 7d              │       * Tránsito
         │    → TOTAL: 67d              │       * Aduanas
         │    → Order: T-67             │       * Buffer
         │    → Landed Cost: €15,000    │   - Landed cost (con flete, aranceles)
         │                              │   - Tracking number
         │  Material B - DDP Germany    │   - Status tracking
         │    → WBS 1.1.2               │
         │    → TOTAL: 25d              │
         │    → Critical Path           │
         └──────────┬───────────────────┘
                    │
                    │ [CREAR SNAPSHOT BASELINE]
                    ▼
         ┌──────────────────────────┐
         │  PROCUREMENT SNAPSHOT    │
         │       v0 (Baseline)      │
         │  - Plan completo         │
         │  - Costes planificados   │
         │  - Fechas planificadas   │
         └──────────────────────────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
┌────────────┐ ┌─────────┐ ┌──────────┐
│  PLAN DE   │ │   RFQ   │ │ ALERTAS  │
│  COMPRAS   │ │Generator│ │Proactivas│
│            │ │         │ │          │
│ - Material │ │- Inco.  │ │- T-30    │
│ - Incoterm │ │- Origin │ │- Transit │
│ - Tránsito │ │- Transit│ │- Customs │
│ - Landed $ │ │- Specs  │ │- Critical│
└────────────┘ └─────────┘ └──────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
           EJECUCIÓN Y CONTROL DE CAMBIOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   [CAMBIO DETECTADO: Supplier cambió precio, plazo retrasado, etc.]
                    │
                    ▼
         ┌──────────────────────────┐
         │   CREAR NUEVA REVISIÓN   │
         │      BOM v1, v2, v3...   │
         │                          │
         │  - change_reason         │
         │  - items_modified        │
         │  - cost_variance         │
         │  - previous_version_id   │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │    BOM_REVISIONS         │
         │  Revision 1: "Q1 Review" │
         │  - Items added: 3        │
         │  - Items removed: 1      │
         │  - Items modified: 5     │
         │  - Cost Δ: +€12,000      │
         │  - Lead time Δ: +8 days  │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │  COMPARADOR DE VERSIONES │
         │    v0 (Baseline)         │
         │      vs                  │
         │    vN (Current)          │
         │                          │
         │  DESVIACIONES:           │
         │  • Coste: +15.2%         │
         │  • Plazo: +12 días       │
         │  • Items: 5 retrasados   │
         │  • Landed cost: +€18K    │
         └──────────┬───────────────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
┌────────────┐ ┌─────────┐ ┌──────────┐
│ DASHBOARD  │ │ ALERTAS │ │ REPORTS  │
│DESVIACIONES│ │CRÍTICAS │ │EJECUTIVOS│
│            │ │         │ │          │
│ - Coste ±% │ │- Delay  │ │- Lessons │
│ - Plazo ±d │ │- Budget │ │  Learned │
│ - On-time% │ │- Transit│ │- Trends  │
└────────────┘ └─────────┘ └──────────┘

```

---

## 5. MVP - Fase 1 (12 Semanas)

**Objetivo:** Lanzar MVP funcional con capacidad de auditoría tridimensional automática para validar hipótesis con primeros clientes.

**Target Release:** Semana 12 (finales de Marzo 2025)
**Target Users:** 3-5 pilotos (empresas construcción conocidas)

### 5.1 Semanas 1-2: FUNDACIÓN

#### Features

- **F1.1:** Setup inicial del proyecto (monorepo con apps/api + apps/web)
- **F1.2:** Configuración de Supabase (PostgreSQL + Auth)
- **F1.3:** Implementación de RLS (Row Level Security) para multi-tenancy
- **F1.4:** Middleware de autenticación (JWT validation, tenant extraction)
- **F1.5:** Setup de Sentry para error tracking
- **F1.6:** Configuración de CI/CD básico (GitHub Actions)

#### Entregables Técnicos

```
apps/
├── api/
│   ├── src/
│   │   ├── main.py                    # FastAPI app
│   │   ├── config.py                  # Settings (Pydantic BaseSettings)
│   │   ├── middleware/
│   │   │   └── auth.py                # JWT validation + tenant extraction
│   │   ├── database/
│   │   │   ├── client.py              # Supabase client
│   │   │   └── schema.sql             # Initial schema con RLS
│   │   └── routers/
│   │       └── health.py              # Health check endpoint
│   ├── requirements.txt
│   └── Dockerfile
├── web/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx               # Landing/login
│   │   │   └── dashboard/
│   │   │       └── page.tsx           # Dashboard placeholder
│   │   ├── lib/
│   │   │   └── supabase.ts            # Supabase client
│   │   └── components/
│   │       └── ui/                    # shadcn/ui components
│   ├── package.json
│   └── next.config.js
└── .github/
    └── workflows/
        ├── api-ci.yml                  # Backend tests + deploy
        └── web-ci.yml                  # Frontend tests + deploy
```

#### Criterios de Aceptación

- [ ] User puede registrarse y hacer login con email/password
- [ ] JWT válido permite acceso a endpoints protegidos
- [ ] RLS impide acceso a datos de otros tenants (test con 2 tenants)
- [ ] Middleware rechaza JWTs inválidos o sin tenant_id
- [ ] Sentry captura errores correctamente (test con error manual)
- [ ] CI/CD pipeline corre tests y despliega a staging en cada push a main
- [ ] Health check endpoint responde 200 OK

#### Riesgos y Mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| Configuración incorrecta de RLS permite data leak | Media | Tests automatizados multi-tenant + code review |
| JWT validation vulnerable | Baja | Usar librería oficial Supabase + security audit |

---

### 5.2 Semanas 3-4: DOCUMENTOS

#### Features

- **F2.1:** Upload de archivos a Cloudflare R2 (presigned URLs)
- **F2.2:** Parser de PDF (extracción de texto con PyMuPDF)
- **F2.3:** Parser de Excel (extracción de hojas con openpyxl)
- **F2.4:** Parser de BC3 (formato FIEBDC para presupuestos españoles)
- **F2.5:** UI de upload con drag & drop y validación de formatos
- **F2.6:** Listado de documentos por proyecto

#### Entregables Técnicos

```python
# apps/api/src/services/storage.py
class R2StorageService:
    """Upload/download files to Cloudflare R2"""
    async def upload_file(file: UploadFile, tenant_id: str) -> str
    async def get_presigned_url(file_key: str) -> str
    async def delete_file(file_key: str) -> bool

# apps/api/src/services/parsers/
├── base.py                    # BaseParser abstract class
├── pdf_parser.py              # PDFParser (PyMuPDF)
├── excel_parser.py            # ExcelParser (openpyxl)
└── bc3_parser.py              # BC3Parser (pyfieldbc)

# apps/api/src/routers/documents.py
@router.post("/upload")
async def upload_document(
    file: UploadFile,
    project_id: UUID,
    document_type: DocumentType,  # contract | schedule | budget
    tenant: TenantContext = Depends(get_tenant)
)

@router.get("/projects/{project_id}/documents")
async def list_documents(project_id: UUID)
```

```typescript
// apps/web/src/components/DocumentUpload.tsx
export function DocumentUpload({ projectId }: Props) {
  // Drag & drop zone
  // File type validation (PDF, XLSX, BC3)
  // Progress indicator
  // Error handling
}
```

#### Criterios de Aceptación

- [ ] PDF de contrato sube correctamente y extrae texto completo
- [ ] Excel de cronograma parsea todas las hojas y filas
- [ ] BC3 de presupuesto parsea capítulos y partidas correctamente
- [ ] Archivos se guardan en R2 con estructura: `{tenant_id}/{project_id}/{doc_id}.ext`
- [ ] UI muestra progress bar durante upload
- [ ] Errores de parsing muestran mensaje claro al usuario
- [ ] Documentos quedan asociados al proyecto correcto (test multi-tenant)

#### Tests Críticos

```python
# tests/test_parsers.py
def test_pdf_parser_extracts_text():
    """PDF parser debe extraer todo el texto del contrato"""

def test_excel_parser_handles_multiple_sheets():
    """Excel parser debe parsear todas las hojas"""

def test_bc3_parser_extracts_budget_items():
    """BC3 parser debe extraer capítulos y partidas con precios"""

def test_upload_enforces_tenant_isolation():
    """Upload no permite subir a proyecto de otro tenant"""
```

---

### 5.3 Semanas 5-6: IA CORE

#### Features

- **F3.1:** Servicio de anonymization (detección y reemplazo de PII)
- **F3.2:** AI Service con Claude API (Sonnet + Haiku)
- **F3.3:** Prompts versionados para extracción (v1.0)
- **F3.4:** Cost controller (budget tracking por tenant)
- **F3.5:** Cache de respuestas IA en Redis (evitar re-procesamiento)
- **F3.6:** Model routing (Haiku para clasificación, Sonnet para extracción)

#### Entregables Técnicos

```python
# apps/api/src/services/anonymizer.py
class AnonymizerService:
    """Detecta y reemplaza PII antes de enviar a Claude API"""

    PII_PATTERNS = {
        "dni": r"\d{8}[A-Z]",
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\+?\d{9,15}",
        "iban": r"ES\d{22}",
        # ... más patrones
    }

    def anonymize(self, text: str) -> tuple[str, dict]:
        """Retorna (texto_anonimizado, mapa_reversión)"""

    def de_anonymize(self, text: str, mapping: dict) -> str:
        """Restaura valores originales"""

# apps/api/src/services/ai/
├── client.py                  # Claude API client wrapper
├── prompts/
│   ├── contract_extraction_v1.py
│   ├── schedule_extraction_v1.py
│   └── budget_extraction_v1.py
├── model_router.py            # Decide qué modelo usar
└── cost_controller.py         # Track y limita costes por tenant

# apps/api/src/services/ai/client.py
class ClaudeService:
    async def extract_contract_clauses(
        self,
        text: str,
        tenant_id: UUID
    ) -> ContractExtraction:
        """Extrae cláusulas del contrato usando Sonnet"""

    async def extract_schedule_items(
        self,
        data: dict,
        tenant_id: UUID
    ) -> ScheduleExtraction:
        """Extrae hitos del cronograma"""

    async def extract_budget_items(
        self,
        bc3_data: dict,
        tenant_id: UUID
    ) -> BudgetExtraction:
        """Extrae partidas del presupuesto"""
```

#### Prompts v1.0 (Ejemplos)

```python
# apps/api/src/services/ai/prompts/contract_extraction_v1.py
SYSTEM_PROMPT = """Eres un experto en análisis de contratos de construcción.
Extrae la siguiente información del contrato:

1. **Fechas clave:**
   - Fecha de firma
   - Plazo de ejecución (inicio y fin)
   - Plazos de entrega parciales

2. **Penalizaciones:**
   - Penalizaciones por retraso (cantidad y forma de cálculo)
   - Penalizaciones por incumplimiento

3. **Revisión de precios:**
   - Cláusulas de revisión de precios
   - Fórmulas aplicables

4. **Garantías:**
   - Garantías exigidas
   - Plazos de garantía

Responde SOLO con JSON válido siguiendo este schema:
{schema_json}
"""

USER_PROMPT = """Analiza el siguiente contrato:

{contract_text}

Extrae la información solicitada."""
```

#### Criterios de Aceptación

- [ ] Anonymizer detecta y reemplaza correctamente DNI, emails, teléfonos, IBANs
- [ ] Claude API extrae cláusulas de contrato de prueba con >80% accuracy
- [ ] Claude API extrae hitos de cronograma con fechas correctas
- [ ] Claude API extrae partidas de BC3 con precios correctos
- [ ] Cost controller bloquea requests cuando tenant alcanza budget (test)
- [ ] Cache Redis evita llamar a Claude API 2 veces para mismo input (test)
- [ ] Model router usa Haiku para clasificación simple (ahorro >50% coste)

#### Tests Críticos

```python
def test_anonymizer_replaces_dni():
    """Anonymizer debe reemplazar DNIs con placeholders"""

def test_cost_controller_blocks_over_budget():
    """Cost controller debe bloquear cuando tenant supera budget"""

def test_cache_avoids_duplicate_api_calls():
    """Cache debe evitar llamadas duplicadas a Claude API"""

def test_contract_extraction_accuracy():
    """Extracción de contrato debe tener >80% accuracy en golden dataset"""
```

---

### 5.4 Semanas 7-8: COHERENCIA + WBS/BOM

#### Features

- **F4.1:** Motor de cruce tridimensional (Contract ↔ Schedule ↔ Budget)
- **F4.2:** Generador de WBS (Work Breakdown Structure) automático
- **F4.3:** Generador de BOM (Bill of Materials) por WBS item
- **F4.4:** Algoritmo de detección de incoherencias (15+ tipos)
- **F4.5:** Generador de alertas (severidad: critical, high, medium, low)
- **F4.6:** Cálculo de Coherence Score (0-100)
- **F4.7:** API endpoints para ejecutar análisis y obtener resultados

#### Entregables Técnicos

```python
# apps/api/src/services/coherence/
├── engine.py                  # Motor principal de coherencia
├── wbs_generator.py           # Generador WBS (NUEVO)
├── bom_generator.py           # Generador BOM (NUEVO)
├── rules/
│   ├── date_rules.py          # Reglas de fechas
│   ├── budget_rules.py        # Reglas de presupuesto
│   ├── penalty_rules.py       # Reglas de penalizaciones
│   └── wbs_bom_rules.py       # Reglas WBS/BOM (NUEVO)
├── scorer.py                  # Calcula Coherence Score
└── alert_generator.py         # Genera alertas

# apps/api/src/services/coherence/wbs_generator.py
class WBSGenerator:
    """Genera WBS automáticamente a partir de documentos"""

    async def generate_wbs(self, project_id: UUID) -> list[WBSItem]:
        """
        Genera estructura WBS jerárquica:

        1. Nivel 1: Proyecto completo
        2. Nivel 2: Fases (extraídas del cronograma y contrato)
        3. Nivel 3: Entregables (hitos contractuales)
        4. Nivel 4: Paquetes de trabajo (actividades cronograma)

        Vincula cada WBS item con:
        - Actividades del cronograma (schedule_activity_ids)
        - Partidas presupuestarias (budget_item_ids)
        - Identifica ruta crítica (is_critical_path)
        """

        # 1. Obtener extracciones
        contract = await self.get_contract_extraction(project_id)
        schedule = await self.get_schedule_extraction(project_id)
        budget = await self.get_budget_extraction(project_id)

        # 2. Generar jerarquía WBS
        wbs_root = self._create_wbs_root(project_id, contract)
        wbs_phases = self._identify_phases(schedule, contract)
        wbs_deliverables = self._map_deliverables(contract.milestones)
        wbs_work_packages = self._map_work_packages(schedule.activities)

        # 3. Vincular con presupuesto
        wbs_items = self._link_budget_items(wbs_phases, budget)

        # 4. Calcular ruta crítica
        wbs_items = self._calculate_critical_path(wbs_items, schedule)

        return wbs_items

# apps/api/src/services/coherence/bom_generator.py
class BOMGenerator:
    """Genera BOM automáticamente a partir de WBS y presupuesto"""

    async def generate_bom(self, project_id: UUID) -> list[BOMItem]:
        """
        Genera BOM por cada WBS item:

        1. Extrae materiales de partidas presupuestarias (BC3)
        2. Calcula cantidades por WBS item
        3. Identifica lead times (IA + base de datos histórica)
        4. Calcula fechas óptimas de pedido
        5. Marca items críticos para ruta crítica
        6. Vincula con cláusulas contractuales (especificaciones)
        """

        # 1. Obtener WBS y presupuesto
        wbs_items = await self.get_wbs_items(project_id)
        budget = await self.get_budget_extraction(project_id)
        contract = await self.get_contract_extraction(project_id)

        bom_items = []

        for wbs_item in wbs_items:
            # 2. Obtener partidas presupuestarias de este WBS item
            budget_items = self._get_budget_items_for_wbs(wbs_item, budget)

            for budget_item in budget_items:
                # 3. Extraer materiales de la partida
                materials = self._extract_materials_from_budget_item(budget_item)

                for material in materials:
                    # 4. Calcular lead time (IA + DB histórica)
                    lead_time = await self._calculate_lead_time(material)

                    # 5. Calcular fecha óptima de pedido
                    optimal_date = self._calculate_optimal_order_date(
                        wbs_item.start_date,
                        lead_time,
                        buffer_days=7
                    )

                    # 6. Vincular con cláusula contractual
                    contract_clause = self._find_related_clause(material, contract)

                    bom_item = BOMItem(
                        wbs_item_id=wbs_item.id,
                        item_name=material.name,
                        quantity=material.quantity,
                        unit=material.unit,
                        unit_price=material.unit_price,
                        lead_time_days=lead_time,
                        optimal_order_date=optimal_date,
                        critical_for_milestone=wbs_item.milestone if wbs_item.is_critical_path else None,
                        contract_clause_ref=contract_clause
                    )

                    bom_items.append(bom_item)

        return bom_items

# apps/api/src/services/coherence/engine.py
class CoherenceEngine:
    """Motor de análisis tridimensional"""

    async def analyze_project(self, project_id: UUID) -> AnalysisResult:
        """Ejecuta análisis completo de coherencia"""

        # 1. Obtener extracciones de los 3 docs
        contract = await self.get_contract_extraction(project_id)
        schedule = await self.get_schedule_extraction(project_id)
        budget = await self.get_budget_extraction(project_id)

        # 2. Generar WBS (NUEVO)
        wbs_items = await self.wbs_generator.generate_wbs(project_id)

        # 3. Generar BOM (NUEVO)
        bom_items = await self.bom_generator.generate_bom(project_id)

        # 4. Aplicar reglas de coherencia
        alerts = []
        alerts.extend(await self.check_date_coherence(contract, schedule))
        alerts.extend(await self.check_budget_coherence(contract, budget))
        alerts.extend(await self.check_schedule_budget_coherence(schedule, budget))
        alerts.extend(await self.check_wbs_coherence(wbs_items, contract, schedule))  # NUEVO
        alerts.extend(await self.check_bom_coherence(bom_items, budget))  # NUEVO

        # 5. Calcular score
        coherence_score = self.scorer.calculate_score(alerts)

        # 6. Guardar análisis
        return await self.save_analysis(project_id, alerts, coherence_score, wbs_items, bom_items)
```

#### Reglas de Coherencia (Ejemplos)

| ID | Regla | Documentos | Severidad |
|----|-------|------------|-----------|
| **R1** | Plazo ejecución contrato ≠ fecha fin cronograma | Contract + Schedule | Critical |
| **R2** | Hito contractual sin actividad en cronograma | Contract + Schedule | High |
| **R3** | Partida presupuesto sin respaldo contractual | Contract + Budget | Medium |
| **R4** | Penalización por retraso > presupuesto partida | Contract + Budget | High |
| **R5** | Cronograma excede plazo contractual | Contract + Schedule | Critical |
| **R6** | Suma partidas presupuesto ≠ precio contrato (±5%) | Contract + Budget | Medium |
| **R7** | Actividad cronograma sin partida presupuestaria | Schedule + Budget | Medium |
| **R8** | Hito entrega parcial sin actividades previas | Schedule | Low |
| **R9** | Cláusula revisión precios sin partidas afectadas | Contract + Budget | Low |
| **R10** | Plazo garantía no contemplado en cronograma | Contract + Schedule | Medium |
| **R11** | WBS item sin actividades de cronograma vinculadas | WBS + Schedule | High |
| **R12** | WBS item sin partidas presupuestarias asignadas | WBS + Budget | High |
| **R13** | Material BOM sin lead time calculado | BOM | Medium |
| **R14** | Material crítico con fecha pedido posterior a fecha necesidad | BOM + Schedule | Critical |
| **R15** | BOM item sin vinculación a partida presupuestaria | BOM + Budget | High |
| **R16** | Suma costes BOM ≠ suma partidas presupuesto (±10%) | BOM + Budget | Medium |
| **R17** | Material sin especificaciones contractuales | BOM + Contract | Low |
| **R18** | WBS critical path no coincide con ruta crítica cronograma | WBS + Schedule | High |

#### Cálculo de Coherence Score

```python
# apps/api/src/services/coherence/scorer.py
class CoherenceScorer:
    """Calcula score 0-100 basado en alertas"""

    SEVERITY_WEIGHTS = {
        "critical": 20,
        "high": 10,
        "medium": 5,
        "low": 2
    }

    def calculate_score(self, alerts: list[Alert]) -> int:
        """
        Score = 100 - sum(severity_weights)
        Min: 0, Max: 100
        """
        deductions = sum(
            self.SEVERITY_WEIGHTS[alert.severity]
            for alert in alerts
        )
        return max(0, 100 - deductions)
```

#### Criterios de Aceptación

- [ ] WBS se genera automáticamente con 4 niveles de jerarquía (proyecto, fase, entregable, tarea)
- [ ] Todos los WBS items están vinculados a actividades del cronograma
- [ ] Todos los WBS items tienen partidas presupuestarias asignadas
- [ ] Ruta crítica se identifica correctamente en WBS
- [ ] BOM se genera automáticamente por cada WBS item
- [ ] BOM incluye lead times calculados para cada material
- [ ] BOM calcula fecha óptima de pedido (fecha_necesidad - lead_time - buffer)
- [ ] Materiales críticos están marcados en BOM
- [ ] Motor detecta 18+ tipos de incoherencias en dataset de prueba (incluyendo WBS/BOM)
- [ ] Proyecto sin incoherencias obtiene score 100
- [ ] Proyecto con incoherencia crítica obtiene score ≤80
- [ ] Alertas incluyen mensaje claro + acción sugerida
- [ ] Análisis se completa en <3 minutos para proyecto típico (3 docs + WBS + BOM)
- [ ] UI muestra alertas ordenadas por severidad

#### Tests Críticos

```python
def test_wbs_generates_4_level_hierarchy():
    """WBS debe generar jerarquía de 4 niveles correctamente"""

def test_wbs_links_all_schedule_activities():
    """Todos los WBS items deben estar vinculados a actividades cronograma"""

def test_wbs_identifies_critical_path():
    """WBS debe identificar correctamente la ruta crítica"""

def test_bom_generates_for_all_wbs_items():
    """BOM debe generarse para todos los WBS items con materiales"""

def test_bom_calculates_lead_times():
    """BOM debe calcular lead times para todos los materiales"""

def test_bom_calculates_optimal_order_date():
    """BOM debe calcular fecha óptima pedido = fecha_necesidad - lead_time - 7días"""

def test_bom_marks_critical_materials():
    """Materiales en ruta crítica deben estar marcados como critical"""

def test_detects_execution_deadline_mismatch():
    """Debe detectar cuando plazo contrato ≠ fecha fin cronograma"""

def test_detects_wbs_without_schedule_link():
    """Debe detectar WBS items sin actividades de cronograma"""

def test_detects_bom_without_budget_link():
    """Debe detectar BOM items sin partida presupuestaria"""

def test_detects_late_material_order():
    """Debe detectar cuando fecha pedido > fecha necesidad - lead_time"""

def test_perfect_project_scores_100():
    """Proyecto sin incoherencias debe obtener score 100"""

def test_critical_alert_reduces_score():
    """Alerta crítica debe reducir score en 20 puntos"""

def test_generates_actionable_alerts():
    """Alertas deben incluir suggested_action no vacío"""
```

---

### 5.5 Semanas 9-10: UI/UX

#### Features

- **F5.1:** Dashboard principal con métricas clave
- **F5.2:** Lista de proyectos con filtros y búsqueda
- **F5.3:** Página de detalle de proyecto
- **F5.4:** Panel de alertas con filtros (severidad, estado)
- **F5.5:** Export de análisis a PDF
- **F5.6:** Responsive design (mobile-friendly)

#### Entregables Técnicos

```typescript
// apps/web/src/app/dashboard/
├── page.tsx                   // Dashboard principal
├── projects/
│   ├── page.tsx               // Lista de proyectos
│   └── [id]/
│       ├── page.tsx           // Detalle de proyecto
│       ├── alerts/
│       │   └── page.tsx       // Alertas del proyecto
│       └── analysis/
│           └── page.tsx       // Resultados de análisis

// apps/web/src/components/
├── DashboardMetrics.tsx       // Cards con métricas
├── ProjectCard.tsx            // Card de proyecto con score
├── AlertList.tsx              // Lista de alertas
├── CoherenceScoreGauge.tsx    // Gauge visual del score
└── AnalysisExportPDF.tsx      // Export a PDF
```

#### Wireframes Clave

**Dashboard:**
```
┌─────────────────────────────────────────────────────────┐
│  C2Pro                                     [User Menu]   │
├─────────────────────────────────────────────────────────┤
│  Dashboard                                              │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Total   │ │  Active  │ │   Avg    │ │  Critical│  │
│  │Projects  │ │ Analysis │ │  Score   │ │  Alerts  │  │
│  │    12    │ │     3    │ │    87    │ │     5    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                         │
│  Recent Projects                                        │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [Score: 92] Proyecto A  | 3 docs | 2 alerts  [>] │ │
│  │ [Score: 78] Proyecto B  | 3 docs | 8 alerts  [>] │ │
│  │ [Score: 95] Proyecto C  | 2 docs | 1 alert   [>] │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Project Detail:**
```
┌─────────────────────────────────────────────────────────┐
│  ← Projects  /  Proyecto A                              │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌───────────────────────────────┐│
│  │  Coherence      │  │  Documents (3)                 ││
│  │   Score: 92     │  │  ✓ Contract.pdf                ││
│  │   [Gauge 92%]   │  │  ✓ Schedule.xlsx               ││
│  │                 │  │  ✓ Budget.bc3                  ││
│  │  [Export PDF]   │  │  [+ Upload Document]           ││
│  └─────────────────┘  └───────────────────────────────┘│
│                                                         │
│  Alerts (5)                         [Filter: All ▼]    │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 🔴 CRITICAL: Execution deadline mismatch          │ │
│  │    Contract: 12 months | Schedule: 14 months      │ │
│  │    → Suggested: Review schedule or request ext.   │ │
│  │    [Acknowledge] [Resolve]                         │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 🟡 MEDIUM: Budget item without contract clause    │ │
│  │    ...                                             │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

#### Criterios de Aceptación

- [ ] Dashboard carga en <2s con datos de 10+ proyectos
- [ ] Gauge de Coherence Score es visualmente claro (colores: 0-60=rojo, 61-80=amarillo, 81-100=verde)
- [ ] Filtros de alertas funcionan (severidad, estado)
- [ ] Export PDF incluye: score, alertas, documentos, fecha
- [ ] Responsive design funciona en mobile (>360px width)
- [ ] Navegación entre páginas es fluida (Next.js prefetch)

---

### 5.6 Semanas 11-12: HARDENING

#### Features

- **F6.1:** Security testing (penetration tests básicos)
- **F6.2:** AI accuracy testing con golden dataset
- **F6.3:** Load testing (100 concurrent users)
- **F6.4:** Deployment a producción
- **F6.5:** Onboarding de 3-5 clientes pilot

#### Entregables Técnicos

```
tests/
├── security/
│   ├── test_rls_isolation.py          # Tests multi-tenant
│   ├── test_jwt_validation.py         # Tests autenticación
│   └── test_sql_injection.py          # Tests SQL injection
├── ai/
│   ├── test_extraction_accuracy.py    # Accuracy vs golden dataset
│   └── golden_dataset/
│       ├── contract_1.json
│       ├── schedule_1.json
│       └── budget_1.json
├── performance/
│   └── locustfile.py                  # Load testing con Locust
└── e2e/
    └── test_full_analysis_flow.py     # Test flujo completo
```

#### Tests de Seguridad

```python
# tests/security/test_rls_isolation.py
async def test_tenant_cannot_access_other_tenant_projects():
    """Tenant A no puede acceder a proyectos de Tenant B"""

async def test_user_cannot_upload_to_other_tenant_project():
    """Usuario no puede subir docs a proyecto de otro tenant"""

async def test_sql_injection_in_search():
    """Búsqueda está protegida contra SQL injection"""
```

#### Golden Dataset (AI Accuracy)

| Documento | Campos a Extraer | Target Accuracy |
|-----------|------------------|-----------------|
| Contract 1 | Fecha inicio, plazo, penalizaciones | >90% |
| Schedule 1 | 10 hitos con fechas | >85% |
| Budget 1 | 20 partidas con precios | >85% |

#### Load Testing

```python
# tests/performance/locustfile.py
class C2ProUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def list_projects(self):
        self.client.get("/api/projects")

    @task(1)
    def upload_document(self):
        # Simula upload

    @task(2)
    def get_analysis(self):
        # Simula obtener análisis
```

**Target Performance:**
- 100 usuarios concurrentes
- Avg response time: <500ms (p95 <1s)
- Error rate: <1%

#### Deployment Checklist

- [ ] Variables de entorno configuradas en Railway + Vercel
- [ ] Backups automáticos habilitados en Supabase
- [ ] Sentry configurado con alertas a email
- [ ] UptimeRobot monitoreando API + Web cada 5 min
- [ ] DNS configurado (c2pro.app o similar)
- [ ] SSL/TLS activo (Vercel automático)
- [ ] Rate limiting activo (60 req/min general, 10 req/min AI)

#### Onboarding Pilots

**Empresas target:**
- 3-5 empresas construcción (50-250 empleados)
- Relación previa con fundador (warm intro)
- Dispuestos a dar feedback semanal
- Pilot gratuito 3 meses a cambio de testimonial

**Plan de onboarding:**
1. Llamada kickoff (30 min): explicar plataforma
2. Setup tenant + usuarios (por nosotros)
3. Subir proyecto real (acompañados)
4. Review semanal resultados + feedback
5. Iteración rápida basada en feedback

#### Criterios de Aceptación (Fase 1 Completa)

- [ ] Tests de seguridad pasan al 100%
- [ ] AI accuracy >85% en golden dataset
- [ ] Load test soporta 100 usuarios concurrentes con <1% error
- [ ] Producción deployada y estable (uptime >99% primera semana)
- [ ] 3 pilots onboarded y usando la plataforma
- [ ] Documentación básica de usuario creada

---

## 6. Fase 2 - Copiloto de Compras

**Timeline:** Semanas 13-20 (8 semanas)
**Objetivo:** Evolucionar de auditoría pasiva a copiloto activo que genera planes de compras.

**PREREQUISITO:** Esta fase requiere que WBS y BOM estén implementados (completado en Fase 1, Semanas 7-8).

### 6.1 Features Principales

#### F7: Generación Automática de Plan de Compras

**Descripción:** A partir del **WBS** y **BOM** generados automáticamente, crear un Plan de Compras optimizado.

**Input (generado en Fase 1):**
- **WBS items** con actividades vinculadas y ruta crítica identificada
- **BOM items** con cantidades, precios, lead times y fechas óptimas calculadas
- Cláusulas contractuales relevantes

**Output:**
- Plan de Compras estructurado con:
  - Material/servicio a comprar (del BOM)
  - Cantidad estimada (del BOM)
  - Fecha óptima de compra (calculada en BOM: fecha_necesidad - lead_time - buffer)
  - Criticidad (basada en WBS critical path)
  - Presupuesto asignado (del BOM)
  - Proveedor sugerido (si disponible en BOM)
  - WBS item asociado (trazabilidad completa)

**Lógica:**
1. **Leer BOM items** del proyecto (ya generados)
2. **Ordenar por fecha óptima de pedido** (campo optimal_order_date del BOM)
3. **Agrupar compras similares** para economías de escala (mismo material, proveedor, fechas cercanas)
4. **Priorizar materiales críticos** (critical_for_milestone no null en BOM)
5. **Generar alertas proactivas** para fechas próximas de pedido (T-15, T-7 días)
6. **Vincular con cláusulas contractuales** (contract_clause_ref del BOM)

#### F8: Generación de Borradores de RFQ

**Descripción:** Generar automáticamente borradores de Request for Quotation (solicitud de oferta) a partir de **BOM items**.

**Input (del BOM + documentos):**
- **BOM item** con:
  - Nombre del material (item_name)
  - Cantidad y unidad (quantity, unit)
  - Especificaciones técnicas (specifications JSON)
  - Cláusula contractual relacionada (contract_clause_ref)
- Condiciones contractuales aplicables
- Fecha de entrega requerida (calculada desde WBS)

**Output:**
- Documento RFQ con:
  - Descripción detallada del material/servicio (del BOM)
  - Cantidades y unidades (del BOM)
  - Especificaciones técnicas (del BOM.specifications + cláusula contractual)
  - Condiciones de entrega (fecha_necesidad del WBS)
  - Plazo de respuesta (7-15 días antes de optimal_order_date)
  - Criterios de evaluación (precio, calidad, plazo, certificaciones)
  - Referencia a cláusula contractual (BOM.contract_clause_ref)

#### F9: Comparador Contrato-Factura

**Descripción:** Comparar facturas recibidas con cláusulas contractuales y partidas presupuestarias.

**Features:**
- Upload de facturas (PDF)
- Extracción automática (proveedor, fecha, items, importes)
- Comparación con contrato:
  - ¿Proveedor está en contrato?
  - ¿Precios coinciden con presupuesto?
  - ¿Cumple condiciones de pago?
- Alertas por discrepancias

#### F10: Alertas Proactivas de Cumplimiento

**Descripción:** Sistema de notificaciones automáticas para plazos, hitos y obligaciones contractuales.

**Tipos de alertas:**
- **T-7 días:** Próximo hito contractual
- **T-15 días:** Fecha óptima de compra según plan
- **T-30 días:** Revisión de precios aplicable
- **T-3 días:** Plazo de pago factura
- **Inmediata:** Nueva incoherencia detectada
- **Tránsito:** Material en tránsito retrasado (vs estimated_arrival_date)
- **Aduanas:** Material detenido en aduanas >3 días del estimado

#### F11: Control de Versiones y Análisis de Desviaciones

**Descripción:** Sistema de versionado del BOM y Plan de Compras con análisis de desviaciones planificado vs actual.

**Funcionalidades:**

1. **Versionado Automático:**
   - **v0 (Baseline):** Plan inicial aprobado
   - **v1, v2, v3...:** Revisiones por cambios (precios, plazos, proveedores, scope)
   - Cada versión registra: change_reason, items_modified, cost_variance, approved_by

2. **Tipos de Revisiones:**
   - **Scheduled Review:** Revisión trimestral/mensual planificada
   - **Scope Change:** Cambio de alcance del proyecto
   - **Supplier Change:** Cambio de proveedor
   - **Cost Update:** Actualización de precios/costes
   - **Delay Impact:** Retrasos que afectan plan de compras

3. **Snapshots del Plan de Compras:**
   - Captura estado completo del plan en un momento dado
   - Permite comparaciones históricas (baseline vs mes 3 vs mes 6)
   - Métricas: total_planned_cost, total_actual_cost, cost_variance, on_time_deliveries, late_deliveries

4. **Comparador Planificado vs Actual:**
   - **Dashboard de Desviaciones:**
     - Coste: Planificado vs Actual (±%)
     - Plazo: On-time delivery rate (%)
     - Cantidad: Variaciones en cantidades pedidas
     - Landed Cost: Variación en coste total desembarcado (Incoterms impact)

   - **Análisis por Material:**
     - Material X: Planificado €10K (FOB), Actual €12K (CIF) → +20%
     - Material Y: Planificado 30d lead time, Actual 45d → +15d retraso
     - Material Z: Tránsito estimado 35d, real 48d (retraso portuario)

   - **Análisis por Categoría:**
     - Steel: +15% coste (commodities price increase)
     - Electrical: +8 días promedio (supplier delays)
     - Equipment: On-time 95% ✓

5. **Trazabilidad de Cambios:**
   - Cada BOM item con version_number > 0 tiene:
     - change_reason (texto explicativo)
     - previous_version_id (linked list de versiones)
     - approved_by + approved_at (auditoría)

6. **Reports Ejecutivos:**
   - Lessons Learned: ¿Qué materiales tuvieron más desviaciones?
   - Supplier Performance: % on-time por proveedor
   - Incoterm Impact: ¿FOB vs DDP cost variance?
   - Transit Time Accuracy: ¿Estimaciones de tránsito fueron correctas?

**Output:**
- Timeline de versiones del BOM
- Dashboard visual de desviaciones (cost, schedule, quantity)
- Gráficos de tendencias (cost variance over time)
- Reporte de lecciones aprendidas para futuros proyectos

### 6.2 Entregables Técnicos

```python
# apps/api/src/services/procurement/
├── plan_generator.py          # Generador de Plan de Compras
├── rfq_generator.py           # Generador de RFQ
├── invoice_comparator.py      # Comparador facturas
├── alert_scheduler.py         # Scheduler de alertas proactivas
├── version_manager.py         # Gestor de versiones BOM (NUEVO)
├── deviation_analyzer.py      # Analizador de desviaciones (NUEVO)
└── incoterm_calculator.py     # Calculadora landed cost por Incoterm (NUEVO)

# apps/api/src/services/procurement/version_manager.py
class BOMVersionManager:
    """Gestiona versionado y revisiones del BOM"""

    async def create_revision(
        self,
        project_id: UUID,
        revision_type: str,
        change_summary: str,
        change_reason: str,
        user_id: UUID
    ) -> BOMRevision:
        """
        Crea nueva revisión del BOM:
        1. Incrementa revision_number
        2. Marca versión anterior como superseded
        3. Crea nueva versión (current) de BOM items modificados
        4. Calcula métricas: items_added, items_removed, items_modified, cost_change
        5. Crea snapshot del plan de compras
        """

    async def compare_versions(
        self,
        project_id: UUID,
        version_a: int,  # e.g., 0 (baseline)
        version_b: int   # e.g., 3 (current)
    ) -> VersionComparison:
        """
        Compara dos versiones del BOM:
        - Items added/removed/modified
        - Cost variance
        - Lead time variance
        - Landed cost variance (Incoterm changes)
        """

    async def get_version_timeline(self, project_id: UUID) -> list[BOMRevision]:
        """Retorna timeline completo de revisiones del proyecto"""

# apps/api/src/services/procurement/deviation_analyzer.py
class DeviationAnalyzer:
    """Analiza desviaciones planificado vs actual"""

    async def analyze_cost_deviations(self, project_id: UUID) -> CostDeviation:
        """
        Analiza desviaciones de coste:
        - Baseline (v0) vs Current (vN)
        - Por material, categoría, proveedor
        - Incoterm impact (FOB vs CIF vs DDP)
        - Landed cost variance
        """

    async def analyze_schedule_deviations(self, project_id: UUID) -> ScheduleDeviation:
        """
        Analiza desviaciones de plazo:
        - Planned lead time vs Actual lead time
        - Production time variance
        - Transit time variance
        - Customs clearance variance
        - On-time delivery rate
        """

    async def analyze_supplier_performance(self, project_id: UUID) -> SupplierPerformance:
        """
        Performance por proveedor:
        - On-time delivery %
        - Cost variance %
        - Lead time accuracy
        - Quality issues
        """

    async def generate_lessons_learned(self, project_id: UUID) -> LessonsLearned:
        """
        Genera reporte de lecciones aprendidas:
        - Materiales con más desviaciones
        - Lead times subestimados/sobreestimados
        - Incoterms más cost-effective
        - Proveedores más confiables
        """

# apps/api/src/services/procurement/incoterm_calculator.py
class IncotermCalculator:
    """Calcula landed cost según Incoterm"""

    INCOTERM_RESPONSIBILITIES = {
        "EXW": {"freight": False, "insurance": False, "customs": False},
        "FOB": {"freight": False, "insurance": False, "customs": False},
        "CIF": {"freight": True, "insurance": True, "customs": False},
        "DAP": {"freight": True, "insurance": True, "customs": False},
        "DDP": {"freight": True, "insurance": True, "customs": True},
    }

    def calculate_landed_cost(
        self,
        unit_price: float,
        quantity: float,
        incoterm: str,
        origin_country: str,
        destination_country: str,
        freight_cost: float = None,
        customs_duties_rate: float = None
    ) -> LandedCost:
        """
        Calcula coste total desembarcado según Incoterm:

        EXW: unit_price * quantity + freight + insurance + customs
        FOB: unit_price * quantity + freight + insurance + customs
        CIF: unit_price * quantity + customs (freight+insurance incluidos)
        DAP: unit_price * quantity + customs (freight+insurance incluidos)
        DDP: unit_price * quantity (todo incluido)
        """

        base_cost = unit_price * quantity
        landed_cost_breakdown = {
            "base_cost": base_cost,
            "freight_cost": 0.0,
            "insurance_cost": 0.0,
            "customs_duties": 0.0,
            "total_landed_cost": base_cost
        }

        # Aplicar costes según Incoterm
        if not self.INCOTERM_RESPONSIBILITIES[incoterm]["freight"]:
            # Comprador paga flete
            landed_cost_breakdown["freight_cost"] = freight_cost or self._estimate_freight(origin, dest)

        if not self.INCOTERM_RESPONSIBILITIES[incoterm]["insurance"]:
            # Comprador paga seguro (típicamente 0.5-1% del valor)
            landed_cost_breakdown["insurance_cost"] = base_cost * 0.007

        if not self.INCOTERM_RESPONSIBILITIES[incoterm]["customs"]:
            # Comprador paga aranceles
            landed_cost_breakdown["customs_duties"] = base_cost * (customs_duties_rate or self._get_tariff_rate(origin, dest))

        landed_cost_breakdown["total_landed_cost"] = sum(landed_cost_breakdown.values())
        return landed_cost_breakdown

# apps/api/src/routers/procurement.py
@router.post("/projects/{project_id}/procurement-plan")
async def generate_procurement_plan(project_id: UUID)

@router.post("/procurement-items/{item_id}/rfq")
async def generate_rfq(item_id: UUID)

@router.post("/invoices/upload")
async def upload_invoice(file: UploadFile, project_id: UUID)

# === NUEVOS ENDPOINTS VERSIONADO ===

@router.post("/projects/{project_id}/bom/revisions")
async def create_bom_revision(
    project_id: UUID,
    revision_data: BOMRevisionCreate,
    user: User = Depends(get_current_user)
):
    """Crea nueva revisión del BOM"""

@router.get("/projects/{project_id}/bom/revisions")
async def list_bom_revisions(project_id: UUID):
    """Lista todas las revisiones del BOM del proyecto"""

@router.get("/projects/{project_id}/bom/compare")
async def compare_bom_versions(
    project_id: UUID,
    version_a: int = 0,
    version_b: int = None  # None = latest
):
    """Compara dos versiones del BOM"""

@router.get("/projects/{project_id}/deviations/cost")
async def get_cost_deviations(project_id: UUID):
    """Dashboard de desviaciones de coste"""

@router.get("/projects/{project_id}/deviations/schedule")
async def get_schedule_deviations(project_id: UUID):
    """Dashboard de desviaciones de plazo"""

@router.get("/projects/{project_id}/supplier-performance")
async def get_supplier_performance(project_id: UUID):
    """Reporte de performance de proveedores"""

@router.get("/projects/{project_id}/lessons-learned")
async def get_lessons_learned(project_id: UUID):
    """Reporte de lecciones aprendidas"""

@router.post("/projects/{project_id}/snapshots")
async def create_procurement_snapshot(project_id: UUID, snapshot_type: str):
    """Crea snapshot del plan de compras actual"""
```

### 6.3 Métricas de Éxito Fase 2

| Métrica | Target |
|---------|--------|
| Tiempo generación Plan de Compras | <5 min para proyecto típico |
| Accuracy RFQ (campos correctos) | >90% |
| Accuracy cálculo landed cost (Incoterms) | >95% vs cálculo manual |
| Accuracy estimación tránsitos | ±5 días para rutas comunes |
| Alertas proactivas útiles (no spam) | >80% consideradas útiles |
| Adopción feature (% usuarios activos) | >60% |
| **Versionado:**
| Proyectos con >1 revisión BOM | >40% (cambios son comunes) |
| Tiempo comparar v0 vs vN | <10 segundos |
| Accuracy detección desviaciones | >90% |
| **Supplier Performance:**
| On-time delivery tracking | 100% de materiales recibidos |
| Accuracy lead time (±10%) | >70% de materiales |

---

## 7. Fase 3 - Control de Ejecución

**Timeline:** Semanas 21-28 (8 semanas)
**Objetivo:** Cerrar el ciclo con seguimiento de avance real vs planificado.

### 7.1 Features Principales

#### F11: Ingesta de Avance Real

**Descripción:** Permitir introducir avance real de actividades y compras realizadas.

**Métodos de ingesta:**
- Manual (UI): usuario marca % avance actividades
- Import Excel: template con actividades y % avance
- API REST: integración con ERP/software project management

#### F12: Comparador Planificado vs Real

**Descripción:** Dashboard visual comparando planificación vs ejecución real.

**Visualizaciones:**
- Curva S (planificado vs real)
- Gantt con desviaciones
- Tabla de desviaciones críticas
- KPIs: SPI (Schedule Performance Index), CPI (Cost Performance Index)

#### F13: Alertas Predictivas

**Descripción:** Usar IA para predecir desviaciones antes de que ocurran.

**Inputs:**
- Histórico de avance
- Desviaciones actuales
- Factores externos (clima, festivos)

**Outputs:**
- Predicción: "Actividad X retrasará 5 días basado en tendencia actual"
- Impacto: "Retraso afectará a hito contractual Y"
- Sugerencias: "Acelerar actividad Z o solicitar extensión plazo"

#### F14: API REST Documentada

**Descripción:** API completa documentada con OpenAPI para integraciones.

**Endpoints clave:**
- CRUD proyectos, documentos, análisis
- Webhooks para eventos (nuevo análisis, alerta crítica)
- Autenticación API Key para integraciones

### 7.2 Métricas de Éxito Fase 3

| Métrica | Target |
|---------|--------|
| Accuracy predicciones (±10%) | >70% |
| Usuarios usando tracking real | >40% |
| Integraciones vía API activas | >5 clientes |

---

## 8. Fase 4 - Futuro (2026+)

### 8.1 Features Exploratorias

#### Predictive Analytics Avanzado
- Forecasting de sobrecostes con ML
- Identificación de patrones de riesgo (NLP sobre contratos históricos)
- Simulación de escenarios (what-if analysis)

#### Natural Language Generation
- Generación automática de informes ejecutivos
- Resúmenes de contratos en lenguaje natural
- Risk assessments narrativos

#### Mobile Application
- App nativa iOS/Android
- Acceso offline a documentos clave
- Notificaciones push para alertas críticas
- Aprobaciones móviles (RFQs, facturas)

#### Machine Learning Interpretability
- Explicar decisiones de IA con SHAP/LIME
- "¿Por qué la IA marcó esta cláusula como riesgo?"
- Confianza del usuario en recomendaciones

#### Integraciones Nativas
- Procore, Aconex, PlanRadar
- SharePoint, Google Drive
- SAP, Oracle ERP
- Microsoft Project, Primavera P6

#### Marketplace de Proveedores
- Directory de proveedores verificados
- Ratings y reviews
- Comparador de ofertas automático
- Negociación asistida por IA

---

## 9. Métricas de Éxito

### 9.1 Métricas de Producto (MVP)

| Métrica | Target Mes 1 | Target Mes 3 | Target Mes 6 |
|---------|--------------|--------------|--------------|
| **Usuarios Activos (MAU)** | 5-10 | 20-30 | 50-75 |
| **Proyectos Analizados** | 10-15 | 50-75 | 150-200 |
| **Coherence Score Promedio** | 75+ | 80+ | 85+ |
| **Alertas Generadas/Proyecto** | 5-10 | 5-10 | 5-10 |
| **Tiempo Análisis Promedio** | <3 min | <2 min | <2 min |
| **NPS (Net Promoter Score)** | N/A | 30+ | 50+ |

### 9.2 Métricas Técnicas

| Métrica | Target |
|---------|--------|
| **Uptime** | >99.5% |
| **API Response Time (p95)** | <1s |
| **AI Accuracy (Extraction)** | >85% |
| **RLS Isolation (Test Pass Rate)** | 100% |
| **Test Coverage (Critical Paths)** | >80% |
| **Security Vulnerabilities (High/Critical)** | 0 |

### 9.3 Métricas de Negocio

| Métrica | Año 1 | Año 2 | Año 3 |
|---------|-------|-------|-------|
| **MRR (Monthly Recurring Revenue)** | €6K | €30K | €90K |
| **Clientes Activos** | 10 | 50 | 150 |
| **ARPU (Average Revenue Per User)** | €600 | €600 | €600 |
| **Churn Mensual** | <5% | <3% | <2% |
| **CAC (Customer Acquisition Cost)** | €3K | €3K | €4K |
| **LTV (Lifetime Value)** | €18K | €24K | €32K |
| **LTV:CAC Ratio** | 6:1 | 8:1 | 8:1 |

---

## 10. Gestión de Riesgos

### 10.1 Riesgos Técnicos

| ID | Riesgo | Probabilidad | Impacto | Mitigación | Owner |
|----|--------|--------------|---------|------------|-------|
| **RT1** | Data breach entre tenants | Baja | Crítico | RLS + tests automatizados + code review | Dev Lead |
| **RT2** | Costes AI descontrolados | Media | Alto | Budget caps + model routing + cache | CTO |
| **RT3** | Claude API outage prolongado | Media | Alto | Circuit breaker + fallback + cache | Dev Lead |
| **RT4** | Calidad extracción IA baja | Media | Alto | Golden dataset + evaluación continua | AI Lead |
| **RT5** | Escalabilidad BD (>1000 proyectos) | Baja | Medio | Partitioning + índices + monitoring | Dev Lead |
| **RT6** | Free tier limits alcanzados | Media | Medio | Monitoreo uso + plan migración | CTO |
| **RT7** | Pérdida de datos (sin backup) | Baja | Crítico | PITR Supabase + tests restore mensuales | CTO |

### 10.2 Riesgos de Producto

| ID | Riesgo | Probabilidad | Impacto | Mitigación | Owner |
|----|--------|--------------|---------|------------|-------|
| **RP1** | No conseguir primeros 3 pilotos | Media | Crítico | Red profesional + outreach agresivo | CEO |
| **RP2** | Pilots no ven valor (churn) | Media | Alto | Onboarding hands-on + feedback semanal | CEO/PM |
| **RP3** | Feature set insuficiente para venta | Media | Alto | User interviews + iteración rápida | PM |
| **RP4** | Pricing incorrecto (muy alto/bajo) | Media | Medio | Benchmarking + tests A/B | CEO |
| **RP5** | UX confusa para usuarios no técnicos | Media | Medio | User testing + iteración UI | Designer |

### 10.3 Riesgos de Mercado

| ID | Riesgo | Probabilidad | Impacto | Mitigación | Owner |
|----|--------|--------------|---------|------------|-------|
| **RM1** | Competidor lanza producto similar | Media | Alto | Foco nicho España + velocidad ejecución | CEO |
| **RM2** | Mercado no adopta IA (desconfianza) | Baja | Crítico | Educación mercado + transparencia IA | CEO/Marketing |
| **RM3** | Regulación GDPR bloquea uso IA | Baja | Alto | DPA Anthropic + abogado privacy + EU hosting | Legal |
| **RM4** | Crisis construcción reduce demanda | Baja | Alto | Diversificar sectores (ingeniería, industria) | CEO |

---

## 11. Plan de Testing

### 11.1 Estrategia de Testing

```
┌─────────────────────────────────────────────────────┐
│               PIRÁMIDE DE TESTING                   │
├─────────────────────────────────────────────────────┤
│                    E2E (5%)                         │
│           User flows críticos completos             │
│                                                     │
│              Integration Tests (15%)                │
│        API + DB + AI Service + Storage              │
│                                                     │
│               Unit Tests (80%)                      │
│   Services, Utils, Parsers, Validators             │
└─────────────────────────────────────────────────────┘
```

### 11.2 Tests por Capa

#### Unit Tests (Target: >80% coverage)

```python
# apps/api/tests/unit/
├── test_anonymizer.py
├── test_parsers.py
├── test_coherence_rules.py
├── test_scorer.py
├── test_cost_controller.py
└── test_validators.py
```

**Ejemplos:**
```python
def test_pdf_parser_extracts_text()
def test_anonymizer_replaces_pii()
def test_coherence_rule_detects_date_mismatch()
def test_scorer_calculates_correctly()
def test_cost_controller_blocks_over_budget()
```

#### Integration Tests (Target: >60% coverage)

```python
# apps/api/tests/integration/
├── test_upload_flow.py
├── test_analysis_flow.py
├── test_auth_flow.py
└── test_rls_isolation.py
```

**Ejemplos:**
```python
async def test_upload_document_flow():
    """Upload → Parse → Store → DB"""

async def test_analysis_flow():
    """Upload 3 docs → Run analysis → Get alerts"""

async def test_rls_isolation():
    """Tenant A cannot access Tenant B data"""
```

#### E2E Tests (Critical User Flows)

```python
# apps/web/tests/e2e/ (Playwright)
├── test_signup_flow.spec.ts
├── test_create_project_flow.spec.ts
└── test_analysis_flow.spec.ts
```

**Ejemplos:**
```typescript
test('user can signup and create project', async ({ page }) => {
  // Signup → Login → Create project → Upload docs
})

test('user can run analysis and see alerts', async ({ page }) => {
  // Create project → Upload 3 docs → Run analysis → See alerts
})
```

### 11.3 Testing en CI/CD

```yaml
# .github/workflows/api-ci.yml
name: API CI/CD

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run unit tests
        run: pytest tests/unit --cov --cov-report=xml
      - name: Run integration tests
        run: pytest tests/integration
      - name: Security scan
        run: bandit -r apps/api/src
      - name: Check coverage >80%
        run: coverage report --fail-under=80

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Railway
        run: railway up
```

---

## 12. Plan de Deployment

### 12.1 Entornos

| Entorno | Propósito | URL | Deploy |
|---------|-----------|-----|--------|
| **Development** | Desarrollo local | localhost | Manual |
| **Staging** | Testing pre-producción | staging.c2pro.app | Auto (push to `main`) |
| **Production** | Usuarios reales | app.c2pro.app | Manual (tag release) |

### 12.2 Deployment Checklist

#### Pre-Deployment

- [ ] Todos los tests pasan (unit + integration)
- [ ] Coverage >80% en rutas críticas
- [ ] Security scan sin vulnerabilidades high/critical
- [ ] Code review aprobado (si aplica)
- [ ] Changelog actualizado
- [ ] Versión bumpeada (semver)

#### Deployment

- [ ] Backup manual BD antes de deploy (producción)
- [ ] Variables de entorno verificadas
- [ ] Deploy backend (Railway)
- [ ] Smoke tests backend (health check)
- [ ] Deploy frontend (Vercel)
- [ ] Smoke tests frontend (login + dashboard)

#### Post-Deployment

- [ ] Verificar Sentry (no errores nuevos)
- [ ] Verificar UptimeRobot (uptime OK)
- [ ] Verificar logs (no errores críticos)
- [ ] Comunicar release a usuarios (si cambios mayores)
- [ ] Monitorear 1h post-deploy

### 12.3 Rollback Plan

**Si algo falla post-deployment:**

1. **Backend (Railway):**
   - Revertir a deployment anterior desde Railway dashboard
   - Tiempo estimado: <2 min

2. **Frontend (Vercel):**
   - Revertir a deployment anterior desde Vercel dashboard
   - Tiempo estimado: <1 min

3. **Base de Datos (Supabase):**
   - Restaurar backup PITR a timestamp pre-deploy
   - Tiempo estimado: ~10-15 min
   - **NOTA:** Solo si cambios de schema rompieron algo crítico

### 12.4 Estrategia de Releases

**MVP (Semanas 1-12):** Continuous deployment a staging, manual a producción

**Post-MVP:**
- **Hotfixes:** Deploy inmediato a producción (bugs críticos)
- **Features:** Deploy quincenal a producción (viernes tarde)
- **Breaking changes:** Comunicar con 1 semana anticipación

---

## 13. Anexos

### 13.1 Glosario Técnico

| Término | Definición |
|---------|------------|
| **WBS** | Work Breakdown Structure - Estructura de desglose del trabajo que organiza el proyecto en fases, entregables y paquetes de trabajo jerárquicos. Vincula actividades del cronograma con partidas presupuestarias. |
| **BOM** | Bill of Materials - Lista de materiales necesarios para el proyecto. Incluye cantidades, precios, lead times, fechas óptimas de pedido, Incoterms, tránsitos y vinculación con WBS items. |
| **Incoterm** | International Commercial Terms - Términos estandarizados que definen responsabilidades entre comprador y vendedor en transacciones internacionales. Afectan quién paga flete, seguro y aduanas. Ejemplos: EXW, FOB, CIF, DAP, DDP. |
| **EXW** | Ex Works - Vendedor entrega en su fábrica. Comprador asume todos los costes de transporte, seguro y aduanas. |
| **FOB** | Free On Board - Vendedor entrega en puerto de origen. Comprador paga flete marítimo, seguro y aduanas desde allí. |
| **CIF** | Cost, Insurance and Freight - Vendedor paga flete y seguro hasta puerto destino. Comprador paga aduanas en destino. |
| **DAP** | Delivered At Place - Vendedor entrega en lugar acordado en destino. Comprador paga aduanas. |
| **DDP** | Delivered Duty Paid - Vendedor entrega en destino con todos los costes incluidos (flete, seguro, aduanas). Precio todo incluido. |
| **Landed Cost** | Coste total desembarcado - Coste real final de un material incluyendo precio base + flete + seguro + aranceles aduaneros. Varía según Incoterm. |
| **Transit Time** | Tiempo de tránsito - Duración del transporte desde origen hasta destino. Varía según modo (marítimo: 30-45d China-Europa, aéreo: 3-7d, terrestre: variable). |
| **BOM Revision** | Revisión del BOM - Nueva versión del Bill of Materials cuando hay cambios (precios, proveedores, plazos, scope). Permite tracking de desviaciones vs baseline. |
| **RLS** | Row Level Security - Mecanismo PostgreSQL para filtrar filas por usuario |
| **Multi-tenancy** | Arquitectura donde múltiples clientes comparten infraestructura con datos aislados |
| **PII** | Personally Identifiable Information - Datos que identifican a una persona |
| **Coherence Score** | Indicador 0-100 que mide alineación entre contrato, cronograma, presupuesto, WBS y BOM |
| **BC3** | Formato estándar español (FIEBDC) para presupuestos de construcción |
| **PITR** | Point-in-Time Recovery - Restaurar BD a timestamp específico |
| **RFQ** | Request for Quotation - Solicitud de oferta a proveedores, generada automáticamente a partir de BOM items |
| **SPI** | Schedule Performance Index - Métrica de cumplimiento de cronograma |
| **CPI** | Cost Performance Index - Métrica de cumplimiento de presupuesto |
| **Lead Time** | Tiempo de entrega total = Tiempo producción + Tiempo tránsito + Tiempo aduanas + Buffer de seguridad |
| **Critical Path** | Ruta crítica - Secuencia de actividades que determina la duración mínima del proyecto. Retrasos en actividades de la ruta crítica retrasan todo el proyecto. |

### 13.2 Stack Decisions (ADRs)

**ADR-001: Por qué FastAPI vs Flask/Django**
- Async nativo (mejor para AI API calls)
- Pydantic v2 built-in (validación automática)
- OpenAPI automático (documentación gratis)
- Mejor DX para API-first app

**ADR-002: Por qué Supabase vs AWS RDS**
- RLS nativo (crítico para multi-tenancy)
- Auth incluido (ahorra desarrollo)
- Backups automáticos + PITR
- Free tier generoso (MVP costo $0)

**ADR-003: Por qué Claude vs GPT-4**
- Mejor calidad en documentos largos (200K context)
- Menos alucinaciones en extracción estructurada
- Pricing competitivo (Sonnet $3/1M vs GPT-4 $30/1M)
- Haiku para tasks simples (ahorro >50%)

**ADR-004: Por qué Cloudflare R2 vs AWS S3**
- Sin egress fees (S3 cobra $0.09/GB)
- S3-compatible (fácil migración futura)
- Free tier 10GB/mes

### 13.3 Referencias

- [Anthropic Claude API Docs](https://docs.anthropic.com)
- [Supabase Documentation](https://supabase.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Next.js Documentation](https://nextjs.org/docs)
- [FIEBDC-3 (BC3) Specification](https://www.fiebdc.es)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [GDPR Compliance Checklist](https://gdpr.eu/checklist/)

### 13.4 Change Log

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 15/12/2024 | Documento inicial (básico) |
| 2.0.0 | 29/12/2024 | Reescritura completa: stack técnico, fases detalladas, métricas, riesgos, testing, deployment |
| 2.1.0 | 29/12/2024 | **CRÍTICO:** Añadido WBS (Work Breakdown Structure) y BOM (Bill of Materials) como prerequisitos fundamentales para Plan de Compras y RFQs. Incluye: modelo de datos completo (wbs_items, bom_items), generadores automáticos, 8 nuevas reglas de coherencia (R11-R18), diagrama de flujo WBS→BOM, actualización Fase 2 con dependencias explícitas, tests críticos específicos, glosario actualizado. |
| **2.2.0** | **29/12/2024** | **CRÍTICO - PROCUREMENT COMPLETO:** Sistema de procurement profesional con: <br>**1. Incoterms & Logística Internacional:** BOM items incluyen incoterm (EXW, FOB, CIF, DAP, DDP), origin_country, destination_country, lead times desglosados (production_time, transit_time, customs_clearance, buffer), landed cost calculator (precio + flete + seguro + aranceles según Incoterm). <br>**2. Versionado y Control de Cambios:** Nueva tabla bom_revisions (v0 baseline, v1+ revisiones), tracking completo de cambios (items_added, items_removed, items_modified, cost_variance), trazabilidad (change_reason, previous_version_id, approved_by). <br>**3. Snapshots y Comparaciones:** Nueva tabla procurement_plan_snapshots (baseline vs revisiones), métricas automáticas (cost_variance, schedule_variance, on_time_deliveries, late_deliveries), comparador de versiones (v0 vs vN). <br>**4. Análisis de Desviaciones:** Dashboard desviaciones planificado vs actual (coste ±%, plazo ±días, landed cost variance), supplier performance tracking (on-time %, cost accuracy, lead time accuracy), lessons learned reports (materiales problemáticos, Incoterms más cost-effective, proveedores confiables). <br>**5. Nuevos Servicios:** BOMVersionManager, DeviationAnalyzer, IncotermCalculator con lógica completa EXW/FOB/CIF/DAP/DDP. <br>**6. Nuevos Endpoints API:** /bom/revisions, /bom/compare, /deviations/cost, /deviations/schedule, /supplier-performance, /lessons-learned, /snapshots. <br>**7. Diagrama Flujo Actualizado:** Incluye generación baseline → ejecución → control cambios → comparación versiones → dashboard desviaciones. <br>**8. Glosario Ampliado:** 11 nuevos términos (Incoterms EXW/FOB/CIF/DAP/DDP, Landed Cost, Transit Time, BOM Revision). |

---

<div align="center">

**— FIN DEL ROADMAP —**

*C2Pro - Contract Intelligence Platform*
*© 2024-2025 Todos los derechos reservados*

**Este documento es la biblia del PM y desarrollo.**
**Cualquier decisión significativa debe ser reflejada aquí.**

</div>
