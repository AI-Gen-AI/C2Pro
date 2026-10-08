# PQ-HITL-2026-01 — SDD de entrega por tareas y criterios de aceptación

**Estado:** PROPUESTA DE ESPECIFICACIÓN · no aprobada como implementación ni como PROD_VALIDATED
**Fecha:** 2026-10-08
**Autoridad:** MASTER machine validation/product/c2pro-master-product-control-v1.yaml, bloque product_quality_hitl_2026_10_08.delivery_specification.
**Vista humana:** docs/product/00-c2pro-master-product-control-v1.md §13.
**Épica:** https://github.com/AI-Gen-AI/C2Pro/issues/936 · tareas #937–#946.

Este SDD es el contrato técnico subordinado al MASTER. No crea un noveno Product WBS ni otro registro vivo de estados. Los 28 identificadores atómicos, estados, dependencias y roles viven exclusivamente en el YAML.

## 1. North Star observable

Una persona profesional carga contratos y documentos reales, identifica obligaciones, riesgos y diferencias respaldadas por la fuente, revisa cada hallazgo, confirma/descarta/propone correcciones con auditoría, aprueba una única versión final inmutable y obtiene Health, Coherence, What Changed y Current State consistentes. No debe requerir inspeccionar JSON, logs o GitHub para comprender el resultado.

**Contrato de producto, verificable en este orden:**

1. Cargar/seleccionar una revisión concreta con autenticación de tenant y proyecto; las 9 cláusulas de la revisión A y las 7 de B son accesibles en vista histórica/propuesta aunque no exista proyección TRUSTED_CURRENT.
2. Distinguir texto contractual verificado, interpretación del riesgo, comentario del crítico y evidencia UNKNOWN. Cita localizada no valida inferencia; no páginas, cláusulas ni confidence inventados.
3. Decisión humana por hallazgo CONFIRMED, CORRECTION_PROPOSED, DISMISSED o NEEDS_INFO; identidad real, motivo, pertenencia al candidato, revisión del ledger e idempotencia persistidas.
4. Construir nuevo candidato PROPOSED versionado sin reescribir el aceptado ni promocionar parcialmente un riesgo.
5. Un acto humano final separado sobre hash/versión/row/thread/checkpoint/generation/fence actuales; aceptación atómica o ninguna modificación TRUSTED.
6. Proyectar Health, Coherence, Alertas, relaciones y evolución sin confundir HISTORICAL, PROPOSED, TRUSTED_CURRENT, UNKNOWN, NOT_EXTRACTED y LOAD_ERROR.
7. E2E navegador + API + PostgreSQL real aislado, adversarial y negativo; QA y revisión principal independientes, UAT del dueño. P0c #686 y luego P0d #687 requieren además evidencias de producción y autorización específica. Nunca se utiliza B pendiente para fabricar un PASS.

**Horizontes:** primero integridad contractual e HITL; después P1 Project Controls bajo una sola WBS y Coherence cross-document; posteriormente Procurement Plan, BoQ, RFQ, ofertas, adjudicación y obligaciones vinculadas a WBS; finalmente PMO/portfolio e indicadores con pruebas de valor. #946 3D se difiere sin impedir el producto base.

## 2. Autoridades y responsables

Se ha comprobado que el repositorio tiene instrucciones históricas en roles/role_planner.md y .claude/rules/agents.md sobre blackboard y modelos fijos. Para el trabajo moderno rigen agents.md raíz, docs/DOCUMENTATION_AUTHORITY.md, .c2pro/control, .c2pro/roles y c2pro-dev-02-role-authority-v1.md. NO modificar blackboard.json ni backlogs históricos.

| Rol canónico | Responsabilidad sobre una tarea | Límite |
|---|---|---|
| orchestrator | Identificar QUÉ tarea es elegible, congelar SDD, aprobar scope, coordinar revisiones, reconciliar evidencia | No autoaprobar implementación, no inferir autoridad productiva |
| implementation_lead | TDD RED/GREEN/REFACTOR en WORK aislado, contrato API/BD/UI en rutas permitidas | No cambio directo en main, no autopromoción o self-merge |
| qa | Pruebas adversariales, real PostgreSQL de test, integración, accesibilidad y E2E | No confundir mock/CI con aceptación humana |
| security | Revisar login/pool/RLS, JWT, identidad, ACL, CAS, replay, triggers, prompt injection | No credenciales/grants de producción implícitos |
| independent_reviewer | Revisor real distinto del trabajador implementador; diffs+tests+evidencia y no narrativa | No editar mientras revisa, no autocertificación |
| specialist | Análisis de contrato, calibración/confidence, rendimiento, UX y alternativas puntuales | No autorizar merge ni sustituir revisor principal |

El rol es funcional y no equivale a un modelo. La selección de worker se hará en un WORK válido. El estado actual .c2pro/control/current.yaml es reconciled_idle; work-queue desarrolla C2PRO-DEV. La deuda C2PRO-DEV-14 trata soporte de envelopes de tareas PRODUCT: este plan NO activará un WORK PQ-HITL ficticio ni reescribirá el control-plane idle. Hasta habilitar dicho adaptador, el MASTER de producto + issues/PR/CI constituyen planificación y evidencia, NO una falsa asignación operativa.

## 3. Ciclo obligatorio: primero QUÉ, luego CÓMO

**D0 — identificar y clasificar.** Relacionar el síntoma con un resultado observable, padre PQ-HITL-01…10 y uno de ocho PWBS. Comprobar si es FEATURE, BUG, SECURITY, QA GAP, CI/INFRA o decisión de producto. No duplicar un identificador que ya existe.

**D1 — especificar.** Redactar Given/When/Then: expectativa, caso negativo, fuente/revisión, tenant, datos, criterio de salida y coste/capacidad. Si modifica confianza, propiedad de datos, persistencia, seguridad o autoridad, evaluar ADR-020/022/026/027/028 y congelar SDD/ADR independiente ANTES de código. Una incógnita se registra como BLOCKED, no se inventa una decisión.

**D2 — descomponer.** Cada paquete <=4 días focalizados; si se ve mayor, subdividir antes de implementar. Dependencias a subtask IDs y ownership funcional explícitos. Para arrancar se necesitan aceptación y WORK envelope vigente/legítimo, scope y rutas, principal implementador distinto del reviewer.

**D3 — RED/GREEN/REFACTOR.** Fijar prueba adversarial que falla; aplicar menor corrección posible; verificar suite dirigida, CI SHA exacto, contrato API↔UI↔BD y seguridad. Sin atajos de CI, sin mutar PROD ni candidatos TRUSTED. QA/reviewer comprueban la tarea completa, no solo la descripción de PR.

**D4 — cerrar por evidencia.** Resultado = ID + criterio logrado + prueba + SHA exacto + CI requerido + revisión independiente + defectos pendientes + riesgo residual + siguiente elegible. MERGED != ACCEPTED != DEPLOYED != PROD_VALIDATED. La sincronización Product Control se hace mediante reconciliación humana, nunca desde el informe del autor.

### Gestión del trabajo inesperado

- **P0_SECURITY_OR_TRUST:** parada de la ruta afectada, reproductor mínimo, test RED de bypass/fuga y revisión de seguridad. Escalar si el arreglo necesita modificar la política de autoridad.
- **P1_BLOCKS_ACCEPTANCE:** fallo que impide criterio del padre. Resolver en el mismo paquete solo si es local; si cruza dominio/permisos, abrir defecto hijo con ID, dueño, dependencia, estimate y test.
- **P2_LOCAL_NONBLOCKING:** registrar, aparcar y mantener prioridad del camino crítico. No optimizar UX secundaria con HITL roto.
- **ENVIRONMENT_OR_CI:** distinguir regresión de flake, permisos, proveedor, runner o test mal instrumentado; no suprimir gates ni degradar aserciones.
- **NEW_SCOPE_REQUEST:** regresar D0/D1. Sin añadir módulos, rutas, migraciones o dependencias por sorpresa.
- **Dos rondas diagnósticas acotadas:** si sigue desconocido, registrar trazas, marcar BLOCKED y cambiar de rol para revisión. No entrar en bucle de parches.

**WIP:** una tarea material de integración por workspace y hasta dos pruebas/especificaciones independientes. Un defecto no suspende automáticamente todo el proyecto, solo su ruta dependiente; el orquestador elige la siguiente tarea elegible en otra ruta. Tras cuotas agotadas de Codex, falta revisor principal válido: HOLD, no un simple cambio cosmético de etiqueta a Gemini.

## 4. Criterios técnicos detallados por iniciativa

### 01 · PQ-HITL-01 / #937 — Crítica fundada en contrato
- **01.1** Given N12 responde OK con observación no verificada y cita localizada, When evalúa el crítico, Then RETRY o HITL conserva el hallazgo y nunca lo convierte en TRUSTED automáticamente; el extractor en retry recibe preocupación+cita delimitadas y la tarjeta las muestra como UNVERIFIED. PR #960 es evidencia de implementación en revisión, no cierre.
- **01.2** Given §5.2 impone coste al Contractor y catorce días tras notificación escrita, Then las afirmaciones se contrastan semánticamente con obligación/tiempo/coste, no con mera subcadena. However, Conversely, LD y títulos legítimos no deben clasificarse como corrupción; fixture realmente corrupto sí alerta.
- **01.3** Medir en goldens tasa de falsas acusaciones de corrupción, trazabilidad de citas y convergencia de retries. Los umbrales se fijan antes de optimización; UNKNOWN no es PASS.

### 02 · PQ-HITL-02 / #938 — Evidencias y confidence
- **02.1** Cada riesgo tiene source evidence verificable de su revisión o localizador NO RESUELTO, con comprobación de tenant y candidato persistido. Prohibido rellenar clause_ref ficticio.
- **02.2** Dado per-risk confidence=null y artifact confidence_score=0.9, la UI indica NOT ASSESSED, no 90%. Diseñar fuente realmente calibrada o política de review acotado, medir carga humana y abstención. #953 queda en HOLD aunque CI esté verde: no es aceptable bloquear todos los contratos por falta de productor de confianza ni obviar HITL.
- **02.3** Riesgo que apunta a cláusulas 6.1, 6.3 y 6.4 retiene todos los enlaces sin inventar geometría ni mezclarlos con otra revisión.

### 03 · PQ-HITL-03 / #939 — Estado verdadero de evidencias
- **03.1** Con A=9 y B=7 persistidas y B pendiente, la vista muestra conteo histórico/propuesto y claramente ausencia de trusted-current, no "0 extraídas". Verificar API/frontend, RLS, relogin y no contaminación de Health/Coherence.
- **03.2** Diferenciar NO EXTRAÍDO / AUTORIDAD NO RESUELTA / HISTÓRICO / PENDIENTE / ERROR CARGA; datos y vacíos honestos por revisión.

### 04 · PQ-HITL-04 / #940 — Auditoría de decisiones y cierre atómico
- **04.1** SDD de estados y ADR de autoridad: fuente RISK o CRITIQUE, IDs inmutables, reviewer real, proyecto/tenant, razonamiento, evidencia, digests, optimistic CAS, idempotencia, coexistencia review legacy y completion binding tardío #714/#758. Ningún evento parcial es TRUSTED.
- **04.2** Validar conexión PostgreSQL **auténticamente restringida** separada de migrador. SQL current_user=session_user NO prueba login original frente a SET SESSION AUTHORIZATION. Forzar NO SUPERUSER/BYPASSRLS/CREATEROLE/REPLICATION, sin privilegio SET ON PARAMETER session_replication_role, dueño, trigger y destructive grants. Probar positivos/negativos y rol pool; #985 en revisión NO equivale a provisioning. Sin grants de producción.
- **04.3** Tests migrados de CAS concurrente, 2 sesiones, clave idem igual/diferente, review/evento ya existente, tenant cruzado, digest/checkpoint/gen/fence obsoletos, rechazo antes de replay y ausencia de TRUSTED parcial.
- **04.4** API decisión con JWT/reviewer, project ACL y pertenencia risk al candidato determinados por servidor; rechazo 403/409/422; operación deshabilitada hasta DB segura. #980 no se abre por tener helper writer.
- **04.5** CORRECTION_PROPOSED compone candidato PROPOSED nuevo, hash/versión nueva, auditoría y evidencia anteriores intactos; DISMISSED/NEEDS_INFO nunca se traducen en aprobación implícita.
- **04.6** Firma humana final separada sobre candidato completo versión/hash + row/thread/checkpoint/generation/fence + CAS; operación atómica, rollback completo si alguno falla, fail closed al retry/rechazo/fencing/takeover.

### 05 · PQ-HITL-05 / #941 — UX de revisión
- **05.1** Cita original, claim, source basis, revisión y estado LOCATED/UNRESOLVED mostrados directamente y marcados NO VERIFICADO. JSON no obligatorio; no falsos controles individuales.
- **05.2** Evidencia a un lado, decisión individual con razón/actor al otro, foco/teclado/permisos/red/error sin no-op; integración con API real de 04.4 y enlaces 06.2.
- **05.3** Vista resumen profesional: pendientes/aceptados/UNKNOWN, materialidad, diff candidato corregido y botones finales separados; bloqueos visibles antes del cierre.

### 06 · PQ-HITL-06 / #942 — Fuentes navegables
- **06.1** Contrato de resolución exacta: cláusula+revisión+span → raw verified span → documento fallback EXPLÍCITO → unresolved. Nunca inventar página/bbox. ACL tenant/proyecto.
- **06.2** Click en una cita abre la misma revisión y resalta únicamente contenido demostrado; multiclausal y cross-A/B, bbox ausente, permisos insuficientes y source not found probados.

### 07 · PQ-HITL-07 / #943 — Taxonomía y grafo
- **07.1** Separación cláusula/entidad extraída, interpretación de riesgo, alerta activa y relación. "0 alertas" no implica "0 riesgos" ni prioridad moderada; determinístico no significa model-backed.
- **07.2** Current trusted graph separado de proposed preview. No nodos/aristas fantasma; pruebas API/UI con ausencia de links, estados UNKNOWN y datos de distintas revisiones.

### 08 · PQ-HITL-08 / #944 — Historial y What Changed
- **08.1** Ciclo por revisión uploaded→parsed→extracted→proposed→review_pending→rejected/trusted; conteos históricos reales y relogin consistente.
- **08.2** What Changed y Current State sólo aceptan hechos según su autoridad; needs_review es observación provisional. P0c #686 y después P0d #687 necesitan cualificación PRODUCT independiente y aprobación humana.

### 09 · PQ-HITL-09 / #945 — Golden, regresión y aceptación
- **09.1** Congelar BEFORE fixes fixtures §5.2, However/Conversely/LD, título, 183 días, 5% de 132500 EUR, confidence null, A9/B7 sin trusted, fuente falsificada y otras negativas. RED primero y expectativas reproducibles.
- **09.2** Negativas PostgreSQL real: rol privilegiado, SET SESSION AUTHORIZATION, permiso especial de replicación, ledger real existente replay, RLS, CAS concurrente, stale checkpoint, injection y promoción parcial.
- **09.3** E2E con navegador/API/DB + relogin: contrato→riesgo→cita→decisión individual→corrección→candidato nuevo→firma final→timeline/Health/Coherence; también rechazo/cancelación/retry.
- **09.4** Paquete de salida: ID por tarea, SHA exacto, gates, revisión principal independiente, evidencias producto, defectos residuales, despliegues realmente observados si aplica y UAT explícita del propietario. No auto-PROD_VALIDATED.

### 10 · PQ-HITL-10 / #946 — Opcional
- **10.1** Gráfico 2D accesible primero y 3D únicamente con señal de valor real tras 09.4; no es requisito del primer producto evaluable.

## 5. Oleadas y definiciones de salida

| Oleada | Paquetes y secuencia | Exit |
|---|---|---|
| G0 · Entender y reproducir | 09.1, análisis de 02.2 y lectura scoped 03.1 | Goldens y contrato observable congelados |
| G1 · Verdad documental | 01.1→01.2→01.3; 02.1→02.3; 03.1→03.2 | Sin falsos OK, fuente honesta y A9/B7 reproducible |
| G2 · Autoridad de decisión | 04.1 SDD/ADR→04.2 rol seguro→04.3 concurrencia→04.4 HTTP | LOGIN real, CAS/RLS, ACL y revisión principal |
| G3 · Operador completo | 06.1→06.2; 04.5→04.6; 05.1→05.2→05.3; 07 y 08 | Review individual, candidato versionado y finalización real |
| G4 · Aceptación | 09.2→09.3→09.4 | Suite adversarial, E2E y UAT; no claims productivos sin #686/#687 |

En paralelo al cierre confiable P0b/c/d pueden detallarse tareas P1 de Project Controls/Coherence en **sus PWBS existentes**, pero no fusionarlas artificialmente con PQ-HITL ni desarrollar procurement y PMO antes de validar la fundación.

## 6. Relación entre tarea, PR, defecto y MASTER

**MASTER YAML:** status, tarea, owner role, dependencia, aceptación, tamaño, bloqueo. **Este SDD:** comportamiento Given/When/Then y límites. **Issue/PR/CI:** observaciones, cambio, historial, ejecución y review, siempre etiquetado con subtask ID. **.c2pro:** work envelopes y asignación REAL cuando sea viable, jamás reemplazando autoridad de producto.

Mensaje de avance recomendado: "PQ-HITL-XX.Y: esperado; implementado; aceptación sí/no; evidencia/red-green; defectos y decisión; siguiente tarea". Una PR puede contener un corte coherente, pero NO es el sujeto principal del reporte. Ninguna PR verde cierra por sí sola el GOAL.

**Prohibido sin autorización específica:** mutar base de producción, reprocess/decision de revisión B, conceder rol DB en PROD, promoción TRUSTED, despliegue, modificación de control-plane .c2pro para aparentar ejecución, 9º WBS, tests debilitados, 3D prematuro.
