# B0 — Comparación ejecutada: parser C2Pro frente a Docling + plan N4 (20/11/2026)

**Estado:** **PASS_LIMITED para investigación, NO-GO para sustituir la ingesta actual ni activar N4/N12.**  
**Rama:** `research/c2pro-docling-contract-integration-20261120`.  
**Baseline funcional inspeccionado:** PR #1276, SHA `916808c5212e3dbc652407f35f3a17557623c06c`.  
**Restricción:** esta PR contiene un flujo **N1→N2→N4→END**, SIN N12/HITL/ProjectGraph; la verificación de parser no es validación de riesgos.

## Corpus y reproducibilidad
- Fuente pública: [SolarMax / Longfellow BESS I, contrato EPC en SEC](https://www.sec.gov/Archives/edgar/data/1519472/000164033425001363/solarmax_ex991.htm). Descargado en HTML desde la SEC y **renderizado localmente a PDF con Chrome** para realizar una comparación sobre exactamente los mismos bytes. El PDF derivado tiene **74 páginas**, 1.211.834 bytes, SHA256 `8c7104d3b5c1a5e0a1f457e23c3480ef3832e3c2567f7b16a95d38e3ee5d48e4`. **No** es el PDF original de la SEC ni coincide necesariamente con los expedientes PDF de QA/UAT; sus páginas NO son numeraciones oficiales del contrato.
- [Harness reproducible](../../apps/api/tests/integration/benchmark_docling_vs_legacy_public_pdf.py) (en el repo, ruta correcta: `apps/api/tests/integration/benchmark_docling_vs_legacy_public_pdf.py`).
- [JSON factual de ejecución](evidence/B0_Longfellow_SEC_PUBLIC_RENDER.json): métricas agregadas, sin reproducción del contrato. Entorno local Windows, Python 3.11, PyMuPDF/Docling 2.151.1. No hubo LLM ni inferencia de pago.

## Resultados medidos

| Comprobación | PDFFileParser actual PR #1276 | Docling opt-in I-C01 |
|---|---:|---:|
| Documento exacto | 74 páginas | las mismas 74 páginas |
| Tiempo local observado | **0,268 s** | **173,640 s** |
| Bloques / texto | 473 bloques, 227.313 caracteres | 655 elementos texto |
| Páginas reportadas/ancladas | 74 | 74 |
| Tablas estructuradas | API antigua no devuelve celdas de tabla | **3 tablas / 291 celdas** |
| Elementos sin anclaje de página | n/d | 0 |
| Inventario para N4 | **22 ventanas** (12k contexto, 400 solapamiento; todos los caracteres conservados) | **BLOQUEADO**: secuencia Docling incompleta |
| Resultado | PASS de lectura e inventario; interpretación no comprobada | PASS de parsing estructural, **FAIL del gate de orden completo** |

**Advertencia metodológica:** los tiempos no son un benchmark de rendimiento en caliente equivalente (Docling carga un modelo de layout; PyMuPDF es extracción directa). Las 3 tablas detectadas no están validadas celda a celda; el HTML oficial contenía tablas de maquetación que no equivalen a BOQ.

### Diagnóstico del bloqueo de orden, muestra independiente de 10 páginas
Un segundo PDF público **derivado de las primeras diez páginas del mismo PDF generado** fue procesado separadamente:
- 102 referencias en `document.texts` y 3 en `document.tables`.
- El iterador `document.iterate_items()` entregó 104 elementos únicos: incluía 9 imágenes y 3 tablas, pero **omitía 10 referencias de texto** de `document.texts`.
- Por tanto `reading_order` no constituye un inventario completo por defecto. El adaptador actual **falla cerrado** en lugar de perder esos 10 elementos y afirmar cobertura; necesitamos resolver la inserción, posición o exclusión explícita de los orphans.
- La sonda de 10 páginas no demuestra que el porcentaje de omisiones sea idéntico en las 74 páginas.

## Nueva estrategia pragmática a partir de la prueba
**No sustituir ciegamente el parser actual por Docling.** Mantener el texto del parser actual como base del N2/N4; Docling, inicialmente, actúa como **sidecar opt-in** de tablas, celdas, página y bbox de la **misma revisión SHA**. Si Docling omite un elemento, su indisponibilidad/orden parcial no elimina el texto que el parser actual sí leyó.

Se ha implementado en esta rama:
- `apps/api/src/documents/adapters/parsers/docling_optional_table_sidecar.py`: lectura baseline estable, hash PDF de revisión y tabla Docling `ADVISORY_UNVERIFIED`; el texto Docling **no reemplaza** la entrada N2. **6/6 unit PASS** (fixtures in-memory). No conectado a producción.
- `apps/api/src/documents/adapters/parsers/docling_n4_source_bridge.py`: enlaza un candidato Docling con el **planificador existente de N4** por offsets y páginas, manteniendo N4/N12 sin ejecutar. **7/7 unit PASS**, pero requiere orden Docling completo y proyección N2 *idéntica*, por lo que **no puede consumirse todavía el PDF real de 74 páginas**. Si N2 altera el texto por PII, bloquea hasta disponer de mapeo de offsets.
- Los adaptadores anteriores siguen disponibles solo como material de desarrollo; no está aprobada su conexión directa.

## B0 → B1/B2 → B3: puertas de aceptación

**B0 INGESTA:** PASS_LIMITED; para GO, demostrar que la base PyMuPDF cubre el documento, que un sidecar Docling no borra ni duplica segmentos, y que las tablas poseen celdas y referencias visualmente contrastadas. Con `layout_missing` no declarar `FULL_SOURCE_COVERAGE`.

**B1/B2 CONTRACTUAL:** todavía **NO EJECUTADO**. LangExtract es una biblioteca de extracción con mapeo de *character spans* y LLM, no garantía semántica. Se necesita mismo texto/ventanas, mismo modelo/presupuesto, oráculo EPC independiente held-out y métricas de obligaciones/condiciones/riesgos, citas e indicadores de faltantes. El contrato SEC público **no incorpora todos los anexos**: esos anexos deben permanecer `REFERENCED_MISSING`, no `EXAMINED`.

**B3 MULTIDOCUMENTO:** todavía **NO EJECUTADO**. MPXJ leyó cronogramas nativos en laboratorio, pero no se han acreditado ruta crítica, holguras y línea base por recálculo independiente. Se necesita contrato + cronograma y BOQ de **la misma revisión/proyecto**, mapping WBS con autoridad y oráculo de discrepancias. N12/ProjectGraph no forman parte del piloto #1276 y requieren un camino UAT distinto.

## Estado de producción y confidencialidad
- No hubo merge, despliegue, cambios de upload policy, llamadas a N4/N12, promociones a `TRUSTED`, Score, HITL ni alertas.
- No se subieron documentos históricos privados, OCR ni nombres de proveedores a esta nueva rama. Todos los ejemplos pertenecen a fuente SEC pública o fixtures sintéticos.
- Los resultados solo prueban capacidad estructural e integridad básica; no constituyen informe jurídico o dictamen de coherencia del proyecto.
