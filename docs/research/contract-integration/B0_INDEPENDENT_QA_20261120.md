# B0 — QA independiente (20/11/2026)

**Revisor:** Gemini, ejecución AI-GEN Ops job `532413dbb1f4e98b5b09eebc6632cb15`, revisión read-only fijada a SHA `ffa69828c365cc78599a2d24e1d3ae95ac9f6ec4`. **Resultado: PASS_LIMITED para investigación y NO-GO para sustituir PDFFileParser.**

## Hallazgos respaldados
- Los 227.313 caracteres procedentes del parser actual se conservaron en las 22 ventanas de N4 planificadas. Esto es **cobertura de lectura del resultado extraído**, no prueba de que el contrato físico se leyó sin omisiones.
- Docling produjo estructura de 3 tablas/291 celdas, sin que se haya demostrado fidelidad celda a celda ni que sean tablas de presupuesto frente a maquetación.
- En la sonda separada de diez páginas del PDF derivado de SEC, `iterate_items()` omitió 10 de las 102 referencias de texto presentes en `document.texts`. **No se extrapola estadísticamente** esa tasa a las 74 páginas. Este hallazgo sí demuestra que consumir el iterador sin control puede omitir datos.
- La paginación/bbox corresponde al PDF local generado desde el HTML SEC, no a una paginación contractual oficial.
- El puente a N4 (7/7 unit) y sidecar (6/6 unit) superaron pruebas de seguridad sintética (fuente SHA, cero trusted). El test conjunto del árbol Docling confirmó 35/35 unit PASS; ninguno demuestra aún N4/N12 útil en contratos reales.

## Dictamen arquitectónico

**Aprobable para investigación:** mantener `PDFFileParser` como fuente de texto para N2/N4 y añadir las tablas Docling como anotaciones opcionales `ADVISORY_UNVERIFIED`, asegurando el mismo hash de PDF y páginas. No alterar el texto N2, no duplicar el planner `n4_source_windows.py` ni falsificar attestation original.

**No aprobable:** sustitución total de parser ni alimentación directa con una secuencia incompleta. Si N2 redacta PII, ningún offset previo debe afirmarse como cita exacta hasta disponer de mapeo original→proyección saneada.

## Correcciones críticas a la formulación del QA

1. **«Cero huérfanos» no es prerrequisito para usar Docling como *sidecar parcial*.** Sí es imprescindible antes de declarar que la *secuencia Docling sustituye íntegramente* al texto actual. Una anotación parcial es admisible si la cobertura faltante se informa y no altera la fuente canónica.
2. **No es obligatorio que todos los PDF estén firmados digitalmente** para probar la fidelidad de extracción. Sí es obligatorio conocer el PDF **original recibido como fuente de verdad del experimento**, su SHA y su paginación, además de distinguir firmas/autoridad contractual de la capacidad del parser.
3. Docling **no ha probado mejora semántica alguna**; el camino LangExtract vs N4 solo tiene sentido con fuente equivalente, oráculo independiente y un presupuesto/tiempo medido, sin introducir otro orquestador N4.

## Siguiente gate

- B0.1 (sin IA facturable): medir fidelidad de tablas sobre documentos PDF originales no derivados y comportamiento sidecar con páginas escaneadas, tabla fusionada y encabezado repetido; afirmar solo cobertura realmente comprobada.
- B1/B2: N4 v2 vs LangExtract sobre exactamente el mismo texto y el mismo oráculo de obligaciones, condiciones y riesgos, con coste/citas/omisión crítica. **NO EJECUTADO AÚN**.
- B3: datos contrato, cronograma (MPXJ) y BOQ del mismo proyecto, revisar baseline y relaciones antes de escribir discrepancias candidatas en ProjectGraph. **NO EJECUTADO AÚN**.

**Producción:** sin merge, UAT, cambios de modelo, HITL, Score, N12 o ProjectGraph.
