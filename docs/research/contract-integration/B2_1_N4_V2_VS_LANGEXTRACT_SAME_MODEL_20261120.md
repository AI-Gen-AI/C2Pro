# B2.1 — Comparación ejecutada N4 v2 experimental vs LangExtract con el mismo modelo

**Fecha:** 20/11/2026. **Dictamen:** PASS_LIMITED para comparación generativa de laboratorio; **NO-GO para afirmar recall contractual validado o integrar en producción**.

## Configuración controlada

- **Fuente única:** contrato EPC público SolarMax/Longfellow de la SEC, proyección del HTML original de 227.151 caracteres (SHA256 `b4009aee679ebef7c81c07446a897ad5f9b7e8c224db7f0156f6a7967af99044`). No es PDF con paginación física acreditada.
- **Ventanas:** 7 y 8, de aproximadamente 12.000 caracteres de contexto cada una, generadas con el `n4_source_windows.py` fijado a la SHA `916808c5`. Los **8 fragmentos internos** fueron delimitados con el **mismo `UnicodeTokenizer`/`ChunkIterator` de LangExtract 1.7.1**, `max_char_buffer=4000`, contexto previo de hasta 400 caracteres.
- **Modelo:** NVIDIA `nvidia/nemotron-3.5-bolt-e4b`, temperatura 0, máximo 3.072 tokens de salida por solicitud, una pasada. **8 llamadas efectivas cada alternativa**, sin mezclar respuestas de otros modelos.
- **Comparación de estrategias:** LangExtract usó `ExampleData` de obligación raíz + atributos; N4 v2 usó un **prompt de esquema de raíces propuesto en laboratorio**, sin few-shot. **No se ha ejecutado `n4_incremental_runner.py` en producción ni se ha sustituido su contrato de salida plano.** Los formatos de prompt y sus instrucciones no son idénticos; esta es una comparación de estrategias, no un A/B que aísle el efecto exclusivo de la librería.
- **Oráculo:** lista **prerregistrada antes de N4** de 13 raíces contractuales identificadas directamente en el texto, SHA256 `3eee6ee765dd04bf7ddab754662a78c5c3466eaed03b1688cd3099b404c01bd3` ([prerregistro](B2_1_ORACLE_PREREGISTRATION_20261120.md)). **No es un oráculo exhaustivo, ciego ni aprobado por experto EPC**; las coincidencias por ancla textual no constituyen recall semántico.
- **Evidencias:** [JSON público sin textos ni credenciales](evidence/B2_1_N4_V2_VS_LANGEXTRACT_SAME_MODEL_20261120.json). Respuestas originales y oráculo completo permanecen en VPS privado.

## Resultado real de una pasada

| Métrica | N4 v2 experimental | LangExtract |
|---|---:|---:|
| Llamadas al modelo | 8 | 8 |
| Tokens de entrada | 8.750 | 10.377 |
| Tokens de salida | 11.269 | 11.423 |
| Tokens totales | **20.019** | 21.800 |
| Candidatos generados | 73 | 115 |
| Candidatos con cita literal exacta | **71** | 79 |
| Candidatos sin cita literal exacta | **2** | 36 |
| Spans fuente exactos únicos (tipo + posición) | 70 | 79 |
| Anclas provisionalmente localizadas (sobre 13) | 12 | 12 |
| Referencias como entidades raíz | 1 | 17 |

Las cifras de citas exactas **no son precisión contractual**. No se ha determinado cuántos de los 71 o 79 extractos representan obligaciones o derechos jurídicamente correctos, duplicados semánticos o meros subfragmentos. El número de referencias raíz tampoco valida sus vínculos: el prompt N4 emitió adicionalmente **seis referencias abiertas** en `outstanding_references`, campo que no es una entidad raíz.

### Hallazgos contrastados

1. **Las omisiones no coinciden.** La comprobación por ancla textual no encontró:
   - N4 v2: `R12` — derecho del propietario a intervenir para mitigar una emergencia (§2.10.5).
   - LangExtract: `R02` — derecho del contratista a solicitar una orden de cambio por retraso de determinados componentes (§2.5.6).
   Esto no demuestra omisión semántica completa si la salida citó otras palabras de la misma obligación; exige revisión humana.
2. **Atomicidad de daños liquidados:** N4 v2 emitió un candidato raíz `obligation` con cita literal y atributos anidados para los tramos de **5.000 / 10.000 / 20.000 USD por día** y el tope de **800.000 USD**, además de otro candidato de obligación en pasaje diferente de la misma cláusula. Falta decidir si ambas son raíces autónomas o una sola obligación con distintas condiciones.
3. **Fidelidad de citas:** N4 v2 produjo 71 candidatos con literalidad exacta sobre la misma proyección textual, frente a 79 en LangExtract; el primero dejó solo 2 sin anclaje, el segundo 36. Eso favorece N4 en **disciplina de literalidad del experimento**, pero no prueba superioridad jurídica o mayor exhaustividad.
4. **Tokens:** 20.019 en N4 v2 frente a 21.800 en LangExtract (8,2 % menos aproximadamente); la diferencia monetaria no está verificada porque el precio del servicio NVIDIA no fue auditado. No extrapolar costes por 100 páginas.
5. **Multipasada:** el ensayo B2 anterior de LangExtract, también bajo NVIDIA, indicó que pasar de una a dos pasadas añadió 26 candidatos pero **solo una cita exacta única**, con 20.705 tokens lógicos adicionales. No repetir multipasada hasta que un oráculo experto demuestre valor.

## Procedimiento y trazabilidad

- Se comprobó primero la lectura literal de 13 anclas de fuente sin consumir inferencia, y se guardó su hash en el repositorio antes de ejecutar N4 experimental.
- N4 v2 experimental: `/home/aigenadmin/aigen-hybrid-pilot/data/c2pro-b2-langextract-vps/scripts/b2_n4_v2_root_same_model.py`; SHA-256 `fc50f80878bcf8a09e008d22bc90ffaaeab90cbf94a8fbe00e43ea009c4ce96c`. Un ensayo inicial de una llamada se reutilizó como evidencia; las otras siete se ejecutaron sin repetir esa llamada.
- Consolidación sin nueva inferencia: `scripts/b2_1_compare_n4_lx_without_new_calls.py`; SHA-256 `dbd29f0a58f1ab44931e40cf8965d6543f471e8e5f4dc6de023635334afe893f`. Reproduce respuestas de LangExtract desde recibos privados, llama al validador experimental `parse_n4_typed_fact_candidate_response` fijado por GitHub y verifica `source_quote` por posiciones contra los bytes/texto fuente; descuenta spans repetidos.
- El **comportamiento productivo real de N4** (ledger, reintentos, control de gasto, N2, N12, HITL, ProjectGraph, Score y política de autoridad) permanece **fuera del experimento**.
- No se publicó texto completo, prompts, tokens de acceso, respuestas privadas ni HTML `lx.visualize()`; solo métricas agregadas.

## Decisión y siguiente gate

**Mantener ambos enfoques como alternativas de laboratorio**, conservando N4 como motor único del producto. No integrar todavía LangExtract. La extracción raíz tipada necesita consolidar:
- Un oráculo independiente revisado por un experto EPC con cobertura y reglas de atomicidad; verificación de **obligación + disparador + plazos + tramos + cap + excepción** para cada raíz, no solo ancla de cita.
- Un recorrido N4 actual real (no solo el esquema de laboratorio), N12 crítico contra fuentes originales con remisiones a anexos, y entrega a ProjectGraph con estado candidato, nunca `TRUSTED` automático.
- Validación de referencias/anexos pendientes y de diferencias entre contrato, presupuesto y cronograma del mismo proyecto.

**Conclusión:** N4 v2 experimental muestra mejor control de citas y menos tokens en esta comparación acotada; LangExtract aporta más spans exactos pero también más candidatos sin anclaje. Ninguno ha demostrado *recall contractual* superior ni utilidad empresarial integral.
