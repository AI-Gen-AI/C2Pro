# 📊 Mockup Review Summary - CE-S2-010

**Fecha:** 2026-01-17
**Mockup:** vision-matched-repo/
**Estado:** ✅ **APROBADO CON RECOMENDACIONES**

---

## 🎯 Resumen Ejecutivo

El mockup de Lovable implementa correctamente las 6 vistas core con alta fidelidad a las especificaciones CE-S2-010. La calidad del código, uso de componentes shadcn/ui y diseño visual son excelentes.

### Puntuación Global: **85/100**

| Vista | Puntuación | Estado | Comentario |
|-------|------------|--------|------------|
| **Dashboard** | 95/100 | ✅ Excelente | Gauge, KPIs, timeline implementados correctamente |
| **Evidence Viewer** | 80/100 | ⚠️ Bueno | Falta PDF viewer real y Dialog de validación |
| **Alerts Center** | 85/100 | ✅ Muy Bueno | Dialog implementado, falta validación por severity |
| **Stakeholder Map** | 90/100 | ✅ Excelente | Matriz Power/Interest completa, falta drag & drop |
| **RACI Matrix** | 90/100 | ✅ Excelente | Tabla editable con gaps detection |
| **Project List** | 88/100 | ✅ Excelente | Table/Card views, filtros funcionando |

---

## ✅ Fortalezas del Mockup

### 1. Arquitectura y Código
```
✅ Estructura de carpetas clara (components/dashboard, layout, pages)
✅ Uso correcto de shadcn/ui components
✅ TypeScript con tipos definidos (types/project.ts)
✅ Responsive design con Tailwind
✅ Mock data bien estructurado (data/mockData.ts)
✅ Hooks custom (use-mobile, use-toast)
```

### 2. Design System
```
✅ Paleta de colores semánticos implementada:
   - Red (critical): hsl(0, 84%, 60%) ✓
   - Amber (warning): hsl(38, 92%, 50%) ✓
   - Green (success): hsl(142, 76%, 36%) ✓

✅ Componentes con estilos consistentes
✅ Animations (pulse-critical, transitions)
✅ Accesibilidad (ARIA labels, keyboard navigation)
```

### 3. Human-in-the-loop (Gate 6)
```
✅ Alerts Center: Dialog con checkbox de confirmación
✅ Alerts Center: Textarea para resolution notes
✅ Alerts Center: Warning específico para Critical alerts
⚠️ Evidence Viewer: Botones Approve/Reject sin Dialog (pendiente)
⚠️ Falta validación dinámica según severity
```

### 4. Componentes Destacados

#### Dashboard - GaugeChart
```tsx
// vision-matched-repo/src/components/dashboard/GaugeChart.tsx:24-28
const getColor = (score: number) => {
  if (score >= 80) return 'hsl(142, 76%, 36%)'; // ✓ Coincide con specs
  if (score >= 60) return 'hsl(38, 92%, 50%)';  // ✓
  return 'hsl(0, 84%, 60%)';                     // ✓
};
```

#### Evidence Viewer - ResizablePanel
```tsx
// vision-matched-repo/src/pages/EvidenceViewer.tsx:145-180
<ResizablePanelGroup direction="horizontal">
  <ResizablePanel defaultSize={40} minSize={30}>
    {/* PDF Viewer */}
  </ResizablePanel>
  <ResizableHandle withHandle />
  <ResizablePanel defaultSize={60} minSize={40}>
    {/* Data Panel con Tabs */}
  </ResizablePanel>
</ResizablePanelGroup>
```
✅ Implementación perfecta según specs (40/60 split)

#### RACI Matrix - Editable Cells
```tsx
// vision-matched-repo/src/pages/RACIMatrix.tsx:169-206
function RACICell({ wbsId, stakeholderId, value, onUpdate }) {
  return (
    <Popover>
      <PopoverTrigger>
        <button className={cn(raciColors[value])}>
          {value}
        </button>
      </PopoverTrigger>
      <PopoverContent>
        {/* Grid de opciones R, A, C, I, - */}
      </PopoverContent>
    </Popover>
  );
}
```
✅ Interacción excelente con Popover para edición

#### Stakeholder Map - Power/Interest Matrix
```tsx
// vision-matched-repo/src/pages/StakeholderMap.tsx:151-154
const manageClosely = mockStakeholders.filter((s) => s.power >= 6 && s.interest >= 6);
const keepSatisfied = mockStakeholders.filter((s) => s.power >= 6 && s.interest < 6);
const keepInformed = mockStakeholders.filter((s) => s.power < 6 && s.interest >= 6);
const monitor = mockStakeholders.filter((s) => s.power < 6 && s.interest < 6);
```
✅ Lógica correcta, gradientes aplicados a cuadrantes

---

## ⚠️ Áreas de Mejora Prioritarias

### 1. Evidence Viewer - Human-in-the-loop (CRÍTICO)

**Problema:** Botones Approve/Reject no abren Dialog de confirmación

**Ubicación:** `vision-matched-repo/src/pages/EvidenceViewer.tsx:269-277`

**Solución:**

```tsx
// Agregar estado
const [approveDialogOpen, setApproveDialogOpen] = useState(false);
const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
const [confirmChecked, setConfirmChecked] = useState(false);
const [validationNotes, setValidationNotes] = useState('');

// Modificar botón Approve
<Button size="sm" onClick={() => {
  setSelectedEntity(entity);
  setApproveDialogOpen(true);
}}>
  <CheckCircle className="h-3 w-3" />
  Approve
</Button>

// Agregar Dialog
<Dialog open={approveDialogOpen} onOpenChange={setApproveDialogOpen}>
  <DialogContent className="sm:max-w-2xl">
    <DialogHeader>
      <DialogTitle>Confirm Extracted Data</DialogTitle>
    </DialogHeader>

    <div className="space-y-4">
      {/* Mostrar texto original vs extraído lado a lado */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label className="text-sm font-medium">Original (PDF)</Label>
          <div className="rounded border p-3 bg-muted text-sm">
            {selectedEntity?.originalText}
          </div>
        </div>
        <div>
          <Label className="text-sm font-medium">Extracted</Label>
          <Textarea
            value={extractedText}
            onChange={(e) => setExtractedText(e.target.value)}
            rows={4}
          />
        </div>
      </div>

      {/* Alert si confidence < 90% */}
      {selectedEntity?.confidence < 90 && (
        <Alert variant="warning">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Low confidence extraction ({selectedEntity.confidence}%).
            Please verify accuracy before approving.
          </AlertDescription>
        </Alert>
      )}

      {/* Checkbox obligatorio si confidence < 90% */}
      {selectedEntity?.confidence < 90 && (
        <div className="flex items-start gap-2">
          <Checkbox
            id="confirm-extraction"
            checked={confirmChecked}
            onCheckedChange={(checked) => setConfirmChecked(!!checked)}
          />
          <Label htmlFor="confirm-extraction" className="text-sm leading-snug">
            I confirm this data is accurate and have reviewed the evidence
          </Label>
        </div>
      )}

      {/* Notas obligatorias si editó texto */}
      {extractedText !== selectedEntity?.text && (
        <div className="space-y-2">
          <Label>Validation Notes* (required when editing)</Label>
          <Textarea
            placeholder="Explain why you modified the extracted text..."
            value={validationNotes}
            onChange={(e) => setValidationNotes(e.target.value)}
            rows={2}
          />
        </div>
      )}
    </div>

    <DialogFooter>
      <Button variant="outline" onClick={() => setApproveDialogOpen(false)}>
        Cancel
      </Button>
      <Button
        onClick={handleConfirmApproval}
        disabled={
          (selectedEntity?.confidence < 90 && !confirmChecked) ||
          (extractedText !== selectedEntity?.text && validationNotes.length < 10)
        }
      >
        Approve & Save
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

**Regla Gate 6:**
> Entidades con `confidence < 90%` DEBEN requerir checkbox de confirmación

---

### 2. Alerts Center - Validación por Severity (IMPORTANTE)

**Problema:** Dialog de resolución es genérico, no valida según severity

**Ubicación:** `vision-matched-repo/src/pages/AlertsCenter.tsx:315-389`

**Solución:**

```tsx
// Agregar funciones de validación
const getMinNotesLength = (severity: Severity): number => {
  switch (severity) {
    case 'critical': return 50;
    case 'high': return 20;
    case 'medium': return 10;
    case 'low': return 0;
  }
};

const requiresCheckbox = (severity: Severity): boolean => {
  return severity === 'critical' || severity === 'high';
};

const requiresRootCause = (severity: Severity): boolean => {
  return severity === 'critical' || severity === 'high';
};

// Agregar estado para root cause
const [rootCause, setRootCause] = useState('');

// Modificar Dialog content
<DialogContent className="sm:max-w-lg">
  <DialogHeader>
    <DialogTitle className="flex items-center gap-2">
      <AlertTriangle className="h-5 w-5 text-amber-500" />
      Resolve Alert
    </DialogTitle>
    {selectedAlert?.severity === 'critical' && (
      <Alert variant="destructive" className="mt-2">
        <AlertDescription>
          ⚠️ Critical alert requires detailed resolution notes (minimum 50 characters)
        </AlertDescription>
      </Alert>
    )}
  </DialogHeader>

  <div className="space-y-4">
    {/* Resolution Notes con validación dinámica */}
    <div className="space-y-2">
      <Label>
        Resolution Notes
        {getMinNotesLength(selectedAlert.severity) > 0 && (
          <span className="text-destructive">
            * (min {getMinNotesLength(selectedAlert.severity)} chars)
          </span>
        )}
      </Label>
      <Textarea
        value={resolutionNotes}
        onChange={(e) => setResolutionNotes(e.target.value)}
        rows={selectedAlert.severity === 'critical' ? 5 : 3}
        placeholder={
          selectedAlert.severity === 'critical'
            ? "Provide detailed resolution notes..."
            : "Describe the resolution..."
        }
      />
      {resolutionNotes.length > 0 && getMinNotesLength(selectedAlert.severity) > 0 && (
        <p className={cn(
          "text-xs",
          resolutionNotes.length >= getMinNotesLength(selectedAlert.severity)
            ? "text-emerald-600"
            : "text-destructive"
        )}>
          {resolutionNotes.length} / {getMinNotesLength(selectedAlert.severity)} characters
        </p>
      )}
    </div>

    {/* Root Cause (solo Critical/High) */}
    {requiresRootCause(selectedAlert.severity) && (
      <div className="space-y-2">
        <Label>Root Cause*</Label>
        <Select value={rootCause} onValueChange={setRootCause}>
          <SelectTrigger>
            <SelectValue placeholder="Select root cause category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="schedule_delay">Schedule Delay</SelectItem>
            <SelectItem value="resource_constraint">Resource Constraint</SelectItem>
            <SelectItem value="scope_change">Scope Change</SelectItem>
            <SelectItem value="external_dependency">External Dependency</SelectItem>
            <SelectItem value="technical_issue">Technical Issue</SelectItem>
            <SelectItem value="budget_overrun">Budget Overrun</SelectItem>
            <SelectItem value="quality_issue">Quality Issue</SelectItem>
            <SelectItem value="other">Other</SelectItem>
          </SelectContent>
        </Select>
      </div>
    )}

    {/* Checkbox (solo Critical/High) */}
    {requiresCheckbox(selectedAlert.severity) && (
      <div className="flex items-start gap-2">
        <Checkbox
          id="confirm"
          checked={confirmChecked}
          onCheckedChange={(checked) => setConfirmChecked(!!checked)}
        />
        <Label htmlFor="confirm" className="text-sm leading-snug">
          I have reviewed the evidence and confirm this alert can be resolved.
        </Label>
      </div>
    )}
  </div>

  <DialogFooter>
    <Button variant="outline" onClick={() => setResolveDialogOpen(false)}>
      Cancel
    </Button>
    <Button
      onClick={handleConfirmResolution}
      disabled={
        resolutionNotes.length < getMinNotesLength(selectedAlert.severity) ||
        (requiresCheckbox(selectedAlert.severity) && !confirmChecked) ||
        (requiresRootCause(selectedAlert.severity) && !rootCause)
      }
    >
      Confirm Resolution
    </Button>
  </DialogFooter>
</DialogContent>
```

**Tabla de Validación:**

| Severity | Min Notes | Checkbox | Root Cause |
|----------|-----------|----------|------------|
| Critical | 50 chars  | ✅ Required | ✅ Required |
| High     | 20 chars  | ✅ Required | ✅ Required |
| Medium   | 10 chars  | ❌ Optional | ❌ Optional |
| Low      | 0 chars   | ❌ Optional | ❌ Optional |

---

### 3. Evidence Viewer - PDF Viewer Real (IMPORTANTE)

**Problema:** Actualmente muestra texto simulado, no un PDF real

**Ubicación:** `vision-matched-repo/src/pages/EvidenceViewer.tsx:160-178`

**Solución:**

```bash
npm install react-pdf pdfjs-dist
```

```tsx
// Agregar imports
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';

// Configurar worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

// Estado
const [numPages, setNumPages] = useState<number>(0);
const [pageNumber, setPageNumber] = useState<number>(12);
const [scale, setScale] = useState<number>(1.0);

// Reemplazar el div simulado por:
<div className="flex-1 overflow-auto p-4 bg-muted/30">
  <Document
    file="/sample-contract.pdf"
    onLoadSuccess={({ numPages }) => setNumPages(numPages)}
    className="mx-auto"
  >
    <Page
      pageNumber={pageNumber}
      scale={scale}
      renderTextLayer={true}
      renderAnnotationLayer={true}
    />
  </Document>

  {/* Page controls */}
  <div className="flex items-center justify-center gap-4 mt-4">
    <Button
      variant="outline"
      size="sm"
      onClick={() => setPageNumber(p => Math.max(1, p - 1))}
      disabled={pageNumber <= 1}
    >
      Previous
    </Button>
    <span className="text-sm">
      Page {pageNumber} of {numPages}
    </span>
    <Button
      variant="outline"
      size="sm"
      onClick={() => setPageNumber(p => Math.min(numPages, p + 1))}
      disabled={pageNumber >= numPages}
    >
      Next
    </Button>
  </div>
</div>

// Conectar zoom buttons
<Button
  variant="ghost"
  size="icon"
  onClick={() => setScale(s => Math.max(0.5, s - 0.1))}
>
  <ZoomOut className="h-4 w-4" />
</Button>
<span className="text-sm">{Math.round(scale * 100)}%</span>
<Button
  variant="ghost"
  size="icon"
  onClick={() => setScale(s => Math.min(2.0, s + 0.1))}
>
  <ZoomIn className="h-4 w-4" />
</Button>
```

---

### 4. Stakeholder Map - Drag & Drop (OPCIONAL)

**Problema:** Los avatares no se pueden arrastrar entre cuadrantes

**Prioridad:** Media (nice-to-have para MVP)

**Solución (si se decide implementar):**

```bash
npm install @dnd-kit/core @dnd-kit/sortable
```

```tsx
import { DndContext, DragEndEvent } from '@dnd-kit/core';
import { useDraggable, useDroppable } from '@dnd-kit/core';

// Wrapper para avatar draggable
function DraggableAvatar({ stakeholder }: { stakeholder: Stakeholder }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: stakeholder.id,
  });

  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
  } : undefined;

  return (
    <div ref={setNodeRef} style={style} {...listeners} {...attributes}>
      <StakeholderAvatar stakeholder={stakeholder} />
    </div>
  );
}

// Wrapper para cuadrante droppable
function DroppableQuadrant({ id, children }: { id: string; children: React.ReactNode }) {
  const { setNodeRef } = useDroppable({ id });

  return <div ref={setNodeRef}>{children}</div>;
}

// Manejar drop
const handleDragEnd = (event: DragEndEvent) => {
  const { active, over } = event;

  if (over) {
    // Confirmar movimiento
    setMoveDialogOpen(true);
    setMovingStakeholder(active.id);
    setTargetQuadrant(over.id);
  }
};

<DndContext onDragEnd={handleDragEnd}>
  <DroppableQuadrant id="manage-closely">
    {manageClosely.map(s => (
      <DraggableAvatar key={s.id} stakeholder={s} />
    ))}
  </DroppableQuadrant>
  {/* ... otros cuadrantes */}
</DndContext>
```

**Nota:** Para MVP, puede dejarse sin drag & drop. Los usuarios pueden editar usando el Sheet de "Edit" en el Popover.

---

## 🔧 Mejoras Menores

### 5. Componentes Faltantes

#### Dashboard - Coherence Score Drill-down

```tsx
// Agregar Sheet en Dashboard.tsx
const [scoreSheetOpen, setScoreSheetOpen] = useState(false);

<div onClick={() => setScoreSheetOpen(true)} className="cursor-pointer">
  <GaugeChart value={mockKPIData.coherence_score} trend={mockKPIData.coherenceTrend} />
</div>

<Sheet open={scoreSheetOpen} onOpenChange={setScoreSheetOpen}>
  <SheetContent className="w-2/5">
    <SheetHeader>
      <SheetTitle>Coherence Score Breakdown</SheetTitle>
    </SheetHeader>
    <div className="mt-6 space-y-4">
      {/* Breakdown por dimensión */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm">Legal Compliance</span>
          <span className="font-semibold">85</span>
        </div>
        <Progress value={85} />
      </div>
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm">Financial Alignment</span>
          <span className="font-semibold">72</span>
        </div>
        <Progress value={72} />
      </div>
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm">Schedule Coherence</span>
          <span className="font-semibold">65</span>
        </div>
        <Progress value={65} />
      </div>
      {/* ... */}
    </div>
  </SheetContent>
</Sheet>
```

#### Alerts Center - Sheet Lateral para Detalles

```tsx
// Modificar el botón Eye
<Button
  variant="ghost"
  size="icon"
  onClick={() => openAlertDetails(alert)}
>
  <Eye className="h-4 w-4" />
</Button>

<Sheet open={detailsSheetOpen} onOpenChange={setDetailsSheetOpen}>
  <SheetContent className="w-2/5">
    {/* Ver solución completa en sección anterior */}
  </SheetContent>
</Sheet>
```

#### Project List - Quick View Sheet

```tsx
// Modificar botón "Quick View" en Card
<Button
  variant="ghost"
  size="sm"
  onClick={(e) => {
    e.stopPropagation();
    openQuickView(project.id);
  }}
>
  Quick View
</Button>

<Sheet open={quickViewOpen} onOpenChange={setQuickViewOpen}>
  <SheetContent className="w-2/5">
    <SheetHeader>
      <SheetTitle>{selectedProject?.name}</SheetTitle>
      <SheetDescription className="font-mono text-xs">
        {selectedProject?.id}
      </SheetDescription>
    </SheetHeader>
    <div className="mt-6 space-y-6">
      {/* Mini Gauge */}
      <GaugeChart value={selectedProject?.coherence_score} size="sm" />

      {/* Top Alerts */}
      <div>
        <h3 className="font-semibold mb-2">Top Alerts</h3>
        {/* Lista compacta */}
      </div>

      {/* Quick Actions */}
      <div className="flex flex-col gap-2">
        <Button variant="outline" asChild>
          <Link to={`/projects/${selectedProject?.id}`}>
            Open Full View →
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to={`/evidence?project=${selectedProject?.id}`}>
            View Evidence
          </Link>
        </Button>
      </div>
    </div>
  </SheetContent>
</Sheet>
```

---

## 📝 Checklist de Implementación

### Prioridad Alta (Crítico para MVP)

- [ ] **Evidence Viewer:** Implementar Dialog de confirmación para Approve/Reject
- [ ] **Evidence Viewer:** Agregar validación obligatoria para confidence < 90%
- [ ] **Alerts Center:** Agregar validación dinámica según severity
- [ ] **Alerts Center:** Implementar campo Root Cause para Critical/High
- [ ] **Evidence Viewer:** Integrar react-pdf para visor real

### Prioridad Media (Importante)

- [ ] **Dashboard:** Implementar Sheet de drill-down para Coherence Score
- [ ] **Alerts Center:** Agregar Sheet lateral para detalles de alerta
- [ ] **Alerts Center:** Implementar bulk actions con validación
- [ ] **Project List:** Agregar Quick View Sheet
- [ ] **Evidence Viewer:** Implementar highlight sync PDF ↔ Data Panel

### Prioridad Baja (Nice-to-have)

- [ ] **Stakeholder Map:** Implementar drag & drop con @dnd-kit
- [ ] **RACI Matrix:** Implementar Auto-Assign AI Dialog
- [ ] **Project List:** Implementar Dialog de creación de proyecto (wizard)
- [ ] **Todas las vistas:** Conectar con API backend real

---

## 🚀 Próximos Pasos

### 1. Implementar Mejoras Críticas

Enfocarse en las áreas de Prioridad Alta listadas arriba. Estas son **bloqueantes para cumplir Gate 6**.

### 2. Testing

```bash
# Agregar tests para validaciones
npm install @testing-library/react @testing-library/user-event vitest

# Crear tests para:
# - Evidence Viewer approval flow
# - Alerts Center resolution validation
# - RACI Matrix gap detection
```

### 3. Integración con Backend

```bash
# Reemplazar mockData con API calls
# Ubicación: vision-matched-repo/src/data/mockData.ts

# Crear service layer:
# - src/services/api.ts
# - src/services/projects.ts
# - src/services/alerts.ts
# - src/services/documents.ts
```

Ejemplo:

```tsx
// src/services/alerts.ts
export async function resolveAlert(
  alertId: string,
  resolution: {
    notes: string;
    rootCause?: string;
    validated: boolean;
  }
) {
  const response = await fetch(`/api/alerts/${alertId}/resolve`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(resolution),
  });

  if (!response.ok) throw new Error('Failed to resolve alert');

  return response.json();
}
```

### 4. Deployment

```bash
# Build del mockup
cd vision-matched-repo
npm run build

# Deploy a Vercel/Netlify para demo
vercel --prod
```

### 5. Migración al Proyecto Principal

Una vez validado el mockup con stakeholders:

```bash
# Copiar componentes aprobados a apps/web
cp -r vision-matched-repo/src/components/* apps/web/components/
cp -r vision-matched-repo/src/pages/* apps/web/app/(dashboard)/

# Adaptar rutas Next.js
# Lovable usa react-router, C2Pro usa Next.js App Router
```

---

## 📊 Comparación: Mockup vs Specs

| Feature | Especificado | Implementado | Match |
|---------|--------------|--------------|-------|
| **Dashboard** |
| Gauge Chart 0-100 | ✅ | ✅ | 100% |
| Colores dinámicos (R/A/G) | ✅ | ✅ | 100% |
| KPI Cards grid | ✅ | ✅ | 100% |
| Activity Timeline | ✅ | ✅ | 100% |
| Top Alerts + Projects | ✅ | ✅ | 100% |
| **Evidence Viewer** |
| ResizablePanel 40/60 | ✅ | ✅ | 100% |
| PDF Viewer | ✅ | ⚠️ Simulado | 50% |
| Tabs (Data/Alerts/Linkages) | ✅ | ✅ | 100% |
| Entity Cards con confidence | ✅ | ✅ | 100% |
| Approve/Reject con Dialog | ✅ | ❌ | 0% |
| Highlight sync | ✅ | ❌ | 0% |
| **Alerts Center** |
| DataTable con filtros | ✅ | ✅ | 100% |
| Severity badges animados | ✅ | ✅ | 100% |
| Resolve Dialog básico | ✅ | ✅ | 100% |
| Validación por severity | ✅ | ⚠️ Parcial | 40% |
| Bulk actions | ✅ | ⚠️ UI only | 30% |
| Sheet lateral detalles | ✅ | ❌ | 0% |
| **Stakeholder Map** |
| Matriz Power/Interest 2x2 | ✅ | ✅ | 100% |
| Avatar con Popover | ✅ | ✅ | 100% |
| Add Stakeholder Sheet | ✅ | ✅ | 100% |
| Vista alternativa List | ✅ | ✅ | 100% |
| Drag & drop | ✅ | ❌ | 0% |
| **RACI Matrix** |
| Tabla editable | ✅ | ✅ | 100% |
| RACI Cell Popover | ✅ | ✅ | 100% |
| Gaps detection | ✅ | ✅ | 100% |
| Validation Summary | ✅ | ✅ | 100% |
| Row detail Sheet | ✅ | ✅ | 100% |
| Auto-Assign AI Dialog | ✅ | ⚠️ Button only | 20% |
| **Project List** |
| Table/Card views | ✅ | ✅ | 100% |
| Filtros y search | ✅ | ✅ | 100% |
| Score con Progress bar | ✅ | ✅ | 100% |
| Critical alerts badge | ✅ | ✅ | 100% |
| Quick View Sheet | ✅ | ❌ | 0% |
| Create Project wizard | ✅ | ⚠️ Button only | 20% |

---

## 🎓 Recomendaciones de Arquitectura

### 1. Estado Global

Considerar';

interface ProjectStore {
  currentProject: Project | null;
  setCurrentProject: (project: Project) => void;
  alerts: Alert[];
  setAlerts: (alerts: Alert[]) => void;
}

export const useProjectStore = create<ProjectStore>((set) => ({
  currentProject: null,
  setCurrentProject: (project) => set({ currentProject: project }),
  alerts: [],
  setAlerts: (alerts) => set({ alerts }),
}));
```

### 2. API Client

Usar TanStack Query (react-query) para data fetching:

```bash
npm install @tanstack/react-query
```

```tsx
// src/hooks/useAlerts.ts
import { useQuery, useMutation } from '@tanstack/react-query';

export function useAlerts(projectId: string) {
  return useQuery({
    queryKey: ['alerts', projectId],
    queryFn: () => fetch(`/api/projects/${projectId}/alerts`).then(r => r.json()),
  });
}

export function useResolveAlert() {
  return useMutation({
    mutationFn: (params: { alertId: string; resolution: Resolution }) =>
      fetch(`/api/alerts/${params.alertId}/resolve`, {
        method: 'PATCH',
        body: JSON.stringify(params.resolution),
      }),
  });
}
```

### 3. Form Validation

Usar react-hook-form + zod:

```bash
npm install react-hook-form zod @hookform/resolvers
```

```tsx
// En Alerts Center Dialog
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const resolutionSchema = z.object({
  notes: z.string().min(20, 'Minimum 20 characters for High severity'),
  rootCause: z.string().min(1, 'Root cause is required'),
  validated: z.boolean().refine(val => val === true, 'Must confirm'),
});

const form = useForm({
  resolver: zodResolver(resolutionSchema),
});
```

---

## ✅ Conclusión

El mockup de Lovable es **excelente** y está listo para ser usado como base de la implementación final. Las áreas de mejora identificadas son implementables en 2-3 días de desarrollo.

**Recomendación:** Aprobar el mockup y proceder con:

1. Implementar mejoras críticas (Prioridad Alta)
2. Integrar con backend API
3. Testing E2E
4. Migrar a `apps/web` del monorepo principal

**Estimación de esfuerzo:**

- Mejoras Prioridad Alta: **2 días**
- Mejoras Prioridad Media: **3 días**
- Integración con backend: **5 días**
- Testing: **2 días**

**Total: ~12 días** para tener el frontend completamente funcional y conectado.

---

**Prepared by:** Claude Code
**Date:** 2026-01-17
**Version:** 1.0

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
