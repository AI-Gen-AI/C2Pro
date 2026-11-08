# C2Pro CORE — N4/N12: causas, pruebas y plan de implantación (08/11/2026)

Rama objetivo: release/core-candidate-20261108. Estado: aceptación técnica limitada; no UAT ni validación jurídica. Fuente: GitHub Actions https://github.com/AI-Gen-AI/C2Pro/actions/runs/42507347031 (SHA 0b33003361d560f6dd07b8b76e88c82e20033ae1). Fixture EPC inmutable SHA-256 6206d62492e786b2b97902cb59f19ba36f3bd996184470e5aecc3009cdf2c8eb.

## Diagnóstico causal: observación frente a hipótesis

| Pri. | Causa o factor | Estado actual | Contramedida y prueba |
|---|---|---|---|
| P0 | El ensayo antiguo degradaba complex_extraction de Sonnet 4.6 a Haiku 4.5 mediante low_budget_mode=True | Confirmado en repositorio y log | Ruta Sonnet estándar, low_budget_mode=False; comprobar modelo real en registro del proveedor |
| P0 | El evaluador N4 omitía extract_input_from_state, utilizado por el grafo y responsable del filtro pre-LLM | Confirmado en código | Reutilizar exactamente ese método con proyección N2 sintética explícita; verificar que conserva 9/9 cláusulas |
| P1 | El prompt anterior recomendaba devolver 3–8 riesgos; Haiku entregó ocho y omitió EPC-05 | Limitación real corregida en PR #1200; causalidad NO acreditada | Repetir oráculo con prompt ya corregido, sin objetivos artificiosos por cláusula |
| P1 | Cupo experimental 4.096 tokens con 4.073 utilizados | Confirmado 99,44 %, con stop_reason=end_turn (sin truncamiento declarado) | Dar al modelo estándar sus 8.192 tokens y verificar stop_reason y uso |
| P1 | N12 se probaba con entradas adversariales fabricadas, no con la salida real de N4 | Confirmado | Separar N12 adversarial de N12 encadenado, cada uno con métricas diferenciadas |
| P1 | Las citas inválidas propuestas podían desaparecer en notas saneadas | Riesgo corregido en PR #1201 | Auditar payload bruto: presentadas, validadas y rechazadas; nunca transformar en aprobación HITL |
| P2 | Haiku podría rendir peor que Sonnet ante exclusiones contractuales | Hipótesis pendiente | Comparación controlada posterior con prompt, contexto y tokens constantes si el ensayo Sonnet no resuelve |
| P2 | Corpus sintético no representa ingestión N2, identidad documental, tenants ni PostgreSQL del recorrido completo | Limitación de alcance confirmada | UAT ulterior con DOCX/XLSX reales, proyecto, persistencia, HITL y aislamiento A/B, sin afirmar Coherence Score antes |

## Implementación propuesta y fases

**M0 — Diagnóstico cerrado:** resultado real anterior: N4 8/9, citas 8/8 válidas, ningún FP; omitida fuerza mayor EPC-05. N12 sobre entrada adversarial: 2/2 omisiones, interpretación errónea EPC-05 y 3/3 citas en salida saneada. Se usaron dos llamadas Haiku con gasto estimado USD 0,027657. Las nueve cláusulas sí estaban en la fuente; no hay prueba causal única ni de fallo del N4 productivo.

**M1 — Evaluador representativo:** script apps/api/scripts/n4_n12_representative_eval.py con la preparación real de N4 sobre una proyección sintética N2 explícita, usando Sonnet 4.6, 8192 tokens, sin caché ni reintentos. Registra huellas y cobertura, no texto original de respuestas.

**M2 — Tres llamadas reales, independientes y limitadas:** 1) N4 Sonnet sobre contrato EPC; 2) N12 Sonnet sobre inyección adversarial controlada; 3) N12 Sonnet sobre la lista realmente extraída por N4. Governor existente con máximo 3 llamadas y 1 USD, referencia SHA exacta, clave test-only, sin S2/UAT/Clerk ni despliegues. El gasto se computa con la telemetría del proveedor, no como factura.

**M3 — Aceptación del ensayo:** N4 debe detectar 9/9 riesgos con citas verificables y sin falsos positivos. N12 adversarial debe detectar 2/2 omisiones y 1/1 lectura incorrecta con citas de EPC-04/05/07 y cero referencias inventadas en bruto. N12 encadenado debe conservar revisión humana y no inventar procedencia documental. Estas tres medidas NO acreditan exactitud jurídica ni completitud del proyecto.

**M4 — Tratamiento de fallo:** si el resultado sigue fallando con Sonnet, localizar la primera causa reproducible (modelo, prompt, parseo, categoría, snippet, source_quote, normalización, filtros). Corregir con prueba adversarial y nueva revisión; no rebajar exigencias para aprobar el oráculo. Si sigue habiendo incertidumbre sobre el factor modelo, diseñar comparación Haiku/Sonnet con condiciones constantes; no cambiar globalmente el catálogo sin evidencia.

**M5 — UAT posterior de producto:** verificar DOCX/XLSX originales, N2 real, persistencia PostgreSQL, documento y revisión, N4→N12 por tenant, HITL y Coherence Score. Hito separado, no incluido en el ensayo de tres llamadas.

## Límites de autoridad y alcance

- No validar jurídicamente interpretaciones a partir de citas localizadas.
- No aprobar HITL ni Coherence Score automáticamente; estado NOT_ASSESSED es correcto cuando la semántica sigue pendiente.
- No afirmar equivalencia con N2 real, OCR, acceso de tenants, bases de datos ni journey completo.
- No hacer despliegues ni modificaciones de infraestructura ajenas al CORE. Evidencia técnica y fallos deben conservarse vinculados al SHA probado.

## Refuerzo de revisión adversarial sobre el evaluador

La PR se revisó adversarialmente y se corrigieron tres defectos de sus controles de aceptación:

1. El paso CI ya no confía en los booleanos calculados por el evaluador. El módulo separado apps/api/scripts/n4_n12_representative_gate.py vuelve a inspeccionar los nueve casos, el contenido del artefacto de métricas y cada reserva/liquidación del registro SDK, incluidos modelo, tokens, coste y fin de respuesta. Un falso mapa de gates=True no puede sustituir este examen.
2. N12 encadenado exige respuesta estructurada, ninguna cita inválida en notas ni en hallazgos brutos, ausencia de fallo de parseo y respuesta real con hash. Un UNASSESSED por JSON malformado NO es un éxito.
3. El indicador de revisión requerida proviene de human_approval_required de ambos CritiqueExtractionUseCase. El informe dice explícitamente hitl_pause_in_graph_tested=False: no afirma que se haya ejecutado o persistido una interrupción HITL real.

La validación es de calidad de extracción y citas. No sustituye la revisión jurídica ni constituye un segundo validador semántico del texto legal.
