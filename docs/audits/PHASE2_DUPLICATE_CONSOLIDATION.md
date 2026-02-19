# Tarea 2.2 — Consolidacion de Duplicados

**Fecha:** 2026-02-19
**Base:** `PHASE2_COMPONENT_AUDIT.md` (Tarea 2.1)

---

## 1. Decisiones por Par Duplicado

### Par 1: CoherenceGauge — CONSOLIDADO

| Aspecto | Ganador: `components/coherence/` | Eliminado: `src/components/features/coherence/` |
|---------|----------------------------------|--------------------------------------------------|
| Lineas | 111 | 88 |
| Rendering | recharts `RadialBarChart` | SVG puro |
| Animacion | `useCountUp` + recharts animation | CSS transition |
| Color por score | `getScoreColor()` (3 niveles) | Siempre `var(--primary)` |
| Label | Auto-genera via `getScoreLabel()` | Requiere prop `label` |
| Usado por pages | Si (2+ pages) | Si (1 page) |

**Acciones realizadas:**
1. Eliminado `src/components/features/coherence/CoherenceGauge.tsx`
2. Actualizado `app/(dashboard)/projects/[id]/coherence/page.tsx`:
   - Import cambiado de `@/src/components/features/coherence/` a `@/components/coherence/`
   - Removido prop `label="Good"` (ahora auto-generado por `getScoreLabel(78)` = "Good")
3. Actualizado `CoherenceGauge.test.tsx`:
   - Import redirigido a `@/components/coherence/CoherenceGauge`
   - Agregado mock de `useCountUp` (retorna valor directo sin animacion)
   - Agregado mock de `recharts` (renderiza `<div>` en lugar de SVG)
   - Removido prop `label` del render del test

### Par 2: ScoreCard — CONSOLIDADO

| Aspecto | Ganador: `components/coherence/` | Eliminado: `src/components/features/coherence/` |
|---------|----------------------------------|--------------------------------------------------|
| Lineas | 125 | 47 |
| Rendering | `Card` + `Badge` + iconos Lucide | `<button>` plano |
| Categoria | `CATEGORY_CONFIG` con icono/color por categoria | Solo texto |
| Animacion | `useCountUp` | Ninguna |
| Severidad | Badge geometrico (circulo/diamante/triangulo) | No tiene |
| Usado por pages | Si (2+ pages) | Si (1 page) |

**Acciones realizadas:**
1. Eliminado `src/components/features/coherence/ScoreCard.tsx`
2. Page ya importaba de `@/components/coherence/ScoreCard` (actualizado junto con CoherenceGauge)
3. Actualizado `ScoreCard.test.tsx`:
   - Import redirigido a `@/components/coherence/ScoreCard`
   - Agregado mock de `useCountUp`
   - Cambiado `category="Scope"` a `category="SCOPE"` (clave del config)
   - Ajustadas assertions al DOM del componente Card (texto "Scope", "20%")

### Par 3: Evidence/PDF — COMPLEMENTARIOS (no duplicados)

**Decision: AMBOS SE MANTIENEN — reorganizacion de directorios**

| Componente | Ubicacion | Proposito |
|-----------|-----------|-----------|
| `EntityValidationCard` | `components/evidence/` | UI de validacion Gate 6 (approve/reject con dialogo) |
| `EntityValidationList` | `components/evidence/` | Lista filtrable con search, stats |
| `PDFViewer` | `components/pdf/` → **movido a `components/evidence/pdf/`** | Visor PDF real con react-pdf, zoom, rotate, highlights |
| `HighlightLayer` | `components/pdf/` → **movido a `components/evidence/pdf/`** | Overlay de highlights sobre PDF |
| `PdfEvidenceViewer` | `src/components/features/evidence/` | Test harness para evidencia PDF (TDD) |
| `MobileEvidenceViewer` | `src/components/features/evidence/` | Visor mobile con virtualizacion (TDD) |
| Utilities (watermark, highlight) | `src/components/features/evidence/` | Logica de negocio testada (TDD) |

**Acciones realizadas:**
1. Movido `components/pdf/PDFViewer.tsx` → `components/evidence/pdf/PDFViewer.tsx`
2. Movido `components/pdf/HighlightLayer.tsx` → `components/evidence/pdf/HighlightLayer.tsx`
3. Movido `components/pdf/pdf-viewer.css` → `components/evidence/pdf/pdf-viewer.css`
4. Eliminado `components/pdf/HighlightSearchBar.tsx` (dead code, no referenciado ni por PDFViewer)
5. Eliminado directorio `components/pdf/` (ahora vacio)
6. Imports internos intactos (`./HighlightLayer` sigue siendo correcto)
7. `src/components/features/evidence/` se mantiene como incubadora TDD

### Par 4: Stakeholders — COMPLEMENTARIOS (no duplicados)

**Decision: AMBOS SE MANTIENEN — funcionalidades distintas**

| Componente | Ubicacion | Proposito |
|-----------|-----------|-----------|
| `StakeholderMatrix` | `components/stakeholders/` | Matriz poder/interes con drag-and-drop (`@dnd-kit`) |
| `StakeholderRaciWorkbench` | `src/components/features/stakeholders/` | Asignacion RACI con grid y reglas de validacion |
| `RaciGrid` | `src/components/features/stakeholders/` | Grid de asignacion R/A/C/I |
| `SeverityBadge` | `src/components/features/stakeholders/` | Badge de severidad |
| `raci-grid-rules` | `src/components/features/stakeholders/` | Reglas de negocio RACI |

**NO se toco nada**: ambos conjuntos son funcionalidad diferente y necesaria. Cuando se integre RACI en pages, se movera a `components/stakeholders/`.

---

## 2. Dead Code Eliminado (Fase A del Audit)

### `components/dashboard/` — ELIMINADO COMPLETO (5 archivos)

| Archivo | Lineas | Razon |
|---------|--------|-------|
| `ActivityTimeline.tsx` | ~60 | 0 importaciones |
| `GaugeChart.tsx` | ~80 | 0 importaciones |
| `KPICards.tsx` | ~50 | 0 importaciones |
| `RecentProjectsCard.tsx` | ~40 | 0 importaciones |
| `TopAlertsCard.tsx` | ~50 | 0 importaciones |

### `components/coherence/` — 2 archivos eliminados

| Archivo | Lineas | Razon |
|---------|--------|-------|
| `CoherenceScoreModal.tsx` | ~50 | 0 importaciones |
| `CategoryBreakdownCard.tsx` | ~40 | 0 importaciones |

### `components/layout/` — 3 archivos eliminados

| Archivo | Lineas | Razon |
|---------|--------|-------|
| `AppLayout.tsx` | ~30 | Duplica la funcion de `layout.tsx` |
| `AppLayout.test.tsx` | ~20 | Test del componente eliminado |
| `sidebar.tsx` | ~40 | Variante no usada de AppSidebar |

### `components/pdf/` — 1 archivo eliminado, 2 movidos

| Archivo | Accion | Razon |
|---------|--------|-------|
| `HighlightSearchBar.tsx` | ELIMINADO | 0 importaciones, ni siquiera por PDFViewer |
| `PDFViewer.tsx` | Movido a `evidence/pdf/` | Util pero no importado aun |
| `HighlightLayer.tsx` | Movido a `evidence/pdf/` | Dependencia de PDFViewer |
| `pdf-viewer.css` | Movido a `evidence/pdf/` | CSS de PDFViewer |

---

## 3. Resumen de Impacto

| Metrica | Antes | Despues |
|---------|-------|---------|
| Archivos de componentes duplicados | 4 (2 CoherenceGauge + 2 ScoreCard) | 0 |
| Archivos dead code | 12 | 0 |
| Archivos eliminados total | — | 14 (2 duplicados + 11 dead + 1 orphan) |
| Archivos movidos | — | 3 (pdf/ → evidence/pdf/) |
| Imports actualizados (pages) | — | 1 page (`coherence/page.tsx`) |
| Tests actualizados | — | 2 (CoherenceGauge.test, ScoreCard.test) |
| Directorios eliminados | — | 2 (`components/dashboard/`, `components/pdf/`) |

### Estructura resultante de `components/`:

```
components/
├── auth/
│   ├── ProtectedRoute.tsx          ← ACTIVO
│   └── ProtectedRoute.test.tsx
├── coherence/
│   ├── AlertsDistribution.tsx      ← ACTIVO (6 componentes, 0 dead code)
│   ├── BreakdownChart.tsx
│   ├── CategoryDetail.tsx
│   ├── CoherenceGauge.tsx          ← GANADOR del duplicado
│   ├── RadarView.tsx
│   └── ScoreCard.tsx               ← GANADOR del duplicado
├── evidence/
│   ├── EntityValidationCard.tsx    ← ACTIVO
│   ├── EntityValidationList.tsx
│   ├── index.ts
│   └── pdf/
│       ├── HighlightLayer.tsx      ← MOVIDO desde components/pdf/
│       ├── PDFViewer.tsx           ← MOVIDO desde components/pdf/
│       └── pdf-viewer.css
├── landing-page-content.tsx        ← ACTIVO
├── layout/
│   ├── AppHeader.tsx               ← ACTIVO (3 archivos, 0 dead code)
│   ├── AppHeader.test.tsx
│   ├── AppSidebar.tsx
│   ├── AppSidebar.test.tsx
│   ├── DemoBanner.tsx
│   └── DemoBanner.test.tsx
├── providers/
│   ├── AuthSync.tsx                ← ACTIVO
│   └── AuthSync.test.tsx
├── stakeholders/
│   └── StakeholderMatrix.tsx       ← ACTIVO
└── ui/
    └── ... (37 primitivos shadcn/ui)
```

**WeightAdjuster.tsx** se mantiene en `src/components/features/coherence/` — es unico (no duplicado) y solo usado por tests (TDD incubator).
