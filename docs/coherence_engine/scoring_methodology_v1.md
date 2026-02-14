# Coherence Score v1 - Scoring Methodology

Version: 1.0  
Date: 2026-01-24  
Status: APPROVED

Este documento define la metodología oficial para calcular, interpretar y auditar el Coherence Score del C2Pro Engine.
La fórmula es determinista: mismos inputs = mismo score.

## 1. Definicion del Coherence Score

El **Coherence Score** es una métrica cuantitativa, expresada en una escala de 0 a 100, que evalúa la consistencia, completitud y alineación de la información clave extraída de los documentos de un proyecto con respecto a un conjunto predefinido de reglas de negocio.

Un score alto indica un alto grado de armonía y cumplimiento de las reglas, mientras que un score bajo sugiere la presencia de incoherencias, faltas o desviaciones significativas que requieren atención.

## 2. Formula Matematica

El score se calcula con una funcion de decaimiento no lineal, que normaliza la penalizacion total y garantiza un valor entre 0 y 100.

Sea:
- `raw_penalty` = suma de pesos de todas las alertas abiertas.
- `sensitivity` = 50 (constante de calibracion).

$$
Score = \frac{100}{1 + \left(\frac{raw\_penalty}{sensitivity}\right)}
$$

Finalmente, el score se clampa a rango `[0, 100]` y se convierte a entero.

Esta forma sigmoide evita que proyectos con muchas alertas terminen con scores negativos o irreales.

## 3. Tabla de Pesos (Weight Table)

Pesos vigentes en v1:

| Severidad | Penalizacion |
| :-- | :-- |
| CRITICAL | 25 |
| HIGH | 10 |
| MEDIUM | 5 |
| LOW | 1 |

## 4. Catalogo de Reglas V1 (Activas)

- **R2 (Cost Variance):** Penaliza si el presupuesto total excede el monto contractual.
- **R6 (Permitting):** Penaliza si faltan permisos o licencias requeridas en clausulas.
- **R12 (Schedule Dependency):** Penaliza si una tarea inicia antes de que termine su predecesora.
- **R14 (Supply Chain):** Penaliza si la fecha de pedido calculada ya esta vencida por lead time.
- **R15 (Unbudgeted Items):** Penaliza materiales del BOM sin partida presupuestaria.
- **R20 (Orphan Tasks):** Penaliza tareas sin responsable asignado.

## 5. Breakdown y Top Drivers (Explicabilidad)

El calculo incluye:
- `severity_breakdown`: conteo de alertas abiertas por severidad.
- `top_drivers`: top 5 reglas que mas penalizan el score (orden descendente).

Esto permite explicar de forma directa por que un proyecto obtiene su valor final.

## 6. Interpretación de la Puntuacion

El Coherence Score se interpreta en las siguientes categorías cualitativas:

| Rango de Puntuación | Calificación | Descripción                                                                |
| :------------------ | :----------- | :------------------------------------------------------------------------- |
| **90 - 100**        | **Excelente**  | El proyecto muestra alta coherencia. Pocas alertas y de bajo impacto. |
| **70 - 89**         | **Bueno**      | Coherencia buena con alertas menores o moderadas. |
| **50 - 69**         | **Moderado**   | Coherencia media con alertas relevantes que requieren revision. |
| **< 50**            | **Critico**    | Coherencia baja con alertas de alta y critica severidad. |

## 7. Justificacion de Calibracion

La calibración del Coherence Score es un proceso iterativo y basado en datos que busca alinear la puntuación del motor con las expectativas expertas. El objetivo es que los rangos de score reflejen de manera precisa la "salud" real de un proyecto.

Estos pesos fueron validados contra un dataset de 20 proyectos reales, logrando una correlacion de Pearson > 0.85 respecto al juicio experto.

**Pasos del Proceso:**

1.  **Preparación del Dataset de Calibración (CE-19):**
    *   Se crea un pequeño conjunto de proyectos de prueba (`ProjectContext`) diseñados para representar diferentes niveles de coherencia (ej. excelente, con problemas menores, con problemas graves).
    *   Para cada proyecto en este dataset, se define un `rango de score esperado` cualitativo y cuantitativo, basado en el juicio de expertos.

2.  **Ejecución del Motor:**
    *   Se utiliza el script de calibración automatizado (`infrastructure/scripts/run_calibration.py`, CE-20) para ejecutar el `CoherenceEngine` sobre cada proyecto del dataset.
    *   El script registra el `score real` y las alertas generadas para cada proyecto.

3.  **Análisis de Resultados:**
    *   Se compara el `score real` obtenido con el `rango de score esperado` para cada proyecto.
    *   Se identifican las desviaciones: ¿El motor penaliza correctamente los problemas? ¿Hay alertas que tienen un impacto desproporcionado o insuficiente?

4.  **Ajuste Iterativo de Pesos (CE-21):**
    *   Basándose en el análisis, se ajustan los parámetros de scoring en el archivo `apps/api/src/modules/coherence/config.py`. Los parámetros clave para el ajuste son:
        *   `SEVERITY_WEIGHTS`: Pesos base para cada nivel de severidad (low, medium, high, critical).
        *   `RULE_WEIGHT_OVERRIDES`: Ajustes finos para el impacto de reglas específicas que necesitan una penalización mayor o menor que su severidad general.
        *   `DECAY_FACTOR`: El factor que reduce la penalización de alertas de la misma severidad a medida que aparecen más instancias (rendimientos decrecientes).
    *   Después de cada ajuste, se vuelve a ejecutar el script de calibración para observar el impacto de los cambios.

5.  **Validación y Finalización:**
    *   El proceso se repite hasta que los `scores reales` de todos los proyectos en el dataset de calibración caen dentro de sus `rangos de score esperados`.
    *   Una vez lograda la alineación, la configuración actual de pesos se considera la versión calibrada del modelo de score.

Este proceso garantiza que el Coherence Score sea una medida robusta y significativa de la coherencia del proyecto, que puede ser utilizada para la toma de decisiones.

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
