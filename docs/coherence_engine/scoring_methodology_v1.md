# Metodología de Scoring y Calibración del Coherence Engine v1

Este documento define la metodología para comprender, interpretar y calibrar el Coherence Score generado por el C2Pro Engine.

## 1. Definición del Coherence Score

El **Coherence Score** es una métrica cuantitativa, expresada en una escala de 0 a 100, que evalúa la consistencia, completitud y alineación de la información clave extraída de los documentos de un proyecto con respecto a un conjunto predefinido de reglas de negocio.

Un score alto indica un alto grado de armonía y cumplimiento de las reglas, mientras que un score bajo sugiere la presencia de incoherencias, faltas o desviaciones significativas que requieren atención.

## 2. Interpretación de la Puntuación

El Coherence Score se interpreta en las siguientes categorías cualitativas:

| Rango de Puntuación | Calificación | Descripción                                                                |
| :------------------ | :----------- | :------------------------------------------------------------------------- |
| **90 - 100**        | **Excelente**  | El proyecto muestra una alta coherencia. Pocas o ninguna alerta, todas de baja severidad. El riesgo de inconsistencia es mínimo. |
| **70 - 89**         | **Bueno**      | El proyecto presenta buena coherencia con alertas menores. Pueden existir algunas alertas de severidad baja o media que no comprometen la integridad general. Riesgo bajo a moderado. |
| **50 - 69**         | **Moderado**   | El proyecto tiene coherencia moderada con alertas significativas. Hay presencia de alertas de severidad media y/o alta, indicando inconsistencias que requieren revisión. Riesgo moderado a alto. |
| **< 50**            | **Crítico**    | La coherencia del proyecto es baja. Predominan alertas de alta y crítica severidad, revelando problemas estructurales o múltiples inconsistencias graves. Riesgo alto. |

## 3. Proceso de Calibración del Score

La calibración del Coherence Score es un proceso iterativo y basado en datos que busca alinear la puntuación del motor con las expectativas expertas. El objetivo es que los rangos de score reflejen de manera precisa la "salud" real de un proyecto.

**Pasos del Proceso:**

1.  **Preparación del Dataset de Calibración (CE-19):**
    *   Se crea un pequeño conjunto de proyectos de prueba (`ProjectContext`) diseñados para representar diferentes niveles de coherencia (ej. excelente, con problemas menores, con problemas graves).
    *   Para cada proyecto en este dataset, se define un `rango de score esperado` cualitativo y cuantitativo, basado en el juicio de expertos.

2.  **Ejecución del Motor:**
    *   Se utiliza el script de calibración automatizado (`scripts/run_calibration.py`, CE-20) para ejecutar el `CoherenceEngine` sobre cada proyecto del dataset.
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
