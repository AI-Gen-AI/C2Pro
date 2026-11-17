# C2Pro V4.1 — S2→S4, contrato A/B sin promoción (17/11/2026)

Estado: SOLO QA/offline. Coordinación canónica: issue #1049. A propietaria de PR #1255; B de #1257 y #1258. Ninguna fusión, despliegue, activación productiva o llamada de IA autorizada por este contrato.

## Responsabilidad

Frente A: fuente N1/N2, N3/N4, N12 solo tras GO CORE, preservación de hallazgos/revisiones, HITL y origen ProjectGraph. Frente B: reconciliación S2 financiera, source-manifest PostgreSQL S4, escrow Coherence y separación validado/pendiente. CORE: autorización de dinero, UAT, promociones y merges.

## Riesgo que cierra este contrato

El texto protegido N2 del contrato EPC SEC tiene SHA256 cf8f4b7d5341b04b7aacd5532b45cf130dd689037412a08ed1e9f7e59bf555c4. El filing PDF SEC original tiene SHA256 2370812124b5f42713153122fc45f1e5716dd85385d881bdd339bd87b9dced06. El archivo del usuario de 94 páginas es distinto y no está cotejado. B exige document_revisions.blob_hash ORIGINAL y run_id actual de proyecto PostgreSQL. Prohibido usar el SHA N2, el run_id de PG desechable, o un resultado financiero SETTLED como sustituto de la identidad S4.

## Entrega realmente ejecutada

Módulo apps/api/src/analysis/application/v41_s2_s4_handoff.py y CLI apps/api/scripts/emit_v41_s2_s4_handoff.py: leyendo únicamente el paquete original de 142 hallazgos facturados, atestados con SHA del documento SEC, producen un manifiesto con punteros SHA y posiciones, NO con el texto fuente o la interpretación del modelo.

- 142 propuestas, 50 citas localizadas en N2 y PDF SEC, 92 sin cita, 0 aprobaciones.
- validated_count = 0; pending_human_review_count = 142.
- N12 checkpoint real y canonical HITL review id: NULL; trusted artifact: ninguno.
- S4 Coherence: UNASSESSED_NOT_CALLED; llamada al proveedor S4: DENEGADA.
- original blob SHA de PostgreSQL, tenant/proyecto/run vigente, manifest sha B y score validado/pendiente: NULL / no evaluados.
- ProjectGraph promotion: DENEGADA.
- SHA canónico del manifiesto: 734067d997bd6f6086ca3d5d11eaa280febfca7a358a75f7c2c45b87d7f86cb4.

Ejecución privada sin proveedor: desde el directorio de evidencias protegido, usar PYTHONPATH apuntando a apps/api y ejecutar emit_v41_s2_s4_handoff.py con parámetro SHA exacto del paquete 7bf753a485a92b7fc096763f7fbf623a9a1c3de878c8efa0df84030041931b43. Nombre de entrada fijo n4_offline_review_packet_sec_verified.json; salida privada s2_s4_handoff_manifest.json con permisos 0600, sin sobrescritura. El paquete, citas y datos de análisis no se suben a GitHub.

## Condiciones que siguen pendientes

1. S2: N4 debe resolver su PARTIAL para aceptación completa; N12 requiere autorización de gasto y checkpoint auténtico, sin repetir 24 llamadas N4.
2. HITL: crear expediente inmóvil con tenant/revisión/generación/fencing, decisión individual humana autenticada por hallazgo y aprobación global posterior. Ningún riesgo validado automáticamente.
3. S4 de B: verificar inventario completo vigente por PostgreSQL con aislamiento repeatable read/serializable, source blob SHA real, pertenencia de cláusula a revisión; no falsificar agregados multifuente.
4. Solo resultados TRUSTED y decisiones autorizadas pueden contribuir a N8/ProjectGraph y scores; conservar validado/pendiente y nunca incrementar score por aceptar riesgo.

El manifiesto es explícitamente NONPROMOTABLE. No es CoherenceVerifiedProjectManifest, no proporciona CoherenceCallIdentity ni autoriza evaluar un único riesgo con proveedor, y no sustituye UAT ni factura externa.

Gates: S2-N4 procesamiento real PASS técnico / PARTIAL evidencial; N12 BLOCKED; HITL PENDING; S4 y Complete Journey NO-GO.