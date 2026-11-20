# VS-1: resultados N4 visibles y honestos (propuesta de intervención única, v1.1)

| Campo | Valor |
|---|---|
| Estado | **PROPUESTA v1.1.** Incorpora M3 (CORE: `GO con recortes`, implementación no autorizada) y M4 (alternativa C). **M1 (Codex) pendiente**: el código no se autoriza sin él. STOP vigentes: N4/N12 facturables, merge y despliegue UAT |
| Qué es y qué no es | Es un **hito de visibilidad**: el usuario distingue entre *resultados disponibles*, *análisis incompleto* y *análisis no ejecutado*. **No es** una validación de la calidad contractual. Esa la dan FG-0/FG-1 con oráculo (protocolo M2) |
| Evidencia | `docs/audits/evidence/2026-11-20-n4-visibility-probe/` y `docs/audits/evidence/2026-11-20-m5-sec-recovery/` |
| Base | `916808c5` (#1276, G4 PASS_LIMITED). Apilar sobre #1276 o esperar a su merge lo decide CORE **después de M1** |

## 1. Cambio mínimo (sin tablas, migraciones, flags ni cambios de prompt)

| # | Dónde (en `916808c5`) | Cambio |
|---|---|---|
| 1 | `n4_governed_bridge.py` | Si el run no es `COMPLETE`, lanzar `N4RunIncomplete(N4GraphBridgeBlocked)` con `run_id`, `status`, `windows_with_result`, `examined`, `blocked`, `total` y `stopped_reason`. Los candidatos no se cargan en el grafo |
| 2 | `nodes.py` (`risk_extractor_node`) | `analysis_blocker_code`: `N4_PARTIAL_RESULTS` o `N4_PRIOR_RUN_RECONCILIATION_REQUIRED`. Se mantiene terminado, sin HITL y con 0 riesgos en el grafo |
| 3 | `ingestion_tasks.py` (las dos listas blancas) | Admitir los dos códigos y persistir `analysis_n4_run_id` |
| 4 | `router.py`: estado del documento | Tres estados distinguibles: `RESULTADOS_PARCIALES` (hay candidatos), `CONCILIACIÓN_PENDIENTE` (guarda cross-generation) y `ANÁLISIS_NO_EJECUTADO` (sin inferencia; nunca "0 riesgos"). `retryable=false` en los dos primeros |
| 5 | `router.py`: lectura | Ampliar la consulta del GET de #1276 a cualquier documento del tenant, eligiendo el run por `analysis_n4_run_id` y la revisión vigente. **Añadir la cobertura por ventana**, que el GET actual no da (M4): `windows_with_result`, `examined`, `blocked` con `blocked_reason`, y `unresolved_refs`. Las citas se clasifican como `N2_EXACT_MATCH` o `NOT_LOCATED`, y el PDF siempre como `ORIGINAL_PDF_UNVERIFIED`. Además `approvable:false`, `severity:"UNASSESSED"` y `n12_status:"UNASSESSED"` |
| 6 | `apps/web/components/features/n4/N4FindingsPanel.tsx` (**nuevo**, ~90–140 líneas, alternativa C de M4) | Panel independiente de solo lectura. **No reutiliza `ReviewFindingsPanel`**: está acoplado a HITL (escrituras, `reviewRowId`, acciones) y un modo `readOnly` no aísla lo suficiente. Reutiliza el badge, los detalles y `apiClient`. Sin botones de decisión |
| 7 | `apps/web/app/(app)/projects/[id]/documents/page.tsx` (~15–35 líneas) | Texto de estado y enlace al panel. Documento seleccionado en la **URL**, para que la vista se mantenga tras recargar. El cliente generado solo se regenera para el contrato nuevo |

**Recortado respecto a v1.0** (M3 y M4): la extracción y refactorización de `ReviewFindingsPanel`, el campo `impact_model_proposed`, los detalles internos que el usuario no necesita y cualquier cambio en N12, AlertGenerator, Score o ProjectGraph.

## 2. Pruebas (PG desechable y stub; son técnicas, no funcionales)
1. Parcial (escenario A de la sonda): el estado muestra `RESULTADOS_PARCIALES` y `retryable=false`. El GET devuelve los 4 candidatos y la cobertura `windows_with_result=2/2, examined=1/2, blocked=1/2`, con la referencia abierta, 2 citas `N2_EXACT_MATCH` y 2 `NOT_LOCATED`.
2. Conciliación pendiente (escenario B sobre `916808c5`): 0 llamadas al proveedor, `CONCILIACIÓN_PENDIENTE` y `retryable=false`.
3. No ejecutado: documento sin runs → `ANÁLISIS_NO_EJECUTADO`.
4. Aislamiento: otro tenant, otro proyecto o una revisión superada reciben 404. Las lecturas no hacen llamadas y dejan ventanas, recibos y saldo idénticos byte a byte.
5. No regresión: los 13 tests N4 PG y los focales G4 de #1276 pasan sin cambios.

## 3. Aceptación observable (sustituye a la matriz de v1.0, según M3)

| Escenario | Condición obligatoria |
|---|---|
| Resultado parcial | La UI muestra los **4 candidatos reales de la BD de prueba**, cada uno identificable y con su causa |
| Cobertura | Se ve 2/2 ventanas con resultado, 1/2 EXAMINED, 1/2 BLOCKED y las referencias abiertas. Nunca "cobertura completa" |
| Citas | 2 "coincidencia exacta en N2; PDF original no verificado" frente a 2 "no localizada". Ninguna aparece como verificada en el PDF |
| No ejecutado | Mensaje `ANÁLISIS_NO_EJECUTADO`, nunca "0 riesgos" |
| Seguridad | Otro tenant, otro proyecto y una revisión obsoleta no recuperan nada |
| Acciones prohibidas | Ni aprobar ni rechazar; sin Retry cuando el bloqueo es por conciliación; las lecturas no alteran recibos ni presupuesto |
| Persistencia real | Navegador → API real → PostgreSQL, con recarga y nuevo login. **Sin MSW en la aceptación** |
| Evaluación humana | Una persona explica qué encontró N4, qué no se evaluó y qué hacer después |

**Regla antimaquillaje** (M3): tests verdes con el panel vacío = **FAIL**. Panel con datos simulados = **PASS técnico limitado**, nunca PASS de análisis contractual. El PASS funcional exige una ejecución real autorizada y contraste con el oráculo (FG-1, protocolo M2).

## 4. Pendiente antes de pedir GO de código
1. Dictamen **M1** (Codex) sobre §1–§2.
2. Decisión de CORE sobre apilar o esperar a #1276.
3. Sobre o autorización de trabajo para el código (PR DRAFT, sin merge ni despliegue).
4. Después, un preview aislado con stub para la aceptación de §3 (no es `UAT_DEPLOY`).
