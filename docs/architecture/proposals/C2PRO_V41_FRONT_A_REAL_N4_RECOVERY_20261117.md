# C2Pro V4.1 / Frente A — recuperación verificable del piloto N4 real (17/11/2026)

**Autoridad y alcance:** #1049 / PR #1255; read-only; ningún nuevo proveedor, cargo, intento N4, fusión ni despliegue.

## Evidencia fija

- [GitHub Actions #44007355327](https://github.com/AI-Gen-AI/C2Pro/actions/runs/44007355327) — SHA de la ejecución `61df7648715085112ad41dacf61565e57725b710` (FAIL por condición de salida del piloto, no por ausencia de recibos).
- Artifact `c2pro-v41-real-evidence-61df7648715085112ad41dacf61565e57725b710`, fichero `real_analysis_evidence.json` SHA256 `549ca20b14549e7d74aee1452a33e43f8aa526036fb57a5d07cc83be55f61cad`.
- Fuente pública SEC EX-99.1, PDF derivado de 73 páginas, NO el PDF original de biblioteca (94 páginas). Proyección N2 SHA256 `cf8f4b7d5341b04b7aacd5532b45cf130dd689037412a08ed1e9f7e59bf555c4`.
- N3 `contract`, 1 llamada OpenAI `gpt-4.1` SETTLED, 1.864 tokens entrada / 8 salida, coste estimado $0,003808.
- N4 24/24 ordinales 0–23: 24 recibos SETTLED con IDs distintos, 62.103 tokens entrada / 26.638 salida, coste estimado $0,390586. 142 candidatos PROPOSED, 142 finding_keys únicas y al menos 3 candidatos por ventana.
- Evidencia de cita: **50** `EXACT_MODEL_SAFE_MATCH` con texto y offset verificados contra la proyección N2; **92** `NOT_FOUND_IN_MODEL_SAFE_SOURCE` con quote y offset nulos. **0 aceptaciones humanas**. Coste conjunto estimado $0,394394; factura externa NO verificada.

## Causa raíz y corrección A

`n4_incremental_store.commit_window()` almacena todos los candidatos y un receipt SETTLED, pero marca la ventana `BLOCKED` si hay `outstanding_references` o si el proveedor informa `window_examined=false`. `progress()` cuenta solo ventanas de estado `EXAMINED`, por eso puede informar `examined_windows=0` y `PARTIAL` aunque todas las llamadas y candidatos se hayan persistido. Estado `PARTIAL` es conservador y **no debe forzarse a COMPLETE**.

En `N4RunOutcome` se añaden métricas **independientes** consultadas directamente a PostgreSQL, con RLS tenant/run: `settled_receipt_windows`, `persisted_result_windows` (ventana con receipt SETTLED + `committed_at` + digest findings) y `blocked_result_windows`. Un recibo SETTLED sin JSON parseable no cuenta como resultado persistido. No se han cambiado esquemas, ledger ni semántica de aprobación. El piloto registra estas tres métricas para siguientes ejecuciones **sin provocar una nueva**.

Script `apps/api/scripts/reconcile_v41_n4_real_artifact.py` permite recuperación read-only del archivo original y fuente N2, ambos con SHA exacta; reconstruye la partición en 24 ventanas y valida una a una las 142 identidades y 50 citas exactas con offset y pertenencia a la ventana. Rechaza recibos duplicados, alteración del offset, aprobación falsa, fuentes cambiadas y revisiones no coincidentes. **No puede recuperar las 24 filas originales `n4_extraction_windows` porque la DB scratch ya fue destruida, ni los textos JSON originales del modelo `outstanding_references` no archivados**. No inventar dichos campos.

## Handoff y gates

- **P0 recuperación financiera:** 24/24 recibos N4 liquidados y propuestas recuperadas; presupuestos sin reservas según artefacto. Frente B #1258 debe corregir la falsa diferencia float `0.39439399999999997` vs Decimal `0.394394`; `N4_ANALYSIS_NOT_COMPLETE` permanece real. No factura verificada.
- **N12:** BLOCKED — no se ejecutó en el piloto, no existe un checkpoint N12 del ensayo y cualquier llamada nueva exige autorización y presupuesto de CORE. Prohibido invocar la continuación facturable preparatoria.
- **HITL:** PARTIAL — 142 riesgos PROPOSED con 50 citas comprobadas y 92 sin literal; en esta entrega no existe sesión de usuario ni decisiones reales. Los tests STUB existentes no sustituyen UAT humano. No aprobaciones automáticas.
- **N8 / ProjectGraph / Coherence:** BLOCKED — no promover hipótesis ni asignar Score más alto por aceptar riesgo. Se necesita unión real de revisión humana, revisión original y fuente multifuente completa.
- **Complete Journey S1–S8:** NO-GO/UAT pendiente; ningún deploy/merge/autorización productiva.

**Regla de continuación:** cualquier nuevo gasto de proveedor es EXCLUSIVO de A/CORE, previa conciliación del ensayo ya pagado y autorización específica de CORE. Mantener PR #1255 DRAFT, flags productivos OFF y coordinación exclusivamente #1049.

## Paquete de revisión individual offline (ampliación Frente A, sin coste)

El comando `scripts/reconcile_v41_n4_real_artifact.py` acepta opcionalmente `--review-packet-out <ruta>` (además de las rutas y SHA exactas obligatorias). Ese JSON es **un borrador de presentación**, no un artefacto canónico N12 ni una sesión HITL autorizada.

- Preserva 142 propuestas identificadas por su `finding_key` original, ventana y revisión N2. Incluye explicación, categoría/impacto propuestos por el modelo y referencia a cláusula expresamente **no verificada**.
- Las 50 citas exactas se muestran con texto e intervalo de **N2**, no página del PDF original; las 92 no verificadas tienen cita e intervalo nulos, con motivo explícito. La salida no reconstruye ni inventa citas, cláusulas, JSON bruto del modelo o aprobaciones.
- Los estados son siempre `review_decision=null`, `review_recording_enabled=false`, `review_row_id=null`, `trusted_artifact_id=null`, `n12_checkpoint_id=null` y `projectgraph_projection_enabled=false`. Los nombres de acciones son únicamente el vocabulario ya soportado por el backend (`CONFIRMED`, `DISMISSED`, `NEEDS_INFO`, `CORRECTION_PROPOSED`), **no** una autorización para enviarlas sin identidad humana.
- El fichero se crea **solo si no existe** y con permisos `0600`, evitando sobrescritura y enlaces simbólicos de destino. No se adjunta a Git ni a artefactos públicos y no hay acceso de red.
- El paquete no puede conectarse a N8 o ProjectGraph hasta que el servicio real cree un candidato inmutable y su expediente autenticado con `artifact_id/version/hash`, revisión, tenant/proyecto, generación/fencing y N12 gobernado. Las decisiones individuales deben registrarse contra esa identidad y sus condiciones CAS de la API; `Aprobar todo` seguirá como control final separado. La aprobación de un riesgo nunca modifica automáticamente Coherence.

**Evidencia de esta ampliación:** 8/8 pruebas sobre el artefacto facturable original, incluyendo recálculo del fingerprint de hallazgo y rechazo de manipulación de categoría, cita/offset y aprobaciones ficticias. El JSON preparado en la copia privada de QA mide 201.920 bytes, SHA256 `1c0b2b775aef72b14ce552af4a63d14186129c0fbbce92c360c9c01df36e5df1`, 142 propuestas, 50 con cita N2 y 92 pendientes. El paquete de QA **no sale del VPS**.

## Comprobación adicional contra el PDF original de la SEC (sin proveedor)

El CLI admite `--original-sec-pdf` al producir el paquete offline. Verifica **SHA256 del filing original** contra el SHA aportado por el artefacto facturable, 224 páginas, cadena completa y ordenada de 73 marcadores `PDF_PAGE`/`SEC_8K_PAGE` dentro de N2 y pertenencia de cada cita a una única página de origen. Compara el texto en esa página utilizando primero coincidencia literal exacta y, si falla, **únicamente normalización de espacios** (no aproximación de palabras ni interpretación contractual). Si no coincide, la verificación se detiene. No se invoca el proveedor ni se crean estados HITL.

Sobre el filing 8-K auténtico SHA256 `2370812124b5f42713153122fc45f1e5716dd85385d881bdd339bd87b9dced06`, las **50/50** citas ya confirmadas en N2 también aparecen en su página de la SEC: **4 exactas únicas, 45 únicas tras normalizar espacios y 1 exacta repetida en la misma página**. Esa última recibe etiqueta de ambigüedad, no localización única. Las otras 92 propuestas siguen sin cita verificable. La paginación y la literalidad del archivo separado de biblioteca de 94 páginas **no han sido verificadas**.

El paquete de 142 fichas con trazabilidad de página se mantiene únicamente en el VPS privado, con modo `0600` y SHA256 `7bf753a485a92b7fc096763f7fbf623a9a1c3de878c8efa0df84030041931b43`. Su contenido es preliminar, no tiene `review_row_id`, credenciales de aprobación, sesión N12 ni permisos de promoción; no se publica en GitHub. Las dos pruebas nuevas de PDF original elevan a **10/10 las pruebas positivas y adversariales sobre las fuentes reales**, sin facturación. No confundir este control documental con N12, una factura auditada o UAT S1–S8.


## Guardia S8707 y ejecución privada de los CLI (checkpoint CORE 17/11)

La rama A introduce `scripts/v41_private_cli_paths.py` para impedir el uso de entradas/salidas arbitrarias: los comandos de preflight/ensayo solo admiten `$RUNNER_TEMP/c2pro-v41-{source,real}/sec_8k.pdf` y su directorio respectivo **en GitHub Actions**. El trabajo facturable permanece desactivado por workflow; esta restricción no abre llamadas al proveedor.

La recuperación privada de evidencia requiere **autorización de rutas independiente de los argumentos** de la CLI:

```bash
export C2PRO_V41_PRIVATE_EVIDENCE_ROOT="/directorio/privado/evidencia"
export C2PRO_V41_PRIVATE_OUTPUT_ROOT="/directorio/privado/salida"
# El directorio de evidencia debe contener estos nombres exactos:
# real_analysis_evidence.json, source_n2_protected.txt y, si se contrasta,
# sec_8k.pdf (filing original con SHA comprobado).
# El directorio de salida debe existir previamente; no usar producción.
```

El recuperador rechaza rutas fuera de esas raíces, nombres no autorizados, `..`, enlaces simbólicos de destino y sobrescrituras de resultados. La salida solo puede ser un JSON nuevo con permisos `0600`. No se imprimen ni publican los textos de la fuente o el contenido sensible de los 142 candidatos. Los dos directorios han de ser locales, privados y preparados por el operador; no conceder permisos de escritura al CLI sobre directorios del repositorio o producción.

**Evidencia de seguridad:** Quality Gate SonarCloud de PR #1255 pasó de Rating C a A tras corregir 5 incidencias `pythonsecurity:S8707` en recuperador, preflight y piloto. Existió además un aviso posterior de fallo de ejecución de un nuevo análisis Sonar, cuya causa no está disponible sin el registro de la tarea; no afirmar que el intento posterior terminó con PASS. Drift Guard y Secret Scan sobre código corregido `cfaf570a85c27543f1ef1ba913472caab39ce2a1` PASS.

**QA exacta del código corregido:** job Ops `b95cce0fb3ab4a67a382a5f1`, PostgreSQL temporal, `44 PASS / 19 SKIPPED`; 19 SKIP corresponden exclusivamente a fixtures privados (proyección N2 y paquete N4) que no se han vuelto a montar, no a fallos de pruebas. Log SHA256 `9e4b984cae766e002f5f09b1c52c1d3770a70c4f9d7d9e41486affb521ee4144`. No repetir las 24 llamadas N4 para remediar esa ausencia.

**N12:** estimación condicional GPT-4.1 ~0,17–0,41 USD para 80k–183k tokens de entrada y 1k–4.096 salida con tarifa interna conservadora 2 USD/1M entrada y 10 USD/1M salida. La configuración actual mantiene reserva de full source `C2PRO_LEGACY_AI_FULLSOURCE_RESERVE_USD=1.20` USD, separada del gasto efectivo. Solicitar a CORE autorización específica de **máximo una llamada y reserva tope 1,20 USD**, después de verificar prompt/tokens, cobertura real N4 y checkpoint, y coordinar idempotencia/coste con B. Ninguna autorización queda implícita en este documento.
