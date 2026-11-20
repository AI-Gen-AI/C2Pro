# B1b — Una inferencia real sobre una cláusula EPC pública, validada con N4 v2

**Fecha:** 20/11/2026 · **Estado:** PASS_LIMITED exclusivamente para el ensayo de formato, citas y diagnóstico semántico puntual.  
**NO** es una ejecución de N4 en C2Pro ni de LangExtract, ni prueba un benchmark equivalente de modelos.

## Origen y procedimiento

1. Se extrajo un segmento de aproximadamente 1.000 caracteres de la **§2.5.5 Liquidated Damages for Delay** del contrato EPC Longfellow publicado en SEC, mediante `PDFFileParser` de C2Pro sobre PDF derivado localmente del HTML oficial. El texto completo de la fuente del laboratorio consta de 227.313 caracteres y 22 ventanas N4 planificadas. El segmento está localizado dentro de la **ventana N4 7** del texto importado.
2. Se convocó **una** revisión generativa Gemini mediante AI-GEN Ops (job `2d45f5e3ddaae618b4678d3e014837d1`, SHA de la rama `91a8d421605da25855adf76ce0b907a02ad04f59`) usando exclusivamente ese fragmento público y el esquema propuesto N4 v2. No se usaron archivos privados. El modelo/configuración y el gasto de esta ejecución **no han sido auditados de forma independiente**.
3. La respuesta JSON original se guardó exclusivamente en el PC autorizado. El programa `apps/api/tests/integration/b1b_typed_fact_real_model_response_check.py` la pasó a `parse_n4_typed_fact_candidate_response` y verificó las posiciones devueltas contra la **proyección textual completa** (no el PDF original atestado).
4. Evidencia estadística reproducible sin citas publicadas: [B1B_GEMINI_TYPED_FACT_REAL_MODEL_METRICS.json](evidence/B1B_GEMINI_TYPED_FACT_REAL_MODEL_METRICS.json).

## Datos comprobados

| Indicador | Resultado |
|---|---:|
| Hechos candidatos generados | **5** |
| Citas exactas contra la proyección textual | **5/5** |
| Tipos extraídos | **1 condición, 4 importes** |
| Hecho explícito clasificado como `obligation` | **0** |
| Fuente con obligación de pago literal | **Sí** |
| Referencias externas pendientes | **1**, Tabla C-1 del Anexo C |
| Estado de cobertura | `PARTIAL_OR_REFERENCES_PENDING` |
| N12 | `UNASSESSED` |
| Promociones `trusted` | **0** |

Las cifras propuestas por Gemini corresponden a los importes de penalización por retraso asociados a terminación mecánica, sustancial y final (5.000, 10.000 y 20.000 USD/día) y a un límite acumulado de 800.000 USD. Su **presencia literal en la fuente** se verifica; no se ha comprobado exhaustivamente la interpretación de excepciones, topes, fechas garantizadas, compensación adicional ni jerarquía contractual con anexos.

### Hallazgo de calidad (diagnóstico, no oráculo held-out)
La fuente establece una obligación de pago del contratista condicionada a la llegada del equipo y al incumplimiento de fechas de terminación. Gemini hizo una afirmación sobre ese deber dentro de un elemento `condition`, pero **no emitió una obligación individual de tipo `obligation`**. La prueba demuestra que **citas 5/5 ≠ cobertura correcta de tipos de hechos**. No implica ausencia total del concepto de obligación en la respuesta.

El PDF original no es un PDF firmado de referencia y no se ha producido atestación de foliatura. La Tabla C-1 del Anexo C se señala como **no examinada**; no hay base para aceptar un plazo contractual desde esa referencia. No se pudo medir precio por ejecución, rendimiento por 100 páginas ni recall del contrato completo.

## Decisión de integración

- **Conservar N4 actual como motor único**. N4 v2 es exclusivamente un **esquema experimental de respuesta**, aún sin conexión al provider/runner ni N12.
- **No integrar LangExtract por ahora** basándose en cuatro coincidencias literales; N4 y LangExtract estricto alcanzaron 4/4 y el modo aproximado requirió desambiguación de literalidad.
- La siguiente evaluación debe ser de **mismo proveedor/modelo y corpus, coste acotado, cláusulas held-out y oráculo independiente**, y medir explícitamente obligaciones vs condiciones vs importes vs riesgos, además de falsos positivos y anexos faltantes.
- No se modificaron PR #1276, producción, UI, HITL, ProjectGraph ni Coherence Score.

**Dictamen global B1:** el contrato tipado N4 v2 es invocable como validador y ya superó 8/8 unit tests sintéticos; una salida real de Gemini fue procesada y las cinco citas se anclaron. **La comprensión contractual completa sigue NO VALIDADA.**
