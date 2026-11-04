# C2Pro — Investigación avanzada de integridad documental y plan autorizado (04/11/2026)

**Estado:** INVESTIGACIÓN COMPLETADA · PLAN APROBADO POR EL PROPIETARIO (04/11/2026) · IMPLEMENTACIÓN EN RAMA AISLADA

**Procedencia:** investigación avanzada terminada el 04/11/2026, contrastada con el repositorio AI-Gen-AI/C2Pro, PR #1112, HEAD inicial `34f1f67d66f26c2e905570c39a0d693c605fca6e`; enriquecida con comprobaciones SQL agregadas de Supabase C2Pro y revisión posterior. Este fichero conserva el **resumen técnico fiel, las decisiones, condiciones y plan accionable**; el informe narrativo original completo permanece en la conversación de investigación. No atribuirle pruebas de ejecución que no existan.

## 1. Conclusión ejecutiva

La principal brecha de calidad está antes de N4/N12: **la fidelidad del trayecto archivo original → parser → unidad estructurada y localizable → representación del modelo → resultado con cita**. C2Pro tiene extractores por formato, `clauses`, `document_chunks`, pgvector, N4, N12 y N8, pero NO una cadena de cobertura verificablemente completa y homogénea para contratos, presupuestos, cronogramas y especificaciones técnicas. La disponibilidad de chunks vectoriales y CI en verde no demuestra exhaustividad.

La decisión es avanzar **incrementalmente con evidencia**, sin sustituir los datos estructurados por RAG, ni añadir recuperación vectorial indiscriminadamente a N4/N12 antes de medirlos. Mantener una prueba sintética de 4 documentos y benchmark del fixture de 9 cláusulas como gate inicial. No usar datos confidenciales.

Estado observado en **Supabase proyecto C2Pro** mediante consultas SQL de solo lectura (04/11/2026): 39 documentos (37 contratos, 1 presupuesto, 1 cronograma); 426 cláusulas; 95 chunks vectoriales documentales; 0 registros en `clause_embeddings`; extensión pgvector 0.8.0. 167 cláusulas tienen `revision_id`, 259 no. **No afirmar que esta base corresponde al runtime Railway sin comprobar su DATABASE_URL efectivo.**

## 2. Cadena actual y pérdidas identificadas

- **Contrato PDF/DOCX:** PyMuPDF captura texto/página/coordenadas en PDF, con OCR Tesseract condicionado; DOCX extrae párrafos y celdas pero pierde contexto de filas/columnas y página real. La persistencia de cláusulas puede descartar segmentos menores de 40 caracteres o truncar los mayores de 4.000. N4 aplica selección determinista por keywords e impone límite típico 40.000 caracteres; N12 limita su revisión a unos 16.000 caracteres. Ni N4 ni N12 trabajan automáticamente con el conjunto completo de `document_chunks`. Riesgo: hechos omitidos antes de inferencia.
- **Presupuesto XLSX/BC3:** se lee primordialmente la hoja activa del XLSX y se obtienen partidas/cantidades/precios/totales; sólo el modo evidencia identifica con rigor filas y rechaza fórmulas no verificadas. `_extract_rag_text` no tiene rama `budget`, por lo que 0 chunks de presupuesto no implica error de parser; sí implica que no hay indexación RAG de partidas por esta ruta. BC3 en #1112 aún tiene fallback falso si no está el parser; la rama P0 de Codex `232ef483` lo elimina explícitamente.
- **Cronograma XLSX:** se obtiene hoja activa, actividad, fechas, duración, WBS y precedentes; no equivale a reconstruir calendarios, FS/SS/FF/SF, retardos, flotaciones, ruta crítica o baseline. La ruta estructurada puede marcar `ANALYZED` sin análisis N1–N17, por diseño.
- **Especificación técnica:** indexa requisitos en secciones numeradas que contienen una obligación; no prueba haber capturado tablas, figuras, apartados sin numeración o anexos. Una extracción parcial no debe promocionarse a conformidad técnica.
- **Planos:** `drawing` existe como tipo, pero el upload general sólo acepta PDF/DOCX/XLSX/BC3; PDF puede dar texto/OCR, no geometría confiable, vistas, símbolos, tolerancias ni interferencias. DWG/DXF/IFC/MPP/XER aún requieren adaptadores especializados y evaluación de licencias.
- **RAG:** `RagService._split_text` normaliza whitespace y corta a 1.000 caracteres, overlap 200, luego embedding `text-embedding-3-small` 1.536 dimensiones; no respeta límites de cláusulas/partidas/actividades ni aporta por chunk localizadores canónicos de origen. RAG es un índice derivado auxiliar, no el origen de verdad.
- **N8:** `find_cross_document_pairs` existe, pero consulta `clause_embeddings`, actualmente vacío en la BD consultada. La función filtra proyecto y tipo documental, pero no revisiones vigentes ni explícitamente tenant. No poblar masivamente embeddings sin un modelo explícito de revisión y aislamiento.

**La rama P0 de Codex `codex/core-p0-20261104` (`232ef483`) introduce `document_coverage_by_revision`, señala hojas Excel/fórmulas no evaluadas, declara cobertura PDF/DOCX sin verificar, registra omisiones de cláusulas y rechaza BC3 ficticio. Fue publicada, pero NO está integrada en #1112 ni en main.**

## 3. Opciones comparables (NO descartar por defecto)

| Vía | Herramientas/candidatos a evaluar | Ventaja | Riesgo/decisión |
| --- | --- | --- | --- |
| Determinista estructurada | PyMuPDF, pdfplumber, python-docx, openpyxl, BC3/FIEBDC, parsers XER/XML, ezdxf, IfcOpenShell | Citas y unidades exactas; coste bajo | Layout complejo, fórmulas/relaciones no evaluadas |
| Layout-aware OSS | Docling, Unstructured, Marker, Apache Tika y herramientas de OCR | Tablas, columnas, bloques y lectura multimodal según capacidad probada | Calidad variable, licencia y recursos |
| SaaS Document AI | Azure Document Intelligence, Google Document AI, AWS Textract, LlamaParse y equivalentes | OCR/tablas/layout robustos en escenarios elegibles | Residencia, precio por página, bloqueo de proveedor, privacidad |
| Modelos vision-language | Interpretación de páginas, tablas, diagramas y anexos complejos con citas verificadas | Recupera señales no accesibles a texto plano | Alucinación, costes, necesidad de comprobación contra fuente |
| SQL/relacional + reglas | PostgreSQL + objetos de dominio (cláusula, partida, actividad, requisito) | Exactitud monetaria, relación temporal, versionado | Contratos de esquema y migraciones |
| RAG vectorial/híbrido | pgvector, BM25, reranking, parent-child, contextual retrieval, late chunking | Contexto cruzado y consultas ad hoc | Top-k **no demuestra cobertura exhaustiva** |
| Grafos y conocimiento | ProjectGraph, GraphRAG, relaciones entre requisitos/riesgos/BOM/WBS | Detecta contradicciones entre familias | Construcción y calidad de relaciones, complejidad |
| CAD/BIM | PDF vectorial+raster, ezdxf, IfcOpenShell, APIs comerciales CAD/BIM y VLM especializados | Amplía a planos/mediciones/modelos | Formatos propietarios, tolerancias y geometría requieren validación |

**Criterio de selección:** evidencia de precisión/recall por familia, cita verificable, esfuerzo, coste, soberanía, seguridad, fiabilidad y portabilidad; no adoptar un único stack global. Los costes y licencias deben verificarse para versiones/volúmenes concretos antes de contratar.

## 4. Arquitectura objetivo, incremental

1. **Source ledger:** byte original inmutable, SHA-256, tenant/proyecto/documento/revisión y tipo.
2. **Parser por modalidad:** extractor nativo + layout/OCR/visión opcional. Mantener signos, unidades, fechas, coordenadas, tablas/filas y advertencias. Nunca inventar contenidos ausentes.
3. **Unidades canónicas:** contrato→cláusula/subcláusula; presupuesto→capítulo/partida/medición/moneda; cronograma→actividad/predecesores/calendario/hito; especificación→requisito y tabla; plano futuro→lámina/objeto/geometría.
4. **Coverage manifest por revisión:** recuentos observados, esperados (sólo si fuente lo permite), descartados, truncados, no verificados; alcance y localizador; estado COMPLETE/PARTIAL/UNASSESSED/UNSUPPORTED/UNVERIFIED, sin confundir parseo con evaluación experta.
5. **Índices derivados:** `document_chunks` para búsqueda contextual, embeddings por unidad canónica para relaciones N8, versión/modelo/dimensión y enlace a la fuente; sustitución segura de revisiones.
6. **N4/N12:** evaluación por lotes de todas las unidades del alcance, con citas. La recuperación top-k aporta contexto opcional, no selecciona qué evidencias deben existir.
7. **N8:** primero writer real de `clause_embeddings` y lector con filtros por tenant/proyecto/revisión vigente; después métricas de pares relevantes y falsos positivos.
8. **UI/QA:** mostrar cobertura junto al resultado, enlaces a fuente exacta y `UNKNOWN/UNASSESSED` cuando falta evidencia. No usar un 200 OK, CI verde o llamada LLM para declarar utilidad del producto.

## 5. Gates y plan autorizado

| Gate | Intervención | Evidencia exigida |
| --- | --- | --- |
| A — Integridad (P0) | Adoptar P0 existente + manifest de observaciones por revisión; contrastar 4 documentos sintéticos | 100% de unidades del fixture contabilizadas o pérdida declarada; todas hojas/fórmulas inventariadas; cero BC3 ficticios |
| B — N4 (Codex 2) | UNA evaluación LLM real con credencial protegida, fixture de 9 cláusulas | recall ≥8/9; precision ≥90%; 100% de citas materiales válidas; cero fuente inventada; modelo, tokens, costes y SHA registrados |
| C — N12 (Codex 2) | Revisión crítica separada de N4 sobre fuente real | Detecta las omisiones EPC-04 y EPC-07 y rechaza interpretación falsa EPC-05, sin mocks |
| D — N8 | Conectar writer y lector pgvector | 9/9 embeddings pertinentes del fixture, dimensiones/modelos correctos, aislamiento tenants, sin revisión obsoleta, pares citables |
| E — Operación | Unir pruebas de fuente, UI y persistencia en rama de integración cuando esté lista | SHA de código/fixture, usuario/pasos, datos sintéticos, sin modificar main hasta aceptación |

**Secuencia de implementación autorizada:** A → B/C (Codex en curso) → D → mejoras focalizadas de contexto/semántica según baseline → experimentos de CAD/BIM. El presupuesto inicial de la investigación es **26–42 horas efectivas aproximadas** para primera evidencia; no es promesa de duración ni coste contratado.

**Coordinación:** Claude sigue como escritor único en PR #1112; Codex 2 conserva rama `audit/n4n12-pgvector-1112`; este trabajo se hace en rama separada `feat/ingestion-evidence-p0-20261104` basada en P0 Codex 1. No merge a main, no despliegue, no datos reales; integración coordinada sólo tras resultados.

### Advertencias técnicas al reutilizar el SQL ilustrativo del informe original

**NO ejecutar como está** el SQL de ejemplo del informe:
- `clause_embeddings.clause_id` es VARCHAR y `clauses.id` UUID: el JOIN directo es incompatible y sus identificadores pueden no referirse al mismo concepto.
- `document_chunks` guarda `revision_id` en JSONB `metadata`, no en columna SQL propia.
- `clause_embeddings` no tiene columna `revision_id` en la estructura observada; debe añadirse mapping válido por identidad/metadatos o migración gobernada antes de filtrar revisiones.
- No confundir última revisión cronológica con revisión **trusted-current**.
- Las consultas deben segmentarse por tenant/proyecto antes de interpretar completitud; no copiar datos de documentos de usuario al informe.

## 6. Fuentes primarias y trazabilidad

- PR #1112 y criterios DONE: https://github.com/AI-Gen-AI/C2Pro/pull/1112
- P0 publicado: https://github.com/AI-Gen-AI/C2Pro/commit/232ef48375eb6672b2df6ea76bcaa49b7c3d6fe6
- N4/N12 runner Codex: https://github.com/AI-Gen-AI/C2Pro/commit/5f9392a783cb223a04a94c0b1b0af8208bda2675
- Diseño chunking Microsoft: https://github.com/MicrosoftDocs/azure-ai-docs/blob/main/articles/search/vector-search-how-to-chunk-documents.md
- Supabase pgvector: https://supabase.com/docs/guides/database/extensions/pgvector
- Gestión embeddings: https://supabase.com/docs/guides/ai/automatic-embeddings
- GitHub Actions secrets: https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- Guía de evaluación: https://docs.langchain.com/langsmith/evaluation-types

**Estado técnico al guardar:** investigación = documentada; implementación = autorizada; gate A en trabajo aislado; gate B/C pendientes de resultados de ejecución real; gate D aún no implementado. No afirmar que todos los proveedores alternativos hayan sido probados.


## 7. Verificación empírica de vectores y decisión de orden (04/11/2026)

**Alcance:** consultas SQL de solo lectura al proyecto Supabase `tcxedmnvebazcsaridge`; revisión de código de PR #1112 HEAD `34f1f67d`; inspección de servicios Railway sin acceder a secretos. **No se ha acreditado que la conexión `DATABASE_URL` efectiva de Railway apunte a esta misma BD:** el conector Railway muestra variables por nombre, con valores redacted.

### Datos contrastados

- `document_chunks`: 95 filas y 19 documentos, todos de tipo contrato. Los 95 embeddings son `vector(1536)`, sin NULL, sin norma cero. Normas min 0.999642, media 1.000089, max 1.000426. Índice `ivfflat vector_cosine_ops`.
- `clause_embeddings`: 0 filas, columna `vector(1536)`, índice `hnsw vector_cosine_ops`. La función SQL `find_cross_document_pairs` sólo lee esta tabla y, ahora mismo, NO puede obtener pares vectoriales en esta BD. **No afirmar que N8 entero carece de funcionalidad**, pues su subgrafo también incluye reglas, cross-doc determinista y señales.
- De los 95 chunks, **8 llevan `metadata.revision_id`**, 87 no; **0 llevan modelo de embedding ni localizador fuente**. Ningún chunk apunta a un documento ausente ni a otro proyecto/tenant según comparación de IDs.
- Distinción de embeddings reales/mock: C2Pro admite `settings.embeddings_mock` y genera con SHA-256 vectores deterministas de norma 1. Se compararon dos ratios de componentes contra ese algoritmo para 87 filas en las que las razones eran válidas: **0 coincidencias**. Los 8 restantes no son verificables con este test; esto excluye esa firma para los 87, **no demuestra el proveedor/modelo ni la calidad semántica**.
- Las 39 filas de `documents` observadas: 37 contratos (426 cláusulas), 1 presupuesto (0 chunks/0 cláusulas), 1 cronograma (0 chunks/0 cláusulas). Los dos documentos estructurados no tienen `document_metadata.stated_total_by_revision` ni `document_metadata.schedule_planned_finish` respectivamente en esta BD; no afirmar que hayan sido procesados de forma vigente.
- `procurement_budget_items` tiene **0** filas; `procurement_wbs_items` tiene **23**. La tabla de compras/BOM NO es la autoridad original del presupuesto y la WBS no reemplaza al cronograma.
- Railway project `c2pro-api`, entorno `production`: servicios `C2Pro` y `C2Pro-Worker` usan rama `integration/acc01-e2e-20261025` y tienen `DATABASE_URL`, `SUPABASE_URL` como nombres de variables, pero **sus valores están ocultos**. Por tanto no afirmar que esta Supabase sea la base del backend runtime sin evidencia de configuración.
- Código `PgvectorEmbeddingRepository.store_embeddings_batch`: `ON CONFLICT (clause_id, project_id) DO NOTHING`; esquema `clause_embeddings` no tiene columna `revision_id` propia. Riesgo de dejar vector obsoleto si cambia la revisión fuente. La consulta SQL de pares filtra proyecto y tipos distintos, **no revisión vigente dentro de SQL**; el wrapper comprueba proyecto/tenant si recibe contexto válido. Corregir el contrato de identidad y actualización antes de poblar producción.

### Orden aprobado para ejecución incremental (sin conflar datos estructurados con vectores)

**A — Garantizar y conservar observaciones estructuradas (PRIMERO).** Presupuesto XLSX/BC3: cada partida original, código/capítulo/cantidad/unidad/precio/total/moneda, fórmula y estado de verificación, `Sheet!row` o localizador original, blob SHA256 y revisión. Cronograma XLSX: cada actividad, identificador fuente/WBS observado, hitos, fechas, tipo de dependencia/lag cuando exista, calendario y baseline si probados, origen de fila y revisión. Si no se puede verificar, `PARTIAL/UNASSESSED`, no completar inventando. Persistir en fuente específica por revisión, no convertir a BOM o WBS canónica. Ya existen parsers y `ScheduleActivityEvidence` aprovechables; la fuente persistida completa aún NO existe. Inicialmente se puede conservar el resumen `stated_total_by_revision` y `schedule_planned_finish` sin pretender que sean el dataset completo.

**B — Conectar pgvector a unidades canónicas ya persistidas.** Contrato y especificación → cláusulas/requisitos verificados en fuente → embeddings de **descripciones textuales** con modelo, versión, SHA de texto, `tenant_id/project_id/document_id/revision_id/source_locator` y `unit_id` estable. Para presupuesto/cronograma vectorizar descripciones **solo opcionalmente**, jamás fechas/importes/unidades como verdad. No reutilizar los 95 chunks RAG como cláusulas canónicas ni confundir `document_chunks` con `clause_embeddings`. Adaptar identidad/UPSERT y limpieza de revisiones en `clause_embeddings`, y consulta tenant/trusted-current; no ejecutar migraciones directas en Supabase sin verificación de entorno e integración.

**C — Conectar nodos DESPUÉS de A/B.** N8 recibe evidencias estructuradas, reglas de comparación contrato↔presupuesto y contrato↔cronograma, más pares candidatos de pgvector trazables. N4 y N12 **NO requieren pgvector** para evaluación inicial de contratos: N12 tiene un fallo independiente de respuesta/JSON (`Automatic critique inconclusive.`); corregir parser/diagnóstico sin confundirlo con recuperación vectorial. El grafo define rutas `schedule→N5` y `budget→N9` si se invoca, pero el worker normal excluye ambos del grafo libre N1–N17; **no dar por hecha su ejecución por figurar en el diagrama**. Una futura conexión no debe atribuir a N5/WBS autoridad sobre actividades ni a N9/BOM autoridad sobre partidas.

**Puerta funcional única:** proyecto EPC sintético con cuatro documentos, reporte por unidad fuente/fiabilidad/revisión, modelo embedding conocido y coste declarado, N4/N12 sin fallback silencioso, N8 con pares reales citables, comparadores numéricos/de fechas y UI. Mantener CI/simulator separados de evaluación real. SIN despliegue, sin tocar #1112 de Claude, sin solicitudes de claves privadas y sin repetir LLM salvo un ensayo autorizado posterior.

### Decisión técnica

**pgvector funciona a nivel de tipo/índice/almacenamiento; la conexión de negocio aún NO.** Para presupuesto y cronograma, la autoridad primaria debe ser relacional/estructurada; los vectores son un índice auxiliar de búsqueda. Postergar optimizaciones IVFFlat/HNSW y nuevos modelos hasta que existan unidades originales trazables y consulta exacta de revisión.



## 8. Gate A — Primera persistencia de fuentes XLSX (04/11/2026)

**Implementación publicada en la misma rama aislada; aún no integrada en #1112 ni en main.** Tras el paso P0 de observaciones de cobertura:

- Nueva tabla `public.document_source_units`, migración Alembic `20261104_0001` (tras `20261101_0001`) y espejo Supabase `20261104000100_document_source_units.sql`. Clave única `tenant/document/revision/family/source_locator`, FK compuesta al registro inmutable de revisión, `blob_hash`, `unit_sha256`, JSONB de fila original y RLS forzada por `app.current_tenant`. No backfill ni exposición intencional a anon/authenticated.
- `structured_source_units.py`: reparseo XLSX con `include_evidence=True` y conservación de filas originales de presupuesto (`line_item`/total declarado) y cronograma (`activity`), manteniendo `Decimal` y fechas como cadenas sin pasar por float. Formula no verificada → `UNASSESSED`, sin falsificar dato. Hoja secundaria sin analizar → `parser_coverage=PARTIAL` conservado; sólo se escriben observaciones de hoja activa.
- `ingestion_tasks._ingest_owned`: inserciones dentro de la misma transacción que `ProcessingAuthority.finish_ingestion`, jamás escritura secundaria independiente. Resumen sin texto `source_units_by_revision` en metadata; bytes fuente validados previamente mediante SHA.
- Lector `load_canonical_source_units`: consulta por `tenant_id/project_id/family` y `current_revision_lateral`; excluye propuesta sin autoridad, no promueve la fuente original a baseline contractual ni WBS/BOM. Este lector **NO** se ha conectado todavía a N8; es deliberadamente un gate anterior a los nodos.
- Pruebas añadidas: nueve tests unitarios de fuentes + ampliación del test PostgreSQL integral existente `test_budget_and_time_rules_coexist.py` para exigir filas por revisión de presupuesto y cronograma. Los tests de cobertura P0 previos permanecen.
- Condiciones para ejecutar/integrar: probar una sola tanda focalizada de unit/integration en worktree aislado y PostgreSQL de ensayo; comprobar migración/RLS/permiso efectivo del worker; distinguir `SOURCE_OBSERVED` de `SOURCE_APPROVED`; mantener #1112 en manos de Claude; no desplegar sin aceptar la fuente y el veredicto de pruebas.
- Futuros incrementos: múltiples hojas y fórmulas calculadas con prueba de recálculo; BC3 source locators; modelos de actividad/calendarios/hitos P6/MS Project; después de ello writer embeddings por cláusula con identidad y revisión fiable, y finalmente N8/comparadores. No fragmentar números, importes y fechas como único vector.

**Estado:** `SOURCE_UNIT_PERSISTENCE_IMPLEMENTED_IN_BRANCH`; `NO_MIGRATION_APPLIED`; `NOT_DEPLOYED`; `N8_NOT_WIRED`. No afirmar cobertura exhaustiva de hojas ni calidad del conjunto sin evidencia.


## 9. Gate A — Resultado de prueba real PostgreSQL aislada (04/11/2026)

**Implementación con evidencia real de ejecución, NO desplegada.**

1. Primer lote sobre `6a6859d2a6b84441d90a6b6445dbeb9a867b3809`: job `fa424c52055e4c4aad1ba509`, **22 PASS, 1 FAIL**. El fallo fue `UndefinedTableError: public.document_source_units does not exist` en el ensayo integral, porque el bootstrap de pytest usa `Base.metadata.create_all`, no Alembic. No fue fallo del parser ni del proveedor IA.
2. Corrección focalizada: nuevo `DocumentSourceUnitORM` en `apps/api/src/documents/adapters/persistence/models.py`, commit `fdf49c1220a8752fe1b7419770e3eb4121ac3ba1`, con FK compuesta, unicidad y schema JSONB equivalentes a la migración. Esto registra la tabla en el metadata del bootstrap de ensayo y del backend.
3. Reejecución **solo del test previamente bloqueado** en PostgreSQL privado: job `5775bb7791c640f78ba2e883`, commit exacto `fdf49c1220a8752fe1b7419770e3eb4121ac3ba1`, `tests/integration/document_flow/test_budget_and_time_rules_coexist.py`: **1 PASS, 0 FAIL**, exit 0, 21.22s, log SHA256 `e04b8ca2865deaf626c49bd9b2d01e374a6a07cfdcf3d58774d53267ba78bbc6`. Prueba sobre dos archivos XLSX y contrato, verifica registros originales `document_source_units` por `tenant/project/document/revision`, presupuesto y actividades, además de reglas de coherencia previamente existentes.
4. No se han repetido las 22 pruebas ya correctas tras añadir el ORM; por eso la evidencia son dos ejecuciones con SHAs explícitos, **no** una afirmación de suite integral verde en HEAD. La ruta Alembic/Supabase, sus políticas RLS y los permisos efectivos del usuario de Railway aún requieren una verificación independiente **antes de despliegue**; los tests usan schema ORM de ensayo, no equivalen a aplicar migraciones en el backend.
5. El estado es **GATE_A_PERSISTENCE_VERIFIED_IN_ISOLATED_TEST**, sin `main`, #1112 ni despliegue; no aporta vectorización ni N8 todavía. La siguiente fase es demostrar identidad segura de `clause_embeddings` y conectar el escritor/lector de revisiones vigentes sobre esta fuente, conservando partidas/fechas en SQL.



## 10. Fase siguiente — writer cláusulas y pgvector en N8 (04/11/2026)

**Código implementado y contrastado en rama aislada, con flag OFF en runtime.** No implica contrato/N12 aceptados ni despliegue.

- Nuevo servicio `apps/api/src/coherence/application/canonical_clause_vectors.py`: selecciona cláusulas de **contratos CANONICAL** y requisitos de **especificaciones TRUSTED**, con `tenant/project/document/revision` obligatorio, texto original, SHA-256 textual, metadatos de origen cuando existen y modelo `text-embedding-3-small`. Excluye filas sin identidad de revisión, orígenes antiguos y propuestas pendientes. Generación de embeddings inyectable para prueba; revalida autoridad de revisión en el propio INSERT; usa `ON CONFLICT DO UPDATE` con mismo tenant y documento. No tiene commit implícito. Presupuestos y cronogramas siguen siendo fuentes relacionales; **no** se vectorizan cifras/fechas como verdad.
- `PgvectorEmbeddingRepository.find_cross_document_pairs` ya no utiliza la función SQL antigua, que carecía de filtro por revisión: compara únicamente embeddings de cláusulas con `revision_id` vigente, documento diferente, tenant y proyecto coincidentes, hash/modelo declarados y revisión CANONICAL/TRUSTED. El grafo N8 usa este método.
- `coherence/graph/nodes.py` ofrece indexación previa a consulta **solo con `C2PRO_CLAUSE_VECTOR_INDEX_ON_DEMAND=1`**; opción desactivada por defecto. En OFF sigue calculando coherencia sin nuevas llamadas al proveedor. No se ha cambiado Railway ni Vercel.
- Prueba de migración nueva `test_document_source_units_migration_pg.py`: comprueba 4 políticas de RLS, FORCE RLS, FK de revisión y unicidad en PostgreSQL de ensayo. No sustituye la validación de GRANT/runtime real.
- Suite focalizada de índice/adaptador/migración en PostgreSQL aislado: job `538905b2edaf449d8b0a8473`, SHA `bacd458a49e00a89423036dda616ecc46314d1f6`: **34 PASS, 1 SKIPPED** (test `test_rag_similarity.py` de integración antiguo, explícitamente omitido), exit 0; log SHA256 `435a199e232b33f64bbb7ba8940d760b4039d39597e07e558700c1a6595f9742`.
- Una prueba PostgreSQL adicional de conexión REAL SQL sin modelos comerciales: `test_canonical_vector_n8_pg.py`. Primera ejecución job `08b078ec1ac94060b5c9d06b`, SHA `1a4f066a...`: FAIL por acceso a `c.source_page`, columna que no pertenece al ORM testado (aunque figura en otro esquema observado). Se corrigió consulta para leer página opcional del JSON `extracted_entities`, sin presumir columna física. Repetición focalizada job `531667e654884d2f9ca002fb`, SHA `7e9c61b15c4baa6fcf69e1d021df5cacecccf5f8`: **1 PASS, exit 0**, log SHA256 `1b4475a78e728b0ecc049d6b0df1e9944631b36934809780e64bdd816fff89f5`. Efectivamente persistió embeddings sintéticos de contrato y especificación TRUSTED, produjo un par de similitud de N8 y **excluyó** una revisión contractual V2 PROPOSED. Sin llamadas IA.
- **Importante:** el test confirma integridad y enlace estructural, **no** precisión semántica o detección de contradicciones EPC. Los embeddings de la prueba son vectores controlados. La BD Supabase previamente observada sigue sin demostrar identidad con Railway; no se aplicó migración/GRANT en ella.

**Veredicto:** `GATE_A_SQL_MIGRATION_ISOLATED = PASS`; `N8_VECTOR_LINK_ISOLATED = PASS`; `REAL_EMBEDDINGS_ON_4_DOCS = NOT_RUN`; `N4_N12_EXPERT_ACCEPTANCE = NOT_ACCEPTED`; `RUNTIME_RLS_GRANT = NOT_VERIFIED`; `MAIN_MERGE_AND_DEPLOY = NOT_DONE`.

**Próximas acciones condicionadas:** validar rol runtime/DSN y migraciones antes de desplegar, insertar embeddings reales del fixture contractual+especificación con modelo registrado, conectar presupuesto/cronograma como evidencia estructurada por revisión al N8/ProjectGraph, y completar una única aceptación EPC real con N12 sin fallback, citas y UI. No ampliar a CAD/BIM todavía, no repetir auditorías ni journeys.
