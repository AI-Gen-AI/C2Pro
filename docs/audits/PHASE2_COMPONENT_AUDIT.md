# Auditoria de Componentes: `components/` vs `src/components/` — C2Pro

**Fecha:** 2026-02-19
**Tarea:** 2.1 del Plan de Reorganizacion
**Alcance:** Inventario componente por componente, deteccion de duplicados, clasificacion, recomendacion

---

## 1. Resumen Ejecutivo

| Metrica | Valor |
|---------|-------|
| Archivos en `components/` | 93 (incluyendo tests) |
| Archivos en `src/components/` | 75 (incluyendo tests) |
| **Total archivos componente** | **168** |
| Pares duplicados (mismo concepto) | **4 pares** |
| Componentes en `components/` sin uso | **8** (dashboard/*, pdf/*) |
| Componentes en `src/` sin uso por pages | **~20** (solo usados por tests) |
| Componentes importados por pages desde `components/` | 16 |
| Componentes importados por pages desde `src/components/` | 3 |

### Problema Central

Existen **dos directorios paralelos de componentes** con filosofias diferentes:

| Directorio | Filosofia | Caracteristicas |
|------------|-----------|-----------------|
| `components/` | **Production-first** | Componentes visuales ricos, usan recharts/react-pdf/dnd-kit, shadcn/ui, importados por pages activas |
| `src/components/features/` | **TDD-first** | Componentes minimalistas con tests exhaustivos, HTML semantico puro, la mayoria NO importados por ninguna page |

Esto viola la regla **R22** del contrato Demo vs Prod: *"Existe UN solo directorio de componentes"*.

---

## 2. Inventario Completo por Directorio

### 2.1 `components/` — 93 archivos

#### `components/auth/` (2 componentes + 2 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `ProtectedRoute.tsx` | ~30 | hooks/useAuth | `dashboard/projects/page.tsx` | ACTIVO |
| `ProtectedRoute.test.tsx` | — | — | — | Test |

#### `components/coherence/` (8 componentes, 0 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `CoherenceGauge.tsx` | 111 | recharts, useCountUp | `(app)/page.tsx`, `dashboard/page.tsx` | ACTIVO - **DUPLICADO** |
| `ScoreCard.tsx` | 125 | Card, Badge, lucide, useCountUp | `(app)/page.tsx`, `dashboard/page.tsx` | ACTIVO - **DUPLICADO** |
| `BreakdownChart.tsx` | 73 | recharts BarChart | `(app)/page.tsx`, `dashboard/page.tsx`, `coherence/page.tsx` | ACTIVO |
| `RadarView.tsx` | 53 | recharts RadarChart | `(app)/page.tsx`, `dashboard/page.tsx`, `coherence/page.tsx` | ACTIVO |
| `AlertsDistribution.tsx` | ~60 | recharts | `(app)/page.tsx`, `dashboard/page.tsx`, `coherence/page.tsx` | ACTIVO |
| `CategoryDetail.tsx` | ~80 | — | `(app)/page.tsx`, `dashboard/page.tsx`, `coherence/page.tsx` | ACTIVO |
| `CoherenceScoreModal.tsx` | ~50 | Dialog | Ninguna page | DEAD CODE |
| `CategoryBreakdownCard.tsx` | ~40 | Card | Ninguna page | DEAD CODE |

#### `components/dashboard/` (5 componentes, 0 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `ActivityTimeline.tsx` | ~60 | — | **NINGUNO** | DEAD CODE |
| `GaugeChart.tsx` | ~80 | recharts PieChart | **NINGUNO** | DEAD CODE |
| `KPICards.tsx` | ~50 | Card | **NINGUNO** | DEAD CODE |
| `RecentProjectsCard.tsx` | ~40 | Card | **NINGUNO** | DEAD CODE |
| `TopAlertsCard.tsx` | ~50 | Card, Badge | **NINGUNO** | DEAD CODE |

> **HALLAZGO CRITICO**: Todo el directorio `components/dashboard/` es dead code. 5 componentes sin una sola importacion.

#### `components/evidence/` (2 componentes + 1 index)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `EntityValidationCard.tsx` | 299 | Card, Badge, AlertDialog, lucide | EntityValidationList | ACTIVO |
| `EntityValidationList.tsx` | 227 | EntityValidationCard, ScrollArea, Select, Input | `evidence/page.tsx` | ACTIVO |
| `index.ts` | ~5 | re-exports | — | Barrel |

#### `components/pdf/` (3 componentes + 1 CSS)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `PDFViewer.tsx` | 399 | react-pdf, pdfjs, HighlightLayer | **NINGUNO** | DEAD CODE |
| `HighlightLayer.tsx` | ~80 | tipos Highlight | PDFViewer (dead) | DEAD CODE |
| `HighlightSearchBar.tsx` | ~60 | Input, lucide | **NINGUNO** | DEAD CODE |
| `pdf-viewer.css` | ~20 | — | PDFViewer (dead) | DEAD CODE |

> **HALLAZGO**: `PDFViewer.tsx` es una implementacion completa con react-pdf (zoom, rotate, download, highlights) pero NO la importa ninguna page. Candidato a rescatar cuando se implemente la page de visualizacion PDF.

#### `components/layout/` (5 componentes + 4 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `AppHeader.tsx` | ~60 | lucide | Todos los layouts | ACTIVO - CRITICO |
| `AppSidebar.tsx` | ~120 | lucide, Link | Todos los layouts | ACTIVO - CRITICO |
| `AppLayout.tsx` | ~30 | AppHeader, AppSidebar | Ninguna page | DEAD CODE (duplica layout) |
| `DemoBanner.tsx` | 34 | — | Todos los layouts | ACTIVO - **VIOLA R14** |
| `sidebar.tsx` | ~40 | — | Ninguna page | DEAD CODE |

#### `components/providers/` (1 componente + 1 test)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `AuthSync.tsx` | ~30 | useAuth | `app/providers.tsx` | ACTIVO |

#### `components/stakeholders/` (1 componente)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `StakeholderMatrix.tsx` | 244 | @dnd-kit/core, hooks/use-stakeholders | `(app)/stakeholders/page.tsx` | ACTIVO |

#### `components/landing-page-content.tsx` (1 componente)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `landing-page-content.tsx` | ~100 | — | `app/page.tsx` | ACTIVO |

#### `components/ui/` (37 componentes shadcn/ui + 18 tests)

Todos son primitivos de shadcn/ui. Usados extensivamente por toda la app. **No requieren accion.**

---

### 2.2 `src/components/` — 75 archivos

#### `src/components/features/alerts/` (3 componentes + 3 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `AlertReviewCenter.tsx` | 346 | Ninguna dep externa | `dashboard/projects/[id]/alerts/page.tsx` (ruta DUPLICADA) | ACTIVO |
| `AlertUndoToast.tsx` | ~40 | alert-undo | Solo tests | SOLO TESTS |
| `alert-undo.ts` | ~30 | — | AlertUndoToast | SOLO TESTS |

#### `src/components/features/coherence/` (3 componentes + 3 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `CoherenceGauge.tsx` | 88 | Solo cn (SVG puro) | **NINGUNO** | **DUPLICADO** de `components/coherence/CoherenceGauge.tsx` |
| `ScoreCard.tsx` | 47 | Solo cn (boton minimo) | **NINGUNO** | **DUPLICADO** de `components/coherence/ScoreCard.tsx` |
| `WeightAdjuster.tsx` | 109 | — (HTML range inputs) | **NINGUNO** | UNICO, solo tests |

#### `src/components/features/compliance/` (2 componentes + 3 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `CookieConsentBanner.tsx` | 143 | consent-gating | Solo tests | SOLO TESTS |
| `LegalDisclaimerModal.tsx` | ~80 | — | Solo tests | SOLO TESTS |
| `consent-gating.ts` | ~30 | — | CookieConsentBanner | SOLO TESTS |

#### `src/components/features/documents/` (2 componentes + 2 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `DocumentUploadDropzone.tsx` | 129 | — (HTML puro) | Solo tests | SOLO TESTS |
| `UploadQueue.tsx` | ~60 | — | Solo tests | SOLO TESTS |

#### `src/components/features/evidence/` (5 componentes + 5 utils + 8 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `PdfEvidenceViewer.tsx` | 177 | highlight-style, watermark-token, watermark-sanitize, EvidenceWatermarkOverlay | Solo tests | **OVERLAP** con `components/pdf/PDFViewer.tsx` |
| `MobileEvidenceViewer.tsx` | ~100 | — | Solo tests | UNICO |
| `EvidenceWatermarkOverlay.tsx` | ~50 | watermark-sanitize | PdfEvidenceViewer | UNICO |
| `highlight-mapper.ts` | ~40 | — | highlight-style | UNICO |
| `highlight-navigation.ts` | ~30 | — | Solo tests | UNICO |
| `highlight-style.ts` | ~40 | highlight-mapper | PdfEvidenceViewer | UNICO |
| `watermark-sanitize.ts` | ~30 | — | EvidenceWatermarkOverlay, PdfEvidenceViewer | UNICO |
| `watermark-token.ts` | ~25 | — | PdfEvidenceViewer | UNICO |

#### `src/components/features/filters/` (2 componentes + 1 util + 2 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `FilterPanel.tsx` | 50 | filter-session-persistence | Solo tests | SOLO TESTS |
| `FilterPersistenceHarness.tsx` | ~30 | filter-session-persistence | Integration tests | Test harness |
| `filter-session-persistence.ts` | ~40 | — | FilterPanel | SOLO TESTS |

#### `src/components/features/onboarding/` (1 componente + 2 utils + 3 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `OnboardingEntry.tsx` | 52 | — (HTML puro) | Solo tests | SOLO TESTS |
| `onboarding-preferences.ts` | ~30 | — | Solo tests | SOLO TESTS |
| `sample-project-bootstrap.ts` | ~40 | — | Solo tests | SOLO TESTS |

#### `src/components/features/processing/` (1 componente + 1 test)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `ProcessingStepper.tsx` | 190 | — (EventSource SSE) | Solo tests | SOLO TESTS |

#### `src/components/features/projects/` (1 componente + 1 test)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `ProjectListTable.tsx` | 60 | ProjectListItemResponse, Link | `(app)/projects/page.tsx` | ACTIVO |

#### `src/components/features/shortcuts/` (2 componentes + 1 harness + 2 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `ScopedKeyboardShortcuts.tsx` | 73 | — (window.addEventListener) | ShortcutScopeHarness | SOLO TESTS |
| `ShortcutHelpDialog.tsx` | ~60 | — | ShortcutScopeHarness | SOLO TESTS |
| `ShortcutScopeHarness.tsx` | ~40 | ScopedKeyboardShortcuts, ShortcutHelpDialog | Integration tests | Test harness |

#### `src/components/features/stakeholders/` (3 componentes + 2 utils + 4 tests)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `StakeholderRaciWorkbench.tsx` | 140 | SeverityBadge, RaciGrid, raci-grid-rules | Integration tests | **OVERLAP** (diferente funcion que StakeholderMatrix) |
| `RaciGrid.tsx` | ~80 | — | StakeholderRaciWorkbench | SOLO TESTS |
| `SeverityBadge.tsx` | ~30 | — | StakeholderRaciWorkbench | SOLO TESTS |
| `raci-grid-rules.ts` | ~50 | — | StakeholderRaciWorkbench | SOLO TESTS |
| `stakeholder-scatter-mapper.ts` | ~40 | — | Solo tests | SOLO TESTS |

#### `src/components/layout/projects/` (1 componente + 1 test)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `ProjectTabs.tsx` | 43 | Link, lucide | `(app)/projects/[id]/layout.tsx` | ACTIVO |

#### `src/components/layout/theme/` (1 componente + 1 test)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `ThemeToggle.tsx` | 27 | next-themes | **NINGUNO** | SOLO TESTS |

#### `src/components/providers/sentry/` (1 componente + 1 test)

| Archivo | Lineas | Dependencias | Importado por | Estado |
|---------|--------|--------------|---------------|--------|
| `SentryInit.tsx` | 43 | @sentry/react, config/env | `app/providers.tsx` | ACTIVO |

---

## 3. Analisis de Duplicados

### 3.1 CoherenceGauge — DOS IMPLEMENTACIONES

| Aspecto | `components/coherence/` (111 lineas) | `src/components/features/coherence/` (88 lineas) |
|---------|--------------------------------------|--------------------------------------------------|
| Renderizado | recharts `RadialBarChart` | SVG puro (`<circle>`, `strokeDasharray`) |
| Animacion | `useCountUp` hook + recharts animation | CSS transition (`duration-[1500ms]`) |
| Color por score | `getScoreColor()` (verde/naranja/rojo) | Siempre `var(--primary)` |
| Label | Auto-generado (`getScoreLabel()`) | Prop `label` requerido |
| Props extra | `calculatedAt` (timestamp) | — |
| Tests | 0 tests | 1 test |
| Imports activos | 2+ pages | 0 pages |

**Veredicto**: **MANTENER `components/`** (mas rico, activamente usado). El de `src/` es un prototipo TDD que nunca escalo a produccion.

### 3.2 ScoreCard — DOS IMPLEMENTACIONES

| Aspecto | `components/coherence/` (125 lineas) | `src/components/features/coherence/` (47 lineas) |
|---------|--------------------------------------|--------------------------------------------------|
| Renderizado | `Card`, `CardContent`, `Badge` + iconos lucide | `<button>` plano |
| Categoria | `CATEGORY_CONFIG` con icono, color, label por categoria | Solo texto `{category}` |
| Animacion | `useCountUp` | Ninguna |
| Severidad | Badge con forma geometrica (circulo/diamante/triangulo) | No tiene |
| Alerts count | Badge rojo circular | Solo texto "{alertCount} alerts" |
| Tests | 0 tests | 1 test |
| Imports activos | 2+ pages | 0 pages |

**Veredicto**: **MANTENER `components/`** (componente completo de produccion). El de `src/` es un skeleton de test.

### 3.3 Evidence/PDF — DOS ENFOQUES

| Aspecto | `components/pdf/` + `components/evidence/` | `src/components/features/evidence/` |
|---------|----------------------------------------------|--------------------------------------|
| PDF rendering | `react-pdf` real con `pdfjs` worker | HTML mock (`data-testid="pdf-page-canvas"`) |
| Highlights | `HighlightLayer` sobre PDF real | CSS classes via `resolveHighlightStyle()` |
| Watermarks | No implementado | `EvidenceWatermarkOverlay`, `watermark-token`, `watermark-sanitize` |
| Validacion entidades | `EntityValidationCard` + `EntityValidationList` (Gate 6) | No tiene |
| Mobile | No implementado | `MobileEvidenceViewer` con virtualizacion |
| Navigation | No implementado | `highlight-navigation` con cursor |
| Imports activos | EntityValidationList por evidence/page | Solo tests |

**Veredicto**: **COMPLEMENTARIOS**, no duplicados. Cuando se integre el visor PDF real:
1. Mantener `components/pdf/PDFViewer.tsx` como renderizador real
2. Integrar watermark y highlight utilities de `src/components/features/evidence/`
3. Mantener `components/evidence/EntityValidationCard|List` para validacion
4. Mover todo a un solo directorio `components/evidence/`

### 3.4 Stakeholders — DOS FUNCIONALIDADES DIFERENTES

| Aspecto | `components/stakeholders/StakeholderMatrix` (244 lineas) | `src/components/features/stakeholders/` (6 archivos) |
|---------|-----------------------------------------------------------|------------------------------------------------------|
| Proposito | Matriz de poder/interes (drag-and-drop entre cuadrantes) | Workbench RACI (asignar R/A/C/I a stakeholders por actividad) |
| Interaccion | `@dnd-kit` drag-and-drop | Click para asignar rol |
| Data source | `useStakeholders(projectId)` hook con API | Estado local hardcodeado |
| Business rules | `mapStakeholderQuadrant()` | `resolveRaciGridViolations()` |
| Imports activos | `(app)/stakeholders/page.tsx` | Solo integration tests |

**Veredicto**: **AMBOS SE NECESITAN** — son funcionalidades distintas (Power/Interest matrix vs RACI grid). Consolidar en `components/stakeholders/`.

---

## 4. Clasificacion Global

### 4.1 Componentes ACTIVOS (importados por pages reales)

| # | Componente | Ubicacion | Importado por |
|---|-----------|-----------|---------------|
| 1 | `AppHeader` | `components/layout/` | 3 layouts |
| 2 | `AppSidebar` | `components/layout/` | 3 layouts |
| 3 | `DemoBanner` | `components/layout/` | 3 layouts |
| 4 | `AuthSync` | `components/providers/` | providers.tsx |
| 5 | `SentryInit` | `src/components/providers/sentry/` | providers.tsx |
| 6 | `CoherenceGauge` | `components/coherence/` | 2+ pages |
| 7 | `ScoreCard` | `components/coherence/` | 2+ pages |
| 8 | `BreakdownChart` | `components/coherence/` | 3+ pages |
| 9 | `RadarView` | `components/coherence/` | 3+ pages |
| 10 | `AlertsDistribution` | `components/coherence/` | 3+ pages |
| 11 | `CategoryDetail` | `components/coherence/` | 3+ pages |
| 12 | `EntityValidationCard` | `components/evidence/` | EntityValidationList |
| 13 | `EntityValidationList` | `components/evidence/` | evidence/page.tsx |
| 14 | `StakeholderMatrix` | `components/stakeholders/` | stakeholders/page.tsx |
| 15 | `ProtectedRoute` | `components/auth/` | dashboard/projects/page.tsx |
| 16 | `LandingPageContent` | `components/` | page.tsx |
| 17 | `ProjectListTable` | `src/components/features/projects/` | (app)/projects/page.tsx |
| 18 | `ProjectTabs` | `src/components/layout/projects/` | projects/[id]/layout.tsx |
| 19 | `AlertReviewCenter` | `src/components/features/alerts/` | dashboard/projects/[id]/alerts/page.tsx |
| 20 | Primitivos `ui/` (37) | `components/ui/` | Toda la app |

**Total componentes activos: 20 + 37 ui = 57**

### 4.2 Componentes DEAD CODE (0 importaciones fuera de tests)

| # | Componente | Ubicacion | Razon |
|---|-----------|-----------|-------|
| 1 | `ActivityTimeline` | `components/dashboard/` | Nunca importado |
| 2 | `GaugeChart` | `components/dashboard/` | Nunca importado |
| 3 | `KPICards` | `components/dashboard/` | Nunca importado |
| 4 | `RecentProjectsCard` | `components/dashboard/` | Nunca importado |
| 5 | `TopAlertsCard` | `components/dashboard/` | Nunca importado |
| 6 | `PDFViewer` | `components/pdf/` | Nunca importado (pero util — rescatar) |
| 7 | `HighlightLayer` | `components/pdf/` | Solo por PDFViewer (dead) |
| 8 | `HighlightSearchBar` | `components/pdf/` | Nunca importado |
| 9 | `AppLayout` | `components/layout/` | Duplica layout.tsx |
| 10 | `sidebar` | `components/layout/` | Variante no usada de AppSidebar |
| 11 | `CoherenceScoreModal` | `components/coherence/` | Nunca importado |
| 12 | `CategoryBreakdownCard` | `components/coherence/` | Nunca importado |

**Total dead code en `components/`: 12 componentes**

### 4.3 Componentes SOLO-TESTS (existen para test suites, no importados por pages)

| # | Componente | Test Suite |
|---|-----------|------------|
| 1 | `CoherenceGauge` (src) | S3 coherence |
| 2 | `ScoreCard` (src) | S3 coherence |
| 3 | `WeightAdjuster` | S3 coherence |
| 4 | `AlertUndoToast` + `alert-undo` | S3-04 |
| 5 | `CookieConsentBanner` + `consent-gating` | S3-09 GDPR |
| 6 | `LegalDisclaimerModal` | S3-09 |
| 7 | `DocumentUploadDropzone` | S3 documents |
| 8 | `UploadQueue` | S3 documents |
| 9 | `PdfEvidenceViewer` + utilities | S3-01, S3-02, S3-03 |
| 10 | `MobileEvidenceViewer` | S3-02 |
| 11 | `EvidenceWatermarkOverlay` | S3-03 |
| 12 | `FilterPanel` + `filter-session-persistence` | S3-10 |
| 13 | `OnboardingEntry` + utils | S3-11 |
| 14 | `ProcessingStepper` | S2-10 |
| 15 | `ScopedKeyboardShortcuts` + `ShortcutHelpDialog` | S3-05 |
| 16 | `StakeholderRaciWorkbench` + `RaciGrid` + utils | S3-07 |
| 17 | `ThemeToggle` | theme test |

**Total solo-tests en `src/`: ~20 componentes**

> **Patron**: `src/components/features/` contiene componentes escritos con TDD puro (test suite IDs: S2-10, S3-01 a S3-11). Son prototipos funcionales con HTML semantico pero sin estilos de produccion. Representan la **especificacion ejecutable** de features futuras.

---

## 5. Mapa de Dependencias Cruzadas

```
app/providers.tsx
├── @/components/providers/AuthSync
└── @/src/components/providers/sentry/SentryInit

app/(app)/layout.tsx
├── @/components/layout/AppSidebar
├── @/components/layout/AppHeader
└── @/components/layout/DemoBanner

app/(app)/page.tsx
├── @/components/coherence/CoherenceGauge      ← components/
├── @/components/coherence/ScoreCard           ← components/
├── @/components/coherence/BreakdownChart      ← components/
├── @/components/coherence/RadarView           ← components/
├── @/components/coherence/AlertsDistribution  ← components/
└── @/components/coherence/CategoryDetail      ← components/

app/(app)/projects/page.tsx
└── @/src/components/features/projects/ProjectListTable  ← src/

app/(app)/projects/[id]/layout.tsx
└── @/src/components/layout/projects/ProjectTabs  ← src/

app/(app)/stakeholders/page.tsx
└── @/components/stakeholders/StakeholderMatrix  ← components/

app/(app)/projects/[id]/evidence/page.tsx
└── @/components/evidence (EntityValidationList)  ← components/

app/dashboard/projects/[id]/alerts/page.tsx  (RUTA DUPLICADA)
└── @/src/components/features/alerts/AlertReviewCenter  ← src/
```

**Problema**: Las pages importan de AMBOS directorios sin patron claro. Incluso `providers.tsx` importa un componente de cada directorio.

---

## 6. Plan de Consolidacion Recomendado

### Fase A: Eliminar dead code (sin riesgo)

| Accion | Archivos | Riesgo |
|--------|----------|--------|
| Eliminar `components/dashboard/` completo | 5 archivos | ZERO — ninguna importacion |
| Eliminar `components/layout/AppLayout.tsx` | 1 archivo | ZERO — duplica layout |
| Eliminar `components/layout/sidebar.tsx` | 1 archivo | ZERO — variante no usada |
| Eliminar `components/coherence/CoherenceScoreModal.tsx` | 1 archivo | ZERO — nunca importado |
| Eliminar `components/coherence/CategoryBreakdownCard.tsx` | 1 archivo | ZERO — nunca importado |
| **Total** | **9 archivos** | |

### Fase B: Eliminar duplicados (mantener el mejor)

| Par duplicado | Mantener | Eliminar | Accion imports |
|---------------|----------|----------|----------------|
| CoherenceGauge | `components/coherence/` | `src/components/features/coherence/CoherenceGauge.tsx` | Los tests de src/ deben apuntar a components/ |
| ScoreCard | `components/coherence/` | `src/components/features/coherence/ScoreCard.tsx` | Los tests de src/ deben apuntar a components/ |

### Fase C: Mover componentes de `src/` activos a `components/`

| Componente | Origen | Destino | Porque |
|-----------|--------|---------|--------|
| `ProjectListTable` | `src/components/features/projects/` | `components/projects/` | Importado por page activa |
| `ProjectTabs` | `src/components/layout/projects/` | `components/layout/` | Importado por layout activo |
| `SentryInit` | `src/components/providers/sentry/` | `components/providers/` | Importado por providers.tsx |
| `AlertReviewCenter` | `src/components/features/alerts/` | `components/alerts/` | Importado por page (cuando se elimine ruta duplicada) |

### Fase D: Decidir sobre componentes solo-tests

**Opcion recomendada**: Mantener `src/components/features/` como directorio de **componentes en desarrollo** (TDD-first) hasta que se integren en pages reales. Cuando se integren:

1. Enriquecer con estilos shadcn/ui
2. Mover a `components/`
3. Actualizar imports de tests

**Componentes prioritarios para promocion** (tienen business logic testada):
- `WeightAdjuster` — necesario para coherence settings
- `DocumentUploadDropzone` — necesario para upload flow
- `ProcessingStepper` — necesario para processing view
- `StakeholderRaciWorkbench` + `RaciGrid` — necesario para RACI page
- `CookieConsentBanner` — necesario para GDPR compliance
- `FilterPanel` — necesario para cualquier page con filtros

### Fase E: Consolidar evidence/pdf

| Paso | Accion |
|------|--------|
| 1 | Crear `components/evidence/pdf/` |
| 2 | Mover `components/pdf/PDFViewer.tsx` a `components/evidence/pdf/PDFViewer.tsx` |
| 3 | Integrar watermark utilities de `src/` en el PDFViewer real |
| 4 | Mantener `EntityValidationCard` y `EntityValidationList` en `components/evidence/` |
| 5 | Eliminar `components/pdf/` (ahora vacio) |

---

## 7. Estructura Objetivo

```
components/
├── auth/
│   └── ProtectedRoute.tsx
├── coherence/
│   ├── AlertsDistribution.tsx
│   ├── BreakdownChart.tsx
│   ├── CategoryDetail.tsx
│   ├── CoherenceGauge.tsx      ← mantener este (recharts)
│   ├── RadarView.tsx
│   └── ScoreCard.tsx           ← mantener este (con iconos)
├── evidence/
│   ├── EntityValidationCard.tsx
│   ├── EntityValidationList.tsx
│   ├── pdf/
│   │   ├── PDFViewer.tsx       ← movido de components/pdf/
│   │   └── HighlightLayer.tsx
│   └── index.ts
├── layout/
│   ├── AppHeader.tsx
│   ├── AppSidebar.tsx
│   ├── DemoBanner.tsx
│   └── ProjectTabs.tsx         ← movido de src/components/layout/
├── projects/
│   └── ProjectListTable.tsx    ← movido de src/components/features/
├── providers/
│   ├── AuthSync.tsx
│   └── SentryInit.tsx          ← movido de src/components/providers/
├── stakeholders/
│   ├── StakeholderMatrix.tsx
│   └── (futuro: RaciGrid, cuando se integre)
├── landing-page-content.tsx
└── ui/
    └── ... (37 primitivos shadcn/ui)

src/components/features/        ← "incubadora" TDD
├── alerts/                     ← promote cuando pages lo necesiten
├── compliance/                 ← promote para GDPR
├── documents/                  ← promote para upload flow
├── filters/                    ← promote para filter UX
├── onboarding/                 ← promote para onboarding
├── processing/                 ← promote para SSE processing
└── shortcuts/                  ← promote para keyboard shortcuts
```

---

## 8. Metricas de Impacto

| Metrica | Antes | Despues (Fase A+B+C) |
|---------|-------|----------------------|
| Archivos totales componentes | 168 | ~150 |
| Dead code eliminado | 0 | 12 archivos |
| Duplicados resueltos | 4 pares | 0 pares |
| Directorios de componentes activos | 2 (`components/`, `src/components/`) | 1 principal + 1 incubadora |
| Imports cruzados entre directorios | ~5 | 0 en produccion |

---

*Este documento debe ser referenciado al ejecutar las tareas 2.2-2.5 del plan de reorganizacion.*
