# B2 — LangExtract con inferencia real en VPS (dos ventanas N4 × dos pasadas)

**Fecha:** 20/11/2026. **Estado:** **B2 técnico ejecutado · PASS_LIMITED; NO-GO para integración productiva de LangExtract**. No se ha ejecutado todavía N4 v2 como comparador del mismo modelo, ni existe un oráculo EPC *held-out*.

## Qué se ejecutó realmente

- **Instalación:** LangExtract **1.7.1** en entorno privado de VPS `/home/aigenadmin/aigen-hybrid-pilot/data/c2pro-b2-langextract-vps/.venv`, Python 3.12.3. Ninguna dependencia añadida a C2Pro productivo.
- **Inferencia autenticada real:** NVIDIA API `nvidia/nemotron-3.5-bolt-e4b`, clave existente protegida en OpenCode del VPS. Se probó el endpoint y se integró un `BaseLanguageModel.infer()` privado que llama a NVIDIA **dentro del flujo nativo `lx.extract()`**. No se copiaron claves al código o a GitHub.
- **Fuente pública:** contrato Longfellow/SolarMax en HTML de SEC, proyección de **227.151 caracteres** con SHA256 `b4009aee679ebef7c81c07446a897ad5f9b7e8c224db7f0156f6a7967af99044`. NO es el PDF renderizado de B0/B1; sus offsets no equivalen a páginas físicas originales.
- **Ventanas:** `n4_source_windows.py` de la SHA fija `916808c5...`, ordinales **7 y 8**, contextos de **11.999 y 11.994 caracteres**; parte del contrato público. El conjunto de salida contiene la superposición propia del planner; no se infiere que se hayan leído los 227k caracteres.
- **Estrategia real de LangExtract:** texto íntegro de ambas ventanas, segmentado **internamente en ~4.000 caracteres** para evitar truncamiento. `ExampleData` sintético centrado en una obligación raíz con desencadenante, tramos, tope, dimensiones y referencias; `extraction_passes=2`; `context_window_chars=400`, formato JSON; resolutor final configurado **sin fuzzy** y sin aceptar coincidencias parciales.
- **Ejecución:** 16 respuestas generativas exitosas en el estudio completo, de las cuales cuatro se reutilizaron mediante caché en el lanzamiento final y doce fueron llamadas nuevas. Todas las respuestas nativas de este ensayo terminaron `stop` con JSON válido. Los **dos intentos iniciales** sobre una ventana completa de 12k sin segmentar habían terminado en `length` con JSON inválido y están excluidos de la medición de extracciones aceptadas. No se repitió automáticamente ningún intento truncado.
- **Control de consumo:** límite de llamadas, de tokens de salida por llamada y presupuesto agregado de tokens nuevos; logs de `usage` con lectura privada en VPS. El **coste monetario NVIDIA no está verificado**. El saldo OpenAI/Gemini de las capturas del propietario **no se utilizó**.

## Resultado cuantitativo: reaplicando los mismos recibos sin nuevas llamadas

| Indicador | Una pasada | Dos pasadas | Delta de segunda pasada |
|---|---:|---:|---:|
| Llamadas lógicas al modelo | 8 | 16 | +8 |
| Tokens de entrada + salida | 21.800 | 42.505 | +20.705 |
| Candidatos extraídos tras consolidación LangExtract | 115 | 141 | +26 |
| Citas estrictamente literales y correctamente posicionadas | 79 | 80 | **+1** |
| Candidatos sin verificación literal | 36 | 61 | **+25** |
| Spans literales únicos tras descontar coincidencias entre ventanas | 79 | 80 | **+1** |

- **Ventana 7 (dos pasadas):** 73 candidatos, 36 anclados exactamente, 37 sin anclaje estricto; tipos: 55 obligaciones y 18 referencias.
- **Ventana 8 (dos pasadas):** 68 candidatos, 44 anclados exactamente, **24 no verificados** (23 sin intervalo y uno cuyo texto no coincide pese al estado de alineación); tipos: 53 obligaciones, 6 derechos, 4 condiciones y 5 referencias.
- La segunda pasada recuperó **un** span literal exacto nuevo y no perdió ninguno de los 79 de la primera. No se interpreta el número de spans como número de obligaciones jurídicamente correctas.

Evidencia reproducible de métricas, **sin texto fuente, respuestas, prompts ni credenciales**: [B2_NVIDIA_LANGEXTRACT_REAL_2WINDOWS_2PASSES_20261120.json](evidence/B2_NVIDIA_LANGEXTRACT_REAL_2WINDOWS_2PASSES_20261120.json).

## Auditoría visual

Se ejecutó `lx.visualize()` sobre el resultado real recuperado de los recibos, sin nuevas llamadas:
- `evidence/visual_audit_private/SEC_N4_WINDOW_07_2pass_native_LangExtract.html`
- `evidence/visual_audit_private/SEC_N4_WINDOW_08_2pass_native_LangExtract.html`

Ambas visualizaciones se conservan **solo en el VPS**; contienen la proyección textual de las dos ventanas y no se suben al repositorio público.

## Dictamen crítico

1. **GO técnico para experimento real:** integración NVIDIA ↔ LangExtract nativa y ejecución completa de 2 ventanas × 2 pasadas **demostradas**; problema de truncamiento mitigado por segmentación interna.
2. **NO-GO para activar multipasada por defecto:** la segunda pasada elevó los candidatos sin cita literal de 36 a 61 y apenas añadió una cita literal única, consumiendo 20.705 tokens lógicos adicionales. Eso **no mide el recall real**, pero cuestiona su rendimiento marginal en este modelo/documento.
3. **NO-GO para introducir LangExtract en N4 actual:** aún no hay prueba equivalente de N4 v2 con **el mismo modelo, las mismas ventanas y el mismo presupuesto**, ni oráculo independiente de raíces/atributos, omisiones y falsos positivos. Tampoco están verificados costes por 100 páginas o N12.
4. **Punto delicado:** la comparación contra la proyección HTML SEC verifica literalidad de cadena, **no autenticidad de página o fidelidad al PDF físico**. Una alineación estricta `MATCH_EXACT` puede ser incoherente con la cadena original: se detectó un caso y se clasificó como no verificado mediante comparación adicional de bytes/cadena.
5. **Atomicidad aún a demostrar:** el few-shot ordena agrupar obligaciones con `trigger/rate_tiers/cap` como atributos; el hecho de producir JSON y atributos no certifica esa agrupación para todas las cláusulas ni que no haya sobreextracción o duplicados semánticos.

## Siguiente puerta (B2.1 → B3)

- Crear **oráculo ciego, independiente y revisado por experto EPC**, de 8–15 hechos raíz con disparadores, tramos, tope, excepciones y dependencias, sobre estas mismas ventanas. No derivarlo de las predicciones ni basarse solo en números de sección.
- Ejecutar **una** comparación N4 v2 con NVIDIA bajo el mismo presupuesto y estas ventanas; medir *precision/recall* de **hechos raíz**, sus atributos, falsos positivos, cobertura y coste medido.
- No activar nuevos modelos, OpenContracts ni N12/ProjectGraph hasta demostrar mejora y establecer una atestación original verificable. Mantener las respuestas como `CANDIDATE_UNVALIDATED`.

**Límites de la conclusión:** no se ha validado interpretación jurídico-contractual, no se ha ejecutado N12 ni ProjectGraph, no hay promoción `trusted`, y no se ha desplegado nada.
