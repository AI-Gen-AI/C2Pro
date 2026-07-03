# C2Pro — Technical, Product, and Execution Improvement Proposal

**Autor:** Claude Fable 5 (Principal Eng / Lead Security Auditor / Product Architect)
**Fecha:** 2026-07-02 · **Rama:** `main` · **Método:** pase de evidencias sobre código vivo (≈40 verificaciones directas: git, CI, backend, frontend) + validación de 60+ documentos de `docs/audits/`. El código vivo es la fuente de verdad; las auditorías previas se trataron como hipótesis a falsar.
**Estado del repo verificado:** repo **PÚBLICO** (`AI-Gen-AI/C2Pro`), pack 284,85 MiB, 611 tests backend / 249 frontend, deploy-staging roto desde ≥2026-06-30.

> **Nota de alcance (2026-07-02):** esta versión añade la **§5.11 — Fase 2 de Producto: Suite de Aprovisionamiento (Procurement)** y las tareas `EPIC-PROC2-*` en §13, corrigiendo la omisión del roadmap Phase 2 (Procurement Plan, WBS, RfQ, BoQ, comunicaciones de stakeholders) señalada por el owner.

---

## 1. Executive Summary

- **Current technical maturity:** **6,5/10.** Monolito modular FastAPI/Next.js real y sofisticado (611 ficheros de test backend, 249 frontend, 14 evaluadores deterministas, gates CI reales de ADR-009/ADR-013/golden-corpus), pero con deuda operacional verificada: secretos en HEAD, deploy de staging roto, gates de cobertura decorativos en el job principal, e higiene de repo pobre (284,85 MiB de pack, 1.418 ficheros `.mypy_cache` trackeados).
- **Current product maturity:** **3/5 — Candidato a MVP.** El viaje E2E existe y se ha demostrado con documentos reales (contrato ADIF-AV → 14 riesgos fundamentados; incoherencia presupuestaria del 2,8% detectada en vivo el 2026-06-27). No es prototipo: es un MVP con bugs P2 en el loop y sin salida de informe.
- **Current production-readiness estimate:** **NO production-ready.** Dos bloqueadores duros: (1) `service_role` de Supabase + JWT secret + DATABASE_URL vivos en el HEAD de un **repositorio PÚBLICO** desde 2026-01-09; (2) el pipeline de deploy a staging lleva roto desde al menos 2026-06-30 (`RAILWAY_TOKEN` inválido).
- **Strongest current product wedge:** **Auditoría de coherencia tridimensional (Contrato + Cronograma + Presupuesto) con evidencia trazable y validación HITL, para Contract Managers de EPC.** El motor determinista de presupuesto ya funciona en vivo; TIME está cableado pero le falta profundidad determinista.
- **Main blocker to user value:** el loop no se cierra: no hay exportación de informe de hallazgos, la re-subida de documentos devuelve 500 (`TASK-DOC-REUPLOAD-005`), el borrado/reemplazo de presupuestos deja filas BOM huérfanas que corrompen la reconciliación (`TASK-DOC-BOM-ORPHAN-007`), y el gate LLM tarda ~8 min por evaluación (`TASK-COH-LLM-PERF-010`).
- **Main blocker to production safety:** secretos reales expuestos públicamente ~6 meses, con la allowlist de gitleaks (`^eyJ.*` en `\.env\..*$`) neutralizando deliberadamente el único gate que los detectaría; flags `C2PRO_AI_MOCK`/`C2PRO_SKIP_HITL` sin bloqueo en producción.
- **Recommended execution stance:** **Congelar features. Ejecutar Fase 0 (48h) de inmediato. Estabilizar el wedge Level-1 (30 días) antes de cualquier expansión.** El BUILD-GATE v3 ya vigente (no construir ADR-019/020/021 hasta uso semanal real) es correcto — mantenerlo. La Fase 2 de Producto (Procurement) queda enumerada pero diferida detrás del wedge.

---

## 2. Audit Inputs Reviewed

62 ficheros en `docs/audits/` (+3 en `Consenso/`), en 4 oleadas. Todos leídos o muestreados; los citados abajo se revisaron en detalle.

| Audit Source | Location | Status | Main Claims | Usefulness | Notes |
|---|---|---|---|---|---|
| `Consenso/Consenso_Claude.md` (Comité de consenso, 14-jun) | `docs/audits/Consenso/` | Leído íntegro | Secretos en HEAD; higiene; licencia; BCK-064; Celery+API; CI decorativa; refuta "re-init mayo" y "no hay evals" | **Muy alta** — el más riguroso; grados VERIFIED/REJECTED | Predata PRs #158–#182; varias preguntas abiertas quedan respondidas aquí |
| `Repository_Evidence_Pack.md` (14-jun, se autocorrige) | `docs/audits/` | Leído (cabecera+resumen) | v1 canónico / v2 shadow-proyección; secreto vivo en HEAD; `missing_dimensions` hardcodeado; backlogs en desacuerdo sobre BCK-064 | **Muy alta** — trazado a fichero/línea | Coincide ~95% con mi verificación |
| `C2Pro_CONSENSUS OF CONSENSUSES_Codex.md` (24-jun) | `docs/audits/` | Leído íntegro | Falta columna temporal/estado de proyecto; coherence ≠ health; wedge = overlay; congelar expansión | **Alta (estrategia)** | Sus 10 prioridades CTO se ejecutaron parcialmente DESPUÉS (thin spine v3, PR #158) — desactualizado vs código actual |
| `C2Pro_CONSENSUS OF CONSENSUSES_{Claude,deepseek,gemini}.md` (24-jun) | `docs/audits/` | Muestreados | Convergen con el de Codex | Media | Redundantes entre sí |
| `C2PRO_DEEP_Audit_*.md`, `C2Pro_Master_audit_Consolidation_*.md` (6 modelos) | `docs/audits/` | Greps dirigidos | Mismo corpus (shadow, BCK-064, CI, higiene) | Media | Capa intermedia ya sintetizada por los consensos |
| `Comite_DD_*.md`, `Sintesis*/Síntesis*` (7 modelos, 13–14-jun) | `docs/audits/` | Muestreados | Primera oleada DD; contiene errores luego rechazados (re-init, "no evals", "frontend shell") | Baja-media | Usar solo vía el Consenso |
| ADR Blueprints v3 (`Blueprint_*`, Challenger verdict) | `docs/audits/` | Muestreados | Diseño ADR-013..021 | Media | Ya ratificados como ADRs; superados por la implementación |
| Auditorías legacy (`API_AUDIT_*`, `PHASE1_*`, `PRODUCTION_READINESS_*`, `UX_AUDIT_*`) | `docs/audits/` | Listados | Inventarios endpoint/página antiguos | Baja | Obsoletas (4 meses, ~300 commits) |
| **Nota** | — | — | La carpeta `docs/audits/` de jun está **sin trackear en git** (`??`) | — | Recomendado versionarla (historia de decisión) |

---

## 3. Evidence Matrix

| Area | Audit Claim / Product Claim | Source | Live Code Status | Evidence | Severity | Confidence | Product Impact |
|---|---|---|---|---|---|---|---|
| Secretos | `.env.staging` con `service_role`, `anon`, `JWT_SECRET_KEY`, `DATABASE_URL` en HEAD | Consenso, Evidence Pack | **CONFIRMED** (agravado: repo **PÚBLICO**) | `git ls-files` incluye `.env.staging`; primer commit `0794753ce` 2026-01-09; `gh repo view` → `visibility=PUBLIC` | CRÍTICA | Alta | Desastre de confianza |
| Secretos | DATABASE_URL con password embebido | (nuevo) | **CONFIRMED** | check `://user:pass@` → `PASSWORD EMBEDDED: YES` | CRÍTICA | Alta | Acceso directo a BD |
| Secretos | `.gitignore` cubre `.env.*` pero el fichero fue commiteado antes | Evidence Pack | **CONFIRMED** | `.gitignore:31` `.env.*` + `!.env.example`; ya estaba trackeado | Alta | Alta | Falsa sensación de seguridad |
| CI/Seguridad | Allowlist de gitleaks neutraliza la detección del secreto | (nuevo) | **CONFIRMED** | `.gitleaks.toml:39-51`: matcher `^eyJ.*` sobre `files=["\.env\..*$"]`; `secret-scan.yml` usa `--no-git` | CRÍTICA | Alta | El gate "verde" oculta el incidente |
| Coherencia | v1 es el path canónico; v2 corre en shadow/proyección, no computa score | Evidence Pack, Consenso | **CONFIRMED** | `router.py:816-846` `_maybe_add_v2_dashboard`: `adapt_v1_dashboard()` + `ShadowRunner().compare()`; `config.py:355` `coherence_v2_enabled=False`, `shadow_mode=True` | Media | Alta | v2 consume trabajo sin valor de usuario aún |
| Coherencia | v2 shadow "quema tokens" de LLM | ChatGPT, Consenso | **REFUTED (matizado)** | `shadow_runner.py` hace `compare()`/`emit()` sobre dicts v1→v2; **no invoca LLM**. Coste = CPU/logging, no tokens | Baja | Alta | El riesgo de coste real está en el gate LLM |
| Coherencia | Falta dimensión SCHEDULE/TIME (BCK-064) → producto bidimensional | Consenso, Evidence Pack | **PARTIALLY CONFIRMED** | Routing arreglado: `graph.py:48-53` `_DB_DOC_TYPE_TO_REGISTRY={"schedule":"schedule_gantt"}`; PERO `scoring.py:236,306` aún `missing_dimensions or ["schedule","budget"]`; TIME sin evaluadores DET | Alta | Alta | "Tridimensional" es engañoso en la pata cronograma |
| Coherencia | Presupuesto no se reconcilia numéricamente | memoria proyecto | **REFUTED (ya resuelto)** | 14 evaluadores DET incl. DET-BUD-SUM/INTERNAL; demo viva 2026-06-27: 636M vs 654M (2,8%) | — | Alta | BUDGET es ahora la pata más fuerte |
| CI | `--cov-fail-under=0` en unit job | Consenso, Evidence Pack | **CONFIRMED** | `tests.yml:140`; `test_backend_ci_guards.py:19` **exige** que siga siendo 0 | Media | Alta | Regresiones de cobertura pasan el gate |
| CI | `continue-on-error: true` en gates reales | Consenso | **PARTIALLY CONFIRMED** | 3 ocurrencias: `tests.yml:213` (integration), `real-document-operability.yml:115`, `ai-agent-swarm.yml:160`. Existen gates duros (cov=70 en RDO, golden-corpus, ADR-009/013) | Media | Alta | Integration puede fallar sin bloquear merge |
| Infra | Celery worker + API en el mismo contenedor | Consenso | **CONFIRMED** | `start.sh:14-31` celery bg + `exec uvicorn`; `Dockerfile:103` `CMD ["bash","start.sh"]` | Alta | Alta | Un OOM del worker tumba la API |
| Cache | Cache LLM sin `tenant_id` → fuga cross-tenant | ChatGPT | **PARTIALLY CONFIRMED (2 caches)** | (a) Coherence cache `cache_keys.py:105` **SÍ** incluye tenant/project. (b) `prompt_cache.py:77-108` flash cache = **solo content-hash**, sin tenant | Alta | Alta | Riesgo real de servir respuesta LLM de otro tenant |
| Cache | ContentHashCache del gate coherencia sin tenant | (nuevo) | **PARTIALLY CONFIRMED** | `content_hash_cache.py:36` ns=`coherence.llm_gate:{key}`; tenant depende de que el `key` (clause_text) lo incluya | Media | Media | Colisión posible con cláusula idéntica |
| Runtime | Checkpointer cae a `MemorySaver` | ChatGPT/GLM/Claude | **CONFIRMED (mecanismo); impacto según deploy** | `workflow.py:303-349` fallback; `requirements.txt:32` instala `langgraph-checkpoint-postgres` → deploy estándar NO cae a memoria | Media | Alta | Benigno con requirements actual |
| Deploy | — | (nuevo) | **CONFIRMED roto** | `deploy-staging.yml`: `Invalid RAILWAY_TOKEN`; `No url found for submodule 'worktrees/sentry-perf-gemini'` | Alta | Alta | No hay despliegue automatizado funcionando |
| Repo | Gitlinks/submódulos rotos commiteados | (nuevo) | **CONFIRMED** | `git ls-files -s` modo 160000: `worktrees/sentry-perf-gemini`, `worktrees/sentry-perf/w5b-benchmarks`; sin `.gitmodules` | Media | Alta | Rompe checkout/deploy |
| Higiene | `.mypy_cache` (1.418), PDF cliente, dual lockfile, transcript | Consenso, Evidence Pack | **CONFIRMED** | 1.418 `.mypy_cache`; 7 PDFs incl. `HVPNL_First Contract`; triple lockfile; `codex resumen ultimo trabajo.txt` | Media | Alta | Pack 285 MiB; confidencialidad cliente |
| Licencia | Incoherente ISC vs Proprietary vs sin LICENSE | Consenso | **CONFIRMED** | `package.json:13` `"ISC"`; `README.md:7` badge "Proprietary" → `LICENSE` inexistente; sin `LICENSE` | Media | Alta | Ambigüedad legal/IP (repo público) |
| Duplicación | `coherence/` (canónico) vs `modules/coherence/` (legacy) | Consenso | **CONFIRMED (acoplados)** | `coherence/domain/entities.py:5` importa DE `modules.coherence`; también `modules/scoring`, `modules/decision_intelligence` | Media | Alta | No es dead code: retirar exige migración |
| Evals | "No hay eval framework / prompt registry" | Kimi et al. | **REFUTED** | `evals/run_evals.py`, `golden-corpus-evals.yml`, `prompt_registry.py`, gate golden en RDO:108 | — | Alta | Diferenciador real infravalorado |
| Producto | Falta columna temporal/estado de proyecto | Consensus of Consensuses | **PARTIALLY CONFIRMED (en construcción)** | Existen `src/temporal/`, `src/project_state/`, `src/change_intelligence/`, `src/health/` (thin-spine v3) | Media | Alta | La crítica motivó la spine v3 |
| Observabilidad | Sentry no cableado | Consenso | **REFUTED** | `main.py:12,138-147` `sentry_sdk.init(...)` con guard `BadDsn` | Baja | Alta | Cableado; solo falta DSN |
| Producto | 500s vivos en alerts/stakeholders (BCK-051) | Gemini | **INCONCLUSIVE** | `C2PRO_MASTER_BACKLOG.md:64`: drift reparado; correlación de logs bloqueada por acceso prod | Media | Baja | No reproducible sin logs prod |

---

## 4. Current Product Reality

### 4.1 What C2Pro Currently Is
Una **plataforma de inteligencia documental/contractual con andamiaje de proyecto**, no todavía una plataforma viva de inteligencia de proyecto. Centro de gravedad: subir documento → parsear → anonimizar PII → extraer riesgos/WBS/stakeholders → puntuar coherencia cross-document → gate HITL → persistir. Es real y demostrado con documentos EPC reales, no mockeado.

### 4.2 What C2Pro Is Trying To Become
Un **overlay de inteligencia de proyecto AI-native** sobre el registro documental EPC: detectar qué cambió entre revisiones, qué contradice, cuánto puede costar, quién debe actuar y cómo afecta a la salud del proyecto — con evidencia trazable. Los módulos `temporal/`, `change_intelligence/`, `health/`, `project_state/` (thin-spine v3) son el primer paso, correctamente bloqueados por un BUILD-GATE hasta que haya uso semanal real.

### 4.3 Actual End-to-End User Journey Available Today
Funciona (con fricciones): crear proyecto → subir documento (`documents/page.tsx` POST real → Celery `process_document_async.delay`) → análisis async → ver coherencia (`coherence/page.tsx` → `getDashboardSummary` real) → revisar en HITL (`review/page.tsx` → hooks `hitl` reales approve/reject) → dashboard persiste. **Rompe en:** re-subir documento (HTTP 500), borrar/reemplazar presupuesto (BOM huérfano corrompe reconciliación), y **no hay exportación de informe**. El gate LLM tarda ~482s.

### 4.4 Product Maturity Score
**3/5 — MVP candidate.** Evidencia: (a) loop E2E real demostrado (14 riesgos ADIF-AV; incoherencia 2,8% en vivo); (b) 22 rutas frontend autenticadas reales cableadas a APIs; (c) pero bugs P2 en el loop, sin salida de informe, y sin uso semanal recurrente. Por encima de "internal demo" (2); por debajo de "private beta" (4) porque el loop no cierra ni exporta valor.

### 4.5 Main Product Gaps
1. **No hay entregable exportable** (informe de coherencia/hallazgos).
2. **Loop de re-subida/versión roto** — impide el caso EPC central.
3. **TIME sin profundidad determinista.**
4. **Latencia del gate LLM** (~8 min).
5. **HITL no productizado** (colas por rol, owners, SLA).

---

## 5. Recommended Final Product Wedge

### 5.1 Near-Term Product Positioning
**"Auditoría tridimensional de coherencia contractual con evidencia trazable para EPC"** — no "AI Project Management", no reemplazo de Primavera/Procore. Detectar incoherencias Contrato↔Presupuesto↔Cronograma **antes** de que causen sobrecostes, con cada hallazgo respaldado por fuente/página/confianza.

### 5.2 Primary User Persona
**Contract Manager / Cost Controller de EPC** (beachhead con consenso STRONG; único rol con encaje de uso diario).

### 5.3 Primary Job-To-Be-Done
"Cuando recibo un contrato + su presupuesto + su cronograma, necesito saber en minutos dónde se contradicen y con qué evidencia, para actuar antes de firmar/certificar."

### 5.4 Level-1 Core Workflow
Crear proyecto → subir el **triplete** (contrato + presupuesto + cronograma) → análisis → **Coherence Score con desglose por dimensión (SCOPE/BUDGET/TIME/LEGAL) y hallazgos con evidencia** → revisar/corregir en HITL → **exportar informe de auditoría**.

### 5.5 Minimum Useful Product Loop
Subir triplete → score + top-N incoherencias con cita → validar 1-click → exportar PDF. Debe completarse **fiablemente** en **<3 min**.

### 5.6 Required Screens / User Flows
Ya existen (reutilizar): `projects/new`, `projects/[id]/documents`, `.../coherence`, `.../review`, `.../budget`, `.../evidence`. **Falta:** botón/flujo "Exportar informe" y estado "análisis en progreso" fiable para el triplete.

### 5.7 Required Backend Capabilities
Reconciliación DET BUDGET (✅) + TIME determinista v0 (⚠️ falta) + persistencia de revisiones (✅ `temporal/DocumentRevision`, cablear) + endpoint export informe (⚠️ falta) + fix idempotencia BOM (⚠️).

### 5.8 Required AI Capabilities
Gate LLM de aplicabilidad (✅) **paralelizado** (⚠️) + tracking de coste por tenant (⚠️ hoy `tenant_id=None`). Honest-null (✅, diferenciador). Prompts en inglés (⚠️ los R-* están en español).

### 5.9 Required Outputs / Reports
**Informe de auditoría de coherencia exportable** (PDF): score global + subscores por dimensión + tabla de hallazgos (severidad, dimensión, cita/página, confianza) + estado HITL. Este entregable convierte la herramienta en producto.

### 5.10 Success Metrics
- Tiempo triplete→informe < 3 min. · % hallazgos con evidencia = 100%. · ≥1 Contract Manager con **uso semanal** 4 semanas (desbloquea BUILD-GATE v3). · 0 P0/P1 abiertos en el loop core.

### 5.11 Fase 2 de Producto — Suite de Aprovisionamiento (Procurement)

Corrección de alcance: además del wedge de coherencia (Fase 1), el roadmap de producto contempla una **Fase 2 = Suite de Aprovisionamiento**: Procurement Plan, identificación de WBS, generador RfQ, generador BoQ y comunicaciones de stakeholders. Diferida detrás del wedge, pero **enumerada** aquí porque parte ya está construida y no debe perderse de vista.

**Estado real en código vivo (verificado 2026-07-02):**

| Capacidad Fase 2 | Estado | Evidencia | Gap |
|---|---|---|---|
| **Procurement Plan** | ✅ Código EXISTE, **gated OFF** | `procurement/domain/procurement_plan_generator.py`, `application/use_cases/build_procurement_plan_use_case.py`, `planning_service.py`, `customs_lead_time_calculator.py`, `incoterm_adjuster.py`; router gateado por `feature_rfq_generation=False` (`config.py:319`) | Habilitar flag, exponer router, UI |
| **WBS identification** | ✅ EXISTE y cableado | `wbs_router` siempre incluido (`main.py:314`); `procurement/application/wbs_generator_service.py`, `import_wbs_from_projects_use_case.py`; `feature_wbs_generation=True` | Endurecer/UX; sin gap funcional grave |
| **BoM generation** | ✅ EXISTE y en vivo | `procurement/application/use_cases/generate_bom_use_case.py`, `bom_builder_service.py`, `bom_validation_rules.py`; `feature_bom_generation=True`; alimenta la reconciliación DET-BUD | Productizar salida/UX |
| **RfQ generator** | ❌ **MISSING** | `grep RFQ/quotation` en `procurement/` = 0 resultados; el flag `feature_rfq_generation` es un misnomer que en realidad gatea todo el router de procurement | Implementar de cero |
| **BoQ generator** | ❌ **MISSING** (≠ BoM) | `grep BoQ/bill_of_quant` = 0; existe BoM (Bill of Materials), no BoQ (Bill of Quantities) | Definir si BoQ = BoM extendido o artefacto nuevo; implementar |
| **Stakeholder comms** | ❌ **MISSING** | `stakeholders/` tiene extracción + RACI + power/interest, pero no módulo de comunicaciones/notificación de stakeholders | Implementar de cero (reusar `notification_settings`) |
| **Stakeholder extraction + RACI** | ✅ EXISTE, gated | `stakeholders/application/extract_stakeholders_use_case.py`, `raci_router`, `generate_raci_use_case`; `feature_stakeholder_extraction=True`, `feature_raci_generation=False` | Productizar; habilitar RACI |

**Recomendación de secuenciación:** mantener la Fase 2 **diferida** hasta que el wedge Fase 1 tenga uso semanal real (mismo criterio que el BUILD-GATE v3). Cuando se active: **primero exponer lo ya construido** (Procurement Plan, WBS, BoM — bajo coste, alto valor) y **después** construir lo que falta (RfQ, BoQ, comunicaciones de stakeholders). Ver tareas `EPIC-PROC2-*` en §13.

---

## 6. Functional Gap Analysis

| Product Capability | Current State | Evidence | Gap | User Impact | Priority | Recommended Fix |
|---|---|---|---|---|---|---|
| Contract upload/import | ✅ Real | `documents/page.tsx:104` POST | — | — | — | — |
| Document parsing | ✅ Real (async) | `documents/router.py:152` `process_document_async.delay` | — | — | — | — |
| Clause extraction | ✅ Real | `analysis/adapters/graph` N4/N5/N6 | — | — | — | — |
| Risk detection | ✅ Real, fundamentado | Demo ADIF-AV 14 riesgos | Depende de registro de tools (hotfix 006) | Medio | P2 | Test de regresión de registry |
| Obligation detection | ⚠️ Parcial | reglas R-RESPONSIBILITY | Cobertura limitada | Medio | P2 | Ampliar reglas EPC |
| Coherence scoring | ✅ Real (v1) + DET-BUD | `scoring.py`, 14 evaluadores | v2 en shadow (sin score) | Bajo | P3 | Mantener shadow; no expandir |
| Schedule/TIME dimension | ⚠️ Routing ✅, scoring débil | `graph.py:48-53`; `scoring.py:236` hardcode; sin DET-TIME | Falta profundidad determinista TIME | Alto | **P1** | DET-TIME + quitar hardcode |
| Contract vs cost/schedule consistency | ✅ BUDGET; ⚠️ TIME | Demo 2,8% 2026-06-27 | Cross-check contrato EN/INR | Alto | P1 | Extraer totales EN/INR |
| Human-in-the-loop review | ⚠️ Mecanismo, no workflow | `review/page.tsx` hooks reales | Sin colas por rol/owner/SLA | Alto | P2 | Productizar colas (post-wedge) |
| Report generation/export | ❌ Ausente | solo `export_project_data` genérico | **No hay informe de hallazgos** | **Crítico** | **P0-producto** | Endpoint export PDF |
| Project/workspace org | ✅ Real | 22 rutas | — | — | — | — |
| Tenant isolation | ✅ RLS + coherence cache; ⚠️ flash cache | `cache_keys.py:105` ✅; `prompt_cache.py` sin tenant | Fuga posible flash cache | Alto | **P1** | `tenant_id` en flash cache |
| Auth/authz | ✅ Clerk JWT | `clerk_auth.py` | — | — | — | — |
| Frontend workflow completeness | ⚠️ Loop no cierra | re-subida 500, sin export | Ver bugs P2 + export | Alto | P1 | Fixes + export |
| Error handling | ⚠️ Mixto | honest-null ✅; 500 en re-subida | `tenant_id` faltante en DTO | Medio | P2 | `-005` |
| Observability | ✅ Cableado | Sentry `main.py:138` | Falta DSN | Bajo | P2 | Proveer DSN |
| Test coverage | ⚠️ Volumen alto, gate 0 | 611 tests; `cov-fail-under=0` | Gate no protege | Medio | P1 | Umbral escalonado |
| CI reliability | ⚠️ Deploy roto | `deploy-staging` fail | Sin deploy funcional | Alto | **P0** | Rotar token, fix submódulos |

---

## 7. Technical Risk Analysis

| Risk | Severity | Product Impact | Security Impact | Evidence | Immediate Fix | Long-Term Fix |
|---|---|---|---|---|---|---|
| `service_role`+JWT+DB URL vivos en HEAD de repo PÚBLICO | CRÍTICA | Brecha reputacional | Acceso total BD/bypass RLS | `.env.staging` trackeado; `visibility=PUBLIC`; `0794753ce` | Rotar TODO + purgar historia | Secret manager + gate fail-closed |
| Allowlist gitleaks oculta el secreto | CRÍTICA | — | Gate neutralizado | `.gitleaks.toml:39-51`; `secret-scan.yml --no-git` | Quitar allowlist `^eyJ.*`/`.env.*`; escanear historia | gitleaks en pre-commit |
| Deploy staging roto | Alta | Sin releases | — | `Invalid RAILWAY_TOKEN` | Rotar token GH secrets | Smoke-test post-deploy |
| Flash cache LLM sin tenant | Alta | Respuestas cruzadas | Fuga cross-tenant | `prompt_cache.py:77-108` | `tenant_id` en components | Auditar todas las keys |
| Celery+API mismo contenedor | Alta | OOM worker tumba API | DoS accidental | `start.sh`; `Dockerfile:103` | Separar servicio celery | Escalado independiente |
| Flags mock/skip sin guard prod | Alta | Fabricación silenciosa | Bypass HITL | `nodes.py:72-85` | Assert `not is_production` | Config fail-closed |
| `cov-fail-under=0` + test que lo fija | Media | Regresiones pasan | — | `tests.yml:140`; guard:19 | Subir a 60 + guard | Escalar a 80 |
| `continue-on-error` integration/full-suite | Media | Bugs mergean verdes | — | `tests.yml:213`, `RDO:115` | Quitar en integration | Gate duro |
| Submódulos/gitlinks rotos | Media | Rompe checkout CI | — | `git ls-files -s` 160000 | Eliminar gitlinks + worktrees | `.gitignore worktrees/` |
| Higiene: mypy_cache/PDF/dual lock | Media | Pack 285 MiB | PDF cliente HVPNL | 1.418 + 7 PDFs | `git rm --cached` + purga | CI guard |
| `modules/coherence` acoplado | Media | Doble mantenimiento | — | `coherence/domain/entities.py:5` | No tocar aún | ADR freeze-vs-migrate |
| Licencia incoherente (repo público) | Media | Ambigüedad IP | — | ISC vs Proprietary vs sin LICENSE | Decidir + LICENSE | — |
| Latencia gate LLM ~482s | Media | Loop inusable | — | `COH-LLM-PERF-010` | Paralelizar | Batch/async pool |

---

## 8. Phase 0 — Critical Security and Runtime Blockers / First 48h

### 8.1 Secrets in HEAD and Git History

| File | Variable | En HEAD | Tipo | Fingerprint (masked) | Riesgo | Remediación |
|---|---|---|---|---|---|---|
| `.env.staging` | `SUPABASE_SERVICE_ROLE_KEY` | **SÍ** | JWT god-key (bypassa RLS) | `eyJhbG…` | CRÍTICO | Rotar en Supabase YA |
| `.env.staging` | `SUPABASE_ANON_KEY` | **SÍ** | JWT anon | `eyJhbG…` | Alto | Rotar |
| `.env.staging` | `JWT_SECRET_KEY` | **SÍ** | Secreto firma HS256 | `c2pro-…` | CRÍTICO | Rotar (invalida tokens) |
| `.env.staging` | `DATABASE_URL` | **SÍ** | Postgres con password embebido | `postgresql://po…@…` | CRÍTICO | Rotar credencial BD |
| `.env.staging` | `SUPABASE_URL` | SÍ | Endpoint proyecto | `https://…` | Medio | Identifica el proyecto |

Agravante: **repo público desde 2026-01-09** (~6 meses). Asumir credenciales comprometidas.

**Plan (orden estricto):**

1. **Rotar antes de purgar:** Supabase → regenerar `service_role` y `anon`; cambiar password del rol Postgres; nuevo `JWT_SECRET_KEY`.
2. **Revocar/invalidar:** rotar el JWT secret invalida sesiones — coordinar. Revisar logs de acceso Supabase.
3. **Reemplazar** por variables del proveedor (Railway) o secret manager.

4. **Purgar historia:**

```bash
git filter-repo --invert-paths \
  --path .env.staging \
  --path apps/api/.env.test \
  --path "docs/assets/Pruebas/HVPNL_First Contract (Main Contents).pdf" \
  --path "docs/projects samples/Acuerdo terminacion Edificios Electricos IP fdo ambas partes.pdf"
```

5. **Validar post-purga:**

```bash
git log --all --oneline -- .env.staging   # vacío
gitleaks detect --source . --no-banner     # sin --no-git
```

6. **Force-push + coordinación:** `ALLOW_PUSH_MAIN=1 git push --force-with-lease origin main`. Avisar a colaboradores (re-clonar). Considerar hacer el repo **privado** durante la rotación.

### 8.2 Unsafe Runtime Flags and Fail-Closed Guard

- `C2PRO_AI_MOCK` y `C2PRO_SKIP_HITL` (`nodes.py:72-85`) sin bloqueo en prod. Añadir en arranque (`main.py` lifespan): si `settings.is_production` y cualquiera activo → **abortar arranque** (fail-closed).
- Corregir `deploy-staging.yml`: `RAILWAY_TOKEN` inválido + submódulo roto. Eliminar gitlinks (`git rm --cached worktrees/...`) y `worktrees/` a `.gitignore`.

### 8.3 Immediate P0 Acceptance Criteria

- [ ] `git ls-files | grep .env.staging` vacío; historia purgada; `gitleaks detect` (con historia) limpio.
- [ ] `service_role`, `anon`, `JWT_SECRET_KEY`, password BD **rotados** y verificados como no-válidos.
- [ ] Allowlist `^eyJ.*`/`.env.*` eliminada; `secret-scan` sin `--no-git`.
- [ ] Arranque `ENVIRONMENT=production` + `C2PRO_AI_MOCK=1` **falla**.
- [ ] PDFs de cliente purgados de historia.
- [ ] `deploy-staging` verde o desactivado hasta rotación.

---

## 9. Phase 1 — Core Product and Coherence Stabilization

### 9.1 Coherence Pipeline Current State

`scoring.py` (v0.3, decay exponencial, floor 5.0/ceiling 97.0, source-weighting) es el **path canónico v1** y es sólido. 14 evaluadores DET incl. DET-BUD-SUM/INTERNAL. Gate LLM de aplicabilidad funciona (async, observable — PR #177). v2 corre como **proyección shadow additiva**, **no computa score y no llama al LLM**. Dimensiones: SCOPE, BUDGET, TIME, LEGAL (+QUALITY, TECHNICAL en enum).

### 9.2 Schedule/TIME Dimension Analysis

- **Puntuadas hoy:** SCOPE y BUDGET con DET; LEGAL/TIME dependen del gate LLM. **BUDGET es la más fuerte.**
- **Dónde falta TIME:** (1) `scoring.py:236,306` hardcodea `["schedule","budget"]` en null-paths (legado BCK-064); (2) **no hay evaluadores DET-TIME**.
- **¿Llega el dato de cronograma?** SÍ tras el fix de routing (`graph.py:48-53`). El WBS se genera. No es problema de ingestión.
- **Minimal fix path:** (a) eliminar el hardcode y derivar de evidencia real; (b) añadir 2-3 evaluadores DET-TIME v0 (hito contractual vs fecha; duración total vs plazo; penalizaciones por retraso). **Es extensión de dominio, no reingeniería de ingestión.**
- **Regresión:** media — cubrir con `TS-UD-COH-SCH-001` (7/7) + nuevos tests DET-TIME.
- **Valor:** hace **honesta** la promesa "tridimensional".

### 9.3 Active vs Legacy Coherence Dependency Map
`src/coherence/` (canónico) **importa de** `src/modules/coherence/` (`application/ports.py:5`, `domain/entities.py:5`, `domain/rules.py:5`). `modules/scoring` y `modules/decision_intelligence` también consumen `modules.coherence`. **NO es dead code**: es una capa de dominio compartida viva. Retirarla exige mover entidades a `coherence/` o `shared_kernel/` primero → **ADR freeze-vs-migrate antes de tocar.**

### 9.4 Minimal Stabilization Plan
1. Quitar hardcode `["schedule","budget"]` en `scoring.py`.
2. Añadir DET-TIME v0 (2-3 evaluadores).
3. Extraer totales contrato EN/INR (`COH-BUD-RECON-006`).
4. Paralelizar el gate (`COH-LLM-PERF-010`).
5. Pasar `tenant_id` real a `anthropic_wrapper` (`COH-LLM-USAGE-011`).
6. **No** expandir v2 ni retirar `modules/` sin ADR.

### 9.5 Acceptance Criteria
- [ ] Triplete real → score con las 4 dimensiones; `score_missing_dimensions` refleja evidencia real, no hardcode.
- [ ] ≥1 incoherencia TIME determinista detectada.
- [ ] Gate LLM < 3 min sobre el contrato piloto.
- [ ] `ai_spend_current` por tenant refleja las llamadas.
- [ ] Suite coherencia verde; BUDGET (2,8%) sin regresión.

---

## 10. Phase 2 — Product Workflow and UX Completion

### 10.1 Current End-to-End Flow
| Paso | ¿Puede el usuario? | Evidencia |
|---|---|---|
| 1. Crear/seleccionar proyecto | ✅ | `projects/new`, `projects/[id]` |
| 2. Subir documento | ✅ | `documents/page.tsx:104` POST |
| 3. Disparar análisis | ✅ (async) | Celery `process_document_async.delay` |
| 4. Revisar coherencia/hallazgos | ✅ | `coherence/page.tsx` → `getDashboardSummary` |
| 5. Validar/corregir HITL | ⚠️ básico | `review/page.tsx` hooks hitl reales |
| 6. Generar informe útil | ❌ | solo `export_project_data` genérico |
| 7. Volver y ver resultados | ✅ | persistencia dashboard |
| 8. Límites de tenant | ✅ (caveat flash cache) | RLS + coherence cache scoped |

### 10.2 Missing User-Facing Capabilities
Exportación de informe de auditoría; re-subida sin 500 (`-005`); borrado/reemplazo de presupuesto sin BOM huérfano (`-007`); estado de progreso claro.

### 10.3 Proposed Level-1 UX Flow
Reutilizar las 22 rutas. Añadir: botón "Exportar informe" en `coherence/page.tsx`; estado "Analizando… (n/3)" en `documents/page.tsx`; fix del flujo de re-subida (revisión de contratos = caso EPC central).

### 10.4 Product Acceptance Criteria
- [ ] Contract Manager sube triplete y descarga PDF de auditoría, sin tocar la API a mano.
- [ ] Re-subir revisión de contrato no da 500 y crea `DocumentRevision`.
- [ ] Reemplazar presupuesto recalcula con filas correctas (sin huérfanos).
- [ ] Loop subir→informe < 3 min.

---

## 11. Phase 3 — Infrastructure, Multi-Tenancy, and Operational Cleanup

### 11.1 API / Worker Process Split
`start.sh` corre `alembic upgrade head` + Celery (bg) + `exec uvicorn` en **un contenedor** (`Dockerfile:103`). `deploy-staging.yml` ya intenta `railway up --service api` **y** `--service celery-worker` — la infra prevé el split; falta que cada servicio use su comando. **Propuesta:** un image, dos servicios Railway (API `uvicorn`, worker `celery`), migraciones en release/init step separado. Sin microservicios.

### 11.2 Cache Tenant Isolation
| Cache | File | Key | tenant_id | Riesgo | Fix |
|---|---|---|---|---|---|
| Coherence score | `coherence/cache_keys.py:105` | `coherence:{ver}:{ns}:{tenant}:{project}` | ✅ | Bajo | Ninguno |
| **Flash LLM** | `core/ai/prompt_cache.py:77-108` | SHA-256(model+system+messages+tools+temp) | ❌ | **Alto** | Añadir `tenant_id` a components |
| Coherence LLM gate | `coherence/adapters/ai/content_hash_cache.py:36` | `coherence.llm_gate:{key}` | ⚠️ implícito | Medio | Namespace con `tenant_id` explícito |

Patrón objetivo: `tenant:{tenant_id}:project:{project_id}:document:{document_id}:hash:{content_hash}`.

### 11.3 Repository Hygiene Cleanup
1. **Untrack:** `git rm -r --cached .mypy_cache` (1.418); `git rm --cached package-lock.json apps/web/package-lock.json` (mantener `pnpm-lock.yaml`); transcript; gitlinks worktrees.
2. **`.gitignore`:** `.mypy_cache/`, `worktrees/`, dual lockfile, `*.txt` raíz.
3. **Purga historia:** SÍ para PDFs cliente + `.env.staging` (mismo `filter-repo` de Fase 0).
4. **Validar:** `git ls-files | grep -c mypy_cache` = 0; `git count-objects -vH`.
5. **CI guard:** job que falle si reaparecen `.env.*`/`.mypy_cache`/dual lock.

### 11.4 Operational Acceptance Criteria
- [ ] API y Celery servicios separados; matar worker ≠ caída API.
- [ ] Flash cache con `tenant_id`; test no-colisión.
- [ ] `git ls-files` sin `.mypy_cache`/PDFs/dual lock.
- [ ] CI guard verde.

---

## 12. Phase 4 — CI/CD Hardening

### 12.1 GitHub Actions Gates
| Workflow | Step | Efecto | Cambio |
|---|---|---|---|
| `tests.yml:213` | Integration | `continue-on-error: true` | Quitar (gate duro) |
| `real-document-operability.yml:115` | Full suite | `continue-on-error: true` | Mantener solo si es tracking; documentar |
| `ai-agent-swarm.yml:160` | Artefactos | `continue-on-error: true` | Aceptable |
| `deploy-staging.yml` | Deploy | `Invalid RAILWAY_TOKEN` | Rotar + smoke-test |

### 12.2 Coverage Enforcement
`tests.yml:140` `--cov-fail-under=0` **y** `test_backend_ci_guards.py:19` exige que sea 0. Cambiar ambos a la vez: umbral **60** (ya usado en `e2e-security-tests.yml:122`; RDO usa 70 para core/ai). Escalonar 60 → 70 (día 30) → 80 (día 90). Validar: `pytest --cov=src --cov-fail-under=60`.

### 12.3 CI Acceptance Criteria
- [ ] Integration bloquea el merge si falla.
- [ ] `cov-fail-under >= 60` + guard actualizado.
- [ ] `deploy-staging` verde con smoke-test.
- [ ] Secret-scan escanea historia sin allowlist `.env.*`.

---

## 13. Prioritized Execution Backlog (WBS seed — todas las tareas con ID)

> IDs estables para el siguiente paso (WBS → SDD). Fuente: este informe. Effort: S≤1d, M 2-4d.

### EPIC-STAB-P0 — Security & Runtime Blockers (48h)
| Priority | Task ID | Dep | Task | File(s) | Effort | AC |
|---|---|---|---|---|---|---|
| P0 | `TASK-STAB-SEC-01` | — | Rotar TODOS los secretos de `.env.staging` (service_role, anon, JWT, DB pwd) | Supabase/Railway | S | Viejas creds no autentican |
| P0 | `TASK-STAB-SEC-02` | SEC-01 | Purgar `.env.staging` + PDFs cliente de historia (`git filter-repo`) | git | S | `git log` limpio; gitleaks OK |
| P0 | `TASK-STAB-SEC-03` | — | Quitar allowlist `^eyJ.*`/`.env.*` de gitleaks; escanear historia | `.gitleaks.toml`, `secret-scan.yml` | S | Escaneo detecta secretos |
| P0 | `TASK-STAB-SEC-04` | — | Fail-closed prod para `C2PRO_AI_MOCK`/`SKIP_HITL` | `main.py`, `config.py` | S | Arranque prod aborta con flag |
| P0 | `TASK-STAB-INF-01` | — | Fix `deploy-staging` (RAILWAY_TOKEN + submódulos/worktrees rotos) | `deploy-staging.yml`, worktrees | S | Deploy verde |

### EPIC-STAB-P1 — Coherence & Tenant Stabilization
| Priority | Task ID | Dep | Task | File(s) | Effort | AC |
|---|---|---|---|---|---|---|
| P1 | `TASK-STAB-COH-01` | — | Quitar hardcode `missing_dimensions` + DET-TIME v0 | `coherence/scoring.py`, rules | M | 4 dimensiones evaluadas |
| P1 | `TASK-STAB-COH-02` | — | Paralelizar gate LLM (ex `COH-LLM-PERF-010`) | coherence gate | M | Loop < 3 min |
| P1 | `TASK-STAB-SEC-05` | — | `tenant_id` en flash cache LLM | `core/ai/prompt_cache.py` | S | Test no-colisión cross-tenant |
| P1 | `TASK-STAB-UX-01` | — | Endpoint + UI export informe auditoría PDF | `coherence/router.py`, web | M | Contract Manager descarga PDF |
| P1 | `TASK-STAB-CI-01` | — | `cov-fail-under` 0→60 + actualizar guard | `tests.yml`, `test_backend_ci_guards.py` | S | Gate en 60 |
| P1 | `TASK-STAB-INF-02` | — | Split API/Celery en 2 servicios Railway | `start.sh`, Dockerfile, Railway | M | Matar worker ≠ caída API |

### EPIC-STAB-P2 — Product Loop / Ops
| Priority | Task ID | Dep | Task | File(s) | Effort | AC |
|---|---|---|---|---|---|---|
| P2 | `TASK-STAB-COH-03` | COH-02 | `tenant_id` real a `anthropic_wrapper` (coste, ex `COH-LLM-USAGE-011`) | `core/ai/anthropic_wrapper.py` | S | Coste por tenant ≠ 0 |
| P2 | `TASK-STAB-COH-04` | — | Totales contrato EN/INR (ex `COH-BUD-RECON-006`) | budget extraction | M | DET-BUD-SUM en contrato EN |
| P2 | `TASK-STAB-UX-02` | — | Fix re-subida HTTP 500 (ex `DOC-REUPLOAD-005`) | `DocumentDTO` | S | Re-subida crea revisión |
| P2 | `TASK-STAB-UX-03` | — | Fix BOM huérfano en delete/replace (ex `DOC-BOM-ORPHAN-007`) | budget delete/replace | M | Reconciliación correcta |
| P2 | `TASK-STAB-UX-04` | — | Estado "análisis en progreso" para el triplete | web documents | S | UI muestra n/3 |
| P2 | `TASK-STAB-HYG-01` | — | Untrack caches/dual lock/transcript/worktrees + `.gitignore` + CI guard | git, CI | S | Sin mypy_cache/dual-lock |
| P2 | `TASK-STAB-LEG-01` | — | Resolver licencia + añadir `LICENSE` + `SECURITY.md` | raíz | S | Licencia coherente |

### EPIC-STAB-P3 — Arch / CI Follow-ups
| Priority | Task ID | Dep | Task | File(s) | Effort | AC |
|---|---|---|---|---|---|---|
| P3 | `TASK-STAB-CI-02` | CI-01 | Quitar `continue-on-error` en integration | `tests.yml` | S | Integration bloquea |
| P3 | `TASK-STAB-ARC-01` | — | ADR freeze-vs-migrate `modules/coherence` | ADR | M | Decisión documentada |

### EPIC-PROC2 — Fase 2 de Producto: Suite de Aprovisionamiento (diferida detrás del wedge)
> Desglose del placeholder `EPIC-LC-WORKFLOWS` existente. Estado verificado en §5.11.
| Priority | Task ID | Dep | Task | Estado actual | File(s) | Effort |
|---|---|---|---|---|---|---|
| P2 | `TASK-PROC2-PLAN-01` | wedge Fase 1 | Exponer/habilitar Procurement Plan (hoy gated `feature_rfq_generation=False`) + router + UI | ✅ EXISTS-GATED | `procurement/`, `config.py:319`, web | M |
| P2 | `TASK-PROC2-WBS-01` | — | Endurecer WBS identification + import desde proyectos | ✅ EXISTS | `procurement/wbs_generator_service.py`, `wbs/` | M |
| P2 | `TASK-PROC2-BOM-01` | — | Productizar generador BoM (salida/UX) | ✅ EXISTS | `procurement/.../generate_bom_use_case.py` | M |
| P2 | `TASK-PROC2-BOQ-01` | PROC2-BOM-01 | Generador BoQ (Bill of Quantities) — decidir si extiende BoM o es artefacto nuevo | ❌ MISSING | procurement (nuevo) | M |
| P2 | `TASK-PROC2-RFQ-01` | PROC2-BOM-01/BOQ-01 | Generador RfQ (flag existe, código no) | ❌ MISSING | procurement (nuevo) | M |
| P2 | `TASK-PROC2-STK-01` | — | Módulo de comunicaciones de stakeholders (reusar `notification_settings`) | ❌ MISSING | `stakeholders/` (nuevo) | M |
| P3 | `TASK-PROC2-STK-02` | — | Productizar extracción de stakeholders + RACI (gated `feature_raci_generation=False`) | ✅ EXISTS-GATED | `stakeholders/raci_router` | M |

---

## 14. Minimal Patch Plan

**1. Fail-closed prod flags** — `main.py` lifespan: `if settings.is_production and (os.getenv("C2PRO_AI_MOCK")=="1" or os.getenv("C2PRO_SKIP_HITL")=="1"): raise RuntimeError(...)`. Test: arranque prod+flag falla. Rollback: revertir guard.

**2. Flash cache tenant** — `prompt_cache.py:100-108`: `components["tenant_id"]=str(tenant_id)`; propagar por `get()/set()` y callers en `llm_client.py`. Test: dos tenants mismo prompt → keys distintas. Rollback: revertir.

**3. cov 0→60 (atómico con guard)** — `tests.yml:140` + `test_backend_ci_guards.py:19` a `60` simultáneamente. Test: el propio guard. Rollback: volver a 0 en ambos.

**4. Quitar hardcode dimensiones** — `scoring.py:236,306`: `missing_dimensions or _derive_missing(evidence)`. Test: `TS-UD-COH-SCH-001` + caso con schedule presente. Rollback: revertir a literal.

**5. Untrack + gitignore** — `.gitignore` (nuevo bloque) + `git rm --cached` caches/lock/transcript/worktrees. Test: CI guard. Rollback: `git checkout`.

---

## 15. Product Roadmap Recommendation

### 15.1 First 48 Hours
Rotar + purgar secretos; quitar allowlist gitleaks; fail-closed flags; arreglar deploy-staging. *Value:* usuarios sin riesgo legal/seguridad. *Dep técnica:* filter-repo, Railway secrets. *Dep seguridad:* rotación previa a purga. *AC:* §8.3.

### 15.2 First 7 Days
Tenant en flash cache; split API/Celery; higiene repo; cov 60; licencia+LICENSE. *Value:* base operable/confiable. *AC:* §11.4, §12.3.

### 15.3 First 30 Days (cerrar wedge Level-1)
Export informe PDF; fix re-subida (-005) y BOM huérfano (-007); DET-TIME v0 + quitar hardcode; paralelizar gate LLM. *Value:* el loop cierra y entrega valor exportable; "tridimensional" honesto. *Dep:* `temporal/DocumentRevision` (existe). *AC:* §9.5, §10.4.

### 15.4 First 60–90 Days
1 Contract Manager con uso semanal (piloto); productizar HITL en colas por rol; totales EN/INR; cov 80. Solo tras esto: evaluar desbloquear BUILD-GATE v3 (change-impact/health) **y** arrancar **Fase 2 Procurement** (empezando por exponer lo ya construido: Procurement Plan, WBS, BoM). *AC:* uso semanal 4 semanas; 0 P0/P1 en el loop.

---

## 16. Commands Appendix

```bash
# Audit file discovery
ls -la docs/audits/ docs/audits/Consenso/

# Secret scanning (working tree + history)
gitleaks detect --source . --no-banner
git ls-files | grep -iE '(^|/)\.env' | grep -v example
git show HEAD:.env.staging | grep -E '^(SUPABASE_SERVICE_ROLE_KEY|JWT_SECRET_KEY|DATABASE_URL)'
git log --all --oneline -- .env.staging

# Git history purge
git filter-repo --invert-paths --path .env.staging --path apps/api/.env.test \
  --path "docs/assets/Pruebas/HVPNL_First Contract (Main Contents).pdf"
gitleaks detect --source . --no-banner

# Dependency/import mapping (legacy coherence coupling)
grep -rn 'from src.modules.coherence' apps/api/src/ --include='*.py' | grep -v modules/coherence

# Cache isolation checks
grep -n 'tenant' apps/api/src/coherence/cache_keys.py
grep -n 'def build_flash_cache_key' -A25 apps/api/src/core/ai/prompt_cache.py

# Phase 2 procurement state
grep -rln 'RFQ\|RfQ\|quotation' apps/api/src/procurement --include='*.py'   # 0 = MISSING
grep -rln 'BoQ\|bill_of_quant' apps/api/src --include='*.py'                 # 0 = MISSING
grep -nE 'feature_rfq|feature_bom|feature_wbs|feature_stakeholder|feature_raci' apps/api/src/config.py

# CI validation
grep -rn 'continue-on-error\|cov-fail-under' .github/workflows/
python -m pytest apps/api/tests/unit/test_backend_ci_guards.py -xvs

# Test execution
cd apps/api && C2PRO_AI_MOCK=1 pytest tests/unit -m "not integration" --cov=src --cov-fail-under=60

# Repository cleanup
git rm -r --cached .mypy_cache
git rm --cached package-lock.json "codex resumen ultimo trabajo.txt"
git rm --cached worktrees/sentry-perf-gemini worktrees/sentry-perf/w5b-benchmarks
git count-objects -vH | grep size-pack
```

---

## 17. Final Recommendation

1. **Congelar el trabajo de features** (mantener el BUILD-GATE v3; no construir ADR-019/020/021).
2. **Ejecutar la Fase 0 de inmediato (48h)** — secretos vivos en repo público = incidente activo; la allowlist de gitleaks que los oculta debe eliminarse en el mismo cambio.
3. **Estabilizar el wedge Level-1** (auditoría tridimensional con export de informe y HITL) **antes de expandir** — el loop ya existe y está demostrado; falta cerrarlo.
4. **Aplazar** lo no-core (v2 nativo, retirada de `modules/coherence`, v3 change-impact/health, **y la Fase 2 Procurement/RfQ/BoQ/stakeholder-comms**) hasta que CI/seguridad/loop core sean fiables y haya uso semanal real. La Fase 2 queda **enumerada** (`EPIC-PROC2-*`) pero no se arranca antes del wedge.
5. **Continuar con la arquitectura actual** (monolito modular hexagonal) — adecuada; no simplificar ni migrar a microservicios. Única división: API/worker como dos servicios del mismo image.

El diagnóstico central de las auditorías ("falta la columna vertebral temporal/de proyecto") sigue siendo correcto, pero el código ya avanzó: la thin-spine v3 existe y está bloqueada. El error a evitar es saltar a construir spine v3 o Fase 2 Procurement antes de que el wedge documental/contractual —que **hoy funciona**— entregue valor exportable a un usuario real.

---

## 18. Refinement Question

¿Quieres que convierta este análisis en un segundo prompt de Claude Code para implementación patch-por-patch (con tests, commits por tarea y criterios de aceptación), empezando por el track P0 de Fase 0 (rotación/purga de secretos + fail-closed + fix de deploy)? Como siguiente paso, cada `TASK-STAB-*` / `EPIC-PROC2-*` de §13 puede expandirse a una WBS y luego a una spec SDD.
