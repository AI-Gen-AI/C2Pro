# CE-S2-010: Mockup Review & Analysis

**Fecha:** 2026-01-17
**Mockup URL:** https://vision-matched-repo.lovable.app/
**Stack:** Vite + React + TypeScript + Tailwind + shadcn/ui

---

## 📊 Resumen Ejecutivo

| Criterio | Cumplimiento | Notas |
|----------|--------------|-------|
| **Estructura General** | ✅ 95% | Layout, sidebar, header correctos |
| **Componentes UI** | ✅ 100% | shadcn/ui implementado completamente |
| **Design System** | ✅ 90% | Colores, tipografía, espaciado coherentes |
| **Human-in-the-loop** | ⚠️ 70% | Implementado parcialmente, falta validación completa |
| **Funcionalidad** | ⚠️ 60% | Mock data, falta integración con API |

**Estado:** ✅ **APROBADO para continuar con implementación**
**Recomendación:** Implementar mejoras listadas en Sección 3 antes de producción

---

## 1. Análisis por Vista

### 1.1 Dashboard ✅ **Excelente**

**Archivo:** `src/pages/Dashboard.tsx`

#### ✅ Cumple Especificaciones

- **Layout:** Grid responsivo con Gauge + KPIs ✓
- **GaugeChart:**
  - Semi-circular con recharts ✓
  - Colores dinámicos (verde/ámbar/rojo) ✓
  - Trend indicator (+2 vs last week) ✓
  - Implementación: `vision-matched-repo/src/components/dashboard/GaugeChart.tsx:24-28`

- **KPI Cards:**
  - Grid de 4 cards ✓
  - Active Projects con badge "3 at risk" ✓
  - Open Alerts con breakdown críticos ✓
  - Budget Health con Progress bar ✓
  - Colores según estado ✓
  - Implementación: `vision-matched-repo/src/components/dashboard/KPICards.tsx:84-115`

- **Activity Timeline:** ✓
- **Top Alerts Card:** ✓
- **Recent Projects Card:** ✓

#### 🎨 Diseño

```tsx
// Colores del GaugeChart - Coincide 100% con specs
const getColor = (score: number) => {
  if (score >= 80) return 'hsl(142, 76%, 36%)'; // Green ✓
  if (score >= 60) return 'hsl(38, 92%, 50%)';  // Amber ✓
  return 'hsl(0, 84%, 60%)';                     // Red ✓
};
```

**Puntuación:** 95/100

#### 💡 Recomendaciones

1. **Coherence Score Drill-down:** Implementar Sheet lateral al click en el Gauge
   ```tsx
   // Agregar en GaugeChart.tsx
   <div onClick={() => setSheetOpen(true)} className="cursor-pointer">
     {/* Gauge content */}
   </div>
   <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
     <SheetContent>
       {/* Breakdown por dimensión */}
     </SheetContent>
   </Sheet>
   ```

2. **Critical Alert Animation:** El badge debería tener `animate-pulse`
   ```tsx
   // En TopAlertsCard.tsx
   <Badge variant="destructive" className="animate-pulse">
     {criticalCount} Critical
   </Badge>
   ```

---

### 1.2 Evidence Viewer ✅ **Muy Bueno**

**Archivo:** `src/pages/EvidenceViewer.tsx`

#### ✅ Cumple Especificaciones

- **Split View:** ResizablePanel 40/60 ✓
  - Implementación: `vision-matched-repo/src/pages/EvidenceViewer.tsx:145-180`
- **Toolbar:** Zoom, Rotate, Download ✓
- **Filtros:** Document selector, Alert filter ✓
- **Tabs:** Extracted Data, Alerts, Linkages ✓
- **Entity Cards:**
  - Border izquierdo según confidence ✓
  - Confidence badge ✓
  - Validated state con CheckCircle ✓
  - Linked WBS/Alerts badges ✓

#### ⚠️ Áreas de Mejora

**1. PDF Viewer Real**

Actualmente es texto simulado. Necesita:

```bash
npm install react-pdf pdfjs-dist
```

```tsx
// Reemplazar en EvidenceViewer.tsx línea 160-178
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

<Document file="/sample-contract.pdf">
  <Page pageNumber={pageNumber} />
</Document>
```

**2. Human-in-the-loop - Approve/Reject**

Actualmente solo tiene botones simples. Falta Dialog de confirmación:

```tsx
// Implementar en línea 269-277
{!entity.validated && (
  <div className="flex gap-2 pt-2">
    <Button size="sm" onClick={() => handleApprove(entity)}>
      <CheckCircle className="h-3 w-3" />
      Approve
    </Button>
    <Button size="sm" variant="outline" onClick={() => handleReject(entity)}>
      <XCircle className="h-3 w-3" />
      Reject
    </Button>
  </div>
)}

// Agregar Dialog
<Dialog open={approveDialogOpen} onOpenChange={setApproveDialogOpen}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Confirm Extracted Data</DialogTitle>
    </DialogHeader>
    <div className="space-y-4">
      {/* Muestra texto original vs extraído lado a lado */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-medium">Original Text (PDF)</label>
          <div className="rounded border p-3 bg-muted text-sm">
            {selectedEntity?.originalText}
          </div>
        </div>
        <div>
          <label className="text-sm font-medium">Extracted Text</label>
          <Textarea
            value={extractedText}
            onChange={(e) => setExtractedText(e.target.value)}
            rows={4}
          />
        </div>
      </div>

      {/* Checkbox obligatorio si confidence < 90% */}
      {selectedEntity?.confidence < 90 && (
        <div className="flex items-start gap-2">
          <Checkbox
            id="confirm-extraction"
            checked={confirmChecked}
            onCheckedChange={(checked) => setConfirmChecked(!!checked)}
          />
          <label htmlFor="confirm-extraction" className="text-sm">
            I confirm this data is accurate and have reviewed the evidence
          </label>
        </div>
      )}

      {/* Notas opcionales si editó */}
      {extractedText !== selectedEntity?.text && (
        <div>
          <label className="text-sm font-medium">Validation Notes*</label>
          <Textarea
            placeholder="Explain why you modified the extracted text..."
            value={validationNotes}
            onChange={(e) => setValidationNotes(e.target.value)}
            required
          />
        </div>
      )}
    </div>
    <DialogFooter>
      <Button variant="outline" onClick={() => setApproveDialogOpen(false)}>
        Cancel
      </Button>
      <Button
        onClick={confirmApproval}
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

**Regla Crítica (Gate 6):**
> Entidades con `confidence < 90%` DEBEN requerir checkbox de confirmación antes de aprobar.

**3. Highlight Sync**

Implementar navegación bidireccional PDF ↔ Data Panel:

```tsx
// Agregar Context
const [activeHighlight, setActiveHighlight] = useState<string | null>(null);

// En PDF viewer
<span
  onClick={() => {
    setActiveHighlight(entity.id);
    // Scroll right panel to entity card
    document.getElementById(`entity-${entity.id}`)?.scrollIntoView();
  }}
  className="bg-yellow-200 cursor-pointer hover:bg-yellow-300"
>
  {highlightedText}
</span>

// En Entity Card
<Card
  id={`entity-${entity.id}`}
  className={cn(
    'border-l-4',
    activeHighlight === entity.id && 'ring-2 ring-primary animate-pulse-once'
  )}
>
```

**Puntuación:** 80/100

---

### 1.3 Alerts Center ✅ **Muy Bueno**

**Archivo:** `src/pages/AlertsCenter.tsx`

#### ✅ Cumple Especificaciones

- **Filtros:** Severity, Status, Search ✓
  - Implementación: `vision-matched-repo/src/pages/AlertsCenter.tsx:137-197`
- **DataTable:** Con columnas ID, Severity, Type, Project, Status ✓
- **Severity Badges:** Con dots de colores y animation-pulse para critical ✓
  ```tsx
  // vision-matched-repo/src/pages/AlertsCenter.tsx:40-61
  critical: {
    label: 'Critical',
    className: 'severity-critical',
    dotClass: 'bg-red-500 animate-pulse-critical', // ✓
  }
  ```
- **Bulk Selection:** Checkbox para select all ✓
- **Resolve Dialog:** ✅ **IMPLEMENTADO**
  - Checkbox de confirmación ✓
  - Textarea para resolution notes ✓
  - Warning para Critical alerts ✓
  - Implementación: `vision-matched-repo/src/pages/AlertsCenter.tsx:315-389`

#### ⚠️ Mejoras Necesarias

**1. Validación según Severity**

Actualmente el Dialog es genérico. Debe validar según tabla:

```tsx
// Modificar en AlertsCenter.tsx línea 315-389
const getMinNotesLength = (severity: Severity) => {
  switch (severity) {
    case 'critical': return 50;
    case 'high': return 20;
    case 'medium': return 10;
    case 'low': return 0;
  }
};

const requiresCheckbox = (severity: Severity) => {
  return severity === 'critical' || severity === 'high';
};

const requiresRootCause = (severity: Severity) => {
  return severity === 'critical' || severity === 'high';
};

// En el Dialog
<DialogContent>
  {/* ... */}

  {/* Resolution Notes con validación dinámica */}
  <div className="space-y-2">
    <label className="text-sm font-medium">
      Resolution Notes
      {getMinNotesLength(selectedAlert.severity) > 0 && (
        <span className="text-destructive">* (min {getMinNotesLength(selectedAlert.severity)} chars)</span>
      )}
    </label>
    <Textarea
      value={resolutionNotes}
      onChange={(e) => setResolutionNotes(e.target.value)}
      rows={selectedAlert.severity === 'critical' ? 5 : 3}
      placeholder={
        selectedAlert.severity === 'critical'
          ? "Provide detailed resolution notes (minimum 50 characters)..."
          : "Describe the resolution or actions taken..."
      }
    />
    {resolutionNotes.length > 0 && (
      <p className="text-xs text-muted-foreground">
        {resolutionNotes.length} / {getMinNotesLength(selectedAlert.severity)} characters
      </p>
    )}
  </div>

  {/* Root Cause (solo Critical/High) */}
  {requiresRootCause(selectedAlert.severity) && (
    <div className="space-y-2">
      <label className="text-sm font-medium">Root Cause*</label>
      <Select value={rootCause} onValueChange={setRootCause}>
        <SelectTrigger>
          <SelectValue placeholder="Select root cause" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="schedule_delay">Schedule Delay</SelectItem>
          <SelectItem value="resource_constraint">Resource Constraint</SelectItem>
          <SelectItem value="scope_change">Scope Change</SelectItem>
          <SelectItem value="external_dependency">External Dependency</SelectItem>
          <SelectItem value="technical_issue">Technical Issue</SelectItem>
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
      <label htmlFor="confirm" className="text-sm leading-snug">
        I have reviewed the evidence and confirm this alert can be resolved.
      </label>
    </div>
  )}

  {/* ... */}

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

**2. Bulk Actions con Validación**

Actualmente los botones "Bulk Assign" y "Change Status" están presentes pero sin funcionalidad. Implementar:

```tsx
// Agregar Dialog de bulk resolve
const handleBulkResolve = () => {
  const selectedAlertObjects = mockAlerts.filter(a => selectedAlerts.includes(a.id));
  const criticalCount = selectedAlertObjects.filter(a => a.severity === 'critical').length;
  const highCount = selectedAlertObjects.filter(a => a.severity === 'high').length;

  if (criticalCount > 0 || highCount > 0) {
    // Mostrar warning
    setBulkResolveWarning(
      `⚠️ ${criticalCount} Critical and ${highCount} High alerts require individual review.`
    );
  }

  setBulkResolveDialogOpen(true);
};

<Dialog open={bulkResolveDialogOpen} onOpenChange={setBulkResolveDialogOpen}>
  <DialogContent className="sm:max-w-2xl">
    <DialogHeader>
      <DialogTitle>Bulk Resolve Alerts</DialogTitle>
    </DialogHeader>

    {bulkResolveWarning && (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{bulkResolveWarning}</AlertDescription>
      </Alert>
    )}

    <div className="space-y-2">
      <h4 className="font-medium">Selected Alerts:</h4>
      {selectedAlertObjects.map(alert => (
        <div key={alert.id} className="flex items-center justify-between p-2 rounded border">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{alert.id}</span>
            <Badge variant="outline" className={severityConfig[alert.severity].className}>
              {severityConfig[alert.severity].label}
            </Badge>
            <span className="text-sm">{alert.title}</span>
          </div>
          {(alert.severity === 'critical' || alert.severity === 'high') ? (
            <Badge variant="destructive">❌ Requires individual review</Badge>
          ) : (
            <Badge variant="secondary">✅ Can bulk resolve</Badge>
          )}
        </div>
      ))}
    </div>

    {/* Solo permite bulk para Medium/Low */}
    <Textarea
      placeholder="Resolution notes for eligible alerts..."
      rows={3}
    />

    <DialogFooter>
      <Button variant="outline" onClick={() => setBulkResolveDialogOpen(false)}>
        Cancel
      </Button>
      <Button
        onClick={handleBulkConfirm}
        disabled={eligibleCount === 0}
      >
        Resolve {eligibleCount} Eligible Alerts
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

**3. Sheet Lateral para Detalles**

Agregar Sheet que se abre al click en el icono Eye:

```tsx
// Modificar línea 271-273
<Button
  variant="ghost"
  size="icon"
  className="h-8 w-8"
  onClick={() => openAlertDetails(alert)}
>
  <Eye className="h-4 w-4" />
</Button>

<Sheet open={detailsSheetOpen} onOpenChange={setDetailsSheetOpen}>
  <SheetContent className="w-2/5 overflow-y-auto">
    <SheetHeader>
      <SheetTitle className="flex items-center gap-2">
        <span className="font-mono">{selectedAlert?.id}</span>
        <Badge variant="outline" className={severityConfig[selectedAlert?.severity].className}>
          {severityConfig[selectedAlert?.severity].label}
        </Badge>
      </SheetTitle>
    </SheetHeader>

    <div className="mt-6 space-y-6">
      {/* Alert Details */}
      <div>
        <h3 className="font-semibold mb-2">Alert Details</h3>
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-muted-foreground">Type</dt>
            <dd className="font-medium">{selectedAlert?.type}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Description</dt>
            <dd>{selectedAlert?.description}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Created</dt>
            <dd>{formatDistanceToNow(selectedAlert?.created_at)} ago</dd>
          </div>
        </dl>
      </div>

      <Separator />

      {/* Affected Items */}
      <div>
        <h3 className="font-semibold mb-2">Affected Items</h3>
        <div className="space-y-1">
          {selectedAlert?.linked_wbs?.map(wbs => (
            <Badge key={wbs} variant="secondary">{wbs}</Badge>
          ))}
        </div>
      </div>

      <Separator />

      {/* Link to Evidence */}
      <Button variant="outline" className="w-full" asChild>
        <Link to={`/evidence?alert=${selectedAlert?.id}`}>
          View in Evidence Viewer →
        </Link>
      </Button>
    </div>
  </SheetContent>
</Sheet>
```

**Puntuación:** 85/100

---

### 1.4 Stakeholder Map - Pendiente de Revisión

Déjame revisar:

<function_calls>
<invoke name="Read">
<parameter name="file_path">C:\Users\esus_\Documents\AI\ZTWQ\c2pro\vision-matched-repo\src\pages\StakeholderMap.tsx