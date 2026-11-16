# C2Pro V4 — Análisis crítico del dictamen de Claude y propuesta de decisión
**Fecha:** 2026-11-16
**Estado:** revisión terminada; recomendación para decisión de propietario, SIN GO de ejecución.
**Fuentes:** plan C2PRO_V4_AGENTIC_INTELLIGENCE_REVIEW_20261116; dictamen CLAUDE_SONNET_ARCHITECTURE_VERDICT_20261116; código PR #1234 y workflow/nodes en la rama experimental.

## 1. Evaluación
Acepto el veredicto **GO condicionado para MVP estrecho**. La revisión encontró defectos plausibles que deben aclararse antes del rediseño total:
- N3 produce `insufficient_extractable_text`, pero el conditional map de `workflow.py` no contiene ese valor. Ruta a error probable; test real necesario.
- N12 puede regresar a N4: el código concatena crítica/feedback al documento completo y lo vuelve a enviar. Gran riesgo de tokens/repetición.
- La verificación literal pre-HITL está implementada como caso especial para `technical_spec`, pero N15 general corre después de HITL. Riesgos contractuales merecen verificación antes de presentar candidato al humano.
- `risks=[]` resulta ambiguo entre 0 riesgos reales, normalización vacía y extracción incompleta: exigir status + cobertura y distinguir fallos.
- PR #1234 transporta solo respuesta textual/JSON, sin tools; OpenAI y Gemini tienen configuraciones de formato diferentes y no fijan límites explícitos del esfuerzo de razonamiento. Medir antes de atribuir fallos a capacidad de GPT/Gemini.
- Coste: preflight por request no protege la ejecución, documento ni tenant frente a continuaciones caras.
- N3 rutea solo a un extractor: no basta con convertir las salidas del router en lista, habría que ajustar fan-out/fan-in y reducers para no ejecutar N12 varias veces.

## 2. Matices y correcciones a Claude
1. **N15:** no mover ciegamente toda la topología; considerar extraer el servicio de validación y ejecutarlo antes del HITL en todos los documentos, manteniendo revalidación después de correcciones humanas. El caso pre-HITL de especificaciones ya existe.
2. **N12:** la regla propuesta de `0 llamadas si cobertura completa` no garantiza descubrir falsos negativos. Cobertura es una condición necesaria, no evidencia de detección exhaustiva; para fuentes complejas o alto riesgo, muestreo/adversarial o evaluación crítica semántica independiente focalizada.
3. **Ventanas antes de tools:** acepto `ventanas + ledger` como MVP rentable y agnóstico del proveedor, pero no como objetivo final obligatorio; si falla el razonamiento cross-window o los anexos, incorporar herramientas de consulta/adquisición de contexto focalizadas, no decenas de agentes.
4. **Datos provisionales y ProjectGraph:** no esperaría necesariamente aprobación humana para *mostrar* relaciones provisionales, siempre que estén claramente segregadas de relaciones confiables y no entren en el score validado ni alteren estado canónico. El dictamen «Tier-2 consume ledger tras HITL» es demasiado restrictivo si se entiende literalmente.
5. **Requisitos de producto:** preservar desde diseño los tres modos UI aprobados — Rápido/Completo/Auditoría — sin afirmar que están listos hasta disponer de benchmark y semántica de cobertura. Modo Rápido siempre preliminar, no «sin riesgos».
6. **Benchmark:** 4 cláusulas SolarMax sirven como caso inicial adversarial, no validación estadística. Crear gold con expertos, casos multidisciplinares e inclusión de documentos sin riesgos, textos corruptos, anexos faltantes y diversas metodologías.
7. **Presupuesto de reasoning:** la ausencia de configuración explícita es una hipótesis causal plausible, pero en la prueba GPT concisa reportada había 727 tokens de razonamiento de 6000 de salida; la inflación de salida por estructura de diez campos también sigue siendo causa posible. No prometer que ajustar effort resuelve el FAIL.
8. **Cobertura propia de revisión:** Claude no examinó schema.py, ADR-014/017 ni módulos HITL completos, por lo que algunos juicios no son auditoría exhaustiva. Hay que revisar antes de cambios de datos; no declarar gate superado.

## 3. Propuesta revisada de orden de implementación (si GO)
**F0 — medir y fijar baseline:** mapa N1-N17/ProjectGraph, PII y estados, consumo LLM real por nodo, benchmark gold inicial y definición precisa de resultados válidos. Ningún cambio al piloto.
**PR A — robustez sin ampliar arquitectura:** test/fix N3 texto insuficiente; estado N4 de extracción completa/parcial/ausente; cita pre-HITL por servicio reutilizable para contratos y revisiones; no alterar score por aceptaciones.
**PR B — comparabilidad proveedor:** homogeneizar contrato de respuesta y settings de reasoning, instrumentar hidden tokens y costes completos; repetir GPT/Gemini/Claude con mismo contexto/schema/hashes.
**PR C — MVP incremental N4:** inventario de secciones, ledger de candidatos y cobertura, ventanas + excepción contextual, CAS/idempotencia, reinicio sin duplicación, limitador presupuesto multinivel, mapeo de citas al original. Feature flag OFF en pilot.
**PR D — crítica focal y calidad:** N12 no repetir documento completo salvo justificación; evaluación independiente para omisiones críticas; métricas de coste y calidad; no convertir PARTIAL en GO.
**PR E — extensión a N3 multifunción, N5/N9, requisitos técnicos y Tier-2 ProjectGraph:** solo cuando MVP y contratos hayan sido validados. Mantener el objetivo común multi-vertical sin imponer WBS/BOQ.
**PR F — 3 modos UI y Complete Journey:** Rápido/preliminar, Completo/default, Auditoría/revisión reforzada; panel validado/provisional y HITL humano. Se coordina con #1229 y #1049 sin duplicar trabajo.

## 4. Gates de evaluación
- 100% citas aceptadas son literales y resolubles en revisión original; la interpretación se valida aparte.
- 100% unidades de fuente disponible con cobertura declarada, y fuentes ausentes identificadas; no equivale a 100% de recall real.
- Cero `risks=[]` presentados como «sin riesgos» sin prueba suficiente de cobertura+calidad.
- Reanudación de una ventana sin duplicar pagos ni hallazgos; error/coste parcial registrado.
- Cero acceso cross-tenant; protección PII sin romper evidencia original; sin SQL seed ni final approval falso.
- Reportar p50/p95 latencia y coste por documento vs baseline, precision/recall experto, estabilidad multi-run y tasa de incompletos.
- Despliegue PILOT solo tras pruebas reales y validación del propietario; #1229 independiente sigue abierto.

## 5. Recomendación ejecutiva
**GO para diseño final y MVP técnico acotado tras confirmación del propietario; NO-GO para refactor global simultáneo.** Priorizar evidencia útil en dashboard y el Complete Journey, no la cantidad de agentes o nodos. Mantener #1234 draft, no fusionar ni desplegar automáticamente.

**Nota:** documento de análisis propio; no sustituye pruebas o revisión de ingeniería completa.
