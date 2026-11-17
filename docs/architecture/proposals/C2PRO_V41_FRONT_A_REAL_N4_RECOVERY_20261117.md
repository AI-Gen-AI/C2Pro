# C2Pro V4.1 / Frente A — recuperación verificable del piloto N4 real (17/11/2026)

**Autoridad y alcance:** #1049 / PR #1255; read-only; ningún nuevo proveedor, cargo, intento N4, fusión ni despliegue.

## Evidencia fija

- [GitHub Actions #44007355327](https://github.com/AI-Gen-AI/C2Pro/actions/runs/44007355327) — SHA de la ejecución \`61df7648715085112ad41dacf61565e57725b710\` (FAIL por condición de salida del piloto, no por ausencia de recibos).
- Artifact \`c2pro-v41-real-evidence-61df7648715085112ad41dacf61565e57725b710\`, fichero \`real_analysis_evidence.json\` SHA256 \`549ca20b14549e7d74aee1452a33e43f8aa526036fb57a5d07cc83be55f61cad\`.
- Fuente pública SEC EX-99.1, PDF derivado de 73 páginas, NO el PDF original de biblioteca (94 páginas). Proyección N2 SHA256 \`cf8f4b7d5341b04b7aacd5532b45cf130dd689037412a08ed1e9f7e59bf555c4\`.
- N3 \`contract\`, 1 llamada OpenAI \`gpt-4.1\` SETTLED, 1.864 tokens entrada / 8 salida, coste estimado $0,003808.
- N4 24/24 ordinales 0–23: 24 recibos SETTLED con IDs distintos, 62.103 tokens entrada / 26.638 salida, coste estimado $0,390586. 142 candidatos PROPOSED, 142 finding_keys únicas y al menos 3 candidatos por ventana.
- Evidencia de cita: **50** \`EXACT_MODEL_SAFE_MATCH\` con texto y offset verificados contra la proyección N2; **92** \`NOT_FOUND_IN_MODEL_SAFE_SOURCE\` con quote y offset nulos. **0 aceptaciones humanas**. Coste conjunto estimado $0,394394; factura externa NO verificada.

## Causa raíz y corrección A

\`n4_incremental_store.commit_window()\` almacena todos los candidatos y un receipt SETTLED, pero marca la ventana \`BLOCKED\` si hay \`outstanding_references\` o si el proveedor informa \`window_examined=false\`. \`progress()\` cuenta solo ventanas de estado \`EXAMINED\`, por eso puede informar \`examined_windows=0\` y \`PARTIAL\` aunque todas las llamadas y candidatos se hayan persistido. Estado \`PARTIAL\` es conservador y **no debe forzarse a COMPLETE**.

En \`N4RunOutcome\` se añaden métricas **independientes** consultadas directamente a PostgreSQL, con RLS tenant/run: \`settled_receipt_windows\`, \`persisted_result_windows\` (ventana con receipt SETTLED + \`committed_at\` + digest findings) y \`blocked_result_windows\`. Un recibo SETTLED sin JSON parseable no cuenta como resultado persistido. No se han cambiado esquemas, ledger ni semántica de aprobación. El piloto registra estas tres métricas para siguientes ejecuciones **sin provocar una nueva**.

Script \`apps/api/scripts/reconcile_v41_n4_real_artifact.py\` permite recuperación read-only del archivo original y fuente N2, ambos con SHA exacta; reconstruye la partición en 24 ventanas y valida una a una las 142 identidades y 50 citas exactas con offset y pertenencia a la ventana. Rechaza recibos duplicados, alteración del offset, aprobación falsa, fuentes cambiadas y revisiones no coincidentes. **No puede recuperar las 24 filas originales \`n4_extraction_windows\` porque la DB scratch ya fue destruida, ni los textos JSON originales del modelo \`outstanding_references\` no archivados**. No inventar dichos campos.

## Handoff y gates

- **P0 recuperación financiera:** 24/24 recibos N4 liquidados y propuestas recuperadas; presupuestos sin reservas según artefacto. Frente B #1258 debe corregir la falsa diferencia float \`0.39439399999999997\` vs Decimal \`0.394394\`; \`N4_ANALYSIS_NOT_COMPLETE\` permanece real. No factura verificada.
- **N12:** BLOCKED — no se ejecutó en el piloto, no existe un checkpoint N12 del ensayo y cualquier llamada nueva exige autorización y presupuesto de CORE. Prohibido invocar la continuación facturable preparatoria.
- **HITL:** PARTIAL — 142 riesgos PROPOSED con 50 citas comprobadas y 92 sin literal; en esta entrega no existe sesión de usuario ni decisiones reales. Los tests STUB existentes no sustituyen UAT humano. No aprobaciones automáticas.
- **N8 / ProjectGraph / Coherence:** BLOCKED — no promover hipótesis ni asignar Score más alto por aceptar riesgo. Se necesita unión real de revisión humana, revisión original y fuente multifuente completa.
- **Complete Journey S1–S8:** NO-GO/UAT pendiente; ningún deploy/merge/autorización productiva.

**Regla de continuación:** cualquier nuevo gasto de proveedor es EXCLUSIVO de A/CORE, previa conciliación del ensayo ya pagado y autorización específica de CORE. Mantener PR #1255 DRAFT, flags productivos OFF y coordinación exclusivamente #1049.
