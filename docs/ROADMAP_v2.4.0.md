# C2Pro Product Roadmap
**Contract Intelligence Platform - Master Development Plan**

**Versión:** 2.4.0
**Última actualización:** 05 de Enero de 2026
**Autor:** Jesús - Strategic Procurement Director
**Clasificación:** CONFIDENCIAL

---

## Índice

1. [Visión y Propuesta de Valor](#1-visión-y-propuesta-de-valor)
2. [Principios Rectores](#2-principios-rectores)
3. [Stack Tecnológico](#3-stack-tecnológico)
4. [Arquitectura del Sistema](#4-arquitectura-del-sistema)
5. [Modelo de Datos](#5-modelo-de-datos)
6. [Seguridad y Compliance](#6-seguridad-y-compliance) ← **NUEVO**
7. [CTO Gates Checklist](#7-cto-gates-checklist) ← **NUEVO**
8. [MVP - Fase 1 (12 Semanas)](#8-mvp---fase-1-12-semanas)
9. [Fase 2 - Copiloto de Compras](#9-fase-2---copiloto-de-compras)
10. [Fase 3 - Control de Ejecución](#10-fase-3---control-de-ejecución)
11. [Fase 4 - Futuro (2026+)](#11-fase-4---futuro-2026)
12. [Coherence Score Specification](#12-coherence-score-specification) ← **NUEVO**
13. [Métricas de Éxito](#13-métricas-de-éxito)
14. [Gestión de Riesgos](#14-gestión-de-riesgos)
15. [Plan de Testing](#15-plan-de-testing)
16. [Plan de Deployment](#16-plan-de-deployment)
17. [Anexos](#17-anexos)

---

## Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 15/12/2024 | Documento inicial |
| 2.0.0 | 29/12/2024 | Reescritura completa |
| 2.1.0 | 29/12/2024 | WBS y BOM como prerequisitos |
| 2.2.0 | 29/12/2024 | Sistema procurement con Incoterms |
| 2.3.0 | 03/01/2026 | Stakeholder Intelligence, MCP, Graph RAG, Multi-Agent |
| **2.4.0** | **05/01/2026** | **HARDENING & CTO-READY** (ver detalle abajo) |

---

## Detalle de Cambios v2.4.0

### Correcciones Críticas de Seguridad

| Cambio | Impacto | Sección |
|--------|---------|---------|
| **RLS completo** en 14 tablas (antes 7) | Aislamiento multi-tenant real | §5, §6 |
| **UNIQUE(tenant_id, email)** en users | Soporte B2B enterprise | §5.3 |
| **Cast UUID en policies** | Evita fallos silenciosos | §5.4 |
| **MCP Database allowlist** | Elimina SQL injection risk | §4.4 |
| **Clauses como entidad** con FKs | Trazabilidad legal real | §5.3 |
| **Knowledge graph nodes** | Integridad referencial | §5.3 |

### Nuevas Secciones

| Sección | Descripción |
|---------|-------------|
| **§6 Seguridad y Compliance** | Cifrado, retención, PII, GDPR, logging IA |
| **§7 CTO Gates Checklist** | 8 gates go/no-go por fase |
| **§12 Coherence Score Spec** | Fórmula formal, pesos, calibración, anti-gaming |

### Reorganización del Backlog

| Antes (v2.3.0) | Ahora (v2.4.0) | Razón |
|----------------|----------------|-------|
| Sem 1-2: Foundation | Sprint 0: Foundation + **Guardrails** | Security first |
| Sem 3-4: Documents | Sprint 1-2: Ingesta + **Clauses entity** | Trazabilidad legal |
| Sem 5-6: IA Core | Sprint 3: Coherencia v0 | Reordena prioridades |
| Sem 7-8: Coherence | Sprint 4: UI mínima pilotos | Feedback temprano |

### Decisiones de Producto

| Decisión | Resultado |
|----------|-----------|
| **Implicit Needs Inference** | Movido a Fase 3 como experimental opt-in |
| **Human-in-the-loop** | Obligatorio para outputs de riesgo/contrato |
| **Maturity levels** | Añadido por feature (Prototype/Pilot/Production) |

---

## 1. Visión y Propuesta de Valor

### 1.1 Visión

> **"Hacer de C2Pro el sistema operativo cognitivo que toda empresa de construcción EPC necesita para conectar contrato, ingeniería y ejecución en un flujo unificado."**

### 1.2 El Problema

El **15-30% de los sobrecostes** en proyectos EPC se deben a la desconexión sistémica entre:

- **Contrato (Legal):** Cláusulas, plazos, penalizaciones, stakeholders
- **Ingeniería (Técnico):** WBS, especificaciones, alcance
- **Cronograma (Temporal):** Actividades, hitos, dependencias
- **Presupuesto (Económico):** Partidas, mediciones, precios
- **Compras (Supply Chain):** BOM, proveedores, lead times

### 1.3 Propuesta de Valor Única

> **"C2Pro es el único sistema que conecta automáticamente CONTRATO LEGAL con EJECUCIÓN FÍSICA a través de INGENIERÍA y COMPRAS como sistema cognitivo unificado."**

### 1.4 Disclaimer Legal (OBLIGATORIO en UI y docs)

> ⚠️ **AVISO IMPORTANTE**
> 
> C2Pro no constituye asesoramiento legal ni sustituye la interpretación profesional de contratos. El sistema identifica potenciales incoherencias y proporciona hipótesis trazables con referencias a cláusulas específicas. Todas las conclusiones deben ser validadas por profesionales cualificados antes de tomar decisiones.

### 1.5 Diferenciadores Clave

| Diferenciador | Beneficio | Evidencia |
|---------------|-----------|-----------|
| Auditoría Tridimensional | Detecta incoherencias en minutos | Ahorro 8-16h/proyecto |
| IA Especializada EPC | Entiende cláusulas, WBS, BOM | >85% accuracy |
| Coherence Score 0-100 | Cuantifica riesgo | Fórmula documentada |
| Stakeholder Intelligence | Mapea stakeholders auto | RACI generado |
| Graph RAG Trazabilidad | Contract→WBS→BOM→Stakeholder | FK reales |
| Human-in-the-loop | Validación obligatoria | Legal shield |

### 1.6 Posicionamiento Competitivo

**Análisis de 17 competidores:**

| Categoría | Competidores | C2Pro Diferente |
|-----------|--------------|-----------------|
| Sourcing | Keelvar, GEP, Fairmarkit | + WBS/BOM desde contrato |
| Contract Mgmt | Icertis, Ironclad, Agiloft | + Coherencia back-to-back |
| PO Automation | Zip, Coupa, Procurify | + Trazabilidad legal con FKs |
| Decision Intel | Aera, o9, Pactum | + Específico EPC, closed-loop |

**Gaps que NINGÚN competidor cubre:**
- ✅ Generación WBS/BOM desde texto contractual
- ✅ Coherencia back-to-back con trazabilidad legal (FK a cláusulas)
- ✅ MRP Cognitivo alineado a cronograma
- ✅ Closed-loop con validación visual
- ✅ Human-in-the-loop obligatorio

---

## 2. Principios Rectores

### 2.1 Principios de Producto

1. **User-Centric:** Features validadas con entrevistas
2. **AI-Assisted, Human-Validated:** IA propone, humano decide
3. **Actionable Insights:** No solo detectar, proponer soluciones
4. **Nicho Deep:** Dominar EPC antes de expandir
5. **Trazabilidad Legal:** Cada output referencia su origen

### 2.2 Principios Técnicos

1. **Security First:** RLS completo, cifrado, auditoría
2. **Multi-tenant by Design:** Aislamiento desde día 1
3. **Observability Built-in:** Logging estructurado, cost control
4. **Graph-First:** Knowledge graphs para relaciones
5. **Human-in-the-Loop:** Obligatorio para outputs críticos

### 2.3 Principios de Desarrollo

1. **Ship Fast, Learn Faster:** Ciclos 2 semanas
2. **Quality Gates:** No avanzar sin tests críticos
3. **Document as You Build:** ADRs para decisiones
4. **CTO Gates:** Checklist antes de cada fase

---

## 3. Stack Tecnológico

### 3.1 Stack Completo

| Capa | Tecnología | Versión | Justificación |
|------|------------|---------|---------------|
| **Frontend** | Next.js | 14+ | SSR, Vercel deploy |
| | React | 18+ | Ecosystem |
| | Tailwind CSS | 3+ | Rapid prototyping |
| | shadcn/ui | latest | Accesible, customizable |
| **Backend** | FastAPI | 0.104+ | Async, Pydantic v2 |
| | Python | 3.11+ | AI/ML ecosystem |
| **Database** | PostgreSQL | 15+ | ACID, RLS nativo |
| | Supabase | Managed | Auth, backups, PITR |
| **Cache** | Redis/Upstash | 7+ | Rate limiting, cache |
| **Storage** | Cloudflare R2 | - | Sin egress fees, cifrado |
| **IA** | Claude Sonnet 4 | latest | 200K context |
| | Claude Haiku 4 | latest | Fast, económico |
| **MCP** | Protocol | 2025-11 | Estándar abierto |
| **Graph** | NetworkX | latest | Graph RAG MVP |
| **Orchestration** | LangGraph | latest | Multi-agent |
| **Observability** | Sentry | Free | Error tracking |
| | Structlog | latest | JSON logging |

### 3.2 Model Routing Rules

```yaml
model_routing:
  contract_extraction:
    model: "claude-sonnet-4"
    reason: "Documentos largos, alta precisión"
    max_tokens: 4096
    temperature: 0.1
    
  stakeholder_classification:
    model: "claude-haiku-4"
    reason: "Tarea simple, volumen alto"
    max_tokens: 256
    temperature: 0.0
    
  coherence_check:
    model: "claude-haiku-4"
    reason: "Reglas determinísticas"
    max_tokens: 512
    temperature: 0.0
    
  raci_generation:
    model: "claude-sonnet-4"
    reason: "Razonamiento complejo"
    max_tokens: 2048
    temperature: 0.2
    
  multimodal_expediting:
    model: "claude-sonnet-4-vision"
    reason: "Análisis de imágenes"
    max_tokens: 1024
    temperature: 0.1
```

---

## 4. Arquitectura del Sistema

### 4.1 Diagrama de Arquitectura v2.4.0

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE PRESENTACIÓN                                 │
│                  Next.js 14 + Tailwind + shadcn/ui                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Dashboard │  │Projects  │  │Evidence  │  │ Alerts   │  │Stakeholder│      │
│  │  + Score │  │  + Docs  │  │  Viewer  │  │  Panel   │  │   Map    │      │
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
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐                │
│  │Stakeholder │ │  Clauses   │ │Procurement │ │    MCP     │                │
│  │   Router   │ │   Router   │ │   Router   │ │  Gateway   │                │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CAPA DE AGENTES (Multi-Agent via MCP)                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Contract     │ │   Clause     │ │    WBS       │ │    BOM       │        │
│  │ Parser Agent │ │Extractor Agent│ │Generator Agent│ │Builder Agent │        │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Stakeholder  │ │  Coherence   │ │    RACI      │ │    Alert     │        │
│  │Extractor Agent│ │Checker Agent │ │Generator Agent│ │ Router Agent │        │
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
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  Clause  │ │   RACI   │ │  Alert   │ │   BOM    │ │   Cost   │          │
│  │ Service  │ │Generator │ │  Router  │ │ Version  │ │ Control  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
          │              │                │              │
          ▼              ▼                ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
    │PostgreSQL│  │  Redis   │  │    R2    │  │  Claude API  │
    │(Supabase)│  │(Upstash) │  │(Encrypted)│  │  (Anthropic) │
    │          │  │          │  │          │  │              │
    │ - RLS 14 │  │ - Cache  │  │- Docs    │  │- Sonnet 4    │
    │   tablas │  │ - Rate   │  │- Cifrado │  │- Haiku 4     │
    │ - PITR   │  │   Limit  │  │- Retenc. │  │- No training │
    │ - Audit  │  │ - Pub/Sub│  │          │  │- Zero retain │
    └──────────┘  └──────────┘  └──────────┘  └──────────────┘
```

### 4.2 Flujo de Datos con Trazabilidad Legal

```
[Usuario] → Upload Docs (Contract, Schedule, Budget)
    │
    ▼
[Document Service] → Parser (PDF/Excel/BC3)
    │
    ▼
[Clause Extractor Agent] → Extrae cláusulas con IDs estables
    │                           │
    │                           ▼
    │                      ┌─────────────┐
    │                      │   CLAUSES   │ ← Entidad con FK
    │                      │   TABLE     │
    │                      │ id, code,   │
    │                      │ text, type  │
    │                      └──────┬──────┘
    │                             │
    ├─────────────────────────────┼─────────────────────────┐
    │                             │                         │
    ▼                             ▼                         ▼
[Stakeholder              [WBS Generator]           [BOM Builder]
 Extractor]                     │                         │
    │                           │                         │
    │ source_clause_id (FK)     │ funded_by_clause_id     │ contract_clause_id (FK)
    │                           │                         │
    ▼                           ▼                         ▼
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│STAKEHOLDERS │          │  WBS_ITEMS  │          │  BOM_ITEMS  │
│             │          │             │          │             │
│ clause_id───┼──────────┼─────────────┼──────────┼───clause_id │
└─────────────┘          └─────────────┘          └─────────────┘
         │                      │                        │
         └──────────────────────┼────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │    KNOWLEDGE GRAPH    │
                    │                       │
                    │  Nodes + Edges con    │
                    │  referencias a        │
                    │  clause_id reales     │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   COHERENCE ENGINE    │
                    │                       │
                    │ Alertas con:          │
                    │ - source_clause_id    │
                    │ - affected_wbs_ids    │
                    │ - affected_bom_ids    │
                    │ - evidence completa   │
                    └───────────────────────┘
```

### 4.3 Arquitectura Multi-Agente

| Agente | Responsabilidad | Input | Output | Modelo | Human-in-loop |
|--------|----------------|-------|--------|--------|---------------|
| ContractParserAgent | Extrae estructura | PDF | JSON | Sonnet 4 | No |
| **ClauseExtractorAgent** | Extrae cláusulas con IDs | PDF | Clauses[] | Sonnet 4 | **Sí (verificar)** |
| StakeholderExtractorAgent | Identifica stakeholders | PDF + clauses | Stakeholders[] | Sonnet 4 | **Sí (verificar)** |
| WBSGeneratorAgent | Genera WBS | Extractions | WBS[] | Sonnet 4 | **Sí (aprobar)** |
| BOMBuilderAgent | Crea BOM | WBS + Budget | BOM[] | Sonnet 4 | **Sí (aprobar)** |
| CoherenceCheckerAgent | Detecta incoherencias | Graph | Alerts[] | Haiku 4 | No |
| RACIGeneratorAgent | Mapea RACI | Stakeholders + WBS | RACI[] | Haiku 4 | **Sí (revisar)** |
| AlertRouterAgent | Rutea alertas | Alerts + RACI | Notifications | Haiku 4 | No |

### 4.4 MCP Server Configuration (SECURIZADO)

```python
# apps/api/src/mcp/servers/database_server.py

class DatabaseMCPServer:
    """
    MCP Server para acceso a base de datos.
    
    SEGURIDAD: NO permite SQL arbitrario.
    Solo vistas y funciones predefinidas.
    """
    
    # ALLOWLIST de operaciones permitidas
    ALLOWED_VIEWS = [
        "v_project_summary",
        "v_project_alerts",
        "v_project_clauses",
        "v_project_stakeholders",
        "v_project_wbs",
        "v_project_bom",
        "v_coherence_breakdown",
        "v_raci_matrix",
    ]
    
    ALLOWED_FUNCTIONS = [
        "fn_get_clause_by_id",
        "fn_get_stakeholder_by_id",
        "fn_get_neighbors",
        "fn_find_path",
        "fn_get_subgraph",
    ]
    
    # LÍMITES por query
    QUERY_LIMITS = {
        "statement_timeout": "5s",
        "row_limit": 1000,
        "max_cost": 10000,
    }
    
    # Rate limiting por tenant
    RATE_LIMITS = {
        "requests_per_minute": 60,
        "requests_per_hour": 500,
    }
    
    async def query_view(
        self,
        view_name: str,
        project_id: UUID,
        filters: dict = None
    ) -> QueryResult:
        """
        Ejecuta query sobre vista permitida.
        
        - Valida view_name está en ALLOWLIST
        - Aplica filtro project_id obligatorio (RLS adicional)
        - Aplica límites
        - Loguea para auditoría
        """
        if view_name not in self.ALLOWED_VIEWS:
            raise SecurityError(f"View {view_name} not allowed")
        
        # Query con límites
        result = await self._execute_with_limits(
            f"SELECT * FROM {view_name} WHERE project_id = $1",
            [project_id],
            self.QUERY_LIMITS
        )
        
        # Audit log
        await self._log_query(view_name, project_id, len(result))
        
        return result
    
    async def call_function(
        self,
        function_name: str,
        params: dict
    ) -> FunctionResult:
        """
        Ejecuta función permitida.
        """
        if function_name not in self.ALLOWED_FUNCTIONS:
            raise SecurityError(f"Function {function_name} not allowed")
        
        # ... implementación con límites y logging
```

### 4.5 Stakeholder Intelligence Module

#### Componentes (sin Implicit Needs en MVP)

```python
# apps/api/src/services/stakeholder/

class StakeholderExtractor:
    """Extrae stakeholders de contratos usando NLP"""
    
    async def extract_from_contract(
        self, 
        document_id: UUID,
        clauses: list[Clause]  # Ahora recibe cláusulas con IDs
    ) -> list[Stakeholder]:
        """
        Extrae stakeholders CON referencia a clause_id.
        """

class StakeholderClassifier:
    """Clasifica por poder/interés"""
    
    QUADRANTS = {
        ("high", "high"): "key_player",
        ("high", "low"): "keep_satisfied",
        ("low", "high"): "keep_informed",
        ("low", "low"): "monitor"
    }

class RACIGenerator:
    """Genera matriz RACI"""
    
    async def generate_raci(
        self,
        project_id: UUID,
        require_human_approval: bool = True  # OBLIGATORIO por defecto
    ) -> RACIResult:
        """
        Genera RACI con flag de human-in-the-loop.
        """

class StakeholderAlertRouter:
    """Rutea alertas a stakeholders"""
    
    ROUTING_RULES = {
        "date_mismatch": ["project_manager", "planner"],
        "budget_overrun": ["project_manager", "finance"],
        "safety_risk": ["hse_officer", "project_manager"],
        "quality_deviation": ["quality_manager", "engineering"],
        "supplier_delay": ["procurement", "project_manager"],
        "critical_path_impact": ["project_manager", "client"],
        "clause_violation": ["legal", "project_manager"],  # NUEVO
    }
```

#### Implicit Needs Inference (FASE 3 - EXPERIMENTAL)

```python
# apps/api/src/services/stakeholder/implicit_needs.py

class ImplicitNeedsInferrer:
    """
    EXPERIMENTAL - Solo disponible en Fase 3+
    
    Requisitos:
    - Opt-in explícito por tenant
    - Modo advisory-only (nunca auto-action)
    - Explainability obligatorio
    - Audit log completo
    """
    
    def __init__(self):
        self.enabled_by_default = False  # OPT-IN
        self.mode = "advisory"  # Nunca auto-action
        self.explainability_required = True
        self.phase_available = 3  # No disponible antes
    
    async def infer_needs(
        self,
        stakeholder: Stakeholder,
        context: ProjectContext
    ) -> Optional[ImplicitNeedsResult]:
        """
        Solo ejecuta si:
        1. Tenant tiene opt-in activo
        2. Usuario tiene permiso
        3. Fase >= 3
        """
        if not self._is_enabled_for_tenant(context.tenant_id):
            return None
        
        if context.current_phase < self.phase_available:
            return None
        
        result = await self._infer(stakeholder, context)
        
        # OBLIGATORIO: explicar el "por qué"
        result.explanation = self._generate_explanation(result)
        result.confidence = self._calculate_confidence(result)
        result.disclaimer = (
            "ADVISORY ONLY. Esta inferencia es experimental. "
            "Verificar directamente con el stakeholder."
        )
        
        # Audit log
        await self._log_inference(stakeholder.id, result)
        
        return result
```

### 4.6 Graph RAG Architecture

#### Knowledge Graph con Integridad Referencial

```sql
-- NODOS: Entidad central para integridad
CREATE TABLE knowledge_graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    label VARCHAR(255),
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, entity_type, entity_id)
);

-- EDGES: Ahora con FK a nodos
CREATE TABLE knowledge_graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    source_node_id UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    
    relationship_type VARCHAR(100) NOT NULL,
    properties JSONB DEFAULT '{}',
    confidence NUMERIC(3,2) DEFAULT 1.0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(project_id, source_node_id, target_node_id, relationship_type)
);

-- Índices
CREATE INDEX idx_kg_nodes_project ON knowledge_graph_nodes(project_id);
CREATE INDEX idx_kg_nodes_type ON knowledge_graph_nodes(entity_type);
CREATE INDEX idx_kg_edges_source ON knowledge_graph_edges(source_node_id);
CREATE INDEX idx_kg_edges_target ON knowledge_graph_edges(target_node_id);
CREATE INDEX idx_kg_edges_rel ON knowledge_graph_edges(relationship_type);
```

#### Entity Types y Relationships

```yaml
entity_types:
  - contract
  - clause      # NUEVO: entidad propia
  - milestone
  - penalty
  - schedule
  - activity
  - dependency
  - budget
  - budget_item
  - wbs_item
  - bom_item
  - stakeholder
  - organization

relationship_types:
  - CONTAINS      # Contract CONTAINS Clause
  - REQUIRES      # Clause REQUIRES Activity
  - DEPENDS_ON    # Activity DEPENDS_ON Activity
  - FUNDED_BY     # WBS FUNDED_BY Budget_Item
  - NEEDS_MATERIAL # WBS NEEDS_MATERIAL BOM_Item
  - RESPONSIBLE_FOR # Stakeholder RESPONSIBLE_FOR WBS
  - ACCOUNTABLE_FOR # Stakeholder ACCOUNTABLE_FOR WBS
  - APPROVES      # Stakeholder APPROVES BOM_Item
  - PENALIZES     # Penalty PENALIZES Milestone
  - SUPPLIES      # BOM_Item SUPPLIES WBS
  - REFERENCES    # Clause REFERENCES Stakeholder
  - DEFINES       # Clause DEFINES Milestone  # NUEVO
  - RESTRICTS     # Clause RESTRICTS Activity  # NUEVO
```

---

## 5. Modelo de Datos

### 5.1 Diagrama ER Simplificado

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   TENANTS   │───┐   │   USERS     │       │  PROJECTS   │
│             │   │   │             │       │             │
│ id          │   │   │ id          │       │ id          │
│ name        │   └──►│ tenant_id   │◄──────│ tenant_id   │
│ settings    │       │ email       │       │ name        │
│ ai_budget   │       │ role        │       │ coherence_  │
└─────────────┘       │             │       │   score     │
                      │ UNIQUE:     │       └──────┬──────┘
                      │(tenant_id,  │              │
                      │ email)      │              │
                      └─────────────┘              │
                                                   │
                    ┌──────────────────────────────┼──────────────────────────┐
                    │                              │                          │
                    ▼                              ▼                          ▼
           ┌─────────────┐              ┌─────────────┐              ┌─────────────┐
           │  DOCUMENTS  │              │  CLAUSES    │◄─────────────│  ANALYSES   │
           │             │              │   (NUEVO)   │              │             │
           │ id          │◄─────────────│ id          │              │ id          │
           │ project_id  │              │ project_id  │              │ project_id  │
           │ type        │              │ document_id │              │ status      │
           │ filename    │              │ clause_code │              │ coherence_  │
           └─────────────┘              │ clause_type │              │   score     │
                                        │ full_text   │              └──────┬──────┘
                                        │ confidence  │                     │
                                        └──────┬──────┘                     │
                                               │                            │
                    ┌──────────────────────────┼────────────────────────────┤
                    │                          │                            │
                    ▼                          ▼                            ▼
           ┌─────────────┐              ┌─────────────┐              ┌─────────────┐
           │STAKEHOLDERS │              │  WBS_ITEMS  │              │   ALERTS    │
           │             │              │             │              │             │
           │ id          │              │ id          │              │ id          │
           │ project_id  │              │ project_id  │              │ project_id  │
           │ clause_id   │──────────────│ clause_id   │◄─────────────│ source_     │
           │   (FK)      │              │   (FK)      │              │  clause_id  │
           │ name        │              │ code        │              │ severity    │
           │ role        │              │ name        │              │ evidence_   │
           │ quadrant    │              │ level       │              │   json      │
           └──────┬──────┘              └──────┬──────┘              └─────────────┘
                  │                            │
                  │                            │
                  ▼                            ▼
           ┌─────────────┐              ┌─────────────┐
           │STAKEHOLDER_ │              │  BOM_ITEMS  │
           │  WBS_RACI   │              │             │
           │             │              │ id          │
           │stakeholder_id│             │ project_id  │
           │ wbs_item_id │              │ wbs_item_id │
           │ raci_role   │              │ clause_id   │──► CLAUSES
           └─────────────┘              │   (FK)      │
                                        │ item_name   │
                                        │ quantity    │
                                        │ lead_time   │
                                        └─────────────┘
```

### 5.2 Tablas Core (con RLS)

```sql
-- =====================================================
-- TENANTS
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

-- RLS: Solo admins pueden ver otros tenants
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_self_only ON tenants
    FOR ALL USING (id = (auth.jwt() ->> 'tenant_id')::uuid);

-- =====================================================
-- USERS (CORREGIDO: UNIQUE por tenant)
-- =====================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- CORREGIDO: Unicidad por tenant, no global
    UNIQUE(tenant_id, email)
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_users ON users
    FOR ALL USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

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
    coherence_score_breakdown JSONB,  -- NUEVO: detalle del score
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_projects ON projects
    FOR ALL USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

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
    storage_encrypted BOOLEAN DEFAULT TRUE,  -- NUEVO
    file_size_bytes BIGINT,
    upload_status VARCHAR(50) DEFAULT 'uploaded',
    parsed_at TIMESTAMPTZ,
    retention_until TIMESTAMPTZ,  -- NUEVO: política retención
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_documents ON documents
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );
```

### 5.3 Tablas Nuevas/Corregidas

```sql
-- =====================================================
-- CLAUSES (NUEVO - Entidad propia para trazabilidad)
-- =====================================================
CREATE TABLE clauses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    extracted_entities JSONB,  -- stakeholders, dates, amounts encontrados
    extraction_confidence NUMERIC(3,2),
    extraction_model VARCHAR(50),
    
    -- Auditoría
    manually_verified BOOLEAN DEFAULT FALSE,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(project_id, document_id, clause_code)
);

ALTER TABLE clauses ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_clauses ON clauses
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

CREATE INDEX idx_clauses_project ON clauses(project_id);
CREATE INDEX idx_clauses_type ON clauses(clause_type);
CREATE INDEX idx_clauses_code ON clauses(clause_code);

-- =====================================================
-- EXTRACTIONS (con RLS)
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

ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_extractions ON extractions
    FOR ALL USING (
        document_id IN (
            SELECT d.id FROM documents d
            JOIN projects p ON d.project_id = p.id
            WHERE p.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- ANALYSES (con RLS)
-- =====================================================
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) DEFAULT 'coherence',
    status VARCHAR(50) DEFAULT 'pending',
    result_json JSONB,
    coherence_score INTEGER CHECK (coherence_score BETWEEN 0 AND 100),
    coherence_breakdown JSONB,  -- NUEVO: detalle por regla
    alerts_count INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_analyses ON analyses
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- ALERTS (con RLS y trazabilidad mejorada)
-- =====================================================
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id) ON DELETE CASCADE,
    
    -- Clasificación
    severity VARCHAR(20) NOT NULL,
    type VARCHAR(50),
    rule_id VARCHAR(20),  -- NUEVO: referencia a regla
    
    -- Contenido
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    suggested_action TEXT,
    
    -- TRAZABILIDAD MEJORADA
    source_clause_id UUID REFERENCES clauses(id),  -- NUEVO: FK a cláusula
    affected_document_ids UUID[] DEFAULT '{}',  -- NUEVO: array tipado
    affected_wbs_ids UUID[] DEFAULT '{}',
    affected_bom_ids UUID[] DEFAULT '{}',
    evidence_json JSONB,  -- Evidencia estructurada
    
    -- Estado
    status VARCHAR(50) DEFAULT 'open',
    requires_human_review BOOLEAN DEFAULT FALSE,  -- NUEVO
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    resolution_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_alerts ON alerts
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- AI_USAGE_LOGS (con RLS y campos adicionales)
-- =====================================================
CREATE TABLE ai_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id),
    user_id UUID REFERENCES users(id),
    
    -- Modelo y operación
    model VARCHAR(50),
    operation VARCHAR(100),
    prompt_version VARCHAR(50),  -- NUEVO
    
    -- Tokens y coste
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,4),
    
    -- Hashes para auditoría y cache
    input_hash VARCHAR(64),  -- NUEVO: SHA-256
    output_hash VARCHAR(64),  -- NUEVO
    
    -- Metadatos
    latency_ms INTEGER,
    cached BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE ai_usage_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_ai_logs ON ai_usage_logs
    FOR ALL USING (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);

-- =====================================================
-- STAKEHOLDERS (con FK a clauses)
-- =====================================================
CREATE TABLE stakeholders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Identificación
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
    
    -- TRAZABILIDAD: FK a cláusula origen
    source_clause_id UUID REFERENCES clauses(id),  -- CAMBIADO de source_clause_ref
    extraction_confidence NUMERIC(3,2),
    
    -- Auditoría
    is_auto_extracted BOOLEAN DEFAULT TRUE,
    manually_verified BOOLEAN DEFAULT FALSE,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE stakeholders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_stakeholders ON stakeholders
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- WBS_ITEMS (con FK a clauses)
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
    
    -- Referencias
    schedule_activity_ids JSONB,
    budget_item_ids JSONB,
    funded_by_clause_id UUID REFERENCES clauses(id),  -- NUEVO
    
    -- Responsable
    responsible VARCHAR(255),
    
    -- Estimaciones
    estimated_duration_days INTEGER,
    estimated_cost NUMERIC(12,2),
    is_critical_path BOOLEAN DEFAULT FALSE,
    
    -- Auditoría
    requires_approval BOOLEAN DEFAULT FALSE,  -- NUEVO
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(project_id, code)
);

ALTER TABLE wbs_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_wbs ON wbs_items
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- BOM_ITEMS (con FK a clauses)
-- =====================================================
CREATE TABLE bom_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    wbs_item_id UUID REFERENCES wbs_items(id),
    parent_bom_id UUID REFERENCES bom_items(id),
    
    -- Versionado
    version_number INTEGER DEFAULT 0,
    version_status VARCHAR(50) DEFAULT 'current',

    -- Identificación
    item_code VARCHAR(100),
    item_name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    
    -- Cantidades
    unit VARCHAR(50),
    quantity NUMERIC(12,3) NOT NULL,
    unit_price NUMERIC(12,2),
    total_price NUMERIC(12,2),

    -- Proveedor y Logística
    supplier VARCHAR(255),
    origin_country VARCHAR(100),
    incoterm VARCHAR(20),

    -- Lead Times
    production_time_days INTEGER,
    transit_time_days INTEGER,
    customs_clearance_days INTEGER DEFAULT 0,
    buffer_days INTEGER DEFAULT 7,
    total_lead_time_days INTEGER,

    -- Fechas
    optimal_order_date DATE,
    required_on_site_date DATE,
    
    -- Estado
    status VARCHAR(50) DEFAULT 'planned',
    
    -- TRAZABILIDAD: FK a cláusula
    contract_clause_id UUID REFERENCES clauses(id),  -- CAMBIADO de contract_clause_ref
    specifications JSONB,
    
    -- Auditoría
    requires_approval BOOLEAN DEFAULT FALSE,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE bom_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_bom ON bom_items
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- STAKEHOLDER_WBS_RACI (con RLS)
-- =====================================================
CREATE TABLE stakeholder_wbs_raci (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stakeholder_id UUID NOT NULL REFERENCES stakeholders(id) ON DELETE CASCADE,
    wbs_item_id UUID NOT NULL REFERENCES wbs_items(id) ON DELETE CASCADE,
    
    raci_role VARCHAR(20) NOT NULL,  -- R, A, C, I
    approval_threshold NUMERIC(12,2),
    
    is_auto_generated BOOLEAN DEFAULT TRUE,
    override_reason TEXT,
    
    -- Human-in-the-loop
    requires_review BOOLEAN DEFAULT TRUE,  -- NUEVO
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stakeholder_id, wbs_item_id, raci_role)
);

ALTER TABLE stakeholder_wbs_raci ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_raci ON stakeholder_wbs_raci
    FOR ALL USING (
        stakeholder_id IN (
            SELECT s.id FROM stakeholders s
            JOIN projects p ON s.project_id = p.id
            WHERE p.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- STAKEHOLDER_ALERTS (con RLS)
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

ALTER TABLE stakeholder_alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_stakeholder_alerts ON stakeholder_alerts
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- BOM_REVISIONS (con RLS)
-- =====================================================
CREATE TABLE bom_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    revision_name VARCHAR(100),
    revision_type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'draft',

    total_items_count INTEGER,
    items_added INTEGER DEFAULT 0,
    items_removed INTEGER DEFAULT 0,
    items_modified INTEGER DEFAULT 0,
    total_cost_change NUMERIC(12,2),

    change_summary TEXT,
    created_by UUID REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, revision_number)
);

ALTER TABLE bom_revisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_bom_revisions ON bom_revisions
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- PROCUREMENT_PLAN_SNAPSHOTS (con RLS)
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

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE procurement_plan_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_snapshots ON procurement_plan_snapshots
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- KNOWLEDGE_GRAPH_NODES (con RLS)
-- =====================================================
CREATE TABLE knowledge_graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    label VARCHAR(255),
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, entity_type, entity_id)
);

ALTER TABLE knowledge_graph_nodes ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_kg_nodes ON knowledge_graph_nodes
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- =====================================================
-- KNOWLEDGE_GRAPH_EDGES (con RLS y FK a nodes)
-- =====================================================
CREATE TABLE knowledge_graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    source_node_id UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    
    relationship_type VARCHAR(100) NOT NULL,
    properties JSONB DEFAULT '{}',
    confidence NUMERIC(3,2) DEFAULT 1.0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, source_node_id, target_node_id, relationship_type)
);

ALTER TABLE knowledge_graph_edges ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_kg_edges ON knowledge_graph_edges
    FOR ALL USING (
        project_id IN (
            SELECT id FROM projects 
            WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );
```

### 5.4 Resumen de RLS Coverage

| Tabla | RLS | Tipo Aislamiento | Verificado |
|-------|-----|------------------|------------|
| tenants | ✅ | Self-only | ✅ |
| users | ✅ | By tenant_id | ✅ |
| projects | ✅ | By tenant_id | ✅ |
| documents | ✅ | Via project→tenant | ✅ |
| **clauses** | ✅ | Via project→tenant | ✅ **NUEVO** |
| extractions | ✅ | Via document→project→tenant | ✅ |
| analyses | ✅ | Via project→tenant | ✅ |
| alerts | ✅ | Via project→tenant | ✅ |
| ai_usage_logs | ✅ | By tenant_id | ✅ |
| stakeholders | ✅ | Via project→tenant | ✅ |
| wbs_items | ✅ | Via project→tenant | ✅ |
| bom_items | ✅ | Via project→tenant | ✅ |
| stakeholder_wbs_raci | ✅ | Via stakeholder→project→tenant | ✅ |
| stakeholder_alerts | ✅ | Via project→tenant | ✅ |
| bom_revisions | ✅ | Via project→tenant | ✅ |
| procurement_plan_snapshots | ✅ | Via project→tenant | ✅ |
| knowledge_graph_nodes | ✅ | Via project→tenant | ✅ |
| knowledge_graph_edges | ✅ | Via project→tenant | ✅ |

**Total: 18 tablas con RLS ✅**

---

## 6. Seguridad y Compliance

### 6.1 Seguridad de Documentos

```yaml
document_security:
  storage:
    provider: "Cloudflare R2"
    encryption_at_rest: true
    encryption_method: "AES-256"
    access_control: "per project/tenant"
    path_structure: "/{tenant_id}/{project_id}/{document_id}"
    
  retention:
    policy_default: "indefinite"
    ai_payloads_full: "30 days"
    ai_logs_summary: "90 days"
    deleted_documents: "30 days (soft delete)"
    
  optimization:
    store_full_text: false  # Preferir offsets
    store_chunks_with_ids: true
    deduplicate_content: true
    
  pii_handling:
    anonymizer_enabled: true
    detected_types:
      - "dni/nie"
      - "passport"
      - "email"
      - "phone"
      - "iban"
      - "address"
    storage: "hashed references only"
```

### 6.2 Seguridad de IA

```yaml
ai_security:
  logging:
    required_fields:
      - prompt_version
      - model
      - input_tokens
      - output_tokens
      - cost_usd
      - input_hash   # SHA-256 para detectar duplicados
      - output_hash  # Para verificación y cache
      - user_id
      - project_id
      - timestamp
      
  provider_policy:
    anthropic:
      no_training: true  # Contractual
      zero_retention: true  # Si disponible
      document_in_privacy_policy: true
      
  rate_limiting:
    per_tenant:
      requests_per_minute: 60
      requests_per_hour: 500
      budget_monthly_usd: "configurable"
    per_user:
      requests_per_minute: 20
      
  cost_control:
    budget_alerts: [50, 75, 90, 100]  # % del presupuesto
    auto_block_at: 100  # % 
    model_fallback: "haiku when budget low"
```

### 6.3 MCP Security

```yaml
mcp_security:
  database_server:
    sql_allowed: false  # NO SQL arbitrario
    only_allowlist: true
    allowed_views: 8  # Ver §4.4
    allowed_functions: 5
    
  query_limits:
    statement_timeout: "5s"
    row_limit: 1000
    max_cost: 10000
    
  rate_limiting:
    per_tenant_per_minute: 60
    per_tenant_per_hour: 500
    
  audit:
    log_all_queries: true
    log_results_count: true
    alert_on_anomaly: true
```

### 6.4 GDPR Compliance

```yaml
gdpr_compliance:
  data_minimization:
    - "Solo recopilar datos necesarios"
    - "Offsets en lugar de texto completo cuando posible"
    - "Hashes en lugar de PII"
    
  right_to_access:
    endpoint: "GET /api/users/me/data-export"
    format: "JSON + PDF"
    response_time: "30 days max"
    
  right_to_erasure:
    endpoint: "DELETE /api/users/me"
    cascade: true
    soft_delete_period: "30 days"
    hard_delete: "automated after period"
    
  right_to_portability:
    format: "JSON"
    includes:
      - user_profile
      - projects
      - documents_metadata
      - analyses
      - alerts
      
  data_processing_agreement:
    required: true
    template: "/legal/dpa-template.pdf"
    
  privacy_policy:
    url: "/privacy"
    last_updated: "required field"
    ai_disclosure: "explicit section required"
```

### 6.5 Audit Logging

```sql
-- Tabla de audit log
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID,
    
    -- Acción
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    
    -- Contexto
    ip_address INET,
    user_agent TEXT,
    
    -- Datos
    old_values JSONB,
    new_values JSONB,
    
    -- Metadatos
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para búsqueda
CREATE INDEX idx_audit_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_time ON audit_logs(created_at);

-- Particionamiento por tiempo (opcional para escala)
-- CREATE TABLE audit_logs_y2026m01 PARTITION OF audit_logs
--     FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

---

## 7. CTO Gates Checklist

### 7.1 Las 8 Gates

Antes de dar luz verde a cada fase, el CTO debe verificar:

| # | Gate | Descripción | Verificación |
|---|------|-------------|--------------|
| 1 | **Multi-tenant Isolation** | RLS en TODAS las tablas con tenant_id/project_id | Test cross-tenant |
| 2 | **Identity Model** | UNIQUE(tenant_id, email) + casts UUID | Test mismo email 2 tenants |
| 3 | **MCP Security** | No SQL libre, allowlist + límites | Penetration test |
| 4 | **Legal Traceability** | Tabla clauses + FKs reales | Query de trazabilidad |
| 5 | **Coherence Score Formal** | Fórmula, pesos, calibración, anti-gaming | Documentación |
| 6 | **Human-in-the-loop** | Obligatorio en outputs de riesgo | UX review |
| 7 | **Observability** | Límites tenant, auditoría prompts/tokens | Dashboard verificar |
| 8 | **Document Security** | PII, cifrado, retención, RBAC | Security audit |

### 7.2 Checklist por Fase

#### MVP (Fase 1) - Gates Requeridas

- [x] Gate 1: Multi-tenant (RLS 18 tablas)
- [x] Gate 2: Identity (UNIQUE corregido)
- [x] Gate 3: MCP (allowlist implementado)
- [x] Gate 4: Trazabilidad (clauses entity)
- [x] Gate 5: Coherence Score (v1 documentado)
- [x] Gate 6: Human-in-the-loop (UX definido)
- [x] Gate 7: Observability (ai_usage_logs)
- [x] Gate 8: Document Security (R2 + anonymizer)

#### Fase 2 - Gates Adicionales

- [ ] Gate 5+: Coherence Score calibrado con pilotos
- [ ] Gate 7+: Cost control probado en producción

#### Fase 3 - Gates Adicionales

- [ ] Gate 6+: Human-in-the-loop para Implicit Needs
- [ ] Gate 3+: MCP servers externos (SAP, Primavera)

### 7.3 Riesgos CTO-Level Documentados

| Riesgo | Mitigación | Estado |
|--------|------------|--------|
| **Legal/Compliance** | Disclaimer: "no interpreta, asiste con trazabilidad" | Documentado |
| **Alucinación** | Evidencia + confidence + human-in-loop obligatorio | Implementado |
| **Escalabilidad Grafo** | NetworkX MVP → Plan Neo4j/Falkor si crece | ADR documentado |
| **MCP Superficie** | Capabilities mínimas, allowlist estricto | Implementado |
| **Implicit Needs** | Fase 3+, opt-in, advisory-only | Decisión tomada |

---

## 8. MVP - Fase 1 (12 Semanas)

### 8.1 Objetivo

Lanzar MVP funcional con:
- Auditoría tridimensional automática
- Extracción de cláusulas con trazabilidad
- Extracción básica de stakeholders
- Coherence Score v1
- Human-in-the-loop para outputs críticos

### 8.2 Backlog Reorganizado (Security First)

#### Sprint 0 (Semana 1): Foundations + Guardrails

**Foco:** Seguridad desde día 1

| ID | Feature | Prioridad | Criterio Aceptación |
|----|---------|-----------|---------------------|
| S0.1 | Setup monorepo + CI/CD | P0 | Pipeline funciona |
| S0.2 | Supabase + Auth | P0 | Login funciona |
| S0.3 | **RLS 18 tablas** | P0 | Test cross-tenant PASA |
| S0.4 | **UNIQUE(tenant_id, email)** | P0 | Mismo email 2 tenants OK |
| S0.5 | Logging estructurado + Sentry | P0 | Errors capturados |
| S0.6 | R2 con paths tenant/project | P0 | Aislamiento storage |
| S0.7 | ai_usage_logs tabla | P0 | Logs capturados |

**Tests Críticos Sprint 0:**
```python
def test_tenant_cannot_access_other_tenant_projects():
    """CRÍTICO: Aislamiento multi-tenant"""
    
def test_same_email_different_tenants_allowed():
    """CRÍTICO: B2B enterprise support"""
    
def test_rls_blocks_all_tables():
    """CRÍTICO: Verificar 18 tablas"""
```

#### Sprint 1-2 (Semanas 2-4): Ingesta + Clauses Entity

**Foco:** Documentos y trazabilidad legal

| ID | Feature | Prioridad | Criterio Aceptación |
|----|---------|-----------|---------------------|
| S1.1 | Upload documentos a R2 | P0 | PDF/Excel/BC3 suben |
| S1.2 | Parser PDF (PyMuPDF) | P0 | Texto extraído |
| S1.3 | Parser Excel (openpyxl) | P0 | Hojas parseadas |
| S1.4 | Parser BC3 (pyfiebdc) | P0 | Partidas extraídas |
| S1.5 | Anonymizer Service | P0 | PII detectado/reemplazado |
| S1.6 | **ClauseExtractorAgent** | P0 | Cláusulas con IDs estables |
| S1.7 | **Tabla clauses + FKs** | P0 | Trazabilidad funciona |
| S1.8 | Golden Dataset v0 | P1 | 10 proyectos anotados |

**Tests Críticos Sprint 1-2:**
```python
def test_clause_extraction_creates_stable_ids():
    """CRÍTICO: IDs estables para trazabilidad"""
    
def test_clause_fk_from_stakeholder():
    """CRÍTICO: FK funciona"""
    
def test_anonymizer_detects_dni_email_phone_iban():
    """CRÍTICO: PII protegido"""
```

#### Sprint 3 (Semanas 5-6): Motor de Coherencia v0

**Foco:** Detección de incoherencias

| ID | Feature | Prioridad | Criterio Aceptación |
|----|---------|-----------|---------------------|
| S3.1 | AI Service + Claude API | P0 | Extracción funciona |
| S3.2 | Cost controller | P0 | Bloquea al exceder |
| S3.3 | Cache Redis | P0 | Evita duplicados |
| S3.4 | WBSGeneratorAgent | P0 | WBS 4 niveles |
| S3.5 | BOMBuilderAgent | P0 | BOM con lead times |
| S3.6 | CoherenceEngine v0 | P0 | 10 reglas core |
| S3.7 | AlertGenerator | P0 | Alertas con evidencias |
| S3.8 | **Coherence Score v1** | P0 | Fórmula implementada |

**Reglas Core (10 para MVP):**

| ID | Regla | Severidad |
|----|-------|-----------|
| R1 | Plazo contrato ≠ fecha fin cronograma | Critical |
| R2 | Hito sin actividad en cronograma | High |
| R5 | Cronograma excede plazo contractual | Critical |
| R6 | Suma partidas ≠ precio contrato (±5%) | Medium |
| R11 | WBS sin actividades vinculadas | High |
| R12 | WBS sin partidas asignadas | High |
| R14 | Material crítico con fecha pedido tardía | Critical |
| R15 | BOM sin partida presupuestaria | High |
| R19 | Stakeholder sin datos contacto | Low |
| R20 | Aprobador contractual no identificado | Medium |

#### Sprint 4 (Semanas 7-8): Stakeholders + RACI

**Foco:** Identificación de stakeholders

| ID | Feature | Prioridad | Criterio Aceptación |
|----|---------|-----------|---------------------|
| S4.1 | StakeholderExtractorAgent | P0 | Extrae nombres/roles |
| S4.2 | StakeholderClassifier | P0 | Cuadrante asignado |
| S4.3 | RACIGeneratorAgent | P0 | Matriz generada |
| S4.4 | **Human-in-loop RACI** | P0 | Requiere revisión |
| S4.5 | Knowledge Graph básico | P1 | Nodos + edges |

#### Sprint 5 (Semanas 9-10): UI Mínima Pilotos

**Foco:** Feedback temprano de usuarios

| ID | Feature | Prioridad | Criterio Aceptación |
|----|---------|-----------|---------------------|
| S5.1 | Dashboard + Score gauge | P0 | Carga <2s |
| S5.2 | Lista proyectos | P0 | Filtros funcionan |
| S5.3 | **Evidence Viewer** | P0 | Link a cláusula/WBS/BOM |
| S5.4 | Panel alertas | P0 | Severidad visible |
| S5.5 | Stakeholder Map | P0 | Matriz poder/interés |
| S5.6 | RACI viewer | P0 | Editable |
| S5.7 | Export PDF | P1 | Con trazabilidad |

#### Sprint 6 (Semanas 11-12): Hardening + Pilots

**Foco:** Estabilidad y feedback

| ID | Feature | Prioridad | Criterio Aceptación |
|----|---------|-----------|---------------------|
| S6.1 | Security testing | P0 | 0 vulnerabilidades high |
| S6.2 | AI accuracy testing | P0 | >85% en golden dataset |
| S6.3 | Load testing | P0 | 100 usuarios, <1% error |
| S6.4 | **Cross-tenant attack tests** | P0 | Todos bloqueados |
| S6.5 | Deploy producción | P0 | Uptime >99% |
| S6.6 | Onboard 3-5 pilots | P0 | Feedback recopilado |
| S6.7 | Documentación básica | P1 | Usuario + API |

### 8.3 Criterios de Aceptación Fase 1

| Categoría | Criterio | Target |
|-----------|----------|--------|
| **Seguridad** | RLS en todas las tablas | 18/18 |
| **Seguridad** | Tests cross-tenant | 100% pasan |
| **Funcional** | Parsers (PDF/Excel/BC3) | Funcionan |
| **IA** | Accuracy extracción | >85% |
| **IA** | Cláusulas con ID estable | 100% |
| **Coherencia** | Reglas implementadas | 10 core |
| **Coherencia** | Score calculado | Fórmula v1 |
| **UX** | Evidence viewer | Links funcionan |
| **UX** | Human-in-loop | Implementado |
| **Performance** | Load test 100 usuarios | <1% error |
| **Pilots** | Empresas onboarded | 3-5 |
d": alert.rule_id,
            "severity": alert.severity,
            "weight": weight,
            "impact_raw": impact,
            "impact_normalized": impact_normalized,
            "confidence": confidence,
            "penalty": penalty
        })
    
    # Normalización con sigmoid para mantener 0-100
    # Suaviza el score para que no sea demasiado sensible
    normalized_score = int(100 / (1 + raw_penalty / 50))
    normalized_score = max(0, min(100, normalized_score))
    
    return CoherenceResult(
        score=normalized_score,
        raw_penalty=raw_penalty,
        alerts_count=len([a for a in alerts if a.status == "open"]),
        breakdown=sorted(breakdown, key=lambda x: -x["penalty"])[:10],
        top_5_drivers=sorted(breakdown, key=lambda x: -x["penalty"])[:5],
        methodology_version="1.0",
        calculated_at=datetime.utcnow()
    )


def _calculate_impact(alert: Alert, context: ProjectContext) -> float:
    """
    Calcula impacto en € o días según tipo de alerta.
    """
    if alert.type in ["budget_overrun", "cost_variance"]:
        # Impacto económico
        return alert.evidence_json.get("amount_eur", 0)
    
    elif alert.type in ["date_mismatch", "schedule_delay"]:
        # Impacto en días × coste diario proyecto
        days = alert.evidence_json.get("variance_days", 0)
        daily_cost = context.total_budget / context.total_duration_days
        return abs(days) * daily_cost
    
    elif alert.type == "critical_path_impact":
        # Impacto máximo si afecta ruta crítica
        return context.max_impact * 0.8
    
    else:
        # Default: impacto medio
        return context.max_impact * 0.3
```

### 12.2 Interpretación del Score

| Rango | Interpretación | Acción Recomendada |
|-------|----------------|-------------------|
| 90-100 | Excelente coherencia | Monitoreo rutinario |
| 80-89 | Buena coherencia | Revisar alertas medium |
| 70-79 | Coherencia aceptable | Revisar alertas high |
| 60-69 | Coherencia preocupante | Acción inmediata en critical |
| 0-59 | Coherencia crítica | Revisión completa urgente |

### 12.3 Calibración

```yaml
calibration:
  golden_dataset:
    version: "1.0.0"
    size: "50 proyectos sintéticos"
    coverage:
      - contract_types: [obra_civil, industrial, edificacion]
      - complexity: [simple, medium, complex]
      - languages: [es, en]
    
    validation:
      - coherence_rules: "500 pares (proyecto, alerta_esperada)"
      - score_correlation: "vs expert assessment"
      
  calibration_process:
    frequency: "Cada 20 proyectos piloto"
    metrics:
      - "Correlation con expert score"
      - "False positive rate por regla"
      - "False negative rate por regla"
    adjustments:
      - "Pesos por severidad"
      - "Umbrales de impacto"
      - "Confidence thresholds"
```

### 12.4 Anti-Gaming

```python
class AntiGamingPolicy:
    """
    Previene manipulación del Coherence Score.
    """
    
    rules = [
        # 1. No dismiss sin documentación
        "Alerts cannot be dismissed without resolution_notes",
        
        # 2. Historial inmutable
        "Score history is append-only, never modified",
        
        # 3. Audit trail
        "All resolutions logged with user_id, timestamp, notes",
        
        # 4. Re-escaneo automático
        "Score recalculated on document changes",
        
        # 5. Tiempo mínimo entre resoluciones
        "Min 1 hour between bulk resolutions (>5 alerts)",
    ]
    
    async def validate_resolution(
        self,
        alert_id: UUID,
        resolution: AlertResolution,
        user: User
    ) -> ValidationResult:
        """
        Valida que la resolución cumple políticas anti-gaming.
        """
        errors = []
        
        if not resolution.notes or len(resolution.notes) < 20:
            errors.append("Resolution notes must be at least 20 characters")
        
        if resolution.dismiss_reason == "not_applicable":
            # Requiere aprobación de segundo usuario
            if not resolution.approved_by or resolution.approved_by == user.id:
                errors.append("Dismiss requires approval from different user")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )
```

---

## 13. Métricas de Éxito

### 13.1 Métricas de Producto

| Métrica | MVP | Fase 2 | Fase 3 |
|---------|-----|--------|--------|
| Usuarios activos mensuales | 15 | 50 | 150 |
| Proyectos analizados | 20 | 100 | 300 |
| Documentos procesados | 60 | 300 | 900 |
| Cláusulas extraídas | 200 | 1,500 | 5,000 |
| Alertas generadas | 100 | 800 | 3,000 |
| Alertas resueltas | 50% | 65% | 75% |
| Stakeholders identificados | 200 | 1,000 | 3,000 |
| RACI entries | - | 2,000 | 8,000 |
| NPS | 30 | 40 | 50 |

### 13.2 Métricas de Negocio

| Métrica | MVP | Fase 2 | Fase 3 |
|---------|-----|--------|--------|
| MRR | €0 | €5K | €25K |
| Clientes de pago | 0 | 5 | 25 |
| Churn mensual | - | <10% | <5% |
| LTV/CAC | - | >3 | >5 |

### 13.3 Métricas de Impacto

| Métrica | Target | Medición |
|---------|--------|----------|
| Reducción tiempo análisis | 80% (8h→1.5h) | Survey pilotos |
| Reducción sobrecostes evitables | 15-30% | Seguimiento 6 meses |
| Detección temprana riesgos | +87% | Alertas vs issues reales |
| Mejora OTIF | +28% | Datos proveedor |
| Reducción crisis tardías | -71% | Incidentes reportados |

### 13.4 Métricas de Seguridad

| Métrica | Target | Frecuencia |
|---------|--------|------------|
| Cross-tenant access attempts | 0 | Continuo |
| PII leaks | 0 | Continuo |
| Failed auth attempts spike | Alert <100/min | Continuo |
| RLS bypass attempts | 0 | Semanal audit |
| MCP unauthorized queries | 0 | Diario |

---

## 14. Gestión de Riesgos

### 14.1 Riesgos Técnicos

| Riesgo | Prob. | Impacto | Mitigación | Owner |
|--------|-------|---------|------------|-------|
| Claude API downtime | Baja | Alto | Cache + retry + fallback | Backend |
| Accuracy <80% | Media | Alto | Golden dataset + prompt tuning | AI Lead |
| Latencia >5min | Media | Medio | Paralelización + optimización | Backend |
| **Data leak tenants** | Baja | **Crítico** | RLS 18 tablas + tests | Security |
| Graph RAG complexity | Media | Medio | NetworkX MVP, escalar después | Backend |
| **MCP SQL injection** | Media | **Crítico** | Allowlist estricto | Security |

### 14.2 Riesgos de Producto

| Riesgo | Prob. | Impacto | Mitigación | Owner |
|--------|-------|---------|------------|-------|
| Adopción lenta EPC | Media | Alto | Pilots gratis + casos éxito | Product |
| **Percepción "interpreta legal"** | Media | **Alto** | Disclaimer explícito | Legal |
| Resistencia usuarios | Alta | Medio | UX simple + onboarding | Product |
| **Implicit needs backlash** | Media | Alto | Opt-in + advisory + Fase 3 | Product |

### 14.3 Riesgos de Negocio

| Riesgo | Prob. | Impacto | Mitigación | Owner |
|--------|-------|---------|------------|-------|
| Competidor con funding | Media | Medio | Diferenciación nicho EPC | CEO |
| Cambio pricing Claude | Baja | Medio | Model routing + budget | CTO |
| Regulación IA (EU AI Act) | Media | Alto | Compliance by design | Legal |

### 14.4 Riesgos de Agentes

| Riesgo | Prob. | Impacto | Mitigación | Owner |
|--------|-------|---------|------------|-------|
| Acción incorrecta | Media | Alto | Human-in-loop obligatorio | Product |
| Prompt injection docs | Media | Alto | Sanitización + sandboxing | Security |
| Over-reliance IA | Media | Medio | Confidence scores visibles | UX |
| Alucinaciones | Media | Alto | Evidencia + verificación | AI Lead |

---

## 15. Plan de Testing

### 15.1 Pirámide de Tests

```
          /\
         /  \  E2E (10%)
        /    \  - Flujo completo análisis
       /------\  - Cross-tenant isolation
      /        \  - Human-in-loop flows
     /----------\  Integration (30%)
    /            \  - API endpoints
   /              \  - Database + RLS
  /----------------\  - Graph queries
 /                  \ Unit (60%)
/____________________\  - Parsers, Rules, Score
```

### 15.2 Tests Críticos de Seguridad

```python
# tests/security/test_tenant_isolation.py

class TestTenantIsolation:
    """Tests CRÍTICOS de aislamiento multi-tenant"""
    
    async def test_user_cannot_access_other_tenant_projects(self):
        """Gate 1: Aislamiento projects"""
        
    async def test_user_cannot_access_other_tenant_documents(self):
        """Gate 1: Aislamiento documents"""
        
    async def test_user_cannot_access_other_tenant_clauses(self):
        """Gate 1: Aislamiento clauses (NUEVO)"""
        
    async def test_user_cannot_access_other_tenant_alerts(self):
        """Gate 1: Aislamiento alerts"""
        
    async def test_user_cannot_access_other_tenant_stakeholders(self):
        """Gate 1: Aislamiento stakeholders"""
        
    async def test_same_email_different_tenants_works(self):
        """Gate 2: B2B enterprise support"""
        
    async def test_rls_blocks_direct_sql_attack(self):
        """Gate 1: SQL directo bloqueado"""
        
    async def test_mcp_rejects_arbitrary_sql(self):
        """Gate 3: MCP allowlist"""
        
    async def test_mcp_respects_query_limits(self):
        """Gate 3: MCP límites"""
```

### 15.3 Tests de Trazabilidad

```python
# tests/traceability/test_clause_fks.py

class TestClauseTraceability:
    """Tests de trazabilidad legal (Gate 4)"""
    
    async def test_stakeholder_has_clause_fk(self):
        """Stakeholder referencia clause_id"""
        
    async def test_bom_item_has_clause_fk(self):
        """BOM item referencia clause_id"""
        
    async def test_alert_has_clause_fk(self):
        """Alert referencia source_clause_id"""
        
    async def test_evidence_viewer_shows_clause_link(self):
        """UI muestra link a cláusula original"""
        
    async def test_clause_deletion_cascades_correctly(self):
        """FK cascade funciona"""
```

### 15.4 Tests de Coherence Score

```python
# tests/coherence/test_score.py

class TestCoherenceScore:
    """Tests del Coherence Score (Gate 5)"""
    
    async def test_perfect_project_scores_100(self):
        """Proyecto sin alertas = 100"""
        
    async def test_critical_alert_reduces_score_significantly(self):
        """Alerta critical reduce score"""
        
    async def test_score_formula_matches_spec(self):
        """Fórmula implementada = especificación"""
        
    async def test_breakdown_shows_top_drivers(self):
        """Breakdown muestra top 5 drivers"""
        
    async def test_anti_gaming_requires_resolution_notes(self):
        """No dismiss sin notas"""
        
    async def test_score_history_is_immutable(self):
        """Historial no modificable"""
```

---

## 16. Plan de Deployment

### 16.1 Entornos

| Entorno | URL | Deploy | Base de Datos |
|---------|-----|--------|---------------|
| Development | localhost | Manual | Local |
| Staging | staging.c2pro.app | Auto (push main) | Supabase staging |
| Production | app.c2pro.app | Manual (tag) | Supabase prod |

### 16.2 Pre-Deployment Checklist

```yaml
pre_deployment:
  code_quality:
    - [ ] All tests pass
    - [ ] Coverage >80% critical paths
    - [ ] No high/critical vulnerabilities (Snyk)
    - [ ] Code review approved
    
  security:
    - [ ] RLS tests pass (all 18 tables)
    - [ ] Cross-tenant tests pass
    - [ ] MCP allowlist tests pass
    - [ ] No secrets in code
    
  documentation:
    - [ ] Changelog updated
    - [ ] Version bumped (semver)
    - [ ] API docs updated
    
  database:
    - [ ] Migrations tested in staging
    - [ ] Backup verified
    - [ ] RLS policies applied
```

### 16.3 Deployment Checklist

```yaml
deployment:
  pre_deploy:
    - [ ] Notify team in Slack
    - [ ] Verify staging is stable
    - [ ] Backup production DB
    
  deploy:
    - [ ] Deploy backend (Railway)
    - [ ] Run smoke tests backend
    - [ ] Deploy frontend (Vercel)
    - [ ] Run smoke tests frontend
    
  post_deploy:
    - [ ] Verify Sentry (no new errors)
    - [ ] Verify UptimeRobot
    - [ ] Check key flows manually
    - [ ] Monitor 1h post-deploy
    - [ ] Communicate release (if major)
```

### 16.4 Rollback Plan

| Componente | Método | Tiempo |
|------------|--------|--------|
| Backend | Railway revert | <2 min |
| Frontend | Vercel revert | <1 min |
| Database | Supabase PITR | ~15 min |
| Cache | Redis flush | <1 min |

---

## 17. Anexos

### 17.1 Catálogo de Reglas de Coherencia

```yaml
# coherence_rules.yaml - Versión 1.0

rules:
  - id: "R1"
    name: "contract_schedule_deadline_mismatch"
    description: "Plazo ejecución contrato ≠ fecha fin cronograma"
    inputs:
      - contract.execution_deadline
      - schedule.end_date
    detection_logic: "abs(contract.execution_deadline - schedule.end_date) > 7 days"
    severity: "critical"
    suggested_actions:
      - "Verificar fecha contractual en cláusula de plazos"
      - "Ajustar cronograma o solicitar modificación contractual"
    evidence_fields:
      - contract_clause_id
      - schedule_end_date
      - variance_days

  - id: "R2"
    name: "milestone_without_activity"
    description: "Hito contractual sin actividad en cronograma"
    inputs:
      - contract.milestones[]
      - schedule.activities[]
    detection_logic: "milestone NOT IN schedule.activities.linked_milestones"
    severity: "high"
    suggested_actions:
      - "Crear actividad para el hito en cronograma"
      - "Verificar si hito aplica al alcance actual"
    evidence_fields:
      - milestone_clause_id
      - milestone_name
      - milestone_date

  - id: "R5"
    name: "schedule_exceeds_contract"
    description: "Cronograma excede plazo contractual"
    inputs:
      - contract.execution_deadline
      - schedule.end_date
    detection_logic: "schedule.end_date > contract.execution_deadline"
    severity: "critical"
    suggested_actions:
      - "Comprimir cronograma"
      - "Solicitar extensión de plazo"
      - "Evaluar penalizaciones potenciales"
    evidence_fields:
      - contract_clause_id
      - contract_deadline
      - schedule_end_date
      - excess_days

  - id: "R6"
    name: "budget_contract_mismatch"
    description: "Suma partidas ≠ precio contrato (±5%)"
    inputs:
      - contract.total_price
      - budget.sum_items
    detection_logic: "abs(budget.sum - contract.total_price) / contract.total_price > 0.05"
    severity: "medium"
    suggested_actions:
      - "Revisar partidas faltantes"
      - "Verificar cálculos de mediciones"
    evidence_fields:
      - contract_price_clause_id
      - contract_total
      - budget_total
      - variance_percentage

  - id: "R11"
    name: "wbs_without_activities"
    description: "WBS item sin actividades vinculadas"
    inputs:
      - wbs_items[]
      - schedule.activities[]
    detection_logic: "wbs_item.schedule_activity_ids IS EMPTY"
    severity: "high"
    suggested_actions:
      - "Vincular actividades del cronograma"
      - "Verificar si WBS item está fuera de alcance"
    evidence_fields:
      - wbs_item_id
      - wbs_code
      - wbs_name

  - id: "R12"
    name: "wbs_without_budget"
    description: "WBS item sin partidas asignadas"
    inputs:
      - wbs_items[]
      - budget.items[]
    detection_logic: "wbs_item.budget_item_ids IS EMPTY"
    severity: "high"
    suggested_actions:
      - "Asignar partidas presupuestarias"
      - "Verificar si es trabajo sin coste directo"
    evidence_fields:
      - wbs_item_id
      - wbs_code
      - wbs_name

  - id: "R14"
    name: "critical_material_late_order"
    description: "Material crítico con fecha pedido tardía"
    inputs:
      - bom_items[]
      - schedule.activities[]
    detection_logic: "bom_item.optimal_order_date < TODAY AND bom_item.status = 'planned'"
    severity: "critical"
    suggested_actions:
      - "Realizar pedido inmediatamente"
      - "Buscar alternativas con menor lead time"
      - "Evaluar impacto en cronograma"
    evidence_fields:
      - bom_item_id
      - item_name
      - optimal_order_date
      - required_on_site_date
      - days_late

  - id: "R15"
    name: "bom_without_budget"
    description: "BOM item sin partida presupuestaria"
    inputs:
      - bom_items[]
      - budget.items[]
    detection_logic: "bom_item.budget_item_id IS NULL"
    severity: "high"
    suggested_actions:
      - "Asignar partida presupuestaria"
      - "Crear partida si no existe"
    evidence_fields:
      - bom_item_id
      - item_name
      - estimated_cost

  - id: "R19"
    name: "stakeholder_without_contact"
    description: "Stakeholder mencionado sin datos de contacto"
    inputs:
      - stakeholders[]
    detection_logic: "stakeholder.email IS NULL AND stakeholder.phone IS NULL"
    severity: "low"
    suggested_actions:
      - "Completar datos de contacto"
      - "Verificar con Project Manager"
    evidence_fields:
      - stakeholder_id
      - stakeholder_name
      - stakeholder_role
      - source_clause_id

  - id: "R20"
    name: "approver_not_identified"
    description: "Aprobador contractual no identificado"
    inputs:
      - clauses[]
      - stakeholders[]
    detection_logic: "clause.type = 'approval' AND clause.approver NOT IN stakeholders"
    severity: "medium"
    suggested_actions:
      - "Identificar aprobador en organización cliente"
      - "Solicitar clarificación contractual"
    evidence_fields:
      - clause_id
      - clause_code
      - approval_type
      - threshold_amount
```

### 17.2 Golden Dataset Specification

```yaml
golden_dataset:
  version: "1.0.0"
  description: "Dataset para validación de accuracy AI y Coherence Score"
  
  composition:
    total_projects: 50
    by_type:
      obra_civil: 20
      industrial: 15
      edificacion: 15
    by_complexity:
      simple: 15    # <10 WBS items, <50 BOM items
      medium: 20    # 10-50 WBS, 50-200 BOM
      complex: 15   # >50 WBS, >200 BOM
    by_language:
      spanish: 40
      english: 10
      
  annotations:
    clauses:
      total: 500
      fields:
        - clause_code
        - clause_type
        - stakeholders_mentioned
        - dates_mentioned
        - amounts_mentioned
      annotators: 2
      agreement_threshold: 0.85
      
    stakeholders:
      total: 300
      fields:
        - name
        - role
        - organization
        - department
        - power_level
        - interest_level
      annotators: 2
      agreement_threshold: 0.80
      
    coherence_alerts:
      total: 500
      format: "(project_id, expected_rule_id, expected_severity)"
      coverage: "All 20 rules at least 10 examples each"
      
  validation_metrics:
    extraction_accuracy: ">85%"
    stakeholder_accuracy: ">80%"
    coherence_precision: ">85%"
    coherence_recall: ">80%"
    score_correlation: ">0.85 vs expert"
    
  versioning:
    location: "/tests/golden/"
    format: "JSON + annotations CSV"
    git_tracked: true
    changelog: "CHANGELOG.md required"
```

### 17.3 ADRs (Architecture Decision Records)

```markdown
## ADR-001: FastAPI vs Flask/Django
**Status:** Accepted
**Context:** Necesitamos framework backend para API
**Decision:** FastAPI
**Reasons:**
- Async nativo para AI API calls
- Pydantic v2 built-in
- OpenAPI automático
- Mejor DX

## ADR-002: Supabase vs AWS RDS
**Status:** Accepted
**Context:** Necesitamos PostgreSQL managed
**Decision:** Supabase
**Reasons:**
- RLS nativo (crítico para multi-tenancy)
- Auth incluido
- Backups + PITR
- Free tier generoso

## ADR-003: Claude vs GPT-4
**Status:** Accepted
**Context:** Modelo de lenguaje principal
**Decision:** Claude (Sonnet 4 + Haiku 4)
**Reasons:**
- Mejor en documentos largos (200K context)
- Menos alucinaciones en extracción
- MCP support nativo
- Pricing competitivo

## ADR-004: Graph RAG vs Vector RAG
**Status:** Accepted
**Context:** Arquitectura de retrieval
**Decision:** Graph RAG con NetworkX
**Reasons:**
- Mejora 6.4 puntos en multi-hop
- Relaciones explícitas para trazabilidad
- Mejor para coherencia

## ADR-005: MCP vs Custom APIs
**Status:** Accepted
**Context:** Integración de agentes
**Decision:** MCP Protocol
**Reasons:**
- Estándar abierto
- Interoperabilidad
- Seguridad mejorada
- Reduce time-to-market

## ADR-006: NetworkX vs Neo4j (MVP)
**Status:** Accepted
**Context:** Graph database para MVP
**Decision:** NetworkX in-memory
**Reasons:**
- Suficiente para MVP (<100K nodos)
- Sin infraestructura adicional
- Migración a Neo4j posible después
**Review trigger:** nodes > 50K OR latency > 1s

## ADR-007: Clauses como entidad separada
**Status:** Accepted (v2.4.0)
**Context:** Trazabilidad legal
**Decision:** Tabla clauses con FKs desde stakeholders, bom_items, alerts
**Reasons:**
- Trazabilidad real (no texto libre)
- Queries de evidencia eficientes
- Audit trail completo

## ADR-008: Implicit Needs → Fase 3 Experimental
**Status:** Accepted (v2.4.0)
**Context:** Feature de inferencia de necesidades implícitas
**Decision:** Mover a Fase 3 como experimental opt-in
**Reasons:**
- Riesgo compliance/sesgos
- Requiere más validación
- MVP sin este feature sigue siendo valioso
```

### 17.4 Glosario

| Término | Definición |
|---------|------------|
| **WBS** | Work Breakdown Structure - Estructura de desglose del trabajo |
| **BOM** | Bill of Materials - Lista de materiales |
| **RACI** | Responsible, Accountable, Consulted, Informed |
| **RLS** | Row Level Security - Seguridad a nivel de fila |
| **MCP** | Model Context Protocol - Protocolo de contexto de modelo |
| **Graph RAG** | Retrieval Augmented Generation con Knowledge Graphs |
| **Coherence Score** | Indicador 0-100 de alineación entre documentos |
| **EPC** | Engineering, Procurement, Construction |
| **Incoterm** | International Commercial Terms |
| **PITR** | Point-in-Time Recovery |
| **Golden Dataset** | Dataset anotado para validación de accuracy |
| **Human-in-the-loop** | Validación humana obligatoria antes de acción |

---

<div align="center">

## — FIN DEL ROADMAP v2.4.0 —

**C2Pro - Contract Intelligence Platform**
*Cognitive Operating System for EPC Procurement*

© 2024-2026 Todos los derechos reservados

---

**Este documento es la biblia del PM y desarrollo.**
**Cualquier decisión significativa debe ser reflejada aquí.**

**CTO Gates: 8 checkpoints obligatorios antes de cada fase.**

---

*Última actualización: 05 de Enero de 2026*
*Próxima revisión: Tras completar Sprint 0*

</div>
