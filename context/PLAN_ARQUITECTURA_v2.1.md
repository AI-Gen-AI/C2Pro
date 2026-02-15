# Plan de Saneamiento y Evolución Arquitectónica de C2Pro (v2.1)

> **Versión:** 2.1.1  
> **Fecha:** 2026-01-31  
> **Última Actualización:** 2026-02-15  
> **Estado:** APROBADO por Architecture Review Board  
> **Alineado con:** Diagrama Maestro v2.2.1

---

## Índice

1. [Filosofía](#1-filosofía)
2. [Roadmap por Fases](#2-roadmap-por-fases)
3. [Estado Actual](#3-estado-actual-resumen-ejecutivo)
4. [Fase 1: Fundación - Monolito Modular y DDD](#4-fase-1-fundación---monolito-modular-y-ddd)
5. [Fase 1: Patrones de Diseño - Arquitectura Hexagonal](#5-fase-1-patrones-de-diseño---arquitectura-hexagonal)
6. [Fase 1: Seguridad Multitenant y Perímetro](#6-fase-1-seguridad-multitenant-y-perímetro)
7. [Fase 2: Orquestación y Agentes IA](#7-fase-2-orquestación-y-agentes-ia)
8. [Fase 2: Control de Costos y Resiliencia IA](#8-fase-2-control-de-costos-y-resiliencia-ia)
9. [Fase 2: Componentes de Dominio Clave](#9-fase-2-componentes-de-dominio-clave)
10. [Fase 2: Arquitectura Asíncrona](#10-fase-2-arquitectura-asíncrona)
11. [Fase 3: Contrato API y Front-Back](#11-fase-3-contrato-api-y-front-back)
12. [Fase 3: Estrategia de Pruebas](#12-fase-3-estrategia-de-pruebas)
13. [Fase 3: Observabilidad](#13-fase-3-observabilidad)
14. [Fase 3: Compliance y Auditoría](#14-fase-3-compliance-y-auditoría)
15. [Fase 3: Documentación Viva](#15-fase-3-documentación-viva)
16. [Roadmap de Despliegue y Riesgos](#16-roadmap-de-despliegue-y-riesgos)
17. [Anexos](#anexos)

---

## 1. Filosofía

Este plan representa la hoja de ruta para transformar C2Pro en un **monolito modular con arquitectura hexagonal por módulo**. Se prioriza:

| Principio                | Descripción                              |
| ------------------------ | ---------------------------------------- |
| **Claridad**             | Estructura predecible y documentada      |
| **Estabilidad**          | Cambios controlados con gates de calidad |
| **Evolución Controlada** | Migración incremental sin big-bang       |
| **Trazabilidad**         | Todo cambio auditable y reversible       |

### Principios Arquitectónicos Fundamentales

1. **Separation of Concerns**: Cada módulo encapsula un bounded context
2. **Dependency Inversion**: Dominio define interfaces, infraestructura implementa
3. **Single Source of Truth**: La tabla `clauses` es el eje de trazabilidad
4. **Defense in Depth**: Múltiples capas de seguridad (JWT → Tenant → MCP Gateway)
5. **Fail-Safe Defaults**: Circuit breakers, fallbacks y degradación graceful

---

## 2. Roadmap por Fases

### Estructura de Fases

| Fase       | Nombre               | Secciones   | Estado | Prerequisito |
| ---------- | -------------------- | ----------- | ------ | ------------ |
| **Fase 1** | Fundación            | 4, 5, 6     | 🔄 85% | -            |
| **Fase 2** | Capacidades Críticas | 7, 8, 9, 10 | 🔄 65% | Fase 1 100%  |
| **Fase 3** | Escalado y Madurez   | 11-16       | ⏳ 10% | Fase 2 ≥80%  |

> **Nota (2026-02-14):** Fase 1 ajustada de 95% a 85% — tareas 6.2.2, 6.2.3, 6.4.3, 6.4.4 siguen PENDIENTE.  
> Fase 2 ajustada de 40% a 65% — la mayoría de suites de dominio y aplicación implementadas (ver TDD Backlog v1.1).

### Dependencias Críticas

- **Fase 2 NO puede iniciar** sin Fase 1 completa (verificación `rg` sin violaciones)
- **Fase 3 NO puede iniciar** sin Coherence Engine v2 operativo
- **Producción NO puede lanzar** sin Audit Trail + Observabilidad completos

---

## 3. Estado Actual (Resumen Ejecutivo)

### Arquitectura Implementada

```
apps/api/src/
├── core/                    # Infraestructura transversal
│   ├── auth/               # JWT + Tenant extraction
│   ├── ai/                 # LLM clients, prompts versionados
│   ├── events/             # Event Bus (Redis Pub/Sub)
│   ├── mcp/                # MCP Gateway core
│   ├── middleware/          # Request middleware
│   ├── observability/      # Logging, tracing, metrics
│   ├── persistence/        # Base DB connection (PostgreSQL + Neo4j)
│   ├── privacy/            # PII handling
│   ├── security/           # Anonymizer, tenant context
│   ├── serialization/      # JSON serialization
│   ├── services/           # Shared services (rate limiter, etc.)
│   ├── tasks/              # Celery task definitions
│   └── tenants/            # Tenant isolation logic
├── documents/              # 📄 Módulo Documents
├── stakeholders/           # 👥 Módulo Stakeholders
├── projects/               # 📁 Módulo Projects (WBS)
├── procurement/            # 🛒 Módulo Procurement (BOM)
├── analysis/               # 🤖 Módulo Analysis
├── coherence/              # 🎯 Módulo Coherence Engine
├── anonymizer/             # 🔒 Módulo Anonymizer (PII)
├── alerts/                 # 🔔 Módulo Alerts (stub)
├── bulk_operations/        # 📦 Módulo Bulk Operations (baseline E2E contracts)
├── mcp/                    # 🤖 Módulo MCP Adapters
└── modules/                # 📂 Sub-módulos AI Pipeline
    ├── ingestion/          # Document ingestion pipeline
    ├── extraction/         # Clause/entity extraction
    └── retrieval/          # RAG retrieval
```

> **Nota (2026-02-14):** Estructura actualizada para reflejar el estado real del codebase.  
> El módulo `alerts/` sigue como stub; `bulk_operations/` ya cuenta con contratos base E2E implementados (TS-E2E-FLW-BLK-001).  
> `modules/` contiene sub-módulos del pipeline IA (Phase 4 increments I1-I12).

### Métricas de Progreso

| Área                    | Estado          | Progreso | Nota (2026-02-14)                                     |
| ----------------------- | --------------- | -------- | ----------------------------------------------------- |
| Estructura Modular      | ✅ Activo       | 100%     |                                                       |
| Core Transversal        | ✅ Consolidado  | 100%     |                                                       |
| Routers HTTP Delgados   | ✅ Implementado | 100%     |                                                       |
| Regla Cross-Módulo      | ✅ Aplicada     | 100%     |                                                       |
| Coherence Engine v2     | 🔄 En Progreso  | 85%      | 12/12 suites dominio OK, falta dashboard + YAML rules |
| MCP Gateway             | ✅ Completado   | 100%     | 4/4 tareas Gateway completadas                        |
| Anonymizer Service      | 🔄 En Progreso  | 75%      | Detección + Estrategias OK, falta audit + tests       |
| Seguridad Multitenant   | 🔄 En Progreso  | 70%      | Middleware + Context OK, falta repo filters + RLS     |
| Observabilidad Completa | 🔄 En Progreso  | 40%      |                                                       |
| TDD Suites              | 🔄 En Progreso  | 99%      | 88/89 suites completadas (ver TDD Backlog v1.4)       |
| AI Pipeline (I1-I2)     | ✅ Completado   | 100%     | Ingestion contract + OCR/table reliability completados |
| AI Pipeline (I3-I4)     | ✅ Completado   | 100%     | Clause extraction normalization + hybrid retrieval/rerank/gating completados |
| AI Pipeline (I5-I6)     | ✅ Completado   | 100%     | Graph integrity + coherence pure-rule engine + standardized alert contract completados |
| AI Pipeline (I7-I9)     | ✅ Completado   | 100%     | Risk scoring aggregation + WBS/BOM generation + procurement intelligence + S4 security assertions completados |
| AI Pipeline (I10-I12)   | ✅ Completado   | 100%     | Stakeholder/RACI + HITL workflow + LangSmith/eval harness + S5 security assertions + DevOps CI gates/scheduled drift checks completados |
| AI Pipeline (I13)       | ✅ Completado   | 100%     | Real E2E route contract estabilizado (`/api/v1/decision-intelligence/execute`) + auth/tenant deterministic harness + S6 blocking CI gate |

---

## 4. Fase 1: Fundación - Monolito Modular y DDD

**Responsable:** Arquitecto Principal + Tech Lead  
**Estado:** ✅ COMPLETADO  
**Fecha Cierre:** 2026-01-29

### 4.1 Objetivos Alcanzados

- Estructura única sin duplicidad de código
- Comunicación inter-módulo exclusivamente vía puertos
- Bounded contexts claramente definidos

### 4.2 Tareas Completadas

| ID    | Tarea                                 | Estado  | Fecha      |
| ----- | ------------------------------------- | ------- | ---------- |
| 4.2.1 | ADR monolito modular                  | ✅ DONE | 2026-01-15 |
| 4.2.2 | Definir bounded contexts y estructura | ✅ DONE | 2026-01-18 |
| 4.2.3 | Regla de comunicación inter-módulo    | ✅ DONE | 2026-01-20 |
| 4.2.4 | Consolidar código duplicado           | ✅ DONE | 2026-01-22 |
| 4.2.5 | Separar dominio vs infraestructura    | ✅ DONE | 2026-01-25 |
| 4.2.6 | Eliminar ambigüedad de ubicación      | ✅ DONE | 2026-01-27 |
| 4.2.7 | Definir contratos públicos por módulo | ✅ DONE | 2026-01-29 |

---

## 5. Fase 1: Patrones de Diseño - Arquitectura Hexagonal

**Responsable:** Backend Lead + Arquitecto  
**Estado:** ✅ COMPLETADO  
**Fecha Cierre:** 2026-01-30

### 5.1 Estructura Canónica por Módulo

Cada módulo de negocio **DEBE** implementar la siguiente estructura:

```
MOD_{NOMBRE}/
├── adapters/
│   ├── http/              # Router FastAPI (punto de entrada)
│   │   └── {module}_router.py
│   └── persistence/       # Implementaciones de repositorios
│       ├── models.py      # Modelos SQLAlchemy (INTERNO)
│       └── {module}_repository.py
├── application/
│   ├── dtos/              # Data Transfer Objects
│   ├── ports/             # Interfaces puras (Protocol)
│   ├── services/          # Servicios de aplicación
│   └── use_cases/         # Casos de uso orquestadores
└── domain/
    ├── entities/          # Entidades de dominio
    ├── value_objects/     # Value Objects inmutables
    ├── services/          # Domain Services
    └── events/            # Domain Events
```

### 5.2 Reglas de Dependencia (NORMATIVO)

| Regla  | Descripción                               | Verificación      |
| ------ | ----------------------------------------- | ----------------- |
| **R1** | Router SOLO orquesta y delega a Use Cases | Code review       |
| **R2** | Use Cases pueden usar Domain y Ports      | `rg` analysis     |
| **R3** | Domain NO importa nada externo            | `rg` analysis     |
| **R4** | Ports son interfaces puras (Protocol)     | Type checking     |
| **R5** | Adapters implementan Ports                | Tests de contrato |

### 5.3 Comunicación Inter-Módulo

La comunicación entre módulos se realiza **EXCLUSIVAMENTE** mediante:

```python
# ✅ CORRECTO: DTO definido en application/dtos/
@dataclass(frozen=True)
class WBSItemDTO:
    id: UUID
    code: str
    name: str
    level: int
    start_date: date
    end_date: date
    parent_id: Optional[UUID] = None

# ✅ CORRECTO: Puerto de consulta en application/ports/
class IWBSQueryPort(Protocol):
    def get_wbs_items_for_project(self, project_id: UUID) -> list[WBSItemDTO]: ...
    def wbs_item_exists(self, item_id: UUID) -> bool: ...
```

**PROHIBIDO:**

```python
# ❌ PROHIBIDO: Importar modelos ORM de otros módulos
from projects.adapters.persistence.models import WBSItemModel  # VIOLACIÓN

# ❌ PROHIBIDO: Relaciones ORM cross-módulo
class BOMItemModel(Base):
    wbs_item = relationship("WBSItemModel")  # VIOLACIÓN
    wbs_item_id = Column(UUID, ForeignKey("wbs_items.id"))  # ✅ FK simple OK
```

### 5.4 Tareas Completadas

| ID    | Tarea                                                    | Estado  |
| ----- | -------------------------------------------------------- | ------- |
| 5.4.1 | Dominio puro (entidades, value objects, domain services) | ✅ DONE |
| 5.4.2 | Puertos (interfaces) por módulo                          | ✅ DONE |
| 5.4.3 | Adaptadores (HTTP, persistence, externos)                | ✅ DONE |
| 5.4.4 | Routers delgados delegan a use cases                     | ✅ DONE |
| 5.4.5 | Core simple salvo reglas de negocio complejas            | ✅ DONE |

---

## 6. Fase 1: Seguridad Multitenant y Perímetro

**Responsable:** Security Lead + Backend Lead  
**Estado:** 🔄 EN PROGRESO (70%)

### 6.1 Arquitectura de Seguridad (4 Capas)

```
USUARIO
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA 1: API GATEWAY                                         │
│  FastAPI → JWT Validate (Supabase) → Extract tenant_id       │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA 2: MCP GATEWAY (NUEVO v2.1)                            │
│  Validate Operation → Allowlist → Rate Limit → Query Limits  │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA 3: REPOSITORIOS                                        │
│  Filtro tenant_id OBLIGATORIO en todas las queries           │
└──────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA 4: DATABASE (RLS)                                      │
│  Row Level Security alineado con lógica de aplicación        │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Tareas Seguridad Multitenant

| ID    | Tarea                                                                | Estado        | Prioridad |
| ----- | -------------------------------------------------------------------- | ------------- | --------- |
| 6.2.1 | Middleware obligatorio de tenant                                     | ✅ DONE       | CRÍTICA   |
| 6.2.2 | Repositorios con filtro tenant obligatorio                           | ⏳ PENDIENTE  | CRÍTICA   |
| 6.2.3 | RLS en DB alineado a lógica app                                      | ⏳ PENDIENTE  | ALTA      |
| 6.2.4 | Tenant Context + aislamiento de cache por tenant (TS-UC-SEC-TNT-001) | ✅ COMPLETADO | ALTA      |

### 6.3 MCP Gateway (Securizado) - NUEVO v2.1

**Responsable:** Security Lead + Backend Lead  
**Estado:** 🔄 EN PROGRESO  
**Prioridad:** 🔴 CRÍTICA

El MCP Gateway actúa como perímetro de seguridad para operaciones de agentes IA.

#### 6.3.1 Allowlist de Operaciones

| Tipo                  | Cantidad | Operaciones                                                                                                                                      |
| --------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Views (read-only)** | 8        | `projects_summary`, `alerts_active`, `coherence_latest`, `documents_metadata`, `stakeholders_list`, `wbs_structure`, `bom_items`, `audit_recent` |
| **Functions (write)** | 5        | `create_alert`, `update_score`, `flag_review`, `add_note`, `trigger_recalc`                                                                      |

#### 6.3.2 Límites de Protección

```python
MCP_GATEWAY_CONFIG = {
    "rate_limit": {
        "requests_per_minute": 60,
        "scope": "per_tenant"
    },
    "query_limits": {
        "timeout_seconds": 5,
        "max_rows": 1000
    },
    "audit": {
        "log_all_operations": True,
        "log_blocked_attempts": True
    }
}
```

#### 6.3.3 Tareas MCP Gateway

| ID      | Tarea                            | Estado        | Esfuerzo |
| ------- | -------------------------------- | ------------- | -------- |
| 6.3.3.1 | Implementar validación Allowlist | ✅ COMPLETADO | M        |
| 6.3.3.2 | Configurar Rate Limiting         | ✅ COMPLETADO | S        |
| 6.3.3.3 | Implementar Query Limits         | ✅ COMPLETADO | S        |
| 6.3.3.4 | Habilitar MCP Audit Log          | ✅ COMPLETADO | S        |

### 6.4 Anonymizer Service (PII) - NUEVO v2.1

**Responsable:** Security Lead + AI Lead  
**Estado:** 🔄 EN PROGRESO  
**Prioridad:** 🔴 CRÍTICA

Procesa documentos **ANTES** de extracción para detectar y anonimizar PII.

#### 6.4.1 Flujo

```
Parser (PDF/Excel/BC3) → Anonymizer Service → Clause Extractor → Entity Extraction
                              │
                              └──► Audit Log (PII detectada, sin valores)
```

#### 6.4.2 Tipos de PII

| Categoría           | Ejemplos                   | Estrategia           |
| ------------------- | -------------------------- | -------------------- |
| **Identificadores** | DNI, NIF, NIE, Pasaporte   | Hash irreversible    |
| **Contacto**        | Email, Teléfono, Dirección | Redacción [REDACTED] |
| **Financiero**      | IBAN, Tarjeta crédito      | Tokenización         |
| **Personal**        | Nombres completos          | Pseudonimización     |

#### 6.4.3 Tareas Anonymizer

| ID      | Tarea                                   | Estado        | Esfuerzo |
| ------- | --------------------------------------- | ------------- | -------- |
| 6.4.3.1 | Implementar detección PII (regex + NER) | ✅ COMPLETADO | L        |
| 6.4.3.2 | Configurar estrategia por tipo          | ✅ COMPLETADO | M        |
| 6.4.3.3 | Registrar en audit_logs                 | ⏳ PENDIENTE  | S        |
| 6.4.3.4 | Tests con datos sintéticos              | ⏳ PENDIENTE  | M        |

### 6.5 Infraestructura de Persistencia - NUEVO v2.1

**Estado:** NORMATIVO

#### 6.5.1 Stack de Persistencia

| Servicio       | Tecnología            | Uso                                  |
| -------------- | --------------------- | ------------------------------------ |
| **Relacional** | PostgreSQL (Supabase) | Datos estructurados, 18+ tablas, RLS |
| **Graph**      | Neo4j                 | Graph RAG, relaciones semánticas     |
| **Documentos** | **Cloudflare R2**     | Storage archivos (AES-256)           |
| **Cache**      | Redis                 | Cache, rate limiting, job queue      |
| **Vectores**   | pgvector              | Embeddings, similarity search        |

#### 6.5.2 Entidad Core: `clauses` (EJE DE TRAZABILIDAD)

```sql
-- Tabla central de trazabilidad
CREATE TABLE clauses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    document_id UUID NOT NULL REFERENCES documents(id),
    clause_number VARCHAR(50),
    title TEXT,
    content TEXT NOT NULL,
    clause_type VARCHAR(50),
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    confidence_score DECIMAL(3,2),
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}'
);

-- FKs OBLIGATORIAS desde entidades derivadas
ALTER TABLE stakeholders ADD COLUMN clause_id UUID REFERENCES clauses(id) ON DELETE RESTRICT;
ALTER TABLE wbs_items ADD COLUMN clause_id UUID REFERENCES clauses(id) ON DELETE RESTRICT;
ALTER TABLE bom_items ADD COLUMN clause_id UUID REFERENCES clauses(id) ON DELETE RESTRICT;
ALTER TABLE alerts ADD COLUMN clause_id UUID REFERENCES clauses(id) ON DELETE RESTRICT;
```

**Reglas de Integridad:**

- `ON DELETE RESTRICT` para todas las FKs hacia `clauses`
- Toda creación de stakeholder/wbs/bom/alert requiere `clause_id` válido
- Índices obligatorios en todas las FKs

---

## 7. Fase 2: Orquestación y Agentes IA

**Responsable:** AI Lead + Arquitecto Principal  
**Estado:** 🔄 EN PROGRESO (50%)

### 7.1 Arquitectura de Orquestación (LangGraph)

```
Intent Classifier → Agent Router → State Machine
                          │
    ┌─────────────────────┼─────────────────────┐
    ▼                     ▼                     ▼
document_task      stakeholder_task      project_task
    │                     │                     │
    ▼                     ▼                     ▼
analysis_task      coherence_task       procurement_task
```

### 7.2 Agentes del Sistema

| Agente                     | Módulo       | Función                     | LLM             |
| -------------------------- | ------------ | --------------------------- | --------------- |
| **Clause Extractor**       | Documents    | Extrae cláusulas            | Claude Sonnet 4 |
| **Entity Extractor**       | Documents    | Extrae entidades            | Claude Sonnet 4 |
| **Stakeholder Extractor**  | Stakeholders | Identifica stakeholders     | Claude Sonnet 4 |
| **Stakeholder Classifier** | Stakeholders | Clasifica Power/Interest    | Claude Haiku 4  |
| **RACI Generator**         | Stakeholders | Genera matriz RACI          | Claude Haiku 4  |
| **WBS Generator**          | Projects     | Genera estructura WBS       | Claude Sonnet 4 |
| **BOM Builder**            | Procurement  | Construye Bill of Materials | Claude Sonnet 4 |
| **Graph RAG**              | Analysis     | Queries multi-hop           | Claude Sonnet 4 |
| **LLM Analyzer**           | Analysis     | Análisis cualitativo        | Claude Sonnet 4 |
| **LLM Qualitative**        | Coherence    | Evaluación cualitativa      | Claude Haiku 4  |

### 7.3 Tareas de Orquestación

| ID    | Tarea                              | Estado         | Esfuerzo |
| ----- | ---------------------------------- | -------------- | -------- |
| 7.3.1 | LangGraph como orquestación        | ✅ DONE        | L        |
| 7.3.2 | Interfaces de tool/agente          | 🔄 EN PROGRESO | M        |
| 7.3.3 | Nodos de validación deterministas  | ⏳ PENDIENTE   | M        |
| 7.3.4 | Versionado centralizado de prompts | 🔄 EN PROGRESO | M        |

### 7.4 Estrategia de Proveedores LLM - NUEVO v2.1

**Responsable:** AI Lead + Platform Lead  
**Estado:** 🔄 EN PROGRESO  
**Prioridad:** 🟠 ALTA

#### 7.4.1 Modelo Primario y Fallback

| Uso                       | Proveedor | Modelo              | Justificación          |
| ------------------------- | --------- | ------------------- | ---------------------- |
| **Análisis Principal**    | Anthropic | **Claude Sonnet 4** | Calidad + context 200K |
| **Fallback Análisis**     | OpenAI    | GPT-4o              | Resiliencia            |
| **Coherence Qualitative** | Anthropic | Claude Haiku 4      | Costo-efectivo         |
| **Embeddings**            | Voyage AI | voyage-2            | Especializado docs     |

#### 7.4.2 Criterios de Fallback

```python
FALLBACK_CONFIG = {
    "primary_timeout_ms": 30000,       # 30s → switch a fallback
    "error_rate_threshold": 0.05,       # 5% errors → circuit breaker
    "error_window_minutes": 5,
    "rate_limit_action": "auto_fallback"
}
```

#### 7.4.3 Versionado de Prompts

```
core/ai/prompts/
├── v1/
│   ├── clause_extraction.yaml
│   └── entity_extraction.yaml
├── v2/
│   └── clause_extraction.yaml
└── current -> v2/                   # Symlink a versión activa
```

#### 7.4.4 Tareas LLM Strategy

| ID      | Tarea                                 | Estado         | Esfuerzo |
| ------- | ------------------------------------- | -------------- | -------- |
| 7.4.4.1 | Configurar cliente Anthropic primario | 🔄 EN PROGRESO | M        |
| 7.4.4.2 | Implementar fallback OpenAI           | ⏳ PENDIENTE   | M        |
| 7.4.4.3 | Centralizar prompts YAML              | 🔄 EN PROGRESO | M        |
| 7.4.4.4 | Tracking versión de prompt            | ⏳ PENDIENTE   | S        |

---

## 8. Fase 2: Control de Costos y Resiliencia IA

**Responsable:** Platform Lead + AI Lead  
**Estado:** ⏳ PENDIENTE

### 8.1 Arquitectura de Resiliencia

```
LLM Call
    │
    ▼
Circuit Breaker ──► OPEN ──► Fallback Response
    │                           │
    │ CLOSED                    │
    ▼                           │
Normal Operation ◄──────────────┘
    │
    ▼
Budget Monitor ──► >95% ──► Throttle
    │               │
    │               └──► >100% ──► Block
    │
    ▼
AI Usage Dashboard
```

### 8.2 Tareas Control de Costos

| ID    | Tarea                              | Estado       | Esfuerzo |
| ----- | ---------------------------------- | ------------ | -------- |
| 8.2.1 | Trazabilidad de costos por request | ⏳ PENDIENTE | M        |
| 8.2.2 | Budget circuit breaker ($30/día)   | ⏳ PENDIENTE | M        |
| 8.2.3 | Retry/circuit breaker por tool     | ⏳ PENDIENTE | M        |
| 8.2.4 | Dashboard de costos tiempo real    | ⏳ PENDIENTE | L        |
| 8.2.5 | Alertas automáticas por umbral     | ⏳ PENDIENTE | S        |

### 8.3 Configuración de Resiliencia

```python
RESILIENCE_CONFIG = {
    "circuit_breaker": {
        "failure_threshold": 5,
        "recovery_timeout_seconds": 60,
        "half_open_requests": 3
    },
    "retry": {
        "max_attempts": 3,
        "backoff_base_seconds": 1,
        "backoff_max_seconds": 30,
        "backoff_multiplier": 2
    },
    "budget": {
        "daily_limit_usd": 30.00,
        "warning_threshold": 0.80,
        "throttle_threshold": 0.95,
        "block_threshold": 1.00
    }
}
```

---

## 9. Fase 2: Componentes de Dominio Clave

**Responsable:** Product + Backend Lead  
**Estado:** 🔄 EN PROGRESO (60%)

### 9.1 Coherence Engine v2 (6 Categorías) - NUEVO v2.1

**Responsable:** Product + Backend Lead + AI Lead  
**Estado:** 🔄 EN PROGRESO  
**Prioridad:** 🔴 CRÍTICA

#### 9.1.1 Visión General

```
┌────────────────────────────────────────────────────────────────┐
│                    COHERENCE ENGINE v2                          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🎯 SCOPE    💰 BUDGET   ✅ QUALITY  ⚙️ TECHNICAL  ⚖️ LEGAL   │
│    80%         62%         85%          72%          90%       │
│    20%         20%         15%          15%          15%       │
│                                                                 │
│                        ⏱️ TIME                                  │
│                          75%                                    │
│                          15%                                    │
│                                                                 │
│                    ┌─────────────┐                              │
│                    │ PESOS       │                              │
│                    │CONFIGURABLES│                              │
│                    └──────┬──────┘                              │
│                           │                                     │
│                    ┌──────┴──────┐                              │
│                    │🎯 GLOBAL    │                              │
│                    │  78/100     │                              │
│                    └─────────────┘                              │
└────────────────────────────────────────────────────────────────┘
```

#### 9.1.2 Definición de Categorías

| Categoría     | Código | Descripción                       | Peso Default |
| ------------- | ------ | --------------------------------- | ------------ |
| **SCOPE**     | 🎯     | Alcance definido vs Contrato      | 20%          |
| **BUDGET**    | 💰     | Costos vs Presupuesto aprobado    | 20%          |
| **QUALITY**   | ✅     | Cumplimiento de estándares        | 15%          |
| **TECHNICAL** | ⚙️     | Coherencia ingeniería/specs       | 15%          |
| **LEGAL**     | ⚖️     | Cláusulas y compliance            | 15%          |
| **TIME**      | ⏱️     | Cronograma vs hitos contractuales | 15%          |

#### 9.1.3 Mapeo de Reglas por Categoría

```yaml
coherence_rules_v2:
  SCOPE:
    - R11: "WBS sin actividades vinculadas"
    - R12: "WBS sin partidas asignadas"
    - R13: "Alcance no cubierto por WBS"
  BUDGET:
    - R6: "Suma partidas ≠ precio contrato (±5%)"
    - R15: "BOM sin partida presupuestaria"
    - R16: "Desviación presupuestaria >10%"
  QUALITY:
    - R17: "Especificación sin estándar definido"
    - R18: "Material sin certificación requerida"
  TECHNICAL:
    - R3: "Especificación contradictoria"
    - R4: "Requisito técnico sin responsable"
    - R7: "Dependencia técnica no resuelta"
  LEGAL:
    - R1: "Plazo contrato ≠ fecha fin cronograma"
    - R8: "Cláusula de penalización sin hito"
    - R20: "Aprobador contractual no identificado"
  TIME:
    - R2: "Hito sin actividad en cronograma"
    - R5: "Cronograma excede plazo contractual"
    - R14: "Material crítico con fecha pedido tardía"
```

#### 9.1.4 Fórmula de Cálculo

```python
def calculate_coherence_score_v2(
    alerts: list[Alert],
    weights: CategoryWeights,
    context: ProjectContext
) -> CoherenceResult:
    # 1. Agrupar alertas por categoría
    alerts_by_category = group_by_category(alerts)

    # 2. Calcular sub-score por categoría (0.0 - 1.0)
    sub_scores = {}
    for category in CATEGORIES:
        category_alerts = alerts_by_category.get(category, [])
        sub_scores[category] = calculate_category_score(category_alerts, context)

    # 3. Aplicar pesos configurables
    weighted_sum = sum(sub_scores[cat] * weights[cat] for cat in CATEGORIES)

    # 4. Normalizar a 0-100
    global_score = int(weighted_sum * 100)

    return CoherenceResult(
        global_score=global_score,
        sub_scores=sub_scores,
        weights_used=weights,
        methodology_version="2.0"
    )

DEFAULT_WEIGHTS = {
    "SCOPE": 0.20, "BUDGET": 0.20, "QUALITY": 0.15,
    "TECHNICAL": 0.15, "LEGAL": 0.15, "TIME": 0.15
}
```

#### 9.1.5 Componentes del Motor

| Componente             | Responsabilidad                      | Estado         |
| ---------------------- | ------------------------------------ | -------------- |
| **Rules Engine**       | Evalúa 20 reglas determinísticas     | 🔄 EN PROGRESO |
| **LLM Qualitative**    | Fallback para evaluaciones complejas | ⏳ PENDIENTE   |
| **Score Calculator**   | Aplica fórmula con pesos             | 🔄 EN PROGRESO |
| **Anti-Gaming Policy** | Detecta manipulación                 | ✅ COMPLETADO  |

#### 9.1.6 Anti-Gaming Policy

| Patrón                   | Detección             | Acción                |
| ------------------------ | --------------------- | --------------------- |
| Cambios masivos          | >10 cambios/hora      | Flag revisión         |
| Resolve-reintroduce      | Misma alerta 3+ veces | Penalización -5pts    |
| Score alto sin evidencia | >90% con <5 docs      | Auditoría obligatoria |
| Weight manipulation      | >20% cambio en 24h    | Notificación admin    |

#### 9.1.7 Impacto en Base de Datos

```sql
ALTER TABLE coherence_scores ADD COLUMN IF NOT EXISTS sub_scores JSONB DEFAULT '{}';
CREATE INDEX idx_coherence_subscores ON coherence_scores USING GIN (sub_scores);
```

#### 9.1.8 Tareas Coherence Engine v2

| ID        | Tarea                                                                | Estado         | Esfuerzo |
| --------- | -------------------------------------------------------------------- | -------------- | -------- |
| 9.1.8.1   | Implementar evaluación por categorías                                | 🔄 EN PROGRESO | L        |
| 9.1.8.1.a | Definir Category Enum + pesos default (TS-UD-COH-CAT-001)            | ✅ COMPLETADO  | S        |
| 9.1.8.1.b | Implementar reglas determinísticas por categoría (TS-UD-COH-RUL-001) | ✅ COMPLETADO  | M        |
| 9.1.8.1.c | Validar reglas de presupuesto (TS-UD-COH-RUL-002)                    | ✅ COMPLETADO  | S        |
| 9.1.8.1.d | Validar reglas de tiempo (TS-UD-COH-RUL-003)                         | ✅ COMPLETADO  | S        |
| 9.1.8.1.e | Validar reglas técnicas (TS-UD-COH-RUL-004)                          | ✅ COMPLETADO  | S        |
| 9.1.8.1.f | Validar reglas legales (TS-UD-COH-RUL-005)                           | ✅ COMPLETADO  | S        |
| 9.1.8.1.g | Validar reglas de calidad (TS-UD-COH-RUL-006)                        | ✅ COMPLETADO  | S        |
| 9.1.8.1.h | Implementar SubScores Calculator (TS-UD-COH-SCR-001)                 | ✅ COMPLETADO  | S        |
| 9.1.8.1.i | Implementar Global Score Calculator (TS-UD-COH-SCR-002)              | ✅ COMPLETADO  | S        |
| 9.1.8.1.j | Implementar Custom Weights Calculator (TS-UD-COH-SCR-003)            | ✅ COMPLETADO  | S        |
| 9.1.8.1.k | Implementar Alert Entity & Mapping (TS-UD-COH-ALR-001)               | ✅ COMPLETADO  | S        |
| 9.1.8.2   | Migrar reglas a YAML/DB                                              | ⏳ PENDIENTE   | M        |
| 9.1.8.3   | Pesos configurables por proyecto                                     | ⏳ PENDIENTE   | M        |
| 9.1.8.4   | Anti-Gaming Policy                                                   | ✅ COMPLETADO  | L        |
| 9.1.8.5   | Coherence Dashboard con drill-down                                   | ⏳ PENDIENTE   | L        |

### 9.2 Graph RAG con `IGraphRepository`

| ID    | Tarea                           | Estado       | Esfuerzo |
| ----- | ------------------------------- | ------------ | -------- |
| 9.2.1 | Abstraer Graph RAG con interfaz | ⏳ PENDIENTE | M        |
| 9.2.2 | Implementar adapter Neo4j       | ⏳ PENDIENTE | M        |
| 9.2.3 | Multi-hop queries optimizadas   | ⏳ PENDIENTE | L        |

### 9.3 Integración WBS-Procurement - NUEVO v2.1

**Responsable:** Backend Lead (Projects + Procurement)  
**Estado:** ⏳ PENDIENTE  
**Prioridad:** 🟠 ALTA

#### 9.3.1 Flujo de Integración

```
┌─────────────────┐     WBS Items DTO     ┌─────────────────┐
│  MOD_PROJECTS   │ ────────────────────► │  MOD_PROCUREMENT │
│  WBS Manager    │   (via Port)          │  BOM Builder    │
│  (4 niveles)    │                       │       ▼         │
└─────────────────┘                       │  BOM Analyzer   │
                                          │       ▼         │
                                          │  Lead Time Calc │
                                          │       ▼         │
                                          │  Procurement    │
                                          │  Plan Generator │
                                          └─────────────────┘
```

#### 9.3.2 Contrato DTO

```python
@dataclass(frozen=True)
class WBSItemDTO:
    id: UUID
    code: str           # e.g., "1.2.3.1"
    name: str
    level: int          # 1-4
    start_date: date
    end_date: date
    parent_id: Optional[UUID] = None
    specifications: Optional[dict] = None
```

#### 9.3.3 Puerto de Consulta

```python
class IWBSQueryPort(Protocol):
    def get_wbs_items_for_project(self, project_id: UUID, level: Optional[int] = None) -> list[WBSItemDTO]: ...
    def get_wbs_item_by_id(self, item_id: UUID) -> Optional[WBSItemDTO]: ...
    def wbs_item_exists(self, item_id: UUID) -> bool: ...
```

#### 9.3.4 Lead Time Calculator

```python
class LeadTimeCalculator:
    def calculate_optimal_order_date(self, bom_item: BOMItem, wbs_item: WBSItemDTO) -> LeadTimeResult:
        required_on_site = wbs_item.start_date - timedelta(days=bom_item.buffer_days)
        total_lead_time = (
            bom_item.production_time_days +
            bom_item.transit_time_days +
            bom_item.customs_clearance_days +
            bom_item.buffer_days
        )
        optimal_order_date = required_on_site - timedelta(days=total_lead_time)
        return LeadTimeResult(optimal_order_date, required_on_site, {...})
```

#### 9.3.5 Tareas Integración

| ID         | Tarea                                                             | Estado        | Esfuerzo |
| ---------- | ----------------------------------------------------------------- | ------------- | -------- |
| 9.3.5.0    | Implementar WBS Item Entity (TS-UD-PRJ-WBS-001)                   | ✅ COMPLETADO | S        |
| 9.3.5.0.a  | Implementar WBS Hierarchy & Codes (TS-UD-PRJ-WBS-002)             | ✅ COMPLETADO | S        |
| 9.3.5.0.b  | Implementar WBS Validation Rules (TS-UD-PRJ-WBS-003)              | ✅ COMPLETADO | S        |
| 9.3.5.0.c  | Implementar WBS CRUD Operations (TS-UD-PRJ-WBS-004)               | ✅ COMPLETADO | S        |
| 9.3.5.0.d  | Implementar Project Entity (TS-UD-PRJ-PRJ-001)                    | ✅ COMPLETADO | S        |
| 9.3.5.0.e  | Implementar WBSItemDTO & IWBSQueryPort (TS-UD-PRJ-DTO-001)        | ✅ COMPLETADO | S        |
| 9.3.5.0.f  | Implementar BOM Item Entity (TS-UD-PROC-BOM-001)                  | ✅ COMPLETADO | S        |
| 9.3.5.0.g  | Implementar BOM Validation Rules (TS-UD-PROC-BOM-002)             | ✅ COMPLETADO | S        |
| 9.3.5.0.h  | Implementar Lead Time Calculator Basic (TS-UD-PROC-LTM-001)       | ✅ COMPLETADO | S        |
| 9.3.5.0.i  | Implementar Lead Time Calculator Incoterms (TS-UD-PROC-LTM-002)   | ✅ COMPLETADO | S        |
| 9.3.5.0.j  | Implementar Lead Time Calculator Customs (TS-UD-PROC-LTM-003)     | ✅ COMPLETADO | S        |
| 9.3.5.0.k  | Implementar Lead Time Alerts (TS-UD-PROC-LTM-004)                 | ✅ COMPLETADO | S        |
| 9.3.5.0.l  | Implementar Procurement Plan Generation (TS-UD-PROC-PLN-001)      | ✅ COMPLETADO | S        |
| 9.3.5.0.m  | Implementar Stakeholder Entity (TS-UD-STK-ENT-001)                | ✅ COMPLETADO | S        |
| 9.3.5.0.n  | Implementar Power/Interest Classification (TS-UD-STK-CLS-001)     | ✅ COMPLETADO | S        |
| 9.3.5.0.o  | Implementar Quadrant Assignment (TS-UD-STK-CLS-002)               | ✅ COMPLETADO | S        |
| 9.3.5.0.p  | Implementar JWT Validation (TS-UC-SEC-JWT-001)                    | ✅ COMPLETADO | S        |
| 9.3.5.0.q  | Implementar Audit Trail Core (TS-UC-SEC-AUD-001)                  | ✅ COMPLETADO | S        |
| 9.3.5.0.r  | Implementar Celery Job Queue (TS-INT-EVT-CEL-001)                 | ✅ COMPLETADO | S        |
| 9.3.5.0.s  | Implementar Dead Letter Queue (TS-INT-EVT-DLQ-001)                | ✅ COMPLETADO | S        |
| 9.3.5.0.t  | Implementar All DTOs Validation (TS-UA-DTO-ALL-001)               | ✅ COMPLETADO | S        |
| 9.3.5.0.u  | Implementar DTO Serialization/Deserialization (TS-UA-DTO-SER-001) | ✅ COMPLETADO | S        |
| 9.3.5.0.v  | Implementar Error Handlers (TS-UAD-HTTP-ERR-001)                  | ✅ COMPLETADO | S        |
| 9.3.5.0.w  | Implementar Clause Repository + DB (TS-INT-DB-CLS-001)            | ✅ COMPLETADO | S        |
| 9.3.5.0.x  | Implementar Document Repository + DB (TS-INT-DB-DOC-001)          | ✅ COMPLETADO | S        |
| 9.3.5.0.y  | Implementar WBS Repository + DB (TS-INT-DB-WBS-001)               | ✅ COMPLETADO | S        |
| 9.3.5.0.z  | Implementar Generate WBS Use Case (TS-UA-PRJ-UC-001)              | ✅ COMPLETADO | S        |
| 9.3.5.0.aa | Implementar CRUD WBS Item Use Case (TS-UA-PRJ-UC-002)             | ✅ COMPLETADO | S        |
| 9.3.5.1    | Definir DTO WBS Items                                             | ✅ COMPLETADO | S        |
| 9.3.5.2    | Puerto consulta Projects                                          | ✅ COMPLETADO | M        |
| 9.3.5.3    | BOM Builder consume WBS                                           | ✅ COMPLETADO | M        |
| 9.3.5.4    | Lead Time Calculator                                              | ✅ COMPLETADO | M        |

> **Nota (2026-02-14):** Las tareas 9.3.5.1-4 fueron completadas como parte de las suites  
> TS-UD-PRJ-DTO-001, TS-UD-PROC-BOM-001/002, TS-UD-PROC-LTM-001/002/003/004.  
> Ver items 9.3.5.0.e, 9.3.5.0.f, 9.3.5.0.h-k para detalles de implementación.

---

## 10. Fase 2: Arquitectura Asíncrona - NUEVO v2.1

**Responsable:** Platform Lead + Backend Lead  
**Estado:** ⏳ PENDIENTE  
**Prioridad:** 🟠 ALTA

### 10.1 Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                      CAPA ASÍNCRONA                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐     ┌─────────────────┐                    │
│  │   Job Queue     │     │   Event Bus     │                    │
│  │    (Celery)     │     │ (Redis Pub/Sub) │                    │
│  └────────┬────────┘     └────────┬────────┘                    │
│           │                       │                              │
│           ▼                       ▼                              │
│  ┌─────────────────┐     ┌─────────────────────────────────┐   │
│  │  Worker Pool    │     │  Eventos:                        │   │
│  │  (4 workers)    │     │  • document.uploaded             │   │
│  └─────────────────┘     │  • document.processed            │   │
│                          │  • clause.extracted              │   │
│                          │  • alert.created                 │   │
│                          │  • alert.resolved                │   │
│                          │  • coherence.updated             │   │
│                          │  • stakeholder.identified        │   │
│                          └─────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 Catálogo de Eventos

| Evento               | Productor | Consumidores                |
| -------------------- | --------- | --------------------------- |
| `document.uploaded`  | API       | Document Processor          |
| `document.processed` | Documents | Analysis, Coherence         |
| `clause.extracted`   | Documents | Stakeholders, Alerts, Graph |
| `alert.created`      | Analysis  | UI, Coherence               |
| `alert.resolved`     | API       | Coherence, Audit            |
| `coherence.updated`  | Coherence | UI Dashboard, Audit         |

Reglas de transporte (Redis Pub/Sub):
- Canal canónico: `c2pro.{env}.{tenant_id}.{topic}`
- Scope multi-tenant obligatorio: suscripciones y publicación por `tenant_id`
- Metadatos mínimos de observabilidad por evento: `correlation_id`, `tenant_id`, `topic`

### 10.3 Flujo Async - Document Processing

```
Upload → API → Job Queue → Worker → [
    Parser → Anonymizer → Clause Extractor → Embeddings → Graph Index
] → Event Bus → [document.processed] → Trigger Analysis
```

### 10.4 Tareas Arquitectura Async

| ID     | Tarea                          | Estado        | Esfuerzo |
| ------ | ------------------------------ | ------------- | -------- |
| 10.4.1 | Configurar Celery + Redis      | ✅ COMPLETADO | M        |
| 10.4.2 | Implementar Event Bus          | ✅ COMPLETADO | M        |
| 10.4.3 | Migrar docs processing a async | ⏳ PENDIENTE  | L        |
| 10.4.4 | Documentar catálogo eventos    | ✅ COMPLETADO | S        |
| 10.4.5 | Dead letter queue              | ✅ COMPLETADO | M        |
| 10.4.6 | Monitoring workers             | ⏳ PENDIENTE  | M        |

---

## 11. Fase 3: Contrato API y Front-Back

**Responsable:** Frontend Lead + API Lead + DevOps  
**Estado:** ⏳ PENDIENTE

### 11.1 Tareas

| ID     | Tarea                         | Estado       | Esfuerzo |
| ------ | ----------------------------- | ------------ | -------- |
| 11.1.1 | Generación automática OpenAPI | ⏳ PENDIENTE | M        |
| 11.1.2 | Tests de contrato en CI       | ⏳ PENDIENTE | M        |
| 11.1.3 | Client SDK auto-generado      | ⏳ PENDIENTE | L        |

### 11.2 Endpoints Especiales (UI)

| Endpoint                                    | Propósito           | Agregación             |
| ------------------------------------------- | ------------------- | ---------------------- |
| `GET /api/evidence/{clause_id}`             | Evidence Viewer     | Clause + Docs + Alerts |
| `GET /api/coherence/dashboard/{project_id}` | Coherence Dashboard | Scores + Breakdown     |
| `GET /api/stakeholders/map/{project_id}`    | Stakeholder Map     | Matrix Power/Interest  |
| `GET /api/alerts/by-category/{project_id}`  | Alerts by Category  | Grouped alerts         |

### 11.3 Vistas UI Requeridas

| Vista                   | Descripción                           |
| ----------------------- | ------------------------------------- |
| **Evidence Viewer**     | Documento con highlights de cláusulas |
| **Stakeholder Map**     | Matriz Power/Interest interactiva     |
| **Coherence Dashboard** | Score con drill-down por categoría    |
| **Disclaimer Legal**    | Aceptación obligatoria en onboarding  |

---

## 12. Fase 3: Estrategia de Pruebas

**Responsable:** QA Lead + Tech Leads  
**Estado:** ⏳ PENDIENTE

### 12.1 Pirámide de Tests

| Nivel       | Cobertura | Tecnología              |
| ----------- | --------- | ----------------------- |
| Unit Tests  | 60%       | pytest                  |
| Integration | 25%       | pytest + testcontainers |
| Contract    | 10%       | pact                    |
| E2E         | 5%        | Cypress                 |

### 12.2 Tareas de Testing

| ID     | Tarea                          | Estado       | Esfuerzo |
| ------ | ------------------------------ | ------------ | -------- |
| 12.2.1 | Unit tests dominio y use cases | ⏳ PENDIENTE | L        |
| 12.2.2 | Integración adaptadores        | ⏳ PENDIENTE | L        |
| 12.2.3 | Contratos APIs externas        | ⏳ PENDIENTE | M        |
| 12.2.4 | E2E flujos críticos            | 🔄 EN PROGRESO (TS-E2E-ERR-TIM-001 + TS-E2E-ERR-CON-001 implementados) | L        |

### 12.3 Tests de Integración Cross-Módulo

| Test                 | Módulos               | Validación          |
| -------------------- | --------------------- | ------------------- |
| WBS → Procurement    | Projects, Procurement | DTO contract válido |
| Documents → Analysis | Documents, Analysis   | Trigger de eventos  |
| Analysis → Coherence | Analysis, Coherence   | Cálculo de scores   |

### 12.4 Tests de Seguridad MCP

| Test                 | Descripción                       | Criterio           |
| -------------------- | --------------------------------- | ------------------ |
| Allowlist Validation | Operaciones permitidas/bloqueadas | 100% cobertura     |
| Rate Limiting        | 60 req/min por tenant             | Throttle efectivo  |
| Query Limits         | Timeout 5s, max 1000 rows         | Queries canceladas |

### 12.5 Tests de Coherence Engine

| Test                 | Descripción           | Criterio            |
| -------------------- | --------------------- | ------------------- |
| Rules Unit           | Cada regla individual | 20/20 reglas        |
| Category Calculation | Score por categoría   | 6/6 categorías      |
| Weight Configuration | Pesos modificables    | Suma = 100%         |
| Anti-Gaming          | Patrones manipulación | Detección mayor 95% |

### 12.6 Tests de Anonymizer

| Test          | Descripción          | Datos               |
| ------------- | -------------------- | ------------------- |
| PII Detection | Detección correcta   | 100 docs sintéticos |
| Anonimización | Estrategia aplicada  | Por tipo PII        |
| Audit Log     | Registro sin valores | Verificación manual |

### 12.7 I13 Real E2E Contract (WS-C/WS-D/WS-E/WS-F)

Estado: `✅ COMPLETADO (2026-02-15)`

Prerrequisitos normativos para ejecución real E2E (sin mocks de servicio):
1. Infra preflight obligatorio:
   `python apps/api/scripts/bootstrap_test_infra.py --start-services --require-redis`
2. Tenant/auth deterministic seed en harness E2E:
   `apps/api/tests/conftest.py`
3. Endpoint contractual disponible:
   `POST /api/v1/decision-intelligence/execute`
4. CI blocking gate activo:
   job `i13-real-e2e` en `.github/workflows/tests.yml`.

Rationale del parche de migración (bloqueo infra):
- Archivo: `apps/api/alembic/versions/20260124_0001_add_raci_evidence_text.py`
- Cambio: guards idempotentes para existencia de tabla/columna en `upgrade/downgrade`.
- Motivo: evitar fallas de bootstrap por estados parciales de esquema no relacionados con lógica I13.

Riesgos conocidos y mitigación:
1. Riesgo: los guards pueden ocultar drift estructural severo.
   Mitigación: verificación de head alembic en bootstrap + artefactos de diagnóstico CI.
2. Riesgo: fallback manual omita Redis y de falsos positivos.
   Mitigación: `--require-redis` en rutas CI/S6 bloqueantes.

Runbook operativo:
- `docs/runbooks/I13_REAL_E2E_INFRA_RUNBOOK.md`

---

## 13. Fase 3: Observabilidad

**Responsable:** Platform Lead  
**Estado:** 🔄 EN PROGRESO (40%)

### 13.1 Stack de Observabilidad

| Componente   | Tecnología        | Función             |
| ------------ | ----------------- | ------------------- |
| **Tracing**  | OpenTelemetry     | trace_id end-to-end |
| **Logging**  | Structlog         | JSON estructurado   |
| **Errors**   | Sentry            | Error tracking      |
| **Metrics**  | Prometheus        | Collection          |
| **AI Usage** | Dashboard interno | Tokens/costos       |

### 13.2 Tareas de Observabilidad

| ID     | Tarea                    | Estado         | Esfuerzo |
| ------ | ------------------------ | -------------- | -------- |
| 13.2.1 | trace_id end-to-end      | ⏳ PENDIENTE   | M        |
| 13.2.2 | logging JSON (Structlog) | 🔄 EN PROGRESO | S        |
| 13.2.3 | visualización grafos IA  | ⏳ PENDIENTE   | M        |
| 13.2.4 | Integración Sentry       | ⏳ PENDIENTE   | M        |
| 13.2.5 | AI Usage Dashboard       | ⏳ PENDIENTE   | L        |
| 13.2.6 | Budget alerts $30/día    | ⏳ PENDIENTE   | M        |

### 13.3 Budget Circuit Breaker

```python
BUDGET_CONFIG = {
    "daily_limit_usd": 30.00,
    "thresholds": {
        "warning": 0.80,      # 80% -> Alert admin
        "throttle": 0.95,     # 95% -> Throttle non-critical
        "block": 1.00         # 100% -> Block new requests
    }
}

async def check_budget_and_execute(operation):
    current_spend = await get_daily_spend()
    percentage = current_spend / BUDGET_CONFIG["daily_limit_usd"]

    if percentage >= 1.00:
        raise BudgetExceededException("Daily budget exhausted")
    if percentage >= 0.95:
        await throttle_request()
    if percentage >= 0.80:
        await send_budget_warning(current_spend, percentage)

    return await operation()
```

---

## 14. Fase 3: Compliance y Auditoría

**Responsable:** Legal + Security Lead + Arquitecto  
**Estado:** ⏳ PENDIENTE  
**Prioridad:** 🟠 ALTA

### 14.1 Audit Trail

#### 14.1.1 Estructura de Audit Log

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    action_category VARCHAR(50),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    old_value JSONB,
    new_value JSONB,
    source VARCHAR(20) NOT NULL,
    source_detail JSONB,
    trace_id VARCHAR(64),
    ip_address INET
);

CREATE INDEX idx_audit_tenant_time ON audit_logs(tenant_id, timestamp DESC);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
```

#### 14.1.2 Eventos Auditados

| Categoría        | Eventos                                      | Source |
| ---------------- | -------------------------------------------- | ------ |
| **User Actions** | alert.approved, alert.rejected, note.added   | human  |
| **System**       | document.processed, score.calculated         | system |
| **LLM**          | analysis.completed, extraction.completed     | llm    |
| **MCP**          | mcp.operation_allowed, mcp.operation_blocked | mcp    |
| **Security**     | pii.detected, auth.failed                    | system |

### 14.2 Anti-Gaming Policy

| Patrón                    | Descripción                        | Detección         | Acción                |
| ------------------------- | ---------------------------------- | ----------------- | --------------------- |
| **Mass Changes**          | Más de 10 cambios por hora         | Contador temporal | Flag revisión         |
| **Resolve-Reintroduce**   | Misma alerta 3+ veces              | Hash contenido    | Penalización -5pts    |
| **Suspicious High Score** | Mayor 90% con menos de 5 docs      | Correlación       | Auditoría obligatoria |
| **Weight Manipulation**   | Más de 20% cambio en 24h           | Delta tracking    | Notificación admin    |
| **Bulk Approve**          | Más de 20 alertas en menos de 5min | Rate analysis     | Require justification |

### 14.3 PII y GDPR

| Requisito         | Implementación        | Estado       |
| ----------------- | --------------------- | ------------ |
| Detección PII     | Anonymizer Service    | ⏳ PENDIENTE |
| Derecho al olvido | API de eliminación    | ⏳ PENDIENTE |
| Portabilidad      | Export JSON/CSV       | ⏳ PENDIENTE |
| Consentimiento    | Disclaimer + checkbox | ⏳ PENDIENTE |

### 14.4 Disclaimer Legal

El sistema requiere aceptación explícita de términos de uso antes de acceder:

**Contenido del Disclaimer:**

- C2Pro es herramienta de análisis asistido (no sustituye asesoría legal)
- Los análisis pueden contener imprecisiones
- Usuario responsable de verificar información crítica
- Checkboxes obligatorios de aceptación

### 14.5 Tareas de Compliance

| ID     | Tarea                    | Estado         | Esfuerzo |
| ------ | ------------------------ | -------------- | -------- |
| 14.5.1 | Implementar audit_logs   | ⏳ PENDIENTE   | L        |
| 14.5.2 | Anti-Gaming Policy       | 🔄 EN PROGRESO | L        |
| 14.5.3 | Cumplimiento GDPR básico | ⏳ PENDIENTE   | M        |
| 14.5.4 | Disclaimer UI            | ⏳ PENDIENTE   | M        |
| 14.5.5 | API eliminación datos    | ⏳ PENDIENTE   | M        |

---

## 15. Fase 3: Documentación Viva

**Responsable:** Arquitecto Principal + Tech Leads  
**Estado:** 🔄 EN PROGRESO

### 15.1 ADRs (Architecture Decision Records)

| ADR     | Título                                                | Estado    | Fecha      |
| ------- | ----------------------------------------------------- | --------- | ---------- |
| ADR-001 | Monolito Modular sobre Microservicios                 | Aprobado  | 2026-01-15 |
| ADR-002 | Arquitectura Hexagonal por Módulo                     | Aprobado  | 2026-01-18 |
| ADR-003 | LangGraph como Orquestador                            | Aprobado  | 2026-01-20 |
| ADR-004 | Claude Sonnet 4 como LLM Primario                     | Aprobado  | 2026-01-25 |
| ADR-005 | Cloudflare R2 para Storage                            | Aprobado  | 2026-01-28 |
| ADR-006 | Coherence Engine v2 con 6 Categorías                  | Draft     | 2026-01-31 |
| ADR-007 | MCP Gateway Security Model                            | Pendiente | -          |
| ADR-008 | Reglas de Capa Frontend (Server vs Client Components) | Aprobado  | 2026-02-12 |

### 15.2 Tareas de Documentación

| ID     | Tarea                       | Estado         | Esfuerzo |
| ------ | --------------------------- | -------------- | -------- |
| 15.2.1 | Mantener ADRs actualizados  | 🔄 EN PROGRESO | Continuo |
| 15.2.2 | Diagramas C4 completos      | ⏳ PENDIENTE   | L        |
| 15.2.3 | API Reference auto-generada | ⏳ PENDIENTE   | M        |

---

## 16. Roadmap de Despliegue y Riesgos

**Responsable:** Arquitecto Principal + Product  
**Estado:** ⏳ PENDIENTE

### 16.1 Fases de Despliegue

| Fase      | Período | Alcance          | Hitos                                |
| --------- | ------- | ---------------- | ------------------------------------ |
| **ALPHA** | Q1 2026 | Internal testing | Coherence v2, 6 Módulos, Hexagonal   |
| **BETA**  | Q2 2026 | 5 Pilots         | MCP Gateway, Anti-Gaming, Full Audit |
| **GA**    | Q3 2026 | Public Launch    | 100 tenants, SLA 99.9%, SOC2 ready   |

### 16.2 Matriz de Riesgos

| ID  | Riesgo                        | Prob. | Impacto | Mitigación              |
| --- | ----------------------------- | ----- | ------- | ----------------------- |
| R1  | Costos IA exceden presupuesto | Media | Alto    | Budget circuit breaker  |
| R2  | Latencia LLM inaceptable      | Media | Alto    | Fallback + cache        |
| R3  | Vulnerabilidad MCP            | Baja  | Crítico | Allowlist + audit       |
| R4  | Data breach PII               | Baja  | Crítico | Anonymizer + encryption |
| R5  | Gaming del score              | Alta  | Medio   | Anti-Gaming Policy      |
| R6  | Dependencia vendor LLM        | Media | Alto    | Multi-provider          |
| R7  | Escalabilidad workers         | Media | Medio   | Auto-scaling            |
| R8  | Compliance GDPR               | Baja  | Alto    | Audit trail + deletion  |

### 16.3 Plan de Contingencia

| Escenario               | Trigger              | Acción                 |
| ----------------------- | -------------------- | ---------------------- |
| Anthropic API down      | Más de 5min downtime | Switch to OpenAI       |
| Budget 100%             | Daily limit reached  | Block new LLM requests |
| Security incident       | Anomaly detected     | Isolate tenant + alert |
| Performance degradation | P95 mayor a 5s       | Scale workers          |

### 16.4 Tareas de Despliegue

| ID     | Tarea                            | Estado       | Esfuerzo |
| ------ | -------------------------------- | ------------ | -------- |
| 16.4.1 | Mapear fases a hitos             | ⏳ PENDIENTE | M        |
| 16.4.2 | Identificar riesgos y mitigación | ⏳ PENDIENTE | M        |
| 16.4.3 | Criterios go/no-go               | ⏳ PENDIENTE | S        |
| 16.4.4 | Plan de rollback                 | ⏳ PENDIENTE | M        |

---

## Anexo A: Checklist de Consolidación Cross-Módulo (Fase 1)

**Estado Final: COMPLETADO (2026-01-29)**

- [x] Eliminar imports ORM cruzados en adapters HTTP
- [x] Crear puertos de consulta mínimos entre módulos
- [x] Migrar servicios con ORM cruzado a puertos/DTOs
- [x] Aislar adapters transicionales con TODO
- [x] Reducir relaciones ORM cross-módulo a FKs simples
- [x] Documentar contratos públicos por módulo
- [x] Verificar cumplimiento con rg

**Comando de Verificación:**

```bash
rg "from.*adapters\.persistence\.models" apps/api/src/*/application/
# Resultado esperado: No matches found
```

---

## Anexo B: Definition of Done (DoD)

| Criterio                         | Verificación      | Estado     |
| -------------------------------- | ----------------- | ---------- |
| rg sin imports ORM               | Comando retorna 0 | Completado |
| Puertos interfaces puras         | Type checking     | Completado |
| Routers solo orquestan           | Code review       | Completado |
| Contratos documentados           | docs/             | Completado |
| Adapters transicionales aislados | TODOs             | Completado |

---

## Anexo C: Changelog v2.0 a v2.1

**Fecha:** 2026-01-31

### Nuevas Secciones Añadidas

| Sección                          | Descripción                | Prioridad |
| -------------------------------- | -------------------------- | --------- |
| 6.3 MCP Gateway                  | Seguridad perimetral MCP   | CRÍTICA   |
| 6.4 Anonymizer Service           | Anonimización PII          | CRÍTICA   |
| 6.5 Infraestructura Persistencia | Stack + tabla clauses      | CRÍTICA   |
| 7.4 Estrategia LLM               | Claude primario + fallback | ALTA      |
| 9.1 Coherence Engine v2          | 6 categorías + anti-gaming | CRÍTICA   |
| 9.3 Integración WBS-Procurement  | Lead Time Calculator       | ALTA      |
| 10 Arquitectura Asíncrona        | Celery + Event Bus         | ALTA      |
| 14 Compliance y Auditoría        | Audit + GDPR + Disclaimer  | ALTA      |

### Correcciones Críticas

| Corrección         | Antes           | Después         |
| ------------------ | --------------- | --------------- |
| Storage documentos | No especificado | Cloudflare R2   |
| LLM primario       | No especificado | Claude Sonnet 4 |
| LLM fallback       | No especificado | GPT-4o          |
| Embeddings         | No especificado | Voyage AI       |

### Alineación con Diagrama v2.2.1

| Componente             | Plan v2.0 | Plan v2.1     |
| ---------------------- | --------- | ------------- |
| MCP Gateway            | Ausente   | Sección 6.3   |
| Coherence 6 Categorías | Genérico  | Sección 9.1   |
| Anonymizer Service     | Ausente   | Sección 6.4   |
| Cloudflare R2          | Ausente   | Sección 6.5   |
| Claude Sonnet 4        | Ausente   | Sección 7.4   |
| Lead Time Calculator   | Ausente   | Sección 9.3   |
| Tabla clauses          | Ausente   | Sección 6.5.2 |
| Event Bus              | Implícito | Sección 10    |
| Sentry                 | Ausente   | Sección 13    |
| Anti-Gaming            | Ausente   | Sección 14.2  |
| Audit Trail            | Ausente   | Sección 14.1  |
| Disclaimer             | Ausente   | Sección 14.4  |

---

## Firmas de Aprobación

| Rol                  | Nombre                     | Fecha      | Firma     |
| -------------------- | -------------------------- | ---------- | --------- |
| Arquitecto Principal | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | Pendiente |
| Tech Lead            | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | Pendiente |
| Security Lead        | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | Pendiente |
| Product Owner        | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | Pendiente |
| AI Lead              | **\*\*\*\***\_**\*\*\*\*** | 2026-01-31 | Pendiente |

---

**Documento generado por:** Architecture Review Board  
**Fecha:** 2026-01-31  
**Versión:** 2.1.1  
**Estado:** APROBADO - Pendiente firmas  
**Próxima revisión:** 2026-02-28

---

## Changelog v2.1 → v2.1.1

**Fecha:** 2026-02-14

| Sección            | Cambio                                               | Razón                                                                  |
| ------------------ | ---------------------------------------------------- | ---------------------------------------------------------------------- |
| Sec 2 (Roadmap)    | Fase 1: 95% → 85%, Fase 2: 40% → 65%                 | Ajuste realista: Sec 6 incompleta, suites TDD avanzadas                |
| Sec 3 (Métricas)   | Coherence 60% → 85%, MCP 75% → 100%, +3 nuevas filas | Refleja suites completadas y estado actual                             |
| Sec 3 (Estructura) | Agregados 8 módulos faltantes al árbol               | Codebase tiene anonymizer, alerts, mcp, modules/, etc.                 |
| Sec 9.3.5.1-4      | PENDIENTE → COMPLETADO                               | Ya implementados como parte de suites TS-UD-PRJ-DTO-001, TS-UD-PROC-\* |
| Sec 12 (Frontend)  | S2-10 SSE processing stepper + withCredentials → ✅  | Cobertura RED/GREEN en unit + integración MSW (FLAG-3)                 |
| Sec 3 / Phase 4    | AI Pipeline I1-I2 (Ingestion + OCR/Table) → ✅       | Cierre de Sprint 1 Core AI con suites TS-I1-CIC-001 y TS-I2-OCR-TBL-001 |
| Sec 3 / Phase 4    | AI Pipeline I3-I4 (Extraction + Retrieval) → ✅      | Cierre de Sprint 2 Core AI con suites TS-I3-\* y TS-I4-\* + TS-SEC-EXT-RET-001 |
| Sec 3 / Phase 4    | AI Pipeline I5-I6 (Graph + Coherence) → ✅           | Cierre de Sprint 3 Core AI con suites TS-I5-\* y TS-I6-\* + TS-SEC-GRAPH-COH-001 |
| Sec 3 / Phase 4    | AI Pipeline I7-I9 (Scoring + WBS/BOM + Procurement) → ✅ | Cierre de Sprint 4 Core AI con suites TS-I7-\*, TS-I8-\*, TS-I9-\* + TS-SEC-S4-001 |
| Sec 3 / Phase 4    | AI Pipeline I10-I12 (Stakeholders + HITL + Observability) → ✅ | Cierre de Sprint 5 Core AI con suites TS-I10-\*, TS-I11-\*, TS-I12-\* + TS-SEC-S5-001 + TS-DEVOPS-S5-001 |
| Sec 3 / Phase 4    | AI Pipeline I13 real E2E path → ✅ | Contrato de ruta I13 + harness auth/tenant determinístico + CI S6 bloqueante `i13-real-e2e` |
| Sec 12.7           | Nuevo contrato operativo I13 real E2E + rationale de parche de migración | Formaliza prerrequisitos, riesgos y runbook (`docs/runbooks/I13_REAL_E2E_INFRA_RUNBOOK.md`) |
| Sec 10.2 / 10.4.4  | Catálogo Event Bus Redis + reglas de tenant scope/metadata → ✅ | Formaliza canal `c2pro.{env}.{tenant_id}.{topic}` y cierre documental del Event Bus |
| Sec 6 / Sec 12.7   | Contrato RLS GUC `app.current_tenant` hardening → ✅ | Se agrega bootstrap de GUC a nivel conexión PostgreSQL + validación RED/GREEN de suite E2E de aislamiento tenant |
