# F1 — Evidencias públicas adicionales de contratos, cronogramas y precios — 20/11/2026

**Estado:** ENSAYOS LOCALES EJECUTADOS, LÍMITES DE CONFIANZA EXPLÍCITOS, SIN UAT O MERGE.  
**Rama:** `research/c2pro-integration-open-source-20261120`.  
**PC de laboratorio autorizado:** `%LOCALAPPDATA%\\AI-GEN\\C2ProOSSResearch20261120`; entornos virtuales separados para MPXJ/Docling.  
**Prohibido inferir de este informe:** calidad contractual N4/N12, Coherence Score, integración ProjectGraph, contratos completos con anexos, calendarios/baselines verificados, interrelación entre fuentes de proyectos distintos.

## A. Los tres PDF SolarMax solicitados (pendiente de sus bytes)
- `solarmax_ex991_original.pdf` — expedientes QA.
- `solarmax_SEC_EPC_full_text.pdf` — UAT.
- `solarmax_ex991_73page_sec_rendition.pdf` — recuperación SEC.
Búsqueda de nombres exactos y metadata `name contains` en Google Drive conectado: **sin resultados**. Búsqueda acotada a PC y VPS actual tampoco permitió establecer ruta/bytes verificables. Expedientes históricos mencionan versiones de 94, 51 y 73 páginas, pero **no se revalidaron los PDF ni los SHA en esta ejecución**. No se hizo ninguna comparación PDF↔PDF ni se afirmó que esas tres versiones correspondan a un mismo documento.

## B. Contratos EPC oficiales, directamente de SEC — Docling sobre HTML original
| Caso | Fuente oficial | SHA256 del HTML descargado | Tablas HTML | Tablas Docling | Marcadores recuperados | Tiempo local |
|--|--|--|--:|--:|--|--:|
| Longfellow BESS I / SolarMax, 31/07/2025 | https://www.sec.gov/Archives/edgar/data/1519472/000164033425001363/solarmax_ex991.htm | `0213CE2D545C38896251C3A7A96ADE6283A857AE3308440875E734F04A21EA34` | 78 | 78 | 8/8 | 1,930 s |
| Naguabo BESS / SolarMax, 31/12/2025 | https://www.sec.gov/Archives/edgar/data/1519472/000164033426000032/solarmax_ex991.htm | `B90A590E134E92059915E9B3D574A06F38FDEF9AEF756DB456B256AD4C3BEA60` | 83 | 83 | 8/8 | 1,792 s |

[Script reproducible](spikes/sec_epc_html_structural_eval.py) · [Resultados JSON](evidence/sec_public_contract_structural_eval.json).

**Marcadores chequeados (presencia de referencias, no extracción semántica):** secciones 2.5.5, 9.6, 4.3.1, art. 13, Exhibit C/D y Table C-1/D-2. Los dos documentos SEC corresponden a contratos distintos; no son versiones de un mismo contrato.

### ALERTA P0 — Cobertura falsa de anexos
La publicación HTML oficial del contrato Longfellow llega a la página de firma y **no incorpora después los anexos C/D/E con su contenido**. Naguabo sucede de forma comparable. Por tanto, recuperar referencias `Exhibit C` y `Table D-2` no demuestra haber analizado las tablas reales ni el presupuesto/cronograma. C2Pro debe declarar los anexos referenciados como `REQUIRED_BUT_NOT_PROVIDED` (pendiente de conseguir el original), sin generar de ellos hechos `trusted`.

Además, `html_tables` puede incluir tablas de maquetación; igualdad de cantidades (78/78, 83/83) no equivale a fidelidad celda a celda. Los marcadores son **indicadores de superficie**, no recall de obligaciones ni extractos anclados a PDF. Los HTML quedan en PC y el origen oficial se enlaza; no se suben contenidos contractuales completos al repo.

## C. Cuatro XER externos — MPXJ 16.10

| Fuente pública | Actividades en MPXJ | Relaciones en MPXJ | Resultado |
|--|--:|--:|--|
| [Stratum 4D demo](https://github.com/xunaidlnt-sudo/stratum-4d/blob/main/samples/demo.xer) | 19 | 14 | PASS de importación |
| [Project Toolkit demo](https://github.com/indrapandu/project-toolkit/blob/main/tools/p6-xer-viewer/sample.xer) | 30 | 27 | PASS de importación |
| [P6 Schedule AI sample](https://github.com/akhilkarthik/P6-Schedule-AI-Automation/blob/main/sample_schedule.xer) | 72 | 0 | PASS de importación, **sin precedencias recuperadas** |
| [Meridian EPC Level 3 demo 809 actividades](https://sketchdule.com/blog/xer-to-one-pager-screenshots) | sin resultado | sin resultado | **FAIL**: `org.mpxj.MPXJException`, línea 3 (causa Java: currencyName null) |

[Script](spikes/mpxj_public_xer_import.py) · [JSON](evidence/mpxj_public_xer_import.json).

Se distinguieron también filas `TASK` crudas: Stratum 14, Project Toolkit 24, P6 AI 64, Meridian 809. El recuento MPXJ incorpora nodos de estructura, por lo que no se debe interpretar 19/14 etc. como ganancia o pérdida de actividad sin comparación de identidades. Los ejemplos son **archivos públicos ilustrativos**; no se verificaron cronogramas reales/as-built, calendarios, baselines, recursos y lógica avanzada ni calendarios Primavera contra un segundo parser.

El fallo de Meridian se conserva: antes de alterar un XER para importarlo hay que comprobar si es inválido o hay un bug de compatibilidad. No editar automáticamente datos originales.

## D. Precios reales públicos — ODOT 2025
**Fuente oficial:** https://www.oregon.gov/odot/business/pages/average_bid_item_prices.aspx  
**ZIP descargado:** https://www.oregon.gov/odot/Business/Estimating/2025%20BID%20DATA%20PROGRAM.zip  
**Excel contenido:** `2025 - BID DATA PROGRAM.xlsx` (SHA256 `77D885090E5F75A30364B7349010A9F0A63F16B9736C9B419267DFD5AD996F65`).

La pestaña **BID ITEMS**, rango **B15:N114** (100 filas de datos), se leyó directamente desde el equipo autorizado: **100 partidas válidas, 18 contratos distintos, 0 discrepancias** para `cantidad × precio_unitario = importe_extendido` con tolerancia 0,02 USD.

[JSON de evidencia](evidence/odot_bid_data_100_rows_eval.json).

**Límite:** es un extracto de datos de licitaciones reales multi-proyecto, no un presupuesto completo de un EPC ni un compromiso contable o forecast. No emparejarlo con SolarMax ni usarlo para declarar diferencias de alcance de un proyecto ficticio.

## E. Dictamen
- **Docling HTML / lectura externa:** PASS técnico de ingestión de fuentes HTML originales, **PASS_LIMITED** para investigación contractual: no hay comprobación legal/semántica ni mapeo de citas a originales PDF.
- **MPXJ:** 3 importaciones externas PASS / 1 FAIL; requiere preflight, manejo claro de errores, oráculo de IDs y lógica de cronograma para pasar gate.
- **Datos económicos:** PASS aritmético acotado a 100 registros ODOT, sin BOQ completo comparable.
- **C2Pro N4/N12→ProjectGraph:** **NOT_TESTED**. No se han cambiado prompts, datos de producto, TRUSTED, HITL, Alerts ni Score.

### Gate para pruebas con los PDF originales
1. Localizar los **tres bytes PDF exactos** con fuente y autorización verificables. Registrar `SHA256, page_count, text_coverage, images, tables, page anchors` y deduplicación semántica de los tres; separar original vs conversiones y determinar si corresponden a un mismo contrato.
2. Repetir Docling contra el parser actual sobre los PDF idénticos y un oráculo independiente de cláusulas, anexos y páginas, sin pérdidas ni hallazgos inventados.
3. Obtener un P6 XER/MPP efectivamente exportado de un proyecto real anonimizando información si procede, y una BOQ/cost baseline del **mismo proyecto**; solo entonces ejecutar comparación transversal y relacionar obligaciones con WBS, fechas y partidas.
4. Registrar `MISSING_ANNEX`, `UNASSESSABLE` o `INSUFFICIENT_EVIDENCE` cuando proceda; no atribuir valor de producción a la presencia de menciones.
5. QA independiente y posterior decisión explícita antes de integrar. La alternativa integradora sigue siendo experimento aislado.

**Ningún merge/despliegue.** Se conservaron solamente resúmenes técnicos de fuentes públicas y scripts en esta rama.
