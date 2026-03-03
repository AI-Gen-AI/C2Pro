# Plan de Implementación: Coherence Score con Desglose por Categorías

**Basado en:** COHERENCE_SCORE_ENHANCEMENT_ANALYSIS.md
**Fecha:** 2026-01-20

---

## RESUMEN EJECUTIVO

### Objetivo
Implementar un sistema de desglose del Coherence Score por categorías (Legal, Financial, Technical, Schedule, Scope), permitiendo al usuario hacer clic en el score para ver un detalle completo del impacto de cada categoría.

### Entregables
1. Backend: Modelos, scoring service y endpoints con soporte para categorías
2. Frontend: Modal interactivo con desglose visual por categorías
3. Documentación y tests

---

## DESGLOSE DETALLADO DE TAREAS

### 📦 FASE 1: Backend - Modelo de Datos (Prioridad: ALTA)

#### Task 1.1: Agregar campo `category` a modelo `Alert`
**Archivo:** `apps/api/src/modules/coherence/models.py`

**Cambios:**
```python
class Alert(BaseModel):
    rule_id: str
    severity: str
    category: str  # NEW: 'legal', 'financial', 'technical', 'schedule', 'scope'
    message: str
    evidence: Evidence
```

**Validaciones:**
- Agregar enum para categorías válidas
- Asegurar que category sea obligatorio

**Tiempo:** 30 min

---

#### Task 1.2: Crear modelo `CategoryBreakdown`
**Archivo:** `apps/api/src/modules/coherence/models.py`

**Nuevo modelo:**
```python
class SeverityCount(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0

class CategoryBreakdown(BaseModel):
    category: str
    score: float
    alert_count: int
    severity_breakdown: SeverityCount
    impact_percentage: float  # % del total de deducciones
```

**Tiempo:** 30 min

---

#### Task 1.3: Extender modelo `CoherenceResult`
**Archivo:** `apps/api/src/modules/coherence/models.py`

**Cambios:**
```python
class CoherenceResult(BaseModel):
    overall_score: float  # Rename from 'score'
    alerts: list[Alert]
    category_breakdown: list[CategoryBreakdown]  # NEW
    calculated_at: datetime  # NEW
```

**Tiempo:** 20 min

---

#### Task 1.4: Actualizar tests unitarios de modelos
**Archivo:** `apps/api/tests/unit/test_coherence_models.py` (crear si no existe)

**Tests a crear:**
- Test creación de Alert con category
- Test creación de CategoryBreakdown
- Test creación de CoherenceResult con category_breakdown
- Test validación de categorías inválidas

**Tiempo:** 1 hora

---

### 📋 FASE 2: Backend - Reglas y Motor (Prioridad: ALTA)

#### Task 2.1: Actualizar `initial_rules.yaml` con categorías
**Archivo:** `apps/api/src/modules/coherence/initial_rules.yaml`

**Ejemplo de cambio:**
```yaml
- id: "contract-penalty-clause"
  name: "Contract Penalty Clause Violation"
  category: "legal"  # NEW
  severity: "critical"
  # ... rest of rule
```

**Categorización sugerida:**
- Budget overrun → financial
- Penalty clauses → legal
- Schedule delays → schedule
- Equipment compatibility → technical
- Scope changes → scope

**Tiempo:** 1 hora

---

#### Task 2.2: Modificar motor de coherencia para asignar categorías
**Archivo:** `apps/api/src/modules/coherence/engine.py`

**Cambios:**
- Al generar alertas, copiar el campo `category` de la regla al alert
- Asegurar que todas las alertas tengan categoría asignada

**Tiempo:** 30 min

---

#### Task 2.3: Actualizar tests de motor de coherencia
**Archivo:** `apps/api/tests/integration/test_coherence_engine.py`

**Tests a actualizar/crear:**
- Test que verifica que las alertas incluyen category
- Test de evaluación completa con múltiples categorías

**Tiempo:** 1 hora

---

### 🧮 FASE 3: Backend - Scoring Service (Prioridad: ALTA)

#### Task 3.1: Implementar cálculo de score por categoría
**Archivo:** `apps/api/src/modules/coherence/scoring.py`

**Nuevos métodos:**
```python
class ScoringService:
    def compute_score_with_breakdown(
        self, alerts: list[Alert]
    ) -> tuple[float, list[CategoryBreakdown]]:
        """
        Computes overall score and breakdown by category.

        Returns:
            (overall_score, category_breakdown_list)
        """
        # 1. Group alerts by category
        # 2. Calculate deductions per category
        # 3. Calculate score per category
        # 4. Calculate impact percentage
        # 5. Return overall score + breakdown
```

**Lógica de cálculo:**
- Cada categoría parte de 100 puntos
- Se aplican las mismas reglas de deducción (severity + decay)
- Impact percentage = (deducciones de categoría / deducciones totales) * 100

**Tiempo:** 2-3 horas

---

#### Task 3.2: Actualizar método `compute_score` existente
**Archivo:** `apps/api/src/modules/coherence/scoring.py`

**Cambios:**
- Mantener método original para compatibilidad
- O migrar completamente a nuevo método con breakdown

**Tiempo:** 30 min

---

#### Task 3.3: Agregar tests de scoring avanzado
**Archivo:** `apps/api/tests/unit/test_scoring_service.py`

**Tests a crear:**
- Test score por categoría con alertas de una sola categoría
- Test score por categoría con alertas de múltiples categorías
- Test cálculo de impact percentage
- Test edge cases (sin alertas, todas las alertas de una categoría)

**Tiempo:** 1.5 horas

---

### 🔌 FASE 4: Backend - Endpoints y Service (Prioridad: MEDIA)

#### Task 4.1: Actualizar endpoint `/v0/coherence/evaluate`
**Archivo:** `apps/api/src/modules/coherence/router.py`

**Cambios:**
- Usar nuevo método `compute_score_with_breakdown`
- Asegurar que response incluye category_breakdown

**Tiempo:** 30 min

---

#### Task 4.2: Actualizar/Crear endpoint GET `/projects/{id}/coherence-score`
**Archivo:** `apps/api/src/modules/projects/router.py`

**Endpoint:**
```python
@router.get("/{project_id}/coherence-score")
async def get_project_coherence_score(
    project_id: UUID,
    db: Session = Depends(get_db)
) -> CoherenceScoreResponse:
    """
    Retrieves the latest coherence score for a project,
    including category breakdown.
    """
```

**Tiempo:** 1 hora (si no existe) / 30 min (si ya existe)

---

#### Task 4.3: Actualizar service de coherence
**Archivo:** `apps/api/src/modules/coherence/service.py`

**Cambios:**
- Actualizar `CoherenceScore` mock con category_breakdown
- O implementar lógica real si ya no es mock

**Tiempo:** 30 min

---

### 💻 FASE 5: Frontend - Tipos y API Client (Prioridad: MEDIA)

#### Task 5.1: Definir tipos TypeScript
**Archivo:** `apps/web/types/coherence.ts` (crear)

```typescript
export type AlertCategory = 'Legal' | 'Financial' | 'Technical' | 'Schedule' | 'Scope';

export interface SeverityBreakdown {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface CategoryBreakdown {
  category: AlertCategory;
  score: number;
  alert_count: number;
  severity_breakdown: SeverityBreakdown;
  impact_percentage: number;
}

export interface CoherenceScoreDetail {
  overall_score: number;
  category_breakdown: CategoryBreakdown[];
  calculated_at: string;
}
```

**Tiempo:** 30 min

---

#### Task 5.2: Crear hook `useCoherenceScore`
**Archivo:** `apps/web/hooks/useCoherenceScore.ts` (crear)

```typescript
export function useCoherenceScore(projectId: string) {
  return useQuery({
    queryKey: ['coherence-score', projectId],
    queryFn: () => fetchCoherenceScore(projectId),
  });
}
```

**Tiempo:** 30 min

---

#### Task 5.3: Crear función de API client
**Archivo:** `apps/web/lib/api/coherence.ts` (crear)

```typescript
export async function fetchCoherenceScore(
  projectId: string
): Promise<CoherenceScoreDetail> {
  // Implementation
}
```

**Tiempo:** 30 min

---

### 🎨 FASE 6: Frontend - Componentes UI (Prioridad: ALTA)

#### Task 6.1: Crear `CategoryBreakdownCard`
**Archivo:** `apps/web/components/coherence/CategoryBreakdownCard.tsx`

**Props:**
```typescript
interface CategoryBreakdownCardProps {
  category: AlertCategory;
  score: number;
  alertCount: number;
  severityBreakdown: SeverityBreakdown;
  impactPercentage: number;
}
```

**UI:**
- Card con color según categoría
- Mini gauge o progress bar para el score
- Lista de severity counts con badges
- Impact percentage destacado

**Tiempo:** 1.5 horas

---

#### Task 6.2: Crear `CoherenceScoreModal`
**Archivo:** `apps/web/components/coherence/CoherenceScoreModal.tsx`

**Props:**
```typescript
interface CoherenceScoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  overallScore: number;
  categoryBreakdown: CategoryBreakdown[];
}
```

**UI:**
- Dialog/Modal usando Radix UI
- Header con overall score
- Grid de CategoryBreakdownCard
- Footer con botones de acción

**Tiempo:** 2 horas

---

#### Task 6.3: Modificar `GaugeChart` para ser clickeable
**Archivo:** `apps/web/components/dashboard/GaugeChart.tsx`

**Cambios:**
- Agregar prop `onClick?: () => void`
- Agregar cursor pointer cuando onClick está presente
- Agregar indicador visual de que es clickeable (ej: hover effect)

**Tiempo:** 30 min

---

#### Task 6.4: Crear constantes de colores por categoría
**Archivo:** `apps/web/lib/constants/categories.ts`

```typescript
export const CATEGORY_COLORS = {
  Legal: '#3B82F6',
  Financial: '#10B981',
  Technical: '#8B5CF6',
  Schedule: '#F59E0B',
  Scope: '#06B6D4',
} as const;
```

**Tiempo:** 15 min

---

### 🔗 FASE 7: Frontend - Integración (Prioridad: ALTA)

#### Task 7.1: Integrar modal en Dashboard
**Archivo:** `apps/web/app/(app)/page.tsx`

**Cambios:**
```typescript
const [scoreModalOpen, setScoreModalOpen] = useState(false);
const { data: scoreDetail } = useCoherenceScore(currentProjectId);

<GaugeChart
  value={mockKPIData.coherenceScore}
  onClick={() => setScoreModalOpen(true)}
/>

<CoherenceScoreModal
  isOpen={scoreModalOpen}
  onClose={() => setScoreModalOpen(false)}
  overallScore={scoreDetail?.overall_score}
  categoryBreakdown={scoreDetail?.category_breakdown}
/>
```

**Tiempo:** 1 hora

---

#### Task 7.2: Agregar loading states y error handling
**Archivo:** `apps/web/components/coherence/CoherenceScoreModal.tsx`

**Mejoras:**
- Skeleton loading para category cards
- Error state si falla la carga
- Empty state si no hay datos

**Tiempo:** 45 min

---

### 🧪 FASE 8: Testing y Refinamiento (Prioridad: MEDIA)

#### Task 8.1: Tests unitarios de componentes
**Archivos:** `apps/web/components/coherence/__tests__/`

- Test CategoryBreakdownCard rendering
- Test CoherenceScoreModal interacción
- Test GaugeChart onClick

**Tiempo:** 2 horas

---

#### Task 8.2: Tests de integración E2E
**Herramienta:** Playwright o Cypress

**Escenarios:**
- Click en gauge abre modal
- Modal muestra breakdown correcto
- Cierre de modal funciona
- Navegación a alertas desde modal

**Tiempo:** 2 horas

---

#### Task 8.3: Ajustes de UX/UI
**Feedback-driven:**
- Ajustar colores según feedback
- Mejorar responsive design
- Pulir animaciones y transiciones

**Tiempo:** 1.5 horas

---

### 📚 FASE 9: Documentación (Prioridad: BAJA)

#### Task 9.1: Documentar API endpoints
**Archivo:** Actualizar OpenAPI docs / Swagger

**Tiempo:** 30 min

---

#### Task 9.2: Documentar componentes frontend
**Archivos:** Agregar JSDoc comments

**Tiempo:** 30 min

---

#### Task 9.3: Guía de usuario
**Archivo:** `docs/USER_GUIDE_COHERENCE_SCORE.md`

**Contenido:**
- Cómo interpretar el score
- Qué significa cada categoría
- Cómo usar el desglose para tomar decisiones

**Tiempo:** 1 hora

---

## DEPENDENCIAS Y ORDEN RECOMENDADO

```
FASE 1 (Modelos) → FASE 2 (Reglas) → FASE 3 (Scoring)
                                          ↓
                                       FASE 4 (Endpoints)
                                          ↓
                    FASE 5 (Tipos TS) ← ┘
                           ↓
                    FASE 6 (UI Components)
                           ↓
                    FASE 7 (Integración)
                           ↓
                    FASE 8 (Testing)
                           ↓
                    FASE 9 (Docs)
```

---

## RESUMEN DE ESFUERZO

| Fase | Tareas | Tiempo Estimado |
|------|--------|-----------------|
| 1. Backend - Modelos | 4 | 2.5 horas |
| 2. Backend - Reglas | 3 | 2.5 horas |
| 3. Backend - Scoring | 3 | 4 horas |
| 4. Backend - Endpoints | 3 | 2 horas |
| 5. Frontend - API | 3 | 1.5 horas |
| 6. Frontend - UI | 4 | 4.5 horas |
| 7. Frontend - Integración | 2 | 1.75 horas |
| 8. Testing | 3 | 5.5 horas |
| 9. Documentación | 3 | 2 horas |
| **TOTAL** | **28 tareas** | **~26 horas** |

---

## SIGUIENTE PASO

¿Quieres que empecemos con la implementación? Sugiero comenzar por:

**Opción A (Backend First):**
- Fase 1: Modelos
- Fase 2: Reglas
- Fase 3: Scoring

**Opción B (Prototipo Visual First):**
- Fase 5: Tipos TypeScript
- Fase 6: UI Components (con datos mock)
- Luego backend

**Opción C (Incremental):**
- Task 1.1-1.3 (Modelos)
- Task 6.1-6.2 (UI Components con mock)
- Ver funcionando visualmente
- Continuar con backend completo

¿Cuál prefieres?

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
