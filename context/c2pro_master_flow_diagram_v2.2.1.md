# C2Pro - Diagrama de Flujo Maestro v2.2.1
## Fecha: 2026-01-31

---

## Changelog v2.2 → v2.2.1

### 🆕 Nuevas Funcionalidades

| ID | Cambio | Descripción | Impacto |
|----|--------|-------------|---------|
| NEW-001 | **6 Categorías de Coherence Score** | SCOPE, BUDGET, QUALITY, TECHNICAL, LEGAL, TIME | Mayor granularidad en análisis |
| NEW-002 | **Sub-scores por categoría** | Cada categoría genera score independiente (0-100%) | Drill-down analytics |
| NEW-003 | **Pesos configurables** | Ponderación ajustable por tipo de proyecto | Flexibilidad por cliente |
| NEW-004 | **WBS → Procurement Integration** | WBS Manager alimenta directamente a BOM Builder | Trazabilidad mejorada |
| NEW-005 | **Lead Time Calculator** | Nuevo componente en Procurement | Planificación de compras |

### 🔧 Correcciones de Sintaxis

| ID | Corrección | Detalle |
|----|------------|---------|
| FIX-001 | Subgraphs anidados | Corregida estructura de COHERENCE_CATEGORIES |
| FIX-002 | Duplicación de nodos | Eliminados nodos ENTRY duplicados |
| FIX-003 | Capitalización | Corregido "Subgraph" → "subgraph" |
| FIX-004 | Frontend consolidado | Una sola sección ENTRY con todas las vistas |

---

## 🎯 Coherence Score v2 - Sistema de 6 Categorías

### Arquitectura del Score

```
┌─────────────────────────────────────────────────────────────────┐
│                    COHERENCE ENGINE v2                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │🎯 SCOPE  │  │💰 BUDGET │  │✅ QUALITY│                      │
│  │   80%    │  │   62%    │  │   85%    │                      │
│  │ Alcance  │  │ Costos   │  │Estándares│                      │
│  │vs Contrato│ │vs Budget │  │          │                      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                      │
│       │             │             │                             │
│  ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐                      │
│  │⚙️TECHNICAL│ │⚖️ LEGAL  │  │⏱️ TIME   │                      │
│  │   72%    │  │   90%    │  │   75%    │                      │
│  │Ingeniería│  │Cláusulas │  │Cronograma│                      │
│  │  Specs   │  │Compliance│  │  Hitos   │                      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                      │
│       │             │             │                             │
│       └─────────────┼─────────────┘                             │
│                     │                                           │
│              ┌──────┴──────┐                                    │
│              │⚖️ PESOS     │                                    │
│              │CONFIGURABLES│                                    │
│              └──────┬──────┘                                    │
│                     │                                           │
│              ┌──────┴──────┐                                    │
│              │🎯 GLOBAL    │                                    │
│              │  78/100     │                                    │
│              └─────────────┘                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Definición de Categorías

| Categoría | Código | Descripción | Reglas Asociadas | Peso Default |
|-----------|--------|-------------|------------------|--------------|
| **SCOPE** | 🎯 | Alcance definido vs Contrato | R11, R12, R13 | 20% |
| **BUDGET** | 💰 | Costos vs Presupuesto aprobado | R6, R15, R16 | 20% |
| **QUALITY** | ✅ | Cumplimiento de estándares | R17, R18 | 15% |
| **TECHNICAL** | ⚙️ | Coherencia ingeniería/specs | R3, R4, R7 | 15% |
| **LEGAL** | ⚖️ | Cláusulas y compliance | R1, R8, R20 | 15% |
| **TIME** | ⏱️ | Cronograma vs hitos contractuales | R2, R5, R14 | 15% |

### Mapeo de Reglas por Categoría

```yaml
coherence_rules_v2:
  SCOPE:
    - R11: "WBS sin actividades vinculadas"
    - R12: "WBS sin partidas asignadas"
    - R13: "Alcance no cubierto por WBS"
    
  BUDGET:
    - R6: "Suma partidas ≠ precio contrato (±5%)"
    - R15: "BOM sin partida presupuestaria"
    - R16: "Desviación presupuestaria >10%"
    
  QUALITY:
    - R17: "Especificación sin estándar definido"
    - R18: "Material sin certificación requerida"
    
  TECHNICAL:
    - R3: "Especificación contradictoria"
    - R4: "Requisito técnico sin responsable"
    - R7: "Dependencia técnica no resuelta"
    
  LEGAL:
    - R1: "Plazo contrato ≠ fecha fin cronograma"
    - R8: "Cláusula de penalización sin hito"
    - R20: "Aprobador contractual no identificado"
    
  TIME:
    - R2: "Hito sin actividad en cronograma"
    - R5: "Cronograma excede plazo contractual"
    - R14: "Material crítico con fecha pedido tardía"
```

### Fórmula de Cálculo

```python
def calculate_coherence_score_v2(
    alerts: list[Alert],
    weights: CategoryWeights,
    context: ProjectContext
) -> CoherenceResult:
    """
    Coherence Score v2 con 6 categorías.
    """
    # 1. Agrupar alertas por categoría
    alerts_by_category = group_by_category(alerts)
    
    # 2. Calcular sub-score por categoría
    sub_scores = {}
    for category in CATEGORIES:
        category_alerts = alerts_by_category.get(category, [])
        sub_scores[category] = calculate_category_score(
            category_alerts, 
            context
        )
    
    # 3. Aplicar pesos configurables
    weighted_sum = sum(
        sub_scores[cat] * weights[cat] 
        for cat in CATEGORIES
    )
    
    # 4. Normalizar a 0-100
    global_score = int(weighted_sum * 100)
    
    return CoherenceResult(
        global_score=global_score,
        sub_scores=sub_scores,
        weights_used=weights,
        breakdown_by_category=alerts_by_category,
        methodology_version="2.0"
    )

# Pesos por defecto
DEFAULT_WEIGHTS = {
    "SCOPE": 0.20,
    "BUDGET": 0.20,
    "QUALITY": 0.15,
    "TECHNICAL": 0.15,
    "LEGAL": 0.15,
    "TIME": 0.15
}
```

### UI: Vista de Coherence Score

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 COHERENCE DASHBOARD - Proyecto: Torre Skyline              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│     🎯 GLOBAL SCORE                                             │
│     ┌─────────────────┐                                         │
│     │      78/100     │  ████████████████████░░░░░░             │
│     │   "Aceptable"   │                                         │
│     └─────────────────┘                                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  BREAKDOWN POR CATEGORÍA                                        │
│                                                                 │
│  🎯 SCOPE      ████████████████████░░░░  80%  ✓ Bueno          │
│  💰 BUDGET     ████████████░░░░░░░░░░░░  62%  ⚠ Atención       │
│  ✅ QUALITY    █████████████████████░░░  85%  ✓ Bueno          │
│  ⚙️ TECHNICAL  ██████████████░░░░░░░░░░  72%  ⚠ Atención       │
│  ⚖️ LEGAL      ██████████████████████░░  90%  ✓ Excelente      │
│  ⏱️ TIME       ███████████████░░░░░░░░░  75%  ⚠ Atención       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [Ver Alertas por Categoría]  [Ajustar Pesos]  [Exportar PDF]  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛒 Procurement - Integración con WBS

### Flujo Mejorado

```
┌─────────────────┐
│  MOD_PROJECTS   │
│                 │
│  WBS Generator  │
│       │         │
│       ▼         │
│  WBS Manager    │──────────┐
│  (4 niveles)    │          │
└─────────────────┘          │
                             │ WBS Items
                             │ (IDs + Estructura)
                             │
                             ▼
┌─────────────────────────────────────────────┐
│             MOD_PROCUREMENT                  │
│                                             │
│  ┌─────────────┐                           │
│  │ BOM Builder │◄──── WBS Items            │
│  │    Agent    │      + Specs              │
│  └──────┬──────┘                           │
│         │                                   │
│         ▼                                   │
│  ┌─────────────┐                           │
│  │BOM Analyzer │                           │
│  │(+ Incoterms)│                           │
│  └──────┬──────┘                           │
│         │                                   │
│         ▼                                   │
│  ┌─────────────┐                           │
│  │ Lead Time   │◄──── Supplier Data        │
│  │ Calculator  │      + Transit Times      │
│  └──────┬──────┘                           │
│         │                                   │
│         ▼                                   │
│  ┌─────────────┐                           │
│  │ Procurement │                           │
│  │Plan Generator│──────► optimal_order_date│
│  └─────────────┘                           │
│                                             │
└─────────────────────────────────────────────┘
```

### Lead Time Calculator

```python
class LeadTimeCalculator:
    """
    Calcula fechas óptimas de pedido basado en:
    - WBS item required_date
    - Supplier production_time
    - Transit time (basado en Incoterm + origin)
    - Customs clearance (si aplica)
    - Buffer configurable
    """
    
    def calculate_optimal_order_date(
        self,
        bom_item: BOMItem,
        wbs_item: WBSItem
    ) -> date:
        required_on_site = wbs_item.start_date - timedelta(days=bom_item.buffer_days)
        
        total_lead_time = (
            bom_item.production_time_days +
            bom_item.transit_time_days +
            bom_item.customs_clearance_days +
            bom_item.buffer_days
        )
        
        optimal_order_date = required_on_site - timedelta(days=total_lead_time)
        
        return optimal_order_date
```

---

## Resumen de Componentes v2.2.1

### Módulos (6)

| Módulo | Estado | Cambios v2.2.1 |
|--------|--------|----------------|
| Documents | ✅ | Sin cambios |
| Stakeholders | ✅ | Sin cambios |
| Projects | ✅ | WBS → Procurement link |
| Procurement | ✅ | + Lead Time Calculator |
| Analysis | ✅ | Sin cambios |
| **Coherence** | ✅ | **6 Categorías + Sub-scores** |

### CTO Gates (8/8 ✅)

Todas las gates siguen cumplidas. La adición de categorías **mejora** Gate 5 (Coherence Score Formal).

### Impacto en Base de Datos

```sql
-- Actualización tabla coherence_scores
ALTER TABLE coherence_scores ADD COLUMN IF NOT EXISTS
    sub_scores JSONB DEFAULT '{}';
    
-- Estructura del JSONB sub_scores:
-- {
--   "SCOPE": 80,
--   "BUDGET": 62,
--   "QUALITY": 85,
--   "TECHNICAL": 72,
--   "LEGAL": 90,
--   "TIME": 75,
--   "weights_used": {
--     "SCOPE": 0.20,
--     "BUDGET": 0.20,
--     ...
--   }
-- }

-- Índice para queries por categoría
CREATE INDEX idx_coherence_subscores ON coherence_scores 
    USING GIN (sub_scores);
```

---

## Archivos Generados

| Archivo | Descripción |
|---------|-------------|
| `c2pro_master_flow_v2.2.1.mermaid` | Diagrama corregido con 6 categorías |
| `c2pro_master_flow_diagram_v2.2.1.md` | Esta documentación |

---

**Versión:** 2.2.1  
**Fecha:** 2026-01-31  
**Estado:** FINAL - Aprobado por Product Owner
