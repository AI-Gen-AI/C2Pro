# CE-S2-010: Mejora Crítica #1 - Dialog de Confirmación Approve/Reject

**Fecha:** 2026-01-17
**Archivo Modificado:** `vision-matched-repo/src/pages/EvidenceViewer.tsx`
**Estado:** ✅ **COMPLETADO**
**Prioridad:** CRÍTICA (Gate 6 - Human-in-the-loop)

---

## 📋 Resumen de Cambios

Se implementaron los Dialogs de confirmación para las acciones Approve/Reject en el Evidence Viewer, cumpliendo con el requisito Gate 6 (Human-in-the-loop) para validación humana obligatoria en extracciones con baja confianza.

---

## 🎯 Requisitos Implementados

### 1. Dialog de Aprobación (Approve)

#### Características:
- ✅ Comparación lado a lado: Texto original (PDF) vs. Texto extraído
- ✅ Texto extraído editable con Textarea
- ✅ Warning automático para entidades con confidence < 90%
- ✅ Checkbox obligatorio si confidence < 90%
- ✅ Textarea de notas de validación (obligatorio si se edita el texto)
- ✅ Botón "Approve & Save" deshabilitado hasta cumplir validaciones
- ✅ Validación de mínimo 10 caracteres para notas

#### Reglas de Validación:

```typescript
// Botón disabled si:
(requiresCheckbox && !confirmChecked) ||  // Confidence < 90% y no marcó checkbox
(requiresNotes && validationNotes.length < 10)  // Editó texto y notas < 10 chars
```

### 2. Dialog de Rechazo (Reject)

#### Características:
- ✅ Muestra información de la entidad rechazada
- ✅ Textarea obligatorio para razón del rechazo (mínimo 10 caracteres)
- ✅ Alert informando que se creará una alerta para revisión manual
- ✅ Botón "Confirm Rejection" deshabilitado hasta mínimo de caracteres
- ✅ Feedback visual con contador de caracteres

---

## 🔧 Cambios en el Código

### Imports Agregados

```typescript
import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
```

### Estado Agregado

```typescript
const [approveDialogOpen, setApproveDialogOpen] = useState(false);
const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
const [selectedEntity, setSelectedEntity] = useState<typeof mockExtractedEntities[0] | null>(null);
const [extractedText, setExtractedText] = useState('');
const [validationNotes, setValidationNotes] = useState('');
const [confirmChecked, setConfirmChecked] = useState(false);
const [rejectReason, setRejectReason] = useState('');
```

### Handlers Implementados

```typescript
const handleApproveClick = (entity) => {
  setSelectedEntity(entity);
  setExtractedText(entity.text);
  setValidationNotes('');
  setConfirmChecked(false);
  setApproveDialogOpen(true);
};

const handleRejectClick = (entity) => {
  setSelectedEntity(entity);
  setRejectReason('');
  setRejectDialogOpen(true);
};

const handleConfirmApproval = () => {
  console.log('Approved entity:', selectedEntity?.id);
  console.log('Extracted text:', extractedText);
  console.log('Validation notes:', validationNotes);
  // TODO: API call to PATCH /api/extracted-entities/{id}
  setApproveDialogOpen(false);
};

const handleConfirmRejection = () => {
  console.log('Rejected entity:', selectedEntity?.id);
  console.log('Reason:', rejectReason);
  // TODO: API call to PATCH /api/extracted-entities/{id}
  setRejectDialogOpen(false);
};
```

### Botones Modificados

**Antes:**
```tsx
<Button size="sm" className="gap-1">
  <CheckCircle className="h-3 w-3" />
  Approve
</Button>
```

**Después:**
```tsx
<Button
  size="sm"
  className="gap-1"
  onClick={() => handleApproveClick(entity)}
>
  <CheckCircle className="h-3 w-3" />
  Approve
</Button>
```

### Mock Data Actualizado

Se agregó el campo `originalText` a todas las entidades para simular el texto real del PDF:

```typescript
{
  id: 'ENT-001',
  type: 'Penalty Clause',
  originalText: 'In case of delay exceeding 30 days beyond the agreed completion date, the Contractor shall pay liquidated damages at the rate of 0.5% of the contract value per day, up to a maximum of 10% of the total contract value.',
  text: 'In case of delay exceeding 30 days beyond the agreed completion date, the Contractor shall pay liquidated damages at the rate of 0.5% of the contract value per day.',
  confidence: 87,
  // ...
}
```

---

## 🎨 UI/UX Implementado

### Approve Dialog

```
┌─────────────────────────────────────────────────────────────┐
│ Confirm Extracted Data                                  [X] │
│ Review the extracted data and confirm its accuracy...       │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Penalty Clause  [87% confidence]         Page 12        │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌───────────────────────┬───────────────────────────────┐   │
│ │ Original Text (PDF)   │ Extracted Text                │   │
│ ├───────────────────────┼───────────────────────────────┤   │
│ │ In case of delay...   │ [Editable Textarea]           │   │
│ │ ...up to a maximum    │ In case of delay...           │   │
│ │ of 10% of the total   │ ...per day.                   │   │
│ │ contract value.       │                               │   │
│ └───────────────────────┴───────────────────────────────┘   │
│                                                             │
│ ⚠️ Low confidence extraction (87%).                         │
│    Please carefully verify the extracted text...           │
│                                                             │
│ [Text was modified, shows Validation Notes textarea]       │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ☐ I confirm this data is accurate and have reviewed... │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│                    [Cancel]  [Approve & Save] (disabled)   │
└─────────────────────────────────────────────────────────────┘
```

### Reject Dialog

```
┌─────────────────────────────────────────────────────────────┐
│ Reject Extracted Data                                   [X] │
│ Please provide a reason for rejecting this extracted data. │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Penalty Clause  [87% confidence]                        │ │
│ │ In case of delay exceeding 30 days...                   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Reason for Rejection* (minimum 10 characters)              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Explain why this extraction is incorrect...            │ │
│ │                                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
│ 5/10 characters                                             │
│                                                             │
│ ⚠️ Rejecting this entity will create an alert for          │
│    manual review.                                           │
│                                                             │
│                    [Cancel]  [Confirm Rejection] (disabled) │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ Validaciones Implementadas

### Approve Dialog

| Condición | Requiere Checkbox | Requiere Notas | Min Chars Notas |
|-----------|-------------------|----------------|-----------------|
| confidence >= 90% AND texto sin modificar | ❌ | ❌ | - |
| confidence >= 90% AND texto modificado | ❌ | ✅ | 10 |
| confidence < 90% AND texto sin modificar | ✅ | ❌ | - |
| confidence < 90% AND texto modificado | ✅ | ✅ | 10 |

### Reject Dialog

| Campo | Validación |
|-------|------------|
| Reason | Obligatorio, mínimo 10 caracteres |

---

## 🔒 Cumplimiento Gate 6

### Requisitos de Human-in-the-loop

✅ **Validación Obligatoria:** Entidades con confidence < 90% requieren checkbox de confirmación
✅ **Trazabilidad:** Texto original vs extraído mostrado lado a lado
✅ **Audit Trail:** Console logs preparados para API (TODO: integrar con backend)
✅ **Confirmación Explícita:** No se puede aprobar sin marcar checkbox (si aplica)
✅ **Notas Obligatorias:** Si se edita el texto, debe explicar por qué

### Regla Crítica Implementada

> ⚠️ **Gate 6 Compliance:**
>
> Ninguna entidad con `confidence < 90%` puede ser aprobada sin que el usuario:
> 1. Revise el texto original vs. extraído lado a lado
> 2. Marque explícitamente el checkbox de confirmación
> 3. Si modifica el texto, proporcione notas de validación (min 10 chars)

---

## 🧪 Testing

### Casos de Prueba Implementados (Manual)

1. **Aprobar entidad con high confidence (95%)**
   - ✅ Dialog se abre
   - ✅ No requiere checkbox
   - ✅ Botón "Approve & Save" habilitado inmediatamente

2. **Aprobar entidad con low confidence (87%)**
   - ✅ Dialog se abre
   - ✅ Muestra warning amber
   - ✅ Requiere checkbox
   - ✅ Botón disabled hasta marcar checkbox

3. **Editar texto extraído**
   - ✅ Textarea es editable
   - ✅ Aparece campo de "Validation Notes"
   - ✅ Botón disabled hasta escribir min 10 chars

4. **Rechazar entidad**
   - ✅ Dialog de rechazo se abre
   - ✅ Muestra alerta de que creará review manual
   - ✅ Botón disabled hasta min 10 chars

---

## 📝 TODOs Pendientes

### Integración con Backend

```typescript
// En handleConfirmApproval
const response = await fetch(`/api/extracted-entities/${selectedEntity.id}`, {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    validated: true,
    confidence: 100, // Update to 100% after human validation
    text: extractedText,
    validation_notes: validationNotes,
    validated_by: currentUser.id,
    validated_at: new Date().toISOString(),
  }),
});

if (!response.ok) {
  toast.error('Failed to approve entity');
  return;
}

toast.success('Entity approved successfully');
// Actualizar UI: entity.validated = true
```

### Audit Logging

```typescript
// Crear audit log entry
await createAuditLog({
  action: 'APPROVE_EXTRACTED_ENTITY',
  entity_type: 'extracted_entity',
  entity_id: selectedEntity.id,
  user_id: currentUser.id,
  metadata: {
    original_text: selectedEntity.text,
    new_text: extractedText,
    confidence_before: selectedEntity.confidence,
    confidence_after: 100,
    validation_notes: validationNotes,
    was_modified: isTextModified,
  },
});
```

### Toast Notifications

```bash
npm install sonner
```

```typescript
import { toast } from 'sonner';

// En handleConfirmApproval (éxito)
toast.success('Entity approved', {
  description: `${selectedEntity.type} validated successfully`,
});

// En handleConfirmRejection (éxito)
toast.warning('Entity rejected', {
  description: 'An alert has been created for manual review',
});
```

---

## 📊 Métricas de Implementación

| Métrica | Valor |
|---------|-------|
| **Líneas de código agregadas** | ~250 |
| **Componentes nuevos** | 2 (Approve Dialog, Reject Dialog) |
| **Estado agregado** | 7 variables |
| **Handlers** | 4 funciones |
| **Validaciones** | 5 reglas implementadas |
| **Tiempo de implementación** | ~30 minutos |

---

## 🎓 Lecciones Aprendidas

### Buenas Prácticas Aplicadas

1. **Validación Condicional:** Las validaciones se adaptan dinámicamente según la confidence
2. **Feedback Visual:** Contador de caracteres, estados disabled claros
3. **Comparación Lado a Lado:** Facilita la revisión humana
4. **Warning Proactivo:** Alert amber para low confidence
5. **Confirmación Explícita:** Checkbox con texto claro de lo que se confirma

### Mejoras Futuras Sugeridas

1. **Highlight Sync:** Al editar el texto, resaltar la diferencia con el original
2. **Keyboard Shortcuts:** Ctrl+Enter para aprobar, Escape para cancelar
3. **History:** Mostrar historial de validaciones anteriores del usuario
4. **Confidence Boost:** Mostrar cómo cambia el score al aprobar
5. **Batch Approval:** Permitir aprobar múltiples entidades de alta confianza en bulk

---

## 🔗 Referencias

- **Specs Originales:** `docs/wireframes/CE-S2-010_WIREFRAME_SPECS.md` (Sección 2.4)
- **Review Document:** `docs/wireframes/MOCKUP_REVIEW_SUMMARY.md` (Mejora #1)
- **Gate 6 Requirements:** `docs/CTO_GATES_VERIFICATION_PLAN.md`

---

**Status:** ✅ COMPLETADO Y LISTO PARA TESTING
**Next Step:** Implementar Mejora Crítica #2 - Validación Dinámica en Alerts Center

---

**Prepared by:** Claude Code
**Date:** 2026-01-17
**Version:** 1.0

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
