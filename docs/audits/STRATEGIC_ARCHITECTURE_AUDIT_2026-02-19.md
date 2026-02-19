# Auditoría Estratégica Integral — C2Pro
**Fecha:** 2026-02-19
**Tipo:** Arquitectura, Separación Demo/Producción, Orden Frontend
**Versión del codebase auditada:** main branch (Feb 2026)

---

## 1. Diagnóstico Ejecutivo

### Estado Actual

C2Pro es una plataforma de inteligencia contractual (Contract Intelligence) construida como monorepo con:

- **Backend:** FastAPI + Python 3.11, arquitectura hexagonal parcial, LangGraph para orquestación AI
- **Frontend:** Next.js 15 + React 19 + TypeScript + Tailwind + shadcn/ui
- **Infraestructura:** PostgreSQL (Supabase), Redis, Cloudflare R2, Sentry
- **AI:** Anthropic Claude API, RAG, Coherence Engine v2

El proyecto tiene una **base conceptual sólida** y documentación técnica exhaustiva (>20 documentos de contexto, diagramas de flujo, TDD backlogs con 1,400+ tests planificados). Sin embargo, la implementación real presenta desalineación significativa respecto a la arquitectura documentada.

### Nivel de Riesgo: **ALTO**

| Dimensión | Nivel | Justificación |
|-----------|-------|---------------|
| Deuda técnica | **Alto** | Directorios duplicados, datos demo en producción, rutas redundantes |
| Escalabilidad | **Medio-Alto** | Frontend no escala sin reorganización; backend escala mejor |
| Mantenibilidad | **Alto** | Un desarrollador nuevo no puede determinar qué es demo y qué es producción |
| Coherencia arquitectónica | **Medio** | Backend sigue hexagonal parcialmente; frontend sin patrón claro |
| Riesgo de producto | **Alto** | Un usuario en producción puede ver datos ficticios |

### Grado de Escalabilidad

- **Backend:** 7/10 — La arquitectura hexagonal y modular permite crecer, pero las dependencias cruzadas entre bounded contexts y los datos mock en código de producción lo comprometen.
- **Frontend:** 3/10 — La duplicación de directorios, rutas y la mezcla demo/producción hacen que escalar sea inviable sin un refactor previo.

---

## 2. Problemas Críticos Detectados

### P1 — Críticos (Bloquean escalado y ponen en riesgo el producto)

**P1.1 — Datos demo hardcodeados en rutas de producción**

| Archivo | Líneas | Problema |
|---------|--------|----------|
| `apps/web/app/(app)/page.tsx` | 12-27 | `const DATA = { score: 78, project: 'Torre Skyline'... }` — Dashboard principal sin API real |
| `apps/web/app/(app)/documents/page.tsx` | 38-151 | `const mockDocuments = [...]` — 8 documentos ficticios, sin llamada API |
| `apps/web/app/dashboard/projects/[id]/coherence/page.tsx` | ~1-25 | Datos hardcodeados de coherencia |

**Impacto:** Un usuario en producción navegando a `/documents` ve datos ficticios. No existe mecanismo que impida esto.

**P1.2 — Estructura de componentes frontend duplicada**

Dos directorios de componentes coexisten con implementaciones diferentes del mismo componente:

```
apps/web/components/coherence/CoherenceGauge.tsx  → 112 líneas, usa Recharts
apps/web/src/components/features/coherence/CoherenceGauge.tsx → 89 líneas, usa SVG nativo
```

Los pages importan de ambas ubicaciones simultáneamente:
```typescript
// En app/(app)/projects/[id]/coherence/page.tsx:
import { CoherenceGauge } from '@/src/components/features/coherence/CoherenceGauge';
import { BreakdownChart } from '@/components/coherence/BreakdownChart';
```

**Impacto:** UI inconsistente, bundle bloat, pesadilla de mantenimiento.

**P1.3 — Tres sistemas de rutas dashboard redundantes**

```
app/(app)/   ← Rutas principales (mezcla API real + datos mock)
app/dashboard/     ← Duplicado byte-a-byte del layout + pages con mock data
app/demo/          ← Redirige a /demo/projects pero comparte layout
```

**Impacto:** Tres rutas que renderizan versiones ligeramente diferentes del dashboard. Navegación impredecible.

**P1.4 — Mock data en código de producción del backend**

```python
# coherence/service.py (líneas 24-44)
MOCK_PROJECT_DB = {
    "00000000-0000-0000-0000-000000000001": {"name": "Project with Score"},
}
MOCK_SCORE_DB = {
    "00000000-0000-0000-0000-000000000001": CoherenceScore(score=85, ...)
}
```

```python
# modules/decision_intelligence/application/ports.py
class _DefaultExtractionService:
    async def extract_clauses(self, chunks):
        return [{"text": "Payment term must include due date.", "confidence": 0.92}]
```

**Impacto:** Estos defaults pueden ejecutarse en producción si las dependencias no se inyectan correctamente.

---

### P2 — Altos (Degradan la calidad y dificultan evolución)

**P2.1 — Violaciones de bounded contexts en el backend**

```python
# analysis/adapters/ai/agents/raci_generator.py
from src.stakeholders.domain.models import RACIRole  # ❌ Importa dominio ajeno

# analysis/adapters/graph/knowledge_graph.py
from src.documents.domain.models import Clause  # ❌
from src.procurement.domain.models import WBSItem  # ❌
from src.stakeholders.domain.models import RACIRole, Stakeholder  # ❌

# coherence/alert_generator.py
from src.analysis.domain.enums import AlertSeverity  # ❌ Dependencia cruzada
```

**Impacto:** Los módulos no se pueden deployar, testear ni evolucionar independientemente.

**P2.2 — Entidad Project duplicada con representaciones incompatibles**

```python
# projects/domain/models.py (Pydantic BaseModel)
class Project(BaseModel):
    id: UUID; tenant_id: UUID; name: str; code: str; ...

# projects/domain/project.py (dataclass)
@dataclass
class Project:
    id: UUID; tenant_id: UUID; name: str; ...
    coherence_score: int | None  # Campo que no existe en la otra versión
```

**P2.3 — Orquestación LangGraph: solo 7 de 17 nodos implementados**

La documentación define 17 nodos (N1-N17). El código real tiene 7 nodos ad-hoc que no corresponden 1:1 con el plan:
- `router`, `risk_extractor`, `wbs_extractor`, `budget_parser`, `critique`, `human_interrupt`, `save_to_db`

Los servicios individuales (extracción, coherencia, stakeholders) existen pero **no están integrados como nodos del grafo**.

**P2.4 — MSW configurado pero las pages lo ignoran**

El provider inicializa MSW correctamente en modo demo:
```typescript
// providers.tsx
if (!env.IS_DEMO) return;
const { worker } = await import("@/mocks/browser");
await worker.start(...);
```

Pero las pages hardcodean datos en vez de llamar a la API (que MSW interceptaría):
```typescript
// (app)/page.tsx — NO llama API, usa const DATA = {...}
```

**Resultado:** MSW es inútil porque ninguna page hace fetch que pueda interceptar.

**P2.5 — Store `app-mode` existe pero no se usa**

```typescript
// stores/app-mode.ts
const defaultMode = process.env.NEXT_PUBLIC_APP_MODE === "demo" ? "demo" : "prod";
export const useAppModeStore = create<AppModeState>()(...);
```

Este store se define pero ningún componente lo consulta para decidir si mostrar datos reales o mock.

---

### P3 — Medios (Deuda técnica acumulable)

| ID | Problema | Ubicación |
|----|----------|-----------|
| P3.1 | Tres sistemas de mock data (MSW, `lib/mockData.ts`, inline en pages) | Frontend completo |
| P3.2 | Mensajes de error en español en código inglés | `lib/api/client.ts` ("Sin permisos") |
| P3.3 | No hay error boundaries en el frontend | App-wide |
| P3.4 | Feature flags del backend no se verifican en todos los endpoints | `apps/api/src/config.py` |
| P3.5 | Coherence engine tiene `engine.py` y `engine_v2.py` coexistiendo | `coherence/` |
| P3.6 | Prompts de ejemplo con datos ficticios en código fuente | `core/ai/example_prompts.py` |
| P3.7 | HITL solo tiene ports/domain definidos, sin service implementation | `modules/hitl/` |

---

## 3. Problema Central del Proyecto

> **El proyecto no tiene una frontera definida entre lo que es demostración y lo que es producto real, y esta contaminación afecta tanto al frontend (datos hardcodeados en rutas de producción) como al backend (mock databases en código fuente), haciendo imposible determinar programáticamente si el sistema está mostrando información real o ficticia.**

---

## 4. Arquitectura Recomendada

### 4.1 Diagrama Conceptual

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                       │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  app/(app)/   │  │  app/(demo)/ │  │  components/       │   │
│  │  Rutas PROD   │  │  Rutas DEMO  │  │  (única ubicación) │   │
│  │  Solo API     │  │  MSW activo  │  │                    │   │
│  └──────┬───────┘  └──────┬───────┘  │  ui/               │   │
│         │                  │          │  features/          │   │
│         ▼                  ▼          │  layout/            │   │
│  ┌──────────────────────────────┐    └────────────────────┘   │
│  │  lib/api/ (Generated Client) │                              │
│  │  Siempre llama a la API      │                              │
│  │  MSW intercepta en demo      │                              │
│  └──────────────┬───────────────┘                              │
│                  │                                              │
│  ┌──────────────┴───────────────┐                              │
│  │  stores/ (Zustand)           │                              │
│  │  app-mode controla           │                              │
│  │  comportamiento demo/prod    │                              │
│  └──────────────────────────────┘                              │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CAPA HTTP (Routers)                                     │   │
│  │  Solo validación + delegación a use cases                │   │
│  └───────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
│  ┌───────────────────────┴─────────────────────────────────┐   │
│  │  CAPA APLICACIÓN (Use Cases / Services)                  │   │
│  │  Orquesta lógica de negocio                              │   │
│  │  NO importa de otros bounded contexts                    │   │
│  └───────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
│  ┌───────────────────────┴─────────────────────────────────┐   │
│  │  CAPA DOMINIO (Entidades, Value Objects, Domain Services)│   │
│  │  SIN dependencias externas                               │   │
│  │  SIN datos mock                                          │   │
│  └───────────────────────┬─────────────────────────────────┘   │
│                           │                                     │
│  ┌───────────────────────┴─────────────────────────────────┐   │
│  │  CAPA INFRAESTRUCTURA (Adapters)                         │   │
│  │  Persistence / AI / External APIs                        │   │
│  │  Implementa ports del dominio                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ORQUESTACIÓN (LangGraph)                                │   │
│  │  17 nodos definidos como funciones puras                 │   │
│  │  Cada nodo wrappea un use case existente                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Separación Demo vs Producción

```
Estrategia: MISMAS RUTAS + DATA LAYER SWITCHING

                    ┌─────────────────┐
                    │  NEXT_PUBLIC_    │
                    │  APP_MODE=demo   │
                    │  o producción    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  providers.tsx   │
                    │  if demo → MSW  │
                    │  if prod → noop │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Pages SIEMPRE  │
                    │  llaman a API   │
                    │  via generated  │
                    │  client         │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼──────┐  ┌───▼────────┐  ┌─▼────────────┐
     │  Demo Mode    │  │            │  │  Prod Mode    │
     │  MSW intercepts│ │  fetch()   │  │  Real API     │
     │  returns mock  │ │            │  │  responds     │
     └───────────────┘  └────────────┘  └──────────────┘
```

**Principio clave:** Las pages NUNCA contienen datos. Siempre llaman a la API. En demo, MSW intercepta. En producción, llega al backend real.

### 4.3 Estructura Modular Frontend Propuesta

```
apps/web/
├── app/
│   ├── (app)/                    ← Rutas de la aplicación (única)
│   │   ├── layout.tsx
│   │   ├── page.tsx              ← Dashboard (llama API)
│   │   ├── documents/page.tsx    ← Documentos (llama API)
│   │   ├── projects/
│   │   │   ├── page.tsx          ← Lista proyectos (llama API)
│   │   │   └── [id]/
│   │   │       ├── coherence/page.tsx
│   │   │       ├── documents/page.tsx
│   │   │       └── analysis/page.tsx
│   │   ├── alerts/page.tsx
│   │   ├── stakeholders/page.tsx
│   │   └── settings/page.tsx
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── api/[...proxy]/route.ts
│   ├── layout.tsx
│   └── providers.tsx
│
├── components/                    ← ÚNICA ubicación de componentes
│   ├── ui/                       ← Primitivos (shadcn/ui)
│   ├── layout/                   ← AppSidebar, AppHeader, DemoBanner
│   ├── features/                 ← Componentes de dominio
│   │   ├── coherence/            ← CoherenceGauge, ScoreCard, etc.
│   │   ├── documents/
│   │   ├── projects/
│   │   ├── stakeholders/
│   │   ├── evidence/
│   │   └── alerts/
│   └── shared/                   ← ErrorBoundary, LoadingStates, etc.
│
├── hooks/                        ← Custom hooks
├── stores/                       ← Zustand stores (app-mode realmente usado)
├── contexts/                     ← React contexts (auth)
├── lib/
│   ├── api/                      ← Cliente generado (Orval)
│   └── utils/
├── mocks/                        ← MSW handlers + seed data (SOLO aquí hay mock data)
│   ├── browser.ts
│   ├── handlers/
│   └── data/
└── types/
```

**Directorios a eliminar:**
- `apps/web/src/components/` → Consolidar en `apps/web/components/features/`
- `apps/web/app/dashboard/` → Eliminar completamente
- `apps/web/app/demo/` → Eliminar (demo se controla por env, no por ruta)
- `apps/web/lib/mockData.ts` → Migrar datos útiles a `mocks/data/`, luego eliminar

---

## 5. Plan de Reorganización por Fases

### Fase 1 — Separación Conceptual (Semana 1-2)

**Objetivo:** Definir qué es demo y qué es producción sin tocar código.

| Tarea | Detalle |
|-------|---------|
| 1.1 | Inventariar cada page del frontend y clasificarla: ¿usa API real o datos mock? |
| 1.2 | Inventariar cada endpoint del backend y clasificar: ¿tiene mock data hardcodeada? |
| 1.3 | Documentar la matriz page ↔ endpoint ↔ fuente de datos |
| 1.4 | Definir el contrato: "En producción, TODA page llama a API. En demo, MSW intercepta" |
| 1.5 | Definir qué endpoints backend son necesarios para que las pages funcionen sin mock |

**Entregable:** Documento `DEMO_VS_PROD_CONTRACT.md` con la matriz completa.

---

### Fase 2 — Reorganización Estructural del Frontend (Semana 3-4)

**Objetivo:** Una sola estructura de componentes, una sola estructura de rutas.

| Tarea | Detalle |
|-------|---------|
| 2.1 | Auditar `components/` vs `src/components/features/` componente por componente |
| 2.2 | Para cada duplicado, elegir la mejor implementación y consolidar |
| 2.3 | Mover todos los componentes de `src/components/features/` a `components/features/` |
| 2.4 | Actualizar todos los imports (buscar `@/src/components` → `@/components/features`) |
| 2.5 | Eliminar `app/dashboard/` (duplicado de `app/(app)/`) |
| 2.6 | Eliminar `app/demo/` (demo se controla por env variable, no por ruta) |
| 2.7 | Renombrar `app/(dashboard)/` a `app/(app)/` para claridad semántica |
| 2.8 | Eliminar `lib/mockData.ts` — mover datos relevantes a `mocks/data/seed.ts` |
| 2.9 | Verificar que MSW handlers cubren todos los endpoints que las pages necesitan |
| 2.10 | Hacer que `useAppModeStore` realmente controle el banner demo y cualquier UI condicional |

**Entregable:** Frontend con estructura única y limpia. Zero datos mock en pages.

---

### Fase 3 — Limpieza de Dominio Backend (Semana 5-6)

**Objetivo:** Eliminar mock data de producción, corregir bounded contexts.

| Tarea | Detalle |
|-------|---------|
| 3.1 | Eliminar `MOCK_PROJECT_DB` y `MOCK_SCORE_DB` de `coherence/service.py` |
| 3.2 | Eliminar `_DefaultExtractionService` y `_DefaultIngestionService` de `decision_intelligence/ports.py` — reemplazar con errores explícitos si no se inyecta dependencia |
| 3.3 | Mover `core/ai/example_prompts.py` a tests o docs |
| 3.4 | Consolidar entidad `Project` en una sola definición (elegir Pydantic o dataclass) |
| 3.5 | Eliminar `engine.py` legacy de coherence (mantener solo `engine_v2.py`) |
| 3.6 | Crear shared DTOs/events para comunicación entre bounded contexts en vez de importar modelos de dominio |
| 3.7 | Refactorizar `analysis/adapters/graph/knowledge_graph.py` para no importar de `documents.domain`, `procurement.domain`, `stakeholders.domain` |
| 3.8 | Extraer `AlertSeverity` a un módulo shared kernel si es necesario compartirlo |

**Entregable:** Backend sin mock data en src/, bounded contexts respetados.

---

### Fase 4 — Refactor Frontend: Pages como orquestadores puros (Semana 7-8)

**Objetivo:** Cada page solo hace fetch + renderiza componentes.

| Tarea | Detalle |
|-------|---------|
| 4.1 | `(app)/page.tsx` → Server component que llama a `DashboardService.getSummary()` |
| 4.2 | `(app)/documents/page.tsx` → Server component que llama a `DocumentsService.list()` |
| 4.3 | `(app)/projects/[id]/coherence/page.tsx` → llama a `CoherenceService.getScore(id)` |
| 4.4 | Asegurar que cada page tiene: loading state, error state, empty state |
| 4.5 | Implementar error boundaries a nivel de layout |
| 4.6 | Agregar MSW handlers para cada endpoint nuevo que las pages necesiten |
| 4.7 | Verificar que `NEXT_PUBLIC_APP_MODE=demo` + MSW produce la misma UX que antes (sin regresión) |
| 4.8 | Eliminar cualquier `const DATA = {...}` o `const mock* = [...]` que quede en pages |

**Entregable:** Frontend donde toda data viene de API (real o mock via MSW).

---

### Fase 5 — Consolidación y Validación (Semana 9-10)

| Tarea | Detalle |
|-------|---------|
| 5.1 | Ejecutar todos los tests existentes y verificar que pasan |
| 5.2 | Verificar flujo completo en modo demo (MSW) |
| 5.3 | Verificar flujo completo en modo producción (API real) |
| 5.4 | Documentar la arquitectura final en un ADR |
| 5.5 | Actualizar los diagramas de flujo para reflejar la realidad del código |
| 5.6 | Integrar los nodos faltantes del LangGraph (N1-N17) como wrapping de use cases existentes |
| 5.7 | Implementar HITL service real (no solo ports) |
| 5.8 | Verificar que feature flags del backend realmente bloquean endpoints no-ready |

---

## 6. Checklist de Auditoría Técnica

### Frontend

- [ ] Solo existe UN directorio de componentes (`components/`)
- [ ] No existe `src/components/` como directorio paralelo
- [ ] No existe `app/dashboard/` (solo `app/(app)/`)
- [ ] No existe `app/demo/` como directorio de rutas
- [ ] Ninguna page contiene `const mock`, `const DATA`, o datos hardcodeados
- [ ] Todas las pages hacen fetch a la API via el client generado
- [ ] MSW handlers cubren todos los endpoints que las pages necesitan
- [ ] `useAppModeStore` se usa activamente para controlar UI demo vs prod
- [ ] Existe error boundary a nivel de layout
- [ ] Cada page tiene loading, error, y empty state
- [ ] No hay imports cruzados entre `@/src/` y `@/components/`
- [ ] `lib/mockData.ts` no existe (datos mock solo en `mocks/`)
- [ ] No hay mensajes en español en código con UI en inglés (o viceversa, pero consistente)

### Backend

- [ ] No existe `MOCK_*` variables en código fuente (fuera de tests)
- [ ] No existen `_Default*Service` que retornen datos ficticios
- [ ] La entidad `Project` tiene una sola definición canónica
- [ ] Ningún módulo importa `from src.{otro_modulo}.domain.models`
- [ ] Si se comparte un enum (ej: `AlertSeverity`), está en un shared kernel
- [ ] `coherence/engine.py` legacy está eliminado (solo `engine_v2.py`)
- [ ] Feature flags se verifican en cada endpoint protegido
- [ ] `example_prompts.py` no está en `/src/` (movido a tests o docs)
- [ ] Cada bounded context puede testearse en aislamiento

### Orquestación

- [ ] Los 17 nodos del LangGraph están implementados como funciones
- [ ] Cada nodo wrappea un use case existente (no duplica lógica)
- [ ] El GraphState tiene todos los campos necesarios (ya cumplido: 48 campos)
- [ ] HITL tiene service implementation (no solo ports)
- [ ] Hay tests de integración para el flujo completo del grafo

### Separación Demo/Producción

- [ ] `NEXT_PUBLIC_APP_MODE` controla el modo (demo/production)
- [ ] En demo: MSW intercepta todas las llamadas HTTP
- [ ] En producción: MSW no se inicializa
- [ ] No hay rutas exclusivas de demo (demo es un modo, no una ruta)
- [ ] El backend no tiene modo demo (siempre responde con datos reales)
- [ ] Mock data solo existe en: `apps/web/mocks/` y `tests/`

---

## 7. Riesgos si no se Corrige

### Escalabilidad

- Agregar un nuevo módulo (ej: "Gestión de Riesgos") requerirá decidir: ¿creo componentes en `components/` o en `src/components/features/`? ¿Creo ruta en `(app)/` o en `dashboard/`? Esta ambigüedad se multiplica con cada feature.
- El backend no puede crecer a microservicios si los bounded contexts importan modelos de dominio entre sí.

### Equipo

- Un desarrollador nuevo necesita semanas para entender qué es demo y qué es real.
- Dos developers trabajando en paralelo en el mismo componente (pero en directorios diferentes) generarán conflictos silenciosos.
- No hay convención clara: ¿Pydantic BaseModel o dataclass para entidades? Cada developer elegirá diferente.

### Mantenimiento

- Corregir un bug en `CoherenceGauge` requiere preguntarse: ¿cuál de las dos versiones es la que se usa? ¿Se usa alguna en algún sitio que no conozco?
- Actualizar una dependencia (ej: Recharts) puede romper un componente que nadie sabía que existía en el directorio paralelo.
- Los 8 documentos mock en `documents/page.tsx` no se actualizarán cuando el modelo de datos del backend cambie, creando divergencia silenciosa.

### Inversión

- Cada hora de desarrollo futuro en el frontend tiene un ~30% de overhead por la necesidad de navegar la ambigüedad estructural.
- El refactor será más costoso cuanto más tiempo se aplace — cada nueva feature se construirá sobre la estructura desordenada.
- Tests escritos contra datos mock inline no validan el producto real.

### Producto Final

- **Riesgo máximo:** Un cliente en una demo de ventas ve datos incorrectos porque se navegó a una ruta "producción" que muestra mocks. O peor: un usuario real ve datos de "Torre Skyline" que nunca existieron.
- La experiencia de usuario será inconsistente entre rutas que usan API real (projects/page.tsx funciona) y rutas que no (documents/page.tsx muestra ficción).
- La credibilidad del producto se ve comprometida si un evaluador técnico audita el frontend.

---

## Anexo A — Análisis de Implementación vs Flow Diagram

### Componentes del Diagrama de Flujo v2.2.1

| Componente | Estado | Cobertura |
|------------|--------|-----------|
| LangGraph Orchestration (17 nodos) | Parcial | 41% — 7 nodos ad-hoc implementados |
| GraphState (48 campos) | Completo | 100% |
| Coherence Engine v2 (6 categorías) | Completo | 100% — subscores, pesos, reglas |
| WBS/BOM Generation | Completo | 100% — modelos, servicios, AI extraction |
| Procurement Planning | Completo | 100% — lead time, Incoterms, plan generator |
| Stakeholder Management + RACI | Completo | 100% — extracción, clasificación, matriz |
| Document Ingestion Pipeline | Parcial | 70% — parsers existen, clasificación por categoría falta |
| PII Anonymizer | Completo | 100% — detección, redacción, config por tenant |
| Human-in-the-Loop | Esqueleto | 40% — solo ports/domain, sin service |
| MCP Gateway | Completo | 100% — allowlist, rate limit, audit |
| Redis Event Bus | Completo | 100% — tenant-scoped pub/sub |
| Database Schema + RLS | Completo | 95% — todas las tablas core, políticas RLS |

### Gaps Críticos entre Diagrama y Código

1. **10 nodos de LangGraph no implementados** — Los servicios existen como código aislado pero no están conectados como nodos del grafo orquestador.
2. **Clasificación de cláusulas por categoría de coherencia no implementada** — El extractor de cláusulas no asigna SCOPE/BUDGET/TIME/etc.
3. **HITL Gate (N13) y Human Approval Checkpoint (N14)** — Solo stubs.
4. **Citation Validator (N15)** — No existe.
5. **Final Assembler (N16)** — No existe.

---

## Anexo B — Mapa de Bounded Contexts Actual

```
┌─────────────────────────────────────────────────────────────┐
│                    BOUNDED CONTEXTS                          │
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │ Projects │───▶│  Documents   │───▶│  Coherence      │   │
│  │          │    │  - Clauses   │    │  - Rules R1-R20 │   │
│  │          │    │  - SubClauses│    │  - 6 categorías │   │
│  └────┬─────┘    └──────┬───────┘    └────────┬────────┘   │
│       │                 │                      │            │
│       │    ┌────────────┼───────────┐          │            │
│       │    │            │           │          │            │
│       ▼    ▼            ▼           ▼          │            │
│  ┌──────────────┐ ┌───────────┐ ┌────────┐    │            │
│  │ Stakeholders │ │Procurement│ │Analysis│◄───┘            │
│  │ - RACI       │ │ - WBS/BOM │ │- Graph │                 │
│  │ - Power/Int  │ │ - LeadTime│ │- AI    │                 │
│  └──────────────┘ └───────────┘ └────────┘                 │
│                                                              │
│  ── Dependencias cruzadas detectadas (a corregir): ──       │
│  Analysis → imports Stakeholders.domain ❌                   │
│  Analysis → imports Documents.domain ❌                      │
│  Analysis → imports Procurement.domain ❌                    │
│  Coherence → imports Analysis.domain.enums ❌                │
└─────────────────────────────────────────────────────────────┘
```

**Solución:** Crear un `shared_kernel/` con DTOs y enums compartidos, o usar eventos para comunicación inter-módulo.

---

## Anexo C — Análisis de Entidades (DDD)

### Entidades Principales

| Entidad | Tipo | Módulo | Archivo | Observaciones |
|---------|------|--------|---------|---------------|
| Project | Aggregate Root | projects | `domain/models.py` + `domain/project.py` | **DUPLICADA** — dos representaciones |
| Document | Aggregate Root | documents | `domain/models.py` | Lifecycle correcto (UPLOADED→PARSED) |
| Clause | Entity | documents | `domain/models.py` | Bien definida, con verificación manual |
| SubClause | Entity | documents | `domain/entities/subclause.py` | Frozen dataclass, validación jerárquica |
| CoherenceAlert | Entity | coherence | `domain/alert_mapping.py` | Mapeo determinístico R1-R20 |
| WBSItem | Aggregate Root | procurement | `domain/models.py` | Jerárquico, con presupuesto |
| BOMItem | Entity | procurement | `domain/models.py` | Vinculado a WBS items |
| Stakeholder | Aggregate Root | stakeholders | `domain/models.py` | Con poder/interés |
| RaciAssignment | Entity | stakeholders | `domain/models.py` | Mapeo rol-actividad |
| ReviewItem | Entity | hitl | `domain/entities.py` | Con SLA tracking |
| GraphNode | Value Object | analysis | `domain/models.py` | Frozen, representación grafo |

### Value Objects Identificados

| Value Object | Módulo | Notas |
|--------------|--------|-------|
| CoherenceCategory | coherence | Enum: SCOPE, BUDGET, QUALITY, TECHNICAL, LEGAL, TIME |
| AlertSeverity | analysis | Enum: LOW, MEDIUM, HIGH, CRITICAL — **compartido indebidamente** |
| DocumentStatus | documents | Enum: UPLOADED, QUEUED, PARSING, PARSED, ERROR |
| RACIRole | stakeholders | Enum: RESPONSIBLE, ACCOUNTABLE, CONSULTED, INFORMED |
| HITLStatus | orchestration | Enum: NOT_REQUIRED, PENDING, APPROVED, REJECTED, ESCALATED |
| BOMCategory | procurement | Enum: MATERIAL, EQUIPMENT, SERVICE, CONSUMABLE |

### Casos de Uso Identificados vs Implementados

| Caso de Uso | Módulo | ¿Implementado? |
|-------------|--------|-----------------|
| Upload Document | documents | ✅ Completo |
| Parse Document | documents | ✅ Completo |
| Extract Clauses | documents | ✅ Parcial (sin clasificación por categoría) |
| Calculate Coherence Score | coherence | ✅ Completo |
| Generate WBS from Document | procurement | ✅ Completo |
| Generate BOM from WBS | procurement | ✅ Completo |
| Extract Stakeholders | stakeholders | ✅ Completo |
| Generate RACI Matrix | stakeholders | ✅ Completo |
| Analyze Document (orchestrated) | analysis | ⚠️ Parcial (7/17 nodos) |
| Review Item (HITL) | hitl | ❌ Solo ports |
| Decision Intelligence Execute | decision_intelligence | ⚠️ Skeleton con defaults peligrosos |

### Problemas de Modelado

1. **Lógica de negocio en el frontend:** Las funciones `getSeverity()`, `getStatusIcon()`, `getStatusColor()` en pages del frontend replican lógica que debería estar en el dominio backend.
2. **Entidades implícitas:** No existe una entidad `DashboardSummary` o `ProjectOverview` que el frontend necesita — por eso se hardcodea.
3. **Inconsistencia en representación:** `Project` existe como Pydantic BaseModel Y como dataclass. Decidir uno.
4. **Reglas de coherencia hardcodeadas:** R1-R20 están en un diccionario Python. Considerar una configuración externalizada.

---

*Fin de la auditoría. Este documento debe tratarse como base para la toma de decisiones arquitectónicas.*
