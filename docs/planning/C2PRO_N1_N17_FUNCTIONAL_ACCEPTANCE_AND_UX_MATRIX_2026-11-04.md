# C2Pro CORE — Matriz de validación funcional N1–N17 y experiencia usuario
**Fecha:** 04/11/2026 · **Rama:** `feat/c2pro-core-pilot-20261104` · **HEAD examinado:** `92c2a60860ac98e337d8b9d4f62f10ee27363c36`

## Decisión ejecutiva

No crear N18 ni una segunda orquestación paralela ahora. Mantener los 17 **identificadores funcionales**; N13 y N14 comparten el nodo técnico `human_interrupt` y el grafo tiene un `enrichment_dispatch` auxiliar. Lo que falta es conectar fuentes verificadas, ejecución, síntesis de proyecto y salidas que el profesional EPC realmente pueda utilizar.

**Esta matriz no acredita aceptación de 17 nodos.** Distingue tres niveles de evidencia:
- **CÓDIGO:** nodo registrado y ruta de ejecución identificable.
- **PRUEBA AISLADA:** se ejercita con datos sintéticos, mocks o PostgreSQL privado; no prueba utilidad del modelo IA ni experiencia en producción.
- **ACEPTADO POR USUARIO:** proyecto EPC de cuatro documentos, IA real y resultados navegables, trazados y coherentes; **TODAVÍA NO** alcanzado para el conjunto.

### Evidencia actual sin inflar los resultados
- Una batería focalizada de 7 rutas de test de grafo, dependencias, enrutamiento, extracción/coherencia documental y HITL, job `1a04e1c76e824b23929a7e0e`, SHA `92c2a608...`: **76 PASS, 0 FAIL, 1 warning**, log SHA256 `13549444789de89b70c23b3a03612584249d5e4c9e33069325b1dec147ee8c9b`. Incluye dobles/mocks y PostgreSQL aislado, **no 76 comprobaciones semánticas de IA**.
- Integración piloto P0 contratos+presupuesto+cronograma+pgvector: job `ca9a4583a5354b56b98fbcd6` mismo SHA: **14 PASS**, también aislado.
- N4 Anthropic real anterior: ocho riesgos/citas, 8/9 observados, pero el oráculo EPC-05 abreviado tenía un defecto de evaluación; corrección en rama piloto NO revalidada comercialmente.
- N12 llamada real en run GitHub `41873943823`: tres hallazgos con citas de EPC-04, EPC-05 y EPC-07 en respuesta estructurada, pero `critique_notes` acabó en fallback `Automatic critique inconclusive.`. Corrección del normalizador validada offline, **NO nueva aceptación real** ni revisión experta del contenido íntegro de las explicaciones.
- N8 pgvector PostgreSQL: **1 PASS** con embeddings sintéticos de contrato y especificación, excluye revisión V2 propuesta; **NO** evaluación semántica de embeddings comerciales reales en los cuatro documentos.
- Railway `c2pro-api` tiene únicamente entorno `production`; API, Worker, Scheduler y Redis ONLINE en commit `34f1f67d`, **no despliegue del HEAD piloto**. `DATABASE_URL`/SUPABASE_URL configuradas pero redacted en MCP; los registros DNS confirman pooler Supabase `eu-north-1`, no ID de proyecto ni rol. La base Supabase accesible por MCP no contiene `document_source_units`, y `clause_embeddings=0`. **NO** autoriza asumir que se trata de la base usada por Railway.

## Matriz por identificador (qué sirve al usuario y qué falta)

| Nodo | Función real contrastada | Evidencia y estado | Criterio para aceptarlo por el usuario EPC |
|---|---|---|---|
| **N1** Ingesta | El nodo recibe **texto ya extraído**, comprueba longitud significativa y clasifica categoría de coherencia. El parseo PDF/XLSX y revisión ocurre en el worker previo. | **BÁSICO PROBADO** en tests; título «Document Ingestion» sobredimensiona su función. XLSX multih ojas/formatos y cobertura de origen no aceptados. | Cuatro originales y revisiones reconocidos, datos estructurados contados por hoja/fila, cobertura explícita, errores visibles. |
| **N2** Anonimización | Detecta y redacta PII en `anonymized_text`, conserva original en `document_text`. | **BÁSICO PROBADO**; pruebas email/teléfono. **DEFECTO DE INTEGRACIÓN**: N3 pasa el original a IA cuando clasifica; N4/N5 extraen del original. | Ninguna llamada LLM con PII sin justificación; usar proyección anonimizada y enlace de citas a evidencia original protegida por ACL. |
| **N3** Router | Tipo prevalidado evita IA; si no, clasificación, ruta contrato→N4, especificación/cronograma→N5, presupuesto→N9. | **RUTA PROBADA**; NO asegura anonimización en rama IA. Cronograma tratado como WBS y presupuesto como BOM: no equivale a conservar fuentes originales. | Cada documento llega al parser/esquema correcto; actividades y partidas originales llegan a N8 sin inventar WBS/BOM. |
| **N4** Risk Extractor | LLM de riesgos contractuales con citas y mitigación. | **IA REAL PARCIAL (8/9)**, con observación EPC-05 y límites de texto/filtrado. | Riesgos de contrato citados, omisiones y falsos positivos listados, sin declarar correcto un riesgo sin frase fuente. |
| **N5** WBS Extractor | Propone WBS de entregables/actividades a partir de texto mediante IA. | **IMPLEMENTADO/PRUEBA DE CÓDIGO**. No sustituye cronograma observado ni WBS aprobada. | WBS candidata diferenciada de actividades importadas; propuesta revisable y vinculada a IDs origen/fecha/precedencia. |
| **N6** Stakeholder Extractor | Extrae personas/organizaciones cuando existe tenant y fuente textual. | **IMPLEMENTADO Y TESTEADO**; no hay una lista real de actores del piloto aceptada. | Actores sin duplicados, roles justificados y procedencia documental; no inventar responsables. |
| **N7** RACI Generator | Genera matriz a partir de actores y WBS, o SKIPPED si faltan. | **IMPLEMENTADO Y TESTEADO**, dependencia fuerte de N5/N6. | Asignaciones coherentes, sin «A/R» inventados; estado propuesta/humano, no bloqueo del CORE si no hay suficientes fuentes. |
| **N8** Coherence Scorer | Calcula coherencia/fragmentos Health y puede usar cláusulas y pares pgvector por revisión. | **AISLADO PARCIAL**: datos estructurados XLSX y vector contrato↔especificación pasan pruebas separadas; falta comparar los cuatro documentos y asegurar evidencia genuina. | Contradicciones contrato–presupuesto, contrato–cronograma y contrato–especificación con 2 fuentes citadas, score solo si evidencia suficiente, estados NO_ASSESSED separados de 0. |
| **N9** Budget Parser | En el grafo usa `ParseBudgetUseCase` que entrega **BOM items** desde texto. | **IMPLEMENTADO/INCOMPLETO PARA EPC**: nueva persistencia `document_source_units` no alimenta directamente este nodo. | Partidas, cantidades, unidades, precios, fórmula, moneda, total por revisión; reconciliación numérica y divergencias vs contrato. |
| **N10** Knowledge Graph | Llama `build_project_knowledge_graph` para leer/generar grafo desde persistencia de proyecto. | **IMPLEMENTADO/TESTEADO**; el grafo lo ejecuta **antes de N17**, que persiste el análisis actual. Posible desfase con riesgos N4 no persistidos aún (hipótesis a demostrar). | Relaciones del proyecto actual, IDs de fuente y revisión, no solo entidades de ejecuciones anteriores. |
| **N11** Decision Intelligence | `DecisionPackageAssemblyService` compone score, riesgos, actores, WBS, BOM y citas. | **DATOS ENSAMBLADOS, NO INTELIGENCIA ACCIONABLE**: `evidence_links: []` siempre vacío; no recibe actividades ni partidas canónicas; carece de propuesta `acción/impacto/prioridad/responsable/plazo` estructurada. | 3–5 recomendaciones priorizadas con por qué, impacto EPC, acción concreta, quién debe decidir, estado y enlace verificable. |
| **N12** Critique | Revisa extracción, devuelve RETRY/HITL. | **NO ACEPTADO REAL**: tres hallazgos citados en llamada Anthropic real pero salida final fue fallback. Corrección posterior offline. | Dos omisiones y una interpretación falsa detectadas y explicadas con citas verificables, sin fallback y sin dar por válida una explicación incoherente. |
| **N13** Human Interrupt | Puerta de revisión/pausa; llama servicio HITL con procedencia por revisión. | **TESTS Y CÓDIGO**; UI final de pausa → decisión → continuación aún sin prueba de piloto 4 documentos. | Aviso legible de decisión pendiente y motivo, cita verificable; nunca aprobación tácita. |
| **N14** HITL Resume | Mismo nodo técnico N13, rama de resume y autoridad/checkpoint; **no es un motor adicional**. | **TESTS DE CONTINUACIÓN**; no validar por separado como si fuera agente autónomo. | Una aprobación/rechazo, reanudación sin duplicar la revisión ni cambiar tenant/revisión. |
| **N15** Citation Validator | Valida coincidencias en texto del documento para riesgos/WBS. | **IMPLEMENTADO/TESTEADO**; fuente local única, no comparación 2 documentos; N4 con texto original y N15 con texto anonimizado puede rechazar citas legítimas o perder correspondencia. | Abrir documento, revisión, página/fila/cláusula desde la alerta; estado FOUND/NOT_FOUND/UNASSESSED sin citas inventadas. |
| **N16** Final Assembler | Genera `final_report` a partir del estado del grafo, con resumen y detalles. | **ENSAMBLA ESTRUCTURA/TESTEADO**; interfaz de informe no consume necesariamente esta salida: “Current State” consulta endpoint de proyección y “Audit Report” recompone frontend desde dashboard, alertas, documentos y revisión. | Resultados N4–N15 realmente visibles en UI e informe descargable; ninguna discrepancia inexplicada entre N16, dashboard y exportación. |
| **N17** Save to DB | Persistencia de análisis, alertas y eventos con fencing, deduplicación y gating HITL. | **IMPLEMENTADO/TESTEADO**, el análisis contractual nuevo no está desplegado; no demuestra conservación del proyecto EPC 4 docs en Railway. | Recargar/salir/volver al proyecto y ver mismos resultados, revisiones, estados y links sin pérdida ni mezcla de tenants. |

**N1-N17 y S1-S8 NO son equivalentes.** `ProjectGraph`/Snapshot/Health son un segundo nivel transversal. Una ejecución de nodos documentales no acredita síntesis del proyecto ni UX.

## Defectos transversales clasificados por impacto de usuario

### P0 — Impiden acreditar CORE funcional útil

1. **Fuente fiable → nodo:** `ProjectState` no contiene por contrato las nuevas filas verificadas `document_source_units` de presupuesto y cronograma. N5 genera WBS, N9 BOM; N8/N11/N16 no consumen directamente esas filas como autoridad original. Corregir integración en los nodos actuales, no crear «Budget Agent» o «Schedule Agent» en paralelo.
2. **N12 real:** fallback posterior a respuesta del proveedor con tres findings citados. La corrección está en rama piloto y solo está validada offline. Una sola evaluación real al cerrar el recorrido, sin auditorías comerciales repetidas.
3. **N8 y N10 de proyecto:** interdocumental real de cuatro fuentes, revisiones vigentes y grafo coherente. Verificar explícitamente que N10 recoge la extracción más reciente pese a situarse antes de N17; si no, actualizar contrato/proyección o secuenciación.
4. **N11 + N16 → usuario:** las respuestas deben ser decisiones EPC y citas navegables, no solo `risk_count` y JSON. `DecisionPackageAssemblyService.evidence_links` está vacío por diseño; enlazar evidencia con permisos. La UI de informes actual usa endpoints/proyecciones diferentes; conectar contrato de salida y reconciliar.
5. **N2 → N3/N4/N5:** aplicar la versión anonimizada a **toda llamada de modelo** y mantener localizadores de la versión original para citas. Evitar el parche ingenuo que impide verificar las citas tras el redactado.

### P1 — Mejoras tras un piloto visible

- Ampliar XLSX a todas las hojas, BC3, formatos MS Project/P6, fórmulas verificadas, tablas técnicas y PDFs escaneados con cobertura. No presumir formato soportado.
- Convertir riesgos/incidencias en acciones priorizadas con responsable propuesto, plazo y decisión humana, no aprobación automática.
- Métrica de cobertura/calidad por documento; N6/N7 opcionales al principio si no hay roles probados.
- ProjectGraph/Health: comparar cambios entre revisiones y garantizar alertas persistentes que solo se cierran con evidencia y revisión.

### ¿Hacen falta nodos adicionales?

**NO N18 ahora.** Tres capacidades faltantes son mejor responsabilidad de componentes internos:
- **Source Evidence Adapter** dentro de la ingesta/preparación (N1/N3/N5/N9), no una nueva capa de agentes.
- **Cross-document evidence resolver** integrado con N8 + `ProjectGraph`, respetando autoridad de revisión.
- **Actionable decision presenter** dentro de N11/N16 + API/UI, con procedencia y estados.

Solo considerar un nuevo nodo cuando un camino de negocio verificable requiera una etapa independiente, con entrada/salida, autoridad, coste, fallos y razón para no implementarla en los existentes.

## Guion de aceptación por un profesional EPC: una sola prueba real

**Preparación:**
- Un proyecto EPC sintético; cuatro documentos originales y verificables: contrato con 9 cláusulas y oráculo existente; presupuesto XLSX con partidas y totales; cronograma XLSX con actividades/hitos/dependencias; especificación con requisitos y revisiones.
- Incluir contradicciones **inoculadas, conocidas previamente**: al menos una contrato↔presupuesto, una contrato↔cronograma y una contrato↔especificación. Registrar antes del ensayo qué cláusulas, importes o fechas deben aparecer. Sin datos confidenciales.
- Confirmar endpoint frontal/backend, tenant y DSN/rol de Railway, migración, estado de datos, modelo embedding, coste/llamadas autorizadas. No desplegar ramas aisladas a una base cuyo aislamiento/identidad no esté verificado.

**Secuencia que el usuario debe poder hacer:**
1. Crear proyecto, subir cuatro originales y consultar estado individual: extraído/observado/no evaluado; revisión y origen. N1–N3 y estructurados deben registrar qué parser se usó y cobertura por documento.
2. Abrir contrato: N4 riesgos con citas literales y N12 crítica con 3 hallazgos conocidos. Ningún fallback disfrazado de PASS.
3. Abrir presupuesto: partidas, unidades, moneda, suma y errores identificados en origen; abrir cronograma: hitos, predecesores y fechas. Separar fuente original de WBS/BOM generadas.
4. Abrir coherencia: N8 contradicciones sobre pares reales de fuentes y score solo si la dimensión fue evaluada. N10 relaciones de documento y revisión actuales, no anteriores.
5. Abrir resultados/decisiones: N11 propone acciones EPC concretas, N15 permite visitar evidencia, N13/N14 solicita revisión si corresponde; N16 informe que coincida con dashboard y N17 garantice que recarga conserva todo.

**Criterios de éxito duro:**
- Evidencias fuente verificables en 4/4 documentos, sin faltantes silenciosos.
- N4/N12 con matriz de verdad conocida y texto de citas; no inventar precisión/recall a partir de etiquetas sin analizar explicación.
- Contradicciones inoculadas de 3 pares documentales encontradas con ambos localizadores; si no, reportar exactamente qué dimensión es UNASSESSED.
- N11 al menos tres decisiones/recomendaciones materiales con fuente y propuesta concreta; sin dueño/plazo fabricados.
- UI real y export: se ven y se navegan los hallazgos; refrescar sesión mantiene estados y citas.
- No exposición entre tenants, no aprobación tácita, no puntuación ficticia `0` cuando no hay evidencia.
- Veredicto final `CORE_PILOT_ACCEPTED` **solo si** el recorrido completo se demuestra; de lo contrario `NOT_ACCEPTED` con primer bloqueo funcional.

## Orden de trabajo práctico (sin más auditorías globales)

1. Corregir **contrato de evidencias estructuradas N1/N3/N5/N9→N8**, usar unidades originales por revisión y preservar restricciones de anonimización/proveniencia.
2. Reconciliar **N8→N10→N11→N15→N16→UI**, con el mismo identificador de hallazgo/fuente y su revisión; añadir propuestas de decisión sin inventar autoridad.
3. Verificar N12 corregido y una sola prueba real completa de 4 documentos con IA. Crear/modificar únicamente lo que bloquee esa prueba, sin redespliegues de prueba por nodo.
4. Publicar en un entorno real pero aislado con los cuatro documentos sintéticos, comprobar UX y persistencia al volver a abrir el proyecto.

**No se han desplegado cambios**, activado IA adicional ni tocado `#1112`, `main`, Railway o Supabase al elaborar esta matriz. Claude sigue siendo escritor exclusivo de #1112; la propuesta de correcciones queda limitada a la rama CORE Pilot hasta que se coordine la integración.
