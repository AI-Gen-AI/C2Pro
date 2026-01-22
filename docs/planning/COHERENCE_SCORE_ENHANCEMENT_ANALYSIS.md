# Análisis: Mejora del Coherence Score con Desglose por Categorías

**Fecha:** 2026-01-20
**Objetivo:** Implementar desglose detallado del Coherence Score por categorías de alerta

---

## 1. ANÁLISIS DEL OBJETIVO

### 1.1 Estado Actual

**Backend:**
- El sistema tiene un motor de coherencia que evalúa reglas y genera alertas
- Las alertas tienen `severity` (critical, high, medium, low) pero NO tienen categorías
- El scoring se calcula con base en severity y deducción de puntos
- Modelo actual: `CoherenceResult` con `alerts[]` y `score`

**Frontend:**
- GaugeChart muestra el score global (0-100)
- No hay desglose por categorías
- No hay vista detallada al hacer clic en el score

### 1.2 Objetivo Deseado

Implementar un sistema de **categorización de alertas** similar al de la página Alerts:
- **Legal**: Cláusulas contractuales, penalidades, términos legales
- **Financial**: Presupuesto, sobrecostos, variaciones económicas
- **Technical**: Especificaciones técnicas, compatibilidad de equipos
- **Schedule**: Cronograma, retrasos, hitos críticos
- **Scope**: Alcance del proyecto, cambios en requerimientos

### 1.3 Funcionalidad Esperada

1. **Vista Global del Score**: El gauge actual se mantiene mostrando el score general
2. **Click to Expand**: Al hacer clic en el score, se despliega un desglose detallado
3. **Desglose por Categoría**:
   - Mostrar el score por cada categoría
   - Número de alertas por categoría y severidad
   - Impacto de cada categoría en el score total
4. **Navegación**: Desde el desglose, poder navegar a las alertas específicas

---

## 2. ANÁLISIS TÉCNICO

### 2.1 Cambios en el Backend

#### 2.1.1 Modelo de Datos
- **Agregar campo `category`** al modelo `Alert`
- **Crear nuevo modelo `CategoryBreakdown`** con:
  - `category`: string (legal, financial, technical, schedule, scope)
  - `score`: float (score parcial de esta categoría)
  - `alert_count`: int (número de alertas)
  - `severity_breakdown`: dict (conteo por severidad)
  - `impact`: float (% de impacto en el score total)

- **Extender `CoherenceResult`** para incluir:
  - `overall_score`: float (score general)
  - `category_breakdown`: list[CategoryBreakdown]
  - `alerts`: list[Alert] (con categoría incluida)

#### 2.1.2 Reglas y Configuración
- Actualizar `initial_rules.yaml` para incluir categoría en cada regla
- Actualizar el motor de coherencia para asignar categoría a cada alerta generada

#### 2.1.3 Scoring Service
- Modificar `ScoringService.compute_score()` para:
  - Calcular score general
  - Calcular score por categoría
  - Calcular impacto proporcional de cada categoría

#### 2.1.4 Endpoint
- Mantener `/v0/coherence/evaluate` con modelo extendido
- Considerar nuevo endpoint `/projects/{id}/coherence-score` (ya existe según git log)

### 2.2 Cambios en el Frontend

#### 2.2.1 Componentes Nuevos
- **`CoherenceScoreModal`**: Modal/Dialog que se abre al hacer clic en el gauge
- **`CategoryBreakdownCard`**: Card individual para cada categoría
- **`CategoryScoreGauge`**: Gauge pequeño para score por categoría

#### 2.2.2 Componentes a Modificar
- **`GaugeChart`**: Agregar onClick handler para abrir el modal
- **Dashboard page**: Integrar el nuevo modal

#### 2.2.3 Tipos TypeScript
```typescript
interface CategoryBreakdown {
  category: 'Legal' | 'Financial' | 'Technical' | 'Schedule' | 'Scope';
  score: number;
  alert_count: number;
  severity_breakdown: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  impact: number; // Percentage
}

interface CoherenceScoreDetail {
  overall_score: number;
  category_breakdown: CategoryBreakdown[];
  calculated_at: string;
}
```

---

## 3. DISEÑO DE UX/UI

### 3.1 Vista Modal del Desglose

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Coherence Score Breakdown              [X]         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Overall Score: 78 / 100                            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                      │
│  ┌────────────────┐  ┌────────────────┐           │
│  │ Legal      85  │  │ Financial  72  │           │
│  │ 7 alerts       │  │ 12 alerts      │           │
│  │ ■ 1 Critical   │  │ ■ 2 Critical   │           │
│  │ ■ 2 High       │  │ ■ 5 High       │           │
│  │ Impact: 18%    │  │ Impact: 25%    │           │
│  └────────────────┘  └────────────────┘           │
│                                                      │
│  ┌────────────────┐  ┌────────────────┐           │
│  │ Technical  68  │  │ Schedule   92  │           │
│  │ 9 alerts       │  │ 2 alerts       │           │
│  └────────────────┘  └────────────────┘           │
│                                                      │
│  ┌────────────────┐                                │
│  │ Scope      95  │                                │
│  │ 1 alert        │                                │
│  └────────────────┘                                │
│                                                      │
│            [View All Alerts] [Export Report]       │
└─────────────────────────────────────────────────────┘
```

### 3.2 Colores por Categoría

- **Legal**: Blue (#3B82F6)
- **Financial**: Green (#10B981)
- **Technical**: Purple (#8B5CF6)
- **Schedule**: Orange (#F59E0B)
- **Scope**: Cyan (#06B6D4)

---

## 4. PLAN DE IMPLEMENTACIÓN

### Fase 1: Backend - Modelo de Datos
1. Agregar campo `category` a modelo `Alert`
2. Crear modelo `CategoryBreakdown`
3. Extender modelo `CoherenceResult`
4. Actualizar tests unitarios

### Fase 2: Backend - Reglas y Motor
1. Actualizar `initial_rules.yaml` con categorías
2. Modificar motor de coherencia para asignar categorías
3. Actualizar tests de integración

### Fase 3: Backend - Scoring Service
1. Implementar cálculo de score por categoría
2. Implementar cálculo de impacto proporcional
3. Agregar tests de scoring avanzado

### Fase 4: Frontend - Tipos y API
1. Definir tipos TypeScript
2. Crear hook `useCoherenceScore`
3. Actualizar cliente API

### Fase 5: Frontend - Componentes
1. Crear `CategoryBreakdownCard`
2. Crear `CoherenceScoreModal`
3. Modificar `GaugeChart` para ser clickeable

### Fase 6: Integración y Testing
1. Integrar modal en Dashboard
2. Tests end-to-end
3. Ajustes de UX/UI

---

## 5. ESTIMACIÓN DE ESFUERZO

- **Fase 1**: 2-3 horas
- **Fase 2**: 3-4 horas
- **Fase 3**: 2-3 horas
- **Fase 4**: 1-2 horas
- **Fase 5**: 4-5 horas
- **Fase 6**: 2-3 horas

**Total**: ~14-20 horas de desarrollo

---

## 6. CONSIDERACIONES ADICIONALES

### 6.1 Extensibilidad
- El sistema debe permitir agregar nuevas categorías fácilmente
- Considerar categorías customizables por tenant en el futuro

### 6.2 Performance
- El cálculo de category breakdown no debe impactar significativamente el tiempo de respuesta
- Considerar caching si el número de alertas es muy alto

### 6.3 Internacionalización
- Las categorías deben ser traducibles
- Usar constantes para los nombres de categorías

### 6.4 Prioridades Adicionales
- **Alta**: Legal, Financial, Schedule (críticas para el negocio)
- **Media**: Technical (importante pero menos crítica)
- **Baja**: Scope (informativa)

---

## 7. PRÓXIMOS PASOS

1. ✓ Análisis completado
2. Validar con usuario/stakeholder
3. Desglosar en tickets de trabajo
4. Comenzar implementación por fases
