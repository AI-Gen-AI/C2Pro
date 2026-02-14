# C2Pro Product Roadmap
**Contract Intelligence Platform - Master Development Plan**

**Versión:** 2.3.0
**Última actualización:** 03 de Enero de 2026
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

## Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 15/12/2024 | Documento inicial (básico) |
| 2.0.0 | 29/12/2024 | Reescritura completa: stack técnico, fases detalladas, métricas, riesgos, testing, deployment |
| 2.1.0 | 29/12/2024 | **CRÍTICO:** Añadido WBS (Work Breakdown Structure) y BOM (Bill of Materials) como prerequisitos fundamentales para Plan de Compras y RFQs. Incluye: modelo de datos completo (wbs_items, bom_items), generadores automáticos, 8 nuevas reglas de coherencia (R11-R18), diagrama de flujo WBS→BOM, actualización Fase 2 con dependencias explícitas, tests críticos específicos, glosario actualizado. |
| 2.2.0 | 29/12/2024 | **CRÍTICO - PROCUREMENT COMPLETO:** Sistema de procurement profesional con Incoterms & Logística Internacional, Versionado y Control de Cambios, Snapshots y Comparaciones, Análisis de Desviaciones. Nuevos servicios: BOMVersionManager, DeviationAnalyzer, IncotermCalculator. |
| **2.3.0** | **03/01/2026** | **ACTUALIZACIÓN TECNOLÓGICA 2025:** <br>**1. Stakeholder Intelligence Module:** Extracción automática de stakeholders desde contratos (NLP), clasificación poder/interés, generación RACI desde WBS, alertas contextuales por tipo de stakeholder. Nuevas tablas: stakeholders, stakeholder_wbs_raci, stakeholder_alerts. <br>**2. Model Context Protocol (MCP):** Integración del estándar abierto de Anthropic para conexión de agentes. MCP Servers para filesystem, database, SAP, Primavera. <br>**3. Graph RAG Architecture:** Knowledge graphs para relaciones Contract→WBS→BOM→Stakeholder. Mejora 6.4 puntos en multi-hop reasoning vs RAG básico. Nueva tabla: knowledge_graph_edges. <br>**4. Multi-Agent Architecture:** 9 agentes especializados (ContractParser, WBSGenerator, BOMBuilder, CoherenceChecker, StakeholderExtractor, RFQDrafter, AlertRouter, RACIGenerator, ExpeditingVision) orquestados via LangGraph. <br>**5. Advanced RAG 2025:** Self-RAG, Corrective RAG, Multimodal RAG para expediting con fotos. <br>**6. Competitive Positioning:** Análisis de 17 competidores, diferenciación como "cognitive operating system for EPC procurement". <br>**7. Nuevas Reglas de Coherencia:** R19-R20 para stakeholders. |

---

## 1. Visión y Propuesta de Valor

### 1.1 Visión

> **"Hacer de C2Pro el sistema operativo cognitivo que toda empresa de construcción EPC necesita para conectar contrato, ingeniería y ejecución en un flujo unificado."**

Empoderar a empresas de construcción, ingeniería e industria con orquestación cognitiva automática que conecta el contrato legal con la ejecución física, detectando incoherencias antes de que se conviertan en sobrecostes.

### 1.2 El Problema

El **15-30% de los sobrecostes** en proyectos de construcción e ingeniería se deben a la desconexión sistémica entre dominios críticos:

- ❌ **Contrato (Legal)** → Cláusulas, plazos, penalizaciones, stakeholders
- ❌ **Ingeniería (Técnico)** → WBS, especificaciones, alcance
- ❌ **Cronograma (Temporal)** → Actividades, hitos, dependencias
- ❌ **Presupuesto (Económico)** → Partidas, mediciones, precios
- ❌ **Compras (Supply Chain)** → BOM, proveedores, lead times

**Consecuencias:**
- Penalizaciones por incumplimiento de plazos contractuales
- Sobrecostes por partidas no alineadas con el contrato
- Pérdida de oportunidades de revisión de precios
- Falta de trazabilidad entre documentos clave
- Riesgos no identificados hasta que es tarde
- Stakeholders críticos no informados a tiempo

### 1.3 Propuesta de Valor Única

> **"C2Pro es el único sistema que conecta automáticamente CONTRATO LEGAL con EJECUCIÓN FÍSICA a través de INGENIERÍA y COMPRAS como sistema cognitivo unificado."**

| Diferenciador | Beneficio Cuantificable |
|---------------|-------------------------|
| **Auditoría Tridimensional Automática** | Detecta incoherencias en minutos (ahorro 8-16h/proyecto) |
| **IA Especializada en EPC** | Entiende cláusulas, WBS, BOM del sector |
| **Coherence Score 0-100** | Indicador único que cuantifica el riesgo |
| **Stakeholder Intelligence** | Identifica y mapea stakeholders automáticamente |
| **Graph RAG para Trazabilidad** | Conecta Contract→WBS→BOM→Stakeholder |
| **De Auditoría a Copiloto** | Genera Planes de Compras y RFQs optimizados |
| **Closed-Loop Control** | Seguimiento planificado vs real con alertas predictivas |

### 1.4 Posicionamiento Competitivo

**C2Pro vs Competencia (17 empresas analizadas):**

| Categoría | Competidores | Lo que hacen | Lo que C2Pro hace diferente |
|-----------|--------------|--------------|----------------------------|
| **Sourcing/Optimization** | Keelvar, GEP, Fairmarkit | Análisis de ofertas, auctions | + WBS/BOM desde contrato, dimensión temporal |
| **Contract Management** | Icertis, Ironclad, Agiloft | CLM, templates, compliance | + Coherencia back-to-back, SOW/SLA generativos |
| **PO Automation** | Zip, Coupa, Procurify | Workflows, aprobaciones | + Trazabilidad legal completa, alertas contextuales |
| **Decision Intelligence** | Aera, o9, Pactum | Predictive, negotiation | + Específico EPC, closed-loop con evidencia visual |

**Gaps que NINGÚN competidor cubre:**
- ✅ Generación WBS/BOM desde texto contractual
- ✅ Coherencia back-to-back (Contract→SOW→SLA) con trazabilidad legal
- ✅ MRP Cognitivo alineado a cronograma de proyecto
- ✅ Algoritmo Tripolar con dimensión temporal vs MRP
- ✅ Closed-loop con validación visual (Computer Vision)
- ✅ Inferencia de necesidades implícitas de stakeholders
- ✅ Gestión dinámica P×I basada en comportamiento de proveedor

### 1.5 Mercado Objetivo

| Segmento | Características |
|----------|-----------------|
| **Primario (MVP)** | Empresas medianas (50-250 empleados), facturación 15-100M€, proyectos >500K€, España y LATAM |
| **Secundario (Fase 2)** | Grandes constructoras (>250 empleados), proyectos >5M€, necesidades de integración ERP |
| **Terciario (Fase 3)** | Estudios de ingeniería, promotores inmobiliarios, consultoras de PM |

---

## 2. Principios Rectores

### 2.1 Principios de Producto

1. **User-Centric:** Cada feature debe resolver un dolor real validado con entrevistas
2. **AI-First, Not AI-Only:** La IA potencia, pero el usuario decide y valida
3. **Actionable Insights:** No solo detectar problemas, proponer soluciones concretas
4. **Nicho Deep, Not Wide:** Dominar EPC antes de expandir a otros sectores
5. **Cognitive Orchestrator:** No ser otro ERP transaccional, ser el sistema que los conecta

### 2.2 Principios Técnicos

1. **Simple, Seguro, Suficiente:** Arquitectura optimizada con capacidad de escalar
2. **Monolito Modular → Multi-Agente:** Empezar simple, evolucionar a agentes especializados
3. **Security by Design:** Multi-tenancy con RLS, anonymization de PII, GDPR-compliant
4. **Cost-Conscious:** Free tiers + serverless hasta tener revenue recurrente
5. **IA como Core:** Claude API con model routing, budget control, cache inteligente y MCP
6. **Graph-First:** Knowledge graphs para relaciones semánticas entre entidades

### 2.3 Principios de Desarrollo

1. **Ship Fast, Learn Faster:** Ciclos de 2 semanas máximo por entregable
2. **Quality Gates:** No pasar de fase sin tests críticos pasando
3. **Document as You Build:** Código autodocumentado + decisiones en ADRs
4. **Progressive Enhancement:** MVP funcional → optimizar → features avanzadas

---

## 3. Stack Tecnológico

### 3.1 Stack Completo

| Capa | Tecnología | Versión | Justificación | Alternativa Considerada |
|------|------------|---------|---------------|-------------------------|
| **Frontend** | Next.js | 14+ | SSR, excelente DX, Vercel deploy | Remix |
| | React | 18+ | Estándar industry, ecosystem | Vue |
| | Tailwind CSS | 3+ | Utility-first, rapid prototyping | CSS Modules |
| | shadcn/ui | latest | Componentes accesibles, customizables | MUI |
| | TypeScript | 5+ | Type safety, mejor DX | JavaScript |
| **Backend** | FastAPI | 0.104+ | Async, Pydantic v2, OpenAPI auto | Flask |
| | Python | 3.11+ | Ecosystem AI/ML, async nativo | Node.js |
| | Pydantic | v2 | Validación automática, serialización | Marshmallow |
| **Database** | PostgreSQL | 15+ | ACID, JSON, Full-text search | MongoDB |
| | Supabase | Managed | RLS nativo, backups, auth incluido | AWS RDS |
| **Cache** | Redis | 7+ | Pub/sub, rate limiting, cache | Memcached |
| | Upstash | Serverless | Pay-per-request, sin mínimo | Redis Cloud |
| **Storage** | Cloudflare R2 | - | S3-compatible, sin egress fees | AWS S3 |
| **IA** | Claude API | Sonnet 4 | Mejor calidad docs largos, 200K ctx | GPT-4 |
| | | Haiku 4 | Fast, barato para clasificación | GPT-3.5 |
| **MCP** | Protocol | 2025-11 | Estándar abierto para integración agentes | Custom APIs |
| **Knowledge Graph** | NetworkX | latest | Graph RAG para relaciones semánticas | Neo4j |
| **Agent Framework** | LangGraph | latest | Orquestación multi-agente | Monolítico |
| **RAG** | Graph RAG | - | Relaciones Contract→WBS→BOM→Stakeholder | Vector RAG básico |
| | Self-RAG | - | Retrieval adaptativo con reflexión | Fixed retrieval |
| | Multimodal RAG | - | Texto + imágenes para expediting | Solo texto |
| **Observability** | Sentry | Free tier | Error tracking, performance | Rollbar |
| | Structlog | latest | Structured logging JSON | Python logging |
| | UptimeRobot | Free tier | Uptime monitoring, alertas | Pingdom |
| **Parsers** | PyMuPDF (fitz) | latest | PDF extraction, rápido | PyPDF2 |
| | openpyxl | latest | Excel read/write | xlrd |
| | pyfiebdc | latest | BC3 parsing (presupuestos) | Custom parser |
| **Deployment** | Vercel | Pro | Frontend, edge functions, CDN | Netlify |
| | Railway | Hobby+ | Backend, PostgreSQL addon | Render |
| **CI/CD** | GitHub Actions | - | Integrado con repo, free tier | GitLab CI |

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
anthropic==0.40.0
tiktoken==0.5.1
langgraph==0.2.0

# Graph & RAG
networkx==3.2.1
sentence-transformers==2.2.2

# MCP Integration
mcp-sdk==1.0.0

# Document Parsing
PyMuPDF==1.23.8
openpyxl==3.1.2
pyfieldbc==1.1.0

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
    "recharts": "^2.10.3",
    "d3": "^7.8.5"
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

### 4.1 Diagrama de Arquitectura Completo (v2.3.0)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE PRESENTACIÓN                                 │
│                  Next.js 14 + Tailwind + shadcn/ui                          │
│                          (Deploy: Vercel)                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Dashboard │  │Projects  │  │ Upload   │  │ Alerts   │  │Stakeholder│      │
│  │  Page    │  │   List   │  │   Page   │  │  Panel   │  │   Map    │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ HTTPS / JWT
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE APLICACIÓN                                   │
│                    FastAPI + Pydantic v2 (Railway)                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐                │
│  │    Auth    │ │  Projects  │ │ Documents  │ │  Analysis  │                │
│  │ Middleware │ │   Router   │ │   Router   │ │   Router   │                │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                               │
│  │Stakeholder │ │Procurement │ │    MCP     │                               │
│  │   Router   │ │   Router   │ │  Gateway   │                               │
│  └────────────┘ └────────────┘ └────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CAPA DE AGENTES (Multi-Agent via MCP)                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Contract     │ │    WBS       │ │    BOM       │ │  Coherence   │        │
│  │ Parser Agent │ │Generator Agent│ │Builder Agent │ │Checker Agent │        │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Stakeholder  │ │    RFQ       │ │    Alert     │ │  Expediting  │        │
│  │Extractor Agent│ │Drafter Agent │ │ Router Agent │ │ Vision Agent │        │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE SERVICIOS                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  Parser  │ │Anonymizer│ │Graph RAG │ │Coherence │ │Stakeholder│          │
│  │ Service  │ │ Service  │ │ Service  │ │  Engine  │ │ Service  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │   BOM    │ │   RACI   │ │  Alert   │ │Incoterm  │                       │
│  │ Version  │ │Generator │ │  Router  │ │Calculator│                       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
          │              │                │              │
          ▼              ▼                ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
    │PostgreSQL│  │  Redis   │  │    R2    │  │  Claude API  │
    │(Supabase)│  │(Upstash) │  │(Cloudflr)│  │  (Anthropic) │
    │          │  │          │  │          │  │              │
    │ - RLS    │  │ - Cache  │  │- Docs    │  │- Sonnet 4    │
    │ - Auth   │  │ - Rate   │  │- Files   │  │- Haiku 4     │
    │ - PITR   │  │   Limit  │  │- Images  │  │- MCP Support │
    │ - Graphs │  │ - Pub/Sub│  │          │  │              │
    └──────────┘  └──────────┘  └──────────┘  └──────────────┘

    ┌──────────────────────────────────────────────────────────────┐
    │                  MCP SERVERS (Integrations)                   │
    │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │
    │  │Filesystem│ │Database │ │   SAP   │ │Primavera│            │
    │  │ Server  │ │ Server  │ │ Server  │ │ Server  │            │
    │  └─────────┘ └─────────┘ └─────────┘ └─────────┘            │
    └──────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────────┐
    │               OBSERVABILIDAD & MONITOREO                     │
    │  Sentry (Errors) | Structlog (Logs) | UptimeRobot (Uptime)  │
    └──────────────────────────────────────────────────────────────┘
```

### 4.2 Flujo de Datos - Análisis de Coherencia con Graph RAG

```
[Usuario] → Upload Docs (Contract, Schedule, Budget, Org Chart)
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
    │               [AI Service] → Claude API (extract all entities)
    │                    │
    │    ┌───────────────┼───────────────┐
    │    ▼               ▼               ▼
    │ [Clauses]    [Activities]    [Stakeholders]
    │    │               │               │
    │    └───────────────┼───────────────┘
    │                    ▼
    │         ┌──────────────────┐
    │         │   KNOWLEDGE      │
    │         │     GRAPH        │ ← Graph RAG
    │         │                  │
    │         │ Contract ──→ WBS │
    │         │    ↓         ↓   │
    │         │ Stakeholder←→BOM │
    │         └────────┬─────────┘
    │                  │
    │                  ▼
    │         [Graph RAG Queries] → Multi-hop reasoning
    │                  │
    └─────────┬────────┘
              ▼
         [Coherence Engine] → Cruza entidades via grafo
              │
              ▼
         [Alert Generator] → Genera alertas + stakeholder routing
              │
              ▼
         [RACI Generator] → Mapea stakeholders a WBS
              │
              ▼
         [Scoring Engine] → Calcula Coherence Score (0-100)
              │
              ▼
         [PostgreSQL] → Guarda Analysis + Alerts + Graph
              │
              ▼
         [Frontend] ← GET /api/analysis/{id}
              │
              ▼
         [Usuario] → Ve dashboard con alertas, score, stakeholder map
```

### 4.3 Modelo de Datos Completo (v2.3.0)

```sql
-- =====================================================
-- TENANTS (Multi-tenancy)
-- =====================================================
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

-- =====================================================
-- USERS
-- =====================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- PROJECTS
-- =====================================================
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'draft',
    coherence_score INTEGER CHECK (coherence_score BETWEEN 0 AND 100),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- DOCUMENTS
-- =====================================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_format VARCHAR(10),
    storage_url TEXT NOT NULL,
    file_size_bytes BIGINT,
    upload_status VARCHAR(50) DEFAULT 'uploaded',
    parsed_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- EXTRACTIONS (Datos extraídos por IA)
-- =====================================================
CREATE TABLE extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extraction_type VARCHAR(50),
    data_json JSONB NOT NULL,
    confidence_score NUMERIC(3,2),
    model_version VARCHAR(50),
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- ANALYSES
-- =====================================================
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) DEFAULT 'coherence',
    status VARCHAR(50) DEFAULT 'pending',
    result_json JSONB,
    coherence_score INTEGER CHECK (coherence_score BETWEEN 0 AND 100),
    alerts_count INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- ALERTS
-- =====================================================
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id) ON DELETE CASCADE,
    severity VARCHAR(20) NOT NULL,
    type VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    affected_documents JSONB,
    suggested_action TEXT,
    status VARCHAR(50) DEFAULT 'open',
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- AI_USAGE_LOGS
-- =====================================================
CREATE TABLE ai_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id),
    model VARCHAR(50),
    operation VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- WBS (Work Breakdown Structure)
-- =====================================================
CREATE TABLE wbs_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES wbs_items(id),
    code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    level INTEGER NOT NULL,
    type VARCHAR(50),
    schedule_activity_ids JSONB,
    budget_item_ids JSONB,
    responsible VARCHAR(255),
    estimated_duration_days INTEGER,
    estimated_cost NUMERIC(12,2),
    is_critical_path BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, code)
);

-- =====================================================
-- BOM (Bill of Materials) - Con Incoterms y Versionado
-- =====================================================
CREATE TABLE bom_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    wbs_item_id UUID REFERENCES wbs_items(id),
    parent_bom_id UUID REFERENCES bom_items(id),
    version_number INTEGER DEFAULT 0,
    version_status VARCHAR(50) DEFAULT 'current',

    -- Identificación
    item_code VARCHAR(100),
    item_name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    subcategory VARCHAR(100),

    -- Cantidades y Precios
    unit VARCHAR(50),
    quantity NUMERIC(12,3) NOT NULL,
    unit_price NUMERIC(12,2),
    total_price NUMERIC(12,2),

    -- Proveedor y Logística Internacional
    supplier VARCHAR(255),
    origin_country VARCHAR(100),
    destination_country VARCHAR(100),
    incoterm VARCHAR(20),

    -- Lead Times Desglosados
    production_time_days INTEGER,
    transit_time_days INTEGER,
    customs_clearance_days INTEGER DEFAULT 0,
    buffer_days INTEGER DEFAULT 7,
    total_lead_time_days INTEGER,

    -- Fechas
    optimal_order_date DATE,
    actual_order_date DATE,
    estimated_arrival_date DATE,
    actual_arrival_date DATE,
    required_on_site_date DATE,

    -- Estado y Tracking
    status VARCHAR(50) DEFAULT 'planned',
    tracking_number VARCHAR(255),
    critical_for_milestone VARCHAR(255),

    -- Costes Adicionales (Incoterm)
    freight_cost NUMERIC(12,2),
    customs_duties NUMERIC(12,2),
    insurance_cost NUMERIC(12,2),
    total_landed_cost NUMERIC(12,2),

    -- Referencias
    budget_item_id UUID,
    contract_clause_ref VARCHAR(255),
    specifications JSONB,

    -- Auditoría de Cambios
    change_reason TEXT,
    previous_version_id UUID REFERENCES bom_items(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para BOM
CREATE INDEX idx_bom_project_version ON bom_items(project_id, version_number);
CREATE INDEX idx_bom_status ON bom_items(status);
CREATE INDEX idx_bom_optimal_date ON bom_items(optimal_order_date);

-- =====================================================
-- BOM_REVISIONS - Historial de Cambios
-- =====================================================
CREATE TABLE bom_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    revision_name VARCHAR(100),
    revision_type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'draft',

    -- Métricas
    total_items_count INTEGER,
    items_added INTEGER DEFAULT 0,
    items_removed INTEGER DEFAULT 0,
    items_modified INTEGER DEFAULT 0,
    total_cost_change NUMERIC(12,2),
    total_leadtime_change_days INTEGER,

    -- Razón y Aprobación
    change_summary TEXT,
    change_reason TEXT,
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(project_id, revision_number)
);

-- =====================================================
-- PROCUREMENT_PLAN_SNAPSHOTS
-- =====================================================
CREATE TABLE procurement_plan_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    bom_revision_id UUID REFERENCES bom_revisions(id),
    snapshot_date TIMESTAMPTZ DEFAULT NOW(),
    snapshot_type VARCHAR(50),

    plan_data JSONB NOT NULL,

    total_planned_cost NUMERIC(12,2),
    total_actual_cost NUMERIC(12,2),
    cost_variance NUMERIC(12,2),
    cost_variance_percentage NUMERIC(5,2),

    on_time_deliveries INTEGER,
    late_deliveries INTEGER,
    pending_deliveries INTEGER,
    avg_delay_days NUMERIC(5,1),

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- STAKEHOLDERS (NUEVO v2.3.0)
-- =====================================================
CREATE TABLE stakeholders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Identificación (extraído por NLP)
    name VARCHAR(255),
    role VARCHAR(100),
    organization VARCHAR(255),
    department VARCHAR(100),
    
    -- Clasificación
    power_level VARCHAR(20) DEFAULT 'medium',
    interest_level VARCHAR(20) DEFAULT 'medium',
    quadrant VARCHAR(50),
    
    -- Contacto
    email VARCHAR(255),
    phone VARCHAR(50),
    
    -- Necesidades implícitas (inferidas por IA)
    implicit_needs JSONB,
    communication_preference VARCHAR(50),
    
    -- Fuente de extracción
    source_document_id UUID REFERENCES documents(id),
    source_clause_ref VARCHAR(255),
    extraction_confidence NUMERIC(3,2),
    
    -- Auditoría
    is_auto_extracted BOOLEAN DEFAULT TRUE,
    manually_verified BOOLEAN DEFAULT FALSE,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para Stakeholders
CREATE INDEX idx_stakeholders_project ON stakeholders(project_id);
CREATE INDEX idx_stakeholders_department ON stakeholders(department);
CREATE INDEX idx_stakeholders_quadrant ON stakeholders(quadrant);

-- =====================================================
-- STAKEHOLDER_WBS_RACI (NUEVO v2.3.0)
-- =====================================================
CREATE TABLE stakeholder_wbs_raci (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stakeholder_id UUID NOT NULL REFERENCES stakeholders(id) ON DELETE CASCADE,
    wbs_item_id UUID NOT NULL REFERENCES wbs_items(id) ON DELETE CASCADE,
    
    raci_role VARCHAR(20) NOT NULL,
    approval_threshold NUMERIC(12,2),
    
    is_auto_generated BOOLEAN DEFAULT TRUE,
    override_reason TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stakeholder_id, wbs_item_id, raci_role)
);

-- =====================================================
-- STAKEHOLDER_ALERTS (NUEVO v2.3.0)
-- =====================================================
CREATE TABLE stakeholder_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stakeholder_id UUID NOT NULL REFERENCES stakeholders(id) ON DELETE CASCADE,
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    
    relevance_score NUMERIC(3,2),
    notification_status VARCHAR(50) DEFAULT 'pending',
    sent_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- KNOWLEDGE_GRAPH_EDGES (NUEVO v2.3.0)
-- =====================================================
CREATE TABLE knowledge_graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    source_type VARCHAR(50) NOT NULL,
    source_id UUID NOT NULL,
    
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    
    relationship_type VARCHAR(100) NOT NULL,
    properties JSONB DEFAULT '{}',
    confidence NUMERIC(3,2) DEFAULT 1.0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(project_id, source_type, source_id, target_type, target_id, relationship_type)
);

-- Índices para Knowledge Graph
CREATE INDEX idx_kg_project ON knowledge_graph_edges(project_id);
CREATE INDEX idx_kg_source ON knowledge_graph_edges(source_type, source_id);
CREATE INDEX idx_kg_target ON knowledge_graph_edges(target_type, target_id);
CREATE INDEX idx_kg_relationship ON knowledge_graph_edges(relationship_type);

-- =====================================================
-- Row Level Security (RLS) Policies
-- =====================================================
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

ALTER TABLE stakeholders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_stakeholders ON stakeholders
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects WHERE tenant_id = auth.jwt() ->> 'tenant_id'
        )
    );

ALTER TABLE stakeholder_wbs_raci ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_raci ON stakeholder_wbs_raci
    FOR ALL USING (
        stakeholder_id IN (
            SELECT s.id FROM stakeholders s
            JOIN projects p ON s.project_id = p.id
            WHERE p.tenant_id = auth.jwt() ->> 'tenant_id'
        )
    );

ALTER TABLE knowledge_graph_edges ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_kg ON knowledge_graph_edges
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects WHERE tenant_id = auth.jwt() ->> 'tenant_id'
        )
    );
```

### 4.4 Arquitectura Multi-Agente con MCP (NUEVO v2.3.0)

#### 4.4.1 Agentes Especializados

| Agente | Responsabilidad | Input | Output | Modelo |
|--------|----------------|-------|--------|--------|
| **ContractParserAgent** | Extrae cláusulas, hitos, penalizaciones | PDF contrato | JSON estructurado | Sonnet 4 |
| **StakeholderExtractorAgent** | Identifica stakeholders y roles | PDF contrato + orgchart | Lista stakeholders | Sonnet 4 |
| **WBSGeneratorAgent** | Genera estructura de desglose | Extracciones + schedule | WBS jerárquico | Sonnet 4 |
| **BOMBuilderAgent** | Crea lista de materiales | WBS + budget | BOM con lead times | Sonnet 4 |
| **CoherenceCheckerAgent** | Detecta incoherencias | Knowledge Graph | Alertas + Score | Haiku 4 |
| **RACIGeneratorAgent** | Mapea stakeholders a WBS | Stakeholders + WBS | Matriz RACI | Haiku 4 |
| **RFQDrafterAgent** | Genera solicitudes de oferta | BOM items | Documentos RFQ | Sonnet 4 |
| **AlertRouterAgent** | Rutea alertas a stakeholders | Alertas + RACI | Notificaciones | Haiku 4 |
| **ExpeditingVisionAgent** | Valida avance con fotos | Imágenes + BOM | Status updates | Sonnet 4 Vision |

#### 4.4.2 MCP Server Configuration

```python
# apps/api/src/mcp/servers/

# filesystem_server.py - Acceso a documentos
class FilesystemMCPServer:
    """MCP Server para acceso a documentos del proyecto"""
    
    capabilities = ["read_file", "list_files", "search_content"]
    
    async def read_file(self, file_path: str) -> FileContent:
        """Lee contenido de documento"""
    
    async def list_files(self, project_id: UUID) -> list[FileMetadata]:
        """Lista documentos del proyecto"""
    
    async def search_content(self, query: str, project_id: UUID) -> list[SearchResult]:
        """Búsqueda semántica en documentos"""

# database_server.py - Queries PostgreSQL
class DatabaseMCPServer:
    """MCP Server para acceso a base de datos"""
    
    capabilities = ["query", "get_entity", "get_relationships"]
    
    async def query(self, sql: str, params: dict) -> QueryResult:
        """Ejecuta query seguro (solo SELECT)"""
    
    async def get_entity(self, entity_type: str, entity_id: UUID) -> Entity:
        """Obtiene entidad por tipo e ID"""
    
    async def get_relationships(self, entity_type: str, entity_id: UUID) -> list[Relationship]:
        """Obtiene relaciones de entidad en Knowledge Graph"""

# erp_server.py - SAP/Oracle (Fase 2+)
class ERPMCPServer:
    """MCP Server para integración con ERPs"""
    
    capabilities = ["get_purchase_orders", "get_suppliers", "create_requisition"]
    
    async def get_purchase_orders(self, project_code: str) -> list[PurchaseOrder]:
        """Obtiene órdenes de compra de SAP/Oracle"""
    
    async def get_suppliers(self, category: str) -> list[Supplier]:
        """Obtiene proveedores homologados"""
    
    async def create_requisition(self, bom_item_id: UUID) -> Requisition:
        """Crea solicitud de compra en ERP"""

# primavera_server.py - P6 integration (Fase 3)
class PrimaveraMCPServer:
    """MCP Server para integración con Primavera P6"""
    
    capabilities = ["get_schedule", "get_activities", "update_progress"]
    
    async def get_schedule(self, project_code: str) -> Schedule:
        """Obtiene cronograma de Primavera"""
    
    async def get_activities(self, wbs_code: str) -> list[Activity]:
        """Obtiene actividades por WBS"""
    
    async def update_progress(self, activity_id: str, progress: float) -> bool:
        """Actualiza avance en Primavera"""
```

#### 4.4.3 Flujo Multi-Agente

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORQUESTADOR PRINCIPAL                         │
│                   (LangGraph State Machine)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  CONTRACT   │    │ STAKEHOLDER │    │  SCHEDULE   │
    │   PARSER    │    │  EXTRACTOR  │    │   PARSER    │
    │   AGENT     │    │    AGENT    │    │    AGENT    │
    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
           │                  │                  │
           │     MCP: Filesystem Server          │
           │          Database Server            │
           │                  │                  │
           └──────────────────┼──────────────────┘
                              ▼
                    ┌─────────────────┐
                    │  KNOWLEDGE      │
                    │    GRAPH        │
                    │   BUILDER       │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌───────────┐  ┌───────────┐  ┌───────────┐
       │    WBS    │  │    BOM    │  │   RACI    │
       │ GENERATOR │  │  BUILDER  │  │ GENERATOR │
       │   AGENT   │  │   AGENT   │  │   AGENT   │
       └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                  ┌─────────────────┐
                  │   COHERENCE     │
                  │    CHECKER      │
                  │     AGENT       │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │     ALERT       │
                  │    ROUTER       │
                  │     AGENT       │
                  └─────────────────┘
```

### 4.5 Stakeholder Intelligence Module (NUEVO v2.3.0)

#### 4.5.1 Servicios de Stakeholder

```python
# apps/api/src/services/stakeholder/

# extractor.py
class StakeholderExtractor:
    """Extrae stakeholders de documentos contractuales usando NLP"""
    
    async def extract_from_contract(
        self, 
        document_id: UUID
    ) -> list[Stakeholder]:
        """
        Usa Claude para identificar:
        - Nombres de personas con roles
        - Departamentos/áreas (HSE, Calidad, Legal, Finance, Engineering)
        - Organizaciones (Cliente, Subcontratistas, Autoridades)
        - Referencias en cláusulas específicas
        """
        
    async def extract_from_orgchart(
        self,
        document_id: UUID
    ) -> list[Stakeholder]:
        """Extrae de organigramas (PDF/imagen) usando vision"""

# classifier.py
class StakeholderClassifier:
    """Clasifica stakeholders por poder e interés"""
    
    QUADRANT_RULES = {
        ("high", "high"): "key_player",      # Manage closely
        ("high", "low"): "keep_satisfied",    # Keep satisfied
        ("low", "high"): "keep_informed",     # Keep informed
        ("low", "low"): "monitor"             # Monitor
    }
    
    async def classify(
        self,
        stakeholder: Stakeholder,
        project_context: dict
    ) -> StakeholderClassification:
        """
        Clasifica basándose en:
        - Rol en el contrato (firmante, aprobador, ejecutor)
        - Departamento (HSE tiene alto poder en safety-critical)
        - Frecuencia de mención en documentos
        - Umbrales de aprobación asociados
        """

# raci_generator.py
class RACIGenerator:
    """Genera matriz RACI desde WBS y Stakeholders"""
    
    async def generate_raci(
        self,
        project_id: UUID
    ) -> list[StakeholderWBSRaci]:
        """
        Genera RACI basándose en:
        - Tipo de WBS item (phase, deliverable, work_package)
        - Departamento del stakeholder
        - Umbrales de aprobación
        - Cláusulas contractuales de responsabilidad
        
        Reglas por defecto:
        - Project Manager: Accountable para niveles 1-2
        - Área técnica: Responsible para su especialidad
        - Cliente: Informed para hitos contractuales
        - HSE: Consulted para items safety-critical
        - Quality: Consulted para items quality-critical
        - Finance: Accountable para items > umbral económico
        """

# alert_router.py
class StakeholderAlertRouter:
    """Rutea alertas a stakeholders relevantes"""
    
    ALERT_ROUTING_RULES = {
        "date_mismatch": ["project_manager", "planner"],
        "budget_overrun": ["project_manager", "finance"],
        "safety_risk": ["hse_officer", "project_manager"],
        "quality_deviation": ["quality_manager", "engineering"],
        "supplier_delay": ["procurement", "project_manager"],
        "critical_path_impact": ["project_manager", "client"]
    }
    
    async def route_alert(
        self,
        alert: Alert,
        project_id: UUID
    ) -> list[StakeholderAlert]:
        """
        Rutea alertas basándose en:
        - Tipo de alerta
        - Severidad
        - WBS items afectados
        - RACI del stakeholder
        - Preferencias de comunicación
        """

# implicit_needs.py
class ImplicitNeedsInferrer:
    """Infiere necesidades implícitas de stakeholders"""
    
    async def infer_needs(
        self,
        stakeholder: Stakeholder,
        contract_text: str,
        historical_data: dict
    ) -> dict:
        """
        Infiere usando Claude:
        - Aversión al riesgo (basado en cláusulas de penalización)
        - Prioridad plazo vs coste (basado en milestones vs budget)
        - Preferencia de comunicación (formal vs informal)
        - Áreas de preocupación principal
        """
```

#### 4.5.2 Flujo de Stakeholder Intelligence

```
DOCUMENTOS:
┌─────────────┐  ┌─────────────┐
│  CONTRATO   │  │ ORGANIGRAMA │
└──────┬──────┘  └──────┬──────┘
       │                │
       └────────┬───────┘
                ▼
       ┌────────────────┐
       │  EXTRACTOR NLP │
       │  (Claude API)  │
       └────────┬───────┘
                │
                ▼
       ┌────────────────┐
       │  STAKEHOLDERS  │ ← Lista estructurada
       │  IDENTIFICADOS │
       │                │
       │ • Nombre       │
       │ • Rol          │
       │ • Departamento │
       │ • Organización │
       │ • Fuente       │
       └────────┬───────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
┌─────────────┐  ┌─────────────┐
│ CLASSIFIER  │  │   NEEDS     │
│Poder/Interés│  │  INFERRER   │
│             │  │             │
│ • Key Player│  │ • Risk avers│
│ • Keep Sat. │  │ • Schedule  │
│ • Keep Inf. │  │   priority  │
│ • Monitor   │  │ • Comm pref │
└──────┬──────┘  └──────┬──────┘
       │                │
       └────────┬───────┘
                ▼
       ┌────────────────┐
       │    WBS ITEMS   │
       └────────┬───────┘
                │
                ▼
       ┌────────────────┐
       │ RACI GENERATOR │
       │  (Auto-mapeo)  │
       │                │
       │ R: Responsible │
       │ A: Accountable │
       │ C: Consulted   │
       │ I: Informed    │
       └────────┬───────┘
                │
                ▼
       ┌────────────────┐
       │  MATRIZ RACI   │ ← Por cada WBS item
       │   COMPLETA     │
       └────────┬───────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
┌─────────────┐  ┌─────────────┐
│ STAKEHOLDER │  │    ALERT    │
│     MAP     │  │   ROUTER    │
│  (Visual)   │  │ (Contextual)│
└─────────────┘  └─────────────┘
```

#### 4.5.3 API Endpoints Stakeholder

```python
# apps/api/src/routers/stakeholders.py

@router.post("/projects/{project_id}/stakeholders/extract")
async def extract_stakeholders(project_id: UUID):
    """Extrae stakeholders de documentos del proyecto"""

@router.get("/projects/{project_id}/stakeholders")
async def list_stakeholders(
    project_id: UUID,
    department: str = None,
    quadrant: str = None
):
    """Lista stakeholders con filtros opcionales"""

@router.get("/projects/{project_id}/stakeholders/{stakeholder_id}")
async def get_stakeholder(project_id: UUID, stakeholder_id: UUID):
    """Obtiene detalle de stakeholder"""

@router.put("/projects/{project_id}/stakeholders/{stakeholder_id}")
async def update_stakeholder(
    project_id: UUID,
    stakeholder_id: UUID,
    data: StakeholderUpdate
):
    """Actualiza stakeholder (verificación manual)"""

@router.post("/projects/{project_id}/stakeholders/{stakeholder_id}/verify")
async def verify_stakeholder(
    project_id: UUID,
    stakeholder_id: UUID,
    user: User = Depends(get_current_user)
):
    """Marca stakeholder como verificado manualmente"""

@router.get("/projects/{project_id}/raci")
async def get_raci_matrix(project_id: UUID):
    """Obtiene matriz RACI completa del proyecto"""

@router.post("/projects/{project_id}/raci/generate")
async def generate_raci(project_id: UUID):
    """Genera RACI automáticamente desde WBS y stakeholders"""

@router.put("/projects/{project_id}/raci/{raci_id}")
async def update_raci(
    project_id: UUID,
    raci_id: UUID,
    data: RACIUpdate
):
    """Actualiza asignación RACI manualmente"""

@router.get("/projects/{project_id}/stakeholders/{stakeholder_id}/alerts")
async def get_stakeholder_alerts(
    project_id: UUID,
    stakeholder_id: UUID,
    status: str = None
):
    """Obtiene alertas asignadas a un stakeholder"""

@router.post("/stakeholder-alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: UUID):
    """Marca alerta como reconocida por stakeholder"""
```

### 4.6 Graph RAG Architecture (NUEVO v2.3.0)

#### 4.6.1 Knowledge Graph Service

```python
# apps/api/src/services/graph/knowledge_graph.py

class KnowledgeGraphService:
    """Servicio para gestión del Knowledge Graph del proyecto"""
    
    ENTITY_TYPES = [
        "contract", "clause", "milestone", "penalty",
        "schedule", "activity", "dependency",
        "budget", "budget_item",
        "wbs_item", "bom_item",
        "stakeholder", "organization"
    ]
    
    RELATIONSHIP_TYPES = [
        "CONTAINS",           # Contract CONTAINS Clause
        "REQUIRES",           # Clause REQUIRES Activity
        "DEPENDS_ON",         # Activity DEPENDS_ON Activity
        "FUNDED_BY",          # WBS FUNDED_BY Budget_Item
        "NEEDS_MATERIAL",     # WBS NEEDS_MATERIAL BOM_Item
        "RESPONSIBLE_FOR",    # Stakeholder RESPONSIBLE_FOR WBS
        "ACCOUNTABLE_FOR",    # Stakeholder ACCOUNTABLE_FOR WBS
        "APPROVES",           # Stakeholder APPROVES BOM_Item
        "PENALIZES",          # Penalty PENALIZES Milestone
        "SUPPLIES",           # BOM_Item SUPPLIES WBS
        "REFERENCES",         # Clause REFERENCES Stakeholder
    ]
    
    async def build_graph(self, project_id: UUID) -> KnowledgeGraph:
        """
        Construye knowledge graph del proyecto:
        1. Extrae entidades de todas las extracciones
        2. Identifica relaciones entre entidades
        3. Almacena en knowledge_graph_edges
        4. Construye grafo en memoria (NetworkX)
        """
    
    async def add_edge(
        self,
        project_id: UUID,
        source_type: str,
        source_id: UUID,
        target_type: str,
        target_id: UUID,
        relationship: str,
        properties: dict = None
    ) -> KnowledgeGraphEdge:
        """Añade arista al grafo"""
    
    async def get_neighbors(
        self,
        project_id: UUID,
        entity_type: str,
        entity_id: UUID,
        relationship_types: list[str] = None,
        max_depth: int = 2
    ) -> list[GraphNode]:
        """Obtiene vecinos de una entidad (multi-hop)"""
    
    async def find_path(
        self,
        project_id: UUID,
        source_type: str,
        source_id: UUID,
        target_type: str,
        target_id: UUID
    ) -> list[GraphEdge]:
        """Encuentra camino entre dos entidades"""
    
    async def query_subgraph(
        self,
        project_id: UUID,
        center_type: str,
        center_id: UUID,
        radius: int = 2
    ) -> Subgraph:
        """Extrae subgrafo centrado en una entidad"""
```

#### 4.6.2 Graph RAG Retriever

```python
# apps/api/src/services/graph/graph_rag.py

class GraphRAGRetriever:
    """Retriever que usa Knowledge Graph para contexto enriquecido"""
    
    async def retrieve(
        self,
        query: str,
        project_id: UUID,
        top_k: int = 10
    ) -> list[RetrievalResult]:
        """
        Retrieval mejorado con Graph RAG:
        
        1. Vector search inicial (embedding similarity)
        2. Expansión via Knowledge Graph:
           - Entidades relacionadas (1-hop)
           - Contexto estructural (2-hop para relaciones clave)
        3. Re-ranking basado en relevancia + centralidad en grafo
        """
    
    async def multi_hop_reasoning(
        self,
        question: str,
        project_id: UUID,
        max_hops: int = 3
    ) -> ReasoningResult:
        """
        Razonamiento multi-hop para preguntas complejas:
        
        Ejemplo: "¿Qué stakeholder debe aprobar materiales 
                  críticos para el hito de entrega parcial?"
        
        Proceso:
        1. Identificar "hito de entrega parcial" → Milestone
        2. Encontrar WBS items que afectan ese Milestone
        3. Identificar BOM items críticos para esos WBS
        4. Buscar Stakeholders con RACI "Accountable" para esos WBS
        5. Sintetizar respuesta con trazabilidad completa
        """
```

#### 4.6.3 Visualización del Knowledge Graph

```
                    ┌─────────────┐
                    │  CONTRACT   │
                    │  Principal  │
                    └──────┬──────┘
                           │ CONTAINS
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Clause 1 │    │ Clause 2 │    │ Clause 3 │
    │ Plazos   │    │ Penaliz. │    │ Stakehld │
    └────┬─────┘    └────┬─────┘    └────┬─────┘
         │               │               │
         │ REQUIRES      │ PENALIZES     │ REFERENCES
         ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ WBS 1.1  │    │Milestone │    │Stakeholder│
    │ Fase 1   │    │  Hito 1  │    │  Cliente  │
    └────┬─────┘    └──────────┘    └─────┬────┘
         │                               │
         │ NEEDS_MATERIAL                │ ACCOUNTABLE_FOR
         ▼                               ▼
    ┌──────────┐                   ┌──────────┐
    │ BOM Item │◄──────────────────│ WBS 1.1  │
    │Material A│   APPROVES        │          │
    └────┬─────┘                   └──────────┘
         │
         │ SUPPLIES
         ▼
    ┌──────────┐
    │ WBS 1.2  │
    │ Fase 2   │
    └──────────┘
```

---

## 5. MVP - Fase 1 (12 Semanas)

**Objetivo:** Lanzar MVP funcional con capacidad de auditoría tridimensional automática y extracción básica de stakeholders.

**Target Release:** Semana 12
**Target Users:** 3-5 pilotos (empresas construcción conocidas)

### 5.1 Semanas 1-2: FUNDACIÓN

#### Features

- **F1.1:** Setup inicial del proyecto (monorepo)
- **F1.2:** Configuración de Supabase (PostgreSQL + Auth)
- **F1.3:** Implementación de RLS para multi-tenancy
- **F1.4:** Middleware de autenticación
- **F1.5:** Setup de Sentry para error tracking
- **F1.6:** Configuración de CI/CD básico

#### Entregables Técnicos

```
apps/
├── api/
│   ├── src/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── middleware/
│   │   │   └── auth.py
│   │   ├── database/
│   │   │   ├── client.py
│   │   │   └── schema.sql
│   │   └── routers/
│   │       └── health.py
│   ├── requirements.txt
│   └── Dockerfile
├── web/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── dashboard/
│   │   │       └── page.tsx
│   │   ├── lib/
│   │   │   └── supabase.ts
│   │   └── components/
│   │       └── ui/
│   ├── package.json
│   └── next.config.js
└── .github/
    └── workflows/
        ├── api-ci.yml
        └── web-ci.yml
```

#### Criterios de Aceptación

- [ ] User puede registrarse y hacer login
- [ ] JWT válido permite acceso a endpoints protegidos
- [ ] RLS impide acceso a datos de otros tenants
- [ ] Sentry captura errores correctamente
- [ ] CI/CD pipeline funciona
- [ ] Health check responde 200 OK

### 5.2 Semanas 3-4: DOCUMENTOS

#### Features

- **F2.1:** Upload de archivos a Cloudflare R2
- **F2.2:** Parser de PDF (PyMuPDF)
- **F2.3:** Parser de Excel (openpyxl)
- **F2.4:** Parser de BC3 (FIEBDC)
- **F2.5:** UI de upload con drag & drop
- **F2.6:** Listado de documentos por proyecto

#### Criterios de Aceptación

- [ ] PDF de contrato sube y extrae texto completo
- [ ] Excel de cronograma parsea todas las hojas
- [ ] BC3 de presupuesto parsea capítulos y partidas
- [ ] Archivos se guardan en R2 con estructura correcta
- [ ] UI muestra progress bar durante upload
- [ ] Documentos asociados al proyecto correcto

### 5.3 Semanas 5-6: IA CORE

#### Features

- **F3.1:** Servicio de anonymization (PII)
- **F3.2:** AI Service con Claude API
- **F3.3:** Prompts versionados para extracción
- **F3.4:** Cost controller por tenant
- **F3.5:** Cache de respuestas IA en Redis
- **F3.6:** Model routing (Haiku/Sonnet)

#### Criterios de Aceptación

- [ ] Anonymizer detecta DNI, emails, teléfonos, IBANs
- [ ] Claude extrae cláusulas con >80% accuracy
- [ ] Cost controller bloquea cuando excede budget
- [ ] Cache evita llamadas duplicadas
- [ ] Model router usa Haiku para clasificación simple

### 5.4 Semanas 7-8: COHERENCIA + WBS/BOM + STAKEHOLDERS

#### Features

- **F4.1:** Motor de cruce tridimensional
- **F4.2:** Generador de WBS automático
- **F4.3:** Generador de BOM por WBS item
- **F4.4:** Algoritmo de detección de incoherencias (20+ tipos)
- **F4.5:** Generador de alertas
- **F4.6:** Cálculo de Coherence Score
- **F4.7:** **NUEVO: Extracción básica de stakeholders** (NLP desde contrato)
- **F4.8:** **NUEVO: Clasificación poder/interés** (reglas + sugerencias)

#### Reglas de Coherencia (Actualizado v2.3.0)

| ID | Regla | Documentos | Severidad |
|----|-------|------------|-----------|
| R1 | Plazo ejecución contrato ≠ fecha fin cronograma | Contract + Schedule | Critical |
| R2 | Hito contractual sin actividad en cronograma | Contract + Schedule | High |
| R3 | Partida presupuesto sin respaldo contractual | Contract + Budget | Medium |
| R4 | Penalización > presupuesto partida | Contract + Budget | High |
| R5 | Cronograma excede plazo contractual | Contract + Schedule | Critical |
| R6 | Suma partidas ≠ precio contrato (±5%) | Contract + Budget | Medium |
| R7 | Actividad sin partida presupuestaria | Schedule + Budget | Medium |
| R8 | Hito entrega sin actividades previas | Schedule | Low |
| R9 | Cláusula revisión precios sin partidas | Contract + Budget | Low |
| R10 | Plazo garantía no en cronograma | Contract + Schedule | Medium |
| R11 | WBS item sin actividades vinculadas | WBS + Schedule | High |
| R12 | WBS item sin partidas asignadas | WBS + Budget | High |
| R13 | Material BOM sin lead time | BOM | Medium |
| R14 | Material crítico con fecha pedido tardía | BOM + Schedule | Critical |
| R15 | BOM item sin partida presupuestaria | BOM + Budget | High |
| R16 | Suma costes BOM ≠ suma partidas (±10%) | BOM + Budget | Medium |
| R17 | Material sin especificaciones contractuales | BOM + Contract | Low |
| R18 | WBS critical path ≠ ruta crítica cronograma | WBS + Schedule | High |
| **R19** | **Stakeholder mencionado sin datos de contacto** | Contract | Low |
| **R20** | **Aprobador contractual no identificado** | Contract | Medium |

#### Criterios de Aceptación

- [ ] WBS se genera con 4 niveles de jerarquía
- [ ] WBS items vinculados a actividades del cronograma
- [ ] WBS items tienen partidas presupuestarias asignadas
- [ ] Ruta crítica identificada correctamente
- [ ] BOM generado por cada WBS item con materiales
- [ ] BOM incluye lead times calculados
- [ ] BOM calcula fecha óptima de pedido
- [ ] Motor detecta 20+ tipos de incoherencias
- [ ] Score 100 para proyecto sin incoherencias
- [ ] **NUEVO: Stakeholders extraídos de contrato (nombres, roles, departamentos)**
- [ ] **NUEVO: Stakeholders clasificados en cuadrante poder/interés**

### 5.5 Semanas 9-10: UI/UX

#### Features

- **F5.1:** Dashboard principal con métricas
- **F5.2:** Lista de proyectos con filtros
- **F5.3:** Página de detalle de proyecto
- **F5.4:** Panel de alertas con filtros
- **F5.5:** Export de análisis a PDF
- **F5.6:** Responsive design
- **F5.7:** **NUEVO: Vista de stakeholders identificados**
- **F5.8:** **NUEVO: Matriz poder/interés visual**

#### Criterios de Aceptación

- [ ] Dashboard carga en <2s
- [ ] Gauge de Score con colores (0-60 rojo, 61-80 amarillo, 81-100 verde)
- [ ] Filtros de alertas funcionan
- [ ] Export PDF incluye score, alertas, documentos
- [ ] Responsive funciona en mobile
- [ ] **NUEVO: Lista de stakeholders visible en proyecto**
- [ ] **NUEVO: Matriz poder/interés interactiva**

### 5.6 Semanas 11-12: HARDENING

#### Features

- **F6.1:** Security testing
- **F6.2:** AI accuracy testing con golden dataset
- **F6.3:** Load testing (100 usuarios)
- **F6.4:** Deployment a producción
- **F6.5:** Onboarding de 3-5 pilots

#### Criterios de Aceptación Fase 1 Completa

- [ ] Tests de seguridad pasan al 100%
- [ ] AI accuracy >85% en golden dataset
- [ ] Load test soporta 100 usuarios con <1% error
- [ ] Producción estable (uptime >99%)
- [ ] 3 pilots onboarded
- [ ] Documentación básica creada

---

## 6. Fase 2 - Copiloto de Compras

**Timeline:** Semanas 13-20 (8 semanas)
**Objetivo:** Evolucionar de auditoría pasiva a copiloto activo con RACI, Graph RAG y alertas contextuales.

### 6.1 Features Principales

#### F7: Knowledge Graph y Graph RAG (Semanas 13-14)

**Descripción:** Construir Knowledge Graph que conecte todas las entidades del proyecto.

**Entidades:**
- Contract → Clauses → Milestones → Penalties
- Schedule → Activities → Dependencies
- Budget → Budget Items
- WBS → BOM Items
- Stakeholders → Organizations

**Relaciones:**
- Contract CONTAINS Clause
- Clause REQUIRES Activity
- WBS FUNDED_BY Budget_Item
- Stakeholder RESPONSIBLE_FOR WBS
- BOM_Item SUPPLIES WBS

**Beneficio:** Mejora 6.4 puntos en multi-hop reasoning vs RAG básico.

#### F8: Generación RACI Automática (Semanas 15-16)

**Descripción:** Generar matriz RACI desde WBS y stakeholders.

**Input:**
- WBS items generados
- Stakeholders extraídos y clasificados
- Cláusulas de responsabilidad del contrato
- Umbrales de aprobación

**Output:**
- Matriz RACI completa por WBS item
- Sugerencias de asignación (editable)
- Trazabilidad a cláusula contractual

#### F9: Plan de Compras Inteligente (Semanas 15-16)

**Descripción:** Generar Plan de Compras desde BOM con alertas proactivas.

**Output:**
- Plan ordenado por fecha óptima de pedido
- Agrupación de compras similares
- Priorización de materiales críticos
- Alertas T-30, T-15, T-7 días

#### F10: Generación de RFQs (Semanas 17-18)

**Descripción:** Generar borradores de RFQ desde BOM items.

**Output:**
- Documento RFQ con especificaciones del BOM
- Condiciones contractuales aplicables
- Fecha de entrega requerida
- Criterios de evaluación

#### F11: Alertas Contextuales por Stakeholder (Semanas 17-18)

**Descripción:** Rutear alertas al stakeholder correcto según tipo y RACI.

**Tipos de alertas:**
- Date mismatch → Project Manager, Planner
- Budget overrun → Finance, Project Manager
- Safety risk → HSE Officer
- Quality deviation → Quality Manager
- Supplier delay → Procurement
- Critical path impact → Client

#### F12: MCP Servers Básicos (Semanas 19-20)

**Descripción:** Implementar MCP servers para filesystem y database.

**Servers:**
- Filesystem Server: Acceso a documentos
- Database Server: Queries PostgreSQL
- (Preparación para SAP/Primavera en Fase 3)

#### F13: Control de Versiones BOM (Semanas 19-20)

**Descripción:** Sistema de versionado del BOM con análisis de desviaciones.

**Funcionalidades:**
- Baseline (v0) vs revisiones (v1, v2...)
- Tracking de cambios (items added/removed/modified)
- Comparador de versiones
- Dashboard de desviaciones

### 6.2 Métricas de Éxito Fase 2

| Métrica | Target |
|---------|--------|
| Tiempo generación Plan de Compras | <5 min |
| Accuracy RFQ (campos correctos) | >90% |
| Accuracy cálculo landed cost | >95% |
| Accuracy RACI auto-generado | >80% |
| Alertas consideradas útiles | >80% |
| Graph RAG improvement vs basic | >6 puntos |
| Adopción feature (% usuarios) | >60% |

---

## 7. Fase 3 - Control de Ejecución

**Timeline:** Semanas 21-28 (8 semanas)
**Objetivo:** Cerrar el ciclo con seguimiento real vs planificado y validación visual.

### 7.1 Features Principales

#### F14: Ingesta de Avance Real

**Métodos:**
- Manual (UI): usuario marca % avance
- Import Excel: template con avances
- API REST: integración con ERP/PM software
- MCP Server Primavera: sincronización automática

#### F15: Comparador Planificado vs Real

**Visualizaciones:**
- Curva S (planificado vs real)
- Gantt con desviaciones
- Dashboard de desviaciones críticas
- Alertas predictivas de retraso

#### F16: Multimodal RAG para Expediting

**Descripción:** Validar avance con fotos de obra/taller.

**Proceso:**
1. Upload de fotos de progreso
2. Claude Vision analiza imagen
3. Compara con BOM item esperado
4. Actualiza status automáticamente
5. Genera alertas si discrepancia

#### F17: MCP Server Integrations

**Servers:**
- SAP MM/Ariba: Órdenes de compra, proveedores
- Primavera P6: Cronograma, avance
- Oracle: Financials, budget

#### F18: KPIs Predictivos

**Métricas:**
- Probabilidad de retraso por material
- Exposición al riesgo de claim
- Cost at Completion forecast
- Schedule Performance Index (SPI)
- Cost Performance Index (CPI)

### 7.2 Métricas de Éxito Fase 3

| Métrica | Target |
|---------|--------|
| Accuracy comparador plan vs real | >95% |
| Tiempo análisis foto expediting | <30 segundos |
| Accuracy validación visual | >85% |
| Predicción retraso (AUC) | >0.80 |
| Adopción closed-loop | >40% |

---

## 8. Fase 4 - Futuro (2026+)

### 8.1 Negotiation Module (Pactum-inspired)

**Descripción:** Módulo de negociación automática para tail-spend.

**Features:**
- Contra-ofertas automáticas basadas en histórico
- Análisis de precio de mercado
- Negociación multi-ronda via chat
- Escalamiento a humano cuando necesario

**Caso de uso validado:** Zycus Fortune 500 client logró 2% savings en 3,000+ tail-spend negotiations.

### 8.2 Digital Twin de Compras

**Descripción:** Gemelo digital del plan de compras.

**Features:**
- Simulación de escenarios what-if
- Optimización automática de fechas de pedido
- Reajuste dinámico ante cambios de cronograma
- Análisis de sensibilidad

### 8.3 Autonomous Agents

**Descripción:** Agentes autónomos que ejecutan tareas sin supervisión.

**Features:**
- Expediting automático (emails a proveedores)
- Seguimiento de tracking numbers
- Alertas automáticas a stakeholders
- Cierre de órdenes completadas

### 8.4 Industry Expansion

**Sectores adicionales:**
- Oil & Gas (upstream, downstream)
- Mining
- Utilities
- Pharmaceutical plants
- Data centers
| **EXW** | Ex Works - Vendedor entrega en fábrica |
| **FOB** | Free On Board - Vendedor entrega en puerto origen |
| **CIF** | Cost, Insurance and Freight - Vendedor paga flete y seguro |
| **DAP** | Delivered At Place - Vendedor entrega en destino |
| **DDP** | Delivered Duty Paid - Todo incluido |
| **Landed Cost** | Coste total desembarcado |
| **Lead Time** | Tiempo total de entrega |
| **RLS** | Row Level Security - Seguridad a nivel de fila |
| **MCP** | Model Context Protocol - Protocolo estándar para integración de agentes |
| **Graph RAG** | Retrieval Augmented Generation con Knowledge Graphs |
| **Self-RAG** | RAG con reflexión y retrieval adaptativo |
| **CRAG** | Corrective RAG - RAG con evaluación y corrección |
| **Multimodal RAG** | RAG que integra texto e imágenes |
| **Coherence Score** | Indicador 0-100 de alineación entre documentos |
| **BC3** | Formato estándar español para presupuestos (FIEBDC) |
| **PITR** | Point-in-Time Recovery |
| **SPI** | Schedule Performance Index |
| **CPI** | Cost Performance Index |
| **EPC** | Engineering, Procurement, Construction |
| **CLM** | Contract Lifecycle Management |
| **NLP** | Natural Language Processing |
| **PII** | Personally Identifiable Information |

### 13.2 Stack Decisions (ADRs)

**ADR-001: Por qué FastAPI vs Flask/Django**
- Async nativo para AI API calls
- Pydantic v2 built-in (validación automática)
- OpenAPI automático (documentación gratis)
- Mejor DX para API-first app

**ADR-002: Por qué Supabase vs AWS RDS**
- RLS nativo (crítico para multi-tenancy)
- Auth incluido
- Backups automáticos + PITR
- Free tier generoso

**ADR-003: Por qué Claude vs GPT-4**
- Mejor calidad en documentos largos (200K context)
- Menos alucinaciones en extracción estructurada
- Pricing competitivo
- MCP support nativo

**ADR-004: Por qué Graph RAG vs Vector RAG**
- Mejora 6.4 puntos en multi-hop reasoning
- Relaciones explícitas Contract→WBS→BOM→Stakeholder
- Trazabilidad completa para auditoría
- Mejor para preguntas complejas de coherencia

**ADR-005: Por qué MCP vs Custom APIs**
- Estándar abierto con adopción masiva (10K+ servers)
- Interoperabilidad con otras herramientas AI
- Seguridad mejorada con OAuth Resource Server pattern
- Reduce time-to-market para integraciones

**ADR-006: Por qué Multi-Agente vs Monolítico**
- Especialización mejora calidad por tarea
- Facilita testing y debugging
- Escalabilidad independiente
- Alineado con tendencia de mercado (Gartner 2028: 1/3 enterprise software)

**ADR-007: Por qué Cloudflare R2 vs AWS S3**
- Sin egress fees (crítico para docs grandes)
- S3-compatible (migración fácil)
- CDN integrado
- Pricing predecible

**ADR-008: Por qué NetworkX vs Neo4j**
- Suficiente para MVP y Fase 2
- Sin infraestructura adicional
- Integración nativa con Python
- Migración a Neo4j posible en Fase 3+ si necesario

### 13.3 Cálculo de Incoterms - Detalle

```python
# Lógica de cálculo de Landed Cost por Incoterm

INCOTERM_COSTS = {
    "EXW": {
        "seller_pays": [],
        "buyer_pays": ["freight", "insurance", "customs_origin", "customs_dest"],
        "description": "Ex Works - Comprador paga todo desde fábrica"
    },
    "FOB": {
        "seller_pays": ["customs_origin"],
        "buyer_pays": ["freight", "insurance", "customs_dest"],
        "description": "Free On Board - Vendedor entrega en puerto origen"
    },
    "CIF": {
        "seller_pays": ["customs_origin", "freight", "insurance"],
        "buyer_pays": ["customs_dest"],
        "description": "Cost, Insurance, Freight - Vendedor paga hasta puerto destino"
    },
    "DAP": {
        "seller_pays": ["customs_origin", "freight", "insurance"],
        "buyer_pays": ["customs_dest"],
        "description": "Delivered At Place - Vendedor entrega en destino"
    },
    "DDP": {
        "seller_pays": ["customs_origin", "freight", "insurance", "customs_dest"],
        "buyer_pays": [],
        "description": "Delivered Duty Paid - Todo incluido"
    }
}

def calculate_landed_cost(
    unit_price: float,
    quantity: float,
    incoterm: str,
    freight_cost: float,
    insurance_rate: float,  # % del valor
    customs_origin_rate: float,
    customs_dest_rate: float
) -> dict:
    """
    Calcula el coste total desembarcado según Incoterm.
    """
    base_cost = unit_price * quantity
    insurance_cost = base_cost * insurance_rate
    customs_origin = base_cost * customs_origin_rate
    customs_dest = base_cost * customs_dest_rate
    
    incoterm_config = INCOTERM_COSTS[incoterm]
    
    # Lo que paga el comprador
    buyer_costs = base_cost  # Siempre paga el producto
    
    if "freight" in incoterm_config["buyer_pays"]:
        buyer_costs += freight_cost
    if "insurance" in incoterm_config["buyer_pays"]:
        buyer_costs += insurance_cost
    if "customs_origin" in incoterm_config["buyer_pays"]:
        buyer_costs += customs_origin
    if "customs_dest" in incoterm_config["buyer_pays"]:
        buyer_costs += customs_dest
    
    return {
        "base_cost": base_cost,
        "freight_cost": freight_cost if "freight" in incoterm_config["buyer_pays"] else 0,
        "insurance_cost": insurance_cost if "insurance" in incoterm_config["buyer_pays"] else 0,
        "customs_origin": customs_origin if "customs_origin" in incoterm_config["buyer_pays"] else 0,
        "customs_dest": customs_dest if "customs_dest" in incoterm_config["buyer_pays"] else 0,
        "total_landed_cost": buyer_costs,
        "incoterm": incoterm,
        "description": incoterm_config["description"]
    }
```

### 13.4 Cálculo de Lead Time - Detalle

```python
def calculate_lead_time(
    production_time_days: int,
    transit_time_days: int,
    customs_clearance_days: int = 0,
    buffer_days: int = 7,
    is_international: bool = False
) -> dict:
    """
    Calcula lead time total desglosado.
    """
    # Si es internacional, añadir tiempo de aduana
    if is_international and customs_clearance_days == 0:
        customs_clearance_days = 5  # Default para internacional
    
    total_lead_time = (
        production_time_days +
        transit_time_days +
        customs_clearance_days +
        buffer_days
    )
    
    return {
        "production_time_days": production_time_days,
        "transit_time_days": transit_time_days,
        "customs_clearance_days": customs_clearance_days,
        "buffer_days": buffer_days,
        "total_lead_time_days": total_lead_time,
        "breakdown": {
            "production": f"{production_time_days} días",
            "transit": f"{transit_time_days} días",
            "customs": f"{customs_clearance_days} días" if customs_clearance_days > 0 else "N/A",
            "buffer": f"{buffer_days} días"
        }
    }

def calculate_optimal_order_date(
    required_on_site_date: date,
    total_lead_time_days: int
) -> date:
    """
    Calcula fecha óptima de pedido.
    """
    return required_on_site_date - timedelta(days=total_lead_time_days)
```

### 13.5 Referencias

- [Anthropic Claude API Docs](https://docs.anthropic.com)
- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [Supabase Documentation](https://supabase.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Next.js Documentation](https://nextjs.org/docs)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FIEBDC-3 (BC3) Specification](https://www.fiebdc.es)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [GDPR Compliance Checklist](https://gdpr.eu/checklist/)
- [Graph RAG Paper - Microsoft Research](https://arxiv.org/abs/2404.16130)
- [Self-RAG Paper](https://arxiv.org/abs/2310.11511)
- [Incoterms 2020 - ICC](https://iccwbo.org/business-solutions/incoterms-rules/)

### 13.6 Documentos Relacionados

| Documento | Descripción | Ubicación |
|-----------|-------------|-----------|
| **C2Pro_Roadmap_Annex_2025.docx** | Anexo tecnológico con MCP, Agentic AI, RAG 2025 | /outputs/ |
| **Índice Maestro Paper** | Estructura académica del paper C2Pro | Conversaciones previas |
| **Abstract (Académico + Ejecutivo)** | Resúmenes para publicación y pitch | Conversaciones previas |
| **Análisis Competitivo** | 17 empresas, gaps, posicionamiento | Transcripts |
| **Stakeholder Analysis Research** | Evaluación de madurez tecnológica | Transcripts |

---

<div align="center">

## — FIN DEL ROADMAP v2.3.0 —

**C2Pro - Contract Intelligence Platform**
*Cognitive Operating System for EPC Procurement*

© 2024-2026 Todos los derechos reservados

---

**Este documento es la biblia del PM y desarrollo.**
**Cualquier decisión significativa debe ser reflejada aquí.**

---

*Última actualización: 03 de Enero de 2026*
*Próxima revisión programada: Tras completar MVP (Semana 12)*

</div>

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
