> **Actualización B3.1 — 20/11/2026:** el inventario sintético de contrato/cronograma/presupuesto **ya ha pasado por los nueve nodos del ProjectGraph compilado real**, en VPS aislado, sin artefactos TRUSTED, sin escrituras ni cálculo de Coherence (`null`). Se han ejecutado **15/15 pruebas PASS**, incluidas comprobaciones negativas de autoridad y una de ejecución real del grafo. Esto **no** es N4→N12 ni Complete Journey, y los parsers Docling/MPXJ siguen sin ruta de subida productiva. [Informe de la ejecución B3.1](B3_REAL_PROJECTGRAPH_PREVIEW_20261120.md).

# B3 — Integración mínima y segura de fuentes (20/11/2026)

**Estado: SOURCE_BRIDGE_PASS_LIMITED. No es un complete journey ni una implementación productiva.**

## Base y alcance

- Rama: `integration/b3-source-bridge-20261120`; basada directamente en la SHA UAT `916808c5212e3dbc652407f35f3a17557623c06c`, sin alterar esa PR, main, Railway ni Vercel.
- Se **reutilizaron sin rediseñar** tres componentes ya desarrollados en ramas de investigación: `docling_contract_candidate_adapter.py`, `docling_optional_table_sidecar.py` y `mpxj_schedule_candidate_adapter.py`.
- Se añadió un único adaptador de ensamblado `apps/api/src/analysis/application/b3_source_inventory_bridge.py`, que construye referencias de origen compatibles con el inventario `ProjectGraphState.structured_source_refs` y conserva estados sin evaluar.
- Presupuesto/BOQ: reutilizar `ExtractBudgetRevisionEvidenceUseCase` y `BudgetRowEvidence` del producto (XLSX). **No se ha duplicado el parser** ni instalado ERPNext.
- **Importante:** este paso recibe las salidas ya verificadas por sus use cases. No modifica los endpoints de subida, no arranca N4/N12, no produce `structured_source_units`, no alimenta Score ni persiste evidencias.

## Pruebas ejecutadas en VPS

Entorno: `/home/aigenadmin/aigen-hybrid-pilot/data/c2pro-b3-source-bridge-vps`, dependencias estándar de Python 3.12; `PYTHONPATH` aislado. HEAD de código ensayado: `8dc18c59298bcb61ebd3c996020436270ab93bac`.

**10/10 PASS**, `unittest`, sin modelo, sin base de datos y sin datos privados:
- circuito sintético real de funciones: `build_optional_table_sidecar` → `parse_verified_mpxj_candidates` con reader inyectado → filas presupuestarias con identidad de revisión → `assemble_b3_source_inventory`;
- continuidad del texto base cuando Docling presenta orden de lectura incompleto;
- pertenencia estricta a tenant/proyecto, hash del PDF y hash/formato de la revisión del cronograma;
- rechazo de WBS nativo no aprobado, promociones de autoridad, filas de presupuesto ajenas y localizadores duplicados;
- ausencia de texto contractual, score calculado, estado N4/N12 falsificado o efectos de escritura en el paquete resultante.

**Alcance limitado de las pruebas:** el reader MPXJ es inyectado con un `FakeProject` y el sidecar Docling con tablas simuladas; no hay JVM instalado en el VPS, no se procesó ningún MPP/XER real en este ensayo, no se ejecutó Docling nativo ni la aplicación web. Las pruebas con archivos sintéticos en otras ramas no se transfieren automáticamente a esta rama como validación funcional.

## Situación de las integraciones

| Fuente | Componente incorporado en la rama | Aún pendiente |
|---|---|---|
| Contrato y anexos PDF | Docling opcional en paralelo a parser PDF existente, solo tablas/celdas `ADVISORY_UNVERIFIED` | Activar en el use case tras verificación de la misma revisión y cobertura, con costes/latencia |
| Cronograma XER/MPP | MPXJ optional reader produce actividades, fechas y dependencias `CANDIDATE_UNVALIDATED` | Disponibilidad Java y habilitación explícita de formatos en upload policy, adaptador seguro a `ExtractScheduleRevisionEvidenceUseCase`, WBS aprobado |
| Presupuesto XLSX/BOQ | Se consume la forma de filas de `BudgetRowEvidence` existente | Usar fuente XLSX real seleccionada y vincularla en ejecución real |
| ProjectGraph | `structured_source_refs` de las tres familias como inventario sin autoridad | Enlazar con materialización de fuentes verificada, N4/N12, comparadores, alertas y Health/Score bajo sus gates actuales |

## No hay certificación inexistente

- Falta el contrato real + cronograma + presupuesto **del mismo proyecto y revisión**.
- La existencia de tablas Docling no prueba fidelidad de PDF; los candidatos MPXJ no acreditan calendarios/ruta crítica/línea base; las filas XLSX requieren hash y autoridad ya verificados por la aplicación.
- N4 v2/VS-2 PR #1280 no se ha fusionado ni se ha conectado al runtime por esta rama.
- N12, HITL, ProjectGraph scoring y Coherence Score siguen **sin ejecutarse** en B3.
- Todos los documentos privados permanecen en Drive. **No se ha accedido a contenido ni descargado ningún documento de la carpeta nueva** durante este trabajo; únicamente se inspeccionaron metadatos de carpetas.

## Siguiente gate recomendado, con la menor complejidad

**Un único journey aislado**: Documento PDF con hash → parser actual + sidecar Docling → N4 vigente/VS-2 si autorizado → revisión crítica N12 → filas cronograma/presupuesto de revisiones compatibles → ProjectGraph provisional → resultado visible, sin promoción a Score hasta verificación de autoridad. Reusar componentes de #1279 y #1280; no crear un segundo motor. La integración debe bloquearse cuando falta un anexo, la versión no coincide, el WBS no está aprobado o una fecha no es comparable, **sin perder los hechos previamente verificados**.

**Decisión:** rama B3 lista para QA de incorporación de formatos y puente seguro. No merge, no deploy, no UAT, no inferencias facturables.
