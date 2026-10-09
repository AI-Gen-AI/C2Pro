# PQ-HITL-04.1 — SDD de decisiones granulares y liquidación final

**Estado:** PROPOSED / PENDING INDEPENDENT DESIGN REVIEW · **Fecha:** 2026-10-08
**Tarea de producto:** PQ-HITL-04.1, padre PQ-HITL-04 / [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940), programa [#936](https://github.com/AI-Gen-AI/C2Pro/issues/936).
**Dependencia:** goldens PQ-HITL-09.1 (fixture draft #987), evidencia de riesgos de PQ-HITL-02.1 y crítica PQ-HITL-01.1 antes de implementar. Esta propuesta puede revisarse en paralelo sin afirmar que sus dependencias estén aceptadas.
**Autoridad:** Product MASTER YAML, ADR-020, ADR-026 y ADR-027; contratos ya fusionados PQ-HITL-04A/B/C, #714 y #758. Esta especificación no cambia ningún ADR, código, BD, token, revisión o estado en producción.

## 1. Qué tiene que poder hacer el usuario

En **una sesión documental HITL**, un revisor humano autenticado identifica cada riesgo y cada observación de la crítica en el texto original; confirma, descarta, pide datos o propone una corrección motivada. Estas decisiones se conservan como eventos inmutables. Las correcciones preparan un **nuevo candidato PROPOSED**, no mutan el anterior. La aprobación de la versión completa es otro acto humano expreso, sobre ese candidato exacto y tras revisar sus diferencias. Ningún botón de decisión individual ni cierre del último elemento concede automáticamente estado TRUSTED.

**Recorrido feliz:** documento/revisión → candidate digest + review row y thread/checkpoint → lista exhaustiva y estable de hallazgos → evidencia/source locator y decisión individual → composición/supersesión si hay correcciones → comprobación de pendientes → revisión humana de diff completo → aprobación/rechazo final exacto por #714/#758 → una sola transición atómica hacia TRUSTED o ninguna.

**Prioridad:** resultado profesional de extremo a extremo. Una pausa por candidato, no un interrupt LangGraph independiente por cada elemento. Esa reducción de interrupciones **no significa** aceptar automáticamente hallazgos sin revisión. La política cuantitativa de confidence y carga humana pertenece a PQ-HITL-02.2, todavía bloqueada.

## 2. Base de código efectivamente observada — no confundirla con producto final

- El dominio actual define kind RISK/CRITIQUE y actions CONFIRMED, CORRECTION_PROPOSED, DISMISSED, NEEDS_INFO, además de CandidateReviewIdentity con tenant/review_row/revision/artifact_id/version/hash/generation/fence/thread/checkpoint.
- La tabla public.hitl_finding_decisions usa eventos append-only, tenant-scoped, FK exactas, optimistic CAS por ledger_revision y clave idempotencia. El trigger consulta review row, candidate PROPOSED y processing authority. Es una base **provisional**.
- El writer y RecordFindingDecisionUseCase actuales admiten solo RISK como evento escribible; CRITIQUE todavía requiere envelope de evidencia tipada y membership. No prometer dos tipos operativos por la mera presencia del enum/schema.
- No hay flujo verificado para exponer endpoint HTTP con ACL real de proyecto, componer nuevas versiones corregidas y hacer finalización atómica de hallazgos en el mismo camino que #714/#758. Por ello el camino entero sigue INCOMPLETE.
- El writer aún debe demostrar login no privilegiado en el pool real; el predicado SQL por sí solo no identifica la credencial original frente a SET SESSION AUTHORIZATION. #985 es una corrección borrador, no habilitación operativa.
- ADR-026 permite reanudar con checkpoint exacto, o fallback restringido al mismo thread/lineage si no fue capturado. El ledger actual exige checkpoint_id no vacío: **no inventar un checkpoint** para cumplir el contrato. Requiere decisión explícita de compatibilidad antes de exponer la ruta granular.

## 3. Contrato de identidades e invariantes

El envelope de cada decisión debe estar construido por el **servidor** y enlazar:

- tenant_id, project_id, document_id, document_revision_id;
- review_row_id y estado revisable actual; authenticated reviewer_id y permiso de proyecto;
- artifact_id, artifact_version, artifact_hash del candidato **exacto**; source item ID, ordinal y stable_finding_id;
- finding_kind RISK/CRITIQUE sólo si su fuente/membership verificada está soportada;
- generation + fencing_token + autoridad vigente, thread_id y checkpoint_id concreto;
- idempotency_key, expected_ledger_revision, action, reason, proposed_text cuando proceda, source evidence seen y timestamps.

No aceptar tenant/reviewer desde el payload como fuente de autoridad. El id de un hallazgo no depende de su título editable. El reviewer debe ver la fuente del **mismo documento/revisión** que se autoriza. Clave idempotente reutilizada con contenido diferente = conflicto, nunca sobrescribir.

**GATE SECURITY:** autenticación real + identidad del actor obtenida del servidor + tenant RLS + ACL de proyecto/rol Contract Manager + DB connection con principal no privilegiado + trigger con tenant/candidate/fence + revisión CAS. **Todas** las rutas capaces de invocar `finalize_v3`, incluyendo la aprobación clásica, `POST /hitl/resume/{review_id}`, futuros endpoints y adaptadores de reanudación humana, deben comprobar el MISMO permiso de proyecto y registrar un aprobador humano autenticado. Sólo exigir `CurrentTenantId` o aceptar `approved_by=None` en una aprobación explícita no satisface la autorización humana. Hasta endurecer o deshabilitar la ruta directa legacy, el settlement granular debe permanecer desactivado. La ruta de finalización automatizada no-gated de ADR-026 es otra política, nunca se puede usar como bypass de un review marcado obligatorio. Ningún SELECT/INSERT por service_role/superuser disfrazado, ninguna ruta pública antes de pruebas reales de role grants, restricciones de session_replication_role y replay.

**GATE AUTHORITY:** PROPUESTA ≠ TRUSTED; todo evento individual es provisional, no concede autoridad de aprobación de informe, cambio contractual ni comunicación a proveedor. Nunca se cambia Health, Coherence, ProjectGraph o Current State desde un evento individual.

## 4. Máquina de estados — vista de producto derivada de eventos

El estado por hallazgo es una **proyección determinista** del último evento válido para el candidato exacto. El registro físico continúa append-only.

| Estado lógico | Evento o condición | Acción del usuario | Condición para cierre |
|---|---|---|---|
| UNREVIEWED | No decisión sobre finding_id en candidato actual | Ver evidencia y seleccionar acción | Bloquea final |
| CONFIRMED | Evento CONFIRMED | Mantener conclusión encontrada, con fuente visible | Decisión individual cubierta, pero no aprobación final |
| DISMISSED | Evento DISMISSED con reason | Descartar interpretación con motivo auditado | Decisión individual cubierta, pero no aprobación final |
| CORRECTION_PROPOSED | Evento + texto y reason | Proponer sustitución de la conclusión | **Bloquea** final hasta composición de candidato nuevo y nueva revisión humana |
| NEEDS_INFO | Evento + reason | Solicitar evidencia aclaratoria | **Bloquea** final, no cuenta como aceptación |
| STALE/SUPERSEDED | Digest/version/fence/thread/review cambia | No permitir nuevas decisiones sobre fuente antigua | Sólo lectura histórica, nueva revisión vinculada al candidato sucesor |
| FINAL_APPROVED/REJECTED | Acto humano de cierre global en control #714/#758 | Aprobar/rechazar candidata completa | Solo el approved exacto puede generar commit TRUSTED atómico |

**Regla crítica de supersesión:** eventos registrados bajo digest A siguen siendo evidencias inmutables de A; **no** se copian silenciosamente como decisiones válidas de un nuevo digest B. La composición debe generar B con mapeos de procedencia explícitos y exigir su inspección y aprobación final. Cualquier portabilidad propuesta de decisiones requiere algoritmo/política aprobados por revisor independiente. No resetear la auditoría para hacer B parecer sin historial.

**Revisión inicial/binding tardío:** #714 puede guardar candidate_binding después del interrupt original. La continuación del mismo checkpoint sin campo redundante todavía puede ser legítima si la identidad vive en revisión persistida. Dos bindings concretos con digest diferente se rechazan. Esta es compatibilidad de resume, no permiso para relajar checks de tenant/checkpoint/fence.

## 5. Invariantes del revisor y finalizador

1. Cada acción individual registra quién/cuándo/qué/por qué y qué fuente estaba disponible. CONFIRMED puede no requerir reason textual, pero nunca puede omitir identidad, candidato, evidencia vista y clasificación del hallazgo.
2. La tabla tiene evidence_refs JSONB, pero el writer actual no lo llena explícitamente en el INSERT. Por tanto **auditoría de fuente vista NO está demostrada**. Diseñar el envelope y prueba negativa antes de habilitar las operaciones reales.
3. La acción sobre CRITIQUE se mantiene fuera del writer hasta existir membresía inequívoca del critique observation en N12/N13, con revisión/fence/source. No usar el fingerprint RISK con un título o párrafo arbitrarios.
4. El reviewer sólo ve acciones finales habilitadas si cada item bloqueante del candidato actual tiene decisión terminal válida **y** no quedan propuestas de corrección sin materializar/needs-info, y la vista refresca el hash/diff vigente. El cliente no decide esto, el servidor revalida.
5. La firma global se ejecuta por el mecanismo trusted-state existente, con bloqueo/orden de autoridad de #758. **La solicitud humana liga `expected_ledger_revision`, review row, lista completa de hallazgos, candidate hash/version, revisor, checkpoint, generation/fence. En la misma transacción y después de bloquear la review row, el servidor reconsulta la revisión exacta y la proyección terminal de CADA hallazgo vinculada al digest actual**; rechaza si hay nuevas entradas, `NEEDS_INFO`, correcciones sin materializar, hallazgos sin decisión o binding obsoleto. El bloqueo de la fila compartida serializa append/finalización: los nuevos eventos no pueden introducirse entre comprobación y commit de TRUSTED. No introducir otro endpoint que actualice `trust_state` por separado ni un commit gate alternativo.
6. Nuevos retries, reconexiones, cancelaciones, fallo del worker, takeover, nueva revisión o expiración deben producir lectura histórica o rechazo, nunca reanudación del checkpoint ajeno.
7. No cambiar reglas de automatización no-gated sin decisión separada de ADR-020/PQ-HITL-02.2. Una observación unverified no puede desaparecer en N12 sólo porque el modelo dijo OK.
8. Denegación de acceso, stale digest, idempotencia conflictiva o fallo de red nunca deben ser tratados como acción humana satisfactoria.

## 6. Diseño de aplicación y aislamiento por paquetes

**04.2 Rol DB seguro:** provisionar/aislar LOGIN de escritura sólo en entorno autorizado, con test de conexión autenticada no privilegiada, grants mínimos, owner privilege y session_replication_role bloqueados; sin producción en esta etapa.

**04.3 Concurrencia ledger:** probar dos sesiones reales; misma clave y contenido exacto devuelve replay; misma clave distinta intención devuelve conflicto; distinta clave + stale CAS se deniega; tenant cruzado y stale candidate/fence/thread se deniegan **antes** de replay privilegiado.

**04.4 Acción HTTP + ACL:** contrato endpoint server-derived actor y project roles, validación de hash/finding/source, no trusted mutation. **Inventariar y endurecer TODOS los accesos a `finalize_v3`**: revisión crítica del `POST /hitl/resume/{review_id}` actual, que recibe `CurrentTenantId` pero no `get_current_user` en la función de ruta y construye la solicitud sin `approved_by`; negar o retirar esa ruta para decisiones humanas hasta que pruebe identidad y project/Contract Manager ACL. Incluye el endpoint `/queue/{item_id}/approve` aunque ya resuelva usuario, revisor y autorización de proyecto. Debe existir error tipado DENY / CONFLICT / STALE / SOURCE_UNRESOLVED sin filtrar identidad de otro tenant. UI no puede fingir éxito.

**04.5 Compositor de correcciones:** a partir de eventos y candidato A crea candidato B propuesto, único digest/version con diff y provenance, sin alterar A ni sus eventos. Correcciones incompatibles, NEEDS_INFO o ciclos fallan de forma visible. Cada corrección efectivamente aprobada por humano deja una referencia inmutable a una propuesta para el corpus golden según ADR-020, con fuente/redacción protegidas y anonimización gobernada. Registrar la intención idempotente al mismo settlement o en outbox atómico vinculado a `review_row_id+candidate_hash+ledger_revision`; la evaluación/promoción de un nuevo caso golden es independiente, jamás autoentrenamiento o autoconfianza.

**04.6 Liquidación global:** preview exacto B, confirmation explícita distinta, row/lineage/candidate/reviewer/**expected_ledger_revision**/CAS verificados en misma autoridad de #714/#758. Dentro de la transacción protegida por lock de review row, releer ledger y comprobar revision exacta + decisiones terminales de todos los hallazgos del candidato, antes de permitir una aprobación atómica única. Añadir evento/outbox idempotente para creación de candidato de corpus golden tras aprobar correcciones (ADR-020). Reintento no crea segundo TRUSTED ni dos casos golden.

**05.2/05.3 UX:** revisor ve fuente exacta antes de decidir, cuenta pendientes, razón del bloqueo y versión del candidato, con teclado/accesibilidad, estados error/reload/retry. No buttons de per-finding approval hasta implementar 04.4 real.

**09.2/09.3 QA:** contraejemplos de inyección, reviewer sin ACL, concurrente, simulado sin B PROD, clase de fuente no soportada, checkpoint ausente, late-binding, digest mutado y ejecución repetida; pruebas de UI y DB.

## 7. Matriz Given/When/Then mínima

| ID | Given | When | Then |
|---|---|---|---|
| HITL-DEC-01 | Candidato A propuesto, fuente RISK válida y reviewer autorizado | CONFIRMED con idempotency nuevo | Evento 1 append-only, sin cambiar TRUSTED |
| HITL-DEC-02 | Misma petición literal y key | Reintento | Replay del mismo event_id/revision, sin duplicado |
| HITL-DEC-03 | Misma key con acción/reason distinto | Reintento | CONFLICT, ledger intacto |
| HITL-DEC-04 | Dos sesiones esperan revision 0 | Ambas intentan insertar eventos distintos | Una revision 1, otra conflicto/retry controlado |
| HITL-DEC-05 | Item NEEDS_INFO abierto | Se pulsa firma final | DENY con motivo, no trust |
| HITL-DEC-06 | Propuesta CORRECTION_PROPOSED | Componer candidato B | A intacto, B PROPOSED nuevo, antiguas decisiones no autorizan B automáticamente |
| HITL-DEC-07 | Digest o fence cambia | Firma final vieja | STALE, no trust |
| HITL-DEC-08 | Proyecto de otro tenant | Buscar review o source | DENY/NOT FOUND sin fugas, no mutación |
| HITL-DEC-09 | Texto "auto approve" en contrato o en critique | Procesar/enviar decisión | Sólo dato no confiable, no acción ni autorización |
| HITL-DEC-10 | CRITIQUE sin membership tipada verificable | Decisión en endpoint | UNSUPPORTED/DENY, nunca fingir auditado |
| HITL-DEC-11 | Checkpoint faltante pero fallback permitido por ADR-026 | Intentar ledger que exige checkpoint no vacío | Elegir compatibilidad revisada o denegar granulares, jamás inventar ID |
| HITL-DEC-12 | Todas las decisiones válidas para B y firma humana real + expected_ledger_revision exacto | #714/#758 bloquea review row, revalida ledger y commit de B | Un TRUSTED exacto una vez, proyecciones recomputadas solo después |
| HITL-DEC-13 | Firma B cancelada / timeout / concurrencia perdida | Continuación | No trust, eventos/auditoría conservados, estado pendiente honesto |

| HITL-DEC-14 | Firma final visualizó ledger revision 4; otro revisor añade NEEDS_INFO en revision 5 antes del lock final | Firma final con expected revision 4 | CONFLICT, no TRUSTED; la vista debe recuperar revision 5 y bloquear |
| HITL-DEC-15 | Revisor sólo tiene pertenencia al tenant pero no rol de proyecto; ruta legacy /hitl/resume | Solicita approve con approved_by ausente | DENY, sin invocar finalize_v3; entrada alternativa no evita ACL |
| HITL-DEC-16 | Corrección B humanamente aprobada en ledger revision R | Reintenta settlement o job de feedback | Una sola referencia/candidato golden auditable, sin datos sensibles sin revisión, sin autopromoción |


## 8. Decisiones aún NO aprobadas que deben cerrarse durante 04.1

**D1 — Caducidad de decisiones tras corrección:** regla propuesta sin auto-copy de eventos entre digests; definir mapping y nueva revisión visible. Requiere aprobación de diseño.

**D2 — Checkpoint ausente en legado:** ledger granular exige checkpoint exacto pero ADR-026 permite fallback thread+authority. Propuesta segura: **no habilitar granular** sin checkpoint, preservar review legado por su camino actual. Una extensión con fallback requeriría SDD/ADR y tests especiales. No usar falso "checkpoint-only".

**D3 — CRITIQUE:** escoger envelope canónico de observaciones con source text, digest, ordinal y memberships auditables antes de soportar decisiones. Hasta entonces sólo RISK granular. La UI informa explícitamente de esa limitación.

**D4 — Evidence seen:** persistir evidencia real vista/locator en eventos; tabla permite evidence_refs pero la escritura actual no lo pasa. Decidir esquema/tamaño/versiones y confidencialidad antes de implementación.

**D5 — Scope de aprobación final:** reutilizar exclusivamente trusted-state finalizer existente, NO sin endurecerlo: exigir actor humano autenticado y ACL de proyecto/rol en **todos** los caminos de entrada incluido `POST /hitl/resume/{review_id}`; añadir expected_ledger_revision y revalidación de la proyección terminal bajo el mismo bloqueo/orden #758 antes del commit de TRUSTED. Hasta entonces **HOLD** operativo de decisiones granulares y liquidación. Evaluar mediante independent principal security review que nueva composición no invalida P0b ni crea una vía de aprobación lateral.

**D6 — Reviewer workload:** policy routing y capacidad humana todavía no validadas (PQ-HITL-02.2, #953 HOLD). La UX puede diseñarse sin cambiar umbrales.

## 9. Estado y gates de aceptación

Esto es una propuesta de SDD, **NO un ADR aceptado**, no cierra PQ-HITL-04.1 ni altera la implementación existente. Para pasar a ACCEPTED: (a) revisor principal independiente comprueba colisiones con ADR-020/026/027 y #714/#758, (b) decisiones D1–D6 resueltas con owner/arquitectura cuando corresponda, (c) casos Given/When/Then convertibles a contratos TDD por subpaquete sin roles falsos, (d) enlace al MASTER y CI de documentación, (e) ninguna autorización nueva de producción.

**Fuera de alcance:** mutation PROD, migration de B, grants de production, nuevos endpoints, corrección code/UX, replay manual de HITL, **promoción automática de modelos/skills** o cambio al trusted-state gate. ADR-020 **sí** obliga al handoff auditable de correcciones humanas aprobadas a candidatos de golden corpus (con privacidad y aprobación posterior); no se declara implementado. Un SDD nunca constituye revisión/consentimiento humano de hallazgos reales.
