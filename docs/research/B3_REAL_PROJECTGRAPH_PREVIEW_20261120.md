> **Actualización de seguridad / 20-11-2026:** una auditoría independiente impidió fusionar la PR #1281 por el riesgo de invocar nodos del grafo con posibles efectos futuros y por alterar el HEAD de la UAT #1276. Se cambió el preview para ejecutar **solo dos nodos reales y de lectura** del núcleo de ProjectGraph (`load_current_artifacts` y `align_entities`) mediante un grafo restringido compilado; los nodos `cross_doc_coherence`, `health`, `write_snapshot`, `alert_correlation` y `hitl_routing` **ya no se invocan** en el preview. Pruebas actualizadas: **15/15 PASS** en el VPS aislado, incluyendo el grafo restringido. Las referencias a nueve nodos de las secciones siguientes describen **un ensayo histórico anterior y ya sustituido**, no el comportamiento actual del código. **Decisión: NO-GO de fusión en #1276 durante la UAT.**

# B3.1 — ProjectGraph real, inventario de tres fuentes, sin aprobación ni score

**Fecha:** 20/11/2026. **Dictamen:** `PASS_LIMITED — GRAPH_RUNTIME_SOURCE_ONLY`. No es Complete Journey, no compara valores reales, no habilita la integración productiva.

## Código y pruebas realmente ejecutados

- Rama: `integration/b3-source-bridge-20261120`, basada en el HEAD de PR #1276 (`916808c5212e3dbc652407f35f3a17557623c06c`).
- Se reutilizan sin cambios los tres adaptadores ya existentes en las ramas de investigación: sidecar Docling para PDF, parser MPXJ para XER/MPP y filas de evidencia de presupuesto XLSX existentes en el núcleo.
- `apps/api/src/analysis/application/b3_source_inventory_bridge.py` reúne **referencias de revisión**, no textos ni filas numéricas para Score.
- **NUEVO:** `apps/api/src/analysis/application/b3_project_graph_preview.py` valida pertenencia tenant/proyecto, hashes, roles de evidencia no proyectada, duplicados y ausencia de Score/promociones. Luego invoca **`build_project_graph().ainvoke()` real** con `artifacts=[]`, `canonical_materialization_status=no_trusted_artifacts`, `structured_source_refs` recibidas, sin repositorio de snapshots, alertas, DB ni `structured_source_units`. No se alteró la ruta Celery `run_project_graph_once`.
- El preview es de diagnóstico invocable explícitamente. **No está conectado automáticamente a upload**, N4, N12 o ProjectGraph productivo.

## Ejecución aislada verificable en el VPS

- Copia **limpia** del código de GitHub y `venv` independientes: `/home/aigenadmin/aigen-hybrid-pilot/data/c2pro-b3-graph-preview`.
- No se modificó `/home/aigenadmin/repos/C2Pro`, otros worktrees, despliegues Railway/Vercel ni UAT.
- Python 3.12, entorno `ENVIRONMENT=test`, URL de base de datos **ficticia y no conectada**, clave JWT sintética; no se utilizaron credenciales productivas.
- Fixture: sidecar PDF + cronograma `FakeProject` mediante parser MPXJ (JVM no utilizada) + fila de presupuesto con UUID de revisión. **No es un ensayo sobre documentos EPC reales**.
- Resultado: **15/15 PASS** (`unittest`) incluyendo **el grafo LangGraph compilado realmente ejecutado**. Caso específico: `test_actual_compiled_project_graph_all_nine_nodes`.
- Comando reproducible en el entorno aislado, desde `apps/api` (requiere dependencias de prueba, no acceso a BD):
  `ENVIRONMENT=test B3_RUN_ACTUAL_GRAPH=1 PYTHONPATH="$PWD:$PWD/tests/unit/analysis" <venv>/bin/python -m unittest discover -s tests/unit/analysis -p 'test_b3_*.py' -v`.

## Observaciones directas del grafo real

| Nodo ProjectGraph | Estado |
|---|---|
| `load_current_artifacts` | OK, 3 referencias fuente |
| `align_entities` | OK |
| `cross_doc_coherence` | SKIPPED (sin TRUSTED artifacts) |
| `change_impact` | SKIPPED |
| `health` | OK como cálculo diagnóstico; **no** es aceptación de Coherence |
| `snapshot_delta` | OK sin cambios de artifacts |
| `write_snapshot` | SKIPPED |
| `alert_correlation` | SKIPPED |
| `hitl_routing` | SKIPPED |

Resultado externo del preview: `coherence_score: null`, `approved_artifacts: 0`, `trusted_promotions: 0`, `snapshot_written: false`, `alerts_written: false`. La aceptación de esas condiciones está incluida en las pruebas negativas. Cualquier emisión inesperada de score o snapshots hace fallar explícitamente el preview.

## Riesgos y bloqueos relevantes

1. **Sin runtime upload** para Docling/MPXJ: todavía no se conectan a `DocumentRevision` inmutable mediante la política real de subida. El parser actual de cronograma acepta XLSX; XER/MPP exigen un adaptador y permisos de formato específicos.
2. **Sin calidad contractual demostrada**: N4 v2/VS-2 #1280 y la visualización VS-1 #1279 permanecen en sus PRs independientes. Este trabajo no sustituye ni valida su código.
3. **Sin N12, HITL de aceptación ni Score**: no se ha probado el recorrido completo ni las cinco discrepancias contractuales sembradas.
4. **Docling solo apoyo**: el sidecar no debe reemplazar el texto base del parser PDF, ni certificar páginas originales por sí mismo. Calendarios MPXJ, ruta crítica y WBS requieren autoridad independiente.
5. **Escalado siguiente:** la aplicación ya dispone de `run_project_graph_once(..., structured_source_refs=...)`; pero **solo debe recibir el inventario** tras autenticación de revisión y tenant en sus casos de uso. Incorporar un nuevo proveedor, ejecutor de grafos o score paralelo sería innecesario.

## Próxima prueba de valor — única prioridad

**Caso funcional controlado en la integración vigente**: mismo proyecto y misma revisión seleccionada de PDF contractual + cronograma + presupuesto, con datos procesados por sus casos de uso de revisión; N4 candidato con citas, N12 crítico y revisión humana; ProjectGraph debe conservar fuentes, identificar discrepancias y distinguir `PROVISIONAL` / `NOT_ASSESSED` / `TRUSTED` sin alterar automáticamente Coherence.

No se han tocado ni descargado los expedientes privados de la nueva carpeta Drive; la búsqueda de documentos queda fuera de esta línea hasta que funcione el recorrido mínimo.
