# ADR-009: Coherence Score v2 — Evidence-Aware, Explainable, Bottom-Up

**Status:** Accepted  
**Date:** 2026-05-24  
**Deciders:** Jesús Camacho (VP Engineering / Strategic Procurement Director)  
**Sprint context:** S2 (Coherence Engine, 65% en curso)  
**Supersedes:** Coherence Score v1 methodology (scoring_methodology_v1.md, sprint P2-01)  
**Related:** ADR-007 (Clauses as separate entity), CTO Gate 4 (Legal Traceability), CTO Gate 5 (Coherence Score Formal)

## 1. Contexto

Tras el sprint P2-01 se entregó la primera versión funcional del Coherence Score, con:

- Framework RuleEvaluator + Rule Registry desacoplado del motor.
- Reglas deterministas R1 (BudgetOverrunEvaluator) y R5 (ScheduleDelayEvaluator).
- ScoringService calibrado con dataset de proyectos excellent / minor_issues / major_issues.
- Gate 5 marcado como PARTIAL.

Una auditoría posterior del pipeline activo identificó tres defectos sistémicos que impiden cerrar Gate 5 y bloquean el rollout enterprise:

1. **Cobertura y coherencia mezcladas en un solo número.** `ScoringService._calculate_detailed_with_coverage()` calcula `global_score = mean_assessed * coverage_ratio`. Una categoría sin evidencia deprime artificialmente el score global, en lugar de reportarse como dimensión no evaluada.
2. **El score 0 no diferencia “ausencia de evidencia” de “incoherencia crítica”.** `CoherenceRulesEngine.evaluate()` no tiene state machine; `ScoreCalculator.calculate()` usa `category_scores.get(category, 100)` como default, que confunde “no evaluado” con “perfecto”.
3. **Frontend colapsa unknown a cero.** `DashboardClient.tsx` usa `data.coherence_score ?? 0`, lo que renderiza visualmente como “fracaso” lo que es en realidad “evidencia pendiente”.

Adicionalmente, no existe contrato estructurado para evidencia, conflictos cross-document, ni recálculo longitudinal explicable cuando el usuario sube documentos incrementalmente.

## 2. Decisión

Se adopta **Coherence Score v2**, una arquitectura **evidence-aware, explainable y bottom-up** con las siguientes propiedades centrales:

### 2.1 Invariante crítica

> **La ausencia de evidencia NUNCA genera score = 0.**
>
> Si no hay evidencia suficiente para evaluar una dimensión, el score es null y el status refleja rigurosamente el motivo.

### 2.2 Modelo de categorías canónico (seis dimensiones)

Las categorías oficiales del producto son:

| Categoría | Evidencia mínima | Justificación |
|---|---|---|
| **SCOPE** | 2 | Contrato + WBS |
| **BUDGET** | 3 | Contrato + presupuesto + BOM o cashflow |
| **QUALITY** | 2 | Especificación + certificación/HSE |
| **TECHNICAL** | 2 | Especificación + BOM |
| **LEGAL** | 1 | Contrato |
| **TIME** | 2 | Contrato (fechas) + cronograma |

### 2.3 State machine por categoría

Cada categoría tiene un status asignado dinámicamente:

- `scored`: Evaluable y calculada con éxito.
- `insufficient_evidence`: Aplicable pero por debajo del umbral mínimo de documentos requeridos.
- `not_applicable`: Fuera del alcance explícito del proyecto según su contexto.
- `conflicting_evidence`: Contradicciones cross-document insalvables detectadas.
- `error`: Fallo técnico en el procesamiento o extracción de la evidencia.
- `pending_documents`: Estado operacional temporal durante cargas progresivas de archivos.

### 2.4 Semántica del score numérico

- El campo score es estrictamente **nullable**.
- `score = 0` o valores fuertemente penalizados son válidos **únicamente** cuando se cumple una de las siguientes condiciones:
  1. `status == scored` y las penalizaciones cuantitativas de las reglas consumen el total de la puntuación.
  2. `status == conflicting_evidence`, donde la existencia de contradicciones probadas destruye la coherencia de la dimensión.
- Si el status es de ausencia de datos (`insufficient_evidence`, `not_applicable`, `pending_documents`), el score **DEBE** ser `null`.

### 2.5 Triple-axis por categoría

Cada categoría reporta tres ejes independientes e independientes entre sí:

1. **Coherence** (0–100, nullable)
2. **Evidence Coverage** (0–1)
3. **Confidence** (0–1)

### 2.6 Dual-score global

- **Coherence Score™:** Media ponderada calculada sobre las categorías activas que están aportando datos reales al ecosistema del proyecto (categorías en estado `scored` o `conflicting_evidence`).
- **Completeness Score™:** Ratio de cobertura ponderado sobre todas las categorías que aplican al proyecto (excluye `not_applicable`).
- **Confidence Index:** Media ponderada de la confianza técnica sobre las categorías evaluadas.

Los pesos `w_i` iniciales son **equipesados (1/6 cada categoría)** para el lanzamiento inicial.

### 2.7 Flujo arquitectónico

El sistema es **estrictamente bottom-up** para asegurar la trazabilidad legal:

```text
Documents
   ↓ (extracción + quality gates)
Evidence (por categoría)
   ↓
RuleEvaluators (R1-R20, preservados del sprint P2-01)
   ↓
Rule Signals
   ↓
Category Aggregator (NUEVO - Inyecta lógica de estados y penalización por conflicto)
   ↓ (status + score nullable + coverage + confidence)
Per-Category Output
   ↓
Aggregation Service (NUEVO - Consolida el ecosistema global)
   ↓
Global Coherence + Completeness + Confidence
```

**Los RuleEvaluators existentes se preservan.** El Category Aggregator consume sus señales sin modificarlas ni sustituirlas.

### 2.8 UI: Presentación top-down sobre cálculo bottom-up

El cálculo es bottom-up por trazabilidad (Gate 4), pero la UI presentará primero el score global correlacionado inmediatamente con su nivel de completitud para evitar interpretaciones erróneas en proyectos con carga parcial de archivos.

**Regla obligatoria de UI:** Cuando `coherence_score` es `null`, el frontend NUNCA renderizará un fallback a `0/100`. Mostrará un estado vacío (*empty state*) con el texto literal “Pending evidence” y un CTA explícito de “Upload missing documents”.

## 3. Modelo matemático

### 3.1 Ecuaciones globales

Sea `C_scored` el conjunto de categorías con `status == scored`.  
Sea `C_conflict` el conjunto de categorías con `status == conflicting_evidence`.  
Definimos el conjunto de categorías con evaluación activa como `C = C_scored ∪ C_conflict`.  
Sea `A` el conjunto de todas las categorías aplicables del proyecto (excluyendo `not_applicable`).

### 3.2 Reglas de cálculo e impacto por conflicto

- Si `|C| = 0`: `CoherenceScore = null` y `score_reason = "insufficient_evidence"`.
- **Nunca** se multiplicará la coherencia global por el ratio de cobertura (evitando penalizar lo desconocido).
- Para modelar el impacto de las contradicciones sin ocultar el riesgo del proyecto, toda categoría `i ∈ C_conflict` participará obligatoriamente en el score global aplicando una penalización determinista sobre su puntuación individual `s_i`.

> Esto garantiza que los fallos graves de coherencia cross-document depriman el score global con justificación analítica, distinguiéndose limpiamente de la falta de datos.

### 3.3 Modelos diferidos y roadmap evolutivo

Para mitigar riesgos y estabilizar el pipeline cuantitativo en el Sprint S2, se define el siguiente ciclo de adopción para modelos complejos:

1. **Fuzzy Logic (Lógica Difusa):** Descartado definitivamente. Se sustituye por clasificación vía LLM (Structured Outputs) + RuleEvaluators deterministas.
2. **Pesos tenant-adaptativos:** Promovido a backlog de alta prioridad para Fase 2 (Post-rollout) como requerimiento clave de personalización B2B.
3. **Graph-native scoring y Estimación Bayesiana:** Retenidos en fase de investigación (R&D) hasta recolectar métricas estables del shadow-mode.
4. **Regresión calibrada con outcomes:** En espera (*Hold*) a largo plazo, supeditado a la compartición de datos históricos de ejecución real por parte de clientes piloto.

## 4. Taxonomía de alertas

### 4.1 Códigos

- `missing_evidence`
- `low_confidence`
- `conflicting_evidence`
- `critical_incoherence`
- `processing_error`
- `data_quality_issue`

### 4.2 Severidades

- `info`: Incompletitud estándar y esperada (fases tempranas de carga).
- `warning`: Confianza baja o cobertura parcial en dimensiones no críticas.
- `high`: Conflictos semánticos fuertes que requieren revisión humana inmediata.
- `critical`: Incoherencias críticas validadas con alta certeza algorítmica.

### 4.3 Reglas de emisión

- Un conflicto crítico (`conflicts.severity == "critical"`) emite una alerta de nivel `critical` indexada a la categoría. No oculta el problema; lo parametriza.
- Los problemas de `missing_evidence` se representarán visualmente con colores de advertencia neutros/asistenciales (ámbar/azul), prohibiendo el uso del color rojo de error.

## 5. Contrato JSON v2

```json
{
  "project_id": "string",
  "version": "coherence-v2",
  "generated_at": "ISO-8601",
  "global": {
    "coherence_score": 78.4,
    "completeness_score": 0.61,
    "confidence_index": 0.73,
    "status": "partial",
    "score_reason": "scored_categories_only",
    "scored_categories": 4,
    "applicable_categories": 6
  },
  "categories": [
    {
      "category": "BUDGET",
      "status": "insufficient_evidence",
      "score": null,
      "confidence": 0.22,
      "coverage": 0.15,
      "evidence_count": 1,
      "evidence_references": [
        {"document_id": "doc_123", "page": 4, "span_id": "sp_9"}
      ],
      "rationale": "No structured financial tables detected.",
      "detected_conflicts": [],
      "missing_evidence": ["bill_of_quantities", "cost_breakdown", "cashflow"],
      "alerts": [
        {"code": "MISSING_BUDGET_EVIDENCE", "severity": "warning", "confidence": 0.93}
      ],
      "recommendation": "Upload budget workbook or BOQ.",
      "calculation_metadata": {
        "weight": 0.1667,
        "min_evidence_threshold": 3,
        "evaluated_rules": [],
        "model_version": "coh-v2.0.0"
      }
    }
  ]
}
```

## 6. Pseudocódigo del Category Aggregator

```python
for category in CATEGORIES:  # SCOPE, BUDGET, QUALITY, TECHNICAL, LEGAL, TIME
    evidence = evidence_service.collect(category, project_docs)
    applicability = applicability_service.check(category, project_context)

    if not applicability.is_applicable:
        emit(category, status="not_applicable", score=None)
        continue

    if evidence.count < thresholds[category]:
        emit(category, status="insufficient_evidence", score=None)
        alert_service.emit("MISSING_EVIDENCE", severity="warning",
                           category=category, missing=evidence.missing_required)
        continue

    conflicts = conflict_service.detect(category, evidence)
    if conflicts.hard_conflict:
        # Penalización determinista calculada según el refinamiento matemático v2
        score_penalty = 0 if conflicts.severity == "critical" else 30
        emit(category, status="conflicting_evidence", score=score_penalty,
             confidence=evidence.avg_confidence, coverage=evidence.coverage)

        if conflicts.severity == "critical":
            alert_service.emit("CRITICAL_CONFLICT", severity="critical",
                               category=category, conflict_set=conflicts.set)
        continue

    # Consumir las señales de los RuleEvaluators existentes (R1-R20) del sprint P2-01
    rule_signals = rule_registry.evaluate_for_category(category, evidence)
    score, confidence = category_aggregator.score(category, rule_signals, evidence)

    emit(category, status="scored", score=score, confidence=confidence,
         coverage=evidence.coverage, evidence_count=evidence.count)
```

## 7. Plan de migración

### 7.1 Módulos afectados

- `apps/api/src/coherence/scoring.py`
- `apps/api/src/coherence/domain/rules_engine.py`
- `apps/api/src/coherence/application/use_cases/calculate_coherence.py`
- `apps/api/src/coherence/application/dtos/coherence_dtos.py`
- `apps/api/src/core/tasks/ingestion_tasks.py`
- `apps/web/components/coherence/DashboardClient.tsx`

### 7.2 Estrategia (shadow-mode obligatorio)

1. Añadir DTOs y tablas v2 con adapters retrocompatibles.
2. Crear migración de Alembic para evolución de la columna `analyses.coherence_breakdown` JSONB junto con el script de backfill correspondiente.
3. Implementar adapter `v1 -> v2` para blindar la compatibilidad de la API pública en producción.
4. Activar la Feature Flag `coherence_v2_enabled` (por defecto en `off`).
5. Ejecución dual en producción (*Shadow Mode*) durante 2–3 semanas calendario.
6. Monitorear y comparar distribuciones frente al calibration_dataset.
7. Conmutar el frontend de forma definitiva tras la validación empírica de datos en el shadow-mode.

### 7.3 Estimación de esfuerzo

| Componente | Esfuerzo |
|---|---|
| Backend: Evidence Service + Category Aggregator + State Machine | 1.0 Sprint |
| Alembic migration + v1 -> v2 Adapter | 0.5 Sprint |
| Shadow-mode + Dual-run + Telemetría de consistencia | 2–3 Semanas (en paralelo) |
| Frontend: Null-state UI + Status badges + Tri-panel metrics | 0.5 Sprint |
| Tests avanzados (Unitarios + Integración + Golden Corpus) | 0.5 Sprint |

**Total estimado:** 2 Sprints completos de ingeniería + periodo de estabilización en Shadow Mode.

## 8. Plan de testing

### 8.1 Unit tests

- Aislamiento de transiciones de estado (`insufficient_evidence` nunca debe computar numéricamente).
- Control de fronteras (*guardrails*) de penalización por conflicto.

### 8.2 Integration tests

- Simulación de carga secuencial de documentos para verificar la consistencia longitudinal de la máquina de estados.
- Inyección de OCR degradado para validar la resistencia del `ConfidenceIndex`.

### 8.3 Métricas de control en Shadow Mode

- Se define una salvaguarda de regresión automatizada: si el *Mean Absolute Error (MAE)* entre las curvas de distribución de la v1 y v2 en proyectos validados como excelentes supera los 15 puntos, se bloqueará automáticamente el despliegue del flag.

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Complejidad de lectura UX debido al incremento de estados y variables. | Implementación obligatoria de tooltips explicativos y glosario contextual integrado de forma nativa en el dashboard. |
| Confusión entre "Confianza técnica" y "Verdad absoluta". | Documentación explícita aclarando que el eje de confianza mide la integridad de la extracción, no la validez jurídica de la cláusula. |
| Sobrecosto de tokens o tiempo de ejecución en el conflict_service. | Restringir el alcance del MVP en Fase 1 a reglas lógicas e índices cruzados deterministas, abstrayendo la inferencia costosa a fases posteriores. |

## 10. Razones de la decisión

1. **Cierra de forma robusta Gate 5 Formal.** Al aislar la cobertura del análisis puro de consistencia, el modelo cumple las condiciones de auditoría técnica necesarias.
2. **Preserva el trabajo del sprint P2-01.** No destruye código útil; encapsula las reglas atómicas existentes (R1-R20) dentro de un orquestador inteligente de categorías.
3. **Soporte nativo para flujos de trabajo reales.** Los contratos empresariales se cargan de forma asíncrona por diferentes equipos. Diseñar el sistema pensando en estados intermedios protege la experiencia del usuario y evita falsos negativos.

## 11. Consecuencias

### 11.1 Positivas

- Trazabilidad total punta a punta (*Documento -> Cláusula -> Métrica Global*), cumpliendo satisfactoriamente con el objetivo de auditoría del producto.
- Contrato claro, limpio y acotado para los desarrolladores frontend.

### 11.2 Negativas o que requieren atención

- Requiere un esfuerzo de sincronización UI/UX inmediato para implementar los componentes visuales del estado nulo de manera unificada.
- Demanda un proceso riguroso de actualización en la documentación interna y en las notas del próximo lanzamiento al mercado.

## 12. Decisiones explícitamente rechazadas

- **Top-down scoring:** Rechazado para evitar la pérdida de trazabilidad interna y asegurar el correcto funcionamiento de los validadores de reglas atómicas.
- **Colapsar Coherence + Completeness:** Rechazado unánimemente por ser el origen exacto de los sesgos algorítmicos identificados en la primera versión.

## 13. Referencias

- Sprint P2-01: `scoring_methodology_v1.md`
- ROADMAP v2.4.0 §12: Coherence Score Specification
- CTO Gates 1–4: VALIDATED en staging (Supabase eu-north-1)
- `calibration_dataset.example.json`: Baseline empírico v1

**Fin del documento ADR-009.**
