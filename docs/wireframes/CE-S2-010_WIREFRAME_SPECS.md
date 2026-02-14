# CE-S2-010: Wireframe Specifications - 6 Vistas Core

**Actividad:** Wireframes 6 Vistas Core
**Dominio:** UX/UI
**Story Points:** 2
**Fecha:** 2026-01-16
**Estado:** ✅ Especificaciones Completadas

---

## 📋 Tabla de Contenidos

1. [Project Dashboard](#1-project-dashboard)
2. [Evidence Viewer](#2-evidence-viewer-crítica)
3. [Alerts Center](#3-alerts-center)
4. [Stakeholder Map](#4-stakeholder-map)
5. [RACI Matrix Viewer](#5-raci-matrix-viewer)
6. [Project List](#6-project-list)
7. [Design System Guidelines](#design-system-guidelines)

---

## Contexto de Diseño

**Stack:** Next.js 14 + Tailwind CSS + shadcn/ui
**Estilo:** Enterprise Clean (denso en datos, escaneable, minimalista)
**Requisito Crítico:** Human-in-the-loop (Gate 6) - Validación humana obligatoria para acciones críticas
**Paleta:** Monocromática profesional con uso semántico del color

---

## 1. Project Dashboard

### 1.1 Estructura del Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Header (sticky, h-16, bg-background, border-b)                  │
│ [Logo] [Breadcrumb] [Spacer] [Search] [Notifications] [Avatar] │
├──────────┬──────────────────────────────────────────────────────┤
│          │ Main Content (p-6, overflow-y-auto)                  │
│ Sidebar  │                                                      │
│ (w-64)   │ ┌─────────────────────────────────────────────┐    │
│          │ │ Coherence Score Gauge (Card, h-80)          │    │
│ Nav      │ │ [Gauge Chart: 0-100]                        │    │
│ Links    │ │ Trend indicator (+2 vs last week)           │    │
│          │ └─────────────────────────────────────────────┘    │
│ -Dashbrd │                                                      │
│ -Project │ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │
│ -Evidnce │ │ KPI  │ │ KPI  │ │ KPI  │ │ KPI  │               │
│ -Alerts  │ │ Card │ │ Card │ │ Card │ │ Card │               │
│ -Stakhld │ └──────┘ └──────┘ └──────┘ └──────┘               │
│ -RACI    │                                                      │
│          │ ┌─────────────────────────────────────────────┐    │
│          │ │ Activity Timeline (Card)                    │    │
│          │ │ [Timeline of recent events]                 │    │
│          │ └─────────────────────────────────────────────┘    │
│          │                                                      │
│          │ ┌────────────┐ ┌────────────────────────────┐      │
│          │ │ Top Alerts │ │ Recent Projects            │      │
│          │ │ (Card)     │ │ (Card with DataTable)      │      │
│          │ └────────────┘ └────────────────────────────┘      │
└──────────┴──────────────────────────────────────────────────────┘
```

### 1.2 Componentes Clave (shadcn/ui)

| Componente | Uso | Props Relevantes |
|------------|-----|------------------|
| `Card` | Container para cada sección (Score, KPIs, Activity) | `className="shadow-sm"` |
| `Sidebar` | Navegación principal (collapsible) | `collapsible="icon"` |
| `Badge` | Estado de proyectos (Active, On Hold, Completed) | `variant="default\|warning\|destructive"` |
| `Progress` | Budget used indicator | `value={62}` |
| `Avatar` | Usuario actual en header | `fallback="JD"` |
| `Separator` | Divisores entre secciones | `orientation="horizontal"` |
| `Skeleton` | Loading state para KPIs | `className="h-20 w-full"` |
| **Custom:** `GaugeChart` | Coherence Score 0-100 | Usar recharts con configuración circular |
| **Custom:** `TimelineItem` | Eventos recientes | Lista de actividades con timestamp |

### 1.3 KPI Cards - Detalles

**Grid Layout:** `grid grid-cols-4 gap-4`

1. **Coherence Score**
   - Gauge chart central (0-100)
   - Color dinámico: Red (<60), Amber (60-79), Green (80-100)
   - Trend badge: `+2` (verde) o `-5` (rojo)

2. **Active Projects**
   - Número grande: `text-4xl font-bold`
   - Subtítulo: "3 at risk" con Badge destructive

3. **Open Alerts**
   - Número con breakdown: "7 (3 critical)"
   - Link directo a Alerts Center

4. **Budget Health**
   - Progress bar con porcentaje
   - Colores: Verde (<80%), Ámbar (80-95%), Rojo (>95%)

### 1.4 Interacciones Críticas

#### 1.4.1 Coherence Score Drill-down
```
User clicks Gauge → Sheet lateral se abre
├─ Muestra breakdown por dimensión (Legal, Financial, Schedule...)
├─ Lista de alertas que afectan el score
└─ Botón "View Full Report" → navega a /projects/{id}/coherence
```

#### 1.4.2 Critical Alert Preview
```
Si hay alertas Critical en Top Alerts Card:
├─ Badge rojo pulsante (animation-pulse)
├─ Click en alerta → Dialog modal (NO navegación directa)
│  ├─ Título: Alert ID + Severity badge
│  ├─ Descripción corta
│  ├─ Botones:
│  │   ├─ "View Evidence" (secondary) → abre Evidence Viewer
│  │   └─ "Acknowledge & Resolve" (primary) → REQUIERE CONFIRMACIÓN
└─ Confirmación obligatoria:
    └─ Dialog con Checkbox "I have reviewed the evidence and..."
        └─ Botón "Confirm Resolution" (disabled hasta check)
```

**Regla Human-in-the-loop:**
> ⚠️ Ninguna alerta Critical puede resolverse desde el Dashboard sin abrir el Dialog de confirmación.

---

## 2. Evidence Viewer (CRÍTICA)

### 2.1 Estructura del Layout

**Pantalla completa con split view (Resizable panels)**

```
┌─────────────────────────────────────────────────────────────────┐
│ Header (h-14, bg-muted, border-b)                               │
│ [← Back] [Project: PROJ-001 ▾] [Alert: AL-123 ▾] [🔍 Search]   │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────┬────────────────────────────────┐   │
│ │ Panel Izquierdo (40%)    │ Panel Derecho (60%)            │   │
│ │ (PDF/Document Viewer)    │ (Traceability & Data Panel)    │   │
│ │                          │ ┌────────────────────────────┐ │   │
│ │ ┌─────────────────────┐  │ │ Tabs:                      │ │   │
│ │ │ Contract_Final.pdf  │  │ │ [Extracted Data]           │ │   │
│ │ │ Page 12/58          │  │ │ [Alerts]                   │ │   │
│ │ │                     │  │ │ [Linkages]                 │ │   │
│ │ │ Cláusula 4.2.1      │  │ └────────────────────────────┘ │   │
│ │ │ highlighted in 🟡  │  │                                │   │
│ │ │                     │  │ ┌────────────────────────────┐ │   │
│ │ │ "En caso de retraso │  │ │ Extracted Entity:          │ │   │
│ │ │  superior a 30 días"│  │ │ Type: Penalty Clause       │ │   │
│ │ │                     │  │ │ Confidence: 87%   ⚠️       │ │   │
│ │ │ [Text is selectable]│  │ │                            │ │   │
│ │ └─────────────────────┘  │ │ Linked to:                 │ │   │
│ │                          │ │ • WBS-3.1 (Commissioning)  │ │   │
│ │ Toolbar:                 │ │ • Alert AL-123 (High)      │ │   │
│ │ [Zoom] [Rotate] [⬇️]     │ │                            │ │   │
│ │                          │ │ ┌───────────────────────┐  │ │   │
│ │                          │ │ │ ⚠️ Low Confidence     │  │ │   │
│ │                          │ │ │ Requires Validation   │  │ │   │
│ │                          │ │ └───────────────────────┘  │ │   │
│ │                          │ │                            │ │   │
│ │                          │ │ [✓ Approve] [✗ Reject]     │ │   │
│ │                          │ └────────────────────────────┘ │   │
│ └──────────────────────────┴────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Componentes Clave

| Componente | Uso | Props/Config |
|------------|-----|--------------|
| `ResizablePanelGroup` | Split view container | `direction="horizontal"` |
| `ResizablePanel` | Panel izquierdo (PDF) y derecho (Data) | `defaultSize={40}` (left), `{60}` (right) |
| `ResizableHandle` | Divisor draggable | `withHandle` |
| `Tabs` | Navegación entre Extracted/Alerts/Linkages | `defaultValue="extracted"` |
| `Card` | Container para cada entidad extraída | `className="border-l-4 border-amber-500"` (si confidence <90%) |
| `Alert` | Warning box para low confidence | `variant="warning"` |
| `Button` | Approve/Reject actions | `variant="default\|destructive"` |
| `Select` | Filtros de Alert/Clause | `defaultValue="all"` |
| `Badge` | Confidence score, Severity | `variant="secondary"` |
| **Custom:** `PDFViewer` | Visor de documentos con highlight | react-pdf + custom highlight layer |
| **Custom:** `HighlightLayer` | Overlay para resaltado de texto | Canvas con coordenadas del bbox |

### 2.3 Panel Derecho - Tabs en Detalle

#### Tab 1: Extracted Data
- Lista de entidades extraídas del documento actual
- Cada entidad en un Card:
  - Header: Tipo de entidad + Confidence badge
  - Body: Texto extraído (max 200 chars, expandible)
  - Footer: Botones de validación

#### Tab 2: Alerts
- DataTable de alertas vinculadas al documento/página actual
- Columnas: ID | Severity | Type | Status | Actions
- Filtro por Severity (Critical, High, Medium, Low)

#### Tab 3: Linkages
- Árbol de relaciones:
  ```
  Document: Contract_Final.pdf
  ├─ Clause 4.2.1
  │  ├─ Linked WBS: WBS-3.1, WBS-3.2
  │  ├─ Linked BOM: BOM-12
  │  └─ Alerts: AL-123, AL-124
  └─ Clause 5.1.3
     └─ ...
  ```
- Componente: `Accordion` o `TreeView` (custom)

### 2.4 Interacciones Críticas - Human-in-the-loop

#### 2.4.1 Aprobación de Entidad Extraída (Confidence < 90%)

```javascript
// Flujo de validación obligatoria
User clicks "Approve" en entidad con confidence 87%
├─ Dialog modal se abre:
│  ├─ Título: "Confirm Extracted Data"
│  ├─ Contenido:
│  │  ├─ Muestra el texto original (PDF) lado a lado con el extraído
│  │  ├─ Permite edición inline del texto extraído
│  │  ├─ Checkbox: "I confirm this data is accurate"
│  │  └─ Textarea opcional: "Validation notes" (requerido si edita)
│  └─ Botones:
│     ├─ "Cancel" (secondary)
│     └─ "Approve & Save" (primary, disabled hasta checkbox)
└─ Al confirmar:
   ├─ PATCH /api/extracted-entities/{id} { validated: true, confidence: 100 }
   ├─ Toast success: "Entity validated"
   └─ Card border cambia de amber a green
```

**Componentes:**
- `Dialog` para modal de confirmación
- `Checkbox` para acknowledgement
- `Textarea` para notas (si edita)
- `Alert` con ícono de warning mostrando texto original vs. extraído

#### 2.4.2 Rechazo de Entidad Extraída

```javascript
User clicks "Reject"
├─ Dialog modal se abre:
│  ├─ Título: "Reject Extracted Data"
│  ├─ Textarea obligatorio: "Reason for rejection" (min 10 chars)
│  └─ Botones:
│     ├─ "Cancel"
│     └─ "Confirm Rejection" (disabled hasta min length)
└─ Al confirmar:
   ├─ PATCH /api/extracted-entities/{id} { rejected: true, reason: "..." }
   ├─ Alert automática se crea: "Rejected entity requires review"
   └─ Card se oculta con opción "Show rejected items"
```

#### 2.4.3 Navegación Bidireccional PDF ↔ Data

**Highlight Sync:**
1. User hace click en texto del PDF
   → Panel derecho scroll automático a la entidad correspondiente
   → Card se resalta con animation (border-pulse)

2. User hace click en una entidad del panel derecho
   → PDF scroll automático a la página correcta
   → Texto se resalta en amarillo
   → Zoom automático al bbox (opcional)

**Implementación:**
```javascript
// Context compartido entre paneles
const [activeHighlight, setActiveHighlight] = useState(null)

// En PDFViewer
<span onClick={() => setActiveHighlight(entityId)}>

// En DataPanel
<Card className={activeHighlight === entity.id ? "ring-2 ring-primary" : ""}>
```

### 2.5 Reglas de Diseño Específicas

1. **Color de Highlight según Confidence:**
   - `confidence >= 95%`: Verde (#10b981, opacity 0.2)
   - `confidence 80-94%`: Ámbar (#f59e0b, opacity 0.3)
   - `confidence < 80%`: Rojo (#ef4444, opacity 0.3)

2. **Estados de Validación:**
   - No validado: Border izquierdo ámbar (4px)
   - Aprobado: Border verde + Checkmark icon
   - Rechazado: Opacidad 50%, strikethrough en tipo de entidad

3. **Responsividad:**
   - Desktop: Split view 40/60
   - Tablet: Stack vertical (PDF arriba, Data abajo)
   - Mobile: Tabs en lugar de split (Tab: PDF | Tab: Data)

---

## 3. Alerts Center

### 3.1 Estructura del Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Header (h-16, sticky)                                           │
│ Alerts Center     [🔍 Search alerts...]     [+ New Alert]       │
├─────────────────────────────────────────────────────────────────┤
│ Filters Bar (h-14, bg-muted/50)                                 │
│ [Severity ▾] [Type ▾] [Status ▾] [Project ▾] [Clear Filters]   │
├─────────────────────────────────────────────────────────────────┤
│ Main Content                                                     │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ DataTable (shadcn/ui)                                     │   │
│ │ ┌──────────────────────────────────────────────────────┐  │   │
│ │ │ [✓] │ ID     │ Severity│ Type  │ Project│ Status  │⚡│  │   │
│ │ ├──────────────────────────────────────────────────────┤  │   │
│ │ │ [ ] │ AL-001 │🔴Critical│Legal │PROJ-001│ Open   │…│  │   │
│ │ │ [ ] │ AL-002 │🟠High   │Finance│PROJ-001│ Open   │…│  │   │
│ │ │ [ ] │ AL-003 │🟡Medium │Schedule│PROJ-002│Resolved│…│  │   │
│ │ │ ...                                                    │  │   │
│ │ └──────────────────────────────────────────────────────┘  │   │
│ │ Pagination: ← 1 2 3 ... 8 →             Showing 1-20/156  │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ [Bulk Actions: Assign | Change Status | Export] (disabled)     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Componentes Clave

| Componente | Uso | Props/Config |
|------------|-----|--------------|
| `DataTable` | Tabla principal de alertas | `columns`, `data`, `sorting`, `filtering` |
| `Select` | Filtros dropdown | `multiple`, `clearable` |
| `Badge` | Severity, Status, Type indicators | `variant="destructive\|warning\|default"` |
| `Checkbox` | Selección múltiple | `onCheckedChange` |
| `Button` | Acciones rápidas (Assign, Resolve) | `variant="ghost"` (iconos) |
| `Sheet` | Panel lateral para detalles de alerta | `side="right"`, `className="w-2/5"` |
| `Popover` | Quick actions menu (tres puntos) | `align="end"` |
| `Input` | Búsqueda global | `type="search"`, `debounce={300}` |
| `DropdownMenu` | Bulk actions | `disabled={!hasSelection}` |

### 3.3 Columnas de la DataTable

```typescript
const columns: ColumnDef<Alert>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected()}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
      />
    ),
  },
  {
    accessorKey: "id",
    header: "ID",
    cell: ({ row }) => (
      <Button variant="link" onClick={() => openAlertDetail(row.original.id)}>
        {row.getValue("id")}
      </Button>
    ),
  },
  {
    accessorKey: "severity",
    header: "Severity",
    cell: ({ row }) => {
      const severity = row.getValue("severity")
      const variants = {
        critical: "destructive",
        high: "warning",
        medium: "secondary",
        low: "outline"
      }
      const icons = {
        critical: "🔴",
        high: "🟠",
        medium: "🟡",
        low: "⚪"
      }
      return (
        <Badge variant={variants[severity]}>
          {icons[severity]} {severity.toUpperCase()}
        </Badge>
      )
    },
    // Sorting por severidad numéricamente (critical=4, high=3, ...)
    sortingFn: (rowA, rowB) => severityScore(rowA) - severityScore(rowB)
  },
  {
    accessorKey: "type",
    header: "Type",
    cell: ({ row }) => (
      <Badge variant="outline">{row.getValue("type")}</Badge>
    ),
  },
  {
    accessorKey: "project",
    header: "Project",
    cell: ({ row }) => row.getValue("project"),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status")
      const variant = status === "open" ? "default" : "secondary"
      return <Badge variant={variant}>{status}</Badge>
    },
  },
  {
    id: "actions",
    header: "",
    cell: ({ row }) => <AlertRowActions alert={row.original} />,
  },
]
```

### 3.4 Interacciones Críticas - Human-in-the-loop

#### 3.4.1 Resolver Alerta Critical/High

```javascript
User clicks "Resolve" en alerta con severity Critical
├─ Sheet lateral se abre (desde la derecha, w-2/5)
│  ├─ Header:
│  │  ├─ Alert ID + Severity badge
│  │  └─ Botón cerrar (X)
│  ├─ Body (scroll):
│  │  ├─ Section: Alert Details
│  │  │  ├─ Type, Description, Created date
│  │  │  └─ Link to Evidence: "View in Evidence Viewer →"
│  │  ├─ Section: Affected Items
│  │  │  └─ Lista de WBS/BOM/Clauses vinculados
│  │  ├─ Separator
│  │  ├─ Section: Resolution (solo si severity >= High)
│  │  │  ├─ Alert box: "⚠️ This alert requires validation"
│  │  │  ├─ Textarea obligatorio: "Resolution notes" (min 20 chars)
│  │  │  ├─ Select: "Root cause" (opciones predefinidas)
│  │  │  └─ Checkbox: "I have reviewed the evidence and..."
│  │  └─ File upload opcional: "Attach supporting documents"
│  └─ Footer:
│     ├─ "Cancel" (secondary)
│     └─ "Confirm Resolution" (primary, disabled hasta validaciones)
└─ Al confirmar:
   ├─ PATCH /api/alerts/{id} { status: "resolved", resolution: {...} }
   ├─ Audit log entry se crea automáticamente
   ├─ Toast success con opción Undo (10s)
   └─ Fila se actualiza en DataTable (status badge cambia)
```

**Reglas de Validación (Gate 6):**

| Severity | Requiere Resolution Notes | Requiere Checkbox | Requiere Root Cause |
|----------|---------------------------|-------------------|---------------------|
| Critical | ✅ (min 50 chars) | ✅ | ✅ |
| High | ✅ (min 20 chars) | ✅ | ✅ |
| Medium | ✅ (min 10 chars) | ❌ | ❌ |
| Low | ❌ | ❌ | ❌ |

#### 3.4.2 Ignorar Alerta (Dismiss)

```javascript
User clicks "Dismiss" en AlertRowActions menu
├─ Popover confirmation aparece:
│  ├─ "Are you sure you want to dismiss this alert?"
│  ├─ Textarea: "Reason (optional but recommended)"
│  └─ Botones:
│     ├─ "Cancel"
│     └─ "Dismiss" (variant="destructive")
└─ Al confirmar:
   ├─ PATCH /api/alerts/{id} { status: "dismissed", reason: "..." }
   ├─ Fila se mueve a filtro "Dismissed" (oculta por defecto)
   └─ Notificación al Project Owner (si severity >= High)
```

**IMPORTANTE:**
- Dismiss != Resolve
- Dismissed alerts no cuentan para Coherence Score
- Critical alerts NO pueden ser dismissed sin approval de Admin/Owner

#### 3.4.3 Bulk Actions con Validación

```javascript
User selecciona 5 alertas (2 Critical, 3 Medium) y hace click "Bulk Resolve"
├─ Dialog modal se abre:
│  ├─ Título: "Resolve 5 Alerts"
│  ├─ Warning:
│  │  "⚠️ 2 of the selected alerts are Critical and require individual review."
│  ├─ Lista:
│  │  ├─ AL-001 (Critical) - ❌ Cannot bulk resolve
│  │  ├─ AL-002 (Critical) - ❌ Cannot bulk resolve
│  │  ├─ AL-003 (Medium) - ✅ Can bulk resolve
│  │  ├─ AL-004 (Medium) - ✅ Can bulk resolve
│  │  └─ AL-005 (Medium) - ✅ Can bulk resolve
│  ├─ Textarea: "Resolution notes for 3 eligible alerts"
│  └─ Botones:
│     ├─ "Resolve 3 Eligible Alerts"
│     └─ "Cancel"
└─ Al confirmar:
   ├─ Bulk PATCH para las 3 elegibles
   ├─ Toast: "3 alerts resolved, 2 require individual review"
   └─ Las 2 Critical quedan seleccionadas (prompt user a revisarlas)
```

### 3.5 Filtros Avanzados

**Componente:** `DataTableFacetedFilter` (shadcn/ui example)

```javascript
// Filtros disponibles
const filters = {
  severity: ["critical", "high", "medium", "low"],
  type: ["Legal", "Financial", "Schedule", "Technical", "Scope"],
  status: ["open", "in_progress", "resolved", "dismissed"],
  project: [...allProjects], // dinámico
}

// Filtros con contadores
<Select>
  <SelectItem value="critical">
    Critical <Badge variant="secondary">3</Badge>
  </SelectItem>
  <SelectItem value="high">
    High <Badge variant="secondary">12</Badge>
  </SelectItem>
</Select>
```

**Búsqueda Global:**
- Busca en: ID, Description, Type, Project name
- Debounce de 300ms
- Highlight de términos en resultados

---

## 4. Stakeholder Map

### 4.1 Estructura del Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Header (h-16)                                                   │
│ Stakeholder Map - PROJ-001     [+ Add Stakeholder] [Export]    │
├─────────────────────────────────────────────────────────────────┤
│ Toolbar (h-12, bg-muted/50)                                     │
│ [Filter by Role ▾] [Show Inactive] [View: Matrix | List]       │
├─────────────────────────────────────────────────────────────────┤
│ Main Content: Power/Interest Matrix                             │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │                    High Interest                          │   │
│ │ ┌────────────────────────┬────────────────────────┐       │   │
│ │ │                        │                        │       │   │
│ │ │   Manage Closely       │   Keep Satisfied       │       │   │
│ │ │   (High Power,         │   (High Power,         │       │   │
│ │ │    High Interest)      │    Low Interest)       │       │   │
│ │ │                        │                        │       │   │
│ │ │  [Avatar: CEO]         │  [Avatar: CFO]         │  High │   │
│ │ │  [Avatar: PM]          │  [Avatar: Legal]       │  Power│   │
│ │ │                        │                        │       │   │
│ │ ├────────────────────────┼────────────────────────┤       │   │
│ │ │                        │                        │       │   │
│ │ │   Keep Informed        │   Monitor              │       │   │
│ │ │   (Low Power,          │   (Low Power,          │       │   │
│ │ │    High Interest)      │    Low Interest)       │   Low │   │
│ │ │                        │                        │  Power│   │
│ │ │  [Avatar: Engineer]    │  [Avatar: Vendor]      │       │   │
│ │ │  [Avatar: QA]          │                        │       │   │
│ │ │                        │                        │       │   │
│ │ └────────────────────────┴────────────────────────┘       │   │
│ │           Low Interest                                    │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ Legend: [🔴 Critical] [🟠 Important] [🟢 Monitoring]            │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Componentes Clave

| Componente | Uso | Props/Config |
|------------|-----|--------------|
| **Custom:** `StakeholderMatrix` | Grid 2x2 interactivo | Drag & drop de avatares |
| `Avatar` | Representación de stakeholder | `size="lg"`, tooltip con nombre |
| `Popover` | Detalle de stakeholder al hover/click | `trigger="hover"`, `side="top"` |
| `Card` | Container de cada cuadrante | `className="min-h-80"` |
| `Badge` | Nivel de engagement (Critical/Important) | `className="absolute top-1 right-1"` |
| `Select` | Filtro de roles | `multiple` |
| `Tabs` | Vista alternativa: Matrix | List | `defaultValue="matrix"` |
| `Sheet` | Edición de stakeholder | `side="right"` |
| `Separator` | Divisores entre cuadrantes | `orientation="vertical\|horizontal"` |

### 4.3 Stakeholder Avatar - Detalles

**En la matriz:**
```jsx
<div className="relative group">
  <Avatar className="cursor-pointer hover:ring-2 ring-primary">
    <AvatarImage src={stakeholder.photo} />
    <AvatarFallback>{stakeholder.initials}</AvatarFallback>
  </Avatar>
  {stakeholder.engagement === "critical" && (
    <Badge variant="destructive" className="absolute -top-1 -right-1 h-4 w-4 p-0">
      !
    </Badge>
  )}
</div>
```

**Popover al hover:**
```
┌──────────────────────────────┐
│ John Doe                     │
│ Role: Project Manager        │
│ Organization: Client Corp    │
│ ────────────────────────     │
│ Power: High (8/10)           │
│ Interest: High (9/10)        │
│ ────────────────────────     │
│ [Edit] [View RACI] [Contact] │
└──────────────────────────────┘
```

### 4.4 Interacciones Críticas

#### 4.4.1 Añadir Stakeholder

```javascript
User clicks "+ Add Stakeholder"
├─ Sheet lateral se abre (desde la derecha)
│  ├─ Form:
│  │  ├─ Input: Name* (required)
│  │  ├─ Input: Email* (validated)
│  │  ├─ Input: Organization
│  │  ├─ Select: Role* (Client, Contractor, Vendor, Consultant, etc.)
│  │  ├─ Slider: Power (1-10)* [Visual: 👤────────👥──────────👑]
│  │  ├─ Slider: Interest (1-10)* [Visual: 😴────────😐──────────🔥]
│  │  ├─ Select: Engagement Level (Monitor, Important, Critical)
│  │  ├─ Textarea: Notes
│  │  └─ Upload: Photo (optional)
│  └─ Footer:
│     ├─ "Cancel"
│     └─ "Add Stakeholder" (disabled hasta required fields)
└─ Al guardar:
   ├─ POST /api/stakeholders
   ├─ Avatar aparece en el cuadrante correspondiente (según Power/Interest)
   ├─ Toast success con link "View in RACI →"
   └─ Opcional: Prompt "Add to RACI matrix?"
```

**Validación Human-in-the-loop:**
- No hay validación especial (no es acción crítica)
- Pero si `engagement === "critical"` → Muestra warning:
  > "⚠️ Critical stakeholders require regular communication. Set reminder?"

#### 4.4.2 Mover Stakeholder (Drag & Drop)

```javascript
User arrastra avatar de "Keep Informed" a "Manage Closely"
├─ Visual feedback:
│  ├─ Cursor cambia a "grabbing"
│  ├─ Avatar tiene shadow más grande
│  └─ Cuadrante objetivo tiene border pulsante
├─ Al soltar:
│  ├─ Popover de confirmación aparece:
│  │  "Move John Doe to Manage Closely?"
│  │  "This will update Power: Low → High, Interest: High → High"
│  │  [Cancel] [Confirm Move]
│  └─ Al confirmar:
│     ├─ PATCH /api/stakeholders/{id} { power: 8, interest: 9 }
│     ├─ Avatar se anima al nuevo cuadrante (transition-all duration-300)
│     ├─ Audit log entry
│     └─ Notificación al Project Owner (si engagement = critical)
└─ Si cancela:
   └─ Avatar vuelve a posición original (spring animation)
```

**Componente Drag & Drop:**
- Usar `@dnd-kit/core` (moderno, accesible)
- Snap to grid dentro de cuadrantes
- Colisión detection si hay múltiples avatares

#### 4.4.3 Vista Alternativa: Lista

```javascript
User hace click en "View: List"
├─ Tabs cambia de "Matrix" a "List"
├─ Contenido:
│  └─ DataTable con columnas:
│     ├─ Name (con Avatar)
│     ├─ Role
│     ├─ Organization
│     ├─ Power (Progress bar horizontal)
│     ├─ Interest (Progress bar horizontal)
│     ├─ Engagement (Badge)
│     └─ Actions (Edit, View RACI, Delete)
└─ Sorting/Filtering igual que Alerts Center
```

### 4.5 Reglas de Diseño

**Cuadrantes:**
- Grid 2x2 con `aspect-ratio-square` (cuadrados)
- Fondo: Gradient sutil según cuadrante
  - Manage Closely: `bg-gradient-to-br from-red-50 to-orange-50`
  - Keep Satisfied: `bg-gradient-to-br from-blue-50 to-purple-50`
  - Keep Informed: `bg-gradient-to-br from-green-50 to-teal-50`
  - Monitor: `bg-gradient-to-br from-gray-50 to-slate-50`

**Avatares:**
- Distribución automática con `flex-wrap` si hay muchos
- Máximo 8 avatares por cuadrante (visual comfort)
- Si > 8: Mostrar "+3 more" badge → Click abre Popover con lista

**Engagement Levels:**
```jsx
const engagementConfig = {
  critical: {
    badge: "🔴",
    color: "destructive",
    description: "Requires weekly updates"
  },
  important: {
    badge: "🟠",
    color: "warning",
    description: "Requires bi-weekly updates"
  },
  monitoring: {
    badge: "🟢",
    color: "default",
    description: "Monthly updates sufficient"
  }
}
```

---

## 5. RACI Matrix Viewer

### 5.1 Estructura del Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Header (h-16)                                                   │
│ RACI Matrix - PROJ-001    [Import] [Export] [Auto-Assign AI]   │
├─────────────────────────────────────────────────────────────────┤
│ Toolbar (h-12, bg-muted/50)                                     │
│ [Filter WBS ▾] [Filter Stakeholders ▾] [Show: All | Gaps]      │
├─────────────────────────────────────────────────────────────────┤
│ Main Content: Freezable DataTable                               │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ WBS ID ↕ │ John │ Mary │ Bob  │ Alice│ ...  │ Gaps │      │   │
│ │ (frozen) │  CEO │  PM  │ Eng  │ QA   │      │      │      │   │
│ ├──────────┼──────┼──────┼──────┼──────┼──────┼──────┤      │   │
│ │ WBS-1.0  │  I   │  A   │  R   │  C   │      │  -   │      │   │
│ │ WBS-1.1  │  I   │  A   │  R   │  -   │      │ ⚠️ No C │   │   │
│ │ WBS-1.2  │  -   │  A   │  R   │  C   │      │  -   │      │   │
│ │ WBS-2.0  │  A   │  R   │  C   │  I   │      │  -   │      │   │
│ │ WBS-2.1  │  -   │  -   │  -   │  -   │      │🔴No A,R│    │   │
│ │ ...      │      │      │      │      │      │      │      │   │
│ └──────────┴──────┴──────┴──────┴──────┴──────┴──────┘      │   │
│                     ↕ Scrollable horizontally                    │
│ Legend: R=Responsible A=Accountable C=Consulted I=Informed      │
│                                                                  │
│ Validation Summary:                                              │
│ ✅ 45 WBS items complete  ⚠️ 3 missing Accountable  🔴 1 no R  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Componentes Clave

| Componente | Uso | Props/Config |
|------------|-----|--------------|
| `DataTable` (custom) | Tabla RACI editable | `sticky columns`, `cell editing` |
| `Select` (inline) | Dropdown en cada celda (R, A, C, I, -) | `size="sm"`, trigger on click |
| `Badge` | Indicador de gaps (No A, No R, No C) | `variant="destructive\|warning"` |
| `Popover` | Tooltips explicando R/A/C/I | `trigger="hover"`, `side="top"` |
| `Button` | Auto-Assign AI | `variant="secondary"`, `icon=<Sparkles />` |
| `Sheet` | Panel lateral para validación de fila | `side="right"` |
| `Alert` | Warning de gaps críticos | `variant="destructive"` |
| `Separator` | Divisor entre secciones de WBS | `className="my-2"` |

### 5.3 Estructura de la Tabla

**Configuración:**
```typescript
// Columnas dinámicas según stakeholders
const columns = [
  {
    accessorKey: "wbs_id",
    header: "WBS ID",
    cell: ({ row }) => (
      <div className="font-mono text-sm">
        {row.getValue("wbs_id")}
      </div>
    ),
    // Sticky column
    meta: { sticky: true }
  },
  ...stakeholders.map(stakeholder => ({
    accessorKey: stakeholder.id,
    header: () => (
      <div className="flex flex-col items-center">
        <Avatar size="sm">
          <AvatarImage src={stakeholder.photo} />
          <AvatarFallback>{stakeholder.initials}</AvatarFallback>
        </Avatar>
        <span className="text-xs mt-1">{stakeholder.name}</span>
        <span className="text-xs text-muted-foreground">{stakeholder.role}</span>
      </div>
    ),
    cell: ({ row, column }) => (
      <RACICell
        wbsId={row.original.wbs_id}
        stakeholderId={column.id}
        value={row.original[column.id]}
      />
    ),
    size: 80, // Fixed width
  })),
  {
    accessorKey: "gaps",
    header: "Gaps",
    cell: ({ row }) => <GapsIndicator wbs={row.original} />,
    size: 120
  }
]
```

### 5.4 RACI Cell - Componente Editable

```jsx
function RACICell({ wbsId, stakeholderId, value }) {
  const [isOpen, setIsOpen] = useState(false)

  // Color según valor
  const colorMap = {
    R: "bg-blue-100 text-blue-800 border-blue-300",
    A: "bg-red-100 text-red-800 border-red-300",
    C: "bg-yellow-100 text-yellow-800 border-yellow-300",
    I: "bg-green-100 text-green-800 border-green-300",
    "-": "bg-gray-50 text-gray-400"
  }

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            "w-full h-10 font-semibold border-2 rounded transition-all",
            "hover:scale-105 hover:shadow-sm",
            colorMap[value || "-"]
          )}
        >
          {value || "-"}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-48 p-2">
        <div className="grid grid-cols-2 gap-1">
          {["R", "A", "C", "I", "-"].map(option => (
            <Button
              key={option}
              variant={value === option ? "default" : "outline"}
              size="sm"
              onClick={() => {
                updateRACIAssignment(wbsId, stakeholderId, option)
                setIsOpen(false)
              }}
            >
              {option}
              <span className="ml-1 text-xs text-muted-foreground">
                {raciLabels[option]}
              </span>
            </Button>
          ))}
        </div>
        <Separator className="my-2" />
        <Button variant="ghost" size="sm" className="w-full" onClick={() => {
          openValidationSheet(wbsId)
          setIsOpen(false)
        }}>
          View Details →
        </Button>
      </PopoverContent>
    </Popover>
  )
}

const raciLabels = {
  R: "Responsible",
  A: "Accountable",
  C: "Consulted",
  I: "Informed",
  "-": "None"
}
```

### 5.5 Gaps Indicator

```jsx
function GapsIndicator({ wbs }) {
  const gaps = detectGaps(wbs)

  if (gaps.length === 0) {
    return <Badge variant="outline" className="text-green-600">✓</Badge>
  }

  const hasCritical = gaps.some(g => g.severity === "critical")

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="h-10 px-2">
          <Badge variant={hasCritical ? "destructive" : "warning"}>
            {hasCritical ? "🔴" : "⚠️"} {gaps.length}
          </Badge>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <div className="space-y-2">
          <h4 className="font-semibold">RACI Gaps:</h4>
          {gaps.map((gap, i) => (
            <Alert key={i} variant={gap.severity === "critical" ? "destructive" : "default"}>
              <AlertDescription>{gap.message}</AlertDescription>
            </Alert>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}

// Lógica de detección de gaps
function detectGaps(wbs) {
  const gaps = []
  const assignments = Object.values(wbs).filter(v => v !== wbs.wbs_id && v !== wbs.gaps)

  // Regla 1: Debe haber exactamente 1 Accountable
  const accountableCount = assignments.filter(v => v === "A").length
  if (accountableCount === 0) {
    gaps.push({
      severity: "critical",
      message: "No Accountable assigned (Required: exactly 1)"
    })
  } else if (accountableCount > 1) {
    gaps.push({
      severity: "critical",
      message: `Multiple Accountable (${accountableCount}). Only 1 allowed.`
    })
  }

  // Regla 2: Debe haber al menos 1 Responsible
  const responsibleCount = assignments.filter(v => v === "R").length
  if (responsibleCount === 0) {
    gaps.push({
      severity: "critical",
      message: "No Responsible assigned (Required: at least 1)"
    })
  }

  // Regla 3: Warning si no hay Consulted (no es crítico)
  const consultedCount = assignments.filter(v => v === "C").length
  if (consultedCount === 0) {
    gaps.push({
      severity: "warning",
      message: "No Consulted assigned (Recommended: at least 1)"
    })
  }

  return gaps
}
```

### 5.6 Interacciones Críticas - Human-in-the-loop

#### 5.6.1 Auto-Assign AI (Sugerencias)

```javascript
User clicks "Auto-Assign AI"
├─ Dialog modal se abre:
│  ├─ Título: "AI-Suggested RACI Assignments"
│  ├─ Warning:
│  │  "⚠️ AI suggestions are based on role patterns and WBS structure."
│  │  "Review all assignments before applying."
│  ├─ Preview Table:
│  │  ┌──────────┬──────────┬────────────┬──────────┐
│  │  │ WBS ID   │ Current  │ Suggested  │ Confidence│
│  │  ├──────────┼──────────┼────────────┼──────────┤
│  │  │ WBS-1.1  │ A: None  │ A: Mary PM │   92%    │
│  │  │          │ R: Bob   │ R: Bob     │   95%    │
│  │  ├──────────┼──────────┼────────────┼──────────┤
│  │  │ WBS-2.1  │ No assign│ A: Mary PM │   87%  ⚠️│
│  │  │          │          │ R: Alice QA│   78%  ⚠️│
│  │  └──────────┴──────────┴────────────┴──────────┘
│  ├─ Checkboxes:
│  │  ☑️ Apply suggestions with confidence >= 90%
│  │  ☐ Apply suggestions with confidence >= 80% (requires review)
│  │  ☐ Overwrite existing assignments
│  └─ Botones:
│     ├─ "Review Each" (abre wizard paso a paso)
│     ├─ "Apply Selected" (primary, disabled si no hay checks)
│     └─ "Cancel"
└─ Al aplicar:
   ├─ Bulk PATCH /api/raci-assignments
   ├─ Celdas cambiadas se destacan con animation (flash green)
   ├─ Toast: "12 assignments updated. 3 require manual review."
   └─ Scroll automático a primera celda con confidence < 90%
```

**Regla Human-in-the-loop:**
> ⚠️ Sugerencias con `confidence < 90%` requieren revisión manual. No se aplican automáticamente.

#### 5.6.2 Bulk Edit de Stakeholder Column

```javascript
User hace right-click en header de columna "Mary PM"
├─ Context menu aparece:
│  ├─ "Assign all R to Mary"
│  ├─ "Clear all assignments"
│  ├─ "Copy column"
│  └─ "Remove stakeholder from matrix"
├─ User selecciona "Assign all R to Mary"
├─ Dialog de confirmación:
│  │  "Assign Responsible role to Mary PM for all WBS items?"
│  │  "This will affect 23 rows."
│  │  ⚠️ "This may create multiple Responsible per WBS item."
│  │  Checkbox: "I understand the implications"
│  │  [Cancel] [Confirm Assignment]
└─ Al confirmar:
   ├─ Bulk update
   ├─ Validación post-update: Detectar gaps nuevos
   ├─ Si hay gaps críticos nuevos:
│     └─ Alert: "5 WBS items now have no Accountable. Review required."
   └─ Highlight filas afectadas
```

#### 5.6.3 Validación de Fila Completa

```javascript
User hace click en WBS ID "WBS-2.1" (fila con gaps críticos)
├─ Sheet lateral se abre (desde la derecha, w-1/2)
│  ├─ Header: "WBS-2.1: Commissioning Phase"
│  ├─ Body:
│  │  ├─ Section: WBS Details
│  │  │  ├─ Title, Description, Duration
│  │  │  └─ Parent: WBS-2.0, Children: WBS-2.1.1, WBS-2.1.2
│  │  ├─ Section: Current Assignments
│  │  │  ├─ Table:
│  │  │  │  ┌────────────┬──────┐
│  │  │  │  │ Stakeholder│ Role │
│  │  │  │  ├────────────┼──────┤
│  │  │  │  │ John CEO   │  I   │
│  │  │  │  │ Mary PM    │  -   │
│  │  │  │  │ Bob Eng    │  -   │
│  │  │  │  │ Alice QA   │  -   │
│  │  │  │  └────────────┴──────┘
│  │  │  └─ Alert (destructive):
│  │  │     "🔴 Missing required assignments: Accountable, Responsible"
│  │  ├─ Section: Quick Assign
│  │  │  ├─ "Suggest typical assignments for this WBS type?"
│  │  │  └─ Button: "Get AI Suggestions"
│  │  ├─ Section: Manual Assignment
│  │  │  ├─ Select: Accountable* (required)
│  │  │  ├─ Multi-Select: Responsible* (min 1)
│  │  │  ├─ Multi-Select: Consulted
│  │  │  └─ Multi-Select: Informed
│  │  └─ Textarea: "Assignment notes" (opcional)
│  └─ Footer:
│     ├─ "Cancel"
│     └─ "Save Assignments" (disabled hasta required fields)
└─ Al guardar:
   ├─ PATCH /api/wbs/{id}/raci-assignments
   ├─ Fila en la tabla se actualiza
   ├─ Gaps badge desaparece si se resolvió
   ├─ Toast success
   └─ Sheet se cierra automáticamente
```

### 5.7 Reglas de Diseño

**Colores de Celdas:**
```css
/* Estados */
.raci-cell-R { @apply bg-blue-100 text-blue-800 border-blue-300; }
.raci-cell-A { @apply bg-red-100 text-red-800 border-red-300; }
.raci-cell-C { @apply bg-yellow-100 text-yellow-800 border-yellow-300; }
.raci-cell-I { @apply bg-green-100 text-green-800 border-green-300; }
.raci-cell-empty { @apply bg-gray-50 text-gray-400 border-gray-200; }

/* Interacciones */
.raci-cell:hover { @apply scale-105 shadow-sm; }
.raci-cell-editing { @apply ring-2 ring-primary; }
.raci-cell-updated { @apply animate-flash-green; }
```

**Frozen Column:**
- Primera columna (WBS ID) siempre visible
- `position: sticky`, `left: 0`, `z-index: 10`
- Shadow sutil en el borde derecho para indicar scroll

**Validation Summary:**
- Sticky en la parte inferior (como footer)
- Actualización en tiempo real
- Click en cada métrica filtra la tabla (ej. click "3 missing A" → muestra solo esas filas)

---

## 6. Project List

### 6.1 Estructura del Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Header (h-16)                                                   │
│ Projects     [🔍 Search projects...]     [+ New Project]        │
├─────────────────────────────────────────────────────────────────┤
│ Filters Bar (h-12, bg-muted/50)                                 │
│ [Status ▾] [Coherence Range ▾] [Tenant ▾] [Sort: Recent ▾]     │
├─────────────────────────────────────────────────────────────────┤
│ Main Content: View Toggle                                       │
│ [Table View] [Card View] ← Tabs                                 │
│                                                                  │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ DataTable                                                 │   │
│ │ ┌──────────────────────────────────────────────────────┐  │   │
│ │ │ ID   │Name     │Status│Score│Alerts│Updated  │Actions││  │   │
│ │ ├──────────────────────────────────────────────────────┤  │   │
│ │ │ P-001│Plant EPC│Active│  78 │  7   │2 days ago│  ... ││  │   │
│ │ │ P-002│Refinery │Active│  64 │  12  │1 hour ago│  ... ││  │   │
│ │ │ P-003│Pipeline │OnHold│  92 │  2   │1 week ago│  ... ││  │   │
│ │ │ ...                                                    │  │   │
│ │ └──────────────────────────────────────────────────────┘  │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│ Pagination: ← 1 2 3 ... 12 →           Showing 1-20/237        │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Componentes Clave

| Componente | Uso | Props/Config |
|------------|-----|--------------|
| `DataTable` | Tabla principal de proyectos | Sorting, filtering, pagination |
| `Tabs` | Toggle entre Table/Card view | `defaultValue="table"` |
| `Card` | Vista de tarjetas (alternativa) | `className="hover:shadow-lg"` |
| `Badge` | Status, Score range, Alert count | Variants según estado |
| `Progress` | Coherence Score como barra | `value={78}` |
| `DropdownMenu` | Actions menu (tres puntos) | `align="end"` |
| `Select` | Filtros dropdown | `multiple` para Status |
| `Input` | Búsqueda global | Debounce 300ms |
| `Sheet` | Quick view de proyecto | `side="right"`, `className="w-2/5"` |

### 6.3 Columnas de la DataTable

```typescript
const columns: ColumnDef<Project>[] = [
  {
    accessorKey: "id",
    header: "ID",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{row.getValue("id")}</span>
    ),
  },
  {
    accessorKey: "name",
    header: ({ column }) => (
      <Button
        variant="ghost"
        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
      >
        Name
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: ({ row }) => (
      <Button
        variant="link"
        onClick={() => router.push(`/projects/${row.original.id}`)}
      >
        {row.getValue("name")}
      </Button>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status")
      const variantMap = {
        active: "default",
        on_hold: "warning",
        completed: "secondary",
        archived: "outline"
      }
      return (
        <Badge variant={variantMap[status]}>
          {status.replace("_", " ").toUpperCase()}
        </Badge>
      )
    },
    filterFn: (row, id, value) => value.includes(row.getValue(id)),
  },
  {
    accessorKey: "coherence_score",
    header: ({ column }) => (
      <Button
        variant="ghost"
        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
      >
        Score
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: ({ row }) => {
      const score = row.getValue("coherence_score")
      const color = score >= 80 ? "text-green-600" :
                    score >= 60 ? "text-amber-600" : "text-red-600"
      return (
        <div className="flex items-center gap-2">
          <span className={cn("font-semibold", color)}>{score}</span>
          <Progress value={score} className="w-16 h-2" />
        </div>
      )
    },
  },
  {
    accessorKey: "open_alerts",
    header: "Alerts",
    cell: ({ row }) => {
      const count = row.getValue("open_alerts")
      const criticalCount = row.original.critical_alerts
      return (
        <div className="flex items-center gap-1">
          <Badge variant={criticalCount > 0 ? "destructive" : "secondary"}>
            {count}
          </Badge>
          {criticalCount > 0 && (
            <Badge variant="destructive" className="animate-pulse">
              {criticalCount} 🔴
            </Badge>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "updated_at",
    header: "Updated",
    cell: ({ row }) => {
      const date = row.getValue("updated_at")
      return <span className="text-sm text-muted-foreground">{formatRelative(date)}</span>
    },
  },
  {
    id: "actions",
    cell: ({ row }) => <ProjectRowActions project={row.original} />,
  },
]
```

### 6.4 Vista Alternativa: Cards

```jsx
function ProjectCardView({ projects }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {projects.map(project => (
        <Card key={project.id} className="hover:shadow-lg transition-shadow cursor-pointer"
          onClick={() => router.push(`/projects/${project.id}`)}>
          <CardHeader>
            <div className="flex justify-between items-start">
              <div>
                <CardTitle>{project.name}</CardTitle>
                <CardDescription className="font-mono text-xs mt-1">
                  {project.id}
                </CardDescription>
              </div>
              <Badge variant={statusVariants[project.status]}>
                {project.status.toUpperCase()}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {/* Coherence Score Gauge */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Coherence</span>
                <div className="flex items-center gap-2">
                  <Progress value={project.coherence_score} className="w-24 h-2" />
                  <span className={cn("font-bold", scoreColor(project.coherence_score))}>
                    {project.coherence_score}
                  </span>
                </div>
              </div>

              {/* Alerts Summary */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Alerts</span>
                <div className="flex gap-1">
                  {project.critical_alerts > 0 && (
                    <Badge variant="destructive" className="animate-pulse">
                      {project.critical_alerts} Critical
                    </Badge>
                  )}
                  <Badge variant="secondary">
                    {project.open_alerts} Total
                  </Badge>
                </div>
              </div>

              {/* Updated */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Updated</span>
                <span className="text-sm">{formatRelative(project.updated_at)}</span>
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button variant="ghost" size="sm" onClick={(e) => {
              e.stopPropagation()
              openQuickView(project.id)
            }}>
              Quick View
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                <Button variant="ghost" size="sm">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => router.push(`/projects/${project.id}`)}>
                  View Details
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => router.push(`/projects/${project.id}/evidence`)}>
                  View Evidence
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => archiveProject(project.id)}>
                  Archive
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}
```

### 6.5 Interacciones Críticas

#### 6.5.1 Crear Nuevo Proyecto

```javascript
User clicks "+ New Project"
├─ Dialog modal se abre (tamaño xl)
│  ├─ Título: "Create New Project"
│  ├─ Form (multi-step wizard):
│  │
│  │  ── Step 1: Basic Info ──
│  │  ├─ Input: Project Name* (required, min 3 chars)
│  │  ├─ Textarea: Description
│  │  ├─ Select: Tenant* (si user es super admin)
│  │  ├─ Select: Project Type* (EPC, EPCM, Construction, etc.)
│  │  └─ Buttons: [Next →]
│  │
│  │  ── Step 2: Key Dates ──
│  │  ├─ DatePicker: Start Date*
│  │  ├─ DatePicker: Planned Completion Date*
│  │  ├─ Input: Duration (auto-calculated, editable)
│  │  └─ Buttons: [← Back] [Next →]
│  │
│  │  ── Step 3: Initial Documents (optional) ──
│  │  ├─ Upload: Contract Document
│  │  ├─ Upload: Schedule (MSProject, Excel, etc.)
│  │  ├─ Upload: Budget/BOM
│  │  ├─ Checkbox: "Process documents immediately after creation"
│  │  └─ Buttons: [← Back] [Create Project]
│  │
│  └─ Progress Indicator: Step 1 ● 2 ● 3
│
└─ Al crear:
   ├─ POST /api/projects
   ├─ Si hay documentos y checkbox está marcado:
│  │  └─ POST /api/documents (cada uno)
│  │     └─ Background job para extracción
   ├─ Redirect a /projects/{new_id}
   └─ Toast: "Project created. Processing 3 documents..." (con progress bar)
```

**Validaciones:**
- Nombre único por tenant
- Start date no puede ser en el pasado (warning, no error)
- Completion date > Start date
- Documentos: Max 10MB cada uno, formatos permitidos (PDF, XLSX, MPP, DOCX)

**NO requiere Human-in-the-loop** (creación de proyecto no es acción crítica)

#### 6.5.2 Archivar Proyecto

```javascript
User clicks "Archive" en ProjectRowActions
├─ Dialog de confirmación se abre:
│  ├─ Título: "Archive Project?"
│  ├─ Warning:
│  │  "⚠️ Archiving will:"
│  │  "• Hide the project from default views"
│  │  "• Preserve all data and documents"
│  │  "• Can be undone by restoring the project"
│  ├─ Textarea: "Reason for archiving" (opcional pero recomendado)
│  ├─ Checkbox: "I understand this can be restored later"
│  └─ Botones:
│     ├─ "Cancel"
│     └─ "Archive Project" (variant="destructive", disabled hasta checkbox)
└─ Al confirmar:
   ├─ PATCH /api/projects/{id} { status: "archived", archived_reason: "..." }
   ├─ Proyecto desaparece de la lista (si filtro != "Archived")
   ├─ Toast con Undo option (15s)
   └─ Notificación a todos los stakeholders del proyecto
```

**Human-in-the-loop:**
- Requiere checkbox de confirmación
- No es tan crítico como resolver alertas, pero es irreversible (sin Undo después de 15s)

#### 6.5.3 Quick View (Sheet lateral)

```javascript
User clicks "Quick View" en card o row actions
├─ Sheet lateral se abre (desde la derecha, w-2/5)
│  ├─ Header:
│  │  ├─ Project Name + ID
│  │  ├─ Status badge
│  │  └─ Botón: "Open Full View →" (navega a /projects/{id})
│  ├─ Body (scroll):
│  │  ├─ Section: Coherence Score
│  │  │  └─ Mini gauge chart (tamaño reducido)
│  │  ├─ Section: Top Alerts (max 5)
│  │  │  └─ Lista compacta con badges
│  │  ├─ Section: Recent Activity (max 10)
│  │  │  └─ Timeline items
│  │  ├─ Section: Key Metrics
│  │  │  ├─ Total Documents: 23
│  │  │  ├─ Stakeholders: 12
│  │  │  ├─ WBS Items: 156
│  │  │  └─ Budget Health: 62% (Progress bar)
│  │  └─ Section: Quick Actions
│  │     ├─ Button: "View Evidence"
│  │     ├─ Button: "View Alerts"
│  │     └─ Button: "Export Report"
│  └─ Footer:
│     └─ "Last updated: 2 hours ago"
└─ No cierra automáticamente (user hace click en X o fuera)
```

### 6.6 Filtros y Búsqueda

**Filtros Disponibles:**

1. **Status** (multi-select)
   - Active, On Hold, Completed, Archived

2. **Coherence Range** (slider)
   - 0-100 con range selector
   - Presets: At Risk (<60), Warning (60-79), Healthy (80-100)

3. **Tenant** (select, solo para super admin)
   - Lista de todos los tenants
   - Default: tenant del usuario actual

4. **Sort** (select)
   - Recent (updated_at desc)
   - Name (A-Z)
   - Score (Low to High / High to Low)
   - Alerts (Most to Least)

**Búsqueda Global:**
```javascript
// Busca en: ID, Name, Description
// Debounce: 300ms
// Highlight de términos en resultados

<Input
  type="search"
  placeholder="Search projects..."
  value={searchTerm}
  onChange={(e) => setSearchTerm(e.target.value)}
  className="max-w-sm"
/>
```

### 6.7 Reglas de Diseño

**Score Colors:**
```javascript
function scoreColor(score) {
  if (score >= 80) return "text-green-600"
  if (score >= 60) return "text-amber-600"
  return "text-red-600"
}
```

**Status Badge Variants:**
```javascript
const statusVariants = {
  active: "default",      // Blue
  on_hold: "warning",     // Amber
  completed: "secondary", // Gray
  archived: "outline"     // Gray outline
}
```

**Responsividad:**
- Desktop (>1024px): Tabla completa
- Tablet (768-1023px): Ocultar columnas "Updated", mostrar en tooltip
- Mobile (<768px): Forzar Card View, ocultar Tabla

---

## Design System Guidelines

### Paleta de Colores Semánticos

```javascript
// Tailwind config - colors
const colors = {
  // Neutral (base)
  background: "hsl(0 0% 100%)",       // Blanco
  foreground: "hsl(222.2 84% 4.9%)",  // Negro suave
  muted: "hsl(210 40% 96.1%)",        // Gris claro

  // States
  primary: "hsl(222.2 47.4% 11.2%)",  // Azul oscuro (CTA)
  destructive: "hsl(0 84.2% 60.2%)",  // Rojo (Crítico, Eliminar)
  warning: "hsl(38 92% 50%)",         // Ámbar (Advertencias)
  success: "hsl(142 76% 36%)",        // Verde (Validado, OK)

  // Severity specific
  critical: "hsl(0 84.2% 60.2%)",     // Rojo brillante
  high: "hsl(25 95% 53%)",            // Naranja
  medium: "hsl(48 96% 53%)",          // Amarillo
  low: "hsl(210 40% 96.1%)",          // Gris

  // Borders
  border: "hsl(214.3 31.8% 91.4%)",
  input: "hsl(214.3 31.8% 91.4%)",
  ring: "hsl(222.2 84% 4.9%)",
}
```

### Tipografía

```css
/* Font stack */
font-family: 'Inter Variable', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* Escala de tamaños */
.text-xs:    12px / 16px  (Metadata, timestamps)
.text-sm:    14px / 20px  (Body secundario, labels)
.text-base:  16px / 24px  (Body principal)
.text-lg:    18px / 28px  (Subtítulos)
.text-xl:    20px / 28px  (Títulos de sección)
.text-2xl:   24px / 32px  (Títulos de página)
.text-3xl:   30px / 36px  (Hero numbers, KPIs)
.text-4xl:   36px / 40px  (Dashboard scores)

/* Pesos */
.font-normal:   400 (Body)
.font-medium:   500 (Labels, énfasis)
.font-semibold: 600 (Subtítulos)
.font-bold:     700 (Títulos, KPIs)

/* Monospace para IDs */
.font-mono: 'JetBrains Mono', 'Fira Code', monospace
```

### Espaciado

```javascript
// Sistema de 4px base
const spacing = {
  px: "1px",
  0: "0",
  1: "0.25rem",  // 4px
  2: "0.5rem",   // 8px
  3: "0.75rem",  // 12px
  4: "1rem",     // 16px
  5: "1.25rem",  // 20px
  6: "1.5rem",   // 24px
  8: "2rem",     // 32px
  10: "2.5rem",  // 40px
  12: "3rem",    // 48px
  16: "4rem",    // 64px
  20: "5rem",    // 80px
}

// Aplicación
- Cards: p-6 (24px)
- Sections: space-y-8 (32px entre secciones)
- Form fields: space-y-4 (16px entre inputs)
- Buttons: px-4 py-2 (16px horizontal, 8px vertical)
```

### Componentes Reutilizables

#### Loading States

```jsx
// Skeleton para KPI Card
<Card>
  <CardHeader>
    <Skeleton className="h-4 w-32" />
  </CardHeader>
  <CardContent>
    <Skeleton className="h-16 w-16 rounded-full" />
  </CardContent>
</Card>

// Skeleton para DataTable
<DataTableSkeleton columns={5} rows={10} />
```

#### Empty States

```jsx
<div className="flex flex-col items-center justify-center p-12 text-center">
  <FileQuestion className="h-16 w-16 text-muted-foreground mb-4" />
  <h3 className="text-lg font-semibold mb-2">No alerts found</h3>
  <p className="text-sm text-muted-foreground mb-4">
    Try adjusting your filters or create a new alert.
  </p>
  <Button variant="outline">Clear Filters</Button>
</div>
```

#### Error States

```jsx
<Alert variant="destructive">
  <AlertCircle className="h-4 w-4" />
  <AlertTitle>Error loading data</AlertTitle>
  <AlertDescription>
    Failed to fetch projects.
    <Button variant="link" className="pl-1" onClick={retry}>
      Try again
    </Button>
  </AlertDescription>
</Alert>
```

### Animaciones

```css
/* Transiciones suaves */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
}

/* Animaciones específicas */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes flash-green {
  0%, 100% { background-color: transparent; }
  50% { background-color: hsl(142 76% 90%); }
}

/* Hover effects */
.hover\:shadow-lg:hover {
  box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
  transition: box-shadow 150ms ease-in-out;
}
```

### Accesibilidad (WCAG 2.1 AA)

**Contraste:**
- Text normal: mín 4.5:1
- Text grande (18px+): mín 3:1
- UI elements: mín 3:1

**Keyboard Navigation:**
- Todos los interactivos deben ser accesibles con Tab
- Focus ring visible: `ring-2 ring-offset-2 ring-primary`
- Skip links para navegación rápida

**ARIA Labels:**
```jsx
// Ejemplo: Botón de iconos
<Button variant="ghost" size="icon" aria-label="Close dialog">
  <X className="h-4 w-4" />
</Button>

// Ejemplo: Estado de carga
<div aria-live="polite" aria-busy={isLoading}>
  {isLoading ? <Spinner /> : <DataTable />}
</div>
```

**Screen Reader Friendly:**
- Usar headings jerárquicos (h1 → h2 → h3)
- Describir imágenes/iconos decorativos como `aria-hidden="true"`
- Anunciar cambios dinámicos con `aria-live`

### Responsive Breakpoints

```javascript
const screens = {
  sm: "640px",   // Mobile landscape
  md: "768px",   // Tablet portrait
  lg: "1024px",  // Tablet landscape / Small desktop
  xl: "1280px",  // Desktop
  "2xl": "1536px" // Large desktop
}

// Ejemplo de uso
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
```

---

## Next Steps

### Para Diseñadores (Figma):
1. Usar estas especificaciones para crear mockups high-fidelity
2. Aplicar el Design System (colores, tipografía, espaciado)
3. Exportar assets (iconos, ilustraciones)
4. Documentar interacciones en Figma Prototypes

### Para Desarrolladores:
1. Configurar shadcn/ui en Next.js 14:
   ```bash
   npx shadcn-ui@latest init
   ```
2. Instalar componentes necesarios:
   ```bash
   npx shadcn-ui@latest add card button badge data-table sheet dialog alert
   ```
3. Crear componentes custom (GaugeChart, PDFViewer, StakeholderMatrix, etc.)
4. Implementar rutas según estructura de vistas
5. Conectar con API backend

### Para v0.dev:
1. Copiar las secciones específicas de cada vista
2. Usar como prompt en v0.dev:
   > "Create a Next.js component for [Vista] using shadcn/ui and Tailwind CSS. [Pegar sección de estructura + componentes]"
3. Iterar sobre el código generado

---

## Apéndice: Componentes Custom Requeridos

### 1. GaugeChart
- **Librería:** recharts + custom config
- **Props:** `value`, `max`, `colorThresholds`
- **Ejemplo:**
  ```jsx
  <GaugeChart
    value={78}
    max={100}
    colorThresholds={[
      { value: 60, color: "#ef4444" },
      { value: 80, color: "#f59e0b" },
      { value: 100, color: "#10b981" }
    ]}
  />
  ```

### 2. PDFViewer
- **Librería:** react-pdf
- **Features:** Zoom, rotate, download, highlight layer
- **Props:** `documentUrl`, `highlights`, `onTextSelect`

### 3. HighlightLayer
- **Implementación:** Canvas overlay con coordenadas bbox
- **Props:** `highlights: Array<{bbox, color, opacity}>`

### 4. StakeholderMatrix
- **Implementación:** Grid 2x2 con drag & drop (@dnd-kit/core)
- **Props:** `stakeholders`, `onMove`, `onEdit`

### 5. DataTableFacetedFilter
- **Basado en:** shadcn/ui example (tasks demo)
- **Features:** Multi-select, search, counters

### 6. TimelineItem
- **Implementación:** Custom con vertical line + icons
- **Props:** `events: Array<{timestamp, type, description}>`

---

**Fin del documento CE-S2-010_WIREFRAME_SPECS.md**

---

## Changelog

| Fecha | Autor | Cambios |
|-------|-------|---------|
| 2026-01-16 | Claude Code | Creación inicial - Especificaciones completas de 6 vistas |


---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
