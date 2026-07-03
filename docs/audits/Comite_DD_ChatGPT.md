## Premisa del comité

No trato los informes como “verdad”, sino como **hipótesis**. El consenso solo se acepta cuando coincide con evidencia del repositorio o con varios informes bien fundamentados. Además, hay una limitación: algunas síntesis afirman haber clonado el repositorio completo y medido commits/LOC, pero yo no debo aceptar esas cifras como absolutas si no están verificadas por evidencia directa en esta sesión. Sí puedo usarlas como **evidencia secundaria**.

---

# Phase 1 — Report Quality Assessment

## 1. ChatGPT

|Dimensión|Score|
|---|--:|
|Evidence Quality|7.5|
|Repository Awareness|7.5|
|Technical Depth|7|
|Architectural Rigor|7|
|Product Insight|8.5|
|Security Insight|7|
|Actionability|8|
|Hallucination Risk|Medium|

**Strongest contributions:** detecta bien CI débil, licencia contradictoria, `pnpm test` falso, `continue-on-error`, `cov-fail-under=0`, riesgo de cache AI sin tenant/version/schema y propone el eje “Evidence Graph Platform”. Varios de esos puntos están respaldados por código: el README declara licencia propietaria, mientras `package.json` declara `ISC`; el script raíz `test` falla por diseño; y el workflow usa `--cov-fail-under=0` y `continue-on-error`.

**Weakest contributions:** algunas puntuaciones de completitud son estimaciones sin metodología; “coverage no es gate” debe matizarse si otros workflows tienen thresholds reales. La propia síntesis de Claude corrige que no todos los gates de cobertura son cero.

**Unique contributions:** posicionar C2Pro como **Contract-to-Procurement Intelligence** y no como “Contract AI” genérico; identificar el Evidence Graph como núcleo defendible.

---

## 2. Claude

|Dimensión|Score|
|---|--:|
|Evidence Quality|8|
|Repository Awareness|8|
|Technical Depth|8|
|Architectural Rigor|7.5|
|Product Insight|6.5|
|Security Insight|8.5|
|Actionability|7|
|Hallucination Risk|Low-Medium|

**Strongest contributions:** según las síntesis, Claude aportó los hallazgos más fuertes en seguridad, higiene, scoring y cronograma. La síntesis de Claude corrige además su propio error inicial de historial por clon superficial y afirma que el historial completo muestra unos 740 commits y ~5,5 meses de trabajo.

**Weakest contributions:** parte de sus cifras —commits, LOC, número de archivos basura— deben tratarse como **evidencia secundaria** hasta reproducirlas localmente. Además, su análisis parece menos fuerte en go-to-market.

**Unique contributions:** posible `.env.staging` con `service_role`, `JWT_SECRET_KEY` y `DATABASE_URL`; bug `TASK-BCK-064` sobre cronograma; valor del “honest null-state”; posible riesgo de patentabilidad UE. La exposición de secretos no debe publicarse ni reabrirse en la respuesta: basta con tratarla como P0 a verificar/rotar.

---

## 3. GLM-5.1

|Dimensión|Score|
|---|--:|
|Evidence Quality|7|
|Repository Awareness|7.5|
|Technical Depth|7.5|
|Architectural Rigor|7|
|Product Insight|6|
|Security Insight|7|
|Actionability|7.5|
|Hallucination Risk|Medium|

**Strongest contributions:** detecta duplicación de módulos, migraciones paralelas, posible Celery en mismo contenedor, shadow mode v2 que desperdicia tokens, y módulos muertos como `gamification`. Varias síntesis lo consideran de los informes más cercanos al código.

**Weakest contributions:** algunas afirmaciones quedan como **plausibles pero no verificadas**: Celery en el mismo contenedor, shadow mode “quemando tokens” y porcentajes de completitud por componente. También hay recomendaciones de enterprise governance que pueden ser prematuras.

**Unique contributions:** detección operativa de `start.sh` / Celery + API, dos sistemas de migración, módulos duplicados y shadow-mode v2.

---

## 4. Kimi

|Dimensión|Score|
|---|--:|
|Evidence Quality|3|
|Repository Awareness|3.5|
|Technical Depth|4|
|Architectural Rigor|5|
|Product Insight|6|
|Security Insight|4|
|Actionability|5|
|Hallucination Risk|High|

**Strongest contributions:** buen instinto crítico: “pre-producto”, “coherencia 3D como problema de grafos”, foco en cliente aguas arriba como prestamistas/inversores, y alerta contra inflar roadmap.

**Weakest contributions:** parece haber negado o infravalorado componentes que sí existen: CI, OpenAPI, Celery, pgvector/evals/model router según otras síntesis. La síntesis de Claude/Kimi-Perplexity afirma que Kimi trabajó con una visión superficial y que su AI Design 3/10 es demasiado bajo.

**Unique contributions:** hipótesis estratégica de que el comprador podría estar aguas arriba —prestamistas, aseguradoras, inversores— y no solo contratistas/EPC. Mantener como hipótesis, no como roadmap.

---

## 5. Kimi/Perplexity

|Dimensión|Score|
|---|--:|
|Evidence Quality|6.5|
|Repository Awareness|6|
|Technical Depth|5|
|Architectural Rigor|5.5|
|Product Insight|7|
|Security Insight|6|
|Actionability|7|
|Hallucination Risk|Medium|

**Strongest contributions:** muy útil en higiene de repositorio: nombres concretos de basura en raíz, artefactos de runtime, dual lockfile, posible PDF HVPNL y `.env.staging`.

**Weakest contributions:** peor en profundidad de código; algunas afirmaciones como “sin CI/CD” o “sin OpenAPI” aparecen refutadas por otras síntesis y por evidencia del repo. El repositorio tiene workflow de tests y OpenAPI documentado.

**Unique contributions:** valor del MCP server, posible oportunidad de “Coherence-as-a-Service”, y limpieza detallada de raíz. Útil, pero no debe desplazar los P0 técnicos.

---

## 6. Gemini

|Dimensión|Score|
|---|--:|
|Evidence Quality|1.5|
|Repository Awareness|1|
|Technical Depth|4|
|Architectural Rigor|4|
|Product Insight|2|
|Security Insight|3|
|Actionability|2|
|Hallucination Risk|Very High|

**Strongest contributions:** algunos patrones generales —durable state machine, circuit breakers, sandboxing— podrían servir en un futuro lejano.

**Weakest contributions:** según varias síntesis, Gemini evaluó otro producto: un “Command & Control Professional for Generative AI” / agent OS con swarms, WASM y Temporal. Eso no corresponde al C2Pro real, que es una plataforma vertical de inteligencia contractual.

**Unique contributions:** Temporal/WASM/local model routing. Comité: **descartar por ahora** salvo como ideas futuras.

---

## 7. Grok

|Dimensión|Score|
|---|--:|
|Evidence Quality|5|
|Repository Awareness|5.5|
|Technical Depth|5.5|
|Architectural Rigor|6|
|Product Insight|5.5|
|Security Insight|5|
|Actionability|6|
|Hallucination Risk|Medium|

**Strongest contributions:** parece equilibrado, reconoce valor del motor de coherencia y trabajo de seguridad ya realizado.

**Weakest contributions:** demasiado generoso en seguridad —Architecture 8.0 y Security 8.5 en una síntesis— y menos crítico con higiene. Otra síntesis propone bajar seguridad a 6.5 por `.env.staging`, pero el comité la bajaría aún más si se confirma `service_role`.

**Unique contributions:** propone una ruta 0–14 / 15–45 / 46–90 días razonable, pero aún demasiado cercana a roadmap final.

---

# Phase 2 — Cross-Report Comparison

## Universal Agreement — HIGH confidence

1. **No está listo para producción enterprise.**  
    Evidencia: workflows con `continue-on-error`, real document gate manual/mock, backlog con seguridad pendiente y QA manual pendiente.
    
2. **La arquitectura base existe y no es una maqueta trivial.**  
    Evidencia: diseño v4.1 declara monorepo `apps/api` + `apps/web`, modular monolith y boundaries hexagonales.
    
3. **El Coherence Score / evidence-aware scoring es el activo técnico más prometedor.**  
    Evidencia: README y roadmap lo sitúan como núcleo; PRs recientes corrigen problemas de scoring nulo/coverage/coherence.
    
4. **La higiene del repositorio es un problema de credibilidad.**  
    Evidencia secundaria fuerte en informes; evidencia directa parcial en issue #141 sobre worktree/submodule roto y en docs que ordenan qué debe ir a `docs`, `archive` y `sandbox`.
    
5. **Hay brecha entre la visión declarada y el estado real.**  
    El README habla de auditoría tridimensional y Sprint S2 65%; el backlog todavía lista tareas P0/P1 pendientes en scoring, seguridad y QA.
    

---

## Emerging Consensus — MEDIUM confidence

1. **La dimensión cronograma puede no estar correctamente integrada en scoring.**  
    Base: `TASK-BCK-064` en backlog indica que schedule parsea pero no contribuye a coherence; PR #155 afirma haberlo corregido. Comité: **probable gap histórico, estado actual requiere revalidación runtime**.
    
2. **AI Design no es 3/10 ni 8/10 global.**  
    Hay LangGraph, model router, PII anonymization y structured output, pero faltan prompt registry, evals sistemáticos, red-team y traceabilidad de prompt/modelo.
    
3. **El cache AI está infra-escopeado.**  
    Evidencia: key hash usa prompt, system, model, temperature y max_tokens; no se ve tenant/schema/prompt version en la key.
    
4. **Auth stack ambiguo.**  
    Evidencia: README/API README hablan de Supabase/JWT; `config.py` incluye campos Clerk. No implica necesariamente bug, pero sí deuda de decisión arquitectónica.
    

---

## Significant Disagreements

### Disagreement 1 — ¿Qué tan maduro es el motor AI?

**Position A:** Kimi: AI Design débil, sin RAG/evals/prompt versioning.  
**Position B:** Claude/GLM/ChatGPT: Coherence/AI core existe y es uno de los activos más fuertes.  
**Evidence available:** LangGraph N1–N17, Anthropic wrapper, model router, real workflow, scoring hotfixes.  
**Evidence missing:** ejecutar evals, revisar `scoring.py`, comprobar datasets y métricas reales.  
**Committee position:** **Lean B**, con matiz: núcleo AI 6–7/10; plataforma AI enterprise 4–5/10.

### Disagreement 2 — ¿Seguridad 4/10 o 8/10?

**Position A:** Grok/Kimi dan más peso a RLS/JWT/tests.  
**Position B:** Claude/GLM/ChatGPT penalizan higiene, secretos y operaciones.  
**Evidence available:** RLS/security existe como intención; pero backlog de seguridad sigue abierto y CI no bloquea todo.  
**Evidence missing:** confirmar localmente `.env.staging`, si contiene secretos reales, si fueron rotados y si se purgó historia.  
**Committee position:** **Lean B**. Seguridad actual 4–5/10 hasta resolver exposición y hardening.

### Disagreement 3 — ¿Producto tri-dimensional o bi-dimensional?

**Position A:** README/visión: Contrato + Cronograma + Presupuesto.  
**Position B:** informes críticos: schedule no alimenta score o fue bug reciente.  
**Evidence available:** README declara tri-dimensional; backlog lista `TASK-BCK-064`; PR #155 afirma fix.  
**Evidence missing:** test runtime con contrato + schedule + budget.  
**Committee position:** **Undecided actual / Lean “históricamente bi-dimensional”**.

### Disagreement 4 — ¿Invertible hoy?

**Position A:** “Condicionalmente sí” por potencial.  
**Position B:** “No hoy” por higiene, secretos, bus factor, ausencia de tracción y producción no lista.  
**Evidence available:** producto no enterprise-ready, workflows no bloqueantes, real-doc gate manual.  
**Evidence missing:** usuarios, ingresos, design partners, demo estable.  
**Committee position:** **Lean B**: no invertible institucionalmente hoy; sí puede ser pre-seed/founder-led si se corrigen P0.

---

# Phase 3 — Hallucination Audit

|Claim|Source|Risk|Reason|
|---|---|--:|---|
|C2Pro es “Command & Control Professional for Generative AI” / agent OS|Gemini|Very High|Contradice README y arquitectura real de Contract Intelligence.|
|No hay CI/CD|Kimi/Kimi-P en algunas síntesis|High|Existe `.github/workflows/tests.yml` con jobs de tests y gitleaks.|
|No hay OpenAPI|Kimi-P según síntesis|High|Hay generación/OpenAPI mencionada en PR #149 y docs API.|
|AI Design 3/10 como conclusión global|Kimi|Medium-High|Ignora LangGraph, model router, wrapper y scoring work.|
|Security 8.5/10|Grok|Medium|Puede valorar diseño, pero no pondera suficientemente higiene/secretos/backlog.|
|Commit count 118/121 como definitivo|Claude previo|Medium|La propia síntesis de Claude lo corrige por clon superficial.|
|`.env.staging` con secretos reales|Claude/GLM/Kimi-P|Medium|Riesgo crítico, pero el comité no debe reexponer secretos; verificar localmente y rotar.|
|Temporal/WASM como prioridad|Gemini|High|Arquitectura fantasy para fase actual; no está soportado por necesidad presente.|
|TAM de decenas de billones|varios|High|Sin estudio de mercado; descartar para planificación.|

## Recommendations to discard

- Reconstruir el core sobre Temporal.io.
    
- WASM sandbox como iniciativa actual.
    
- Microservicios/Kafka/RabbitMQ como rediseño inmediato.
    
- SSO/SAML/SOC2 como P0 si aún no hay pilotos con datos reales.
    
- “Abrir todo el repo” sin resolver licencia, secretos e IP.
    
- Usar claims de mercado/TAM sin validación.
    
- Vender “tridimensional” hasta validar runtime con schedule + budget + contract.
    

---

# Phase 4 — Confidence-Based Findings

## Tier 1 — High confidence

- C2Pro es una plataforma vertical de Contract/Procurement Intelligence, no un agent framework genérico.
    
- Existe arquitectura monorepo con backend FastAPI y frontend Next/React declarados.
    
- La arquitectura canónica declara modular monolith y boundaries hexagonales.
    
- CI existe, pero parte del CI no bloquea correctamente.
    
- Root `test` script no ejecuta tests reales.
    
- Real document operability es manual/operator-only y usa mock flag por defecto.
    
- Hay licencia contradictoria: README Proprietary vs `package.json` ISC.
    
- Hay backlog de seguridad pendiente.
    

## Tier 2 — Medium confidence

- Secretos comprometidos en `.env.staging`: tratar como P0 hasta demostrar lo contrario.
    
- Schedule no contribuye plenamente al scoring: histórico probable, estado actual pendiente de runtime.
    
- Coherence v2 cutover incompleto: soportado por PR #152 y backlog, pero necesita traza actual.
    
- Celery + API mismo contenedor: plausible, verificar `start.sh` / deploy config.
    
- Frontend menos maduro que backend: plausible, pero necesita revisión de rutas UX reales.
    

## Tier 3 — Low confidence

- Patentabilidad UE comprometida: posible, pero requiere abogado de IP.
    
- Prestamistas/aseguradoras como ICP principal: interesante, no validado.
    
- Coherence-as-a-Service API como producto standalone: prometedor, pero prematuro.
    
- Golden corpus como moat: lógico, pero requiere datos reales y gobernanza.
    
- MCP server como canal de distribución: oportunidad futura, no P0.
    

---

# Phase 5 — Consensus Roadmap Refinement

No es un roadmap final. Son **candidatos**.

|Initiative|Evidence Strength|Impact|Effort|Confidence|
|---|---|--:|--:|--:|
|Verificar/rotar/purgar posibles secretos `.env*`|Medium-High, riesgo catastrófico|Very High|Medium|High|
|Limpiar root, caches, worktrees, artefactos|High|High|Low-Med|High|
|Corregir licencia + `LICENSE` + `SECURITY.md`|High|High|Low|High|
|Eliminar `continue-on-error` en gates release|High|High|Low|High|
|Convertir real-doc gate en prueba reproducible|High|Very High|Medium|High|
|Validar schedule + budget + contract runtime|High|Very High|Medium|High|
|Tenant/scope/version en AI cache keys|High|High|Low-Med|High|
|Blindar `C2PRO_SKIP_HITL` y mocks en prod|High|High|Low|High|
|Consolidar auth decision: Supabase/Clerk/JWT|Medium|High|Medium|Medium|
|Prompt registry + prompt/model traceability|Medium|High|Medium|Medium-High|
|Evidence Graph / stable clause IDs|Medium|Very High|High|Medium|
|Celery deployment split|Medium|Medium|Low-Med|Medium|
|Product demo synthetic E2E|Medium|High|Medium|Medium|
|Patent/IP counsel|Low-Med|Potentially High|Low|Medium|
|MCP/Coherence API|Low|Medium-High|Medium|Low-Med|

## Items requiring validation before entering roadmap

- Temporal/WASM/microVM.
    
- BIM/IFC integration.
    
- Stripe/billing.
    
- SOC2 formal.
    
- Open-core/community edition.
    
- Full marketplace/white-label.
    
- Fine-tuning domain LLM.
    
- ICP prestamista/aseguradora como target principal.
    

---

# Phase 6 — Expert Committee Review

## CTO

**Agree:** no producción, CI no bloqueante, limpieza y seguridad antes de features.  
**Challenge:** no aceptaría “80% coherence engine” sin runtime.  
**Needs:** demo E2E reproducible, branch protection, deployment config.  
**Prioritize:** secretos, CI, real-doc gate, production fail-closed.

## Principal Engineer

**Agree:** modular monolith es correcto; no microservicios aún.  
**Challenge:** duplicación `core/ai/coherence` puede ser normal durante migración, no necesariamente deuda crítica.  
**Needs:** import graph, dead code scan, dependency map.  
**Prioritize:** consolidar rutas críticas y eliminar broad fallbacks silenciosos.

## Product Lead

**Agree:** el wedge debe ser Contract-to-Procurement Intelligence.  
**Challenge:** “prestamistas/aseguradoras” es hipótesis atractiva, no validada.  
**Needs:** 5–10 entrevistas reales, demo sintética, caso de uso cerrado.  
**Prioritize:** un flujo: contrato + cronograma + presupuesto → hallazgos trazables → PDF.

## Security Lead

**Agree:** cualquier secreto real en historial es P0.  
**Challenge:** RLS/JWT/PII no compensan una god-key filtrada.  
**Needs:** gitleaks full history, rotación, prueba de no exposición, SECURITY.md.  
**Prioritize:** purga/rotación, prod flags, cache tenant-safe.

## AI Systems Architect

**Agree:** AI core existe, pero no está todavía gobernado como sistema enterprise.  
**Challenge:** “AI Design 3/10” es injusto; “8/10” también.  
**Needs:** eval harness, prompt registry, per-output provenance, red-team prompt injection.  
**Prioritize:** traceability + evals + stable evidence IDs.

---

# Phase 7 — Questions For Repository Verification

1. ¿Existe actualmente `.env.staging` o secretos en la rama principal o historial Git? ¿Fueron rotados?
    
2. ¿El flujo real contrato + cronograma + presupuesto produce score con las tres dimensiones activas?
    
3. ¿Qué rutas siguen usando Coherence v1 vs v2?
    
4. ¿El shadow mode v2 ejecuta llamadas LLM reales y descarta resultados?
    
5. ¿`C2PRO_SKIP_HITL` y `C2PRO_AI_MOCK` están bloqueados en producción?
    
6. ¿Las cache keys AI incluyen tenant, prompt version, schema version y model version?
    
7. ¿Qué sistema de auth es canónico: Supabase Auth, Clerk o JWT custom?
    
8. ¿El Real Document Operability workflow puede pasar sin intervención manual y sin mocks?
    
9. ¿Celery worker se despliega separado de API en staging/producción?
    
10. ¿Qué porcentaje de endpoints Swagger ha sido verificado en entorno vivo?
    
11. ¿Hay prompt registry real con IDs inmutables?
    
12. ¿Existe eval dataset con métricas por tarea?
    
13. ¿Los findings tienen stable clause IDs y evidencia trazable?
    
14. ¿Qué artefactos/archivos de raíz están versionados indebidamente?
    
15. ¿Hay design partners o usuarios reales que validen el caso de uso?
    

---

# Phase 8 — Consensus Maturity Score

|Area|Confidence|
|---|--:|
|Architecture|75%|
|Product|60%|
|Security|55%|
|AI Design|70%|
|Maintainability|65%|
|Scalability|45%|
|Roadmap|50%|

## Overall Consensus Confidence

**63%**

No sube más porque faltan tres evidencias decisivas: verificación de secretos/historial, ejecución runtime E2E con tres documentos, y confirmación del estado real de Coherence v2.

---

# Final Output

## What We Know

- C2Pro es una plataforma vertical de inteligencia contractual/procurement, no un agent OS genérico.
    
- Tiene arquitectura real: FastAPI, Next.js, Supabase/PostgreSQL, Redis, R2, Anthropic, LangGraph y módulos de analysis/coherence/documents/projects/HITL.
    
- El repo no está listo para producción enterprise.
    
- Hay CI, pero algunos gates permiten fallos o tienen thresholds débiles.
    
- La documentación declara más madurez de la que el backlog/workflows demuestran.
    
- La licencia está contradictoria.
    
- El Real Document Operability gate no es todavía una prueba automática fuerte.
    
- El Coherence Score es el principal activo técnico/producto.
    

## What We Think We Know

- Probablemente hubo o hay secretos sensibles en `.env.staging`; debe tratarse como incidente hasta descartar.
    
- El producto fue históricamente bi-dimensional aunque se presentaba como tri-dimensional; hay que validar si PR #155 lo cerró realmente.
    
- El AI core es más maduro que lo que Kimi dijo, pero menos enterprise-ready que lo que Grok/GLM sugieren.
    
- El frontend probablemente está menos maduro que el backend, aunque no es una shell vacía.
    
- Hay sobrecarga de documentación, artefactos y deuda de velocidad asistida por IA.
    

## What We Do Not Know Yet

- Si las credenciales fueron rotadas y purgadas del historial.
    
- Si el flujo E2E real funciona con documentos no mock.
    
- Si schedule/budget/contract alimentan realmente el score en producción.
    
- Qué rutas usan Coherence v1/v2.
    
- Si los outputs AI son reproducibles por prompt/model/schema version.
    
- Si hay usuarios/design partners reales.
    
- Si la estrategia ICP correcta es EPC/procurement o prestamistas/aseguradoras.
    

## What Must Be Verified Next

1. `gitleaks detect --no-git` y `gitleaks detect` contra historial completo.
    
2. Test runtime: contrato + cronograma + presupuesto → score + findings + evidencia.
    
3. Auditoría de Coherence v1/v2 routing.
    
4. Revisión de cache key AI.
    
5. Verificación de production flags para HITL/mock/checkpointer.
    
6. Limpieza y conteo real de artefactos versionados.
    
7. Confirmación de auth canónica.
    
8. Validación de una demo sintética end-to-end.
    

## Committee Verdict

**Requires Runtime Investigation**

Justificación: ya hay suficiente evidencia para descartar “roadmap final” y “producción enterprise”, pero todavía no hay suficiente evidencia runtime para saber si el producto puede soportar un piloto real. La siguiente verdad no está en más informes LLM: está en ejecutar el flujo completo con documentos controlados, revisar logs, confirmar scoring tridimensional, validar seguridad y comprobar que la UI/API devuelven resultados trazables.

---

# Consensus Delta

La evidencia que más aumentaría la confianza del comité sería un **paquete de verificación reproducible** con:

1. Resultado de secret scan completo + rotación/purga documentada.
    
2. Ejecución E2E con tres documentos sintéticos: contrato, cronograma y presupuesto.
    
3. Captura de qué dimensiones alimentan el Coherence Score.
    
4. Trazabilidad de un finding hasta cláusula/evidencia/documento.
    
5. CI verde sin `continue-on-error` en gates release.
    
6. Decisión documentada de auth y deployment.