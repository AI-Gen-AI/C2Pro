# Revisión independiente Gemini — 2026-11-20

**Origen:** AI-GEN Ops, Gemini review, job `f255fece20fbc545ba29a989a48e8ee9`, **succeeded (exit 0)**, checkout SHA `822d0b9395dc0ccc7d4eff527c4da032e83bf865`; ejecutó read-only. Documento resumido y contrastado críticamente por CORE, **no transcripción literal**. No son resultados de un benchmark.

## Coincidencias de la revisión
- C2Pro ya posee DocumentGraph/N4/N12 y ProjectGraph como componentes a preservar. El valor de una biblioteca externa debe probarse, no suponerse.
- Los candidatos de primera utilidad son parsing de documentos (Docling) y lectura de cronogramas (MPXJ), porque se sitúan en el límite de entrada de datos y no requieren reemplazar la lógica de coherencia.
- El oráculo de extracción contractual debe contrastar N4/N12 con Docling+LangExtract sobre el mismo contrato + anexos, citando spans y reportando omisiones críticas, coste y cobertura.
- Entidades mínimas a diseñar: DocumentEvidence, SourceSpan, Obligation, Requirement, ScheduleActivity, CostLine, BOMItem, OfferLine, ActorRACI, Discrepancy, Coverage, ReviewDecision y ScoreProjection; todas ligadas a tenant, revisión y procedencia.

## Matices y correcciones respecto al dictamen Gemini
1. **No aceptar como hecho la eficacia funcional de N4/N12 por su presencia en código o tests.** Precisamente la UAT actual todavía está tratando cobertura, visibilidad de candidatos y validez de los resultados. El baseline ha de demostrar calidad sobre contratos y anexos.
2. **OpenContracts no necesita ser forzado a stateless para ser útil.** Puede conservar un corpus/anotaciones como un almacén secundario de evidencias documentales, con autoridad claramente subordinada; lo inadmisible es que determine ProjectGraph trusted, la aprobación o Coherence Score canónico por su cuenta. Evaluar primero si duplica más de lo que aporta.
3. **MPXJ tiene wrapper de Python en la documentación oficial.** Una JVM puede ser una dependencia de ejecución; un microservicio Java separado es una OPCIÓN de aislamiento, no una obligación técnica. Comparar wrapper Python, CLI/sidecar y servicio externo por mantenimiento.
4. **GPL-3.0 ERPNext no implica que cualquier API, importación de librería o DB compartida convierta automáticamente todo software cliente en GPL.** El alcance de las obligaciones depende de la forma de distribución, combinación/obra derivada y condiciones concretas. Recomendar API por bajo acoplamiento operativo; remitir la decisión legal a revisión especializada. La licencia no es razón suficiente para desechar una integración API.
5. **No hay que probar aquí una sustitución de N12 como aprobación.** LangExtract es un generador de propuestas de extracción con source spans; N12/revisor independiente y frontera trusted se mantienen incluso si cambia el extractor.
6. **La comparación contra la rama `main` actual no basta**, porque `main` está históricamente detrás de pilotos activos. Congelar la SHA actual relevante del camino contractual de evaluación sin mezclar ramas.
7. **Coste y latencia no están medidos.** GPU, API rate limits y rendimiento de cada componente requieren pruebas; no debe proclamarse que uno es más rentable sin medición.

## Recomendación de CORE al Planner
- Elaborar 2 arquitecturas candidatas (adaptadores de formato y servicio documental especializado) sobre un único ProjectGraph canónico.
- Empezar con parsing/MPXJ en test aislado sin LLM, después extraction benchmark con oráculo y límite de coste definido.
- Formalizar estado candidate vs trusted, cobertura, versionado y source spans en los contratos de intercambio.
- Describir explícitamente licencias OSS del código, los modelos y los datasets por separado.
- No introducir nuevos backlogs, código de producción, merges ni despliegues por efecto de este estudio.

Enlaces principales:
- https://github.com/Open-Source-Legal/OpenContracts
- https://github.com/joniles/mpxj
- https://github.com/docling-project/docling
- https://github.com/google/langextract
- https://github.com/frappe/erpnext

**Estado:** revisión completada y depositada en rama de investigación, sin decisión de adoptar componente.
