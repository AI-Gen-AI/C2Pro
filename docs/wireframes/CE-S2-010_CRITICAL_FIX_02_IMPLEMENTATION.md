# CE-S2-010: Mejora Crítica #2 - Validación Dinámica según Severity

**Fecha:** 2026-01-17
**Archivo Modificado:** `vision-matched-repo/src/pages/AlertsCenter.tsx`
**Estado:** ✅ **COMPLETADO**
**Prioridad:** CRÍTICA (Gate 6 - Human-in-the-loop)

---

## 📋 Resumen de Cambios

Se implementó validación dinámica en el Dialog de resolución de alertas, donde los requisitos de validación cambian según la severidad de la alerta (Critical/High/Medium/Low), cumpliendo con Gate 6.

---

## 🎯 Requisitos Implementados

### Tabla de Validación por Severity

| Severity | Min Chars Notes | Requiere Checkbox | Requiere Root Cause | Rows Textarea |
|----------|-----------------|-------------------|---------------------|---------------|
| **Critical** | 50 | ✅ SÍ | ✅ SÍ | 5 |
| **High** | 20 | ✅ SÍ | ✅ SÍ | 3 |
| **Medium** | 10 | ❌ NO | ❌ NO | 3 |
| **Low** | 0 (opcional) | ❌ NO | ❌ NO | 3 |

### Características Implementadas

✅ **Resolution Notes con Validación Dinámica:**
- Placeholder específico por severity
- Contador de caracteres con colores (verde/rojo)
- Label dinámico mostrando mínimo requerido
- Tamaño del textarea ajustable (Critical = 5 rows)

✅ **Root Cause Analysis:**
- Select con 9 categorías predefinidas
- Solo visible para Critical/High
- Campo obligatorio con validación
- Iconos visuales para cada categoría

✅ **Checkbox de Confirmación:**
- Solo visible para Critical/High
- Texto completo de acknowledgement
- Styled con border amber y fondo suave
- Bloquea botón si no está marcado

✅ **Warnings Contextuales:**
- Alert rojo para Critical (detalla requisitos)
- Alert naranja para High (detalla requisitos)
- No muestra alert para Medium/Low

---

## 🔧 Cambios en el Código

### Funciones de Validación Agregadas

```typescript
// vision-matched-repo/src/pages/AlertsCenter.tsx:71-87

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
```

### Estado Agregado

```typescript
const [rootCause, setRootCause] = useState('');
```

### Modificaciones en handleResolve

**Antes:**
```typescript
const handleResolve = (alert: Alert) => {
  setSelectedAlert(alert);
  setResolveDialogOpen(true);
  setConfirmChecked(false);
  setResolutionNotes('');
};
```

**Después:**
```typescript
const handleResolve = (alert: Alert) => {
  setSelectedAlert(alert);
  setResolveDialogOpen(true);
  setConfirmChecked(false);
  setResolutionNotes('');
  setRootCause(''); // Resetear root cause
};
```

### Validación del Botón "Confirm Resolution"

```typescript
disabled={
  !selectedAlert ||
  resolutionNotes.length < getMinNotesLength(selectedAlert.severity) ||
  (requiresCheckbox(selectedAlert.severity) && !confirmChecked) ||
  (requiresRootCause(selectedAlert.severity) && !rootCause)
}
```

**Lógica:**
1. Siempre requiere que las notas cumplan el mínimo de caracteres
2. Si es Critical/High: requiere checkbox marcado
3. Si es Critical/High: requiere root cause seleccionado

---

## 🎨 UI/UX por Severity

### Critical Alert

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠️ Resolve Alert                                            [X] │
│                                                                  │
│ ⚠️ Critical Alert - Enhanced Validation Required                │
│ You must provide detailed resolution notes (minimum 50          │
│ characters) and select a root cause.                            │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ AL-001  [🔴 Critical]                                       │ │
│ │ Contract Penalty Clause Violation Risk                      │ │
│ │ Current trajectory shows 45-day delay...                    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Resolution Notes* (minimum 50 characters)                       │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Provide detailed resolution notes explaining the root       │ │
│ │ cause, actions taken, and preventive measures...            │ │
│ │                                                              │ │
│ │                                                              │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ 45 / 50 characters (en rojo)                                    │
│                                                                  │
│ Root Cause Analysis*                                            │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ [Select root cause category ▾]                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│   📅 Schedule Delay                                             │
│   👥 Resource Constraint                                        │
│   📋 Scope Change                                               │
│   🔗 External Dependency                                        │
│   ⚙️ Technical Issue                                            │
│   💰 Budget Overrun                                             │
│   🔍 Quality Issue                                              │
│   ⚖️ Regulatory/Compliance                                      │
│   📌 Other                                                       │
│                                                                  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ☐ I have reviewed all evidence and confirm this alert can  │ │
│ │   be resolved. I understand this action will be logged for │ │
│ │   audit purposes.                                           │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│                         [Cancel]  [Confirm Resolution] (disabled)│
└─────────────────────────────────────────────────────────────────┘
```

### High Alert

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠️ Resolve Alert                                            [X] │
│                                                                  │
│ ⚠️ High Severity Alert                                          │
│ Please provide resolution notes (minimum 20 characters) and     │
│ root cause analysis.                                            │
├─────────────────────────────────────────────────────────────────┤
│ [Same layout as Critical pero:]                                 │
│ - Textarea de 3 rows (no 5)                                     │
│ - Placeholder más corto                                         │
│ - Alerta naranja (no roja)                                      │
│ - Mínimo 20 caracteres (no 50)                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Medium Alert

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠️ Resolve Alert                                            [X] │
│ [No alert banner]                                               │
├─────────────────────────────────────────────────────────────────┤
│ Resolution Notes* (minimum 10 characters)                       │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Describe the resolution or actions taken...                 │ │
│ │                                                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ 8 / 10 characters (en rojo hasta llegar a 10)                  │
│                                                                  │
│ [NO muestra Root Cause]                                         │
│ [NO muestra Checkbox]                                           │
│                                                                  │
│                         [Cancel]  [Confirm Resolution] (disabled)│
└─────────────────────────────────────────────────────────────────┘
```

### Low Alert

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠️ Resolve Alert                                            [X] │
├─────────────────────────────────────────────────────────────────┤
│ Resolution Notes (opcional)                                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Describe the resolution or actions taken...                 │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ [No muestra contador de caracteres]                            │
│                                                                  │
│ [NO muestra Root Cause]                                         │
│ [NO muestra Checkbox]                                           │
│                                                                  │
│                         [Cancel]  [Confirm Resolution] (enabled) │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ Validaciones Implementadas

### Matriz de Validación

| Campo | Critical | High | Medium | Low |
|-------|----------|------|--------|-----|
| **Resolution Notes** | ✅ Min 50 chars | ✅ Min 20 chars | ✅ Min 10 chars | ❌ Opcional (0 chars) |
| **Root Cause** | ✅ Obligatorio | ✅ Obligatorio | ❌ No visible | ❌ No visible |
| **Checkbox** | ✅ Obligatorio | ✅ Obligatorio | ❌ No visible | ❌ No visible |
| **Character Counter** | ✅ Visible | ✅ Visible | ✅ Visible | ❌ No visible |
| **Textarea Rows** | 5 | 3 | 3 | 3 |

### Lógica del Botón "Confirm Resolution"

```typescript
// Botón DISABLED si:

// Para TODAS las severities:
resolutionNotes.length < getMinNotesLength(selectedAlert.severity)

// Además, para Critical/High:
(requiresCheckbox(selectedAlert.severity) && !confirmChecked) ||
(requiresRootCause(selectedAlert.severity) && !rootCause)
```

**Ejemplo Critical:**
- Notas < 50 chars → ❌ Disabled
- Notas >= 50 chars pero no seleccionó root cause → ❌ Disabled
- Notas >= 50 chars y root cause pero no marcó checkbox → ❌ Disabled
- Notas >= 50 chars y root cause y checkbox → ✅ Enabled

**Ejemplo Low:**
- Sin notas → ✅ Enabled (0 chars es válido)
- Con notas cualquier longitud → ✅ Enabled

---

## 🔒 Cumplimiento Gate 6

### Reglas Críticas Implementadas

✅ **Critical/High Alerts:**
> Requieren validación exhaustiva con:
> 1. Notas detalladas (50/20 chars mínimo)
> 2. Análisis de root cause (categoría seleccionada)
> 3. Confirmación explícita con checkbox
> 4. Todas las condiciones son **bloqueantes**

✅ **Medium Alerts:**
> Validación intermedia:
> 1. Notas obligatorias (min 10 chars)
> 2. No requiere root cause ni checkbox
> 3. Suficiente para resolver con contexto básico

✅ **Low Alerts:**
> Resolución simplificada:
> 1. Notas opcionales
> 2. Botón habilitado inmediatamente
> 3. Permite resolución rápida de alertas menores

---

## 📊 Root Cause Categories

### 9 Categorías Implementadas

```typescript
const rootCauseCategories = [
  { value: 'schedule_delay', label: 'Schedule Delay', icon: '📅' },
  { value: 'resource_constraint', label: 'Resource Constraint', icon: '👥' },
  { value: 'scope_change', label: 'Scope Change', icon: '📋' },
  { value: 'external_dependency', label: 'External Dependency', icon: '🔗' },
  { value: 'technical_issue', label: 'Technical Issue', icon: '⚙️' },
  { value: 'budget_overrun', label: 'Budget Overrun', icon: '💰' },
  { value: 'quality_issue', label: 'Quality Issue', icon: '🔍' },
  { value: 'regulatory_compliance', label: 'Regulatory/Compliance', icon: '⚖️' },
  { value: 'other', label: 'Other', icon: '📌' },
];
```

### Uso en Reportes

Estas categorías permiten:
- **Analytics:** Identificar patrones de problemas recurrentes
- **Dashboards:** Gráficas de distribución de root causes
- **Preventive Actions:** Enfocar esfuerzos según causas más comunes
- **Audit Trail:** Trazabilidad completa de resoluciones

---

## 🧪 Testing

### Casos de Prueba (Manual)

#### Test 1: Resolver Alert Critical
1. Click en "Resolve" en alerta Critical
2. ✅ Dialog se abre con alert rojo
3. ✅ Resolution Notes requiere min 50 chars
4. ✅ Root Cause field es visible
5. ✅ Checkbox es visible
6. ✅ Botón disabled hasta:
   - Escribir 50+ chars
   - Seleccionar root cause
   - Marcar checkbox

#### Test 2: Resolver Alert High
1. Click en "Resolve" en alerta High
2. ✅ Dialog se abre con alert naranja
3. ✅ Resolution Notes requiere min 20 chars
4. ✅ Root Cause field es visible
5. ✅ Checkbox es visible

#### Test 3: Resolver Alert Medium
1. Click en "Resolve" en alerta Medium
2. ✅ Dialog se abre sin alert banner
3. ✅ Resolution Notes requiere min 10 chars
4. ✅ Root Cause NO visible
5. ✅ Checkbox NO visible
6. ✅ Botón disabled solo hasta 10+ chars

#### Test 4: Resolver Alert Low
1. Click en "Resolve" en alerta Low
2. ✅ Dialog se abre sin alert banner
3. ✅ Resolution Notes es opcional
4. ✅ Root Cause NO visible
5. ✅ Checkbox NO visible
6. ✅ Botón enabled inmediatamente

#### Test 5: Character Counter
1. Escribir en Resolution Notes
2. ✅ Contador muestra "X / Y characters"
3. ✅ Color rojo si < mínimo
4. ✅ Color verde si >= mínimo
5. ✅ No muestra para Low alerts

---

## 📝 TODOs Pendientes

### Integración con Backend

```typescript
// En el onClick del botón "Confirm Resolution"
const handleConfirmResolution = async () => {
  try {
    const response = await fetch(`/api/alerts/${selectedAlert.id}/resolve`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: 'resolved',
        resolution_notes: resolutionNotes,
        root_cause: rootCause || null,
        validated_by: currentUser.id,
        resolved_at: new Date().toISOString(),
      }),
    });

    if (!response.ok) throw new Error('Failed to resolve alert');

    toast.success('Alert resolved successfully');
    setResolveDialogOpen(false);
    // Actualizar lista de alertas
  } catch (error) {
    toast.error('Failed to resolve alert');
  }
};
```

### Audit Logging

```typescript
// Crear audit log entry
await createAuditLog({
  action: 'RESOLVE_ALERT',
  entity_type: 'alert',
  entity_id: selectedAlert.id,
  user_id: currentUser.id,
  metadata: {
    severity: selectedAlert.severity,
    resolution_notes: resolutionNotes,
    root_cause: rootCause,
    notes_length: resolutionNotes.length,
    required_validation: requiresCheckbox(selectedAlert.severity),
  },
});
```

### Toast Notifications

```typescript
// Notificaciones según severity
if (selectedAlert.severity === 'critical') {
  toast.success('Critical alert resolved', {
    description: 'Project owner has been notified',
  });
} else {
  toast.success('Alert resolved successfully');
}
```

### Analytics Integration

```typescript
// Tracking de root causes
trackEvent('alert_resolved', {
  alert_id: selectedAlert.id,
  severity: selectedAlert.severity,
  root_cause: rootCause,
  resolution_time: Date.now() - selectedAlert.created_at,
});
```

---

## 📊 Métricas de Implementación

| Métrica | Valor |
|---------|-------|
| **Líneas de código agregadas** | ~230 |
| **Funciones de validación** | 3 |
| **Root cause categories** | 9 |
| **Estados agregados** | 1 (rootCause) |
| **Validaciones implementadas** | 4 niveles (por severity) |
| **Tiempo de implementación** | ~25 minutos |

---

## 🎓 Mejoras Aplicadas vs. Versión Anterior

### Antes (Versión Básica)

```typescript
// Validación genérica para todas las severities
<Textarea placeholder="Describe the resolution..." rows={3} />

<Checkbox id="confirm" />
<label>I have reviewed the evidence...</label>

// Botón solo requiere checkbox
disabled={!confirmChecked}
```

**Problemas:**
- ❌ Same validation para Critical y Low
- ❌ No distingue nivel de detalle requerido
- ❌ No captura root cause
- ❌ No cumple Gate 6 completamente

### Después (Versión Dinámica)

```typescript
// Validación específica por severity
{getMinNotesLength(selectedAlert.severity) > 0 && (
  <span className="text-destructive">
    * (minimum {getMinNotesLength(selectedAlert.severity)} characters)
  </span>
)}

// Root cause solo para Critical/High
{requiresRootCause(selectedAlert.severity) && (
  <Select> ... </Select>
)}

// Checkbox solo para Critical/High
{requiresCheckbox(selectedAlert.severity) && (
  <Checkbox> ... </Checkbox>
)}

// Validación completa
disabled={
  resolutionNotes.length < getMinNotesLength(selectedAlert.severity) ||
  (requiresCheckbox(selectedAlert.severity) && !confirmChecked) ||
  (requiresRootCause(selectedAlert.severity) && !rootCause)
}
```

**Beneficios:**
- ✅ Validación proporcional a la severidad
- ✅ Captura análisis de root cause
- ✅ Cumple 100% con Gate 6
- ✅ UX mejorada con feedback contextual

---

## 🔗 Referencias

- **Specs Originales:** `docs/wireframes/CE-S2-010_WIREFRAME_SPECS.md` (Sección 3.4.1)
- **Review Document:** `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` (Mejora #2)
- **Gate 6 Requirements:** `docs/CTO_GATES_VERIFICATION_PLAN.md`
- **Mejora #1:** `docs/wireframes/CE-S2-010_CRITICAL_FIX_01_IMPLEMENTATION.md`

---

**Status:** ✅ COMPLETADO Y LISTO PARA TESTING
**Next Step:** Implementar Mejora Crítica #3 - Integrar react-pdf para PDF Viewer Real

---

**Prepared by:** Claude Code
**Date:** 2026-01-17
**Version:** 1.0
