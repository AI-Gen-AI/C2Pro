# C2Pro Integration — Estado operativo I-01 (20/11/2026)

**Prioridad del propietario:** integración de software existente en C2Pro; no inventario, clasificación ni análisis de documentos históricos. El trabajo de corpus está cerrado en esta rama y depositado en un Drive privado. Se conservan pruebas antiguas sólo como evidencia secundaria.

## Estado funcional actual
| Área | Estado comprobado | Alcance y límites |
|---|---|---|
| Código MPXJ → candidatos Schedule | **IMPLEMENTADO EN RAMA EXPERIMENTAL** | `apps/api/src/documents/adapters/parsers/mpxj_schedule_candidate_adapter.py`; no conectado al router, composite parser ni upload policy |
| Tests unitarios | **PASS 10/10** | Windows, Python 3.11, `unittest`, fixtures en memoria/fakes; prueba de SHA incorrecto antes de parsear, UUID scope, tipo, deduplicación de UID, predecesoras, ausencia de fechas, limpieza de temporal, límite de tamaño y cero trusted |
| Smoke MPXJ real | **PASS** | `MPXJ 16.10` + `JPype1`, fuente XER sintética local con 4 tareas / 2 precedencias / 1 calendario; `CANDIDATE_UNVALIDATED`, `time_assessment=NOT_ASSESSED`, sin efectos ni promociones |
| Integración en API C2Pro y UI | **NO IMPLEMENTADA** | El stack existente solo admite planificación XLSX, `ExtractScheduleRevisionEvidenceUseCase` exige XLSX; los endpoints, migraciones y contratos de la aplicación no se tocaron |
| QA independiente | **SOLICITADA / EN CURSO** | Revisión de Gemini con SHA fijada y solo lectura; dictamen no asumido |
| Docling → parser estructural | **PENDIENTE I-02** | Implementar opt-in con comparación contra PDFFileParser actual; sin sustituir N4/N12 |
| ProjectGraph/Coherence/HITL | **SIN CAMBIOS** | Ninguna observación importada entra en la autoridad canónica |

## Ejecución
- Primer smoke nativo encontró error de inicialización JPype (faltaba registrar `mpxj` antes de `startJVM`); se corrigió en la rama y se repitió.
- Ejecución final observada: `{status:PASS, activity_count:4, predecessor_count:2, calendars_seen:1, trusted_promotions:0, effects_allowed:false, time_assessment:NOT_ASSESSED}`.
- Diez pruebas unitarias repetidas con `OK` en 0,120 segundos.
- **Importante:** lo anterior demuestra un *adaptador opcional ejecutable*, NO el viaje de usuario completo ni soporte de subida MPP/XER.

## Arquitectura y restricción decisiva
Se detecta que `apps/api/src/documents/domain/upload_policy.py` permite `.pdf/.docx/.xlsx/.bc3` (más WBS) y no MPP/XER; `CompositeFileParser` enruta schedule XLSX al ExcelFileParser; la prueba `ExtractScheduleRevisionEvidenceUseCase` opera con revisión XLSX cuyo blob ha sido verificado. Por tanto **activar subida sin un bridge a la autoridad de revisiones sería un bypass**. No ampliar extensiones, no escribir ProjectGraph y no afirmar fechas contractuales aprobadas.

## Próximo incremento I-01b (sólo tras QA y reconciliar SHA de rama activa)
1. Comparar baseline de esta rama (octubre) con código N4-only/UAT vigente; no rebase a ciegas.
2. Diseñar interfaz `native_schedule_candidate` desde `DocumentRevision` con bytes inmutables SHA-256, tenant, project, document/revision y validador de forma; nunca autorizar WBS por source code libre.
3. Aislar ejecución JVM/MPXJ con límites y diagnóstico seguro; feature flag desactivado y sin cambios en upload policy hasta pruebas de autorización.
4. Test e2e aislado: origen → puerto → candidata visible solo lectura con cobertura y `NOT_ASSESSED`; no llegar a `TRUSTED`, Score, HITL ni Alert por simple parsing.
5. Continuar I-02 Docling en paralelo solo en código aislado si no invade el camino principal.

**Resultado de esta intervención:** se corrigió el desvío de objetivos, se dejó un plan de integración y un primer adaptador ejecutable con pruebas. Nada se ha desplegado, aprobado como arquitectura definitiva ni fusionado.
