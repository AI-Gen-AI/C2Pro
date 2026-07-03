# C2Pro — Síntesis Multi-Modelo de Due Diligence y Hoja de Ruta de Consenso

**Fecha:** 14 de junio de 2026 **Informes recibidos (6):** ChatGPT, Gemini, Kimi, Kimi-Perplexity, GLM-5.1, Claude. _(El prompt menciona un séptimo informe — Grok — pero no se adjuntó; no se incluye en esta síntesis.)_ **Método de esta síntesis:** No me limito a comparar opiniones. Volví a clonar el repositorio **completo** (`git fetch --unshallow`, sin límite de profundidad) y **verifiqué contra el código real** cada afirmación factual en disputa. Donde un informe acertó, lo digo; donde alucinó, lo demuestro con evidencia del repo. Esto incluye **corregir un dato erróneo de mi propio informe previo** (ver §0).

---

## 0. Nota metodológica y corrección de datos (importante)

Mi primer análisis usó un clon superficial (`--depth 50`), lo que truncó el historial y me llevó a afirmar **“121 commits, ~1 mes de historia, repo reinicializado el 2026-05-09”**. **Eso era incorrecto.** Con el historial completo:

|Dato|Mi informe previo (erróneo)|**Verdad verificada esta sesión**|Quién acertó|
|---|---|---|---|
|Nº de commits|121|**740**|ChatGPT (738) ✅|
|Primer commit|2026-05-09|**2025-12-29** (~5,5 meses)|GLM-5.1 (“~6 meses, ene-2026”) ✅|
|Autoría|118 fundador + 3 bot|**612 fundador (3 grafías) + 114 “Claude” (Claude Code) + 90 co-authored + 13 dependabot + 1 v0**|—|
|Tags de release|(implicaba ninguno)|**Existen:** `v1.0.0-milestone-e2e`, `v1.0.0-rag-milestone`|—|

**Conclusión de la corrección:** el proyecto **no** es de 1 mes; tiene ~5,5 meses de trabajo continuo. El **bus factor sigue siendo 1** (un humano), pero está **co-desarrollado intensamente por agentes de IA** (114 commits firmados literalmente por “Claude”, 90 co-autoría). Esto _refuerza_ la observación “heavily AI-assisted” pero _corrige_ la narrativa de “maqueta reinicializada”.

---

## 1. Evaluación informe por informe

### 🥇 ChatGPT — _El más riguroso y mejor fundamentado_

- **Mejores aportes (verificados):** detectó `continue-on-error` en CI, `--cov-fail-under=0`, el script raíz `test` falso, el conflicto de licencia **ISC vs Proprietary**, los flags `C2PRO_SKIP_HITL`/`C2PRO_AI_MOCK`, el modelo de cláusula “sintética” (una sola `Clause` por documento), el cutover v2 incompleto, y el **conteo de commits correcto (738)**. Marco estratégico fuerte: _Evidence Graph_ + reposicionar como _Contract-to-Procurement Intelligence_.
- **Supuestos más débiles:** dijo que el umbral de cobertura “no es un gate” — **parcialmente falso**: hay `cov-fail-under=0` en 2 sitios, pero **70 en 5 y 90 en 2**. Algunas cifras (1 star, 0 forks) provienen de la web, no del código.
- **Conservar:** casi todo. **Rechazar/matizar:** la generalización “CI no bloquea nada”.

### 🥇 GLM-5.1 — _El otro informe genuinamente leído sobre código_

- **Mejores aportes (verificados):** dos `core/`, dos `ai/`, dos sistemas de migración; duplicación `modules/coherence` vs `coherence`; `gamification/` y `golden/` como **código muerto** (confirmado: 0 referencias en `main.py`); **shadow-mode v2 que descarta resultados** quemando tokens; `model_routing.yaml` (Haiku/Sonnet/Opus); clasificación Capa 1/2 con escalado LLM; bus factor = 1; edad real ~6 meses. Su **tabla de completitud por componente** es la mejor del conjunto.
- **Supuestos más débiles:** dijo `procurement/` “scaffold vacío/no iniciado” — **matiz**: está **cableado pero detrás de feature-flag** (2 referencias en `main.py`). “Sin rate limiting en endpoints IA” — existe infraestructura de rate limiting (`core/middleware/rate_limiter.py`); falta verificar cobertura en `/coherence`·`/analysis`. Frontend “30%” es duro (hay ~52.7k LOC TS y 34 rutas).
- **Conservar:** casi todo. **Rechazar:** nada grave; sólo matizar “dead modules” (procurement no lo es).

### 🥈 Claude (mi informe previo) — _Preciso salvo el dato de historial_

- **Mejores aportes (verificados):** el hallazgo de seguridad **más preciso** — `.env.staging` con **`service_role` (bypassa RLS), `JWT_SECRET_KEY` y `DATABASE_URL`**, JWTs de formato real, en el historial (`cc9d080`), pese a que `.gitignore` sí ignora `.env.*` (fue forzado). El **gap del producto P0** mejor identificado: **la dimensión “cronograma” no alimenta el scoring** (`TASK-BCK-064`) → la promesa “tridimensional” es hoy bidimensional. Cuantificación de higiene (`.mypy_cache` = 1.418 ficheros, ~29%). Insight: el _honest scoring_ (devolver `null` en vez de inventar 0/100) como foso de confianza.
- **Supuesto más débil (corregido):** **“121 commits / 1 mes / repo reinicializado”** — erróneo por clon superficial (ver §0).
- **Conservar:** seguridad, gap de cronograma, dual-engine, higiene. **Corregir:** edad/commits.

### 🥉 Kimi-Perplexity — _Bueno en higiene, flojo en verificación de código_

- **Mejores aportes (verificados):** enumeración precisa de basura en raíz (`nombre prueba`, `=2.0.0`, `{.txt`, `blackboard.json` 126KB, `stablish only 5…txt` 211KB, el PDF de HVPNL, el fichero con ruta Windows corrupta), dual lockfile, **sin LICENSE**.
- **Supuestos incorrectos (refutados):** “**No hay CI/CD**” → **falso** (15 workflows). “**No hay OpenAPI**” → **falso** (`docs/api/openapi.yaml`). Confunde “Gate 5 al 65%” con “motor inexistente”. Identifica HVPNL como entidad **holandesa** → **es india** (Haryana Vidyut Prasaran Nigam Ltd.).
- **Conservar:** lista de higiene. **Rechazar:** “sin CI”, “sin OpenAPI”, lectura de “motor incompleto”.

### ❌ Kimi — _Conclusiones centrales equivocadas (no leyó el código)_

- **Problema raíz:** admite al final que _“some inferences were made where code was not directly accessible”_. Concluyó que **no existen**: el motor de coherencia, Celery, RAG, pgvector, evals, CI. **Todos refutados:** `core/tasks/celery_app.py`, `alembic/…add_clause_embeddings.py`, `apps/api/evals`, 15 workflows, motor `coherence/scoring.py` (897 LOC). Puntuó **AI Design 3/10 (“área más débil”)** → es exactamente lo contrario: es el área **más madura**.
- **Conservar:** un par de ideas estratégicas independientes válidas (ICP aguas arriba: prestamistas/aseguradoras; flywheel de datos; HITL como producto). **Rechazar:** casi todos los “critical findings” y “quick wins” (recomiendan construir lo que ya existe).

### ❌❌ Gemini — _Alucinación casi total — rechazar en bloque_

- **Problema raíz:** **no analizó este repositorio**. Inventó un producto distinto: _“C2Pro (Command & Control Professional for Generative AI)”_, un “agent operating system” con _swarms_, _WASM sandbox_, _Temporal.io_, _agent mesh networks_, _race conditions in agent state_… Nada de esto existe ni guarda relación con C2Pro (inteligencia contractual EPC). El nombre expandido es fabricado.
- **Conservar:** sólo coincidencias genéricas y accidentales (añadir `SECURITY.md`, `.gitignore`, pre-commit, logging estructurado). **Rechazar:** las 25 _findings_, la TAM “$15B”, la arquitectura propuesta y todo el marco.

---

## 2. Extracción de consenso

### A. Coinciden TODOS los que leyeron el repo (y es VERDAD verificada)

- `.env.staging` commiteado es un incidente **crítico**.
- Higiene del repo catastrófica (basura en raíz, `.mypy_cache`, PDF real, transcripciones, dual lockfile).
- El proyecto **no es invertible tal cual**, pero el _wedge_ es real → limpiar + pilotos + ingresos.
- Backend más maduro que frontend; falta observabilidad cableada (Sentry DSN).
- LICENSE ausente/ambigua.

### B. Coinciden la mayoría (verificado)

- **Coherence Score™ es el activo novedoso / componente más fuerte** (ChatGPT, GLM, Claude). _Kimi disiente, pero Kimi se equivoca._
- Bus factor = 1 (GLM, Claude, ChatGPT implícito).
- Cutover v2 incompleto / shadow mode activo.
- Duplicación arquitectónica (dual `core`/`ai`/`coherence`/migraciones).
- Reposicionar como inteligencia **vertical** (no framework de agentes).

### C. Lo menciona uno solo, pero es importante

- **(Claude)** La dimensión _cronograma_ no contribuye al score (`TASK-BCK-064`) → la promesa “tridimensional” es hoy **bidimensional**. _Hallazgo de producto más infravalorado del conjunto._
- **(GLM)** El shadow-mode v2 **descarta resultados** → coste de tokens sin retorno hasta el cutover.
- **(GLM/Kimi)** ICP **aguas arriba**: prestamistas/aseguradoras de construcción tienen más dolor y presupuesto que el contratista.
- **(ChatGPT)** Modelo de cláusula demasiado grueso (1 cláusula sintética por documento) → bloquea trazabilidad legal granular.
- **(Claude, memoria de dominio)** Riesgo de **novedad absoluta UE** para patente: una divulgación pública (defensa de TFM, o este repo público) puede comprometer la patentabilidad del método. _No es asesoría legal; verificar con IP counsel._

### D. Contradicciones entre informes (resueltas en §6)

Nº commits/edad · ¿existe el motor? · score de AI Design · ¿hay CI? · ¿hay RAG/pgvector/Celery/evals? · origen de HVPNL · marco de producto (vertical vs agent-OS) · ¿backend sobre-ingenierizado o no construido?

### E. Afirmaciones que requerían verificación → **ya resueltas esta sesión** (ver §3)

---

## 3. Ponderación de evidencia

Clasificación de cada afirmación mayor, con la evidencia del repo verificada esta sesión.

|Afirmación|Clase|Evidencia (verificada)|
|---|---|---|
|`.env.staging` con `service_role`+`JWT_SECRET`+`DATABASE_URL`|**Evidence-backed**|JWTs HS256 reales (208/219 chars); en `cc9d080`; `.gitignore` ignora `.env.*`|
|`.mypy_cache` (1.418 ficheros, ~29%), PDF, transcripciones, dual lockfile en repo|**Evidence-backed**|`git ls-files`|
|Licencia contradictoria: `package.json`=**ISC**, README=**Proprietary**, sin `LICENSE`|**Evidence-backed**|`grep license package.json` + ausencia de fichero|
|Script raíz `test` = `echo "Error: no test specified" && exit 1`|**Evidence-backed**|`package.json`|
|CI con `continue-on-error: true`|**Evidence-backed**|`tests.yml`, `real-document-operability.yml`, `ai-agent-swarm.yml`|
|“Cobertura sin gate”|**Misleading (parcial)**|`cov-fail-under=0` ×2, pero **=70 ×5, =90 ×2**|
|Flags `C2PRO_SKIP_HITL`/`C2PRO_AI_MOCK` permiten saltar HITL/usar mock|**Evidence-backed**|en `analysis/…/graph/nodes.py`, `workflow.py`, `anthropic_client.py`|
|740 commits; primer commit 2025-12-29; ~5,5 meses|**Evidence-backed**|historial completo (unshallow)|
|Motor de coherencia maduro (v2, honest scoring) = componente más fuerte|**Evidence-backed**|`coherence/scoring.py` (897 LOC); ADR-009|
|Dimensión cronograma **no** alimenta el score|**Evidence-backed**|`TASK-BCK-064` (P0, su propio backlog)|
|`gamification/` y `golden/` = código muerto|**Evidence-backed**|0 referencias en `main.py`|
|`procurement/` cableado pero feature-flagged|**Evidence-backed**|2 referencias en `main.py`|
|Existen Celery, pgvector/clause-embeddings, evals, OpenAPI, model router|**Evidence-backed**|rutas confirmadas (refuta a Kimi/Kimi-P)|
|Frontend = “shell / sin rutas”|**Incorrect**|52.697 LOC TS, 34 rutas `page.tsx`|
|“Sin CI/CD” / “Sin OpenAPI” (Kimi/Kimi-P)|**Incorrect**|15 workflows; `docs/api/openapi.yaml`|
|“Sin rate limiting” (Kimi)|**Misleading (parcial)**|existe `core/middleware/rate_limiter.py`; cobertura en rutas IA = _verificar_|
|Checkpointer degrada a memoria en fallo (ChatGPT/GLM)|**Plausible-unverified**|citan `TASK-BCK-051`/try-except; no tracé el código línea a línea|
|Celery en el mismo contenedor que la API (GLM)|**Plausible-unverified**|afirmado vía `start.sh`; no verifiqué el arranque|
|Cláusula “sintética” única por documento (ChatGPT)|**Plausible-unverified**|coherente con el diseño; no tracé el nodo|
|Producto = “agent OS / swarms” (Gemini)|**Incorrect / alucinado**|el repo es inteligencia contractual vertical|
|AI Design 3/10 “área más débil” (Kimi)|**Incorrect**|es el área más madura (7–8/10)|
|TAM $15B (Gemini), $50B bull (Kimi/GLM)|**Speculative**|sin estudio de mercado|
|Pivot a prestamistas/aseguradoras; flywheel de datos; HITL-as-product|**Plausible-unverified**|hipótesis estratégicas razonables|

### Scorecard de consenso (excluyendo Gemini por no fundamentado; con Kimi ponderado a la baja)

|Categoría|Consenso /10|Comentario|
|---|--:|---|
|Architecture|6.5|DDD hexagonal sólido, lastrado por duplicación de generaciones|
|Code Quality|5.0|Núcleo excelente; raíz y código muerto lo hunden|
|Security|5.0|Diseño 7–8 (RLS, PII, gitleaks), pero `.env.staging` lo tapa|
|**AI Design**|**7.5**|Honest scoring, router, Capa 1/2, evidencia — lo más fuerte|
|Product Strategy|6.5|ICP nítido y foso de dominio; falta GTM/ingresos|
|Scalability|4.5|Monolito + Celery; sin historia de escalado horizontal|
|Maintainability|4.5|Disciplina de backlog/ADR alta; 280k LOC con 1 humano|
|Documentation|6.5|Extensa pero con _drift_ y mezcla ES/EN|
|Innovation|7.5|Coherence Score + estado `null` honesto = novedad real|
|Enterprise Readiness|3.0|Multi-tenant/RLS bien; sin SLA/observabilidad/legal|
|**Global**|**~5.5**|Núcleo fuerte, bordes inacabados, deuda de higiene|

---

## 4. Consolidación de la hoja de ruta (5 fases)

### Fase Inmediata — 0–14 días · _Contención y credibilidad_

1. **Rotar y purgar secretos** de `.env.staging` (`service_role`, `JWT_SECRET`, `DATABASE_URL`) + reescritura de historial (`git filter-repo`).
2. **Resolver la licencia**: decidir Proprietary vs open-source, corregir `package.json` (hoy ISC) y **añadir fichero `LICENSE`** + `SECURITY.md`.
3. **Des-basurizar el repo**: eliminar de seguimiento `.mypy_cache`, `.pytest-tmp`, `playwright-report`, `test-results`, `tmp-gh-artifacts`, `backups`, `temp_conflicting_frontend_files`, transcripciones `.txt`, `=2.0.0`, `nombre prueba`, fichero con ruta Windows; consolidar a **un solo lockfile** (pnpm).
4. **Retirar el PDF de HVPNL** del historial → almacenamiento con control de acceso (riesgo confidencialidad/legal).
5. **Blindar producción**: prohibir `C2PRO_SKIP_HITL`/`C2PRO_AI_MOCK` y el fallback in-memory del checkpointer en prod.
6. **Higiene CI mínima**: quitar `continue-on-error` de los _gates_ que deben bloquear; subir los `cov-fail-under=0` a un umbral real; arreglar `test` raíz; resolver el submódulo roto (`worktrees/sentry-perf-gemini`, issue de CI).

### Fase Corta — 15–45 días · _Estabilización de arquitectura + cierre del MVP_

7. **Cerrar la promesa tridimensional**: cablear la dimensión **cronograma** al scoring (`TASK-BCK-064`).
8. **Terminar el cutover v1→v2** (canary 10→50→100 con guard de MAE) y **detener el shadow-mode** o conectarlo a un panel que lo aproveche.
9. **Consolidar la duplicación**: decidir explícitamente _congelar_ o _migrar_ `analysis/`+`modules/`; unificar `core/`, `ai/`, `coherence/` y los dos sistemas de migración.
10. **Observabilidad**: cablear Sentry (DSN) + métricas; cerrar tareas de seguridad pendientes (RLS de `clause_embeddings`, guards de cookie-consent).
11. **Eliminar código muerto** (`gamification/`, `golden/`) tras verificar 0 imports.
12. **Separar el worker Celery** en su propio contenedor; confirmar rate limiting en `/coherence`·`/analysis`.

### Fase Media — 46–90 días · _Productización y endurecimiento IA_

13. **Extracción de cláusulas con IDs estables** (sustituir la “cláusula sintética” única) → trazabilidad de evidencia por hallazgo.
14. **Capa de evals como gate**: ampliar el golden corpus; métricas de precisión/recall y de citación; registro de prompts versionado (LangSmith Hub).
15. **UX de confianza**: panel con estados “evidencia insuficiente”, export PDF/Excel de auditoría, onboarding “3 documentos → score en <5 min”.
16. **Landing + pricing + billing (Stripe)**; **2–3 design partners EPC** sobre documentos reales anonimizados.

### Fase Larga — 3–6 meses · _Enterprise-readiness y monetización_

17. SSO/SAML, exportación de audit log, retención por tenant, runbook de incidentes, pruebas de carga, primeras certificaciones (SOC 2 Tipo I).
18. **Multi-idioma** (ES/EN, luego PT/FR/DE) para LATAM/EMEA.
19. Cobro recurrente real; primeros ingresos; **reducir bus factor** (segundo ingeniero).
20. **Patente provisional antes de divulgación pública** (cronograma TFM ↔ novedad UE).

### Fase Futura — 6–12 meses · _Evolución de plataforma_

21. Integraciones (Procore/Autodesk/Primavera), **change-order / coherencia incremental**, benchmarking anónimo (efecto red), API “Coherence Score”, evaluación de ICP aguas arriba (aseguradoras/prestamistas), posible servidor MCP, fine-tuning de dominio.

---

## 5. Matriz de decisión

|Iniciativa|Impacto|Esfuerzo|Riesgo|Confianza|Dependencias|Prioridad|
|---|--:|--:|--:|--:|---|---|
|Rotar + purgar secretos `.env.staging`|10|2|3|**Alta (verif.)**|—|**P0**|
|Resolver licencia + `LICENSE`/`SECURITY.md`|8|1|2|**Alta**|—|**P0**|
|Des-basurizar repo + lockfile único|7|2|2|**Alta**|—|**P0**|
|Retirar PDF HVPNL del historial|8|2|4|**Alta**|filter-repo|**P0**|
|Blindar `SKIP_HITL`/`AI_MOCK`/checkpointer en prod|8|3|4|Media-alta|—|**P0**|
|Cablear cronograma al scoring (`TASK-BCK-064`)|9|6|5|**Alta (su backlog)**|ingestión schedule|**P1**|
|Terminar cutover v2 + cortar shadow|8|6|5|**Alta**|adapter v1→v2|**P1**|
|Consolidar dual `core`/`ai`/`coherence`/migraciones|7|7|6|**Alta**|decisión freeze/migrate|**P1**|
|Observabilidad (Sentry/métricas) + SEC pendientes|7|4|3|**Alta**|DSN/operador|**P1**|
|CI: quitar `continue-on-error`, subir cobertura|6|3|3|**Alta**|—|**P1**|
|Separar contenedor Celery + rate limit en IA|6|4|4|Media|infra deploy|**P1**|
|Eliminar `gamification`/`golden` (0 imports)|4|2|2|**Alta**|grep verify|**P1**|
|Extracción de cláusulas con IDs estables|9|8|6|Media-alta|—|**P2**|
|Evals como gate + registro de prompts|8|6|4|Media-alta|golden corpus|**P2**|
|Landing/pricing/billing + design partners|9|6|6|Media|UX, legal|**P2**|
|SSO/SAML, audit export, SOC 2 Tipo I|7|9|6|Media|—|**P3**|
|Multi-idioma documental|6|6|4|Media|—|**P3**|
|Integraciones Procore/Autodesk; change-order|9|9|7|Baja-media|API, partners|**P3**|
|Patente provisional pre-divulgación|8|3|7|Media (legal)|IP counsel|**P2**|

---

## 6. Resolución de desacuerdos

1. **Nº de commits / edad.** ChatGPT (738, 6 meses) vs Claude previo (121, 1 mes). → **Mejor soportado: ChatGPT/GLM.** Evidencia: historial completo = **740 commits, primer commit 2025-12-29**. _Recomendación: usar 740/~5,5 meses; mi cifra previa queda corregida._
2. **¿Existe el motor de coherencia?** Kimi (no) vs todos los demás (sí, el más fuerte). → **Soportado por evidencia: sí existe** (`coherence/scoring.py`, ADR-009). _Rechazar Kimi._
3. **Score AI Design.** Kimi 3/10 vs GLM 8 / Claude 7. → **GLM/Claude.** Es el área más madura. _Consenso 7–8._
4. **¿Hay CI/RAG/pgvector/Celery/evals/OpenAPI?** Kimi/Kimi-P (no) vs ChatGPT/GLM/Claude (sí). → **Sí, todo verificado.** _Rechazar las negaciones._
5. **Origen de HVPNL.** Kimi-P (holandesa) vs Claude (india). → **India** (Haryana Vidyut Prasaran Nigam Ltd.). _Dato menor, pero corregido._
6. **Marco de producto.** Gemini (agent-OS/swarms) vs resto (inteligencia contractual vertical EPC). → **Vertical.** _Rechazar Gemini en bloque._
7. **¿Backend sobre-ingenierizado o no construido?** Kimi (“CRUD sin motor”) vs GLM/ChatGPT/Claude (“backend sobre-ingenierizado vs UX/GTM fino”). → **Lo segundo.** El backend (incl. el motor) está muy desarrollado; lo escaso es GTM, ingresos y partes del frontend.
8. **¿`procurement` muerto?** GLM (scaffold vacío) vs realidad. → **Cableado pero feature-flagged** (no muerto). En cambio `gamification`/`golden` **sí** están muertos. _Matizar GLM._

**Evidencia adicional necesaria (no resuelta esta sesión):** trazas línea-a-línea del fallback in-memory del checkpointer, del arranque mono-contenedor de Celery, de la cobertura de rate limiting en rutas IA, y del modelo de cláusula único. Son **plausibles** (vienen de los dos informes fiables) pero no las verifiqué a nivel de código.

---

## 7. Hoja de ruta de consenso (formato ejecutable)

> Se detallan las iniciativas P0/P1; las P2/P3 siguen el patrón de §4–5.

**7.1 Purga de secretos (P0)**

- **Meta:** que ninguna credencial viva permanezca en el repo ni en el historial.
- **Por qué importa:** `service_role` bypassa RLS; `JWT_SECRET` permite forjar tokens. Descalifica cualquier DD.
- **Owner:** Founder/Sec.
- **Tareas:** rotar las 3 credenciales en Supabase/infra → `git filter-repo` sobre un mirror → forzar push coordinado → gate CI que falle ante cualquier `.env.*` salvo `.example`.
- **Aceptación:** `git log -p` sin secretos; `git ls-files | grep '\.env'` solo muestra `.example`; credenciales nuevas en gestor de secretos.
- **Complejidad:** Baja-media · **Riesgo:** Medio (reescritura de historial) · **Deps:** ninguna.

**7.2 Licencia y gobierno legal (P0)**

- **Meta:** postura legal coherente. **Por qué:** hoy el badge dice Proprietary, `package.json` dice ISC (¡permisiva!), y no hay `LICENSE`.
- **Tareas:** decidir modelo → alinear `package.json` → añadir `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODEOWNERS`.
- **Aceptación:** un único modelo de licencia consistente en todos los surfaces.
- **Complejidad:** Baja · **Riesgo:** Bajo.

**7.3 Des-basurización (P0)**

- **Meta:** repo que parezca el trabajo senior que hay debajo. **Por qué:** ~29% son ficheros de caché; transcripciones y PDF erosionan credibilidad en 10 minutos.
- **Tareas:** `git rm -r --cached` de cachés/artefactos/temp; borrar transcripciones y ficheros basura; un solo lockfile; `.gitignore` endurecido.
- **Aceptación:** raíz limpia; `git ls-files '.mypy_cache/*' | wc -l` = 0.
- **Complejidad:** Baja · **Riesgo:** Bajo.

**7.4 Cronograma → scoring (P1)**

- **Meta:** que “tridimensional” sea cierto. **Por qué:** hoy `score_missing_dimensions=["schedule"]` tras subir cronograma (`TASK-BCK-064`).
- **Owner:** Backend/IA. **Tareas:** reconciliar ingestión de cronograma con el motor; tests de integración con cronograma real.
- **Aceptación:** un proyecto con contrato+cronograma+presupuesto produce score que **usa** las tres dimensiones; no quedan dimensiones “missing” espurias.
- **Complejidad:** Media-alta · **Riesgo:** Medio · **Deps:** pipeline de ingestión.

**7.5 Cutover v2 + consolidación de motores (P1)**

- **Meta:** un solo motor autoritativo; cero duplicación. **Por qué:** dos generaciones (`coherence` vs `modules/coherence`) acopladas vía `analysis/` multiplican la matriz de test y el coste de shadow.
- **Owner:** Arquitecto. **Tareas:** completar canary v2; cortar/aprovechar shadow; decidir freeze vs migrate de `analysis/`+`modules/`; unificar `core`/`ai`/migraciones; renumerar ADRs (hay dos ADR-004; faltan 007/008).
- **Aceptación:** un único path de scoring en `main.py`; un diagrama de arquitectura que coincide con el código.
- **Complejidad:** Alta · **Riesgo:** Medio-alto.

**7.6 Observabilidad + endurecimiento prod (P1)**

- **Meta:** dejar de volar a ciegas y cerrar escotillas. **Tareas:** Sentry DSN + métricas; prohibir `SKIP_HITL`/`AI_MOCK`/fallback memoria en prod; cerrar SEC pendientes; separar Celery; verificar rate limit en IA; quitar `continue-on-error` de gates críticos.
- **Aceptación:** errores en Sentry; CI bloquea regresiones reales; flags de bypass imposibles en prod.
- **Complejidad:** Media · **Riesgo:** Medio.

---

## 8. Preparación para agentes CLI (segunda pasada de ejecución)

### 8.1 Desglose de tareas por agente (especialización)

- **Agente A — Seguridad/Historial:** purga de secretos + PDF; gate anti-`.env`.
- **Agente B — Higiene/Repo:** des-tracking de cachés/artefactos; lockfile único; `.gitignore`; licencia/gobierno.
- **Agente C — CI/Calidad:** quitar `continue-on-error`; subir `cov-fail-under`; arreglar `test` raíz y submódulo roto.
- **Agente D — Arquitectura/Consolidación:** decisión freeze/migrate; unificación `core`/`ai`/migraciones; retirar `gamification`/`golden`.
- **Agente E — Producto/Coherencia:** cronograma→scoring; cutover v2; IDs de cláusula.
- **Agente F — Observabilidad/Prod:** Sentry/métricas; blindaje de flags; Celery; rate limit.

### 8.2 Orden seguro (dependencias)

A (seguridad) → B (higiene) → C (CI verde y bloqueante) → **luego en paralelo** D, F → **al final** E (cambios de comportamiento del producto, con CI ya fiable).

### 8.3 Ficheros/módulos a inspeccionar **primero**

`.env.staging` · `.gitignore` · `.gitleaks.toml` · `package.json` · `.github/workflows/*` · `apps/api/src/main.py` · `apps/api/src/coherence/scoring.py` · `apps/api/src/coherence/adapters/v1_to_v2.py` · `apps/api/src/analysis/**` · `apps/api/src/modules/**` · `apps/api/src/core/{ai,tasks,middleware}/**` · `docs/architecture/decisions/009-*.md` · `C2PRO_MASTER_BACKLOG.md`.

### 8.4 Comandos de verificación (solo lectura / tests; sin cambios destructivos)

```
git ls-files | grep -E '\.env'                      # solo .example debe aparecer
git ls-files '.mypy_cache/*' | wc -l                # debe ser 0 tras limpieza
grep -rn 'continue-on-error: true' .github/workflows # 0 en gates críticos
grep -rn 'cov-fail-under=0' .github/workflows        # 0
grep -rn 'C2PRO_SKIP_HITL\|C2PRO_AI_MOCK' apps/api/src # solo tras guard de entorno
grep -c 'gamification\|golden' apps/api/src/main.py  # 0 (confirmar muerto antes de borrar)
cd apps/api && pytest -q                             # suite completa verde (~4.574 tests)
cd apps/web && pnpm test && pnpm build               # frontend verde + build
make openapi && git diff --exit-code docs/api/openapi.yaml  # sin drift de OpenAPI
```

### 8.5 Estrategia de ramas

Trunk-based con ramas cortas desde `main`; **branch protection** (PR obligatorio, CI verde, ≥1 review). La purga de historial se hace en un **mirror** y se coordina (no en la rama de trabajo). Considerar **repo privado** hasta cerrar P0 y la patente.

### 8.6 Secuencia de PRs (un concern por PR)

PR-1 secretos+gate (idealmente en privado) → PR-2 PDF fuera de historial → PR-3 higiene/lockfile → PR-4 licencia/gobierno → PR-5 CI endurecido → PR-6 retirar código muerto → PR-7 consolidación de motores → PR-8 cronograma→scoring → PR-9 observabilidad/blindaje.

### 8.7 Expectativas de test automatizado

Suite Python completa verde y **bloqueante**; tests de frontend + build verdes; `cov-fail-under` ≥70 donde hoy es 0; sin drift de OpenAPI; nuevos tests para cronograma→scoring y para los guards de entorno.

### 8.8 Guardarraíles (evitar daño)

- **Nunca** `git push --force` sin mirror de respaldo y sin sign-off humano; la reescritura de historial es irreversible.
- **Nunca** commitear secretos; rotar siempre antes de purgar (purgar no “des-filtra” una credencial ya expuesta).
- **No borrar** un módulo sin `grep` que confirme **0 imports** y CI verde.
- **Un concern por PR**; no mezclar limpieza con cambios de comportamiento.
- **No tocar** lógica de scoring sin la capa de evals/tests delante.
- **No desactivar** RLS/PII/HITL ni introducir bypasses nuevos.
- Cambios de arquitectura (freeze/migrate) **requieren ADR** previo.

---

## 9. Preguntas abiertas (solo las que cambian decisiones)

1. **Licencia:** ¿Proprietary cerrado u open-core? Determina el fichero `LICENSE`, el badge y si el repo debe ser privado.
2. **HVPNL:** ¿es un cliente/relación real o un documento de prueba? Define si es activo comercial (caso de estudio) o pasivo legal a purgar.
3. **Patente:** ¿hay defensa de TFM o publicación inminente? Por novedad absoluta UE, condiciona si el repo debe pasar a privado **ya** y si la provisional va antes.
4. **`analysis/`+`modules/`:** ¿congelar (producto enfocado) o migrar (plataforma agéntica)? Decide semanas de trabajo y qué se borra.
5. **ICP:** ¿contratista EPC (dolor operativo) o prestamista/asegurador (más presupuesto, aguas arriba)? Cambia GTM, pricing y features.
6. **Cronograma→scoring:** ¿está realmente cerrado por PR #155 o sigue abierto (`TASK-BCK-064`)? Hay riesgo de **drift backlog↔PR**: verificar en entorno vivo.

---

# Consenso final

### La acción más importante (una sola)

**Rotar y purgar del historial las credenciales de `.env.staging` (service_role + JWT secret + DATABASE_URL) hoy mismo.** Es el único hallazgo que, por sí solo, descalifica cualquier due diligence — y está verificado contra el repo. Todo lo demás es recuperable en semanas; una clave `service_role` filtrada, no.

### Top 5 prioridades de ejecución

1. **Cerrar P0 de seguridad/legal/higiene** (secretos, PDF, licencia, basura, blindaje de flags).
2. **Hacer cierta la promesa “tridimensional”** (cronograma→scoring, `TASK-BCK-064`).
3. **Terminar el cutover v2 y consolidar la duplicación** de motores/`core`/`ai`/migraciones.
4. **Cablear observabilidad y endurecer CI** (Sentry, sin `continue-on-error`, cobertura real).
5. **Conseguir 2–3 design partners EPC + landing/pricing** para convertir el TFM en prueba comercial.

### Top 5 riesgos

1. **Bus factor = 1** (un humano + agentes IA) — el riesgo que más penaliza un inversor.
2. **Postura de seguridad/legal** — secretos filtrados + licencia contradictoria.
3. **Commoditización / “AI wrapper”** — Procore/Autodesk podrían añadir la función; el foso debe ser los _evaluators_ + dominio, no el stack.
4. **Núcleo incompleto vs sobre-ingeniería** — cronograma sin cablear y backend sobredimensionado frente a UX/GTM.
5. **Sin ingresos/pilotos + ciclos lentos de construcción + timing de patente UE.**

### Top 5 oportunidades estratégicas

1. **Coherence Score™ como categoría/estándar nombrado** y como **API** embebible (el _honest scoring_ como sello de confianza).
2. **Reposicionar como “Contract-to-Procurement Intelligence”** para EPC, con **grafo de evidencia** y trazabilidad legal por cláusula.
3. **ICP aguas arriba** (aseguradoras/prestamistas) como comprador de mayor valor y urgencia.
4. **HITL + audit trail como producto enterprise** y **flywheel de datos** (corpus propietario de cláusulas/incoherencias).
5. **Experticia de dominio del fundador + bilingüe ES/EN** como foso difícil de copiar (LATAM/EMEA infraservidos).

### Prompt recomendado para la segunda pasada con agentes CLI

> _“Actúa como un equipo de agentes de ingeniería senior sobre el repo `AI-Gen-AI/C2Pro`. Trabaja en este orden estricto y con un PR por tarea, sin mezclar limpieza con cambios de comportamiento. **(1)** Sin tocar el remoto aún, audita y lista todo secreto en `.env.staging` y prepara un plan de rotación + `git filter-repo` sobre un mirror; añade un gate CI que falle ante cualquier `.env.*` salvo `.example`. **(2)** Saca `HVPNL_*.pdf` del historial. **(3)** Quita de seguimiento `.mypy_cache`, `.pytest-tmp`, `playwright-report`, `test-results`, `tmp-gh-artifacts`, `backups`, `temp_conflicting_frontend_files` y las transcripciones `.txt`; deja un único lockfile (pnpm); endurece `.gitignore`. **(4)** Resuelve la licencia (alinea `package.json`, añade `LICENSE`/`SECURITY.md`). **(5)** Quita `continue-on-error` de los gates críticos, sube los `cov-fail-under=0`, arregla el script `test` raíz y el submódulo roto. **(6)** Verifica con `grep` 0 imports y retira `gamification/` y `golden/`. **(7)** Redacta un ADR que decida congelar o migrar `analysis/`+`modules/` y empieza la consolidación de `core/`·`ai/`·migraciones. **(8)** Cablea la dimensión cronograma al scoring (`TASK-BCK-064`) con tests de integración. **(9)** Cablea Sentry y prohíbe `C2PRO_SKIP_HITL`/`C2PRO_AI_MOCK` y el fallback in-memory del checkpointer en producción. Guardarraíles: nunca `--force` sin respaldo ni sign-off; rota antes de purgar; no borres módulos sin confirmar 0 imports y CI verde; no toques la lógica de scoring sin la capa de evals delante; no desactives RLS/PII/HITL. Tras cada PR, ejecuta `pytest -q` en `apps/api`, `pnpm test && pnpm build` en `apps/web` y comprueba `make openapi` sin drift; no abras el siguiente PR hasta que CI esté verde.”_

---

_Esta síntesis se basa en los 6 informes aportados y en una verificación directa contra un clon completo del repositorio realizada en esta sesión. Donde un informe y el código discrepan, prevalece el código. La principal corrección sobre mi propio análisis previo (historial real de 740 commits desde 2025-12-29, no 121 en 1 mes) está documentada en §0._