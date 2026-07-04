# C2Pro — Frontend, Product, Marketing, and End-User Analysis

**Fecha:** 2026-07-03 · **Rama:** `main` · **Autor:** Fable 5 (max effort) · **Método:** pase de evidencias sobre código vivo de `apps/web/` (~45 lecturas directas de páginas, hooks, stores, clientes API, proxy, CI y specs E2E) + validación cruzada con el router de documentos del backend (`apps/api/src/documents/`). El informe previo (`C2Pro — Technical, Product & Execution Improvement Proposal_Fable5.md`, 2026-07-02) se trató como hipótesis, no como fuente.

**Alcance:** solo frontend (`apps/web/`), producto, marketing y usuario final. El backend se consultó únicamente para validar contratos de integración.

---

## 1. Executive Summary

- **Frontend maturity:** **4/10.** Base técnica real y moderna (Next 16 App Router, React 19, Tailwind v4, shadcn/ui, Orval + OpenAPI, Clerk, Sentry, 249 ficheros de test), pero con un bug de crash confirmado (Rules of Hooks en el overview de proyecto), tres paradigmas de fetching conviviendo, componentes huérfanos/placeholder en rutas de navegación primaria, y datos fabricados presentados como reales en pantallas clave.
- **Product UX maturity:** **2/5 (internal demo journey).** El recorrido Nivel-1 no se puede completar desde la UI: **el upload fuerza `document_type="contract"` en el 100 % de los ficheros**, por lo que el triplete Contrato+Presupuesto+Cronograma —la cuña del producto— es literalmente inconstruible desde el frontend.
- **Marketing clarity:** **3/10.** La landing promete ("Detect contract conflicts before they cost millions") pero usa métricas fabricadas sin fuente (94 %, $2.4M, 6x), muestra un "Deploy marker" interno en el footer, el CTA "Get Started" apunta a `/signup` (ruta inexistente → acaba en Sign-In), y la demo pública enseña tipos de documento (contract/specification/proposal) que ni siquiera son el triplete que vende.
- **End-user readiness:** **No apto para usuarios externos hoy.** Un Contract Manager real quedaría bloqueado en el paso 4 del flujo (subir presupuesto/cronograma) y desconfiaría en el paso 6-8 (asignees ficticios, distribución de severidad inventada, revisor registrado como `"current-user"`).
- **Strongest frontend asset:** el **Evidence Viewer** (PDF + highlights + entidades + validación con nota obligatoria si confianza < 90 %) y la **mensajería del triplete en la página de Coherence** ("Provide the full contract, schedule, and budget triplet…"), que es exactamente el producto correcto — solo que el resto de la app no permite cumplirla.
- **Main frontend blocker:** `DocumentUploadDropzone` hardcodea `"CONTRACT"` (`components/features/documents/DocumentUploadDropzone.tsx:81`); el backend exige `document_type` como Form obligatorio y enruta el parser por tipo (`apps/api/src/documents/adapters/http/router.py:376`, `composite_file_parser.py:60-92`). Sin selector de tipo, no hay triplete, no hay Coherence Score completo, no hay producto.
- **Main product UX blocker:** no existe **salida de valor**: no hay pantalla ni endpoint cableado de "informe de auditoría exportable". Los "exports" actuales son popups de `window.print()`, CSV artesanal y un `alert("PDF export - implement with jsPDF or similar")` (`budget/page.tsx:192`).
- **Recommended execution stance:** **congelar superficie y cerrar el loop.** No construir módulos nuevos: (1) selector de tipo de documento en upload, (2) trigger + progreso de análisis visible, (3) findings con evidencia real (eliminar datos fabricados), (4) HITL con identidad real, (5) export de informe de auditoría. Ocultar AI Analytics, Observability, RACI, Kanban, plantillas decorativas y "3D view" detrás de flags hasta beta.

---

## 2. Inputs Reviewed

| Source | Location | Status | Relevance | Notes |
|---|---|---|---|---|
| Código frontend vivo | `apps/web/` (app router, components, hooks, lib, stores, mocks, e2e) | ~45 ficheros leídos en profundidad + greps dirigidos | Fuente de verdad | Base de todo el informe |
| Informe Fable5 previo | `docs/audits/C2Pro — Technical, Product & Execution Improvement Proposal_Fable5.md` | Revisado (secciones frontend) | Contexto | Confirmó "22 rutas cableadas", "sin export", "re-subida 500"; este informe profundiza donde aquél no llegó |
| Backend (validación de contratos) | `apps/api/src/documents/adapters/http/router.py`, `composite_file_parser.py`, enum `DocumentType` | Verificado por grep/lectura | Alta | Confirma que `document_type` es obligatorio y enruta el parsing |
| Cliente generado OpenAPI | `apps/web/lib/api/generated/**` (Orval v8.18) | Inventariado | Alta | Revela hooks generados nunca usados (analyze, evaluate) |
| CI | `.github/workflows/frontend-ci.yml`, `frontend-e2e.yml` | Leídos | Alta | `pnpm test` = solo `src/tests/integration` (50 de 249 ficheros de test) |
| Specs E2E | `apps/web/src/tests/e2e/**` (25+ specs) | Inventariados + 1 leído | Media | Journey de pipeline corre contra proyecto demo `proj_demo_001` |
| Memoria de sesiones previas | Pilot ADIF-AV, demo 636M vs 654M, bug re-upload 500 | Contexto | Media | El pilot ejercitó el backend por API directa, no por la UI — coherente con los hallazgos de este informe |

---

## 3. Frontend Architecture Review

| Area | Current State | Evidence | Developer Impact | User Impact | Severity | Recommended Fix |
|---|---|---|---|---|---|---|
| Framework/rendering | Next 16 App Router + React 19, pero ~95 % client components; solo `projects/[id]/coherence` y `projects/[id]/layout` son server components | `'use client'` en casi todas las páginas de `app/(app)/**` | Se pierde streaming/SSR; bundle grande | Espera visible ("Authenticating…", "Loading…") en cada página | Media | Migrar lecturas iniciales a server components con token server-side (ver fila "auth SSR") |
| Ruta raíz híbrida | `app/page.tsx` es un client component que renderiza landing (anónimo) o `AppDashboardPage` importado directamente (autenticado). Al estar fuera del grupo `(app)`, **el dashboard en `/` se renderiza SIN sidebar ni header**; y `next.config.mjs` redirige `/dashboard → /` permanente, así que la versión con shell es inalcanzable | `app/page.tsx:8,46`; `next.config.mjs:27-37`; `AppSidebar.tsx:60-65` (el item "Dashboard" apunta a `/`) | Dos árboles de layout para la misma pantalla; tests engañosos | CONFIRMED: usuario que pulsa "Dashboard" pierde la navegación (pantalla sin menú); única salida es el botón "Back to Projects" | **Alta** | Crear `app/(app)/page.tsx` o quitar el redirect y servir `/dashboard` dentro del shell; la landing debe ser server component separado |
| Redirects a rutas fantasma | Usuarios con rol `c2pro_admin`/`tenant_admin` son redirigidos a `/admin/c2pro` y `/admin/tenant`, **rutas que no existen** → 404 | `app/page.tsx:18-24`; no existe `app/admin/**` | Roles admin rompen el arranque | CONFIRMED: un admin ve 404 nada más loguearse | **Alta** | Eliminar redirect o crear las rutas |
| Violación de Rules of Hooks | `useMemo` (×5) después de `return` condicionales de loading/error → al pasar de loading→data React lanza "Rendered more hooks than during the previous render" | `app/(app)/projects/[id]/page.tsx:41-57` (returns) vs `:63-102` (useMemo) | Crash capturado por `error.tsx`, pero la Overview de proyecto es inutilizable en carga real | CONFIRMED (patrón): la pestaña Overview crashea al cargar datos | **Crítica** | Mover los `useMemo` antes de los early-returns (o eliminar los memos, son triviales) |
| Estado / fetching | 3 paradigmas conviven: (a) hooks Orval+react-query (proyectos, alerts, HITL), (b) axios manual + useState/useEffect (`useProjectDocuments`, dashboard raíz, evidence global, ai-analytics), (c) `fetch` crudo (upload, reprocess, `fetchApiJson`) | `hooks/useProjectDocuments.ts` (useState); `app/(app)/dashboard/page.tsx:34-99` (manual, N+1 por proyecto); `lib/api/services/http.ts` | Cache incoherente: invalidar queries no refresca páginas manuales; duplicación de manejo de errores | Datos desincronizados entre pestañas; refetch manual | Alta | Estandarizar en react-query + cliente único; matar `useState`-fetching |
| Capa API fragmentada | `apiClient` axios con `normalizeGeneratedApiUrl` que recorta `/api/v1` por regex; `fetchApiJson` paralelo con su propia lógica de scopes (`/api/coherence` vs `/api/v1`); proxy Next `[...proxy]` con `buildBackendUrl` que re-normaliza `v1/`, `coherence/`, `api/coherence/` | `lib/api/client.ts:109-116`; `lib/api/services/http.ts:33-50`; `app/api/[...proxy]/route-utils.ts:38-56` | Tres reescrituras de URL en cadena; cualquier cambio de prefijo rompe silenciosamente | Errores 404/500 crípticos | Alta | Un solo builder de URL; eliminar la regex de normalización haciendo que Orval genere paths relativos |
| **SSR sin autenticación** | `fetchApiJson(path, { server: true })` **no adjunta Authorization ni X-Tenant-ID** (solo los añade en browser); la página server de Coherence llama `getDashboardSummary(id, { server: true })` | `lib/api/services/http.ts:90-97`; `app/(app)/projects/[id]/coherence/page.tsx:23` | La única página SSR de datos llama al backend sin credenciales | CONFIRMED por código: la pestaña Coherence muestra el banner de error salvo que el endpoint sea público (lo cual sería peor) | **Crítica** | Obtener token Clerk server-side (`auth()` de `@clerk/nextjs/server`) y propagarlo; o volver la página client |
| Auth token loop | Clerk → `AuthSync` refresca token cada 50 s a un store Zustand; interceptor axios lo adjunta; 401 → toast + redirect | `components/providers/AuthSync.tsx:68`; `lib/api/client.ts:45-107` | Funcional pero frágil: cualquier fetch fuera de axios (reprocess, SSE) queda sin token | Botones que fallan en silencio | Alta | Helper único `getAuthHeaders()`; usar `getToken()` bajo demanda |
| Fetch sin auth en Retry | "Retry processing" usa `fetch('/api/v1/...reprocess')` crudo sin Authorization; el proxy solo reenvía headers entrantes → 401 seguro; el error solo va a `console.error` | `app/(app)/projects/[id]/documents/page.tsx:100-115`; `app/api/[...proxy]/route.ts:13-33` | Bug invisible | CONFIRMED: el botón de reintento no funciona y no informa | **Alta** | Usar `apiClient.post` |
| Token en query string (SSE) | El stream SSE adjunta `?access_token=<JWT>` en URL | `lib/api/analysis-stream.ts:13-19`; `AnalysisProgressTracker.tsx:136-141` | JWT en logs de servidor/proxy | Riesgo de fuga de sesión | Media | Cookie o ticket de un solo uso |
| Tipado | `tsc strict` ✔ y Orval genera modelos, pero se degrada en runtime: `readNumber(data, "total_budget", "totalBudget")` sobre `Record<string, unknown>` (budget), doble cast en settings, `uploadDocument` acepta `"BOM"` que **no existe** en el enum backend (que sí tiene `budget`) | `budget/page.tsx:73-97,211-217`; `settings/page.tsx:30-56`; `lib/api/index.ts:210-216` vs `generated/models/documentType.ts:46-53` | El contrato de tipos es decorativo donde más importa | Datos mal mapeados (budget→"bom") | Alta | Derivar uniones del enum generado; borrar duck-typing |
| Manejo de errores en mutaciones | Patrón repetido `catch { /* Error handled by mutation state */ }` pero el estado de error **nunca se renderiza**; `useBudget` devuelve `null` y hace `console.error` | `review/page.tsx:181-183,198-200`; `hooks/useBudget.ts:127-172` | Errores tragados | Aprobar/rechazar/crear puede fallar sin feedback | **Alta** | Toast de error estándar en `onError` global del QueryClient |
| Componentes huérfanos/placeholder | `AnalysisProgressTracker` y `ProcessingStepper` solo se usan en sus tests; `GlobalSearch` y `CrossModuleNavigator` se autodeclaran "Placeholder for RED Phase"; `OnboardingEntry` + `sample-project-bootstrap` sin montar en ninguna página; hooks generados `useAnalyzeDocument…` y `useEvaluateProjectCoherence…` sin un solo call-site | greps sobre `apps/web` (solo matches en tests); `components/search/GlobalSearch.tsx:2`; `components/navigation/CrossModuleNavigator.tsx:2` | Código muerto que aparenta funcionalidad; mantenimiento fantasma | Las capacidades clave (progreso, análisis, onboarding) existen a medias pero el usuario nunca las ve | **Alta** | Montar los 2 componentes de progreso en el flujo real; borrar placeholders |
| Triple raíz de componentes | `components/`, `src/components/`, y duplicados `components/coherence/*` vs `components/features/coherence/*` (ScoreCard/CoherenceGauge duplicados; los tests de uno viven en la carpeta del otro) | árbol de ficheros; `CoherenceClient.tsx:14` importa de `@/src/components/...` | Convención rota; imports confusos | — | Media | Consolidar en una raíz única |
| Ficheros gigantes | `projects/page.tsx` 1.362 líneas; `projects/[id]/evidence/page.tsx` 1.636 líneas (dropzone+viewer+graph 3D+templates+exports en un fichero) | wc de lecturas | Viola la propia regla del repo (<800); imposible de revisar | Bugs escondidos | Media | Trocear por feature |
| i18n / idioma | UI 100 % inglés **excepto** el toast de sesión ("Sesión expirada o inválida") y placeholders del form de proyecto ("Edificio Central - Fase 1", "Constructora ABC S.L.") | `lib/api/client.ts:85`; `projects/new/page.tsx:109,135` | Sin capa i18n | Mezcla ES/EN incoherente para un usuario EPC español | Media | Decidir idioma (o i18n mínima) y unificar |
| A11y | Base decente: skip-link, `aria-label`s, `role="status"` sr-only en upload, focus rings; pero input de búsqueda del header decorativo y menús con items muertos | `(app)/layout.tsx:30-35`; `DocumentUploadDropzone.tsx:204-206`; `AppHeader.tsx:111-118,233-239` | — | Elementos interactivos que no hacen nada = trampa a11y | Media | Quitar o cablear los controles decorativos |
| Observabilidad | Sentry inicializado + tunnel `/tunnel` en next.config; errores de UI van a `console.error` mayoritariamente | `next.config.mjs:39-47`; `components/providers/SentryInit.tsx` | Errores de mutación no llegan a Sentry | — | Media | Capturar errores de react-query en Sentry |
| Design system | shadcn/ui consistente en primitivas, pero dos estéticas conviven: páginas "glassmorphism" (`rounded-2xl`, `rounded-[28px]`, `backdrop-blur`, `bg-background/95`) vs páginas planas (review, budget, wbs); colores de severidad a veces tokens (`text-warning`, `destructive`) y a veces Tailwind crudo (`bg-green-100 text-green-700`) | compárese `documents/page.tsx` vs `review/page.tsx`; `getStatusColor` en ambos | Duplicación de estilos de estado | Producto se siente cosido de retales | Media | Tokens semánticos de severidad/estado únicos + guía de radios/sombras |

---

## 4. Route and Screen Inventory

Rutas reales del App Router (verificadas por listado de `app/**/page.tsx`). "Real" = cableada a backend y funcional; "Partial" = cableada pero con huecos o datos inventados; "Placeholder" = decorativa; "Mocked" = datos estáticos/MSW.

| Route / Screen | Purpose | Current State | Real / Partial / Placeholder / Mocked | Main Components | API Dependencies | Product Value | Issues |
|---|---|---|---|---|---|---|---|
| `/` (anónimo) | Landing marketing | Client component con hero, stats, features, CTAs | Partial | `LandingPageContent` | — | Puerta de entrada | Stats fabricadas; CTA `/signup` → ruta inexistente (el proxy la manda a Sign-In); "Deploy marker 2026-03-30-a" visible; links Pricing/Privacy/Terms = `#` |
| `/` (autenticado) | Portfolio dashboard | Lista proyectos + score/alerts/docs por tarjeta, drill-down | Partial | `AppDashboardPage`, `DashboardClient` | `GET projects`, `GET dashboard/{id}` (N+1) | Vista cartera | **Se renderiza sin sidebar/header**; empty state con estilo de error y sin CTA "Create project"; fetching manual |
| `/dashboard` | — | Redirect permanente a `/` | — | — | — | — | Hace inalcanzable la versión con shell |
| `/sign-in`, `/sign-up` | Auth Clerk | Componente Clerk temado, redirect a `/projects` | Real | `SignIn`/`SignUp` Clerk | Clerk | Funcional | Estética slate-900 desconectada del resto (cyan/blanco) |
| `/login`, `/register` | Legacy | Redirect a sign-in/sign-up | Real | — | — | — | OK |
| `/projects` | Lista + creación | Tabla/kanban, filtros, presets, quick-view sheet, wizard 3 pasos, batch import, templates, exports | Partial | `ProjectListTable`, `ProjectKanbanBoard`, dialogs lazy | `GET/POST projects`, `GET projects/{id}/summary` | Núcleo | 1.362 líneas; templates estáticos que **no aplican nada** al crear; batch import solo previsualiza; export PDF = `window.print()`; doble flujo de creación (wizard + `/projects/new`) |
| `/projects/new` | Creación página completa | Form básico → redirect a documents | Real | form propio | `POST projects` | Redundante | Duplica el wizard; sin validación más allá de nombre |
| `/projects/[id]` (Overview) | Resumen proyecto | Stat cards + resumen + alertas recientes | Partial | stat cards | `GET api/coherence/dashboard/{id}`, `GET alerts` | Aterrizaje del proyecto | **Crash Rules-of-Hooks al cargar**; Status "Active" hardcodeado; "Budget Used = 100−subscore" es una métrica inventada |
| `/projects/[id]/documents` | Registro y subida | Tabla docs + KPIs + upload dialog + delete + retry | Partial | `DocumentUploadDropzone` | `GET/POST project documents`, `DELETE document`, reprocess | Paso 4 del wedge | **Todo se sube como `contract`**; sin selector de tipo; retry sin auth (roto); sin polling de estado (refresco manual); tipos mostrados mapean budget→"bom" |
| `/projects/[id]/coherence` | Coherence Score™ | SSR + gauge, breakdown, radar, sub-categorías, banner triplete | Partial | `CoherenceClient`, `CoherenceGauge`, `BreakdownChart`, `RadarView` | `GET api/coherence/dashboard/{id}` (SSR **sin auth**) | Corazón del producto | SSR sin credenciales; distribución de alertas fabricada (`critical=0, high=0, medium=alert_count`); `alertCount=0` por categoría; trend vacío; `categories_v2` (evidencia por categoría) tipado pero **jamás renderizado**; banner interno "Coherence Score v1 is active" |
| `/projects/[id]/analysis` | Resumen análisis | Stat cards + "Analysis Posture" | Partial | — | dashboard + alerts | Debería ser el paso 5 | "Open Processing Stream" es un `<Link>` **al endpoint SSE crudo** (JSON en el navegador, 401 sin token); no hay botón "Run/Re-run analysis" (hook generado sin usar); jerga N1-N17/LangGraph pensada para ingenieros |
| `/projects/[id]/evidence` | Visor evidencia | PDF + highlights + entidades (aprobar/rechazar con nota <90 %) + alerts + timeline + explicación AI + export | Partial | `LazyPdfEvidenceViewer`, `EntityValidationList` | entities, alerts, history, relationship-explanation, approvals | **Mejor pantalla del producto** | 1.636 líneas; "3D Relationship View" = CSS transforms (gimmick); "Evidence Templates" no aplican nada; `resolved_by:"web-evidence-viewer"` hardcodeado; aprobación de entidades solo cableada para stakeholders |
| `/projects/[id]/alerts` | Findings | `AlertReviewCenter` con severidad/estado | Partial | `AlertReviewCenter` | `GET project alerts` | Paso 6-7 | **Asignees ficticios** (`legal.reviewer`, `finance.analyst`) y **clauseId sintetizado** (`clause-${id}`) presentados como reales — mata la confianza |
| `/projects/[id]/review` | HITL queue | Cola con stats, filtros, approve/reject + timeline | Partial | dialogs approve/reject | `GET hitl/queue`, `POST approve/reject` | Paso 8 del wedge | La cola es **global**, no del proyecto (encabezado engaña); `reviewer_name:"current-user"` hardcodeado (audit trail falso); item mostrado como JSON crudo sin link a evidencia; errores de mutación invisibles |
| `/projects/[id]/budget` | Presupuesto | KPIs, breakdown, planned-vs-actual, CRUD items | Partial | tabla + dialogs | `GET/POST/PATCH/DELETE budget items` | Dimensión Budget | Export PDF = `alert()` placeholder; `confirm()` nativo; sin tipado de respuesta; **no muestra la reconciliación** leaf-sum vs stated vs contrato (el hallazgo estrella del pilot) |
| `/projects/[id]/wbs` | WBS tree | Árbol jerárquico, drag&drop, edición | Real (CRUD) | `WBSTree` etc. | WBS endpoints | Dimensión Schedule parcial | Sin vista de cronograma/fechas prominente; drag&drop sin undo |
| `/projects/[id]/stakeholders` | Stakeholders/RACI | Matriz y workbench | Partial | `StakeholderMatrix`, `RaciGrid` | stakeholders API | Secundario al wedge | Distrae del Nivel-1 |
| `/projects/[id]/settings` | Ajustes proyecto | Edición metadata | Real | form | `PATCH project` | Soporte | — |
| `/evidence`, `/alerts`, `/stakeholders`, `/documents` (globales) | Selectores cross-proyecto | Lista proyectos → navega | Real (nav) | — | `GET projects` | Navegación | Duplican navegación; añaden superficie |
| `/ai-analytics` | Costes/deriva LLM | Dashboards de coste, versiones, drift | Real | `CostDashboard` etc. | usage-analytics API | **Interno**, no de usuario EPC | No debería estar en la nav primaria de un CM |
| `/observability` | Salud sistema | Status + análisis recientes (poll 30 s) | Real | — | observability API | **Interno** | Ídem |
| `/settings` | Perfil usuario | Tabs profile/notifications/prefs | Partial | — | `GET/PUT auth/me` (legacy) | Soporte | Preferencias (idioma, TZ, notifs) son estado local no persistido; double-cast de tipos |
| `/raci` | RACI global | Detrás de flag `FEATURE_RACI_GENERATION` | Partial | — | — | Secundario | Correctamente flageado (único ejemplo de gating) |
| `/demo/*` (8 rutas) | Demo pública sin auth | Páginas estáticas con `SAMPLE_DATA` + banner "Sample data only" | Mocked (honesto) | `DemoBanner` | MSW/estático | Marketing | Los tipos demo son contract/specification/**proposal** — ni budget ni schedule: la demo no enseña la cuña |
| **Faltantes** | Onboarding, Run-analysis, Report/Export de auditoría, Billing/Usage, Admin/tenant, página 404 propia | — | **Missing** | — | — | — | Onboarding existe como componente huérfano; `/admin/*` se referencia pero no existe; ningún export de informe de auditoría en toda la app |

---

## 5. Level-1 Workflow Analysis

Flujo objetivo: *entender → login → proyecto → subir triplete → ver progreso → findings → evidencia → HITL → exportar informe → volver*.

| Workflow Step | Frontend Support | Evidence | Missing UX / Missing Data | User Friction | Priority | Recommended Improvement |
|---|---|---|---|---|---|---|
| 1. Entender qué hace C2Pro | Parcial | Landing con promesa clara pero genérica; en la app no hay explicación del método | Sin "cómo funciona" (3 docs → findings → informe); demo no enseña triplete | Media | P1 | Hero con el flujo de 3 pasos + demo alineada a la cuña |
| 2. Sign in | ✅ Completo | Clerk `/sign-in` → `/projects` | — | Baja | — | — |
| 3. Crear/seleccionar proyecto | ✅ Funcional (duplicado) | Wizard en `/projects` + página `/projects/new`; redirect a documents | Dos flujos que divergen; templates decorativos | Baja | P2 | Un solo flujo; borrar o cablear templates |
| 4. Subir contrato + presupuesto + cronograma | ❌ **Bloqueado** | Dropzone hardcodea `"CONTRACT"` (`DocumentUploadDropzone.tsx:81`); backend exige tipo y elige parser por tipo; un XLSX subido como contract falla en el parser (`composite_file_parser.py:82`) | Selector de tipo; checklist visual del triplete (contract ✔ / budget ✘ / schedule ✘) | **Bloqueante total** | **P0** | Selector obligatorio por fichero (default inteligente por extensión) + tarjeta "Triplet status" en documents |
| 5. Ver progreso de procesamiento | ❌ No visible | `AnalysisProgressTracker`/`ProcessingStepper` huérfanos; documents no hace polling; "Open Processing Stream" enlaza al SSE crudo | Estado en vivo tras subir; transición uploaded→processing→analyzed sin F5 | Alta: el usuario no sabe si "está pasando algo" | **P0** | Montar el tracker (versión simplificada de 3-4 etapas, no N1-N17) en documents/analysis + polling |
| 6. Recibir findings de coherencia | Parcial | Coherence page (scores) + alerts page (lista); pilot demostró findings reales vía API | SSR sin auth rompe la página clave; distribución de severidad fabricada; `categories_v2` con evidencia/conflictos/recomendaciones **no renderizado** | Alta | **P0/P1** | Arreglar SSR auth; pintar severidades reales; renderizar categories_v2 (estado por categoría, evidencia faltante, conflictos) |
| 7. Entender evidencia y severidad | Parcial | Evidence viewer real con bbox highlights cuando el alert trae `evidence_location`; alerts page fabrica `clause-${id}` | Link finding→cláusula real; severidad consistente (tokens) | Alta: la traza fabricada destruye confianza | **P0** | Eliminar todo dato sintético; si no hay evidencia, decir "Sin evidencia vinculada" |
| 8. Revisar vía HITL | Parcial | Review queue funcional mecánicamente (approve/reject persisten) | Identidad real del revisor (hoy `"current-user"`); scoping por proyecto; contexto humano del item (hoy JSON crudo); errores visibles | Alta | **P0** | `reviewer_name` desde Clerk; filtrar cola por `project_id`; card legible con link a evidencia |
| 9. Exportar informe de auditoría | ❌ Inexistente | Únicos exports: print-popup (projects, evidence), CSV artesanal (budget), `alert()` placeholder (budget PDF); no hay pantalla "Audit Report" | Todo: composición del informe (score + findings aprobados + evidencia + firma HITL) | **Bloqueante para el valor** | **P0 (MVP)** | Pantalla "Export Audit Report" que consuma un endpoint de informe (o genere client-side desde datos aprobados) con PDF serio |
| 10. Volver y continuar | Parcial | Estado vive en backend; filtros persisten en sessionStorage/localStorage; sign-in vuelve a `/projects` | "Continue where you left off" (último proyecto/pestaña); indicadores de qué cambió desde la última visita | Media | P2 | Tarjeta "Recent activity" en projects + deep-link al último tab |

### Workflow Maturity Score

**2 / 5 — Internal demo journey.**

Justificación con evidencia: los pasos 2-3 son reales y el 6-8 son parcialmente reales (el pilot ADIF-AV demostró findings reales, pero orquestado por API, no por la UI). El flujo se rompe **estructuralmente** en el paso 4 (tipo de documento hardcodeado → el triplete es imposible), el paso 5 no existe visualmente (componentes huérfanos), y el paso 9 no existe en absoluto. No es un 1 (las pantallas están conectadas entre sí y a APIs reales, con auth multi-tenant real); no es un 3 (un MVP exige poder completar el recorrido de punta a punta sin tocar la API a mano, y hoy no se puede). Coincide direccionalmente con el 3/5 "de producto" del informe previo: aquel score incluía el backend; el frontend por sí solo está un escalón por debajo.

---

## 6. Product UX Review

| UX Area | Current State | Evidence | Product Problem | Recommended Improvement | Priority |
|---|---|---|---|---|---|
| Promesa visible en la app | Tras el login no hay rastro de "auditoría tridimensional"; el dashboard dice "Cross-project coherence and alert distribution" | `dashboard/page.tsx:178-180` | El usuario no re-conecta la app con lo que compró | Subtítulos orientados a resultado ("Detect contradictions between your contract, budget and schedule") | P1 |
| Guía hacia el triplete | Solo la página Coherence lo pide ("Upload schedule and budget", "Provide the full contract, schedule, and budget triplet") — **pero el upload no permite cumplirlo** | `CoherenceClient.tsx:74-101,140-143` vs `DocumentUploadDropzone.tsx:81` | La app pide algo que ella misma impide; loop roto | Selector de tipo + checklist de triplete persistente en Documents y Overview | **P0** |
| Explicar por qué importa cada documento | Inexistente; el dropzone lista "contracts, schedules, budgets, or BC3" sin explicar su rol | `DocumentUploadDropzone.tsx:164-166` | Usuario sube "lo que tiene" sin entender el modelo | Micro-copy por tipo: "Budget (XLSX/BC3): usado para contrastar el total declarado contra la suma de partidas y el precio del contrato" | P1 |
| Distinción de dimensiones | Sub-scores SCOPE/BUDGET/QUALITY/TECHNICAL/LEGAL/TIME visibles; sin mapa documento→dimensión | `CoherenceClient.tsx:16-23` | 6 categorías internas ≠ 3 documentos del pitch; confunde | Vista "3 documentos × hallazgos cruzados" como capa principal; las 6 categorías como detalle | P1 |
| Comprensibilidad de findings | Alerts = una línea `message` + severidad; review = JSON crudo; los campos ricos de v2 (missing_evidence, detected_conflicts, recommendation) no se muestran | `alerts/page.tsx:34-49`; `review/page.tsx:414-421`; `lib/api/contracts.ts:23-39` | El "qué hago con esto" no existe | Card de finding: qué chocó con qué, cita a ambos documentos, impacto, recomendación | **P0** |
| Trazabilidad de evidencia | Real en Evidence viewer (bbox); fabricada en Alerts (`clause-${id}`); fake counts en Coherence | ver §4 | Mezcla de trazas reales y decorativas = indistinguible para el usuario → desconfianza total | Regla dura: ningún dato sintético en producción; placeholder honesto ("—") | **P0** |
| Intuitividad del HITL | Mecánica simple (approve/reject) ✔; contexto nulo; identidad falsa | `review/page.tsx` | Un gate de aprobación sin accountability ni contexto no es un gate | Identidad Clerk + card contextual + evidencia inline | **P0** |
| Confianza pre-export | No hay momento "revisa y firma" porque no hay export | — | Sin cierre de valor | Pantalla de composición de informe con resumen de lo aprobado/rechazado | **P0 (MVP)** |
| Foco vs distracción | Nav global: Dashboard, Projects, Evidence, Alerts, Stakeholders, **AI Analytics** (+RACI); tabs de proyecto: 10 ítems incl. Stakeholders/WBS/Settings; kanban, presets, batch import, templates, 3D view | `AppSidebar.tsx:31-38`; `ProjectTabs.tsx:13-24` | La superficie sugiere un ERP a medio hacer, no un auditor afilado | Nav Nivel-1: Projects · Documents · Findings · Review · Report; resto tras "More" o flag | P1 |
| Disponible-ahora vs próximamente | Sin distinción: notificaciones fake en demo, templates decorativos, "View all notifications" muerto, menú Profile/Settings muerto | `AppHeader.tsx:53,198-200,233-239` | El usuario pulsa cosas que no hacen nada | Badge "Coming soon" o eliminación; nada clicable sin acción | P1 |

---

## 7. Final User Perspective

| Persona | Main Job-To-Be-Done | Current Frontend Fit | Frictions | Trust Gaps | Must-Have Improvements |
|---|---|---|---|---|---|
| **EPC Contract Manager** | "Antes de firmar/ejecutar, dime dónde el contrato contradice al presupuesto y al cronograma, con la cláusula exacta" | Puede crear proyecto y subir el contrato; ve un score y alertas | No puede subir presupuesto/cronograma como tales (paso 4 roto); sin botón "analizar"; jerga interna (AUDIT_INCOMPLETE, N1-N17, score v1/v2) | ClauseIds falsos en Alerts; asignees inventados; "94 % detection" sin fuente en la landing; score sin explicación accionable | Selector de tipo; findings con doble cita (contrato ↔ presupuesto); export de informe firmable |
| **Cost Controller** | "Concíliame el total declarado del presupuesto contra la suma de partidas y el precio del contrato" | Página Budget con CRUD y planned-vs-actual | La reconciliación (DET-BUD-SUM, demostrada en pilot: 636M vs 654M) **no se muestra** en Budget; "Budget Used = 100−subscore" es una métrica sin sentido contable | Un número inventado en el Overview lo descalifica todo para un controller | Bloque "Reconciliation: stated vs computed vs contract" con delta % y semáforo; quitar métricas derivadas falsas |
| **Project Manager** | "Vista de salud del proyecto y qué atacar esta semana" | Overview con stat cards + alertas recientes | Overview crashea (hooks); dashboard raíz sin navegación; sin priorización (todas las alertas parecen iguales, distribución fabricada) | Status "Active" hardcodeado; severidades pintadas todas como medium en el gráfico | Fix crash; top-5 findings por severidad real; tendencia del score |
| **Procurement Manager** | "¿Qué partidas/BoM chocan con el alcance contractual?" | WBS tree + stakeholders existen | Sin RfQ/BoQ (correcto para Nivel-1); budget items sin link a WBS ni a cláusulas | Tipos budget mostrados como "bom" | Fuera del Nivel-1: no invertir aún; solo mantener WBS navegable |
| **Legal / Claims Manager** | "Evidencia citable: cláusula, página, texto exacto, quién la validó y cuándo" | Evidence viewer con página+bbox y validación con nota <90 % — la mejor base | Export "PDF" = print popup; timeline de revisión existe pero el revisor es `"current-user"` | Audit trail falso = inutilizable en una disputa; watermark overlay existe pero sin identidad real detrás | Identidad Clerk en cada acción; export con hash/fecha/validador; citas cláusula-página en el informe |

**Síntesis:** las cinco personas fracasan hoy en el mismo punto (ensamblar el triplete y extraer un informe) y desconfían por la misma razón (datos decorativos mezclados con reales). Arreglar esos dos ejes sirve a todas a la vez.

---

## 8. Marketing and Positioning Review

| Marketing Area | Current State | Evidence | Problem | Recommended Copy / UX Direction | Priority |
|---|---|---|---|---|---|
| Above-the-fold | "Detect contract conflicts before they cost millions" + subhead con 6 categorías | `landing-page-content.tsx:42-50` | Titular decente pero subhead lista categorías internas en vez del objeto (contrato+presupuesto+cronograma) | Ver "Recommended Product Messaging" | P1 |
| Métricas de prueba | "94 % Risk Detection · 6x Faster Review · $2.4M Avg. Savings · <30s Analysis" | `:70-84` | **Fabricadas** (sin fuente, sin pilotos citables); riesgo reputacional/legal B2B | Sustituir por hechos verificables del pilot: "14 riesgos detectados en un contrato AV real · desviación presupuestaria del 2,8 % detectada en vivo" (con permiso) o quitar la sección | **P0 (demo)** |
| Artefactos internos visibles | "Deploy marker 2026-03-30-a" en footer; título de pestaña "C2Pro v3.0 - Coherence Monitor" | `:210`; `app/layout.tsx:37` | Huele a herramienta interna de ingeniería | Quitar marker; título "C2Pro — Contract Coherence Audit" | **P0 (demo)** |
| CTAs | "Get Started" → `/signup` (no existe; Clerk lo rebota a Sign-In); "Access Real Workspace"/"Go to Real Platform" → `/login`; "View Live Demo" → `/demo/documents` | `:32,53,59` | Funnel roto y copy que confiesa dudas ("Real" workspace implica que lo demás no lo es) | "Start free audit" → `/sign-up`; "See a live example" → demo del triplete | **P0** |
| Demo pública | Demo honesta (banner "Sample data only") pero muestra contract/specification/**proposal** | `contexts/demo-mode` SAMPLE_DATA; `demo/documents/page.tsx:26-49` | La demo no demuestra la cuña (ni budget ni schedule ni findings cruzados) | Demo guiada: proyecto con triplete cargado → 3 findings cruzados → informe de ejemplo descargable | P1 |
| Diferenciación vs "document AI" genérico | Solo implícita (6 categorías) | landing | No se explica el cruce inter-documento (lo único que Copilot/ChatGPT no hace out-of-the-box) | Pilar central: "No leemos documentos: los confrontamos entre sí" + Coherence Score™ y HITL como marcas | P1 |
| Trust/security | Nada: sin mención de RLS multi-tenant, PII anonymization pre-LLM, HITL, ni data residency; Privacy/Terms = `#` | `:215-223` | Para EPC enterprise es eliminatorio | Sección "Your contracts never train models. PII is stripped before any AI call. Every finding is human-approved." + links legales reales | P1 |
| Screenshots/producto | Ninguna imagen de producto en la landing | — | Promesa sin prueba visual | Captura real del Evidence viewer con un finding citado | P2 |
| Pricing/Billing | Link "Pricing" = `#`; sin página; `serviceTier` existe en código pero sin UI | `:22`; `AuthContext.tsx:77-81` | B2B serio espera al menos "Contact sales" | Página mínima: Pilot / Team / Enterprise — "Book a pilot audit" | P2 |
| Enterprise readiness signals | Clerk (SSO-capable), multi-tenant real, Sentry — nada de esto se comunica | código | Se está pagando el coste sin cobrar el beneficio | Badges: "SSO · Multi-tenant isolation · Human-in-the-loop audit trail" | P2 |
| ¿Producto o herramienta interna? | Mezcla: landing de producto + páginas AI Analytics/Observability en nav de usuario + jerga LangGraph | §4 | Confunde al comprador | Separar superficie usuario/operador | P1 |

### Recommended Product Messaging

- **One-line positioning:** La plataforma de auditoría de coherencia contractual para proyectos EPC: contrato, presupuesto y cronograma confrontados por IA, validados por tu equipo.
- **Primary headline:** *Your contract says one thing. Your budget and schedule say another. Find out before it costs you.*
- **Subheadline:** C2Pro cross-examines the contract, budget and schedule of your EPC project, flags every contradiction with clause-level evidence, and produces an auditable report your team signs off on.
- **Primary CTA:** **Start your first audit** (→ `/sign-up`)
- **Secondary CTA:** **See a real example** (→ demo con triplete y findings)
- **Three value pillars:**
  1. **Tridimensional audit** — one upload each: contract, budget, schedule. C2Pro reads all three against each other, not in isolation.
  2. **Evidence you can defend** — every finding cites the exact clause, page and figure on both sides of the contradiction. Coherence Score™ tells you how aligned your project really is.
  3. **Human-approved, export-ready** — nothing leaves C2Pro without your review. Approve or reject each finding and export a signed audit report.
- **Trust message:** *Multi-tenant isolation at the database layer. PII stripped before any AI call. Your documents never train models. Every finding passes human review — with a full audit trail.*

---

## 9. Visual Design and Interaction Review

| Design Area | Current State | Evidence | User Impact | Recommended Improvement |
|---|---|---|---|---|
| Jerarquía de layout | Shell correcto (sidebar 210px + header 14 + main) cuando aplica; ProjectHeaderCard + tabs razonable | `(app)/layout.tsx`, `ProjectHeaderCard.tsx` | Base sólida | Mantener; arreglar la ruta `/` sin shell |
| Claridad de navegación | Tabs de proyecto **sin estado activo** (todas idénticas, sin `aria-current`); sidebar sí marca activo | `ProjectTabs.tsx:36-44` | El usuario no sabe en qué pestaña está | Estado activo + `aria-current="page"` en tabs |
| Densidad de información | Extremos: páginas glass con chips/pills redundantes (documents: 3 filas de resumen para 4 números) vs review espartano | `documents/page.tsx:192-368` | Fatiga visual y sensación de inconsistencia | Sistema de densidad único (una fila de KPIs, tablas sobrias) |
| Tablas/cards/charts | Recharts en coherence (gauge, radar, barras); tablas HTML correctas con overflow-x | `CoherenceClient`, `documents/page.tsx:371` | OK | Añadir tendencia real (hoy `trend={[]}`) |
| Semántica de color | Doble sistema: tokens (`warning`, `destructive`, `chart-budget`) y utilidades crudas (`bg-green-100 text-green-700`) repetidas en ≥4 páginas con mapeos distintos | `documents:62-73`, `review:61-77`, `budget:238-249`, `alerts` | Severidad "critical" no se ve igual en todas partes | Un solo módulo `severityToToken()` + tokens semánticos |
| Tipografía/espaciado | Inter variable + JetBrains Mono para cifras — buena elección; tracking widget-style (`tracking-[0.18em]`) sobreusado | `layout.tsx`, múltiples | Mono en cifras da credibilidad técnica ✔ | Reservar uppercase-tracking a labels, no a todo |
| Responsive | Sidebar colapsable con overlay móvil; `BottomSheet`, `MobileEvidenceViewer`, `MobileGanttChart`, tests a11y-tablet | componentes móviles + specs S3-02/S3-12 | Inversión móvil real (inusual y positiva) | Verificar tablas anchas en <768px (documents) |
| Accesibilidad | Skip-link, aria-labels, live regions en upload, focus-visible; pero: búsqueda decorativa, items de menú muertos, tabs sin estado, botón-dropzone anidando contenido complejo | §3 | Trampas de interacción para lectores de pantalla | Auditoría axe sobre las 6 pantallas del wedge (base ya existe en `src/tests/accessibility`) |
| Empty/error/loading | `error.tsx` y `global-error.tsx` correctos; loading spinners consistentes; empty states desiguales (dashboard usa estilo error sin CTA; coherence tiene el mejor empty state) | `dashboard:44-47` vs `coherence/page.tsx:39-50` | Momentos "¿y ahora qué?" sin guía | Componente `EmptyState` único con icono+texto+CTA |
| CTA placement | "New Project" bien; pero el CTA más importante del producto (subir triplete / exportar informe) no existe como CTA | — | El producto no "empuja" hacia el valor | CTA primario contextual por etapa del proyecto (upload → analyze → review → export) |
| ¿Enterprise-ready feel? | Con datos reales y sin los fakes, cerca; hoy los detalles (alert(), print popup, deploy marker, EN/ES mezclado) lo delatan | §3-§6 | Percepción de prototipo | Barrido de "detalles delatores" (lista P0/P1 en §12) |

---

## 10. Frontend Data and API Integration Review

| Integration Area | Current State | Evidence | Risk | Recommended Fix |
|---|---|---|---|---|
| Document upload | `fetch` directo a `env.API_BASE_URL` (default `/api` → pasa por el proxy pese al comentario "directly to backend"); tipo hardcodeado `contract`; secuencial fichero a fichero con token fresco | `lib/api/index.ts:207-259`; `DocumentUploadDropzone.tsx:78-87` | Triplete imposible; XLSX como contract → error de parser; comentario engañoso | Selector de tipo; usar cliente único; subir en paralelo con cola visible (`UploadQueue` ya existe, sin usar) |
| Analysis trigger | Hook generado `useAnalyzeDocumentApiV1AnalyzePost` sin call-sites; análisis solo se dispara implícitamente al subir | grep §evidencia | Sin re-run tras corregir documentos; usuario sin control | Botón "Run analysis" en Documents/Analysis |
| Processing stream (SSE) | `EventSource` con token en query; solo en componente huérfano; el link de la página analysis va al endpoint crudo | `analysis-stream.ts`; `analysis/page.tsx:123-127` | Token en logs; UX rota | Montar tracker; token por cookie; quitar el link crudo |
| Coherence dashboard | Client: `/api/coherence/dashboard/{id}` vía proxy ✔; Server (página coherence): `fetchApiJson(server:true)` **sin auth headers** | `http.ts:90-99`; `coherence/page.tsx:23` | La página núcleo falla en producción o el endpoint es público | Token server-side de Clerk o pasar la página a client |
| Coherence evaluate | Hook generado `useEvaluateProjectCoherence…` sin usar; el pilot lo llamó por curl | grep | El "botón de auditoría" no existe en la UI | CTA "Evaluate coherence" tras triplete completo |
| Coherence v2 payload | `categories_v2` (status por categoría, evidence_coverage, missing_evidence, detected_conflicts, recommendation) tipado en `contracts.ts:50-75` y **nunca renderizado** | grep | El dato más explicable del producto está oculto | Render de categorías v2 en la página Coherence |
| HITL review | Cola global sin `project_id`; `reviewer_name:"current-user"`; errores tragados | `review/page.tsx:132,177,192` | Audit trail inválido; cross-project confusion | Params de proyecto + identidad Clerk + toasts de error |
| Budget | Endpoints `/projects/{id}/budget` + CRUD items sin modelo generado (interfaz manual + duck-typing) | `hooks/useBudget.ts`; `budget/page.tsx:211-217` | Drift silencioso frontend/backend | Regenerar Orval para budget; borrar readNumber/readString |
| Auth/tenant propagation | Interceptor axios añade Bearer + X-Tenant-ID desde Zustand; `queryClient.clear()` al cambiar de org ✔ | `client.ts:45-58`; `AuthSync.tsx:98-104` | Sólido en el happy path; fetchs fuera de axios lo pierden | Centralizar |
| Re-upload / revisiones | "Retry processing" sin auth (roto); memoria de proyecto registra bug PATCH 500 de re-subida (tenant_id ausente en DocumentDTO) | `documents/page.tsx:100-115`; memoria 2026-06 | El flujo de corrección (esencial en auditoría) no funciona | Arreglar auth del retry; test E2E de re-subida |
| Mock/fallback data en producción | Severidad de alertas inventada (coherence), assignees/clauses inventados (alerts), notificaciones fake (header demo), stats landing | §4 | **Confianza**: indistinguible de datos reales | Purga total; regla de lint/review: "no literals as data" |
| Type mismatch | `uploadDocument` acepta `BOM` (no existe en backend) y omite `BUDGET`; `documentTypeMap` mapea budget→bom en la UI | `lib/api/index.ts:210-216`; `useProjectDocuments.ts:21-29` | Budget invisible/mal etiquetado en todo el frontend | Alinear con enum generado `DocumentType` |
| Proxy Next | Reenvía método/headers/body como buffer; maneja multipart vía arrayBuffer; reescrituras de coherence duplicadas con `http.ts` | `route.ts`, `route-utils.ts` | Doble mantenimiento de rutas coherence | Unificar reglas de ruteo en un módulo compartido |

---

## 11. Frontend Testing and Quality Gates

| Test Area | Current State | Evidence | Gap | Recommended Test |
|---|---|---|---|---|
| Volumen | 249 ficheros `*.test.*` en `apps/web` (unit colocated + integration + e2e) | find | Volumen ≠ protección: los bugs P0 de este informe conviven con tests verdes | — |
| CI unit/integration | `frontend-ci.yml` ejecuta `pnpm test` = **solo `src/tests/integration`** (50 ficheros); los ~199 tests colocated solo corren con `test:all` (no en CI) | `package.json:14`; workflow `:143` | El grueso de la suite no es gate; p.ej. el crash de hooks del Overview no lo caza nadie | Añadir `test:all` (o al menos las páginas del wedge) al gate |
| E2E en CI | Solo `coherence-v1.spec.ts --project=chromium` en frontend-ci; `frontend-e2e.yml` corre la suite con Clerk pero **sin backend en :8000** (env apunta a localhost sin servicio) | workflows | Los journeys (upload→analyze→review) no se validan contra API real en CI | Job con backend dockerizado + seed, o journeys 100 % MSW deterministas |
| Cobertura del wedge | Existen `document-analysis-pipeline.spec.ts` y `journeys/journey-1-setup / journey-2-review` contra `proj_demo_001` (demo) | specs | El journey demo no puede detectar el hardcode de `contract` (la demo no sube de verdad) | E2E real: subir 3 ficheros con 3 tipos, esperar analyzed, ver finding, aprobar, exportar |
| A11y | `src/tests/accessibility` + spec S3-12 tablet | árbol | No corre como gate explícito visible | Añadir axe checks de las 6 pantallas wedge al job de integración |
| Visual regression | `core-pages.visual.spec.ts` + snapshots | árbol | Proyecto "visual-regression" no aparece en el gate de CI | Ejecutar en frontend-e2e con tolerancia |
| Contract drift | `generate:api:check` (Orval + git diff) en CI ✔ — buen gate | workflow `:157` | No cubre los clientes manuales (useBudget, fetchApiJson) | Migrar los manuales a generado |
| Tests como teatro | Tests de páginas montan con mocks que devuelven data inmediatamente (nunca atraviesan el estado loading→data que crashea) | `projects/[id]/page.test.tsx` (patrón) | Falsa seguridad | Tests de transición: primer render loading, segundo con data |

### Suite mínima para proteger el wedge (propuesta)

1. **E2E-W1 Upload triplete:** crear proyecto → subir PDF como *contract*, XLSX como *budget*, XLSX como *schedule* → los 3 aparecen con su tipo correcto y estado transiciona sin F5.
2. **E2E-W2 Análisis visible:** tras W1, el indicador de progreso aparece y termina; el score de coherence deja de ser "--".
3. **E2E-W3 Finding→evidencia:** click en un finding abre el visor con el highlight de la página correcta.
4. **E2E-W4 HITL:** aprobar un item registra el email real del usuario y el item cambia de estado; rechazar exige razón.
5. **E2E-W5 Export:** "Export audit report" descarga un fichero con score + findings aprobados + citas.
6. **UNIT-W6:** transición loading→data de Overview/Coherence sin crash (regresión Rules-of-Hooks).
7. **UNIT-W7:** `uploadDocument` rechaza tipos fuera del enum generado (regresión BOM/BUDGET).

---

## 12. Frontend Improvement Backlog

Prioridades: **P0 = antes de cualquier demo externa · P1 = MVP · P2 = beta privada · P3 = polish.**

| Priority | Improvement | Perspective | File(s) / Area | Product Value | User Value | Developer Value | Acceptance Criteria |
|---|---|---|---|---|---|---|---|
| **P0** | Selector de tipo de documento en upload (contract/budget/schedule/other, default por extensión) | Product, Final User | `DocumentUploadDropzone.tsx`, `lib/api/index.ts` | Desbloquea la cuña entera | Puede ensamblar el triplete | Elimina el mismatch BOM/BUDGET | Los 3 tipos llegan al backend correctos; XLSX como budget se parsea; E2E-W1 verde |
| **P0** | Fix crash Rules-of-Hooks en Overview | Developer, Final User | `projects/[id]/page.tsx:41-102` | Primera pantalla del proyecto utilizable | No más "Something went wrong" | Patrón corregido y testeado | UNIT-W6 verde; navegar a Overview con red lenta no crashea |
| **P0** | SSR de Coherence con auth (o pasar a client) | Developer | `lib/api/services/http.ts`, `coherence/page.tsx` | La página núcleo carga datos reales | Ve su score | Un solo camino de auth | Coherence carga con sesión Clerk real sin banner de error |
| **P0** | Purga de datos fabricados: assignees, clauseIds, distribución de severidad, alertCount por categoría, notificaciones fake, Status "Active", "Budget Used" | Product, Final User, Marketing | `alerts/page.tsx:25-49`, `CoherenceClient.tsx:148-171`, `AppHeader.tsx:53`, `projects/[id]/page.tsx:101,133` | Credibilidad del producto | Puede fiarse de lo que ve | Regla "no literals as data" | Grep de los literales citados = 0; donde falte dato real, placeholder honesto |
| **P0** | Identidad real en HITL y alerts (`reviewer_name`, `resolved_by` desde Clerk) | Final User, Product | `review/page.tsx:177,192`; `evidence/page.tsx:511` | Audit trail defendible | Su nombre en el registro | — | El backend recibe email/ID de Clerk; timeline muestra el nombre real |
| **P0** | Montar progreso de análisis (tracker simplificado o stepper) + polling de estado de documentos; eliminar link al SSE crudo | Product, Final User | `analysis/page.tsx:123-127`, `AnalysisProgressTracker`, documents | Paso 5 del wedge existe | Sabe que "está pasando algo" | Rescata 2 componentes huérfanos | Tras subir, el estado avanza sin F5; el link crudo desaparece |
| **P0** | Quitar de la landing: stats fabricadas, deploy marker; arreglar CTA `/signup` | Marketing | `landing-page-content.tsx` | Sin riesgo reputacional | Funnel correcto | — | "Get Started" aterriza en `/sign-up`; footer limpio |
| **P0** | Fix "Retry processing" sin auth | Developer | `documents/page.tsx:100-115` | Flujo de corrección funciona | Reintento efectivo | — | Retry devuelve 202 y estado cambia |
| **P1** | Export de informe de auditoría (score + findings aprobados + citas + validador + fecha) en PDF real | Product, Final User, Marketing | nueva pantalla + endpoint o generación client | **La salida de valor del producto** | Entregable para su comité | — | E2E-W5 verde; el PDF cita cláusula/página y quién aprobó |
| **P1** | Checklist visual del triplete (contract ✔ budget ✘ schedule ✘) en Documents y Overview + CTA contextual por etapa | Product | documents, overview | Guía el happy path | Siempre sabe el siguiente paso | — | Con triplete incompleto, el CTA apunta al tipo faltante |
| **P1** | Renderizar `categories_v2` (estado, evidencia faltante, conflictos, recomendación por categoría) | Product, Final User | `CoherenceClient.tsx`, `contracts.ts:50-75` | Explicabilidad = diferenciación | Entiende el porqué del score | Aprovecha contrato ya tipado | Cada categoría muestra status/missing_evidence/recommendation reales |
| **P1** | HITL: scoping por proyecto + card legible con link a evidencia (sustituir JSON crudo) | Final User | `review/page.tsx` | Gate usable | Decide con contexto | — | La cola filtra por proyecto; cada item enlaza a su evidencia |
| **P1** | Botón "Run/Re-run analysis" y "Evaluate coherence" (hooks generados ya existen) | Product | analysis, coherence | Control del usuario | Re-audita tras corregir | Usa código generado muerto | Tras re-subir un budget corregido, puede re-evaluar y ver el score cambiar |
| **P1** | Errores de mutación visibles (toast global en QueryClient) + quitar `catch {}` | Developer, Final User | `queryClient.ts`, review, budget, evidence | — | Nunca falla en silencio | Un patrón único | Toda mutación fallida muestra toast con mensaje |
| **P1** | Nav Nivel-1: ocultar AI Analytics/Observability/RACI/Stakeholders global tras flag o menú "More"; tabs de proyecto reducidos a Overview·Documents·Coherence·Findings·Review·Report(+Settings) | Product | `AppSidebar.tsx`, `ProjectTabs.tsx` | Foco en la cuña | Menos ruido | Menos superficie que mantener | Nav primaria ≤6 ítems; nada placeholder clicable |
| **P1** | Dashboard `/` dentro del shell (o restaurar `/dashboard`) + empty state con CTA "Create your first project" | Developer, Final User | `app/page.tsx`, `next.config.mjs` | Primera sesión coherente | No pierde el menú | Un árbol de layout | Dashboard siempre con sidebar; empty state con botón |
| **P1** | Unificar creación de proyecto (matar `/projects/new` o el wizard) y borrar templates/batch-import decorativos (o cablearlos) | Developer, Product | projects | Menos deuda | Un solo camino claro | −400 líneas | Un único flujo de creación; ningún dialog sin efecto |
| **P1** | CI: `test:all` como gate + 1 journey E2E del wedge con backend seed | Developer | workflows, package.json | Protege el Nivel-1 | — | Regresiones cazadas | frontend-ci falla si el wedge se rompe |
| **P2** | Budget: bloque de reconciliación (stated vs computed vs contract, delta %) usando los findings DET-BUD | Product, Final User | budget page | La demo estrella (2,8 %) visible en producto | Cost Controller convencido | — | Con el pilot cargado, muestra 636M vs 654M y el delta |
| **P2** | Tabs con estado activo + `aria-current`; tokens únicos de severidad; EmptyState común | Developer, Final User | ProjectTabs, ui/ | Consistencia | Orientación | Sistema de diseño real | Auditoría visual pasa; un solo mapeo severidad→color |
| **P2** | Onboarding: montar `OnboardingEntry` + sample project bootstrap en el primer login | Product, Marketing | features/onboarding (huérfano) | Time-to-value | Ve valor sin sus datos | Rescata código existente | Usuario nuevo puede cargar proyecto de ejemplo en 1 click |
| **P2** | Idioma consistente (decidir EN o ES; extraer strings) | Final User | toda la UI | Mercado objetivo ES | Sin mezcla EN/ES | Base i18n | 0 strings fuera del idioma elegido |
| **P2** | Búsqueda del header: cablear `GlobalSearch` (cmdk ya instalado) o quitar el input | Developer, Final User | AppHeader, GlobalSearch | — | Sin controles muertos | — | El input busca o no existe |
| **P3** | Quitar "3D Relationship View" y "Evidence Templates" (o convertirlos en filtros reales) | Product | evidence page | Seriedad | Menos gimmicks | −300 líneas | Evidence page enfocada en PDF+findings |
| **P3** | Trocear `projects/page.tsx` y `evidence/page.tsx` (<800 líneas por fichero) | Developer | ambos | — | — | Mantenibilidad | Cumple la regla del repo |
| **P3** | Página de Pricing/Contact + Privacy/Terms reales | Marketing | landing | Funnel B2B completo | — | — | Sin links `#` |

---

## 13. Proposed Level-1 UX Flow

### Proposed Flow

1. **Landing** → promesa del triplete + "Start your first audit" → Sign-up Clerk.
2. **Primer login** → `/projects` con empty state: "Create your first project" + opción "Explore a sample audit" (sample project bootstrap ya escrito).
3. **Crear proyecto** (un solo flujo: nombre, código, tipo, moneda) → redirect a Documents.
4. **Documents con Triplet Checklist:** tres slots visibles (Contract · Budget · Schedule). Cada upload exige tipo (pre-seleccionado por extensión). El checklist se va marcando; el CTA primario muta: "Upload budget" → "Upload schedule" → "Run coherence audit".
5. **Run audit** → tarjeta de progreso (4 etapas legibles: Reading documents → Cross-checking → Scoring → Ready) con polling/SSE; al terminar, CTA "View findings".
6. **Coherence dashboard:** score global + categorías v2 con estado/evidencia/recomendación; lista de findings ordenada por severidad real. Si falta un documento del triplete: score retenido + CTA al slot faltante (ya existe el banner — conservarlo).
7. **Finding → Evidence viewer:** cada finding abre el PDF con highlight en la cláusula/celda citada, mostrando ambos lados de la contradicción.
8. **Review (HITL) por proyecto:** cards con contexto humano + evidencia inline; aprobar (nota si confianza <90 %) / rechazar con razón; identidad Clerk registrada.
9. **Export Audit Report:** pantalla de composición (qué findings entran, resumen del score, validadores) → PDF descargable con citas y audit trail.
10. **Retorno:** `/projects` muestra "Last audited · score · findings pendientes de revisión" por proyecto; click continúa donde estaba.

### Required Screens

| Screen | Purpose | Required Content | Required Actions | Data Needed | Acceptance Criteria |
|---|---|---|---|---|---|
| Documents + Triplet Checklist | Ensamblar el triplete | 3 slots con estado por tipo; registro de docs con estado vivo | Upload tipado, delete, retry, re-upload | `GET/POST project documents` (tipo correcto), polling status | Usuario monta el triplete sin instrucciones externas |
| Audit Progress | Confianza durante el proceso | 4 etapas + % + errores legibles | Cancel/retry | SSE o polling de pipeline | Nunca hay una espera ciega >5 s |
| Coherence Findings | Núcleo del valor | Score + categorías v2 + findings con severidad real y doble cita | Ordenar/filtrar; abrir evidencia; re-evaluar | dashboard + categories_v2 + alerts con evidence_location | Un CM entiende cada finding sin ayuda |
| Evidence Viewer (existente, podado) | Prueba | PDF + highlights + entidades | Validar entidad, aprobar/rechazar alert | ya cableado | Cada finding con evidencia navega a su página exacta |
| Review Queue (proyecto) | Gate humano | Cards con contexto + evidencia + SLA | Approve (nota <90 %) / Reject (razón) | HITL API + identidad Clerk | Audit trail con nombre real; cola solo del proyecto |
| Export Audit Report | Salida de valor | Resumen score, findings aprobados/rechazados, citas, validadores, fecha | Configurar secciones; descargar PDF | findings aprobados + metadata HITL | PDF defendible ante un tercero |
| Projects (retorno) | Continuidad | Score, delta, pendientes de revisión por proyecto | Abrir en el último estado | list + summary | Volver tras una semana no exige re-orientarse |

### Required UI Components

| Component | Purpose | Current Exists? | Reuse / Build | Acceptance Criteria |
|---|---|---|---|---|
| `DocumentTypeSelect` en dropzone | Tipar cada upload | ❌ (upload hardcodea contract) | Build (pequeño) | Enum = `DocumentType` generado; default por extensión |
| `TripletChecklist` | Estado del triplete | ❌ | Build | 3 estados por tipo; CTA al faltante |
| `AuditProgressCard` | Progreso legible | Parcial (`AnalysisProgressTracker`/`ProcessingStepper` huérfanos) | Reuse + simplificar (4 etapas, sin N1-N17) | Conectado a SSE/polling real |
| `FindingCard` | Finding entendible | Parcial (`AlertReviewCenter` sin evidencia real) | Rebuild ligero | Severidad real, doble cita, CTA evidencia |
| `CategoryV2Panel` | Explicabilidad del score | ❌ (contrato tipado sin UI) | Build | Renderiza status/missing_evidence/recommendation |
| `ReviewItemCard` | HITL con contexto | Parcial (JSON crudo) | Rebuild ligero | Humano-legible + link evidencia + identidad |
| `AuditReportComposer` | Export | ❌ | Build | PDF con citas + validadores |
| `EmptyState` | Consistencia | ❌ (ad-hoc) | Build (1 componente) | Usado en dashboard/projects/documents/coherence |
| `PdfEvidenceViewer` | Prueba | ✅ sólido | Reuse | — |
| `CoherenceGauge`/`BreakdownChart`/`RadarView` | Score | ✅ | Reuse (deduplicar carpetas) | Una sola copia canónica |

---

## 14. Suggested Frontend Copy and UX Messaging

La UI está en inglés; se propone copy EN (mercado EPC internacional) — si se decide ES para el pilot español, traducir consistentemente (hoy hay mezcla).

| Screen | Current Messaging Problem | Suggested Copy |
|---|---|---|
| Landing hero | Subhead lista 6 categorías internas; stats fabricadas | H1: *"Your contract says one thing. Your budget and schedule say another."* · Sub: *"C2Pro cross-examines all three documents of your EPC project and flags every contradiction with clause-level evidence — before it becomes a claim."* |
| Dashboard empty state | "No projects found. Create a project to see coherence data." (estilo error, sin botón) | *"Start your first coherence audit. Create a project and upload its contract, budget and schedule — C2Pro will find what doesn't add up."* + botón **Create project** |
| New project | "Enter your project details. You can upload contracts and documents after creation." | *"Name your project. Next you'll upload the three documents C2Pro audits: contract, budget and schedule."* |
| Document upload | "Upload contracts, schedules, budgets, or BC3 files" (sin roles ni tipo) | *"Each document plays a role: the **contract** sets the promises, the **budget** the money, the **schedule** the time. Tag each file so C2Pro can cross-check them."* |
| Processing state | Inexistente (o jerga "17-node LangGraph pipeline") | *"Auditing your documents — reading (1/4), cross-checking (2/4), scoring (3/4), preparing findings (4/4). This usually takes a few minutes."* |
| Coherence dashboard intro | Banner interno "Coherence Score v1 is active…" | *"Coherence Score: how well your contract, budget and schedule agree. Below,每 category shows what evidence supports it — and what's missing."* (eliminar el banner de versiones) |
| Finding/evidence explanation | Alert = frase suelta; review = JSON | *"**What conflicts:** Contract clause 12.3 caps penalties at 5 %; schedule milestone M4 implies 8 % exposure. **Why it matters:** … **Suggested action:** …"* + link *View evidence (p. 41)* |
| AUDIT_INCOMPLETE banner | Enum interno visible | *"Score withheld: this audit is missing the **budget** and **schedule**. Upload them to unlock the full Coherence Score."* (mantener CTA actual) |
| HITL review instructions | "approve or reject analysis findings" sin contexto | *"You are the final gate. Approve findings that are correct, reject those that aren't — your name and decision become part of the audit trail."* |
| Export report CTA | Inexistente | *"**Export audit report** — a signed PDF with your Coherence Score, every approved finding and its evidence, ready for your steering committee."* |
| Error state (API) | "Verify the backend coherence endpoints are available." | *"We couldn't load this project's data. Retry — if it persists, contact support (error ID included)."* |
| Security/trust (footer login + landing) | Ausente | *"Tenant-isolated storage · PII removed before any AI processing · Human approval on every finding · Your documents never train models."* |

---

## 15. First 7-Day Frontend Action Plan

| Day | Action | Perspective | File(s) / Area | Acceptance Criteria |
|---|---|---|---|---|
| 1 | Fix crash Rules-of-Hooks (Overview) + fix retry sin auth + quitar link SSE crudo | Developer | `projects/[id]/page.tsx`, `documents/page.tsx`, `analysis/page.tsx` | Overview carga con red real; retry devuelve 202 |
| 1 | Barrido landing: stats fabricadas fuera, deploy marker fuera, CTA → `/sign-up`, título de pestaña | Marketing | `landing-page-content.tsx`, `app/layout.tsx` | Landing sin claims no verificables ni artefactos internos |
| 2 | Selector de tipo de documento + alinear unión de tipos con enum generado | Product | `DocumentUploadDropzone.tsx`, `lib/api/index.ts` | Un XLSX puede subirse como budget y se parsea |
| 2-3 | Purga de datos fabricados (assignees, clauseIds, distribución severidad, notifs, Status, Budget Used) | Final User | alerts, coherence, header, overview | Greps de literales = 0; placeholders honestos |
| 3 | Identidad Clerk en HITL/alerts (`reviewer_name`, `resolved_by`) | Final User | review, evidence | Backend recibe email real |
| 4 | SSR auth de Coherence (token server-side) o conversión a client | Developer | `http.ts`, coherence page | Pestaña Coherence carga sin banner de error |
| 4-5 | Triplet checklist v1 en Documents (3 slots + estado) + polling de estado | Product | documents | El triplete se ensambla y su estado avanza sin F5 |
| 5 | Montar AuditProgressCard (simplificación del tracker huérfano) tras upload | Product | analysis/documents | Progreso visible de subida→analyzed |
| 6 | Ocultar AI Analytics/Observability/RACI de la nav (flag); dashboard dentro del shell | Product | AppSidebar, app/page.tsx | Nav ≤6 ítems; `/` con sidebar |
| 7 | E2E del wedge (W1-W4 de §11) corriendo local contra backend seed + `test:all` en CI | Developer | workflows, specs | Pipeline falla si el wedge se rompe |

---

## 16. First 30-Day Frontend MVP Plan

| Workstream | Goal | Required Changes | Acceptance Criteria |
|---|---|---|---|
| **A. Cierre del loop Nivel-1** | El recorrido completo desde la UI sin tocar la API a mano | Upload tipado + checklist (semana 1); Run/Re-run analysis + Evaluate coherence cableados a hooks generados; progreso; re-upload arreglado (bug PATCH 500 coordinado con backend) | Un usuario nuevo completa proyecto→triplete→audit→findings→review en <30 min sin soporte |
| **B. Findings con evidencia** | Confianza | Render `categories_v2`; FindingCard con doble cita; severidades reales end-to-end; evidence deep-links desde findings y review | Cada finding responde "qué choca con qué y dónde" |
| **C. Export de informe** | Salida de valor | `AuditReportComposer` + generación PDF (endpoint backend preferido; fallback client con librería seria, no print popup) con score, findings aprobados, citas, validadores, fecha | PDF entregable a un comité; E2E-W5 verde |
| **D. Higiene y foco** | Percepción enterprise | Purga de fakes (semana 1); consolidación de componentes (3 raíces→1); severidad tokenizada; EmptyState común; idioma unificado; nav podada; borrar placeholders (GlobalSearch/CrossModuleNavigator) o cablearlos | Cero controles muertos; cero datos sintéticos; una sola estética |
| **E. Calidad como gate** | No regresar | `test:all` + journey E2E wedge con backend en CI; tests de transición loading→data; axe en pantallas wedge | frontend-ci rojo si el wedge se rompe |
| **F. Marketing mínimo honesto** | Funnel B2B | Landing reescrita (mensaje §8), demo alineada al triplete con findings de ejemplo, sección trust, Privacy/Terms reales | Demo pública enseña la cuña real; sin claims sin fuente |

---

## 17. Final Recommendation

1. **¿Listo para usuarios externos?** **No.** Bloqueadores objetivos: triplete inconstruible desde la UI (upload hardcodeado a `contract`), crash en la Overview de proyecto, página Coherence con fetch SSR sin credenciales, audit trail HITL con identidad ficticia (`current-user`), y datos fabricados (assignees, clauses, severidades) mezclados con reales.

2. **¿Soporta la cuña Nivel-1?** **Parcialmente (2/5).** Las piezas existen — auth multi-tenant real, registro de documentos, score de coherence, visor de evidencia con highlights, cola HITL, 249 ficheros de test — pero el flujo se corta en la subida (paso 4), no hay progreso visible (paso 5) y no hay salida de informe (paso 9). Es un conjunto de pantallas conectadas a APIs reales, no un recorrido.

3. **Antes de una demo seria (P0, ~1 semana):** selector de tipo de documento; fix del crash de Overview; fix SSR de Coherence; purga total de datos fabricados; identidad real en HITL; progreso de análisis visible; landing sin métricas inventadas ni deploy marker; retry de procesamiento funcional.

4. **Antes del MVP (P1, ~30 días):** export de informe de auditoría (la salida de valor); findings explicables con `categories_v2` y doble cita; re-run de análisis/evaluación desde la UI; errores de mutación visibles; checklist del triplete; navegación podada al Nivel-1; CI que proteja el wedge.

5. **Quitar, ocultar o des-enfatizar:** AI Analytics y Observability fuera de la nav de usuario (son paneles de operador); RACI ya está tras flag (bien) — aplicar lo mismo a Stakeholders global, Kanban, batch import, project/evidence templates decorativos, "3D Relationship View", input de búsqueda del header, items muertos del menú de usuario, banner "Coherence Score v1 is active", y las rutas `/demo` si no se realinean a la cuña.

6. **¿Refinar o rediseñar?** **Refinar, no rediseñar.** La arquitectura (App Router + Orval + Clerk + shadcn), el design system base y el Evidence viewer valen; el problema no es la estética sino (a) tres decisiones de integración rotas (upload type, SSR auth, identidad HITL), (b) datos decorativos, y (c) superficie sin foco. Es trabajo de cirugía dirigida (~6-8 semanas-persona hasta MVP), no de reescritura. Un rediseño ahora destruiría la inversión real en tests, móvil y accesibilidad ya hecha.

---

## 18. Refinement Question

¿Quieres que convierta este análisis en un **segundo prompt de implementación para Claude Code**, con tareas frontend parche-a-parche (P0 → P1), cada una con ficheros exactos, tests de aceptación (incluida la suite mínima del wedge de §11) y criterios de done verificables — lista para integrarse con IDs en `C2PRO_MASTER_BACKLOG.md`?
